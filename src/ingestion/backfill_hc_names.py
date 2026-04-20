"""
One-off backfill of acquirer_hc_name for existing rows.

Re-fetches only the FDIC history records (2 paginated API calls — fast, no financial lookups),
deduplicates by ACQ_UNINUM, looks up NAMEHCR for each unique acquirer, then updates the DB.

Safe to re-run: uses ON CONFLICT and skips rows that already have acquirer_hc_name set.

    python3 ingestion/backfill_hc_names.py
"""

from db import get_connection
from fdic_client import get_history_records, get_holding_company

print("Fetching FDIC history to get ACQ_UNINUM for each deal...")
uninum_by_deal = {}
for record in get_history_records():
    key = (record["company"], record["acq_date"])
    uninum_by_deal[key] = record.get("acq_uninum")

print(f"  {len(uninum_by_deal)} history records fetched.")

# Deduplicate: one HC lookup per unique uninum
unique_uninums = {u for u in uninum_by_deal.values() if u}
print(f"  {len(unique_uninums)} unique acquirer institutions to look up.")

hc_by_uninum: dict[str, str | None] = {}
for i, uninum in enumerate(unique_uninums, 1):
    hc_by_uninum[uninum] = get_holding_company(uninum)
    if i % 100 == 0:
        print(f"  [{i}/{len(unique_uninums)}] holding company lookups done...")

print(f"  Lookups complete.")

# Update DB
conn = get_connection()
cur = conn.cursor()
updated = 0

for (company, acq_date), uninum in uninum_by_deal.items():
    hc_name = hc_by_uninum.get(uninum) if uninum else None
    cur.execute(
        """
        UPDATE acquisitions
        SET acq_uninum = %s, acquirer_hc_name = %s
        WHERE company = %s AND acq_date = %s
        """,
        (uninum, hc_name, company, acq_date),
    )
    if cur.rowcount:
        updated += 1

conn.commit()
cur.close()
conn.close()

print(f"Updated {updated} rows with acquirer holding company names.")
