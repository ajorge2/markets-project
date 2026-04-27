"""
Seed the 13 Stone Point sub-sectors and the indicator_sector_map cross-product.

Idempotent. Run after schema.sql is applied:
    python src/scripts/bootstrap_sectors.py

Every sector × every indicator gets weight=1.0, source='bootstrap_equal'.
The correlation-derived weight pass (src/analysis/weight_derivation.py) will
upsert over these later.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingestion"))

from db import get_connection


SECTORS = [
    # (sort_order, sector_id, label, sector_group)
    (10,  "asset_management",                            "Asset Management",                              "pe"),
    (20,  "business_services",                           "Business Services",                             "both"),
    (30,  "employee_benefits_and_hcm",                   "Employee Benefits & Human Capital Management",  "pe"),
    (40,  "health_insurance_and_workers_comp_services",  "Health Insurance & Workers' Comp. Services",    "pe"),
    (50,  "insurance_distribution",                      "Insurance Distribution",                        "pe"),
    (60,  "insurance_services",                          "Insurance Services",                            "pe"),
    (70,  "insurance_underwriting",                      "Insurance Underwriting",                        "pe"),
    (80,  "lending_and_markets",                         "Lending & Markets",                             "pe"),
    (90,  "real_estate_finance_and_services",            "Real Estate Finance & Services",                "pe"),
    (100, "wealth_management_and_fund_administration",   "Wealth Management & Fund Administration",       "pe"),
    (110, "financial_services",                          "Financial Services",                            "credit"),
    (120, "software_and_technology",                     "Software & Technology",                         "credit"),
    (130, "healthcare_services",                         "Healthcare Services",                           "credit"),
]

# All 10 scoring indicators (raw FRED ids + 2 virtual spreads computed in compute.py).
# DFF/SOFR/TERMCBCCALLNS/FEDFUNDS are inputs to spreads, not scored directly.
INDICATORS = [
    "TOTCI",
    "DFF_SOFR_SPREAD",
    "CC_SPREAD",
    "DRCCLACBS",
    "DRCLACBS",
    "DRCRELEXFACBS",
    "BAMLC0A0CM",
    "BAMLH0A0HYM2",
]


def main() -> None:
    conn = get_connection()
    cur = conn.cursor()

    cur.executemany(
        """
        INSERT INTO sectors (sort_order, sector_id, label, sector_group)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (sector_id) DO NOTHING
        """,
        SECTORS,
    )

    rows = [
        (sid, sec[1], 1.0, "bootstrap_equal")
        for sec in SECTORS
        for sid in INDICATORS
    ]
    cur.executemany(
        """
        INSERT INTO indicator_sector_map (series_id, sector_id, weight, weight_source)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (series_id, sector_id) DO NOTHING
        """,
        rows,
    )

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM sectors")
    n_sectors = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM indicator_sector_map")
    n_map = cur.fetchone()[0]
    print(f"sectors: {n_sectors} rows, indicator_sector_map: {n_map} rows")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
