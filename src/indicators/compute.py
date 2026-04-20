"""
Indicator computation layer.

Takes raw observations from the database and produces normalized stress scores
for each series and each sector.

Normalization: percentile rank against the full available history for that series.
  - 100 = most stressed ever observed
  - 0   = least stressed ever observed
  - 50  = median historical conditions

Direction: for most series, higher value = more stress (spreads, delinquency rates).
           For TOTCI (loan volume), higher = less stress — we invert it.

Spread indicators (CC_SPREAD, DFF_SOFR_SPREAD) are computed at query time from
two stored raw series. Higher spread = more stress (no inversion needed).

Signal design notes:
  - CRE has one signal only (DRCRELEXFACBS). FRED has no free series for commercial
    vacancy; residential vacancy (RRVRUSQ156N) is anticorrelated with office stress
    and has been excluded. This is a documented gap.
  - NFCICREDIT is a broad economy-wide credit index, not CRE-specific. Excluded.
  - Bank fast signal (DFF_SOFR_SPREAD) uses SOFR data from April 2018 onward only.
    Pre-2018 calibration is therefore unavailable; this limits backtest confidence
    before that date.
"""

from datetime import date
from db import get_connection

# Series where a higher value means LESS stress — invert the percentile
INVERTED_SERIES = {"TOTCI"}

# Series where we compute YoY % change rather than using the raw level
# (level series that trend upward with inflation — absolute value is meaningless)
YOY_SERIES = {"TOTCI"}

# Spread indicators: computed from two raw stored series.
# Both components must be in series_registry and backfilled.
# Higher spread = more stress (no inversion).
SPREAD_SERIES = {
    "DFF_SOFR_SPREAD": {
        "numerator_id":   "DFF",
        "denominator_id": "SOFR",
        "label":          "Interbank Rate Dislocation (|DFF\u2212SOFR|)",
        "display_unit":   "pct pts",
        "absolute_value": True,   # stress in either direction: repo stress → SOFR spikes;
                                  # unsecured stress → DFF spikes. |spread| captures both.
    },
    "CC_SPREAD": {
        "numerator_id":   "TERMCBCCALLNS",
        "denominator_id": "FEDFUNDS",
        "label":          "Credit Card Rate Spread over Fed Funds",
        "display_unit":   "pct pts",
        "absolute_value": False,
    },
}

# Sector membership — which series belong to which sector
SECTOR_MAP = {
    "banks":     ["TOTCI", "DFF_SOFR_SPREAD"],
    "consumer":  ["CC_SPREAD", "DRCCLACBS", "DRCLACBS"],
    "cre":       ["DRCRELEXFACBS"],
    "corporate": ["BAMLC0A0CM", "BAMLH0A0HYM2"],
}

# Human-readable labels (spread IDs are virtual — not real series_ids in the DB)
SERIES_LABELS = {
    "TOTCI":           "C&I Loan Volume",
    "DFF_SOFR_SPREAD": "Interbank Rate Dislocation",
    "CC_SPREAD":       "Credit Card Rate Spread",
    "DRCCLACBS":       "Credit Card Delinquency Rate",
    "DRCLACBS":        "Consumer Loan Delinquency Rate",
    "DRCRELEXFACBS":   "CRE Loan Delinquency Rate",
    "BAMLC0A0CM":      "IG Corporate Spread",
    "BAMLH0A0HYM2":    "HY Corporate Spread",
}

SECTOR_LABELS = {
    "banks":     "Bank Stress",
    "consumer":  "Consumer Credit Stress",
    "cre":       "Commercial Real Estate Stress",
    "corporate": "Corporate Credit Stress",
}


def _compute_percentile(value: float, historical_values: list[float], inverted: bool) -> float:
    """
    Compute the stress percentile of a value against its historical distribution.
    Returns a float in [0, 100] where 100 = maximum historical stress.
    """
    if not historical_values:
        return 50.0  # no history, return neutral

    n = len(historical_values)
    rank = sum(1 for v in historical_values if v <= value)
    pct = (rank / n) * 100

    if inverted:
        pct = 100 - pct  # higher value = less stress, so invert

    return round(pct, 1)


def _fetch_series_map(cur, series_id: str, as_of_date: date) -> dict:
    """Fetch all observations for a series as a date→value dict, as of the given date."""
    cur.execute(
        """
        SELECT DISTINCT ON (observation_date)
            observation_date, value
        FROM series_observations
        WHERE series_id = %s
          AND vintage_date <= %s
          AND value IS NOT NULL
        ORDER BY observation_date ASC, vintage_date DESC
        """,
        (series_id, as_of_date),
    )
    return {row[0]: float(row[1]) for row in cur.fetchall()}


def _compute_yoy_series(cur, series_id: str, as_of_date: date) -> tuple[float | None, list[float]]:
    """
    For level series (like TOTCI), compute year-over-year % change for every observation.
    Returns (current_yoy, list_of_all_yoy_values).
    """
    cur.execute(
        """
        SELECT DISTINCT ON (observation_date)
            observation_date, value
        FROM series_observations
        WHERE series_id = %s
          AND vintage_date <= %s
          AND value IS NOT NULL
        ORDER BY observation_date ASC, vintage_date DESC
        """,
        (series_id, as_of_date),
    )
    rows = cur.fetchall()

    if len(rows) < 53:  # need at least a year of weekly data
        return None, []

    # Build a dict of date -> value for fast lookup
    obs_map = {row[0]: float(row[1]) for row in rows}
    dates = sorted(obs_map.keys())

    from datetime import timedelta
    yoy_values = []
    for d in dates:
        # Find closest observation ~52 weeks ago (handle Feb 29 on leap years)
        try:
            target = d.replace(year=d.year - 1)
        except ValueError:
            target = d.replace(year=d.year - 1, day=28)
        # Search within ±4 weeks
        candidates = [
            cd for cd in dates
            if abs((cd - target).days) <= 28
        ]
        if not candidates:
            continue
        closest = min(candidates, key=lambda cd: abs((cd - target).days))
        prior_val = obs_map[closest]
        if prior_val != 0:
            yoy = ((obs_map[d] - prior_val) / prior_val) * 100
            yoy_values.append((d, yoy))

    if not yoy_values:
        return None, []

    all_yoy = [v for _, v in yoy_values]
    current_yoy = yoy_values[-1][1]
    return round(current_yoy, 2), all_yoy


def _compute_spread_series(
    cur, spec: dict, as_of_date: date
) -> tuple[float | None, list[float], dict | None]:
    """
    Compute a spread indicator: numerator_series − denominator_series.
    Forward-fills the denominator into numerator dates, so monthly denominators
    align cleanly with daily numerators.
    Returns (current_spread, all_historical_spreads, metadata_dict).
    """
    num_map = _fetch_series_map(cur, spec["numerator_id"], as_of_date)
    den_map = _fetch_series_map(cur, spec["denominator_id"], as_of_date)

    if not num_map or not den_map:
        return None, [], None

    use_abs = spec.get("absolute_value", False)
    den_dates = sorted(den_map.keys())
    spreads = []
    for obs_date in sorted(num_map.keys()):
        # Most recent denominator observation on or before obs_date
        candidates = [d for d in den_dates if d <= obs_date]
        if not candidates:
            continue
        den_val = den_map[candidates[-1]]
        raw_spread = num_map[obs_date] - den_val
        spreads.append((obs_date, abs(raw_spread) if use_abs else raw_spread))

    if not spreads:
        return None, [], None

    all_spread_values = [v for _, v in spreads]
    current_date, current_spread = spreads[-1]

    return (
        round(current_spread, 4),
        all_spread_values,
        {
            "observation_date": current_date.isoformat(),
            "vintage_date":     current_date.isoformat(),
        },
    )


def _get_historical_values(cur, series_id: str, as_of_date: date) -> list[float]:
    """Fetch all historical values for a series available as of the given date."""
    cur.execute(
        """
        SELECT DISTINCT ON (observation_date)
            value
        FROM series_observations
        WHERE series_id = %s
          AND vintage_date <= %s
          AND value IS NOT NULL
        ORDER BY observation_date, vintage_date DESC
        """,
        (series_id, as_of_date),
    )
    return [row[0] for row in cur.fetchall()]


def _get_current_value(cur, series_id: str, as_of_date: date) -> dict | None:
    """Get the most recent observation for a series as of the given date."""
    cur.execute(
        """
        SELECT DISTINCT ON (observation_date)
            observation_date, vintage_date, value
        FROM series_observations
        WHERE series_id = %s
          AND vintage_date <= %s
          AND value IS NOT NULL
        ORDER BY observation_date DESC, vintage_date DESC
        LIMIT 1
        """,
        (series_id, as_of_date),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "observation_date": row[0].isoformat(),
        "vintage_date":     row[1].isoformat(),
        "value":            float(row[2]),
    }


def _get_staleness(cur, series_id: str) -> str:
    """Get the current staleness status for a series."""
    cur.execute(
        "SELECT status FROM staleness_state WHERE series_id = %s",
        (series_id,)
    )
    row = cur.fetchone()
    return row[0] if row else "unknown"


def _get_worst_staleness(cur, series_ids: list[str]) -> str:
    """Return the worst staleness status across a list of component series."""
    priority = {"overdue": 4, "pending": 3, "fresh": 2, "historical": 1, "unknown": 0}
    worst = "unknown"
    for sid in series_ids:
        s = _get_staleness(cur, sid)
        if priority.get(s, 0) > priority.get(worst, 0):
            worst = s
    return worst


def compute_dashboard(as_of: date = None) -> dict:
    """
    Compute the full dashboard state as of the given date.
    If as_of is None, uses today (live dashboard mode).

    Returns a structured dict with:
      - series: per-series details with current value and stress percentile
      - sectors: per-sector aggregated stress score
      - as_of_date: the date used for computation
      - is_live: whether this is a live or historical (backtest) computation
    """
    is_live = as_of is None
    if as_of is None:
        as_of = date.today()

    conn = get_connection()
    cur = conn.cursor()

    series_results = {}

    for series_id, label in SERIES_LABELS.items():
        inverted = series_id in INVERTED_SERIES

        # --- Spread indicators (computed from two raw series) ---
        if series_id in SPREAD_SERIES:
            spec = SPREAD_SERIES[series_id]
            current_spread, all_spreads, meta = _compute_spread_series(cur, spec, as_of)
            if current_spread is None or not all_spreads:
                series_results[series_id] = {
                    "label": label, "value": None, "observation_date": None,
                    "vintage_date": None, "stress_pct": None, "staleness": "no_data",
                    "display_unit": spec["display_unit"],
                }
                continue
            stress_pct = _compute_percentile(current_spread, all_spreads, inverted=False)
            staleness = (
                _get_worst_staleness(cur, [spec["numerator_id"], spec["denominator_id"]])
                if is_live else "historical"
            )
            series_results[series_id] = {
                "label":            label,
                "value":            current_spread,
                "observation_date": meta["observation_date"],
                "vintage_date":     meta["vintage_date"],
                "stress_pct":       stress_pct,
                "staleness":        staleness,
                "display_unit":     spec["display_unit"],
            }
            continue

        # --- YoY series (level series transformed to growth rate) ---
        if series_id in YOY_SERIES:
            current_yoy, all_yoy = _compute_yoy_series(cur, series_id, as_of)
            if current_yoy is None:
                series_results[series_id] = {
                    "label": label, "value": None, "observation_date": None,
                    "vintage_date": None, "stress_pct": None, "staleness": "no_data",
                    "display_unit": "yoy %",
                }
                continue
            stress_pct = _compute_percentile(current_yoy, all_yoy, inverted)
            current = _get_current_value(cur, series_id, as_of)
            series_results[series_id] = {
                "label":            label,
                "value":            current_yoy,
                "observation_date": current["observation_date"] if current else None,
                "vintage_date":     current["vintage_date"] if current else None,
                "stress_pct":       stress_pct,
                "staleness":        _get_staleness(cur, series_id) if is_live else "historical",
                "display_unit":     "yoy %",
            }
            continue

        # --- Standard series ---
        current = _get_current_value(cur, series_id, as_of)
        if current is None:
            series_results[series_id] = {
                "label": label, "value": None, "observation_date": None,
                "vintage_date": None, "stress_pct": None, "staleness": "no_data",
                "display_unit": "",
            }
            continue

        historical = _get_historical_values(cur, series_id, as_of)
        stress_pct = _compute_percentile(current["value"], historical, inverted)

        series_results[series_id] = {
            "label":            label,
            "value":            current["value"],
            "observation_date": current["observation_date"],
            "vintage_date":     current["vintage_date"],
            "stress_pct":       stress_pct,
            "staleness":        _get_staleness(cur, series_id) if is_live else "historical",
            "display_unit":     "%",
        }

    # Compute per-sector scores as the average of available sub-indicator percentiles
    sector_results = {}
    for sector, members in SECTOR_MAP.items():
        available = [
            series_results[sid]["stress_pct"]
            for sid in members
            if sid in series_results and series_results[sid]["stress_pct"] is not None
        ]
        sector_score = round(sum(available) / len(available), 1) if available else None
        sector_results[sector] = {
            "label":      SECTOR_LABELS[sector],
            "score":      sector_score,
            "components": members,
        }

    cur.close()
    conn.close()

    return {
        "as_of_date": as_of.isoformat(),
        "is_live":    is_live,
        "sectors":    sector_results,
        "series":     series_results,
    }
