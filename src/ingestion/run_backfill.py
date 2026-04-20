"""
Full backfill runner — FDIC and FRED fetch concurrently (both write to JSONL),
then main thread loads both into Postgres, then runs EDGAR.

    python3 ingestion/run_backfill.py
"""

import threading

from fdic_ingest import backfill as fdic_backfill, load as fdic_load
from fred_ingest import backfill_all as fred_backfill, load as fred_load, check_staleness
from edgar_ingest import backfill_deal_prices
from backup import dump

_errors = []


def run_fdic():
    try:
        fdic_backfill()
    except Exception as e:
        _errors.append(f"FDIC: {e}")
        print(f"[FDIC] FATAL: {e}")


def run_fred():
    try:
        fred_backfill()
    except Exception as e:
        _errors.append(f"FRED: {e}")
        print(f"[FRED] FATAL: {e}")


print("=== Fetching FDIC + FRED concurrently ===")
fdic_thread = threading.Thread(target=run_fdic, name="fdic")
fred_thread = threading.Thread(target=run_fred, name="fred")

fdic_thread.start()
fred_thread.start()
fdic_thread.join()
fred_thread.join()

if _errors:
    print(f"\nErrors: {_errors}")
    print("Fix before loading into Postgres.")
else:
    print("\n=== Loading FDIC + FRED into Postgres ===")
    fdic_load()
    fred_load()
    check_staleness()

    print("\n=== Starting EDGAR deal price extraction ===")
    backfill_deal_prices()
    dump("full_backfill")
    print("=== Full backfill complete ===")
