"""
Derive per-sector dual weights via OLS regression.

For each of the 13 sectors S:
  - Equity-side regression: DD_S(t) ~ stress_pct[indicator_i](t)  →  w_equity[i]
  - Credit-side regression: CC_S(t)  ~ stress_pct[indicator_i](t)  →  w_credit[i]
    where CC_S = sub-sector composite for the 4 lending sectors,
                = CC_AGG (aggregate) for the other 9.

Coefficients are clipped to ≥ 0 (negative coefficients = the indicator predicts
*less* stress in that target; we only want positive contribution to the
weighted-average score), then normalized so the 8 weights for that sector sum
to N (number of indicators) — preserves the "weight 1.0 = average pull" semantic.

Writes weight_credit and weight_equity columns of indicator_sector_map.

Run as:  python3 src/analysis/derive_weights.py
"""

from datetime import date, timedelta
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).parent.parent / "ingestion"))
from db import get_connection


# ---- Indicator definitions -------------------------------------------------

INDICATORS = [
    "TOTCI",
    "DFF_SOFR_SPREAD",
    "CC_SPREAD",
    "DRCCLACBS",
    "DRCLACBS",
    "BAMLC0A0CM",
    "BAMLH0A0HYM2",
]
# DRCRELEXFACBS deliberately excluded: it's a sector-specific (CRE) signal, and
# is also an ingredient in CC_real_estate_finance_and_services. Including it as
# a predictor would create circularity — the regression would learn its own
# target. Predictors are general/cross-cutting; sector-specific stress flows
# through the CC_<sector> target instead.

INVERTED = {"TOTCI"}  # higher raw value = less stress; flip percentile

SPREAD_DEFS = {
    "DFF_SOFR_SPREAD": ("DFF", "SOFR", True),         # absolute value
    "CC_SPREAD":       ("TERMCBCCALLNS", "FEDFUNDS", False),
}

SUB_SECTOR_CREDIT_TARGETS = {
    "lending_and_markets":              "CC_lending_and_markets",
    "real_estate_finance_and_services": "CC_real_estate_finance_and_services",
    "financial_services":               "CC_financial_services",
    "business_services":                "CC_business_services",
}


# ---- DB helpers ------------------------------------------------------------

def fetch_series(cur, series_id: str) -> pd.Series:
    """Latest-vintage observation per date for series_id, returned as a pd.Series indexed by date."""
    cur.execute(
        """
        SELECT DISTINCT ON (observation_date) observation_date, value
        FROM series_observations
        WHERE series_id = %s AND value IS NOT NULL
        ORDER BY observation_date ASC, vintage_date DESC
        """,
        (series_id,),
    )
    rows = cur.fetchall()
    if not rows:
        return pd.Series(dtype=float)
    s = pd.Series({r[0]: float(r[1]) for r in rows}, name=series_id)
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


# ---- Indicator transforms --------------------------------------------------

def compute_yoy(s: pd.Series) -> pd.Series:
    """YoY % change. Find the closest observation ~365 days back (within ±28 days)."""
    if s.empty:
        return pd.Series(dtype=float)
    out = {}
    dates = s.index
    for i, d in enumerate(dates):
        target = d - pd.Timedelta(days=365)
        # Search ±28 days
        candidates = s.loc[(dates >= target - pd.Timedelta(days=28)) & (dates <= target + pd.Timedelta(days=28))]
        if candidates.empty:
            continue
        prior_val = candidates.iloc[-1]
        if prior_val == 0:
            continue
        out[d] = (s.iloc[i] - prior_val) / prior_val * 100
    return pd.Series(out, name=f"{s.name}_yoy").sort_index()


def compute_spread(num: pd.Series, den: pd.Series, abs_val: bool) -> pd.Series:
    """Forward-fill den into num's dates, then numerator − denominator."""
    if num.empty or den.empty:
        return pd.Series(dtype=float)
    # Reindex denominator to numerator dates with forward fill
    combined = pd.concat([num.rename("num"), den.rename("den")], axis=1).sort_index()
    combined["den"] = combined["den"].ffill()
    combined = combined.dropna(subset=["num"])  # keep only numerator dates
    spread = combined["num"] - combined["den"]
    if abs_val:
        spread = spread.abs()
    return spread.dropna()


def to_stress_pct(s: pd.Series, inverted: bool = False) -> pd.Series:
    """Full-history percentile rank in [0, 100]. Inverted series get 100 − pct."""
    if s.empty:
        return s
    pct = s.rank(method="average", pct=True) * 100
    if inverted:
        pct = 100 - pct
    return pct


def build_indicator_feature_matrix(cur) -> pd.DataFrame:
    """
    Returns a DataFrame indexed by daily date with one column per indicator,
    each column being the indicator's stress_pct (0-100) forward-filled to daily.
    """
    raw = {}
    # TOTCI YoY
    totci = fetch_series(cur, "TOTCI")
    totci_yoy = compute_yoy(totci)
    raw["TOTCI"] = to_stress_pct(totci_yoy, inverted=True)

    # Spreads
    for sid, (num_id, den_id, abs_val) in SPREAD_DEFS.items():
        num = fetch_series(cur, num_id)
        den = fetch_series(cur, den_id)
        spread = compute_spread(num, den, abs_val)
        raw[sid] = to_stress_pct(spread, inverted=False)

    # Standard series
    for sid in ["DRCCLACBS", "DRCLACBS", "BAMLC0A0CM", "BAMLH0A0HYM2"]:
        s = fetch_series(cur, sid)
        raw[sid] = to_stress_pct(s, inverted=(sid in INVERTED))

    # Daily date range, forward-fill each indicator
    all_dates = pd.date_range(start="1990-01-01", end=pd.Timestamp.today().normalize(), freq="D")
    df = pd.DataFrame(index=all_dates)
    for sid in INDICATORS:
        col = raw.get(sid, pd.Series(dtype=float))
        if col.empty:
            df[sid] = np.nan
        else:
            df[sid] = col.reindex(all_dates).ffill()
    df.index.name = "date"
    return df


# ---- Regression ------------------------------------------------------------

def regress_and_extract_weights(features: pd.DataFrame, target: pd.Series):
    """
    OLS target ~ intercept + features.

    Negative coefficients are kept (they encode an inverse correlation: the
    indicator predicts *less* stress in this target). Coefficients are normalized
    by the max absolute value so the result is bounded in [-1, 1], with the most
    influential indicator at exactly ±1 and others scaled relatively.

    The dashboard's score formula direction-flips negative-weighted indicators,
    so a w = -0.4 is interpreted as: "(100 - stress_pct) of this indicator
    contributes with magnitude 0.4 to the sector score."

    Returns (weights_dict, y_hat_series). y_hat_series contains the model's
    prediction for every date in `features` where all 7 indicators are
    non-null — on the same scale as the target. Returns (uniform_weights, None)
    on fallback paths.
    """
    combined = pd.concat([target.rename("y"), features], axis=1, join="inner").dropna()
    if len(combined) < 30:
        print(f"    [warn] only {len(combined)} aligned obs; using uniform weights")
        return {ind: 1.0 for ind in INDICATORS}, None

    X = combined[INDICATORS].values
    y = combined["y"].values
    X = sm.add_constant(X, has_constant="add")
    try:
        model = sm.OLS(y, X).fit()
    except Exception as e:
        print(f"    [warn] OLS failed: {e}; using uniform weights")
        return {ind: 1.0 for ind in INDICATORS}, None

    raw_coefs = np.asarray(model.params[1:], dtype=float)  # predictor coefficients
    intercept = float(model.params[0])
    max_abs = np.max(np.abs(raw_coefs))
    if not np.isfinite(max_abs) or max_abs == 0:
        print(f"    [warn] all-zero or non-finite coefficients; using uniform weights")
        return {ind: 1.0 for ind in INDICATORS}, None

    scaled = raw_coefs / max_abs  # in [-1, 1], at least one |w| == 1
    weights = {ind: float(scaled[i]) for i, ind in enumerate(INDICATORS)}

    # Predict y_hat across the full feature matrix where every predictor is non-null.
    # Use the *raw* (un-normalized) coefficients so y_hat lands on the target's scale,
    # not on the [-1, 1] re-scaled axis.
    full = features[INDICATORS].dropna()
    if full.empty:
        return weights, None
    y_hat_values = intercept + full.values @ raw_coefs
    y_hat = pd.Series(y_hat_values, index=full.index, name="y_hat")
    return weights, y_hat


# ---- Model-fit persistence -------------------------------------------------

def persist_model_fit(cur, series_id: str, description: str, values: pd.Series) -> None:
    """
    Upsert a sentinel registry row + replace observations for a MODEL_* series.

    These rows are picked up by /data/inventory and become selectable from the
    Analyze Data dropdown so the fit can be overlaid against its target series.
    """
    cur.execute(
        """
        INSERT INTO series_registry
            (series_id, description, sector, signal_speed, update_frequency, fred_series_id, units)
        VALUES (%s, %s, 'derived', 'context', 'daily', NULL, 'model fit')
        ON CONFLICT (series_id) DO UPDATE SET description = EXCLUDED.description
        """,
        (series_id, description),
    )
    # Wipe any previous fit (no per-vintage history kept for model outputs)
    cur.execute("DELETE FROM series_observations WHERE series_id = %s", (series_id,))
    today = date.today()
    rows = [
        (series_id, d.date() if hasattr(d, "date") else d, today, float(v))
        for d, v in values.items()
        if pd.notna(v) and np.isfinite(v)
    ]
    if not rows:
        return
    # psycopg2 executemany is OK at this size (~13k rows × ~26 sectors)
    cur.executemany(
        """
        INSERT INTO series_observations (series_id, observation_date, vintage_date, value)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (series_id, observation_date, vintage_date) DO UPDATE SET value = EXCLUDED.value
        """,
        rows,
    )


# ---- Main ------------------------------------------------------------------

def main():
    conn = get_connection()
    cur = conn.cursor()

    # Idempotent cleanup: drop indicator_sector_map rows for any series no
    # longer in the predictor set (e.g. DRCRELEXFACBS after the circularity fix).
    cur.execute(
        "DELETE FROM indicator_sector_map WHERE series_id NOT IN %s",
        (tuple(INDICATORS),),
    )
    if cur.rowcount:
        print(f"[weights] Removed {cur.rowcount} stale indicator_sector_map rows.")

    print("[weights] Building indicator feature matrix...")
    features = build_indicator_feature_matrix(cur)
    print(f"  feature matrix shape: {features.shape}, "
          f"non-null per indicator: {features.notna().sum().to_dict()}")

    # Fetch sectors
    cur.execute("SELECT sector_id FROM sectors WHERE active ORDER BY sort_order, label")
    sector_ids = [r[0] for r in cur.fetchall()]

    print()
    print("[weights] Running regressions per sector...")
    for sector_id in sector_ids:
        print(f"  {sector_id}")

        # Equity-side
        eq_target = fetch_series(cur, f"DD_{sector_id}")
        if eq_target.empty:
            print(f"    [warn] no DD_{sector_id}; using uniform equity weights")
            eq_weights = {ind: 1.0 for ind in INDICATORS}
            eq_y_hat = None
        else:
            eq_weights, eq_y_hat = regress_and_extract_weights(features, eq_target)

        # Credit-side
        credit_target_id = SUB_SECTOR_CREDIT_TARGETS.get(sector_id, "CC_AGG")
        cr_target = fetch_series(cur, credit_target_id)
        if cr_target.empty:
            print(f"    [warn] no {credit_target_id}; using uniform credit weights")
            cr_weights = {ind: 1.0 for ind in INDICATORS}
            cr_y_hat = None
        else:
            cr_weights, cr_y_hat = regress_and_extract_weights(features, cr_target)

        # Persist model fits as series so they're plottable from Analyze Data.
        if eq_y_hat is not None:
            persist_model_fit(
                cur,
                series_id=f"MODEL_DD_{sector_id}",
                description=f"OLS fit of DD_{sector_id} on {len(INDICATORS)} indicators",
                values=eq_y_hat,
            )
        if cr_y_hat is not None:
            persist_model_fit(
                cur,
                series_id=f"MODEL_{credit_target_id}",
                description=f"OLS fit of {credit_target_id} on {len(INDICATORS)} indicators",
                values=cr_y_hat,
            )

        # Persist
        for ind in INDICATORS:
            cur.execute(
                """
                INSERT INTO indicator_sector_map
                    (series_id, sector_id, weight, weight_source, weight_credit, weight_equity)
                VALUES (%s, %s, %s, 'regression_v1', %s, %s)
                ON CONFLICT (series_id, sector_id) DO UPDATE
                  SET weight        = EXCLUDED.weight,
                      weight_credit = EXCLUDED.weight_credit,
                      weight_equity = EXCLUDED.weight_equity,
                      weight_source = 'regression_v1'
                """,
                (
                    ind,
                    sector_id,
                    0.5 * cr_weights[ind] + 0.5 * eq_weights[ind],
                    cr_weights[ind],
                    eq_weights[ind],
                ),
            )

        # Pretty print top contributors per side
        eq_top = sorted(eq_weights.items(), key=lambda x: -x[1])[:3]
        cr_top = sorted(cr_weights.items(), key=lambda x: -x[1])[:3]
        print(f"    equity top: {[(k, round(v, 2)) for k, v in eq_top]}")
        print(f"    credit top: {[(k, round(v, 2)) for k, v in cr_top]} (target={credit_target_id})")

    conn.commit()
    cur.close()
    conn.close()
    print()
    print("[weights] Done.")


if __name__ == "__main__":
    main()
