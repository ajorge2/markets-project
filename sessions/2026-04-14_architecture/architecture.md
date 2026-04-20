# Architecture: Credit Stress Dashboard
# Date: 2026-04-14
# Status: Draft — pending Adversarial Critic review of CRE data gap

## System Overview

A multi-timescale data fusion system that maintains a continuously updated early warning dashboard for credit stress conditions across FIG subsectors. Ingests daily credit spread data, weekly Fed releases, and monthly delinquency filings. Outputs a vector of 8 observable sub-indicators with explicit staleness tracking.

## Dashboard Indicators

| Sector | Fast Signal | Slow Signal |
|---|---|---|
| Banks | Interbank spread (daily) | Loan growth (weekly) |
| Consumer | Credit card rates (monthly) | Delinquency rates (monthly) |
| CRE | CMBS spreads (daily) | Vacancy rates (quarterly — data gap, see below) |
| Corporate | IG/HY credit spreads (daily) | — |

## Core Schema

```sql
-- Every observation stored with dual timestamps
CREATE TABLE series_observations (
    series_id        TEXT,
    observation_date DATE,    -- period the value covers
    vintage_date     DATE,    -- when it was published
    value            NUMERIC,
    source           TEXT,
    PRIMARY KEY (series_id, observation_date, vintage_date)
);

-- Series metadata and expected update cadence
CREATE TABLE series_registry (
    series_id           TEXT PRIMARY KEY,
    description         TEXT,
    sector              TEXT,
    signal_speed        TEXT,
    update_frequency    TEXT,
    source              TEXT,
    fred_series_id      TEXT
);

-- Current staleness state per series
CREATE TABLE staleness_state (
    series_id           TEXT PRIMARY KEY,
    last_vintage_date   DATE,
    expected_next_date  DATE,
    status              TEXT  -- 'fresh', 'pending', 'overdue'
);
```

## Point-in-Time Query (Backtest Engine)

```sql
-- "What would the dashboard have shown on [date]?"
SELECT DISTINCT ON (series_id, observation_date)
    series_id, observation_date, value
FROM series_observations
WHERE vintage_date <= '[backtest_date]'
ORDER BY series_id, observation_date, vintage_date DESC;
```

## Component Architecture

```
External Sources (FRED API, ICE BofA via FRED)
        ↓  scheduled polling, per-source cadence
Ingestion Scheduler (Python + APScheduler)
        ↓  stores raw observations with vintage timestamp
TimescaleDB
        ↓                    ↓
Staleness Tracker      Indicator Computer
        ↓                    ↓
        └──────────┬──────────┘
                   ↓
              REST API (FastAPI)
              /dashboard/current
              /dashboard/asof?date=YYYY-MM-DD
                   ↓
              Dashboard UI
```

## Technology Choices

| Component | Technology | Justification |
|---|---|---|
| Database | TimescaleDB | Standard SQL, time-series optimized, dual-timestamp schema, compression for historical data |
| Ingestion | Python + fredapi | FRED has a maintained Python client. No JVM overhead justified. |
| Scheduler | APScheduler | Simple, per-job cadence configuration, no message queue needed |
| API | FastAPI | Typed, fast, simple. One user (dashboard). |
| No message queue | — | Update frequency is daily. Kafka/Redpanda adds operational complexity with zero latency benefit. |
| No ML layer | — | Adversarial Critic veto. Observable indicators only. |

## FRED Series IDs

| Indicator | FRED Series ID | Frequency |
|---|---|---|
| Credit card delinquency | DRCCLACBS | Quarterly |
| Auto loan delinquency | DRAUTOACBS | Quarterly |
| C&I loan growth | TOTCI | Weekly |
| IG credit spread | BAMLC0A0CM | Daily |
| HY credit spread | BAMLH0A0HYM2 | Daily |
| CMBS spread | BAMLC0A0CMBS | Daily |
| Credit card interest rate | TERMCBCCALLNS | Monthly |

## Known Data Gap

CRE vacancy rates are not freely available on FRED with sufficient granularity. Options:
1. Use FRED residential vacancy (RRVRUSQ156N) as partial proxy
2. Use CMBS delinquency rate as sole CRE slow signal
3. Document as explicit scope gap

**Pending:** Adversarial Critic review of whether this gap materially weakens the CRE sector gauge.

## Backtest Validation Dates
- 2007-09-01 (pre-GFC stress onset)
- 2020-03-01 (COVID crisis onset)
- 2022-10-01 (rate hike / CRE stress onset)
