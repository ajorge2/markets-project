"""Public redistribution allowlist; API access is not a redistribution license."""
import os
PUBLIC_SERIES = frozenset({'DFF','FEDFUNDS','SOFR','DRCCLACBS','DRCLACBS','DRCRELEXFACBS','TOTCI','TERMCBCCALLNS','T10Y2Y','DSPI','CPROFIT','COMPUTSA','NFCICREDIT','STLFSI4','CC_SPREAD','DFF_SOFR_SPREAD'})
def licensed_data_enabled():
    return os.getenv('MARKETS_LICENSED_DATA') == 'true'
def public_series_allowed(series_id):
    return series_id in PUBLIC_SERIES or licensed_data_enabled()
