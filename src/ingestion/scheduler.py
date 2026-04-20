"""
Ingestion scheduler — runs refresh jobs for each series at the correct cadence.

Cadences:
  daily     — credit spreads, interbank rates (BAMLC0A0CM, BAMLH0A0HYM2, DFF, SOFR)
  weekly    — loan volume (TOTCI)
  monthly   — credit card rate, fed funds (TERMCBCCALLNS, FEDFUNDS)
  quarterly — delinquency rates (DRCCLACBS, DRCLACBS, DRCRELEXFACBS)

Quarterly series: FRED releases these ~6 weeks after quarter end.
We check weekly — if new data has appeared, we pick it up.
"""

import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from fred_ingest import refresh, check_staleness
from backup import dump
from db import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def refresh_series(series_ids: list[str]):
    for sid in series_ids:
        try:
            refresh(sid)
            log.info(f"Refreshed {sid}")
        except Exception as e:
            log.error(f"Failed to refresh {sid}: {e}")
    check_staleness()
    dump("fred_refresh")


def get_series_by_frequency(frequency: str) -> list[str]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT series_id FROM series_registry WHERE update_frequency = %s",
        (frequency,)
    )
    ids = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return ids


def main():
    scheduler = BlockingScheduler(timezone="America/New_York")

    # Daily series — weekdays at 6:00 PM ET (after US market close)
    scheduler.add_job(
        lambda: refresh_series(get_series_by_frequency("daily")),
        CronTrigger(day_of_week="mon-fri", hour=18, minute=0),
        id="daily_refresh",
        name="Daily series refresh",
    )

    # Weekly series — every Monday at 9:00 AM ET
    scheduler.add_job(
        lambda: refresh_series(get_series_by_frequency("weekly")),
        CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="weekly_refresh",
        name="Weekly series refresh",
    )

    # Monthly series — 10th of each month at 9:00 AM ET
    # (most monthly FRED releases land in the first week of the following month)
    scheduler.add_job(
        lambda: refresh_series(get_series_by_frequency("monthly")),
        CronTrigger(day=10, hour=9, minute=0),
        id="monthly_refresh",
        name="Monthly series refresh",
    )

    # Quarterly series — check weekly on Wednesdays
    # FRED releases quarterly data ~6 weeks after quarter end; weekly check catches it promptly
    scheduler.add_job(
        lambda: refresh_series(get_series_by_frequency("quarterly")),
        CronTrigger(day_of_week="wed", hour=9, minute=0),
        id="quarterly_refresh",
        name="Quarterly series refresh (weekly check)",
    )

    log.info("Scheduler started. Jobs:")
    for job in scheduler.get_jobs():
        log.info(f"  {job.name} — next run: {job.next_run_time}")

    scheduler.start()


if __name__ == "__main__":
    main()
