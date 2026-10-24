# Public dashboard boundary

Reads expose research derived from the cited public FRED, FDIC, and SEC sources. Mutating routes require an operator bearer token configured as `MARKETS_ADMIN_TOKEN`; without it all writes are disabled. Keep that token on the server/operator client, never in a static dashboard bundle. Dataset-specific usage terms are listed below.

## Data sources and configuration

The public data interface uses a series allowlist. Additional series and saved analysis routes use `MARKETS_LICENSED_DATA=true` when the operator has the applicable data-use rights. Model-fitting scripts use `FRED_MODEL_USE_PERMITTED=true`. Dashboard scores use the configured available indicators; research results identify their own datasets and settings.

Sources: Board of Governors of the Federal Reserve System, Federal Reserve Bank of New York, Federal Reserve Bank of Chicago, Federal Reserve Bank of St. Louis, retrieved through [FRED](https://fred.stlouisfed.org/); FDIC BankFind; SEC EDGAR. UMCSENT attribution: Surveys of Consumers, University of Michigan, Consumer Sentiment ©, retrieved from FRED. Dataset-specific terms are available at [FRED](https://fred.stlouisfed.org/legal/) and in the [ICE/BofA series notes](https://fred.stlouisfed.org/series/BAMLC0A0CM).
