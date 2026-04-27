"""
yfinance ingestion — fetch daily ETF close prices and store in series_observations.

Used for sector-equity stress proxies (drawdown computed at regression time).
ETFs don't have a vintage history, so vintage_date == observation_date for every row.
Series IDs are prefixed `ETF_<TICKER>` to keep them distinct from FRED ids.
"""

from datetime import date
import yfinance as yf

from db import get_connection


# Sector ETF mapping for Stone Point's 13 sub-sectors.
# One ticker per sector; later regression uses drawdown of that ETF as the
# sector's equity-stress proxy.
SECTOR_ETFS = [
    # (ticker, sector_id, description, units)
    ("XLF", "asset_management",                            "Financial Select Sector SPDR (proxy for asset managers)", "USD"),
    ("XLF", "business_services",                           "Financial Select Sector SPDR (proxy for business services)", "USD"),
    ("PAYX","employee_benefits_and_hcm",                   "Paychex Inc. (HR / payroll services proxy)",                "USD"),
    ("IHF", "health_insurance_and_workers_comp_services",  "iShares US Healthcare Providers ETF",                       "USD"),
    ("KIE", "insurance_distribution",                      "SPDR S&P Insurance ETF",                                    "USD"),
    ("KIE", "insurance_services",                          "SPDR S&P Insurance ETF",                                    "USD"),
    ("KIE", "insurance_underwriting",                      "SPDR S&P Insurance ETF",                                    "USD"),
    ("KBE", "lending_and_markets",                         "SPDR S&P Bank ETF",                                         "USD"),
    ("REM", "real_estate_finance_and_services",            "iShares Mortgage Real Estate ETF (older mREIT ETF, covers 2008)", "USD"),
    ("IAI", "wealth_management_and_fund_administration",   "iShares US Broker-Dealers & Securities Exchanges ETF",      "USD"),
    ("XLF", "financial_services",                          "Financial Select Sector SPDR",                              "USD"),
    ("XLK", "software_and_technology",                     "Technology Select Sector SPDR",                             "USD"),
    ("XLV", "healthcare_services",                         "Health Care Select Sector SPDR",                            "USD"),
]


def unique_tickers():
    """Distinct tickers (some ETFs back multiple sectors — only fetch once)."""
    seen = set()
    out = []
    for ticker, _, desc, units in SECTOR_ETFS:
        if ticker in seen:
            continue
        seen.add(ticker)
        out.append((ticker, desc, units))
    return out


def register_etf_series():
    """Insert ETF rows into series_registry (idempotent)."""
    conn = get_connection()
    cur = conn.cursor()
    for ticker, desc, units in unique_tickers():
        sid = f"ETF_{ticker}"
        cur.execute(
            """
            INSERT INTO series_registry
                (series_id, description, sector, signal_speed, update_frequency, fred_series_id, units)
            VALUES (%s, %s, 'etf', 'fast', 'daily', NULL, %s)
            ON CONFLICT (series_id) DO NOTHING
            """,
            (sid, desc, units),
        )
        cur.execute(
            "INSERT INTO staleness_state (series_id, status) VALUES (%s, 'pending') ON CONFLICT (series_id) DO NOTHING",
            (sid,),
        )
    conn.commit()
    cur.close()
    conn.close()


def ingest_ticker(ticker: str, start: str = "1990-01-01"):
    """Fetch daily close prices for one ETF from inception (or `start`, whichever later)."""
    sid = f"ETF_{ticker}"
    print(f"[yfinance] Fetching {ticker}...", flush=True)
    df = yf.download(ticker, start=start, end=date.today().isoformat(),
                     auto_adjust=False, progress=False, threads=False)
    if df.empty:
        print(f"  {ticker}: no data returned")
        return 0

    # yfinance multi-index column handling (ticker x field)
    if "Close" in df.columns.get_level_values(0):
        close_col = df["Close"]
        if hasattr(close_col, "columns"):  # multi-ticker — single column case
            close_col = close_col.iloc[:, 0]
    else:
        close_col = df.iloc[:, 0]

    rows = []
    for d, v in close_col.items():
        if v is None or (hasattr(v, "__float__") and (v != v)):  # NaN check
            continue
        try:
            val = float(v)
        except Exception:
            continue
        rows.append({
            "sid": sid,
            "observation_date": d.date().isoformat() if hasattr(d, "date") else str(d)[:10],
            "vintage_date":     d.date().isoformat() if hasattr(d, "date") else str(d)[:10],
            "value":            val,
        })

    if not rows:
        print(f"  {ticker}: parsed 0 rows")
        return 0

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM series_observations WHERE series_id = %s", (sid,))
    before = cur.fetchone()[0]
    from psycopg2.extras import execute_values
    execute_values(
        cur,
        """
        INSERT INTO series_observations (series_id, observation_date, vintage_date, value)
        VALUES %s
        ON CONFLICT (series_id, observation_date, vintage_date) DO NOTHING
        """,
        [(r["sid"], r["observation_date"], r["vintage_date"], r["value"]) for r in rows],
        page_size=1000,
    )
    cur.execute("SELECT COUNT(*) FROM series_observations WHERE series_id = %s", (sid,))
    after = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    added = after - before
    print(f"  {ticker}: fetched {len(rows)}, added {added} new rows")
    return added


def ingest_all():
    register_etf_series()
    summary = []
    for ticker, _, _ in unique_tickers():
        added = ingest_ticker(ticker)
        summary.append({"ticker": ticker, "added": added})
    return summary


if __name__ == "__main__":
    s = ingest_all()
    print()
    print("Summary:")
    for r in s:
        print(f"  ETF_{r['ticker']:<6} added={r['added']}")
