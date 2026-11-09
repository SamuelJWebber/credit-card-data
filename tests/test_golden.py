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


def test_the_revision_window_rule_rejects_a_bea_month_of_the_newest_quarter():
    assert MIN_LIVE_AGE_MONTHS[("bea", "M")] >= 4  # September newest: July and August are inside, April is not
    assert months_between(pd.Timestamp("2026-07-31"), pd.Timestamp("2026-09-30")) == 2
    assert months_between(pd.Timestamp("2026-04-30"), pd.Timestamp("2026-09-30")) == 5


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
