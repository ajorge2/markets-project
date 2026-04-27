"""
Derive equity- and credit-stress proxies per sector from raw observations.

Outputs:
  DD_<sector_id>   — daily ETF drawdown from 180-day rolling max (all 13 sectors)
  CC_<sector_id>   — daily forward-filled z-score composite of sub-sector credit
                     signals (4 sectors with FRED bank-lending data)
  CC_AGG           — daily forward-filled z-score composite of aggregate credit
                     stress signals (BAA10Y, NFCICREDIT, STLFSI4); used as the
                     credit regression target for the 9 non-bank sectors

All proxy series are stored in series_observations with vintage_date = observation_date
and a sentinel series_registry row so the data inventory stays consistent.

Run as:  python3 src/analysis/derive_stress_proxies.py
"""

from datetime import date, timedelta
from pathlib import Path
import sys

# Reuse existing DB connection helper
sys.path.insert(0, str(Path(__file__).parent.parent / "ingestion"))
from db import get_connection


# Sector → ETF mapping (mirrors yfinance_ingest.SECTOR_ETFS).
SECTOR_ETF = {
    "asset_management":                            "XLF",
    "business_services":                           "XLF",
    "employee_benefits_and_hcm":                   "PAYX",
    "health_insurance_and_workers_comp_services":  "IHF",
    "insurance_distribution":                      "KIE",
    "insurance_services":                          "KIE",
    "insurance_underwriting":                      "KIE",
    "lending_and_markets":                         "KBE",
    "real_estate_finance_and_services":            "REM",
    "wealth_management_and_fund_administration":   "IAI",
    "financial_services":                          "XLF",
    "software_and_technology":                     "XLK",
    "healthcare_services":                         "XLV",
}

# Sectors with sub-sector FRED credit data → series_id list for the composite.
SUB_SECTOR_CREDIT = {
    "lending_and_markets":              ["DRTSCILM", "CORBLACBS", "DRBLACBS", "CORALACBS"],
    "real_estate_finance_and_services": ["SUBLPDRCSN", "SUBLPDRCSM", "SUBLPDRCSC",
                                          "CORCREXFACBS", "DRCRELEXFACBS", "CORSFRMACBS"],
    "financial_services":               ["DRTSCILM", "CORALACBS"],
    "business_services":                ["DRTSCILM", "CORBLACBS"],
}

# Aggregate credit composite (used for the 9 sectors without sub-sector data).
AGG_CREDIT = ["BAA10Y", "NFCICREDIT", "STLFSI4"]

DRAWDOWN_WINDOW_DAYS = 180


# ---------------------------------------------------------------------------

def _ensure_proxy_registry_row(cur, series_id: str, description: str, frequency: str = "daily"):
    """Idempotent insert of a synthetic registry row so the inventory page surfaces these."""
    cur.execute(
        """
        INSERT INTO series_registry (series_id, description, sector, signal_speed, update_frequency, fred_series_id, units)
        VALUES (%s, %s, 'derived', 'fast', %s, NULL, 'z-score / drawdown')
        ON CONFLICT (series_id) DO NOTHING
        """,
        (series_id, description, frequency),
    )
    cur.execute(
        "INSERT INTO staleness_state (series_id, status) VALUES (%s, 'fresh') ON CONFLICT (series_id) DO NOTHING",
        (series_id,),
    )


def _fetch_series(cur, series_id: str) -> list[tuple]:
    """Return (observation_date, value) pairs in ascending order, latest vintage per obs."""
    cur.execute(
        """
        SELECT DISTINCT ON (observation_date) observation_date, value
        FROM series_observations
        WHERE series_id = %s AND value IS NOT NULL
        ORDER BY observation_date ASC, vintage_date DESC
        """,
        (series_id,),
    )
    return cur.fetchall()


def _wipe_series(cur, series_id: str):
    """Clear prior derived rows so re-runs are idempotent."""
    cur.execute("DELETE FROM series_observations WHERE series_id = %s", (series_id,))


def _bulk_insert(cur, series_id: str, rows: list[tuple]):
    """rows: list of (observation_date, value)."""
    if not rows:
        return 0
    payload = [{"sid": series_id, "obs": d, "vintage": d, "val": float(v)} for d, v in rows]
    cur.executemany(
        """
        INSERT INTO series_observations (series_id, observation_date, vintage_date, value)
        VALUES (%(sid)s, %(obs)s, %(vintage)s, %(val)s)
        ON CONFLICT (series_id, observation_date, vintage_date) DO NOTHING
        """,
        payload,
    )
    return len(payload)


# --- ETF drawdown -----------------------------------------------------------

def compute_drawdown(prices: list[tuple], window_days: int = DRAWDOWN_WINDOW_DAYS) -> list[tuple]:
    """
    drawdown(t) = (rolling_max(price, window)(t) - price(t)) / rolling_max
    Trading-day approximation: walk forward and maintain a rolling window by date.
    Returns list of (date, drawdown_pct in [0, 1]) — only for dates with full window of context.
    """
    if not prices:
        return []
    out = []
    # Use a deque of (date, price) entries within window_days
    from collections import deque
    window: deque = deque()
    for d, p in prices:
        # Pop entries older than window_days
        while window and (d - window[0][0]).days > window_days:
            window.popleft()
        window.append((d, float(p)))
        # Need a meaningful window before reporting
        if (window[-1][0] - window[0][0]).days < window_days // 2:
            continue
        rolling_max = max(x[1] for x in window)
        if rolling_max <= 0:
            continue
        dd = max(0.0, (rolling_max - float(p)) / rolling_max)
        out.append((d, dd))
    return out


# --- Z-score composites -----------------------------------------------------

def _zscore(values: list[float]) -> list[float]:
    """Plain z-score of a list. NaN/inf-safe enough for our quarterly cadences."""
    n = len(values)
    if n == 0:
        return []
    mu = sum(values) / n
    var = sum((v - mu) ** 2 for v in values) / max(1, n - 1)
    sigma = var ** 0.5
    if sigma == 0:
        return [0.0] * n
    return [(v - mu) / sigma for v in values]


def build_credit_composite(cur, component_series: list[str]) -> list[tuple]:
    """
    Build a daily forward-filled z-score-average of the listed FRED series.
    Quarterly observations are forward-filled to daily resolution (so the
    composite remains meaningful between releases).
    Returns (date, composite_value).
    """
    # Fetch each series, z-score, then merge by date
    z_series_by_date: dict[str, list[tuple]] = {}  # series_id → [(date, z)]
    all_dates: set = set()
    for sid in component_series:
        rows = _fetch_series(cur, sid)
        if not rows:
            continue
        dates = [r[0] for r in rows]
        zs = _zscore([float(r[1]) for r in rows])
        z_series_by_date[sid] = list(zip(dates, zs))
        all_dates.update(dates)

    if not all_dates:
        return []

    # Build daily date range from earliest to latest observation
    sorted_obs_dates = sorted(all_dates)
    start = sorted_obs_dates[0]
    end = date.today()

    # Forward-fill each component to daily, then average across components
    daily_values: dict[date, list[float]] = {}
    for sid, points in z_series_by_date.items():
        # Sort points by date
        points.sort(key=lambda x: x[0])
        idx = 0
        last_z = None
        cur_date = start
        while cur_date <= end:
            # Advance idx while next point's date <= cur_date
            while idx < len(points) and points[idx][0] <= cur_date:
                last_z = points[idx][1]
                idx += 1
            if last_z is not None:
                daily_values.setdefault(cur_date, []).append(last_z)
            cur_date += timedelta(days=1)

    # Average across components per day (only days where ≥1 component is observed)
    out = []
    for d in sorted(daily_values.keys()):
        zs = daily_values[d]
        if not zs:
            continue
        out.append((d, sum(zs) / len(zs)))
    return out


# --- Main pipeline ----------------------------------------------------------

def main():
    conn = get_connection()
    cur = conn.cursor()

    print("[derive] Computing equity drawdowns...")
    for sector_id, ticker in SECTOR_ETF.items():
        prices = _fetch_series(cur, f"ETF_{ticker}")
        if not prices:
            print(f"  {sector_id:<46} no ETF data ({ticker})")
            continue
        # Sort by date ascending (DISTINCT ON returns first date but to be safe)
        prices = sorted(prices, key=lambda r: r[0])
        dd_rows = compute_drawdown(prices)
        sid = f"DD_{sector_id}"
        _ensure_proxy_registry_row(cur, sid, f"180-day rolling drawdown of {ticker} (proxy for {sector_id} equity stress)")
        _wipe_series(cur, sid)
        n = _bulk_insert(cur, sid, dd_rows)
        print(f"  {sector_id:<46} {ticker:<6} → {sid:<55} {n} rows  range={dd_rows[0][0]}..{dd_rows[-1][0]}" if dd_rows else f"  {sector_id} no rows")

    print()
    print("[derive] Computing sub-sector credit composites (CC_*)...")
    for sector_id, components in SUB_SECTOR_CREDIT.items():
        composite = build_credit_composite(cur, components)
        sid = f"CC_{sector_id}"
        _ensure_proxy_registry_row(cur, sid, f"Forward-filled z-score composite of sub-sector credit signals for {sector_id}")
        _wipe_series(cur, sid)
        n = _bulk_insert(cur, sid, composite)
        if composite:
            print(f"  {sector_id:<46} → {sid:<55} {n} rows  range={composite[0][0]}..{composite[-1][0]}  components={len(components)}")
        else:
            print(f"  {sector_id:<46} → {sid:<55} 0 rows (no component data)")

    print()
    print("[derive] Computing aggregate credit composite (CC_AGG)...")
    agg = build_credit_composite(cur, AGG_CREDIT)
    _ensure_proxy_registry_row(cur, "CC_AGG", "Aggregate credit-stress composite (BAA10Y, NFCICREDIT, STLFSI4)")
    _wipe_series(cur, "CC_AGG")
    n = _bulk_insert(cur, "CC_AGG", agg)
    if agg:
        print(f"  CC_AGG  {n} rows  range={agg[0][0]}..{agg[-1][0]}  components={len(AGG_CREDIT)}")
    else:
        print("  CC_AGG  0 rows (no component data)")

    conn.commit()
    cur.close()
    conn.close()
    print()
    print("[derive] Done.")


if __name__ == "__main__":
    main()
