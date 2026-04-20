# Candidate Concepts — 2026-04-14 Scoping Session

Saved for future reference. These were the original 5 concepts generated for a general quant/HFT audience before the target was re-specified to Stone Point Capital (FIG-focused PE).

---

## Concept 1 — Multi-Venue Order Flow Imbalance Signal Engine

**One sentence:** A system that reconstructs limit order book state from raw direct feeds across 10+ equity venues simultaneously and computes a cross-venue order flow imbalance signal with proper clock-discipline — not using the SIP.

**Financial insight:** Order Flow Imbalance (OFI) — the difference between buyer-initiated and seller-initiated volume at the top of book — is empirically predictive of short-term price direction (Cont, Kukanov, Stoikov 2014). The naive version uses the SIP consolidated tape which lags direct feeds by 300–500µs during volatility. Cross-venue OFI weighted by venue market share and corrected for feed latency asymmetry is a meaningfully harder and more accurate signal.

**Systems challenge:** Perfect order book reconstruction from raw add/modify/cancel/trade messages with strict sequence number integrity. A single dropped message corrupts the book permanently. Gap detection, retransmission request, and snapshot recovery must all be designed.

**Real-time constraint:** Sub-millisecond end-to-end (feed receipt → book update → OFI computation → signal emission). Multi-venue clock synchronization requires hardware timestamping or PTP-disciplined NTP.

**Differentiation:** 9/10
**Technical risk:** High (requires direct exchange feed access)
**Portfolio signal:** 9/10

---

## Concept 2 — Real-Time Microstructure-Noise-Corrected Realized Variance Estimator

**One sentence:** A streaming system that computes realized variance from tick data using a noise-corrected estimator (TSRV or Realized Kernels) with an adaptive sampling frequency estimated online from the intraday noise-to-signal ratio.

**Financial insight:** Naive realized variance is biased upward by microstructure noise — bid-ask bounce, tick rounding, asynchronous trading. Two-Scale Realized Variance (Aït-Sahalia, Mykland, Zhang 2005) and Realized Kernels (Barndorff-Nielsen et al. 2008) correct for this. The optimal correction parameter is time-varying (intraday-seasonal) and must be estimated online.

**Systems challenge:** Nested stateful streaming computation: an inner estimator (noise level) governs the outer estimator (corrected variance), both updating tick by tick. State is non-trivial to manage under failure and recovery.

**Real-time constraint:** The noise parameter changes throughout the day. A static parameter baked in at startup produces incorrect estimates for most of the trading session.

**Differentiation:** 10/10
**Technical risk:** Medium
**Portfolio signal:** 10/10 (for quant/HFT audience)

**Status:** Selected as primary concept for quant/HFT audience. Deprioritized when target re-specified to Stone Point Capital.

---

## Concept 3 — Adaptive Optimal Execution Engine with Real-Time Impact Model Calibration

**One sentence:** An execution engine that continuously re-estimates its own market impact model from live fill data and adapts the Almgren-Chriss optimal liquidation schedule in real time as the impact parameters evolve.

**Financial insight:** The Almgren-Chriss model gives a closed-form optimal execution schedule under a linear market impact model. In production, impact parameters are time-varying (higher during volatile periods). A system that re-estimates parameters from recent fills and adjusts the schedule mid-order is a real improvement over static models.

**Systems challenge:** Real-time feedback loop from fill data → impact parameter estimation → updated schedule → order modification. Recursive least squares or streaming Bayesian inference feeding a real-time control system.

**Real-time constraint:** Cancel-replace windows at exchanges operate at milliseconds. Adaptation must happen within the window between order submissions.

**Differentiation:** 8/10
**Technical risk:** Medium
**Portfolio signal:** 8/10

---

## Concept 4 — Real-Time Implied Volatility Surface Arbitrage Scanner

**One sentence:** A system that continuously fits a no-arbitrage parametric vol surface (SVI) to live option quote streams and detects violations of static arbitrage conditions within milliseconds of quote updates.

**Financial insight:** The implied vol surface across strikes and expiries must satisfy no-arbitrage constraints (calendar spread positivity, butterfly positivity). These are momentarily violated in live markets due to quote staleness or genuine dislocations. The challenge is distinguishing noise from signal.

**Systems challenge:** SVI parametrization fitting is a non-convex optimization. Re-fitting on every quote update is expensive. Requires incremental warm-start strategy or intelligent re-fit triggering. Under vol spikes, quote updates arrive in bursts.

**Real-time constraint:** Arbitrage violations close within seconds in liquid markets. Full surface re-fitting in >500ms is too slow.

**Differentiation:** 7/10
**Technical risk:** High (calibration convergence failures)
**Portfolio signal:** 7/10

---

## Concept 5 — Streaming Cross-Asset Regime Detector with Online Covariance Estimation

**One sentence:** A system that infers the current market regime from the joint behavior of equities, credit, rates, and vol in real time using online covariance estimation with Random Matrix Theory noise cleaning.

**Financial insight:** Regimes are inferred from changes in the dominant eigenvectors of the clean cross-asset covariance matrix. Ledoit-Wolf shrinkage or RMT-based noise cleaning separates signal from noise eigenvalues in high-dimensional covariance matrices.

**Systems challenge:** Maintaining an online Ledoit-Wolf estimator requires incremental covariance updates without full recomputation. Output is a d×d matrix requiring near-real-time eigendecomposition.

**Real-time constraint:** Operates on second or minute bars, not tick data. Regime transitions happen over hours to days — the real-time constraint is detecting them faster than a daily batch update.

**Differentiation:** 8/10
**Technical risk:** Medium
**Portfolio signal:** 7/10 (broader audience, weaker signal to HFT-focused firms)

**Note:** Most directly applicable to Stone Point Capital context — regime detection has relevance to PE exit timing and macro positioning for FIG portfolio companies.
