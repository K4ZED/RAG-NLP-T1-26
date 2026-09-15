# Bot Telegram RAG untuk Data Ekonomi Jawa Tengah

Ini bot Telegram yang bisa diajak ngobrol soal data ekonomi Provinsi Jawa
Tengah. Datanya asli dari BPS (Badan Pusat Statistik), bukan karangan model.
Caranya pakai pola RAG (Retrieval-Augmented Generation): setiap ada
pertanyaan, bot mencari dulu data BPS yang paling relevan, baru minta Gemini
menjelaskan angka-angka itu dengan bahasa yang natural.

## Cara kerjanya, singkatnya

1. `ingest.py` narik data ekonomi Jawa Tengah dari BPS Web API dan
   nyimpennya ke ChromaDB (database vektor lokal).
2. User kirim pertanyaan ke bot Telegram.
3. Bot mencari dokumen BPS yang paling cocok dengan pertanyaan itu
   (retrieval).
4. Dokumen yang ketemu dikirim ke Gemini sebagai konteks, lalu Gemini
   menyusun jawabannya.

## Isi tiap file

- `bps_client.py`: yang ngobrol langsung ke BPS Web API (ambil daftar
  subjek, variabel, tahun, sampai data mentahnya). BPS nyimpen nilai data
  dalam kode gabungan angka tanpa pemisah, jadi modul ini punya fungsi
  khusus buat "menerjemahkan" kode itu balik jadi data yang bisa dibaca.
  Sudah dites dan cocok 100% dengan data asli.
- `ingest.py`: script yang benar-benar narik semua variabel ekonomi Jawa
  Tengah, nyaring yang datanya udah gak update lagi, terus masukin ke
  ChromaDB.
- `rag_engine.py`: inti dari sistem RAG. Ngurusin embedding (ubah teks jadi
  angka biar bisa dicari), pencarian dokumen, dan minta Gemini bikin
  jawaban.
- `bot.py`: bagian yang ngobrol sama Telegram. Ada menu tombol pas
  `/start`, dan sapaan santai kayak "halo" gak akan dianggap pertanyaan
  data.
- `main.py`: buat nyalain bot. Model embeddingnya dipanasin dulu di sini
  biar pertanyaan pertama user gak nunggu lama.

## Cara jalanin

Siapin dulu environment Python (pakai Python 3.11, soalnya beberapa
library yang dipakai belum stabil di versi Python terbaru):

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Isi file `.env` dengan API key kamu sendiri (BPS, Gemini, Token bot
Telegram). Detail tiap variabelnya:

| Variabel | Buat apa |
|---|---|
| `BPS_API_KEY` | key dari webapi.bps.go.id |
| `GEMINI_API_KEY` | key dari Google AI Studio |
| `TELEGRAM_BOT_TOKEN` | token dari @BotFather |
| `BPS_DOMAIN` | kode wilayah BPS, `3300` itu Jawa Tengah |
| `GEMINI_MODEL` | model Gemini yang dipakai buat jawab |
| `EMBEDDING_BACKEND` | `local` (gratis, jalan di komputer sendiri) atau `gemini` (pakai API, ada batas kuota harian) |
| `LOCAL_EMBEDDING_MODEL` | model embedding lokal yang dipakai |
| `CHROMA_DIR` / `CHROMA_COLLECTION` | lokasi database vektornya disimpan |

Setelah itu, masukkan data BPS ke database dengan menjalankan:

```bash
python ingest.py --max-vars 9999 --years 4 --max-staleness-years 2
```

Baru jalankan bot:

```bash
python main.py
```

Opsi yang bisa dipakai di `ingest.py`:

- `--subjects <id>`: kalau cuma mau ambil subjek BPS tertentu aja
- `--max-vars N`: batasi berapa banyak variabel per subjek
- `--years N`: berapa tahun terakhir yang mau diambil
- `--max-staleness-years N`: lewati variabel yang udah lama gak diupdate

## Hal-hal yang sempat jadi masalah (dan cara benerinnya)

**Kuota Gemini buat embedding cepat habis.** Awalnya semua embedding
(dokumen maupun pertanyaan) dikirim ke Gemini, tapi tier gratisnya cuma
kasih jatah 1000 request per hari. Begitu habis, bot langsung mati total,
bahkan buat pertanyaan simpel sekalipun. Solusinya, embedding dipindah ke
model lokal (`paraphrase-multilingual-mpnet-base-v2`) yang jalan gratis di
komputer sendiri, dan ternyata malah lebih tahan sama typo dan variasi
ketikan Bahasa Indonesia. Kalau suatu saat mau balik pakai Gemini, tinggal
ganti `EMBEDDING_BACKEND` di `.env`, karena dua-duanya disimpan di tempat
yang terpisah biar gak ketuker.

**Data BPS yang udah lama gak update ikut kebawa.** Banyak seri data BPS
yang sebenarnya udah digantikan versi lebih baru, tapi judulnya masih mirip
banget sama seri lama. Contohnya data inflasi versi lama yang berhenti di
2018, padahal ada versi barunya yang datanya sampai sekarang. Karena
judulnya mirip, pencarian dokumen kadang malah ambil yang lama. Makanya
`ingest.py` sekarang otomatis skip variabel yang data terakhirnya udah
terlalu tua.

**BPS kadang gak nurut sama filter tahun yang diminta.** Kadang minta data
2 tahun terakhir, tapi yang dibalikin malah semua tahun dari awal. Jadi
sekarang ada penyaringan tambahan di kode sendiri, bukan cuma mengandalkan
filter dari API BPS.

**Beberapa variabel BPS cuma boleh diminta maksimal 2 tahun sekaligus.**
Kalau minta lebih, permintaannya ditolak dan variabelnya jadi dilewati.
Sekarang kalau kena batasan ini, `ingest.py` otomatis coba lagi dengan
rentang tahun yang lebih kecil, bukan langsung nyerah.

**Jawaban bot awalnya kaku kayak laporan.** Terlalu banyak heading, poin
bernomor, dan tanda tebal di mana-mana. Sekarang instruksi sistem untuk
Gemini diubah supaya jawabannya lebih kayak ngobrol biasa, bukan bikin
laporan data.

**Kalau Gemini lagi sibuk.** Kadang server Gemini overload dan balikin
error sementara. Bot sekarang otomatis coba lagi, dan kalau model utamanya
masih sibuk juga, dia coba pindah ke model Gemini lain daripada nunggu
model yang sama terus-terusan.

## Soal data yang disimpan

Setiap dokumen di database itu isinya satu variabel BPS untuk satu
kategori/sektor tertentu, lengkap dengan judul, satuan, catatan resmi dari
BPS, dan nilai datanya per periode (tahun, triwulan, atau bulan).
