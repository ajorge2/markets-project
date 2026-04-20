# FIG Valuation Intelligence System

A two-layer empirical model that asks: *do credit conditions predict what buyers pay for financial institutions at exit?*

Built in two stages. Stage 1 — a credit stress dashboard that solves look-ahead bias in historical FRED data. Stage 2 — a regression model that uses those signals to predict price-to-book multiples at bank M&A close, then tests whether company-specific sector exposure (from FDIC Call Reports) adds incremental predictive power beyond the macro baseline.

---

## What's Built

### Layer 0 — Credit Stress Dashboard

Monitors eight credit stress signals across banks, consumers, CRE, and corporate credit. Normalizes each to a 0-100 percentile rank. Serves live state and point-in-time historical reconstructions via REST API.

**The core problem it solves:** FRED series are revised after initial publication. Every signal that gets revised (delinquency rates, loan volumes) is stored with two timestamps — `observation_date` (period the value covers) and `vintage_date` (when it was published). The `/dashboard/asof/{date}` endpoint reconstructs the information set that was *actually available* on that date by excluding vintages published after the query date. Non-revised series store `vintage_date = observation_date`.

**Signal design choices:**
- Credit card rate stored as a spread over fed funds — the raw rate is dominated by Fed policy, not borrower risk premium
- DFF-SOFR spread stored as absolute value — dislocation can occur in both directions
- TOTCI (C&I loan volume) transformed to YoY% to remove the inflation trend in the level series

**Backtest results:**

| Event | Bank Stress Score | Notes |
|---|---|---|
| SVB (Mar 9, 2023) | 28.8 / 100 | Correct — duration mismatch at one institution, not systemic |
| COVID (Mar 18, 2020) | 72.3 / 100 | |DFF-SOFR| at 98.6th percentile — fires on repo market dislocation |

### Layer 1 — Bank M&A Multiple Predictor (macro baseline)

Fits a regression: `price_to_book ~ f(macro signals)` using historical public bank acquisitions as observations.

**Data pipeline:**
- FDIC History API → acquisition events (CHANGECODE 223: merger without assistance), company financials at close date
- EDGAR API → 8-K filings for each acquired institution → deal price and consideration type
- FRED API → macro signals aligned to announcement date (not close date — price is set at announcement)

**Macro features:**

| Series | Transform | Rationale |
|---|---|---|
| T10Y2Y | Level | Yield curve shape — leading indicator for bank earnings and recession risk |
| UMCSENT | Level | Consumer sentiment — forward-looking demand signal |
| DSPI | YoY% | Disposable income growth — level has inflation trend |
| CPROFIT | YoY% | Corporate profit growth — same reason |
| COMPUTSA | YoY% | Computer equipment orders — same reason |

VIF analysis drops redundant variables iteratively before fitting. Train/test split at 2020-01-01 — model fit on pre-COVID regime, validated on COVID and post-COVID deals.

---

## What's Planned

### Layer 2 — Sector-specific trust signals

Test whether the credit stress signals from Layer 0 add predictive power *on top of* the macro baseline for banks with specific sector exposures.

Example: does CRE delinquency rate improve multiple prediction for banks with heavy CRE loan book concentration, beyond what the macro model already captures?

Steps:
1. Pull FDIC Call Report data for acquired institutions — quarterly loan book composition by category
2. Compute sector exposure weights (% CRE, % consumer, % C&I, % corporate)
3. Construct a company-specific stress score as a weighted average of the relevant sector signals
4. Test whether adding this score improves predictions beyond Layer 1

This directly addresses the equal-weighting limitation in Layer 0 — the weights will be empirically fitted, not assumed.

### Visualization layer

Three panels, all variables normalized to percentile rank for display:
- Historical bank acquisition multiples over time
- Macro signals aligned to deal dates
- Sector-specific stress scores for a given company's loan book composition

Normalization is for display only — regression uses raw values with fitted coefficients.

---

## Known Limitations

| Limitation | Impact |
|---|---|
| Equal weighting within sectors (Layer 0) | Indefensible under rigorous questioning — Layer 2 is the fix |
| Few labeled observations relative to candidate variables | Bank deals are not frequent; multicollinearity is a real constraint |
| Lag structure unknown | Credit signals lead multiples by an unknown amount — tested by varying signal date |
| Public deal proxy | Stone Point's portfolio is private; model is fit on public bank acquisitions |
| TOTCI revision tracking omitted | Look-ahead bias exists in the YoY denominator for historical periods |
| Percentile normalization uses full historical distribution | Historical scores shift retroactively as new data arrives |
| Scheduler has no persistent state | Process crash loses job history; no alerting on sustained FRED failures |

---

## Stack

| Component | Technology |
|---|---|
| Database | PostgreSQL (dual-timestamp schema for point-in-time queries) |
| Ingestion | Python — FRED API, FDIC BankFind API, EDGAR full-text search |
| Scheduler | APScheduler |
| API | FastAPI |
| Analysis | pandas, statsmodels (OLS + VIF) |

---

## Source Layout

```
src/
  ingestion/
    fred_ingest.py        # FRED series → series_observations
    fdic_ingest.py        # FDIC history → acquisitions table
    edgar_ingest.py       # EDGAR 8-Ks → deal prices
    scheduler.py          # per-source polling cadence
    db.py
  api/
    main.py               # /dashboard/current, /dashboard/asof/{date}
  indicators/
    compute.py            # percentile normalization, spread computation
  analysis/
    build_dataset.py      # joins acquisitions + macro signals, point-in-time
    regression.py         # VIF filtering, OLS, holdout validation
  dashboard/
    index.html
  schema.sql
```
