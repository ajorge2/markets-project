# Open Questions — 2026-04-14 FIG Scoping Session

## Q1: Credit Signal Data Sources
**Owner:** Data Infrastructure Engineer
**Question:** Are free/low-cost sources sufficient — FRED for delinquency and bank data, ICE BofA indices for credit spreads, Fed H.8 for loan growth — or do we need commercial subscriptions (Bloomberg, Refinitiv)?
**Why it blocks:** Data source determines ingestion architecture, update frequency, and whether real-time spread updates are possible or only end-of-day.
**Resolution criteria:** Confirmed data sources with update frequency, access method (API/download/WebSocket), and latency characteristics documented.

## Q2: Latent Variable Model Selection
**Owner:** Quant Strategist + Systems Architect
**Question:** Kalman filter (assumes linear dynamics, Gaussian noise) vs. particle filter (handles non-Gaussian, heavier compute) vs. regime-switching HMM (discrete states, interpretable)?
**Why it blocks:** Model choice determines state representation, computational requirements, and update mechanism. Wrong model produces incorrect cycle estimates that look plausible.
**Resolution criteria:** Model selected with explicit justification for why the signal characteristics justify the choice. Adversarial Critic to review.

## Q3: Output Representation
**Owner:** Orchestrator (requires input from all agents)
**Question:** What does the system actually output? Options: (a) scalar 1-10 cycle score, (b) discrete state label (expansion/peak/contraction/trough), (c) probability distribution over discrete states, (d) vector of sub-indicators.
**Why it blocks:** Output format determines how Stone Point uses this in practice. A probability distribution is more honest but harder to act on. A scalar is easy to act on but hides uncertainty.
**Resolution criteria:** Output format selected with explicit discussion of how a PE MD would use it in an investment committee context.

## Q4: Validation Methodology
**Owner:** Quant Strategist
**Question:** How do we know the cycle position estimate is correct? Proposal: backtest against known turning points (Q3 2007 cycle peak, March 2020 crisis onset, Q4 2015 oil/energy stress). What is the evaluation metric — lead time on turns, false positive rate, something else?
**Why it blocks:** Without a validation methodology, the system is unfalsifiable. An unfalsifiable system is not a credible portfolio piece.
**Resolution criteria:** Evaluation framework with specific metrics and historical test periods documented.

## Q5: FIG-Specific Signal Weighting
**Owner:** Quant Strategist
**Question:** Which signals are most predictive for FIG company valuations specifically? Banks are most sensitive to credit spreads and net interest margins. Insurance companies are more sensitive to catastrophe loss trends and equity market levels. Specialty lenders are sensitive to consumer credit delinquencies. Should the model have sector-specific variants?
**Why it blocks:** A generic credit cycle model may miss the signals most relevant to Stone Point's specific portfolio mix. Getting this wrong reduces the practical value to the target audience.
**Resolution criteria:** Signal relevance ranking by FIG subsector, with rationale grounded in how each subsector's business model connects to credit cycle dynamics.
