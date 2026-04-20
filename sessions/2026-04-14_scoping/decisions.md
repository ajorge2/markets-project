# Scoping Session Decisions — 2026-04-14

## Decision: Project Concept Selection

**Selected:** Concept 2 — Real-Time Microstructure-Noise-Corrected Realized Variance Estimator

**What it is:**
A streaming system that computes realized variance from tick data using a noise-corrected estimator (TSRV or Realized Kernels) with an adaptive sampling frequency estimated online from the intraday noise-to-signal ratio.

**Why selected:**
1. The financial problem is grounded in Nobel-adjacent literature (Aït-Sahalia, Barndorff-Nielsen) and is unknown enough that correctly formulating it already proves expertise
2. The systems challenge — nested stateful streaming where the inner estimator governs the outer — is architecturally interesting independent of finance
3. Requires genuine simultaneous depth in financial econometrics and systems engineering; cannot be surface-faked
4. Lower infra dependency risk than direct-feed-based concepts; historical tick data is accessible

**Concepts rejected:**

| Concept | Rejection Reason |
|---|---|
| Multi-Venue OFI Engine | Requires direct exchange feed access to build honestly. Simulation with delayed data significantly weakens the signal. Higher infra dependency risk. Strong second choice if direct feeds are available. |
| Adaptive Execution Engine | Static Almgren-Chriss is widely taught. Adaptive version has lower novelty ceiling — risks reading as "I know execution models" rather than "I built something novel." |
| Vol Surface Arbitrage Scanner | Well-known industry problem. Financial insight ceiling is lower — primarily a calibration speed problem, not a financial insight problem. |
| Cross-Asset Regime Detector | Broader audience, weaker portfolio signal to HFT/microstructure-focused firms. "Regime detection" phrase triggers skepticism in quant interviews. |

---

## Open Questions (blocking architecture start)

1. **Data source:** What tick data provider is available? (Polygon.io, Databento, IEX Cloud). Determines ingestion architecture.
2. **Algorithm selection:** TSRV vs. Realized Kernels — tractability vs. asymptotic efficiency. Need position from Quant Strategist.
3. **Downstream consumer:** What does the RV estimate feed? Determines output latency budget and state retention requirements.
4. **Real-time definition:** Second-bar updates vs. continuous tick-level incremental computation. Changes streaming topology fundamentally.
5. **Market open adversarial case:** Noise estimator behavior during open (wide spreads + high tick rates simultaneously). Needs Adversarial Critic attack before architecture is committed.

---

## What This Session Revealed

Concept selection revealed that the most intellectually differentiated projects are often the least known — not because they are impractical, but because they sit at intersections that require two separate deep knowledge domains to even formulate. The noise-corrected realized variance problem is invisible to someone who knows only systems engineering, invisible to someone who knows only financial theory, and immediately recognizable to someone who knows both. That asymmetry is the portfolio signal.
