"""
Credit Stress Dashboard API

Endpoints:
  GET /dashboard/current          — live dashboard state
  GET /dashboard/asof/{date}      — point-in-time (backtest) state
  GET /series/{series_id}/history — full time series for a single indicator
  GET /health                     — liveness check
"""

import os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "ingestion"))
sys.path.insert(0, os.path.join(_HERE, "..", "indicators"))

from datetime import date
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware

from compute import compute_dashboard
from db import get_connection

app = FastAPI(title="Credit Stress Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "PUT", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


_GROUPS = {"pe", "credit", "both"}


def _validate_group(group: str | None) -> str | None:
    if group is None:
        return None
    if group not in _GROUPS:
        raise HTTPException(status_code=400, detail=f"group must be one of {sorted(_GROUPS)}")
    return group


@app.get("/sectors")
def sectors_metadata():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT sector_id, label, sector_group, sort_order
        FROM sectors
        WHERE active
        ORDER BY sort_order, label
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {"sector_id": r[0], "label": r[1], "group": r[2], "sort_order": r[3]}
        for r in rows
    ]


@app.put("/sectors/{sector_id}/weights")
def update_sector_weights(
    sector_id: str,
    weights: dict = Body(...),
    snapshot: bool = Query(default=True),
    name: str | None = Query(default=None),
):
    if not isinstance(weights, dict) or not weights:
        raise HTTPException(status_code=400, detail="Body must be a {series_id: weight} object")
    for sid, w in weights.items():
        try:
            w_num = float(w)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"weight for {sid} must be numeric")
        if w_num < 0 or w_num > 1:
            raise HTTPException(status_code=400, detail=f"weight for {sid} must be in [0, 1]")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sectors WHERE sector_id = %s AND active", (sector_id,))
    if not cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail=f"Unknown or inactive sector: {sector_id}")

    for sid, w in weights.items():
        cur.execute(
            """
            INSERT INTO indicator_sector_map (series_id, sector_id, weight, weight_source)
            VALUES (%s, %s, %s, 'user_override')
            ON CONFLICT (series_id, sector_id) DO UPDATE
              SET weight = EXCLUDED.weight, weight_source = 'user_override'
            """,
            (sid, sector_id, float(w)),
        )

    # Snapshot the full sector weight set into the versions table for history/toggle.
    # Skipped (snapshot=false) for non-user-meaningful updates like Reset to Default.
    if snapshot:
        import json
        cur.execute(
            "SELECT series_id, weight FROM indicator_sector_map WHERE sector_id = %s",
            (sector_id,),
        )
        full_weights = {row[0]: float(row[1]) for row in cur.fetchall()}
        clean_name = (name or "").strip() or None
        cur.execute(
            """
            INSERT INTO sector_weight_versions (sector_id, weights, name)
            VALUES (%s, %s::jsonb, %s)
            """,
            (sector_id, json.dumps(full_weights), clean_name),
        )

    conn.commit()
    cur.close()
    conn.close()
    return {"ok": True, "sector_id": sector_id, "updated": len(weights)}


@app.put("/sectors/{sector_id}/weight-versions/{version_id}")
def update_weight_version(sector_id: str, version_id: int, body: dict = Body(...)):
    weights = body.get("weights")
    name = body.get("name")
    has_weights = weights is not None
    has_name = name is not None
    if not has_weights and not has_name:
        raise HTTPException(status_code=400, detail="Body must include 'weights' and/or 'name'")

    if has_weights:
        if not isinstance(weights, dict) or not weights:
            raise HTTPException(status_code=400, detail="'weights' must be a non-empty object")
        for sid, w in weights.items():
            try:
                w_num = float(w)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"weight for {sid} must be numeric")
            if w_num < 0 or w_num > 1:
                raise HTTPException(status_code=400, detail=f"weight for {sid} must be in [0, 1]")

    clean_name = (name.strip() if isinstance(name, str) else None) or None if has_name else None

    import json
    conn = get_connection()
    cur = conn.cursor()
    if has_weights and has_name:
        cur.execute(
            "UPDATE sector_weight_versions SET weights = %s::jsonb, name = %s WHERE version_id = %s AND sector_id = %s",
            (json.dumps({k: float(v) for k, v in weights.items()}), clean_name, version_id, sector_id),
        )
    elif has_weights:
        cur.execute(
            "UPDATE sector_weight_versions SET weights = %s::jsonb WHERE version_id = %s AND sector_id = %s",
            (json.dumps({k: float(v) for k, v in weights.items()}), version_id, sector_id),
        )
    else:
        cur.execute(
            "UPDATE sector_weight_versions SET name = %s WHERE version_id = %s AND sector_id = %s",
            (clean_name, version_id, sector_id),
        )
    rowcount = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"ok": True, "version_id": version_id}


@app.delete("/sectors/{sector_id}/weight-versions/{version_id}")
def delete_weight_version(sector_id: str, version_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM sector_weight_versions WHERE version_id = %s AND sector_id = %s",
        (version_id, sector_id),
    )
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"ok": True, "deleted": deleted}


@app.get("/sectors/{sector_id}/weight-versions")
def list_sector_weight_versions(sector_id: str, limit: int = 10):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be in [1, 100]")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT version_id, saved_at, weights, name
        FROM sector_weight_versions
        WHERE sector_id = %s
        ORDER BY saved_at DESC
        LIMIT %s
        """,
        (sector_id, limit),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {"version_id": r[0], "saved_at": r[1].isoformat(), "weights": r[2], "name": r[3]}
        for r in rows
    ]


def _parse_alpha(alpha: str | None) -> float | None:
    if alpha is None or alpha == "":
        return None
    try:
        v = float(alpha)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"alpha must be a number in [0, 1]; got {alpha!r}")
    if v < 0 or v > 1:
        raise HTTPException(status_code=400, detail=f"alpha must be in [0, 1]; got {v}")
    return v


def _parse_alpha_overrides(raw: str | None) -> dict | None:
    """Accepts a JSON object string {sector_id: alpha} or returns None."""
    if not raw:
        return None
    import json
    try:
        obj = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="alpha_overrides must be a JSON object")
    if not isinstance(obj, dict):
        raise HTTPException(status_code=400, detail="alpha_overrides must be a JSON object")
    out = {}
    for k, v in obj.items():
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"alpha_overrides[{k}] must be numeric")
        if f < 0 or f > 1:
            raise HTTPException(status_code=400, detail=f"alpha_overrides[{k}] must be in [0, 1]")
        out[str(k)] = f
    return out


@app.get("/dashboard/current")
def dashboard_current(
    group: str | None = Query(default=None),
    alpha: str | None = Query(default=None),
    alpha_overrides: str | None = Query(default=None),
):
    return compute_dashboard(
        group=_validate_group(group),
        alpha=_parse_alpha(alpha),
        alpha_overrides=_parse_alpha_overrides(alpha_overrides),
    )


@app.get("/dashboard/asof/{as_of_date}")
def dashboard_asof(
    as_of_date: str,
    group: str | None = Query(default=None),
    alpha: str | None = Query(default=None),
    alpha_overrides: str | None = Query(default=None),
):
    try:
        d = date.fromisoformat(as_of_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Date must be in YYYY-MM-DD format")
    if d > date.today():
        raise HTTPException(status_code=400, detail="Cannot query a future date")
    return compute_dashboard(
        as_of=d,
        group=_validate_group(group),
        alpha=_parse_alpha(alpha),
        alpha_overrides=_parse_alpha_overrides(alpha_overrides),
    )


@app.get("/data/acquisitions")
def acquisitions_inventory():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT company, acq_date, report_date, book_value, acquirer_name,
               acq_uninum, deal_price_millions, price_per_share,
               consideration_type, edgar_adsh, announcement_date, acquirer_hc_name
        FROM acquisitions
        ORDER BY acq_date DESC, company
        """
    )
    rows = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM acquisitions")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM acquisitions WHERE deal_price_millions IS NOT NULL")
    priced = cur.fetchone()[0]
    cur.close()
    conn.close()
    return {
        "total": total,
        "priced": priced,
        "items": [
            {
                "company":             r[0],
                "acq_date":            r[1].isoformat() if r[1] else None,
                "report_date":         r[2].isoformat() if r[2] else None,
                "book_value":          float(r[3]) if r[3] is not None else None,
                "acquirer_name":       r[4],
                "acq_uninum":          r[5],
                "deal_price_millions": float(r[6]) if r[6] is not None else None,
                "price_per_share":     float(r[7]) if r[7] is not None else None,
                "consideration_type":  r[8],
                "edgar_adsh":          r[9],
                "announcement_date":   r[10].isoformat() if r[10] else None,
                "acquirer_hc_name":    r[11],
            }
            for r in rows
        ],
    }


@app.post("/data/catch-up")
def trigger_catch_up():
    from fred_ingest import catch_up
    try:
        results = catch_up()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Catch-up failed: {e}")
    total_added = sum(r["added"] for r in results)
    return {"ok": True, "total_added": total_added, "results": results}


@app.get("/analysis/proxies")
def analysis_proxies():
    """List derived stress-proxy series (DD_*, CC_*, CC_AGG) with date ranges."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT r.series_id, r.description,
               COUNT(o.observation_date) AS obs_count,
               MIN(o.observation_date) AS earliest,
               MAX(o.observation_date) AS latest
        FROM series_registry r
        LEFT JOIN series_observations o ON o.series_id = r.series_id
        WHERE r.series_id LIKE 'DD\\_%' ESCAPE '\\'
           OR r.series_id LIKE 'CC\\_%' ESCAPE '\\'
           OR r.series_id = 'CC_AGG'
        GROUP BY r.series_id, r.description
        ORDER BY
          CASE
            WHEN r.series_id LIKE 'DD\\_%' ESCAPE '\\' THEN 1
            WHEN r.series_id = 'CC_AGG' THEN 2
            ELSE 3
          END,
          r.series_id
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "series_id":  r[0],
            "kind":       "drawdown" if r[0].startswith("DD_") else ("aggregate_credit" if r[0] == "CC_AGG" else "credit_composite"),
            "description": r[1],
            "obs_count":  int(r[2] or 0),
            "earliest":   r[3].isoformat() if r[3] else None,
            "latest":     r[4].isoformat() if r[4] else None,
        }
        for r in rows
    ]


@app.get("/analysis/weights")
def analysis_weights():
    """Per-sector indicator weights: legacy weight + dual columns (credit/equity) + source tag."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.sector_id, s.label, s.sector_group, s.sort_order,
               m.series_id, m.weight, m.weight_source, m.weight_credit, m.weight_equity
        FROM sectors s
        LEFT JOIN indicator_sector_map m ON m.sector_id = s.sector_id
        WHERE s.active
        ORDER BY s.sort_order, m.series_id
        """
    )
    out = {}
    for sid, label, group, sort_order, series_id, w, src, w_c, w_e in cur.fetchall():
        if sid not in out:
            out[sid] = {"label": label, "group": group, "sort_order": sort_order, "weights": []}
        if series_id is not None:
            out[sid]["weights"].append({
                "series_id": series_id,
                "weight":          float(w) if w is not None else None,
                "weight_credit":   float(w_c) if w_c is not None else None,
                "weight_equity":   float(w_e) if w_e is not None else None,
                "weight_source":   src,
            })
    cur.close()
    conn.close()
    return out


@app.post("/analysis/run-regression")
def run_regression():
    """
    Trigger the full derive pipeline (stress proxies → regression). Returns a
    summary of what was rebuilt: counts per derived series and per-sector weight
    snapshots.
    """
    import subprocess, sys as _sys, os as _os
    analysis_dir = _os.path.join(_os.path.dirname(__file__), "..", "analysis")
    try:
        # Step 1: derive stress proxies (writes DD_*, CC_*, CC_AGG into series_observations)
        r1 = subprocess.run(
            [_sys.executable, "derive_stress_proxies.py"],
            cwd=analysis_dir, capture_output=True, text=True, timeout=300,
        )
        if r1.returncode != 0:
            raise HTTPException(status_code=500, detail=f"derive_stress_proxies failed: {r1.stderr[-500:]}")

        # Step 2: derive weights
        r2 = subprocess.run(
            [_sys.executable, "derive_weights.py"],
            cwd=analysis_dir, capture_output=True, text=True, timeout=300,
        )
        if r2.returncode != 0:
            raise HTTPException(status_code=500, detail=f"derive_weights failed: {r2.stderr[-500:]}")

        return {
            "ok": True,
            "stress_proxies_log": r1.stdout[-2000:],
            "regression_log":     r2.stdout[-2000:],
        }
    except HTTPException:
        raise
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Regression timed out (>5min)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")


@app.get("/data/inventory")
def data_inventory():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
          r.series_id,
          r.description,
          r.update_frequency,
          r.units,
          COUNT(o.observation_date) AS obs_count,
          MIN(o.observation_date) AS earliest,
          MAX(o.observation_date) AS latest,
          (SELECT value FROM series_observations
            WHERE series_id = r.series_id
              AND value IS NOT NULL
            ORDER BY observation_date DESC, vintage_date DESC
            LIMIT 1) AS latest_value
        FROM series_registry r
        LEFT JOIN series_observations o ON o.series_id = r.series_id
        GROUP BY r.series_id, r.description, r.update_frequency, r.units
        ORDER BY r.series_id
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "series_id":     r[0],
            "description":   r[1],
            "frequency":     r[2],
            "units":         r[3],
            "obs_count":     int(r[4] or 0),
            "earliest":      r[5].isoformat() if r[5] else None,
            "latest":        r[6].isoformat() if r[6] else None,
            "latest_value":  float(r[7]) if r[7] is not None else None,
        }
        for r in rows
    ]


@app.get("/series/{series_id}/observation/{observation_date}/vintages")
def observation_vintages(series_id: str, observation_date: str):
    try:
        date.fromisoformat(observation_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="observation_date must be YYYY-MM-DD")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT vintage_date, value
        FROM series_observations
        WHERE series_id = %s AND observation_date = %s
        ORDER BY vintage_date DESC
        """,
        (series_id, observation_date),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail="No vintages for that observation")
    return {
        "series_id":        series_id,
        "observation_date": observation_date,
        "vintages": [
            {"vintage_date": r[0].isoformat(), "value": float(r[1]) if r[1] is not None else None}
            for r in rows
        ],
    }


@app.get("/series/{series_id}/history")
def series_history(series_id: str, start: str = "2000-01-01", end: str = None, vintage: str = None):
    end_date = date.today().isoformat() if end is None else end
    vintage_date = end_date if vintage is None else vintage
    try:
        date.fromisoformat(start)
        date.fromisoformat(end_date)
        date.fromisoformat(vintage_date)
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
        (series_id, start, end_date, vintage_date),
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
        "vintage":   vintage_date,
        "data":      [{"date": row[0].isoformat(), "value": float(row[1])} for row in rows],
    }


@app.get("/analysis-plots")
def list_analysis_plots(limit: int = 50):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be in [1, 200]")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT plot_id, name, saved_at, series_ids, start_date, end_date, vintage_date
        FROM analysis_plots
        ORDER BY saved_at DESC
        LIMIT %s
        """,
        (limit,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "plot_id":      r[0],
            "name":         r[1],
            "saved_at":     r[2].isoformat(),
            "series_ids":   r[3],
            "start_date":   r[4].isoformat(),
            "end_date":     r[5].isoformat(),
            "vintage_date": r[6].isoformat(),
        }
        for r in rows
    ]


@app.post("/analysis-plots")
def create_analysis_plot(body: dict = Body(...)):
    name = body.get("name")
    series_ids = body.get("series_ids")
    start_date = body.get("start_date")
    end_date = body.get("end_date")
    vintage_date = body.get("vintage_date")
    if not isinstance(series_ids, list) or not series_ids:
        raise HTTPException(status_code=400, detail="series_ids must be a non-empty list")
    if not all(isinstance(s, str) and s for s in series_ids):
        raise HTTPException(status_code=400, detail="series_ids entries must be non-empty strings")
    for label, val in (("start_date", start_date), ("end_date", end_date), ("vintage_date", vintage_date)):
        if not isinstance(val, str):
            raise HTTPException(status_code=400, detail=f"{label} required")
        try:
            date.fromisoformat(val)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"{label} must be YYYY-MM-DD")
    clean_name = (name.strip() if isinstance(name, str) else None) or None

    import json
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO analysis_plots (name, series_ids, start_date, end_date, vintage_date)
        VALUES (%s, %s::jsonb, %s, %s, %s)
        RETURNING plot_id, saved_at
        """,
        (clean_name, json.dumps(series_ids), start_date, end_date, vintage_date),
    )
    plot_id, saved_at = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return {"ok": True, "plot_id": plot_id, "saved_at": saved_at.isoformat()}


@app.put("/analysis-plots/{plot_id}")
def rename_analysis_plot(plot_id: int, body: dict = Body(...)):
    name = body.get("name")
    clean_name = (name.strip() if isinstance(name, str) else None) or None
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE analysis_plots SET name = %s WHERE plot_id = %s", (clean_name, plot_id))
    rowcount = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Plot not found")
    return {"ok": True, "plot_id": plot_id}


@app.delete("/analysis-plots/{plot_id}")
def delete_analysis_plot(plot_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM analysis_plots WHERE plot_id = %s", (plot_id,))
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Plot not found")
    return {"ok": True, "deleted": deleted}
