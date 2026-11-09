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
    """make_session() stand-in: serves the checked-in page for the dated URL and for 'current'."""

    def __init__(self):
        self.urls = []

    def get(self, url):
        self.urls.append(url)

        class R:
            text = PAGE

        return R()


def _run(vg, monkeypatch, tmp_path, entries, *args):
    root = tmp_path / "repo"
    (root / "checks").mkdir(parents=True, exist_ok=True)
    (root / "checks" / "golden.yaml").write_text(yaml.safe_dump(entries, sort_keys=False), encoding="utf-8")
    pages = _Pages()
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
