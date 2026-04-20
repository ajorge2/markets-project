# Scoping Session Decisions (FIG/PE Target) — 2026-04-14

## Context
Re-run of opening protocol after target audience was re-specified to:
- Primary: Portfolio Technology & Data MD, Stone Point Capital (FIG-focused PE)
- Secondary: Quant dev and SWE hiring at non-PE firms

## Decision: Project Concept Selection

**Selected:** Concept C — Credit Cycle Position Monitor for FIG Exit Timing

**What it is:**
A system that synthesizes real-time credit spread data, loan growth signals, delinquency trends, and bank funding costs into a continuously updated estimate of credit cycle position — directly informing PE exit timing for financial institution portfolio companies.

**Core technical problem:**
Credit cycle position is a latent variable (unobservable directly). It must be inferred from multiple heterogeneous signals with different update frequencies (milliseconds to quarters) and different lead/lag characteristics. The systems challenge is multi-timescale state fusion with online latent variable inference — maintaining a coherent current-state estimate that updates from fast noisy signals and integrates slow reliable signals correctly when they arrive.

**Why selected:**
1. Addresses Stone Point's highest-value decision (exit timing) with a hard technical problem
2. Financial insight (why different signals lead/lag the cycle) requires genuine domain knowledge
3. Systems challenge (multi-timescale streaming, latent variable inference, graceful degradation under missing data) is architecturally interesting to quant/SWE hiring
4. Strong secondary signal to non-PE technical hiring

**Concepts rejected:**

| Concept | Rejection Reason |
|---|---|
| D — Regulatory Filing Detector | Strong PE signal, weaker systems depth. Mostly ETL + anomaly detection. Lower secondary signal to quant/SWE hiring. Best backup if Stone Point context changes. |
| A — Sector Stress Aggregator | Less novel — "aggregate market stress signals" is a known product category. Lower differentiation ceiling. |
| B — Insurance Underwriting Monitor | High domain knowledge requirement for a subsector the user hasn't studied. OTC data access for cat bonds is an infrastructure blocker. |
| E — Public Comp Valuation Surface | Lowest differentiation. Reads as "I built a Bloomberg feature," not "I solved a hard problem." |

## Strategic Note: Two-Project Plan

The original quant/HFT concept (noise-corrected realized variance) remains the stronger portfolio piece for quant firms. Recommendation: build the credit cycle monitor first (targets Stone Point), then build the realized variance system afterward (targets quant/HFT). The infrastructure patterns from project 1 accelerate project 2.

---

## Open Questions (blocking architecture start)

1. **Credit signal data sources:** Are FRED, ICE BofA indices, and Fed H.8 releases sufficient, or are commercial subscriptions needed?
2. **Latent variable model:** Kalman filter (linear, Gaussian) vs. particle filter (non-Gaussian, heavier compute). Which fits the signal characteristics?
3. **Output representation:** Scalar (1-10), discrete states (expansion/peak/contraction/trough), or probability distribution over states?
4. **Validation approach:** Backtest against 2007, 2020, 2015 cycle turns. What is the evaluation metric?
5. **FIG-specific signal weighting:** Which signals matter most for bank vs. insurance vs. specialty finance valuations? Needs Quant Strategist input.

---

## What This Session Revealed

The Stone Point context unlocks a class of problems that are genuinely hard but invisible to people who think "quant finance" only means trading. Credit cycle inference is a latent variable problem with heterogeneous, irregularly-timed observations — a more interesting and less crowded problem space than order book reconstruction or vol surface fitting. The portfolio signal to PE is higher than any of the original five concepts. The secondary signal to quant/SWE hiring is preserved through the systems architecture.
