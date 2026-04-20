# SVB Backtest — March 9, 2023
# (Day before FDIC takeover of Silicon Valley Bank, March 10 2023)
# Run date: 2026-04-14

## Dashboard Output

| Sector       | Score  | Interpretation              |
|--------------|--------|-----------------------------|
| Banks        | 28.8   | Moderate — not elevated      |
| Consumer     | 42.3   | Moderate                    |
| CRE          |  3.9   | Very low                    |
| Corporate    | 43.9   | Moderate                    |

## Per-Signal Detail

| Signal                          | Value       | Stress %ile | Note                                  |
|---------------------------------|-------------|-------------|---------------------------------------|
| C&I Loan Volume (YoY)           | +10.73%     | 28.0        | Loan growth still strong              |
| Interbank Dislocation (|DFF−SOFR|) | 0.02 pct pt | 29.5     | Interbank system calm                 |
| Credit Card Rate Spread         | 15.29 pct pt| 99.1        | Record-high consumer risk premium     |
| Credit Card Delinquency         | 2.25%       | 14.1        | Delinquencies still low               |
| Consumer Loan Delinquency       | 2.08%       | 13.6        | Delinquencies still low               |
| CRE Delinquency                 | 0.68%       |  3.9        | CRE book still performing             |
| IG Corporate Spread             | 1.30%       | 47.7        | Moderate                              |
| HY Corporate Spread             | 4.27%       | 40.1        | Moderate                              |

## What the System Would Have Done

Bank Stress: **38.5/100 — no alarm raised**.

This is the expected and honest result. The system would not have flagged SVB.

## Why This Is Correct Behavior (Not a Bug)

SVB's failure was **idiosyncratic institution risk**, not broad credit cycle stress:

1. **Duration mismatch**: SVB held long-dated MBS funded by short-term deposits. When rates
   rose sharply in 2022-2023, its bond portfolio suffered mark-to-market losses. This is an
   interest rate risk problem, not a credit cycle problem.

2. **Deposit concentration**: SVB's depositor base was unusually concentrated in venture-backed
   tech startups. When VC funding dried up, those firms drew down deposits simultaneously. This
   is a business model / concentration risk — not captured by aggregate credit indicators.

3. **Interbank system was fine**: DFF−SOFR spread = 0.02 pct pts. Most banks were healthy.
   SOFR was not dislocated. The failure was specific to one institution.

## What the System DID Correctly Show

The **CC_SPREAD at 99.1th percentile** was legitimate and significant: the Fed's aggressive
2022-2023 rate hike cycle was being fully passed through to credit card borrowers while
deposit rates lagged. This correctly captured the tightening of consumer credit conditions
that would go on to elevate delinquencies in late 2023 and 2024.

## Documented Limitation

**This system monitors the credit cycle — the aggregate expansion and contraction of credit
across the economy. It is not designed to detect:**
- Individual institution failures from idiosyncratic risk
- Interest rate duration mismatches at specific banks
- Concentration risk in deposit bases
- Unrealized bond portfolio losses

For those signals you would need:
- Bank-level regulatory filings (Call Reports)
- Duration gap / NIIR analysis per institution
- Deposit concentration metrics
- Mark-to-market / AOCI tracking for held-to-maturity portfolios

## Calibration Note on DFF−SOFR Spread

SOFR data begins April 3, 2018. The bank fast signal therefore has only ~5 years of history
for percentile calibration. During genuine interbank stress (e.g., March 2020 COVID dislocation),
the spread did widen measurably, so the signal direction is correct. But the calibration
distribution is thin. Pre-2018 analog: LIBOR−OIS spread (not included in this system).
