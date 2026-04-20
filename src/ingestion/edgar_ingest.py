"""
EDGAR deal price ingestion — searches for 8-K press releases for each acquisition
in the acquisitions table and fills in deal_price_millions, consideration_type, etc.

Run after fdic_ingest.py and backfill_acquirers():
    python3 ingestion/edgar_ingest.py

Rate-limited to respect SEC's fair-use policy (10 req/sec max).
Skips rows that already have deal_price_millions set (safe to re-run).
"""

import time
from db import get_connection
from edgar_client import get_deal_price
from backup import dump

CHECKPOINT_EVERY = 100


def backfill_deal_prices():
    print("Fetching deal prices from EDGAR...")
    conn = get_connection()
    cur = conn.cursor()

    # Only search EDGAR for larger deals — small community banks don't have SEC filings.
    # book_value is in thousands USD; 100000 = $100M equity capital.
    cur.execute("""
        SELECT company, acq_date, acquirer_name
        FROM acquisitions
        WHERE deal_price_millions IS NULL
          AND book_value >= 100000
        ORDER BY acq_date DESC
    """)
    rows = cur.fetchall()
    print(f"  {len(rows)} rows to process")

    found = 0
    not_found = 0
    for i, (company, acq_date, acquirer_name) in enumerate(rows, 1):
        print(f"  [{i}/{len(rows)}] {company} ({acq_date})", end=" ... ", flush=True)

        result = get_deal_price(
            target_name=company,
            close_date=acq_date.isoformat(),
            acquirer_name=acquirer_name,
        )

        if result and result.get("deal_price_millions") is not None:
            cur.execute(
                """
                UPDATE acquisitions
                SET deal_price_millions  = %(deal_price_millions)s,
                    price_per_share      = %(price_per_share)s,
                    consideration_type   = %(consideration_type)s,
                    edgar_adsh           = %(adsh)s,
                    announcement_date    = %(filing_date)s
                WHERE company = %(company)s AND acq_date = %(acq_date)s
                """,
                {
                    **result,
                    "company": company,
                    "acq_date": acq_date,
                },
            )
            conn.commit()
            found += 1
            print(f"${result['deal_price_millions']:.0f}M ({result['consideration_type'] or 'unknown'})"
                  f"  [{found} found so far, {100*i//len(rows)}% done]")
        else:
            not_found += 1
            print("not found")

        if i % CHECKPOINT_EVERY == 0:
            print(f"  [{i}/{len(rows)}] checkpoint...")
            dump("edgar_checkpoint")

        # SEC rate limit: max 10 requests/sec — each get_deal_price makes ~4-6 requests
        time.sleep(0.5)

    cur.close()
    conn.close()
    print(f"\nDone. Found deal prices for {found} / {len(rows)} acquisitions.")


if __name__ == "__main__":
    backfill_deal_prices()
    dump("edgar")
