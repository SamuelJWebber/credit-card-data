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
