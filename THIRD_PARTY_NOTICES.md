# License scope and third-party material

The root MIT license applies to original software authored by Andrew Jorge. It does not relicense third-party data, papers, images, dependencies, trademarks, or employer/client material. Preserve any more specific notices.

FRED/ALFRED: https://fred.stlouisfed.org/legal/. Some series include third-party restrictions; public API access does not grant blanket redistribution rights. FDIC: https://www.fdic.gov/ and SEC EDGAR: https://www.sec.gov/. Cite the original source and verify dataset-specific restrictions before further redistribution. Andrew Jorge's software MIT license does not relicense third-party series, filings, or marks.

## Restricted market data withdrawn

ICE/BofA observations BAMLC0A0CM and BAMLH0A0HYM2 were removed from the current published data file. Their FRED series notes prohibit reproduction/redistribution without prior written permission: https://fred.stlouisfed.org/series/BAMLC0A0CM and https://fred.stlouisfed.org/series/BAMLH0A0HYM2. Public series routes now use an explicit allowlist; raw restricted series and saved analysis routes are unavailable unless the operator establishes the applicable rights and sets MARKETS_LICENSED_DATA=true. Public dashboard scores omit restricted inputs and are not equivalent to historical benchmark scores. Current FRED terms also restrict AI/model uses; model-fitting scripts require FRED_MODEL_USE_PERMITTED=true after rights review. These flags are operator assertions, not licenses granted by this software.

Data attribution: Board of Governors of the Federal Reserve System, Federal Reserve Bank of New York, Federal Reserve Bank of Chicago, Federal Reserve Bank of St. Louis, retrieved through FRED; FDIC BankFind; SEC EDGAR. Historical UMCSENT references: Surveys of Consumers, University of Michigan, Consumer Sentiment ©, retrieved from FRED. Third-party ownership and terms remain unchanged. Older Git commits, backend databases, and downloaded copies are not erased by this update.
