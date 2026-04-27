# Debugger Rules — Architectural Facts

This file is maintained by the **Diagrammer** agent, not the Debugger. The Debugger reads it on every run and treats every entry as a binding architectural fact about the codebase (what modules do, how they connect, where PD / LGD / pricing logic lives, which module owns which data).

The human does not normally edit this file. If the Debugger disagrees with an entry after inspecting the code, it reports the contradiction in its output so the human can resolve it — the Debugger does not self-edit.

## Format
Append new entries to the bottom. Never reorder or delete (supersede instead). Each entry:

```
### YYYY-MM-DD — short title
Fact: <one or two sentences stating the architectural fact>
Source: diagrammer-run <YYYY-MM-DD> | human-correction-relayed-by-diagrammer
Affects: <module path(s) or pipeline name(s) this fact governs>
```

Supersede an older fact by writing a new dated entry that says `Supersedes: <title of older fact>` on its own line, followed by the new fact.

---

<!-- Appended facts go below this line. -->

### 2026-04-25 — Repo contains two distinct products that share only Postgres
Fact: This repo implements two separate products that share only the Postgres database, not code:
  1. **Credit Dashboard** — a stress-monitor product. Composed of: the refresh worker (src/ingestion/scheduler.py + the FRED-related ingestion modules: fred_ingest.py, fred_client.py, db.py, backup.py, jsonl.py), the indicator/compute layer (src/indicators/compute.py), the API service (src/api/main.py), and the static frontend (src/dashboard/index.html). The worker and the API are independent processes; they communicate only through Postgres (`series_observations`, `series_registry`, `staleness_state`).
  2. **Bank M&A Analysis** — a price-to-book regression product. Composed of: the FDIC and EDGAR ingestion modules (fdic_ingest.py, fdic_client.py, edgar_ingest.py, edgar_client.py), the analysis pipeline under src/analysis/ (build_dataset.py, regression.py, analysis.R), and the `acquisitions` Postgres table. Not driven by the scheduler — runs manually.
The shared `src/ingestion/db.py` connection helper and `backup.py` are shared infrastructure used by both products.
Source: diagrammer-run 2026-04-25 (human-confirmed during architecture review)
Affects: all of src/

### 2026-04-25 — TOTCI and NFCICREDIT have fake vintage_dates
Fact: src/ingestion/fred_client.py defines `SKIP_VINTAGE = {"TOTCI", "NFCICREDIT"}`. For these two series only, `get_observations()` does a non-vintage fetch (because FRED's vintage history for them exceeds the 100k-row API cap) and uses `observation_date` as the `vintage_date`. Therefore, in `series_observations`, every row for TOTCI (and NFCICREDIT, if present) has `vintage_date == observation_date`. Point-in-time queries (`WHERE vintage_date <= as_of`) on TOTCI return its **current** revised value, not the value FRED had published as of `as_of`. Any backtest or as-of dashboard query that uses TOTCI is silently using post-revision data — this is a known correctness gap for TOTCI specifically.
Source: diagrammer-run 2026-04-25
Affects: src/ingestion/fred_client.py, src/indicators/compute.py (TOTCI is in SECTOR_MAP["banks"] and is the bank slow signal), and any backtest using the dashboard's as-of API.

### 2026-04-25 — refresh() vintage_date is ingestion time, not publication time
Fact: The live refresh path (`fred_client.py::get_latest_observation`, called by `fred_ingest.py::refresh`) sets `vintage_date = date.today().isoformat()` rather than parsing FRED's `realtime_start`. So every row inserted via the scheduled refresh has `vintage_date` equal to the date the scheduler ran, not the date FRED actually published the value. Usually <24h off; worse if the scheduler is down for a stretch and catches up. The backfill path (`get_observations`) uses real `realtime_start` and is accurate. A bug report claiming "vintage_date for series X looks wrong by a day or two" is almost certainly this, not a deeper bug.
Source: diagrammer-run 2026-04-25
Affects: src/ingestion/fred_client.py (get_latest_observation), src/ingestion/fred_ingest.py (refresh)

### 2026-04-25 — Missing FRED values are dropped, not stored as NULL
Fact: When FRED returns `"value": "."` (FRED's missing-data sentinel), `fred_client.py:62-63` skips the row entirely instead of inserting a NULL-valued row. The schema allows NULL `value` but the code never produces one. So "no row in series_observations for (series, date)" could mean either FRED has no data for that date, or ingestion failed silently for that date — these are indistinguishable from the table alone. To distinguish, check FRED directly or the JSONL backfill output.
Source: diagrammer-run 2026-04-25
Affects: src/ingestion/fred_client.py (get_observations, get_latest_observation)

### 2026-04-25 — Scheduler only drives FRED, not FDIC/EDGAR
Fact: src/ingestion/scheduler.py registers cron jobs only for FRED series (daily/weekly/monthly/quarterly cadences pulled from `series_registry.update_frequency`). FDIC and EDGAR ingestion are not wired into the scheduler — they are run manually as part of the Bank M&A Analysis pipeline. A bug report mentioning "scheduled ingestion failed" is therefore always about FRED, never about M&A data.
Source: diagrammer-run 2026-04-25
Affects: src/ingestion/scheduler.py, src/ingestion/fdic_ingest.py, src/ingestion/edgar_ingest.py

