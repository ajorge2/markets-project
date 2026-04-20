"""
EDGAR client — searches for acquisition filings and extracts deal prices.

Strategy (tried in order):
  1. DEFM14A (definitive merger proxy) — filed by target's holding company before shareholder
     vote, ~1-6 months before close. Contains deal terms verbatim. Higher signal-to-noise
     than 8-K full-text search because DEFM14A is always about the specific merger.
  2. 8-K press release (EX-99.1) — filed by acquirer on announcement date.

Flow per deal:
  1. search_defm14a_filings(target_name, close_date)
       → EFTS full-text search for DEFM14A mentioning target in 2yr window before close
  2. fetch_defm14a_text(cik, adsh)
       → fetches main DEFM14A document, strips HTML, returns first 15k chars
  3. [if DEFM14A misses] search_8k_filings(target_name, close_date)
       → falls back to 8-K full-text search
  4. fetch_press_release_text(cik, adsh)
       → finds EX-99.1, fetches and strips HTML, returns first 12k chars
  5. extract_deal_price(text, target_name)
       → regex patterns for bank M&A deal terms
       → falls back to Claude Haiku if ANTHROPIC_API_KEY is set
"""

import os
import re
import json
import requests
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"
HEADERS = {"User-Agent": "markets-project/1.0 ajorge@researchproject.com"}

# Suffixes FDIC appends that don't appear in press release headlines
_BANK_SUFFIXES = re.compile(
    r',?\s+('
    r'national association|national bank|federal savings bank|'
    r'federal savings association|savings bank|savings association|'
    r'state bank|community bank|federal bank|'
    r'n\.?a\.?|f\.?s\.?b\.?|f\.?s\.?a\.?'
    r')\.?$',
    re.IGNORECASE,
)


def clean_bank_name(name: str) -> str:
    """Strip regulatory suffixes from FDIC institution names for EDGAR full-text search.
    Leaves name unchanged if stripping would reduce it to a single word — avoids
    over-stripping names like 'Dogwood State Bank' → 'Dogwood' (too generic to search).
    """
    cleaned = _BANK_SUFFIXES.sub("", name).strip().strip(",")
    if len(cleaned.split()) < 2:
        return name.strip()
    return cleaned


def search_8k_filings(target_name: str, close_date: str, acquirer_name: str = None) -> list[dict]:
    """
    Search EDGAR full-text for 8-K filings mentioning target_name.
    Searches from 2 years before close_date up to close_date.
    Optionally filters by acquirer_name (the entity that filed).
    Returns list of {adsh, cik, file_date, display_names}.
    """
    close = date.fromisoformat(close_date)
    start = (close - timedelta(days=730)).isoformat()

    # "acquisition" keyword reduces noise from 8-Ks that mention the bank as a lender/counterparty.
    # Note: EDGAR full-text search does not stem, so "acquisition" matches "acquisition" but not
    # "acquire". M&A press releases reliably contain both forms somewhere in the document body.
    # Parenthetical OR syntax is not supported by the EDGAR EFTS API — use AND-only queries.
    params = {
        "q": f'"{target_name}" acquisition',
        "forms": "8-K",
        "dateRange": "custom",
        "startdt": start,
        "enddt": close_date,
    }
    _ = acquirer_name  # retained as parameter; entity filter excluded (name mismatch issues)

    try:
        resp = requests.get(EFTS_URL, params=params, headers=HEADERS, timeout=15)
    except requests.exceptions.RequestException:
        return []
    if resp.status_code != 200:
        return []

    hits = resp.json().get("hits", {}).get("hits", [])
    results = []
    for hit in hits:
        src = hit.get("_source", {})
        ciks = src.get("ciks") or []
        results.append({
            "adsh": src.get("adsh"),
            "cik": ciks[0] if ciks else None,
            "file_date": src.get("file_date"),
            "display_names": src.get("display_names"),
        })
    return results


def get_filing_documents(cik: str, adsh: str) -> list[dict]:
    """
    Fetch the filing's document index from EDGAR.
    Returns list of {doc_type, filename, url}.
    """
    adsh_folder = adsh.replace("-", "")
    index_url = f"{ARCHIVES_BASE}/{cik}/{adsh_folder}/{adsh}-index.htm"

    try:
        resp = requests.get(index_url, headers=HEADERS, timeout=15)
    except requests.exceptions.RequestException:
        return []
    if resp.status_code != 200:
        return []

    docs = []
    # Table columns: seq | description | filename | doc_type | size
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', resp.text, re.DOTALL | re.IGNORECASE)
    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL | re.IGNORECASE)
        if len(cells) < 4:
            continue
        doc_type = re.sub(r'<[^>]+>', '', cells[3]).strip()   # 4th column
        href_match = re.search(r'href="([^"]+)"', cells[2], re.IGNORECASE)  # 3rd column
        if not href_match:
            continue
        href = href_match.group(1)
        # Strip EDGAR inline viewer prefix if present
        href = re.sub(r'^/ix\?doc=', '', href)
        url = href if href.startswith("http") else f"https://www.sec.gov{href}"
        docs.append({"doc_type": doc_type, "url": url})

    return docs


def fetch_press_release_text(cik: str, adsh: str) -> str | None:
    """
    Find the EX-99.1 (press release) exhibit in an 8-K filing and return its plain text.
    Returns None if no press release found.
    """
    docs = get_filing_documents(cik, adsh)

    # Prefer explicit EX-99.1; fall back to any EX-99 variant
    pr_url = None
    for doc in docs:
        if doc["doc_type"] in ("EX-99.1", "EX-99"):
            pr_url = doc["url"]
            break

    if not pr_url:
        return None

    try:
        resp = requests.get(pr_url, headers=HEADERS, timeout=15)
    except requests.exceptions.RequestException:
        return None
    if resp.status_code != 200:
        return None

    # Strip HTML, collapse whitespace
    text = re.sub(r'<[^>]+>', ' ', resp.text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:12000]


def _regex_extract_deal_price(text: str) -> dict:
    """
    Extract deal price from press release text using regex.
    Bank M&A press releases are formulaic — this handles the common patterns.
    Returns {deal_price_millions, price_per_share, consideration_type} with Nones for misses.
    """
    result = {"deal_price_millions": None, "price_per_share": None, "consideration_type": None}

    # Total deal value patterns — ordered by precision (most specific first).
    # Deliberately avoid bare "approximately $X billion" which also matches
    # "approximately $52 billion of assets" (total-assets disclosures in press releases).
    total_patterns = [
        # Explicit consideration/deal language — highest precision
        r'(?:aggregate consideration(?: of)?|total consideration(?: of)?|merger consideration of|transaction valued at|consideration of approximately|valued at approximately)\s+(?:approximately\s+)?\$\s*([\d,\.]+)\s*(billion|million)',
        # "worth approximately $X" — fairly M&A-specific
        r'worth\s+(?:approximately\s+)?\$\s*([\d,\.]+)\s*(billion|million)',
        # "$X billion/million transaction/deal/acquisition/merger"
        r'\$\s*([\d,\.]+)\s*(billion|million)\s+(?:transaction|deal|acquisition|merger|purchase)',
        # "for approximately $X billion/million" — exclude "of assets/deposits/loans" context
        r'for\s+(?:approximately\s+)?\$\s*([\d,\.]+)\s*(billion|million)(?!\s+(?:of\s+)?(?:in\s+)?(?:total\s+)?(?:assets|deposits|loans|common\s+shares))',
        # "purchase price of approximately $X" — very specific
        r'purchase price of (?:approximately )?\$\s*([\d,\.]+)\s*(billion|million)',
    ]
    for pat in total_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = float(m.group(1).replace(",", ""))
            unit = m.group(2).lower()
            result["deal_price_millions"] = val * 1000 if unit == "billion" else val
            break

    # Price per share: "$12.50 per share"
    pps_m = re.search(r'\$\s*([\d,\.]+)\s+per\s+share', text, re.IGNORECASE)
    if pps_m:
        result["price_per_share"] = float(pps_m.group(1).replace(",", ""))

    # Consideration type — order matters: check mixed before pure cash/stock
    text_lower = text.lower()
    mixed_signals = [
        "cash and stock", "cash or stock", "mix of cash",
        "in cash and", "cash and shares", "cash consideration and",
        "combination of cash and", "part cash",
    ]
    pure_cash = ["all-cash", "all cash", "cash consideration", "entirely in cash", "100% cash"]
    pure_stock = ["all-stock", "all stock", "stock-for-stock", "entirely in stock", "100% stock"]

    if any(s in text_lower for s in mixed_signals):
        result["consideration_type"] = "mixed"
    elif any(s in text_lower for s in pure_cash):
        result["consideration_type"] = "cash"
    elif any(s in text_lower for s in pure_stock):
        result["consideration_type"] = "stock"

    return result


def extract_deal_price(text: str, target_name: str) -> dict:
    """
    Extract deal price from press release text.
    Tries regex first; falls back to Claude Haiku if ANTHROPIC_API_KEY is set.
    Returns {deal_price_millions, price_per_share, consideration_type}.
    """
    result = _regex_extract_deal_price(text)
    if result["deal_price_millions"] is not None:
        return result

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return result

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)

        prompt = f"""Extract acquisition deal price from this bank M&A press release.

Target company being acquired: {target_name}

Press release (first 12,000 chars):
{text}

Return JSON only — no explanation. Keys:
- deal_price_millions: total deal value in millions USD (number, or null if not found)
- price_per_share: price per share offered (number, or null)
- consideration_type: "cash", "stock", "mixed", or null

If the press release does not describe an acquisition of {target_name}, return all nulls."""

        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = msg.content[0].text.strip()
        raw = re.sub(r'^```[a-z]*\n?', '', raw)
        raw = re.sub(r'\n?```$', '', raw)
        return json.loads(raw)
    except Exception:
        return result


def _press_release_mentions_acquisition(text: str, target_name: str) -> bool:
    """
    Verify the press release is actually about acquiring target_name, not just
    mentioning it as a lender or counterparty.  Requires target_name to appear
    within 400 characters of an M&A keyword anywhere in the document.
    """
    text_lower = text.lower()
    target_lower = target_name.lower()
    if target_lower not in text_lower:
        return False
    ma_terms = ["acquisition", "acquire", "acquir", "merger", "to be acquired", "will be acquired"]
    for m in re.finditer(re.escape(target_lower), text_lower):
        window = text_lower[max(0, m.start() - 400): m.end() + 400]
        if any(term in window for term in ma_terms):
            return True
    return False


def search_defm14a_filings(target_name: str, close_date: str) -> list[dict]:
    """
    Search EDGAR full-text for DEFM14A filings mentioning target_name.
    DEFM14A = definitive merger proxy filed by the target's holding company.
    Searched from 2 years before close_date up to close_date.
    Returns list of {adsh, cik, file_date, display_names}.
    """
    close = date.fromisoformat(close_date)
    start = (close - timedelta(days=730)).isoformat()
    params = {
        "q": f'"{target_name}"',
        "forms": "DEFM14A",
        "dateRange": "custom",
        "startdt": start,
        "enddt": close_date,
    }
    try:
        resp = requests.get(EFTS_URL, params=params, headers=HEADERS, timeout=15)
    except requests.exceptions.RequestException:
        return []
    if resp.status_code != 200:
        return []

    hits = resp.json().get("hits", {}).get("hits", [])
    results = []
    for hit in hits:
        src = hit.get("_source", {})
        ciks = src.get("ciks") or []
        results.append({
            "adsh": src.get("adsh"),
            "cik": ciks[0] if ciks else None,
            "file_date": src.get("file_date"),
            "display_names": src.get("display_names"),
        })
    return results


def fetch_defm14a_text(cik: str, adsh: str) -> str | None:
    """
    Fetch plain text from the main body of a DEFM14A filing.
    Returns first 15k chars (deal consideration is always in the opening pages).
    """
    docs = get_filing_documents(cik, adsh)

    # Main proxy document type; fall back to first HTML file
    main_url = None
    for doc in docs:
        if doc["doc_type"].upper() in ("DEFM14A", "DEF 14A", "DEFA14A"):
            main_url = doc["url"]
            break
    if not main_url:
        for doc in docs:
            if doc["url"].lower().endswith((".htm", ".html")):
                main_url = doc["url"]
                break

    if not main_url:
        return None

    try:
        resp = requests.get(main_url, headers=HEADERS, timeout=20)
    except requests.exceptions.RequestException:
        return None
    if resp.status_code != 200:
        return None

    text = re.sub(r'<[^>]+>', ' ', resp.text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:15000]


def get_deal_price(target_name: str, close_date: str, acquirer_name: str = None) -> dict | None:
    """
    Top-level function: search EDGAR for acquisition filing, extract deal price.
    Tries DEFM14A first (filed by target's HC, highest signal), then falls back to 8-K.
    Returns {deal_price_millions, price_per_share, consideration_type, filing_date, adsh}
    or None if no filing found.
    """
    search_name = clean_bank_name(target_name)

    # Strategy 1: DEFM14A — definitive merger proxy filed by target's holding company.
    # A DEFM14A is definitionally a merger filing so we skip the mentions check.
    defm_filings = search_defm14a_filings(search_name, close_date)
    for filing in defm_filings[:3]:
        cik = filing["cik"]
        adsh = filing["adsh"]
        if not cik or not adsh:
            continue
        text = fetch_defm14a_text(cik, adsh)
        if not text:
            continue
        result = extract_deal_price(text, search_name)
        if result.get("deal_price_millions") is not None:
            result["filing_date"] = filing["file_date"]
            result["adsh"] = adsh
            return result

    # Strategy 2: 8-K press release (EX-99.1) filed by acquirer on announcement date
    filings = search_8k_filings(search_name, close_date, acquirer_name)
    for filing in filings[:5]:
        cik = filing["cik"]
        adsh = filing["adsh"]
        if not cik or not adsh:
            continue

        text = fetch_press_release_text(cik, adsh)
        if not text:
            continue

        # Skip 8-Ks that don't actually discuss acquiring target_name —
        # full-text search returns any 8-K mentioning the bank, including
        # earnings releases where it appears as a lender or counterparty.
        if not _press_release_mentions_acquisition(text, search_name):
            continue

        result = extract_deal_price(text, search_name)
        if result.get("deal_price_millions") is not None:
            result["filing_date"] = filing["file_date"]
            result["adsh"] = adsh
            return result

    return None
