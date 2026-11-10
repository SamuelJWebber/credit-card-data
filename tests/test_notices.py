"""The notices registry (src/carddash/notices.py): every source has a decision, and the notices are the publishers'
own words (REVIEW.md R2-2, improvement 3).

Two licences end the right to use the data automatically on non-compliance: the FRED API Terms of Use and the NY
Fed's Survey of Consumer Expectations licence. The page carried neither notice. These tests read the licence text
out of the checked-in SCE workbooks, so the registry cannot drift from what the NY Fed wrote.
"""

from __future__ import annotations

import re

import openpyxl
import pandas as pd

from carddash.fetchers import FETCHERS
from carddash.notices import CCP_SOURCE, FRED_API, NOTICES, NYFED, SCE, credit, page_notices, png_notices
from carddash.render import SOURCE_LABELS
from conftest import FIXTURES, REPO


def _norm(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").replace("“", "").replace("”", "").split())


def _sheet_text(path, sheet: str) -> str:
    wb = openpyxl.load_workbook(path, read_only=True)
    try:
        cells = [str(v) for row in wb[sheet].iter_rows(values_only=True) for v in row if v is not None]
    finally:
        wb.close()
    return _norm(" ".join(cells))


def test_every_source_has_a_decision_on_its_notices():
    """A new source cannot arrive without one: an entry with no text is the decision that none is needed, and says
    why in `basis`."""
    sources = set(pd.read_csv(REPO / "crosswalks" / "series.csv", usecols=["source"])["source"])
    assert sources == set(FETCHERS) == set(NOTICES) == set(SOURCE_LABELS)
    for source, n in NOTICES.items():
        assert n.terms and n.basis and re.fullmatch(r"\d{4}-\d\d-\d\d", n.read), source
        assert n.terms_url.startswith("https://"), source
        if not n.text:
            assert not n.png and not n.credit, f"{source}: a figure notice without a page notice"


def test_the_fred_api_notice_is_the_one_its_terms_require():
    assert FRED_API == ("This product uses the FRED® API but is not endorsed or certified by the Federal Reserve "
                        "Bank of St. Louis.")
    assert NOTICES["fred"].text == FRED_API and "Place the following notice prominently" in NOTICES["fred"].basis


def test_the_sce_notice_is_the_licence_text_word_for_word():
    """The Disclaimer sheet of the monthly SCE workbook gives the attribution and disclaimer FRBNY requires 'with any
    publication or presentation of SCE data'; its License sheet gives the shorter form for a figure."""
    disclaimer = _sheet_text(FIXTURES / "nyfed_sce_monthly" / "frbny-sce-data.xlsx", "Disclaimer")
    required = re.search(r"presentation of SCE data: (Source: .*? Survey of Consumer Expectations data\.)", disclaimer)
    assert required, "the Data Attribution paragraph has moved"
    assert _norm(SCE.replace("{year}", "2026")) == required.group(1)
    licence = _sheet_text(FIXTURES / "nyfed_sce_monthly" / "frbny-sce-data.xlsx", "License")
    assert f"attribution for the figure or graph: Source: {credit('nyfed_sce')}." in licence
    assert credit("nyfed_sce") == credit("nyfed_sce_monthly") == "Survey of Consumer Expectations, New York Fed"
    # the credit-access workbook asks for the same attribution (its own copy abbreviates the year and the address)
    access = _sheet_text(FIXTURES / "nyfed_sce" / "frbny-sce-credit-access-data.xlsx", "Disclaimer")
    assert ("FRBNY disclaims any responsibility or legal liability for this analysis and interpretation of Survey of "
            "Consumer Expectations data.") in access and "Source: Survey of Consumer Expectations, © 2013-26" in access


def test_the_new_york_fed_notice_follows_its_terms_of_use():
    """Its Terms of Use: include the source identifiers the NY Fed puts on the content, and with no other form given,
    '© [year] Federal Reserve Bank of New York. Content from the New York Fed subject to the Terms of Use at
    newyorkfed.org.'"""
    assert NYFED.replace("{year}", "[year]") in NOTICES["nyfed_hhdc"].basis
    assert NOTICES["nyfed_hhdc"] is NOTICES["nyfed_state"]
    hhdc = _sheet_text(FIXTURES / "nyfed_hhdc" / "HHD_C_Report_2026Q2.xlsx", "Page 4 Data")
    state = _sheet_text(FIXTURES / "nyfed_state" / "area_report_by_year.xlsx", "Cover Sheet").replace(" / ", "/")
    assert CCP_SOURCE.rstrip(".") in hhdc and CCP_SOURCE.rstrip(".") in state


def test_the_page_prints_each_notice_once_with_the_year_of_its_newest_data():
    years = {"fred": 2026, "nyfed_sce": 2026, "nyfed_sce_monthly": 2027, "nyfed_hhdc": 2026}
    out = page_notices(["census", "nyfed_sce_monthly", "nyfed_sce", "fred", "nyfed_hhdc"], years)
    assert [n["text"] for n in out] == [
        FRED_API, SCE.replace("{year}", "2027"), f"{CCP_SOURCE} {NYFED.replace('{year}', '2026')}"]
    assert out[0]["terms_url"] == "https://fred.stlouisfed.org/docs/api/terms_of_use.html"
    assert page_notices(["census", "fdic"], years) == []  # public-domain sources print nothing
    assert "{year}" not in " ".join(n["text"] for n in page_notices(["nyfed_sce"], {}))


def test_a_png_carries_the_notices_of_its_own_sources():
    years = {"nyfed_sce": 2026, "nyfed_hhdc": 2026, "fred": 2026}
    assert png_notices({"fred"}, years) == []
    assert png_notices({"nyfed_sce"}, years) == [SCE.replace("{year}", "2026")]
    assert png_notices({"nyfed_hhdc", "fdic", "fred"}, years) == [NYFED.replace("{year}", "2026")]


def test_the_readme_carries_every_notice():
    readme = _norm((REPO / "README.md").read_text(encoding="utf-8"))
    texts = {n.text for n in NOTICES.values() if n.text}
    rights = pd.read_csv(REPO / "crosswalks" / "series.csv", usecols=["rights"]).dropna()["rights"]
    for text in texts | set(rights):
        pattern = re.escape(_norm(text)).replace(re.escape("{year}"), r"\d{4}")
        assert re.search(pattern, readme), f"README.md lacks: {text}"
