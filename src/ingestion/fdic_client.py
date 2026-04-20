import requests

FDIC_BASE_URL = "https://api.fdic.gov/banks"


def get_history_records():
    """
    Paginate FDIC history for all CHANGECODE 223 mergers (1990-present).
    Yields one dict per merger with company, cert, acq_date, and acquirer_name.
    """
    offset = 0
    while True:
        response = requests.get(
            f"{FDIC_BASE_URL}/history",
            params={
                "filters": "CHANGECODE:223 AND EFFDATE:[1990-01-01 TO *]",
                "fields": "OUT_INSTNAME,OUT_CERT,EFFDATE,ACQ_INSTNAME,ACQ_UNINUM",
                "limit": 10000,
                "offset": offset,
                "format": "json",
            },
        )
        rows = response.json().get("data", [])
        if not rows:
            break
        for row in rows:
            d = row["data"]
            yield {
                "company": d["OUT_INSTNAME"],
                "cert": d["OUT_CERT"],
                "acq_date": d["EFFDATE"][:10],
                "acquirer_name": d.get("ACQ_INSTNAME"),
                "acq_uninum": d.get("ACQ_UNINUM"),
            }
        offset += 10000


def get_financials_for(record: dict) -> dict | None:
    """
    Fetch the most recent pre-acquisition balance sheet for one company.
    Returns None if no financials found before the acquisition date.
    """
    response = requests.get(
        f"{FDIC_BASE_URL}/financials",
        params={
            "filters": f"CERT:{record['cert']} AND REPDTE:[1990-01-01 TO {record['acq_date']}]",
            "fields": "CERT,REPDTE,EQ",
            "sort_by": "REPDTE",
            "sort_order": "DESC",
            "limit": 1,
            "format": "json",
        },
    )
    data = response.json().get("data", [])
    if not data:
        return None

    fin = data[0]["data"]
    return {
        "company": record["company"],
        "acq_date": record["acq_date"],
        "acquirer_name": record["acquirer_name"],
        "acq_uninum": record["acq_uninum"],
        "report_date": fin.get("REPDTE"),
        "book_value": fin.get("EQ"),
    }


def get_holding_company(acq_uninum: str) -> str | None:
    """Look up the top-tier holding company name for an acquirer via FDIC NAMEHCR."""
    if not acq_uninum:
        return None
    response = requests.get(
        f"{FDIC_BASE_URL}/institutions",
        params={
            "filters": f"UNINUM:{acq_uninum}",
            "fields": "NAMEHCR",
            "limit": 1,
            "format": "json",
        },
    )
    data = response.json().get("data", [])
    if not data:
        return None
    return data[0]["data"].get("NAMEHCR")
