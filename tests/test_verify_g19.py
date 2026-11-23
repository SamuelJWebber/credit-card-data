"""checks/verify_g19.py against a checked-in G.19 release page (the dated 2026-09-08 release, as published).

The script reads the Fed's own HTML tables, never FRED, so it is the independent check on the G.19 goldens. These
tests run it offline: its parser, the release date it reads, --provenance against the dated page each entry cites,
and the re-based entries --rebase prints when a release has moved a number (REVIEW.md R1-11, improvement 3).
"""

from __future__ import annotations

import datetime as dt
import importlib.util

import pytest
import yaml

from conftest import FIXTURES, REPO

PAGE = (FIXTURES / "g19" / "20260908.htm").read_text(encoding="utf-8")
DATED = "https://www.federalreserve.gov/releases/g19/20260908/default.htm"


@pytest.fixture(scope="module")
def vg():
    spec = importlib.util.spec_from_file_location("verify_g19", REPO / "checks" / "verify_g19.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_page_parses_to_the_numbers_the_goldens_cite(vg):
    tables = vg.parse_tables(PAGE)
    revolving = vg.find_row(tables, "Revolving", "level_sa")
    assert vg._num(revolving["May 2026"]) == 1347.7 and vg._num(revolving["Q1 2026"]) == 1338.2
    assert vg._num(vg.find_row(tables, "Depository institutions", "holder_revolving")["Jun 2026"]) == 1206.0
    assert vg.release_date(PAGE) == dt.date(2026, 9, 8)


class _Pages:
    """make_session() stand-in: serves one page, by default the checked-in release, for every URL."""

    def __init__(self, text=PAGE, status=200):
        self.urls, self.text, self.status = [], text, status

    def get(self, url):
        self.urls.append(url)

        class R:
            text = self.text
            content = self.text.encode("utf-8")
            status_code = self.status

        return R()


def _run(vg, monkeypatch, tmp_path, entries, *args, pages=None):
    root = tmp_path / "repo"
    (root / "checks").mkdir(parents=True, exist_ok=True)
    (root / "checks" / "golden.yaml").write_text(yaml.safe_dump(entries, sort_keys=False), encoding="utf-8")
    pages = pages or _Pages()
    monkeypatch.setattr(vg, "make_session", lambda: pages)
    monkeypatch.setattr(vg, "load_dotenv", lambda path: None)
    monkeypatch.setattr(vg, "__file__", str(root / "checks" / "verify_g19.py"))
    return vg.main(list(args)), pages


ENTRY = {"id": "g19_revolving_sa_2026_05", "metric": "revolving_credit_sa", "entity": "ALL_HOLDERS", "tier": "all",
         "period_type": "M", "period_end": "2026-05-31", "source": "fred", "expected": 1347.7, "tolerance": 0.06,
         "check_live": False, "origin": "Fed G.19 release of 2026-09-08, Revolving, SA, 'May 2026' column",
         "origin_url": DATED}


def test_provenance_reads_each_entry_off_the_page_it_cites(vg, monkeypatch, tmp_path, capsys):
    code, pages = _run(vg, monkeypatch, tmp_path, [ENTRY], "--provenance")
    assert code == 0 and pages.urls == [DATED]
    assert "PASS g19_revolving_sa_2026_05: page 1347.7 vs golden 1347.7 (column May 2026, 20260908)" in capsys.readouterr().out
    wrong = {**ENTRY, "expected": 1344.3}  # what the 2026-08-07 release printed for May
    assert _run(vg, monkeypatch, tmp_path, [wrong], "--provenance")[0] == 1


def test_rebase_prints_the_entry_with_the_current_value_and_its_dated_page(vg, monkeypatch, tmp_path, capsys):
    stale = {**ENTRY, "expected": 1344.3, "origin": "Fed G.19 release of 2026-08-07, Revolving, SA, 'May 2026' column",
             "origin_url": "https://www.federalreserve.gov/releases/g19/20260807/default.htm"}
    code, _ = _run(vg, monkeypatch, tmp_path, [stale], "--rebase")
    out = capsys.readouterr().out
    assert code == 1 and "FAIL g19_revolving_sa_2026_05: page 1347.7 vs golden 1344.3" in out
    (candidate,) = yaml.safe_load(out.split("# inside the revision window")[1].split("\n", 1)[1])
    assert candidate["expected"] == 1347.7 and candidate["origin_url"] == DATED
    assert candidate["origin"].startswith("Fed G.19 release of 2026-09-08, 'May 2026' column (1344.3 in the 2026-08-07")
    assert {k: v for k, v in candidate.items() if k not in ("expected", "origin", "origin_url")} == {
        k: v for k, v in stale.items() if k not in ("expected", "origin", "origin_url")}
    # nothing to re-base when everything matches
    code, _ = _run(vg, monkeypatch, tmp_path, [ENTRY], "--rebase")
    assert code == 0 and "Re-based entries" not in capsys.readouterr().out


DENIED = "<html><head><title>Access Denied</title></head><body><h1>Access Denied</h1></body></html>"


@pytest.mark.parametrize("mode", [[], ["--rebase"], ["--provenance"]])
def test_a_page_that_did_not_load_is_an_error_in_every_mode(vg, monkeypatch, tmp_path, capsys, mode):
    """REVIEW.md R2-4: a 403 'Access Denied' page parsed to no tables, every entry was skipped, and the default and
    --rebase modes printed "all checked entries match the current release page" and exited 0."""
    code, _ = _run(vg, monkeypatch, tmp_path, [ENTRY], *mode, pages=_Pages(DENIED, status=403))
    out = capsys.readouterr().out
    assert code == 1 and "all checked entries match" not in out
    assert "answered HTTP 403, not 200" in out


@pytest.mark.parametrize("mode", [[], ["--rebase"], ["--provenance"]])
def test_a_200_page_that_is_not_a_release_is_an_error(vg, monkeypatch, tmp_path, capsys, mode):
    code, _ = _run(vg, monkeypatch, tmp_path, [ENTRY], *mode, pages=_Pages(DENIED.replace("Access Denied", "Maintenance")))
    out = capsys.readouterr().out
    assert code == 1 and "carries no 'Release Date'" in out and "all checked entries match" not in out


def test_a_release_whose_tables_did_not_parse_checks_nothing_and_says_so(vg, monkeypatch, tmp_path, capsys):
    bare = "<p>Release Date: September 8, 2026</p>"  # a release page whose layout this parser no longer reads
    code, _ = _run(vg, monkeypatch, tmp_path, [ENTRY], pages=_Pages(bare))
    out = capsys.readouterr().out
    assert code == 1 and "MISSING g19_revolving_sa_2026_05: no 'Revolving' row on the current page" in out
    assert "0 checked (0 PASS, 0 FAIL), 0 aged off the page, 1 missing" in out
    assert "0 entries checked: nothing was compared" in out


def test_a_month_that_aged_off_the_page_is_skipped_and_a_column_that_vanished_is_not(vg, monkeypatch, tmp_path, capsys):
    """The page prints only its last three months; an older month is expected to be gone. A month the page should
    print and does not is a layout problem, and fails."""
    older = {**ENTRY, "id": "g19_revolving_sa_2026_02", "period_end": "2026-02-28", "expected": 1320.0}
    code, _ = _run(vg, monkeypatch, tmp_path, [ENTRY, older])
    out = capsys.readouterr().out
    assert code == 0 and "SKIP g19_revolving_sa_2026_02: Feb 2026 is older than the page's oldest month (May 2026)" in out
    assert "1 checked (1 PASS, 0 FAIL), 1 aged off the page, 0 missing" in out
    no_july = PAGE.replace(">Jul<", ">Xyz<")  # the July column is gone though May and June are there
    july = {**ENTRY, "id": "g19_revolving_sa_2026_07", "period_end": "2026-07-31", "expected": 1352.6}
    code, _ = _run(vg, monkeypatch, tmp_path, [ENTRY, july], pages=_Pages(no_july))
    out = capsys.readouterr().out
    assert code == 1 and "MISSING g19_revolving_sa_2026_07: none of ['Jul 2026'], though the page runs from May 2026" in out


def _dec_g19_page(revolving_oct="1,375.2", release="December 7, 2026", apr_q3="22.40") -> str:
    """Minimal synthetic December 2026 Fed G.19 HTML release page matching real table layout."""
    return f"""<html><body>
<div>Release Date<sup><a href="#date1">*</a></sup>: <span>{release}</span></div>
<table>
<tr><th></th><th colspan="3">Annual</th><th colspan="2">2025</th><th colspan="6">2026</th></tr>
<tr><th></th><th>2023</th><th>2024</th><th>2025</th><th>Q3</th><th>Q4</th><th>Q1</th><th>Q2</th><th>Q3</th><th>Aug</th><th>Sep r</th><th>Oct p</th></tr>
<tr><td>Total percent change</td><td>1.0</td><td>1.0</td><td>1.0</td><td>1.0</td><td>1.0</td><td>1.0</td><td>1.0</td><td>1.0</td><td>1.0</td><td>1.0</td><td>1.0</td></tr>
<tr><td>Revolving</td><td>1.0</td><td>1.0</td><td>1.0</td><td>1.0</td><td>1.0</td><td>1.0</td><td>1.0</td><td>1.0</td><td>1.0</td><td>1.0</td><td>1.0</td></tr>
<tr><td>Total outstanding</td><td>5000.0</td><td>5100.0</td><td>5200.0</td><td>5150.0</td><td>5200.0</td><td>5210.0</td><td>5220.0</td><td>5240.0</td><td>5230.0</td><td>5240.0</td><td>5250.0</td></tr>
<tr><td>Revolving</td><td>1250.0</td><td>1297.0</td><td>1325.1</td><td>1312.7</td><td>1325.1</td><td>1338.2</td><td>1354.5</td><td>1368.5</td><td>1362.0</td><td>1368.5</td><td>{revolving_oct}</td></tr>
<tr><td>All accounts</td><td>21.00</td><td>21.50</td><td>21.20</td><td>21.10</td><td>21.20</td><td>21.00</td><td>20.94</td><td>21.19</td><td>n.a.</td><td>n.a.</td><td>n.a.</td></tr>
<tr><td>Accounts assessed interest</td><td>22.10</td><td>22.80</td><td>22.30</td><td>22.83</td><td>22.30</td><td>21.52</td><td>22.15</td><td>{apr_q3}</td><td>n.a.</td><td>n.a.</td><td>n.a.</td></tr>
</table>
</body></html>"""


def test_dec_g19_rebase_updates_revised_entries_and_fails_closed_on_missing_or_excess_skips(vg, monkeypatch, tmp_path, capsys):
    dec_page = _dec_g19_page()
    dec_2025 = {**ENTRY, "id": "g19_revolving_sa_2025_12", "period_end": "2025-12-31", "expected": 1324.3,
                "check_live": True, "origin": "Fed G.19 release of 2026-09-08, '2025' column",
                "origin_url": DATED}
    apr_q3 = {"id": "g19_card_apr_assessed_2026_q3", "metric": "card_apr_assessed_interest", "entity": "COMBANKS_ALL",
              "tier": "all", "period_type": "Q", "period_end": "2026-09-30", "source": "fred", "expected": 22.36,
              "tolerance": 0.006, "check_live": True, "origin": "Fed G.19 release of 2026-11-06, 'Q3 2026' column",
              "origin_url": "https://www.federalreserve.gov/releases/g19/20261106/default.htm"}

    # Clean Dec rebase prints candidates citing 20261207 and keeps exit code 1 (mismatches present)
    code, _ = _run(vg, monkeypatch, tmp_path, [dec_2025, apr_q3], "--rebase", pages=_Pages(dec_page))
    out = capsys.readouterr().out
    assert code == 1 and "2 mismatch(es)" in out
    cands = yaml.safe_load(out.split("# inside the revision window")[1].split("\n", 1)[1])
    assert [c["id"] for c in cands] == ["g19_revolving_sa_2025_12", "g19_card_apr_assessed_2026_q3"]
    assert cands[0]["expected"] == 1325.1 and cands[0]["origin_url"].endswith("/releases/g19/20261207/default.htm")
    assert cands[1]["expected"] == 22.4

    # Fail-closed #1: if any entry is MISSING in --rebase mode, exit 1 and NEVER print re-based candidates
    missing_holder = {**dec_2025, "id": "g19_depository", "metric": "revolving_credit_nsa",
                      "entity": "DEPOSITORY_INSTITUTIONS"}
    code, _ = _run(vg, monkeypatch, tmp_path, [dec_2025, missing_holder], "--rebase", pages=_Pages(dec_page))
    out = capsys.readouterr().out
    assert code == 1 and "MISSING g19_depository" in out and "Re-based entries" not in out

    # Fail-closed #2: if more entries aged off than were checked (aged > checked), exit 1 and suppress candidates
    aged_may = {**ENTRY, "id": "g19_revolving_sa_2026_05", "period_end": "2026-05-31"}
    aged_jul = {**ENTRY, "id": "g19_revolving_sa_2026_07", "period_end": "2026-07-31"}
    code, _ = _run(vg, monkeypatch, tmp_path, [dec_2025, aged_may, aged_jul], "--rebase", pages=_Pages(dec_page))
    out = capsys.readouterr().out
    assert code == 1 and "too many entries aged off the page (2 skipped vs 1 checked)" in out
    assert "Re-based entries" not in out


def test_malformed_fed_responses_and_bad_cli_flags_fail_closed(vg, monkeypatch, tmp_path, capsys):
    import requests

    # Network error / timeout
    class _FailingSession:
        def get(self, url):
            raise requests.ReadTimeout("timed out")

    code, _ = _run(vg, monkeypatch, tmp_path, [ENTRY], pages=_FailingSession())
    assert code == 1 and "ERROR could not fetch" in capsys.readouterr().out

    # HTTP 200 empty body
    code, _ = _run(vg, monkeypatch, tmp_path, [ENTRY], pages=_Pages("", status=200))
    assert code == 1 and "empty body" in capsys.readouterr().out

    # HTTP 200 with invalid calendar Release Date (must not crash with uncaught ValueError)
    bad_date_page = _dec_g19_page(release="February 30, 2026")
    for mode in ([], ["--rebase"], ["--provenance"]):
        code, _ = _run(vg, monkeypatch, tmp_path, [ENTRY], *mode, pages=_Pages(bad_date_page))
        out = capsys.readouterr().out
        assert code == 1 and "carries no 'Release Date'" in out and "Re-based entries" not in out

    # Non-finite cell ("NaN", "inf") -> never parses as a float or enters --rebase YAML
    assert vg._num("NaN") is None and vg._num("inf") is None
    nan_page = _dec_g19_page(revolving_oct="NaN", apr_q3="inf")
    oct_entry = {**ENTRY, "id": "g19_revolving_sa_2026_10", "period_end": "2026-10-31", "expected": 1370.0}
    code, _ = _run(vg, monkeypatch, tmp_path, [oct_entry], "--rebase", pages=_Pages(nan_page))
    out = capsys.readouterr().out
    assert code == 1 and "MISSING g19_revolving_sa_2026_10" in out and "Re-based entries" not in out

    # Malformed golden.yaml (empty or non-list) fails closed
    code, _ = _run(vg, monkeypatch, tmp_path, [])
    assert code == 1 and "0 entries checked" in capsys.readouterr().out
    (tmp_path / "repo" / "checks" / "golden.yaml").write_text("not: a_list\n", encoding="utf-8")
    monkeypatch.setattr(vg, "__file__", str(tmp_path / "repo" / "checks" / "verify_g19.py"))
    assert vg.main([]) == 1 and "must be a YAML list" in capsys.readouterr().out

    # Unknown CLI flags or combining --provenance and --rebase fail closed
    for bad_argv in (["--rebas"], ["--provenance", "--rebase"]):
        with pytest.raises(SystemExit) as exc:
            vg.main(bad_argv)
        assert exc.value.code == 2


def test_parse_tables_handles_prefix_row_names_and_uppercase_tags(vg):
    html_upper = (
        "<TABLE><TR><TH></TH><TH COLSPAN=\"2\">2025</TH><TH COLSPAN=\"4\">2026</TH></TR>"
        "<TR><TH></TH><TH>Q3</TH><TH>Q4</TH><TH>Q1</TH><TH>Q2</TH><TH>Sep r</TH><TH>Oct p</TH></TR>"
        "<TR><TD>Total outstanding</TD><TD>1</TD><TD>2</TD><TD>3</TD><TD>4</TD><TD>5</TD><TD>6</TD></TR>"
        "<TR><TD>Total</TD><TD>10</TD><TD>20</TD><TD>30</TD><TD>40</TD><TD>50</TD><TD>60</TD></TR>"
        "<TR><TD>Total</TD><TD>11</TD><TD>21</TD><TD>31</TD><TD>41</TD><TD>51</TD><TD>61</TD></TR>"
        "</TABLE>"
    )
    tables = vg.parse_tables(html_upper)
    assert len(tables) == 1
    assert "Total" in tables[0] and "Total#1" in tables[0] and "Total#2" not in tables[0]
    assert tables[0]["Total#1"]["Oct 2026"] == "61" and tables[0]["Total#1"]["Sep 2026"] == "51"
