# Next Project Direction: FIG Valuation Multiple Predictor
# Date: 2026-04-15
# Status: Planning

## Core Thesis

Credit conditions predict what buyers will pay for financial institutions at exit.
When credit is stressed, valuation multiples compress. When credit is calm, multiples expand.
Stone Point needs to know where multiples are heading to time exits correctly.

This project builds that model empirically.

## The Output Variable

Price-to-book multiple at acquisition close for bank M&A deals.
Source: public bank M&A data (FDIC, S&P Global Market Intelligence, SNL Financial).
Private deal data not required — public bank acquisitions number in the thousands historically
and the macro relationship generalizes across exit types (M&A, IPO, secondary).

## Architecture: Two Layers

### Layer 1 — Macro baseline
Fit a regression: price-to-book multiple ~ f(macro signals).
Use historical bank M&A deals as observations.
Use FRED macro series as inputs — GDP growth, unemployment, yield curve, credit conditions, etc.

Steps:
1. Pull a broad set of FRED macro series (the existing ingestion layer handles this)
2. Align each series to deal close dates
3. Use VIF to identify and drop redundant variables (most macro series are correlated)
4. Fit regression on surviving variables
5. Validate: does the model predict held-out deal multiples reasonably?

### Layer 2 — Sector-specific trust signals
Test whether the signals from the Credit Stress Dashboard add predictive power
on top of the macro baseline for banks with specific sector exposures.

Example: does CRE delinquency rate improve multiple prediction for banks with
heavy CRE loan book concentration, beyond what the macro model already captures?

Data needed: FDIC Call Reports — quarterly loan book composition by category for each bank.
This gives the exposure weights to apply the right sector signals to each company.

Steps:
1. Pull Call Report data for target banks
2. Compute sector exposure weights (% CRE, % consumer, % C&I, etc.)
3. Construct a company-specific stress score as weighted average of sector signals
4. Test whether adding this score improves predictions beyond Layer 1

## Visualization Plan

All variables normalized to percentile rank for display (units incompatible otherwise).
Three panels:
- Historical valuation multiples for past bank deals over time
- Macro signals aligned to deal dates
- Sector-specific trust signals for current portfolio company exposures

Normalization is for visualization only — regression uses raw values with fitted weights.
The weights are the point. Equal weighting (as in the current dashboard) is explicitly
the naive baseline that this model improves on.

## Why This Is Hard

- Few observations relative to candidate variables (bank deals are not frequent)
- Lag structure: credit signals lead valuation multiples by unknown amounts — need to test
- Nonlinearity: the relationship between credit stress and multiples may not be linear
- Private vs. public: Stone Point's actual portfolio is private; model is fit on public deals
- Multiple exit routes: M&A, IPO, secondary — all anchor to the same multiple concept
  but with different market dynamics

## Interview Story

"I started with a macro credit stress dashboard to establish the signal layer.
Then I asked: do these signals actually predict what a buyer will pay for a bank at exit?
I fit a regression using historical public bank M&A data, used VIF to drop redundant
macro variables, validated the baseline model, then tested whether company-specific
sector exposure (from FDIC Call Reports) added incremental predictive power beyond macro.
The result is a model that tells you, given today's credit environment and a specific
bank's loan book composition, where valuation multiples are likely to be when you exit."

## Data Sources

| Data | Source | Notes |
|---|---|---|
| Macro signals | FRED (existing ingestion layer) | Thousands of series available |
| Bank M&A deal multiples | FDIC, S&P Global Market Intelligence | Public deals only |
| Bank loan book composition | FDIC Call Reports | Quarterly, public |
| Credit stress signals | This dashboard | Already built |

## Sequencing

1. Build the macro baseline first — validate that credit conditions predict multiples at all
2. Add sector-specific signals as a second layer — test incremental predictive power
3. Add Call Report exposure weights as a third layer — personalize to specific companies
4. Visualization layer throughout — normalized time series, correlation screening

Do not try to build all three layers simultaneously.
