# Andrew's Inbox

A scratchpad for copy-pasting drafts.

---

## Resume bullet — FIG Stress Intelligence Platform

**FIG Stress Intelligence Platform** | Python · FastAPI · PostgreSQL (JSONB, point-in-time schema) · pandas · statsmodels · APScheduler · Docker · FRED / FDIC BankFind / SEC EDGAR / yfinance

- Built a point-in-time credit-stress system tracking 7 cross-cutting FRED indicators across 13 financial-services sectors (asset management, lending, insurance, real estate finance, etc.); dual-timestamp (`observation_date` / `vintage_date`) storage reconstructs the exact information set available on any historical date, eliminating look-ahead bias from FRED's revised series
- Designed an empirical weighting framework that replaces equal-weighting with fitted coefficients: derived per-sector equity-side proxies (ETF drawdown from 180-day rolling max) and credit-side proxies (forward-filled z-score composites of sub-sector lending signals), then fit paired OLS regressions per sector to produce dual `(w_equity, w_credit)` weights that drive each sector's score
- Validated signal design against historical events — SVB scored 29/100 (idiosyncratic) vs COVID at 72/100 (systemic) — confirming the index distinguishes institution-level shocks from market-wide stress
- Shipped an interactive dashboard (~5k-LOC vanilla JS frontend, 20-endpoint FastAPI service) with vintage-aware historical scrubbing, multi-series overlay charts with per-series normalization, savable plot configurations, and versioned weight snapshots with named history
- Layering a downstream regression that joins FDIC merger events, EDGAR 8-K deal terms, and FRED macros aligned to announcement dates to predict bank M&A price-to-book multiples — testing whether sector-specific stress derived from acquired-bank Call Report exposures adds incremental signal beyond a macro baseline
