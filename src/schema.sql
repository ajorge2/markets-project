-- Credit Stress Dashboard — Database Schema
-- Every observation stored with dual timestamps for point-in-time querying.

CREATE TABLE IF NOT EXISTS series_registry (
    series_id           TEXT PRIMARY KEY,
    description         TEXT NOT NULL,
    sector              TEXT NOT NULL,      -- 'banks', 'consumer', 'cre', 'corporate'
    signal_speed        TEXT NOT NULL,      -- 'fast', 'slow', 'context'
    update_frequency    TEXT NOT NULL,      -- 'daily', 'weekly', 'monthly', 'quarterly'
    fred_series_id      TEXT,               -- NULL if not from FRED
    units               TEXT
);

CREATE TABLE IF NOT EXISTS series_observations (
    series_id           TEXT REFERENCES series_registry(series_id),
    observation_date    DATE NOT NULL,      -- period this value covers
    vintage_date        DATE NOT NULL,      -- when this value was published
    value               NUMERIC,
    PRIMARY KEY (series_id, observation_date, vintage_date)
);

CREATE TABLE IF NOT EXISTS staleness_state (
    series_id           TEXT PRIMARY KEY REFERENCES series_registry(series_id),
    last_vintage_date   DATE,
    last_value          NUMERIC,
    expected_next_date  DATE,
    status              TEXT DEFAULT 'pending'  -- 'fresh', 'pending', 'overdue'
);

-- Index for the point-in-time backtest query pattern
CREATE INDEX IF NOT EXISTS idx_observations_vintage
    ON series_observations (series_id, vintage_date, observation_date);

-- =============================================================================
-- Bank M&A acquisitions — FDIC CHANGECODE 223 (Merger Without Assistance)
--
-- Populated by:
--   fdic_ingest.py     → company, acq_date, report_date, book_value, acquirer_name
--   edgar_ingest.py    → deal_price_millions, price_per_share, consideration_type, edgar_adsh
--
-- price_to_book = deal_price_millions / (book_value / 1000)
--   book_value is in thousands USD (FDIC EQ field units)
-- =============================================================================
CREATE TABLE IF NOT EXISTS acquisitions (
    company                 TEXT        NOT NULL,
    acq_date                DATE        NOT NULL,
    report_date             DATE,                   -- date of last FDIC financials before acq
    book_value              NUMERIC,                -- equity capital in thousands USD (FDIC EQ)
    acquirer_name           TEXT,                   -- ACQ_INSTNAME from FDIC history
    acq_uninum              TEXT,                   -- ACQ_UNINUM from FDIC history (acquirer institution ID)
    deal_price_millions     NUMERIC,                -- aggregate deal value in millions USD
    price_per_share         NUMERIC,                -- per-share price from press release
    consideration_type      TEXT,                   -- 'cash', 'stock', or 'mixed'
    edgar_adsh              TEXT,                   -- EDGAR accession number of source 8-K
    announcement_date       DATE,                   -- 8-K filing date (≈ deal announcement)
    acquirer_hc_name        TEXT,                   -- top-tier holding company of acquirer (FDIC NAMEHCR)
    PRIMARY KEY (company, acq_date)
);

-- =============================================================================
-- Series registry
--
-- Spread indicators (CC_SPREAD, DFF_SOFR_SPREAD) are computed at query time
-- in compute.py from pairs of raw series — they are not stored here.
--
-- Excluded series (documented gaps):
--   RRVRUSQ156N  — residential vacancy: anticorrelated with commercial office
--                  stress; measures apartments, not CRE. No free FRED substitute.
--   NFCICREDIT   — broad economy-wide credit index, not CRE-specific. Would have
--                  shown moderate during the 2023 office vacancy crisis.
-- =============================================================================
INSERT INTO series_registry VALUES
    -- Banks
    ('TOTCI',        'Commercial & industrial loan growth',         'banks',    'slow',    'weekly',    'TOTCI',        'billions USD'),
    ('DFF',          'Effective Federal Funds Rate (daily)',        'banks',    'fast',    'daily',     'DFF',          'percent'),
    ('SOFR',         'Secured Overnight Financing Rate',           'banks',    'fast',    'daily',     'SOFR',         'percent'),
    -- Consumer
    ('DRCCLACBS',    'Credit card delinquency rate',               'consumer', 'slow',    'quarterly', 'DRCCLACBS',    'percent'),
    ('DRCLACBS',     'Consumer loan delinquency rate (all)',        'consumer', 'slow',    'quarterly', 'DRCLACBS',     'percent'),
    ('TERMCBCCALLNS','Credit card interest rate',                  'consumer', 'fast',    'monthly',   'TERMCBCCALLNS','percent'),
    ('FEDFUNDS',     'Federal Funds Effective Rate (monthly avg)', 'consumer', 'context', 'monthly',   'FEDFUNDS',     'percent'),
    -- CRE
    ('DRCRELEXFACBS','CRE loan delinquency rate (excl. farmland)', 'cre',      'slow',    'quarterly', 'DRCRELEXFACBS','percent'),
    -- Corporate
    ('BAMLC0A0CM',   'IG corporate credit spread',                 'corporate','fast',    'daily',     'BAMLC0A0CM',   'percent'),
    ('BAMLH0A0HYM2', 'HY corporate credit spread',                 'corporate','fast',    'daily',     'BAMLH0A0HYM2', 'percent')
ON CONFLICT (series_id) DO NOTHING;

-- Seed staleness state for all registered series
INSERT INTO staleness_state (series_id, status)
SELECT series_id, 'pending' FROM series_registry
ON CONFLICT (series_id) DO NOTHING;
