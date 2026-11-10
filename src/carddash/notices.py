"""What each source's publisher requires the page, its PNGs and the README to say (REVIEW.md R2-2, improvement 3).

One entry per source, read from the publisher's own terms on the date in `read`. Two licences end the right to use
the data automatically on non-compliance (the FRED API Terms of Use and the NY Fed's SCE licence), and the page
carried neither notice until 2026-11-10. tests/test_notices.py requires an entry for every source in
crosswalks/series.csv, so a new source cannot arrive without a decision here; an entry with no `text` is that
decision, with the reason in `basis`.

- `text` is printed once in the page's Notices block (and in the README). `{year}` is the year of the newest period
  the page holds for the source, so the line moves with the data, not with the clock.
- `credit`, where the terms prescribe how a FIGURE names the source, replaces the source's name on its charts and
  PNGs ('Source: Survey of Consumer Expectations, New York Fed', the SCE licence's own form for figures).
- `png` is added to the caption of every PNG drawn from the source. A PNG is made to be pasted into a post, where it
  travels without the page and its Notices block.

Per-series copyright lines (Michigan and Bankrate, which FRED redistributes) are in crosswalks/series.csv `rights`,
because they belong to single series, not to a source.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Notice:
    terms: str
    terms_url: str
    read: str
    basis: str
    text: str = ""
    credit: str = ""
    png: str = ""


FRED_API = (
    "This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis."
)
SCE = (
    "Source: Survey of Consumer Expectations, © 2013-{year} Federal Reserve Bank of New York (FRBNY). The SCE data "
    "are available without charge at http://www.newyorkfed.org/microeconomics/sce and may be used subject to license "
    "terms posted there. FRBNY disclaims any responsibility or legal liability for this analysis and interpretation "
    "of Survey of Consumer Expectations data."
)
NYFED = "© {year} Federal Reserve Bank of New York. Content from the New York Fed subject to the Terms of Use at newyorkfed.org."
CCP_SOURCE = "Source: New York Fed Consumer Credit Panel/Equifax."

_SCE = Notice(
    terms="Survey of Consumer Expectations licence (the License and Disclaimer sheets of every SCE workbook)",
    terms_url="https://www.newyorkfed.org/microeconomics/sce",
    read="2026-11-10",
    basis="'FRBNY requires the following attribution and disclaimer to be included with any publication or "
          "presentation of SCE data'; a figure in a publication with its own attributions may say 'Source: Survey of "
          "Consumer Expectations, New York Fed.' The licence 'terminates automatically if a user fails to comply'.",
    text=SCE,
    credit="Survey of Consumer Expectations, New York Fed",
    png=SCE,
)
_CCP = Notice(
    terms="New York Fed Terms of Use",
    terms_url="https://www.newyorkfed.org/privacy/termsofuse",
    read="2026-11-10",
    basis="'you must include any copyright notice and other source identifiers that the New York Fed includes with "
          "that Content' (its workbooks say 'Source: New York Fed Consumer Credit Panel/Equifax'), and where no form "
          "of attribution is given, 'follow this format: © [year] Federal Reserve Bank of New York. Content from the "
          "New York Fed subject to the Terms of Use at newyorkfed.org.'",
    text=f"{CCP_SOURCE} {NYFED}",
    png=NYFED,
)
_PUBLIC = ("A work of the U.S. government, in the public domain: no notice is required. Every chart names the agency "
           "and links its release.")

NOTICES: dict[str, Notice] = {
    "fred": Notice(
        terms="FRED® API Terms of Use",
        terms_url="https://fred.stlouisfed.org/docs/api/terms_of_use.html",
        read="2026-11-10",
        basis="Under 'Requirements: You must': 'Place the following notice prominently on your application'. Rights "
              "'terminate automatically' on a violation. Copyrighted series carry their owner's line (series.csv "
              "`rights`). The page links the terms beside the notice; its readers never call the API (the nightly "
              "job does), so the clauses for an application 'for use by other users' are not read as applying.",
        text=FRED_API,
    ),
    "nyfed_sce": _SCE,
    "nyfed_sce_monthly": _SCE,
    "nyfed_hhdc": _CCP,
    "nyfed_state": _CCP,
    "phillyfed": Notice(
        terms="Federal Reserve Bank of Philadelphia, Large Bank Credit Card and Mortgage Data page",
        terms_url="https://www.philadelphiafed.org/surveys-and-data/large-bank-credit-card-and-mortgage-data",
        read="2026-11-10",
        basis="The page suggests a citation (Federal Reserve Bank of Philadelphia, Large Bank Credit Card and "
              "Mortgage Data) and sets no licence. Every chart's source line is that citation.",
    ),
    "dfa": Notice(
        terms="Federal Reserve Board website policies",
        terms_url="https://www.federalreserve.gov/disclaimer.htm",
        read="2026-11-10",
        basis="'information on Board's website is in the public domain and may be copied and distributed without "
              "permission. Please cite to the Board as the source.' Every chart does.",
    ),
    "fdic": Notice(terms="FDIC", terms_url="https://www.fdic.gov/", read="2026-11-10", basis=_PUBLIC),
    "tccp": Notice(terms="CFPB", terms_url="https://www.consumerfinance.gov/", read="2026-11-10", basis=_PUBLIC),
    "cfpb_cct": Notice(terms="CFPB", terms_url="https://www.consumerfinance.gov/", read="2026-11-10", basis=_PUBLIC),
    "bea": Notice(terms="Bureau of Economic Analysis", terms_url="https://www.bea.gov/", read="2026-11-10", basis=_PUBLIC),
    "census": Notice(terms="Census Bureau", terms_url="https://www.census.gov/", read="2026-11-10", basis=_PUBLIC),
    "ncua": Notice(terms="NCUA", terms_url="https://www.ncua.gov/", read="2026-11-10", basis=_PUBLIC),
    "issuer_8k": Notice(
        terms="SEC EDGAR",
        terms_url="https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data",
        read="2026-11-10",
        basis="Public filings. The figures are facts each issuer reports in its own 8-K exhibit, and every chart names "
              "the issuer and links the filing. EDGAR's access rules (a declared User-Agent, a request rate) are met "
              "by the fetcher; they ask for no notice.",
    ),
}


def credit(source: str) -> str:
    """How a figure must name `source`, where its terms prescribe a form; '' otherwise."""
    n = NOTICES.get(source)
    return n.credit if n else ""


def page_notices(sources: Iterable[str], years: dict[str, int]) -> list[dict]:
    """The notices the page prints for the sources it shows, one per distinct text, in NOTICES order.
    `years` maps a source to the year of its newest period (the `{year}` in the text)."""
    wanted = set(sources)
    out: list[dict] = []
    for source, n in NOTICES.items():
        if source not in wanted or not n.text:
            continue
        year = max((years[s] for s in NOTICES if NOTICES[s] is n and s in wanted and s in years), default=None)
        text = n.text.replace("{year}", str(year)) if year else n.text.replace("2013-{year}", "2013").replace("© {year} ", "© ")
        if all(o["text"] != text for o in out):
            out.append({"text": text, "terms": n.terms, "terms_url": n.terms_url})
    return out


def png_notices(sources: Iterable[str], years: dict[str, int]) -> list[str]:
    """The lines a PNG drawn from these sources adds to its caption, one per distinct text."""
    out: list[str] = []
    for source in sorted(set(sources) & set(NOTICES), key=list(NOTICES).index):
        n = NOTICES[source]
        if not n.png:
            continue
        year = years.get(source)
        text = n.png.replace("{year}", str(year)) if year else n.png.replace("2013-{year}", "2013").replace("© {year} ", "© ")
        if text not in out:
            out.append(text)
    return out
