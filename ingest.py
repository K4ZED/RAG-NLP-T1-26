"""Pull economic indicator data for Jawa Tengah from BPS and index it into Chroma.

Usage:
    python ingest.py                  # ingest all economic subjects
    python ingest.py --subjects 52 3  # ingest only these sub_id values
    python ingest.py --max-vars 10    # cap variables per subject
    python ingest.py --years 3        # how many most-recent years per variable
"""

import argparse
import html
import re
import time
from datetime import datetime

import bps_client
import config
import rag_engine

TARGET_SUBCAT = "Ekonomi dan Perdagangan"


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    return re.sub(r"<[^>]+>", " ", text).strip()


def group_by_vervar(records: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for r in records:
        groups.setdefault(r["vervar"] or "Total", []).append(r)
    return groups


def build_document(var: dict, vervar_label: str, records: list[dict]) -> str:
    unit = (var.get("unit") or "").strip()
    lines = [
        f"Judul: {var['title']}",
        f"Subjek: {var['sub_name']} ({TARGET_SUBCAT})",
        f"Kategori/Sektor: {vervar_label}",
        f"Satuan: {unit if unit else 'indeks/tanpa satuan'}",
        f"Wilayah: Provinsi Jawa Tengah",
    ]
    note = strip_html(var.get("def")) or strip_html(var.get("notes"))
    if note:
        lines.append(f"Catatan: {note}")
    lines.append(f"Sumber: BPS Provinsi Jawa Tengah (var_id={var['var_id']})")
    lines.append("")
    lines.append("Data:")
    for r in records:
        parts = [p for p in (r["turvar"],) if p]
        label = " | ".join(parts)
        period = " ".join(p for p in (r["tahun"], r["turtahun"]) if p)
        prefix = f"{label} - {period}" if label else period
        value_str = f"{r['value']} {unit}".strip()
        lines.append(f"- {prefix}: {value_str}")
    return "\n".join(lines)


def ingest_subject(subject: dict, max_vars: int, num_years: int, max_staleness_years: int) -> int:
    domain = config.BPS_DOMAIN
    sub_id = subject["sub_id"]
    print(f"[subject {sub_id}] {subject['title']}")

    variables = bps_client.get_vars(domain, sub_id, max_vars=max_vars)
    if not variables:
        return 0

    current_year = datetime.now().year
    total_saved = 0
    for var in variables:
        var_id = var["var_id"]
        try:
            years = bps_client.get_years(domain, var_id)
            if not years:
                continue
            latest_year = max(int(y["th"]) for y in years)
            if latest_year < current_year - max_staleness_years:
                print(
                    f"  ! skip var {var_id} (data usang, terakhir {latest_year}): "
                    f"{var['title'][:70]}"
                )
                continue
            sorted_years = sorted(years, key=lambda y: int(y["th_id"]))
            n = num_years
            while True:
                recent_years = sorted_years[-n:]
                th_list = ";".join(str(y["th_id"]) for y in recent_years)
                try:
                    data = bps_client.get_data(domain, var_id, th=th_list)
                    break
                except bps_client.BPSError as e:
                    # Some vars cap how many years can be requested at once;
                    # fall back to fewer years instead of skipping entirely.
                    if "maximum allowed number of years" in str(e) and n > 1:
                        n -= 1
                        continue
                    raise
            wanted_years = {y["th"] for y in recent_years}
            records = bps_client.decode_records(data)
            # BPS doesn't always honor the th filter (it sometimes returns
            # the full history regardless) - enforce it ourselves so stale
            # years don't sneak into the corpus.
            records = [r for r in records if r["tahun"] in wanted_years]
            if not records:
                continue

            ids, texts, metadatas = [], [], []
            groups = group_by_vervar(records)
            for idx, (vervar_label, group_records) in enumerate(groups.items()):
                doc_text = build_document(var, vervar_label, group_records)
                ids.append(f"var-{var_id}-g{idx}")
                texts.append(doc_text)
                metadatas.append(
                    {
                        "var_id": var_id,
                        "subject": var["sub_name"],
                        "title": var["title"],
                        "unit": var.get("unit", ""),
                        "vervar": vervar_label,
                    }
                )

            rag_engine.upsert_documents(ids, texts, metadatas)
            total_saved += len(ids)
            print(
                f"  - var {var_id}: {var['title'][:70]} "
                f"({len(records)} data points, {len(groups)} chunks saved)"
            )
        except bps_client.BPSError as e:
            print(f"  ! skip var {var_id} (BPS error): {e}")
        except Exception as e:
            print(f"  ! skip var {var_id} (unexpected error): {e!r}")
        time.sleep(0.2)

    return total_saved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subjects", nargs="*", type=int, default=None)
    parser.add_argument("--max-vars", type=int, default=15)
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument(
        "--max-staleness-years",
        type=int,
        default=2,
        help="Skip variables whose most recent data is older than this many years",
    )
    args = parser.parse_args()

    domain = config.BPS_DOMAIN
    all_subjects = bps_client.get_all_subjects(domain)
    economic_subjects = [s for s in all_subjects if s["subcat"] == TARGET_SUBCAT]

    if args.subjects:
        economic_subjects = [s for s in economic_subjects if s["sub_id"] in args.subjects]

    print(f"Found {len(economic_subjects)} economic subjects for domain {domain}")

    total_docs = 0
    for subject in economic_subjects:
        try:
            total_docs += ingest_subject(
                subject, args.max_vars, args.years, args.max_staleness_years
            )
        except Exception as e:
            print(f"! skip subject {subject['sub_id']} ({subject['title']}): {e!r}")

    print(f"\nDone. Indexed {total_docs} documents into '{config.CHROMA_COLLECTION}'.")


if __name__ == "__main__":
    main()
