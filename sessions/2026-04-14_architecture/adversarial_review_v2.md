# Adversarial Review: Built System — Credit Stress Dashboard
# Date: 2026-04-14
# Status: CONDITIONAL VETO — three critical failures in signal design

## Critical Failures (veto-level)

### 1. Residential vacancy (RRVRUSQ156N) measures apartments, not commercial real estate
CRE portfolio = office, industrial, retail. Residential vacancy is anticorrelated with
commercial office vacancy during the 2022-2024 office crisis. Dashboard shows improving
CRE conditions when commercial vacancy was at post-S&L-crisis highs. False negative on
the most important CRE stress episode in 30 years.
FIX: Remove. Use DRCRELEXFACBS as sole CRE slow signal. Document gap.

### 2. NFCICREDIT is a broad economy-wide credit signal, not a CRE fast signal
During 2023-2024: broad credit calm, CRE acutely stressed. NFCICREDIT near-neutral.
Dashboard CRE fast signal: moderate. Reality: office CRE in crisis.
FIX: Move to "broad conditions" context row. CRE sector honest = one signal (delinquency).

### 3. Bank sector has no fast signal — will miss a banking crisis in progress
TOTCI YoY is a lagging behavioral indicator. C&I loans were still growing in March 2023
when SVB failed. Bank stress would have read ~45-50/100 during active regional bank crisis.
FIX: Add SOFR-based interbank spread as bank fast signal.

## Significant Risks

### 4. Credit card rate measures Fed policy, not consumer credit distrust
Rate = Fed funds + spread. Sep 2008 (financial crisis): rate 11.94%, score 1.8th percentile
(Fed had cut). Today (calm): 21%, score 92.9th percentile. Signal is correlated with
monetary policy stance. Consumer stress score is inflated in tightening cycles.
FIX: Use (credit card rate - Fed funds rate) as the signal to isolate the risk premium.

### 5. Dual-timestamp guarantee is partial
4 of 9 series stored with today's vintage → fall back to observation_date.
Genuine vintage-based point-in-time: 5 series, from 2011 onwards only.
TOTCI YoY in historical backtest uses revised Fed data as denominator → look-ahead bias.

### 6. Equal weighting is indefensible under questioning
Arithmetic mean of signals with different units, lead/lag, and economic mechanisms.
Must either justify or explicitly disclaim.

### 7. Stale inputs contribute to sector score at full weight
When quarterly series is overdue, sector score uses 90-day-old data silently.

### 8. Scheduler has no persistent state or alerting
In-memory job store. Process crash = no record of last successful run.
No alerting on sustained FRED failures.

## What Lifts the Veto
1. Remove RRVRUSQ156N, document CRE vacancy gap
2. Remove NFCICREDIT from CRE sector
3. Add SOFR spread to banks
4. Replace TERMCBCCALLNS with (TERMCBCCALLNS - FEDFUNDS) spread
5. Run and save March 2023 SVB backtest — know what the system shows before a reviewer finds it
