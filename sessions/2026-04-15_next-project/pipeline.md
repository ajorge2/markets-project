# FIG Valuation Multiple Predictor — Data Pipeline
# Date: 2026-04-15

## What this builds

A regression model: `price_to_book ~ f(macro signals)`

Where price-to-book is the acquisition multiple paid for a bank at deal close.
The macro signals are FRED series measured at the time of deal announcement.
The goal is to quantify how credit conditions predict what buyers pay for banks at exit.

---

## Run sequence (one time, in order)

```bash
cd src/ingestion

# 1. FDIC — acquisition history + pre-acquisition book values
python3 fdic_ingest.py

# 2. FDIC — acquirer names (fast, just re-paginates history)
python3 fdic_ingest.py --acquirers-only

# 3. FRED — macro signals (already done; re-run to refresh)
python3 fred_ingest.py backfill

# 4. EDGAR — deal prices from 8-K press releases (~90 min)
python3 edgar_ingest.py

# 4a. EDGAR — quality pass: null out implausible P/B values, then re-run
#     See "Data quality" section below. Safe to skip if this is a first run.
psql -d markets_project -f ../scripts/edgar_quality_pass.sql
python3 edgar_ingest.py   # re-run picks up only the nulled rows

# 5. Export analysis dataset
cd ../analysis
python3 -c "from build_dataset import build_dataset; build_dataset().to_csv('deals.csv', index=False)"

# 6. Run regression in R
Rscript analysis.R
```

Steps 1–4 are safe to re-run. Each uses `ON CONFLICT DO NOTHING` (SQL) or
skips rows that already have data. Step 4 skips deals that already have
`deal_price_millions` set.

---

## Data quality — EDGAR extraction (Step 4)

Bank M&A press releases follow a predictable structure, but the EDGAR full-text
search is noisy enough that two categories of false positives appear at scale.
Both were identified empirically after the first pass and fixed before re-run.

### False positive type 1 — wrong dollar amount (regex too broad)

**Symptom:** Extracted deal price implies P/B > 5x for a community bank.

**Root cause:** The original regex matched bare `"approximately $X billion"`,
which also fires on boilerplate like:

> *"After closing of the merger, Old National has approximately $52 billion
> of assets..."*

That sentence appears in nearly every bank M&A press release — the acquirer
always discloses combined total assets. The regex grabbed $52B as the deal
price for CapStar Bank (true deal: ~$263M, ~0.69x book).

**Fix (`edgar_client.py` — `_regex_extract_deal_price`):**
Replaced the broad `"approximately"` alternative with patterns that require
explicit deal language: `"consideration of approximately"`,
`"transaction valued at"`, `"aggregate consideration of"`, etc.
Added a negative lookahead on the `"for approximately $X"` pattern to reject
matches followed by `"of assets"`, `"of deposits"`, or `"of loans"`.

### False positive type 2 — wrong filing (irrelevant 8-K)

**Symptom:** Extracted deal price implies P/B < 0.1x for a large bank, or the
filing entity is unrelated to the deal.

**Root cause:** EDGAR full-text search returns any 8-K that mentions the
bank name — including earnings releases where the bank appears as a lender
in a credit facility. Example: querying for "Comerica Bank" returned a
Credit Acceptance Corporation (CACC) Q2 earnings release. CACC's EX-99.1
mentioned Comerica as one of its revolving credit lenders. The regex then
extracted "$2.1 million associated annual operating costs" as the deal price
for a bank with $7.2B in book equity.

**Fix (`edgar_client.py` — `_press_release_mentions_acquisition`):**
Added a relevance gate before extraction. Requires the target bank name to
appear within 400 characters of an M&A keyword (`"acquisition"`, `"acquir"`,
`"merger"`, etc.) somewhere in the press release. Filings that don't pass are
skipped and the next search result is tried.

### Post-run quality pass

After each EDGAR ingest run, null out rows with implausible P/B multiples
so they are re-queued for the next run:

```sql
-- edgar_quality_pass.sql
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
```

**Why 0.3x–3.5x:** The empirical distribution of unassisted bank M&A
multiples (CHANGECODE 223) is tightly clustered around 1.0x–2.0x book.
Sub-0.3x deals do exist in genuine distress situations but are rare enough
that values below that threshold are more likely extraction errors than real
prices. Above 3.5x is essentially unheard of for unassisted bank mergers and
reliably indicates the regex matched total assets rather than deal value.

The R analysis applies its own 0–5x filter as a second pass; the SQL pass
here is specifically to re-queue bad rows for re-extraction, not to filter
the analysis sample.

---

## Step 1 — FDIC acquisition history (`fdic_ingest.py`)

**What it fetches:**
FDIC BankFind API `/history` endpoint, filtered to `CHANGECODE:223`
(Merger Without Assistance — unassisted mergers only, excludes FDIC-assisted
failures and conversions).

**Fields pulled:**
- `OUT_INSTNAME` → company (the bank being acquired)
- `OUT_CERT` → FDIC certificate number (used to look up financials)
- `EFFDATE` → acq_date (the legal effective date of the merger)

**For each merger record**, it then calls `/financials` to get the most recent
quarterly report before the acquisition date:
- `EQ` → book_value (equity capital in **thousands USD**)
- `REPDTE` → report_date (date of that quarterly filing)

**Pagination:** FDIC returns max 10,000 rows per request. Two pages cover the
~12,988 CHANGECODE:223 records since 1990.

**Output:** `acquisitions` table, ~11,116 rows (some records have no financials
and are skipped).

---

## Step 2 — Acquirer names (`fdic_ingest.py --acquirers-only`)

Re-paginates the same FDIC history endpoint but also requests `ACQ_INSTNAME`
(the acquiring institution name). Updates `acquisitions.acquirer_name` for
each row. This is stored separately because it's needed for EDGAR search but
doesn't affect the financial data.

---

## Step 3 — FRED macro signals (`fred_ingest.py`)

Fetches full vintage history for 5 macro series:

| Series | Description | Transform in regression |
|---|---|---|
| `T10Y2Y` | 10Y minus 2Y Treasury spread | Level (already in pct pts) |
| `UMCSENT` | U. Michigan Consumer Sentiment | Level |
| `DSPI` | Real Disposable Personal Income | YoY % change |
| `CPROFIT` | Real Corporate Profits After Tax | YoY % change |
| `COMPUTSA` | Private Nonresidential Construction Spending | YoY % change |

The income/profit/construction series use YoY % because their levels have
long-run trends (inflation, population growth) that would dominate the signal.
T10Y2Y and UMCSENT are already stationary in levels.

Each observation is stored with two timestamps (`observation_date`,
`vintage_date`) so the regression can use only data that was actually published
at the time of each deal announcement — no look-ahead bias.

---

## Step 4 — EDGAR deal prices (`edgar_ingest.py`)

This is the slow step (~90 min). For each acquisition with `book_value >= $100M`
equity (1,116 deals), it:

1. **Cleans the name** — strips FDIC regulatory suffixes ("National Association",
   "Federal Savings Bank", etc.) that don't appear in press release headlines

2. **Searches EDGAR full-text** — queries `efts.sec.gov` for 8-K filings
   mentioning `"{bank name}" acquisition` within 2 years before the close date.
   The 2-year window covers the typical announcement-to-close lag for bank deals.

3. **Fetches the press release** — finds the EX-99.1 exhibit in the filing
   index (the standard location for acquisition press releases)

4. **Extracts the deal price** — regex patterns match common M&A press release
   language (`"for approximately $X billion"`, `"aggregate consideration of"`,
   `"purchase price of"`, etc.). Falls back to Claude Haiku if
   `ANTHROPIC_API_KEY` is set and regex misses.

5. **Stores** `deal_price_millions`, `consideration_type` (cash/stock/mixed),
   `edgar_adsh` (accession number of the source filing), and
   `announcement_date` (the 8-K filing date, used instead of close date for
   macro signal alignment).

**Why only $100M+ deals:** Small community banks are typically acquired by
other small banks that aren't SEC registrants and don't file 8-Ks. Below $100M
equity, the EDGAR hit rate approaches zero.

**Known false positive risk:** Generic bank names ("First National Bank",
"Peoples Bank") appear in many unrelated 8-Ks. The regex may extract a dollar
figure from the wrong deal. The P/B plausibility filter in step 5
(0.5x–3.5x) catches most of these.

---

## Step 5 — Build dataset (`build_dataset.py`)

Joins the acquisitions table with FRED macro series. For each deal:

- Uses `announcement_date` (from EDGAR filing date) as the macro signal
  lookup date, not the FDIC close date. The deal price is set at announcement,
  so macro conditions at announcement are what matter causally.
- For each macro series, finds the most recent observation with
  `vintage_date <= announcement_date` — point-in-time, no look-ahead.
- Computes YoY % for DSPI, CPROFIT, COMPUTSA.
- Outputs one row per deal.

---

## Step 6 — Regression (`analysis.R`)

1. **EDA** — P/B distribution, P/B over time, deals per year
2. **Correlation matrix** — identifies which macro variables move together
3. **VIF** — iteratively drops variables with VIF > 10 until survivors are
   independent enough for stable OLS estimation
4. **OLS** — fits `lm(price_to_book ~ surviving_variables)` on pre-2020 deals
5. **Diagnostics** — residual plots, Q-Q, leverage
6. **Coefficient plot** — estimates with 95% confidence intervals
7. **Holdout validation** — tests out-of-sample on 2020+ deals (COVID and
   post-COVID macro regime, not seen during training)

**Why VIF instead of regularization:** The goal is interpretation, not
prediction accuracy. VIF → OLS gives unbiased coefficients you can translate
directly into economic meaning ("a 1pp wider yield curve inversion is
associated with a 0.Xx lower P/B multiple"). Regularized coefficients are
biased by design and can't support that kind of statement.

---

## Key schema notes

```
acquisitions.book_value         — thousands USD  (FDIC EQ field)
acquisitions.deal_price_millions — millions USD   (from press release)

price_to_book = deal_price_millions / (book_value / 1000)
```

## Known limitations

| Limitation | Impact |
|---|---|
| EDGAR only covers public acquirers | Private acquirer deals (~30% of market) have no recoverable price |
| Regex extractor has false positive risk on generic bank names | P/B plausibility filter catches most; some noise remains |
| Uses close date as fallback when announcement date unavailable | Minor look-ahead in macro signal alignment for those deals |
| EDGAR full-text search returns 500 errors occasionally | Those deals are skipped and logged as "not found" |
