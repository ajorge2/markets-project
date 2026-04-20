# Decision Log — Credit Stress Dashboard
# Date: 2026-04-14

---

## Decision 1: Dual-timestamp schema vs. snapshot storage

**Options considered**
- A: Store only the current vintage of each series (one row per observation date)
- B: Store both observation_date and vintage_date, keeping full revision history

**Criteria**
- Point-in-time accuracy: can a backtest as of date D use only data available on D?
- Query complexity: how hard is it to reconstruct historical state?
- Storage cost: how many rows does each approach require?

**Choice: B**

**Reasoning**
FRED revised series (delinquency rates, loan volumes) are materially different across vintages. A delinquency rate for Q1 2021 published in Q3 2021 is not the number available in Q1 2021. Storing only current vintages makes it impossible to reconstruct what was knowable at any historical date — backtests become contaminated with future information (look-ahead bias). The dual-timestamp schema enables a single query pattern: `WHERE vintage_date <= as_of_date`, which correctly excludes any data not yet published at that point in time.

**Downside accepted**
Storage is larger. FRED vintage history for revised series can run to thousands of rows per series. Some series (TOTCI, NFCICREDIT) have revision histories so dense that fetching them via the FRED realtime API hits the 100k row limit — vintage tracking was omitted for those series, and the resulting look-ahead bias in their historical scores is documented.

---

## Decision 2: Credit card rate spread vs. raw rate

**Options considered**
- A: Use TERMCBCCALLNS (average credit card interest rate) directly
- B: Use TERMCBCCALLNS minus FEDFUNDS (spread over the federal funds rate)

**Criteria**
- Does the signal isolate consumer credit stress, or does it conflate consumer risk with Fed policy stance?
- Is the signal comparable across different rate environments?

**Choice: B**

**Reasoning**
The raw credit card rate moves with Fed policy. In September 2008 (financial crisis), the rate was ~12% — the Fed had cut aggressively. In 2024 (calm conditions), the rate was ~21% — the Fed had hiked to fight inflation. A naive percentile rank of the raw rate would show 2024 as far more stressed than 2008, which is wrong. The spread over fed funds isolates the risk premium that lenders charge on top of the policy rate floor. This premium reflects actual lender distrust of consumer borrowers. In 2008 the spread was ~12 percentage points; in 2024 it is ~17 percentage points — a genuine and meaningful signal that the premium has never been wider.

**Downside accepted**
The spread requires storing and aligning two series (TERMCBCCALLNS and FEDFUNDS) at the same frequency. Monthly alignment is straightforward but adds a dependency.

---

## Decision 3: Absolute value vs. signed DFF-SOFR spread

**Options considered**
- A: Use DFF minus SOFR (signed spread)
- B: Use |DFF minus SOFR| (absolute dislocation)

**Criteria**
- Does the signal fire on all forms of interbank stress, or only one direction?
- Is the signal direction consistent across different stress episodes?

**Choice: B**

**Reasoning**
DFF (federal funds rate) is unsecured overnight interbank lending. SOFR (Secured Overnight Financing Rate) is collateralized overnight lending against Treasuries. In normal conditions SOFR is slightly below DFF — collateral reduces risk, so lenders accept a lower rate.

Under stress, the spread can widen in either direction:
- Unsecured stress (bank counterparty risk): DFF rises relative to SOFR — signed spread goes positive
- Repo/collateral stress (March 2020): SOFR spiked as Treasuries were hoarded — signed spread went negative to -0.29 pct pts

Using the signed spread, repo stress reads as "low stress" (very negative value, low percentile rank). The absolute value captures the magnitude of dislocation regardless of direction. Verified against March 2020 COVID data: |DFF-SOFR| = 0.29, 98.6th percentile — correctly fires.

**Downside accepted**
Absolute value conflates two mechanistically different stress types. A more sophisticated implementation would track both components separately and interpret each in context. For a first-order stress score, magnitude of dislocation is the right summary statistic.

---

## Decision 4: Remove RRVRUSQ156N (residential vacancy) from CRE sector

**Options considered**
- A: Keep RRVRUSQ156N as a CRE proxy signal
- B: Remove it, document the gap, use DRCRELEXFACBS as sole CRE signal

**Choice: B**

**Reasoning**
RRVRUSQ156N measures apartment vacancy, not commercial real estate vacancy. During the 2022-2024 office crisis — the most significant CRE stress episode in 30 years — residential vacancy was declining (remote work increased housing demand). The two series are anticorrelated during the exact stress episodes this system is meant to detect. Keeping RRVRUSQ156N would have produced false negatives on commercial real estate stress. No free substitute for commercial vacancy exists on FRED. The gap is documented.

**Downside accepted**
CRE sector has no fast signal. DRCRELEXFACBS is quarterly and lags reality by months. A production system would require a non-FRED commercial vacancy data source.

---

## Decision 5: Remove NFCICREDIT from CRE sector

**Options considered**
- A: Keep NFCICREDIT as CRE fast signal
- B: Remove it entirely
- C: Move it to a separate "broad conditions" context row

**Choice: B**

**Reasoning**
NFCICREDIT is the Chicago Fed National Financial Conditions Credit Index — a broad economy-wide credit index, not a CRE-specific signal. During 2023-2024, broad credit conditions were near-neutral while commercial real estate was acutely stressed. Including it in the CRE sector score was actively misleading — it would have diluted the delinquency signal and shown CRE as "moderate" when office vacancy was at post-S&L-crisis highs. Moved to "remove" rather than "context row" because displaying it without clear labeling of its scope would create confusion.

**Downside accepted**
The CRE sector loses its only fast-moving signal. The sector now reflects only what has already happened (delinquencies), not what is developing. Accepted as the honest position given available data.

---

## Decision 6: Equal weighting within sectors

**Options considered**
- A: Equal weights — sector score = arithmetic mean of component percentiles
- B: Fitted weights — regress sector score against a labeled dataset of credit events
- C: Expert-assigned weights — assign weights based on domain judgment about signal importance

**Choice: A**

**Reasoning**
Option B requires a labeled dataset of historical credit stress episodes and sufficient history to fit stable weights — neither was available in scope. Option C produces weights that are defensible in narrative but not empirically grounded, which is a different kind of problem. Equal weights is the honest baseline: it makes no claim about relative signal importance that isn't supported by evidence. The limitation is documented explicitly.

**Downside accepted**
Equal weighting is indefensible under rigorous quantitative questioning. Signals with different lead/lag structures, frequencies, and economic mechanisms are treated as equivalent. A delinquency rate published quarterly contributes equally to the sector score as a daily spread. This is a known and acknowledged weakness, not an oversight.
