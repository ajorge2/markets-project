# License scope and third-party material

The root MIT license applies to original software authored by Andrew Jorge. It does not relicense third-party data, papers, images, dependencies, or trademarks. Preserve any more specific notices.

FRED/ALFRED: https://fred.stlouisfed.org/legal/. Some series include third-party restrictions; public API access does not grant blanket redistribution rights. FDIC: https://www.fdic.gov/ and SEC EDGAR: https://www.sec.gov/. Cite the original source and verify dataset-specific restrictions before further redistribution. Andrew Jorge's software MIT license does not relicense third-party series, filings, or marks.

## Data sources and configuration

The public data interface uses a series allowlist. Additional series and saved analysis routes use `MARKETS_LICENSED_DATA=true` when the operator has the applicable data-use rights. Model-fitting scripts use `FRED_MODEL_USE_PERMITTED=true`. Dashboard scores use the configured available indicators; research results identify their own datasets and settings.

Sources: Board of Governors of the Federal Reserve System, Federal Reserve Bank of New York, Federal Reserve Bank of Chicago, Federal Reserve Bank of St. Louis, retrieved through [FRED](https://fred.stlouisfed.org/); FDIC BankFind; SEC EDGAR. UMCSENT attribution: Surveys of Consumers, University of Michigan, Consumer Sentiment ©, retrieved from FRED. Dataset-specific terms are available at [FRED](https://fred.stlouisfed.org/legal/) and in the [ICE/BofA series notes](https://fred.stlouisfed.org/series/BAMLC0A0CM).
