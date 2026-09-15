# Bot Telegram RAG — Data Ekonomi Jawa Tengah (BPS)

Bot Telegram yang menjawab pertanyaan seputar **data ekonomi Provinsi Jawa Tengah**
menggunakan pola **RAG (Retrieval-Augmented Generation)**: data resmi diambil dari
**BPS Web API**, disimpan sebagai vektor di **ChromaDB**, lalu dijawab secara natural
oleh **Gemini** berdasarkan data yang relevan saja (bukan hasil karangan model).

## Arsitektur

```
BPS Web API  ─▶  ingest.py  ─▶  ChromaDB (vector store, lokal)
                                        │
Telegram user ─▶ bot.py ─▶ rag_engine.py ┘─▶ retrieve top-k dokumen relevan
                                        └─▶ Gemini (generate_content) ─▶ jawaban
```

- **`bps_client.py`** — klien BPS Web API (subject → var → tahun → data). BPS
  mengenkode nilai data dalam key gabungan tanpa separator
  (`vervar+var_id+turvar+th_id+turtahun`); modul ini mendekodenya dengan
  merekonstruksi kandidat key dari kombinasi metadata yang dikembalikan API,
  bukan mem-parsing string-nya secara langsung (sudah divalidasi 100% akurat
  terhadap data live).
- **`ingest.py`** — mengambil semua variabel ekonomi Jawa Tengah (domain BPS
  `3300`) untuk subjek kategori "Ekonomi dan Perdagangan", menyaring variabel
  yang datanya sudah usang/discontinued, memecah tiap variabel jadi dokumen
  per kategori/sektor (vervar), lalu meng-index ke ChromaDB.
- **`rag_engine.py`** — logika embedding + retrieval + generation. Mendukung
  dua backend embedding yang bisa dipilih lewat `.env` (lihat di bawah).
- **`bot.py`** — handler Telegram: `/start` menampilkan menu tombol topik,
  pesan teks bebas dijawab lewat RAG, sapaan ringan (halo/hai/tes) tidak
  masuk ke pipeline RAG.
- **`main.py`** — entry point; melakukan "pemanasan" model embedding saat
  start supaya pertanyaan pertama user tidak kena delay loading model.

## Setup

```bash
python3.11 -m venv .venv        # pakai Python 3.11 (chromadb belum stabil di 3.14)
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # isi API key BPS, Gemini, dan token bot Telegram
```

### Environment variables (`.env`)

| Variabel | Keterangan |
|---|---|
| `BPS_API_KEY` | API key dari [webapi.bps.go.id](https://webapi.bps.go.id) |
| `GEMINI_API_KEY` | API key dari Google AI Studio |
| `TELEGRAM_BOT_TOKEN` | Token dari @BotFather |
| `BPS_DOMAIN` | Kode wilayah BPS (`3300` = Jawa Tengah) |
| `GEMINI_MODEL` | Model generatif utama (default `gemini-flash-latest`) |
| `EMBEDDING_BACKEND` | `local` (gratis, offline, default) atau `gemini` (API, kena kuota harian) |
| `LOCAL_EMBEDDING_MODEL` | Model sentence-transformers untuk backend `local` |
| `CHROMA_DIR` / `CHROMA_COLLECTION` | Lokasi & nama koleksi vector store |

## Menjalankan

```bash
# 1. Index data BPS ke ChromaDB (sekali di awal, ulangi kalau mau refresh data)
python ingest.py --max-vars 9999 --years 4 --max-staleness-years 2

# 2. Jalankan bot
python main.py
```

`ingest.py` menerima beberapa opsi:

- `--subjects <id...>` — hanya ingest subjek BPS tertentu (default: semua
  subjek kategori "Ekonomi dan Perdagangan")
- `--max-vars N` — batasi jumlah variabel per subjek
- `--years N` — jumlah tahun terakhir yang diambil per variabel
- `--max-staleness-years N` — lewati variabel yang data terakhirnya lebih
  tua dari N tahun dari sekarang (variabel discontinued/diganti seri baru)

## Keputusan desain & catatan penting

- **Embedding lokal vs Gemini**: awalnya pakai embedding Gemini
  (`gemini-embedding-001`), tapi tier gratis-nya punya kuota harian ketat
  (1000 request/hari) yang bikin bot berhenti total saat habis — termasuk
  untuk menjawab pertanyaan biasa, bukan cuma saat ingest. Solusinya pindah
  ke model lokal `paraphrase-multilingual-mpnet-base-v2` (via
  `sentence-transformers`) yang jalan di CPU, gratis, dan terbukti lebih
  tahan terhadap variasi ketikan/typo Bahasa Indonesia dibanding model
  MiniLM yang lebih kecil. Backend tetap bisa dipindah ke Gemini lewat
  `EMBEDDING_BACKEND=gemini` di `.env` kapan pun kuota tersedia lagi — kedua
  backend disimpan di koleksi Chroma terpisah supaya tidak tercampur
  (dimensi vektornya berbeda).
- **Filter data usang**: BPS masih menyimpan banyak seri data yang sudah
  digantikan seri baru (mis. IHK inflasi versi lama berhenti di 2018,
  digantikan seri "2022=100"). Karena judul seri lama sering lebih cocok
  secara leksikal dengan pertanyaan umum, retrieval bisa salah mengambil
  data usang. `ingest.py` karena itu melewati variabel yang data
  terakhirnya lebih tua dari `--max-staleness-years`.
- **BPS kadang mengabaikan filter tahun**: request data dengan filter tahun
  tertentu kadang tetap mengembalikan seluruh histori. `ingest.py`
  menyaring ulang hasilnya di sisi klien supaya tahun yang tidak diminta
  tidak ikut ter-index.
- **Beberapa variabel BPS membatasi rentang tahun** (maksimal 2 tahun per
  request untuk sebagian seri) — `ingest.py` otomatis mencoba dengan
  rentang lebih kecil alih-alih melewati variabel tersebut sepenuhnya.
- **Gaya jawaban**: prompt sistem di `rag_engine.py` secara eksplisit
  meminta gaya ngobrol natural (bukan laporan dengan heading/list
  bertingkat), dan identitas bot tetap sebagai "asisten data ekonomi Jawa
  Tengah secara umum" terlepas dari potongan konteks spesifik yang
  ter-retrieve untuk suatu pertanyaan.
- **Ketahanan terhadap gangguan transient**: panggilan ke BPS dan Gemini
  (embedding maupun generation) dibungkus retry dengan backoff. Untuk
  `generate_content`, jika model utama sedang overload (503), bot otomatis
  mencoba model Gemini lain sebagai fallback alih-alih menunggu model yang
  sama berulang kali.

## Struktur data yang di-index

Tiap dokumen mewakili satu kombinasi variabel + kategori/sektor (vervar),
berisi judul, satuan, catatan resmi BPS, dan daftar nilai per periode
(tahun/triwulan/bulan). Metadata tersimpan bersama tiap dokumen untuk
kebutuhan filtering/analisis (`var_id`, `subject`, `title`, `unit`, `vervar`).
