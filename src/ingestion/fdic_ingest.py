"""
FDIC ingestion — fetches all CHANGECODE 223 mergers and pre-acquisition book values.

Writes to JSONL first, then loads into Postgres. JSONL line count is the crash
checkpoint: on resume, records[line_count:] picks up exactly where we left off.

Run standalone:
    python3 ingestion/fdic_ingest.py
Or via run_backfill.py for concurrent execution with FRED.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from db import get_connection
from fdic_client import get_history_records, get_financials_for, get_holding_company
from jsonl import read_jsonl, append_jsonl, count_valid_lines
from backup import dump

BATCH_SIZE = 500
WORKERS = 3
DEFAULT_OUT = Path(__file__).parent.parent / "data" / "fdic_results.jsonl"


def backfill(out: Path = DEFAULT_OUT):
    out.parent.mkdir(exist_ok=True)
    checkpoint = count_valid_lines(out)

    print("[FDIC] Fetching merger history...")
    records = list(get_history_records())
    remaining = records[checkpoint + 1:] if checkpoint else records
    print(f"[FDIC] {len(records)} total — resuming from row {checkpoint}, {len(remaining)} to fetch.")

    if not remaining:
        print("[FDIC] Already complete.")
        return

    for batch_start in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[batch_start:batch_start + BATCH_SIZE]

        # Collect results in memory keyed by submission index so we can write in order
        results: dict[int, dict] = {}
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(get_financials_for, r): i for i, r in enumerate(batch)}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    row = future.result()
                    if row:
                        results[idx] = row
                except Exception as e:
                    print(f"[FDIC] WARNING: {e}")

        # Write in submission order so line count stays meaningful as a checkpoint
        for idx in sorted(results):
            append_jsonl(out, results[idx])

        written_so_far = checkpoint + batch_start + len(batch)
        print(f"[FDIC] {written_so_far}/{len(records)} processed — checkpoint at {count_valid_lines(out)} rows written")
        dump("fdic_checkpoint")

    print(f"[FDIC] Fetch done. {count_valid_lines(out)} rows in {out.name}")


def load(jsonl_path: Path = DEFAULT_OUT):
    rows = read_jsonl(jsonl_path)
    if not rows:
        print("[FDIC] Nothing to load.")
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.executemany(
        """
        INSERT INTO acquisitions (company, acq_date, acquirer_name, acq_uninum, report_date, book_value)
        VALUES (%(company)s, %(acq_date)s, %(acquirer_name)s, %(acq_uninum)s, %(report_date)s, %(book_value)s)
        ON CONFLICT (company, acq_date) DO UPDATE
            SET acquirer_name = EXCLUDED.acquirer_name,
                acq_uninum    = EXCLUDED.acq_uninum,
                report_date   = EXCLUDED.report_date,
                book_value    = EXCLUDED.book_value
        """,
        rows,
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"[FDIC] Loaded {len(rows)} rows into Postgres.")


if __name__ == "__main__":
    backfill()
    load()
    dump("fdic")
