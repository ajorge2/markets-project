"""
FRED ingestion — fetches macro series observations with vintage history.

Two paths:
  backfill_all(out)  — writes all series to JSONL, then load() into Postgres (run once)
  refresh(series_id) — fetches latest and writes directly to Postgres (run on schedule)

Crash recovery for backfill_all: checkpoint tracks the last fully-written series_id.
If a crash happens mid-series, that series is re-fetched on resume; ON CONFLICT
handles any resulting duplicates at load time.
"""

from datetime import date, timedelta
from pathlib import Path

from db import get_connection
from fred_client import get_observations, get_latest_observation
from jsonl import read_jsonl, append_jsonl
from backup import dump


EXPECTED_UPDATE_DAYS = {
    "daily":     1,
    "weekly":    7,
    "monthly":   35,
    "quarterly": 100,
}

DEFAULT_OUT        = Path(__file__).parent.parent / "data" / "fred_results.jsonl"
DEFAULT_CHECKPOINT = Path(__file__).parent.parent / "data" / "fred_checkpoint.txt"


def _get_all_series_ids() -> list[str]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT series_id FROM series_registry ORDER BY series_id")
    ids = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return ids


def _read_checkpoint(checkpoint: Path) -> str | None:
    if not checkpoint.exists():
        return None
    text = checkpoint.read_text().strip()
    return text if text else None


def _write_checkpoint(checkpoint: Path, series_id: str):
    checkpoint.write_text(series_id)


def backfill_all(out: Path = DEFAULT_OUT, checkpoint: Path = DEFAULT_CHECKPOINT):
    out.parent.mkdir(exist_ok=True)

    last_completed = _read_checkpoint(checkpoint)
    series_ids = _get_all_series_ids()

    # Skip series already completed
    if last_completed and last_completed in series_ids:
        start = series_ids.index(last_completed) + 1
        print(f"[FRED] Resuming after {last_completed} — {len(series_ids) - start} series remaining.")
    else:
        start = 0
        print(f"[FRED] Starting backfill for {len(series_ids)} series.")

    for sid in series_ids[start:]:
        print(f"[FRED] Fetching {sid}...")
        try:
            rows = get_observations(sid)
        except Exception as e:
            print(f"[FRED] ERROR {sid}: {e}")
            continue

        if not rows:
            print(f"[FRED] No data for {sid}, skipping.")
            _write_checkpoint(checkpoint, sid)
            continue

        for row in rows:
            append_jsonl(out, {"series_id": sid, **row})

        _write_checkpoint(checkpoint, sid)
        print(f"[FRED] {sid} done — {len(rows)} observations written.")

    print(f"[FRED] Fetch complete.")


def load(jsonl_path: Path = DEFAULT_OUT):
    rows = read_jsonl(jsonl_path)
    if not rows:
        print("[FRED] Nothing to load.")
        return

    conn = get_connection()
    cur = conn.cursor()

    cur.executemany(
        """
        INSERT INTO series_observations (series_id, observation_date, vintage_date, value)
        VALUES (%(series_id)s, %(observation_date)s, %(vintage_date)s, %(value)s)
        ON CONFLICT (series_id, observation_date, vintage_date) DO NOTHING
        """,
        rows,
    )

    # Update staleness for each series based on its last observation in the file
    by_series: dict[str, list] = {}
    for r in rows:
        by_series.setdefault(r["series_id"], []).append(r)

    for sid, obs in by_series.items():
        last = max(obs, key=lambda r: r["vintage_date"])
        _update_staleness(cur, sid, last["vintage_date"], last["value"])

    conn.commit()
    cur.close()
    conn.close()
    print(f"[FRED] Loaded {len(rows)} observations into Postgres.")


def refresh(series_id: str):
    obs = get_latest_observation(series_id)
    if not obs:
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO series_observations (series_id, observation_date, vintage_date, value)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (series_id, observation_date, vintage_date) DO NOTHING
        """,
        (series_id, obs["observation_date"], obs["vintage_date"], obs["value"]),
    )
    _update_staleness(cur, series_id, obs["vintage_date"], obs["value"])
    conn.commit()
    cur.close()
    conn.close()


def _update_staleness(cur, series_id: str, latest_vintage: str, latest_value: float):
    cur.execute("SELECT update_frequency FROM series_registry WHERE series_id = %s", (series_id,))
    row = cur.fetchone()
    if not row:
        return
    days_ahead = EXPECTED_UPDATE_DAYS.get(row[0], 35)
    expected_next = date.fromisoformat(latest_vintage) + timedelta(days=days_ahead)
    cur.execute(
        """
        UPDATE staleness_state
        SET last_vintage_date = %s, last_value = %s, expected_next_date = %s, status = 'fresh'
        WHERE series_id = %s
        """,
        (latest_vintage, latest_value, expected_next, series_id),
    )


def check_staleness():
    today = date.today()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE staleness_state
        SET status = CASE
            WHEN last_vintage_date IS NULL THEN 'pending'
            WHEN expected_next_date <= %s THEN 'overdue'
            ELSE 'fresh'
        END
        """,
        (today,),
    )
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "backfill"

    if mode == "backfill":
        backfill_all()
        load()
        check_staleness()
        dump("fred")
    elif mode == "refresh":
        for sid in _get_all_series_ids():
            try:
                refresh(sid)
            except Exception as e:
                print(f"  ERROR {sid}: {e}")
        check_staleness()
        dump("fred")

    print("Done.")
