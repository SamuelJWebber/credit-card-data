"""How the page and the alerts name each source.

SOURCE_LABELS is the full name, for the health list, the Sources line and the browser's filter. SOURCE_SHORT is
for any line that names a source in passing: the failure banner, the "Due in the next two weeks" line and the
attention issue. Those lines used to cut the full label at its first comma, so a failed issuer_8k read
"Capital One" and the three New York Fed sources all read "Federal Reserve Bank of New York" (REVIEW.md R2-6).
tests/test_render.py requires a distinct short name for every source.
"""

from __future__ import annotations

SOURCE_LABELS = {
    "fred": "FRED, Federal Reserve Bank of St. Louis",  # each series is credited to its publisher (series.csv)
    "tccp": "CFPB Terms of Credit Card Plans survey",
    "phillyfed": "Federal Reserve Bank of Philadelphia, Large Bank Credit Card and Mortgage Data (FR Y-14M)",
    "nyfed_hhdc": "Federal Reserve Bank of New York, Quarterly Report on Household Debt and Credit (Consumer Credit Panel/Equifax)",
    "fdic": "FDIC, Call Report data via the BankFind Suite API",
    "nyfed_sce": "Federal Reserve Bank of New York, Survey of Consumer Expectations Credit Access Survey",
    "nyfed_sce_monthly": "Federal Reserve Bank of New York, Survey of Consumer Expectations (monthly)",
    "bea": "Bureau of Economic Analysis, personal consumption expenditures by type of product (NIPA monthly)",
    "census": "Census Bureau, Monthly Retail Trade Survey",
    "ncua": "NCUA, 5300 Call Report quarterly data (credit unions)",
    "dfa": "Federal Reserve Board, Distributional Financial Accounts",
    "cfpb_cct": "CFPB Consumer Credit Trends (Consumer Credit Panel)",
    "issuer_8k": "Capital One, Synchrony, Bread Financial and American Express, each issuer's own monthly charge-off and delinquency metrics (8-K filings, SEC EDGAR)",
    "nyfed_state": "Federal Reserve Bank of New York, State Level Household Debt Statistics (Consumer Credit Panel/Equifax)",
}

SOURCE_SHORT = {
    "fred": "FRED (Fed and other publishers' series)",
    "tccp": "CFPB card plans survey (TCCP)",
    "phillyfed": "Philadelphia Fed large-bank card data (Y-14M)",
    "nyfed_hhdc": "NY Fed Household Debt and Credit",
    "fdic": "FDIC call reports",
    "nyfed_sce": "NY Fed SCE credit access survey",
    "nyfed_sce_monthly": "NY Fed SCE monthly survey",
    "bea": "BEA personal income and spending",
    "census": "Census monthly retail trade",
    "ncua": "NCUA credit union call reports",
    "dfa": "Fed Distributional Financial Accounts",
    "cfpb_cct": "CFPB Consumer Credit Trends",
    "issuer_8k": "Issuer 8-K filings (Capital One, Synchrony, Bread, Amex)",
    "nyfed_state": "NY Fed state household debt",
}


def short_name(source: str) -> str:
    return SOURCE_SHORT.get(source) or SOURCE_LABELS.get(source) or source
