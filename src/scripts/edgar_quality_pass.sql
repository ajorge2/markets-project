-- edgar_quality_pass.sql
-- Nulls out EDGAR-extracted deal prices with implausible P/B multiples,
-- re-queuing them for the next edgar_ingest.py run.
--
-- Run after each edgar_ingest.py pass:
--   psql -d markets_project -f src/scripts/edgar_quality_pass.sql
--
-- Thresholds: 0.3x–3.5x book value.
-- Below 0.3x: regex likely matched a fee, operating cost, or irrelevant dollar figure.
-- Above 3.5x: regex likely matched combined total assets of the acquirer post-merger.
-- See sessions/2026-04-15_next-project/pipeline.md for full root cause analysis.

UPDATE acquisitions
SET deal_price_millions = NULL,
    price_per_share     = NULL,
    consideration_type  = NULL,
    edgar_adsh          = NULL,
    announcement_date   = NULL
WHERE deal_price_millions IS NOT NULL
  AND book_value > 0
  AND (
    deal_price_millions / (book_value / 1000.0) > 3.5
    OR deal_price_millions / (book_value / 1000.0) < 0.3
  );
