"""
Credit Stress Dashboard API

Endpoints:
  GET /dashboard/current          — live dashboard state
  GET /dashboard/asof/{date}      — point-in-time (backtest) state
  GET /series/{series_id}/history — full time series for a single indicator
  GET /health                     — liveness check
"""

import sys
sys.path.insert(0, "../ingestion")
sys.path.insert(0, "../indicators")

from datetime import date
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from compute import compute_dashboard
from db import get_connection

app = FastAPI(title="Credit Stress Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/dashboard/current")
def dashboard_current():
    return compute_dashboard()


@app.get("/dashboard/asof/{as_of_date}")
def dashboard_asof(as_of_date: str):
    try:
        d = date.fromisoformat(as_of_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Date must be in YYYY-MM-DD format")
    if d > date.today():
        raise HTTPException(status_code=400, detail="Cannot query a future date")
    return compute_dashboard(as_of=d)


@app.get("/series/{series_id}/history")
def series_history(series_id: str, start: str = "2000-01-01", end: str = None):
    end_date = date.today().isoformat() if end is None else end
    try:
        date.fromisoformat(start)
        date.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Dates must be in YYYY-MM-DD format")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT DISTINCT ON (observation_date)
            observation_date, value
        FROM series_observations
        WHERE series_id = %s
          AND observation_date BETWEEN %s AND %s
          AND vintage_date <= %s
          AND value IS NOT NULL
        ORDER BY observation_date ASC, vintage_date DESC
        """,
        (series_id, start, end_date, end_date),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No data found for series {series_id}")

    return {
        "series_id": series_id,
        "start":     start,
        "end":       end_date,
        "data":      [{"date": row[0].isoformat(), "value": float(row[1])} for row in rows],
    }
