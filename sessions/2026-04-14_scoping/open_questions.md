# Open Questions — 2026-04-14 Scoping Session

These must be resolved before architecture begins. Owner = agent responsible for driving resolution.

## Q1: Data Source
**Owner:** Data Infrastructure Engineer
**Question:** What tick data provider is available — Polygon.io, Databento, IEX Cloud, or other?
**Why it blocks:** Provider determines feed protocol, schema, timestamp semantics, and whether a real-time WebSocket stream or historical replay is the primary access pattern. The ingestion architecture diverges significantly between options.
**Resolution criteria:** Confirmed provider with API access, latency characteristics, and historical data depth documented.

## Q2: Estimation Algorithm
**Owner:** Quant Strategist
**Question:** TSRV (Two-Scale Realized Variance) or Realized Kernels first?
**Why it blocks:** TSRV requires maintaining two sampling frequencies and a bias correction term. Realized Kernels require bandwidth selection (a separate estimation problem). These have different implementation complexity, different state shapes, and different theoretical properties. Picking one drives the streaming state design.
**Resolution criteria:** Position paper from Quant Strategist with explicit tradeoff documentation. Adversarial Critic to review.

## Q3: Downstream Consumer
**Owner:** Orchestrator (requires team input)
**Question:** What does the RV estimate feed downstream? Candidate consumers: (a) intraday volatility forecast for options pricing, (b) risk limit computation for a portfolio, (c) standalone signal for short-term vol forecasting.
**Why it blocks:** The output latency budget changes by 2-3 orders of magnitude depending on the answer. Also determines whether the output is a scalar (current RV estimate) or a time series (rolling estimates).
**Resolution criteria:** Downstream use case selected and latency budget documented.

## Q4: Real-Time Definition
**Owner:** Systems Architect
**Question:** Second-bar tumbling window (re-compute estimate every second over a rolling window) vs. continuous tick-level incremental update (update the estimate with every new tick)?
**Why it blocks:** These are different streaming topologies. Second-bar is a windowed aggregation — simpler, bounded state. Continuous tick-level is a stateful incremental computation — harder, but more useful for sub-second consumers.
**Resolution criteria:** Decision with explicit latency budget implications documented by Systems Architect.

## Q5: Market Open Adversarial Case
**Owner:** Adversarial Critic
**Question:** During the market open (9:30–9:45 ET), spreads are typically 2-5x wider than mid-day, and tick rates are high. The noise-to-signal ratio is at its daily maximum. What does the noise estimator do during these 15 minutes? Does pathological behavior at open propagate into the day's estimates via the rolling window? Is there a warm-up period design?
**Why it blocks:** If the estimator produces garbage at open and that garbage contaminates the warm-up state, the first hour of each day's output is unreliable. This is a correctness question, not a performance question.
**Resolution criteria:** Adversarial Critic to formally attack this case. Quant Strategist and Systems Architect to provide mitigation design.
