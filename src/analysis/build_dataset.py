"""
build_dataset.py — assembles the regression dataset.

For each acquisition with a known deal price:
  - Computes price-to-book multiple (deal_price_millions * 1000 / book_value)
  - Looks up each macro signal at the latest observation available on or before acq_date
  - Returns a pandas DataFrame with one row per deal

Macro signals and their transformations:
  T10Y2Y   daily     level          (yield curve spread, already in pct pts)
  UMCSENT  monthly   level          (consumer sentiment index)
  DSPI     monthly   YoY %          (level has inflation trend — change isolates growth signal)
  CPROFIT  quarterly YoY %          (same reason)
  COMPUTSA monthly   YoY %          (same reason)

Uses the most recent vintage available as of acq_date for each observation.
Known limitation: should ideally use announcement date, not close date.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingestion"))

import pandas as pd
from db import get_connection

# (series_id, transform)  — 'level' or 'yoy_pct'
MACRO_SIGNALS = [
    ("T10Y2Y",   "level"),
    ("UMCSENT",  "level"),
    ("DSPI",     "yoy_pct"),
    ("CPROFIT",  "yoy_pct"),
    ("COMPUTSA", "yoy_pct"),
]


def _fetch_macro_series(conn) -> dict[str, pd.DataFrame]:
    """
    Fetch all macro series observations from DB.
    Returns dict of series_id -> DataFrame(observation_date, vintage_date, value).
    """
    cur = conn.cursor()
    series = {}
    for sid, _ in MACRO_SIGNALS:
        cur.execute("""
            SELECT observation_date, vintage_date, value
            FROM series_observations
            WHERE series_id = %s
            ORDER BY observation_date, vintage_date
        """, (sid,))
        rows = cur.fetchall()
        if rows:
            df = pd.DataFrame(rows, columns=["observation_date", "vintage_date", "value"])
            df["observation_date"] = pd.to_datetime(df["observation_date"])
            df["vintage_date"] = pd.to_datetime(df["vintage_date"])
            df["value"] = df["value"].astype(float)
            series[sid] = df
    cur.close()
    return series


def _latest_value_as_of(df: pd.DataFrame, as_of: pd.Timestamp) -> float | None:
    """
    Return the most recent observed value that was published on or before as_of.
    Implements point-in-time logic: vintage_date <= as_of.
    """
    eligible = df[df["vintage_date"] <= as_of]
    if eligible.empty:
        return None
    # Among eligible vintages, take the one with the latest observation_date
    idx = eligible.groupby("observation_date")["vintage_date"].max()
    latest_obs_date = idx.index.max()
    return eligible[
        (eligible["observation_date"] == latest_obs_date) &
        (eligible["vintage_date"] == idx[latest_obs_date])
    ]["value"].iloc[0]


def _yoy_pct(df: pd.DataFrame, as_of: pd.Timestamp) -> float | None:
    """
    Compute YoY % change for a series as of as_of date.
    YoY = (current_value / year_ago_value - 1) * 100
    """
    current = _latest_value_as_of(df, as_of)
    year_ago = _latest_value_as_of(df, as_of - pd.DateOffset(years=1))
    if current is None or year_ago is None or year_ago == 0:
        return None
    return (current / year_ago - 1) * 100


def build_dataset() -> pd.DataFrame:
    """
    Returns a DataFrame with columns:
      company, acq_date, book_value, deal_price_millions, price_to_book,
      T10Y2Y, UMCSENT, DSPI_yoy, CPROFIT_yoy, COMPUTSA_yoy
    """
    conn = get_connection()

    cur = conn.cursor()
    cur.execute("""
        SELECT company, acq_date, announcement_date, book_value, deal_price_millions
        FROM acquisitions
        WHERE deal_price_millions IS NOT NULL
          AND book_value IS NOT NULL AND book_value > 0
        ORDER BY acq_date
    """)
    deals = cur.fetchall()
    cur.close()

    if not deals:
        conn.close()
        print("No deals with price data yet — run edgar_ingest.py first.")
        return pd.DataFrame()

    print(f"Building dataset from {len(deals)} deals with known prices...")
    macro_dfs = _fetch_macro_series(conn)
    conn.close()

    rows = []
    for company, acq_date, announcement_date, book_value, deal_price_millions in deals:
        # Use announcement date for macro lookup if available — price is set at announcement,
        # not close. Close date introduces ~6-12 month lag of macro data not yet in the price.
        signal_date = announcement_date if announcement_date else acq_date
        ts = pd.Timestamp(signal_date)

        # price-to-book: deal_price in millions, book_value in thousands USD
        # → convert book_value to millions: book_value / 1000
        ptb = float(deal_price_millions) / (float(book_value) / 1000)

        row = {
            "company": company,
            "acq_date": acq_date,
            "signal_date": signal_date,   # announcement_date if known, else close date
            "book_value_mm": float(book_value) / 1000,
            "deal_price_mm": float(deal_price_millions),
            "price_to_book": ptb,
        }

        for sid, transform in MACRO_SIGNALS:
            df = macro_dfs.get(sid)
            if df is None:
                col = sid if transform == "level" else f"{sid}_yoy"
                row[col] = None
                continue

            if transform == "level":
                row[sid] = _latest_value_as_of(df, ts)
            elif transform == "yoy_pct":
                row[f"{sid}_yoy"] = _yoy_pct(df, ts)

        rows.append(row)

    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = build_dataset()
    if df.empty:
        sys.exit(0)

    print(f"\nDataset shape: {df.shape}")
    print(f"\nMissing values per column:")
    print(df.isnull().sum())
    print(f"\nPrice-to-book distribution:")
    print(df["price_to_book"].describe())
    print(f"\nSample rows:")
    print(df.head(10).to_string())
