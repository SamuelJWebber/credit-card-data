"""Every golden number must be reproduced from the checked-in fixtures."""

from __future__ import annotations

import pandas as pd

from carddash.golden import MIN_LIVE_AGE_MONTHS, check_golden, load_golden, months_between
from conftest import REPO


def test_live_entries_sit_outside_their_sources_revision_window(fixture_facts):
    """A live entry on a period the next routine release revises turns its source amber for no reason (REVIEW.md
    R1-4: the two BEA entries for July and August 2026 would have gone amber with the October release). The fixture
    is the release each entry was copied from, so its newest period is the reference."""
    newest = fixture_facts.groupby(["metric", "entity", "tier", "period_type", "source"])["period_end"].max()
    too_young = []
    for e in load_golden(REPO / "checks" / "golden.yaml"):
        if not e.get("check_live", True):
            continue
        need = MIN_LIVE_AGE_MONTHS.get((e["source"], e["period_type"]), 0)
        last = newest.get((e["metric"], e["entity"], e.get("tier", "all"), e["period_type"], e["source"]))
        assert last is not None, f"{e['id']}: its series is not in the fixtures"
        age = months_between(pd.Timestamp(str(e["period_end"])), last)
        if age < need:
            too_young.append(f"{e['id']}: {age} month(s) behind {last.date()}, needs {need}")
    assert not too_young, "\n".join(too_young)


def test_bea_live_anchor_predates_the_observed_wage_census_revision_window():
    newest = pd.Timestamp("2026-10-31")
    required_age = MIN_LIVE_AGE_MONTHS[("bea", "M")]
    assert months_between(pd.Timestamp("2026-04-30"), newest) < required_age
    assert months_between(pd.Timestamp("2026-01-31"), newest) >= required_age


def test_numbers_are_stated_to_the_decimals_they_were_copied_with():
    from carddash.golden import golden_decimals, number_text

    cases = {(1347.7, 0.06): "1,347.7", (1297.0, 0.06): "1,297.0", (119.8, 0.0006): "119.800", (137.0, 0.6): "137",
             (15.0, 0.0): "15", (14131.9, 0.11): "14,131.9", (1189601.0, 0.5): "1,189,601"}
    for (value, tol), text in cases.items():
        assert number_text(value, golden_decimals(value, tol)) == text


def test_every_result_says_whether_it_is_live(fixture_facts):
    entries = load_golden(REPO / "checks" / "golden.yaml")
    results = check_golden(fixture_facts, entries)
    assert [r["live"] for r in results] == [bool(e.get("check_live", True)) for e in entries]
    assert len(check_golden(fixture_facts, entries, live_only=True)) == sum(r["live"] for r in results)


def test_every_golden_cites_a_dated_page_not_one_that_moves():
    """REVIEW.md R1-11: thirteen G.19 entries linked /releases/g19/current/ and the census entries marts_current.pdf,
    pages that stop showing the cited number one release later. Each now links the dated copy of the release it
    names (checks/verify_g19.py --provenance re-reads the G.19 ones). The NY Fed keeps no dated copy of the SCE
    credit access page; its two entries link the Internet Archive's copy of 2026-10-08, which states both numbers.
    There is no exception left."""
    import re

    moving = re.compile(r"/current/|_current\.|/latest\b")
    bad = []
    for e in load_golden(REPO / "checks" / "golden.yaml"):
        url = e.get("origin_url", "")
        if url.startswith("https://web.archive.org/web/"):
            if not re.match(r"https://web\.archive\.org/web/\d{14}/https?://", url):
                bad.append(f"{e['id']}: an archive link must name its snapshot time")
        elif moving.search(url) or url.rstrip("/").endswith("/sce/credit-access"):
            bad.append(f"{e['id']}: {url}")
    assert not bad, "\n".join(bad)


def test_every_sec_link_names_a_document_its_filing_holds():
    """REVIEW.md R2-3: the entry that pins Capital One's Discover-merger month linked accession 0000927628-25-000212,
    a 404; the exhibit is in 0000927628-25-000241, filed 2025-07-22. issuer_8k caches every filing index it reads
    under data/raw/issuer_8k/index/ (a filed document list never changes), so this needs no network."""
    import json
    import re

    from carddash.fetchers.issuer_8k import ISSUERS

    archives = {i.archive.rstrip("/") for i in ISSUERS}
    index_dir = REPO / "data" / "raw" / "issuer_8k" / "index"
    bad, seen = [], 0
    for e in load_golden(REPO / "checks" / "golden.yaml"):
        url = e.get("origin_url", "")
        if "sec.gov/Archives" not in url:
            continue
        seen += 1
        m = re.fullmatch(r"(https://www\.sec\.gov/Archives/edgar/data/\d+)/(\d{18})/([^/]+)", url)
        if not m:
            bad.append(f"{e['id']}: not an EDGAR document link: {url}")
            continue
        archive, accession, document = m.groups()
        if archive not in archives:
            bad.append(f"{e['id']}: {archive} is none of the issuers' archives")
        index = index_dir / f"{accession}.json"
        if not index.exists():
            bad.append(f"{e['id']}: no filing {accession} among the {len(list(index_dir.glob('*.json')))} indexes issuer_8k has read")
        elif document not in json.loads(index.read_text(encoding="utf-8")):
            bad.append(f"{e['id']}: filing {accession} holds no {document}")
    assert seen >= 13, "the SEC entries went missing"
    assert not bad, "\n".join(bad)


def test_an_entry_that_names_a_file_links_that_file():
    """REVIEW.md R2-3: two BEA entries quoted the release's Historical Comparisons workbook (pi0926-hist.xlsx) but
    linked the news page, which states neither number."""
    import re

    bad = []
    for e in load_golden(REPO / "checks" / "golden.yaml"):
        for name in re.findall(r"\b[\w.-]+\.(?:xlsx|xls|pdf|csv|zip|txt)\b", str(e.get("origin", ""))):
            if not e.get("origin_url", "").endswith("/" + name):
                bad.append(f"{e['id']}: cites {name} but links {e.get('origin_url')}")
    assert not bad, "\n".join(bad)


def test_every_source_with_a_golden_keeps_a_live_one():
    """Retiring revised entries must not leave a source with nothing checked on the nightly run."""
    entries = load_golden(REPO / "checks" / "golden.yaml")
    sources = {e["source"] for e in entries}
    live = {e["source"] for e in entries if e.get("check_live", True)}
    assert sources == live, f"no live entry left for {sorted(sources - live)}"


def test_all_golden_entries_pass_on_fixtures(fixture_facts):
    entries = load_golden(REPO / "checks" / "golden.yaml")
    assert entries, "golden.yaml is empty"
    results = check_golden(fixture_facts, entries, live_only=False)
    failures = [r["message"] for r in results if not r["ok"]]
    assert not failures, "\n".join(failures)


def test_golden_reports_missing_period(fixture_facts):
    entry = {
        "id": "missing", "metric": "revolving_credit_sa", "entity": "ALL_HOLDERS", "tier": "all",
        "period_type": "M", "period_end": "2099-01-31", "source": "fred", "expected": 1.0,
    }
    (r,) = check_golden(fixture_facts, [entry])
    assert not r["ok"] and "no value" in r["message"]
