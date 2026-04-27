import os
import requests
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()

FRED_API_KEY = os.getenv("FRED_API_KEY")
FRED_BASE_URL = "https://api.stlouisfed.org/fred"

# Series with dense revision history that exceed the 100k vintage observation limit.
# For these, we skip vintage dating and store today as the vintage for all history.
SKIP_VINTAGE = {"TOTCI", "NFCICREDIT", "STLFSI4"}


def _get(endpoint: str, params: dict) -> dict:
    params["api_key"] = FRED_API_KEY
    params["file_type"] = "json"
    response = requests.get(f"{FRED_BASE_URL}/{endpoint}", params=params)
    response.raise_for_status()
    return response.json()


def get_observations(series_id: str, observation_start: str = "1990-01-01") -> list[dict]:
    """
    Fetch all observations for a series.
    Returns list of {observation_date, vintage_date, value}.

    Attempts to fetch with full vintage history first. If the series does not
    support vintage dating, falls back to current values with today as vintage.
    """
    today = date.today().isoformat()

    if series_id in SKIP_VINTAGE:
        # Dense revision history — skip vintage dating to avoid 100k limit
        data = _get("series/observations", {
            "series_id": series_id,
            "observation_start": observation_start,
            "sort_order": "asc",
        })
        vintage_available = False
    else:
        try:
            data = _get("series/observations", {
                "series_id": series_id,
                "observation_start": observation_start,
                "realtime_start": "1776-07-04",
                "realtime_end": today,
                "sort_order": "asc",
            })
            vintage_available = True
        except Exception:
            data = _get("series/observations", {
                "series_id": series_id,
                "observation_start": observation_start,
                "sort_order": "asc",
            })
            vintage_available = False

    rows = []
    for obs in data.get("observations", []):
        if obs["value"] == ".":
            continue
        rows.append({
            "observation_date": obs["date"],
            "vintage_date": obs.get("realtime_start", obs["date"]) if vintage_available else obs["date"],
            "value": float(obs["value"]),
        })
    return rows


def get_vintage_dates(series_id: str) -> list[str]:
    """
    Returns all dates on which this series was revised.
    Used to know when to re-fetch for point-in-time accuracy.
    """
    data = _get("series/vintagedates", {"series_id": series_id})
    return data.get("vintage_dates", [])


def get_latest_observation(series_id: str) -> dict | None:
    """
    Fetch only the most recent observation for a series.
    Used by the staleness tracker to check for new data.
    """
    data = _get("series/observations", {
        "series_id": series_id,
        "sort_order": "desc",
        "limit": 1,
    })
    obs_list = data.get("observations", [])
    if not obs_list or obs_list[0]["value"] == ".":
        return None
    obs = obs_list[0]
    return {
        "observation_date": obs["date"],
        "vintage_date": date.today().isoformat(),
        "value": float(obs["value"]),
    }
