"""The command line: `carddash check` grades only what the nightly run grades (REVIEW.md R1-6), and a refresh in
Actions writes which run it was into health.json (REVIEW.md R2-1)."""

from __future__ import annotations

import json

import pandas as pd

from carddash import cli
from carddash.cli import cmd_check, run_identity
from carddash.loader import write_facts


def test_a_refresh_in_actions_names_its_run_in_health_json(tmp_paths, monkeypatch):
    """checks/verify_releases.py graded a run by the next run's commit when it matched on time alone."""
    assert run_identity({"GITHUB_RUN_ID": "42724326075", "GITHUB_RUN_ATTEMPT": "2", "GITHUB_EVENT_NAME": "schedule"}) \
        == {"id": 42724326075, "attempt": 2, "event": "schedule"}
    assert run_identity({}) is None and run_identity({"GITHUB_RUN_ID": ""}) is None

    class Fake:  # a source with no series.csv rows fails before it fetches anything
        @staticmethod
        def fetch(meta, raw_dir, session, pulled_at):
            raise AssertionError("never called")

    monkeypatch.setattr(cli, "FETCHERS", {"fakesrc": Fake})
    monkeypatch.setattr(cli, "check_golden", lambda *a, **k: [])
    for name, value in (("GITHUB_RUN_ID", "42724326075"), ("GITHUB_RUN_ATTEMPT", "1"), ("GITHUB_EVENT_NAME", "push")):
        monkeypatch.setenv(name, value)
    assert cli.cmd_refresh(tmp_paths, ["fakesrc"], do_render=False) == 0
    doc = json.loads(tmp_paths.health_json.read_text(encoding="utf-8"))
    assert doc["run"] == {"id": 42724326075, "attempt": 1, "event": "push"}
    assert list(doc) == ["generated_at", "run", "sources"]
    monkeypatch.delenv("GITHUB_RUN_ID")  # a local refresh names no run
    assert cli.cmd_refresh(tmp_paths, ["fakesrc"], do_render=False) == 0
    assert "run" not in json.loads(tmp_paths.health_json.read_text(encoding="utf-8"))


def _set_value(facts: pd.DataFrame, metric: str, entity: str, period_end: str, value: float) -> None:
    hit = (facts["metric"] == metric) & (facts["entity"] == entity) & (facts["period_end"] == pd.Timestamp(period_end))
    assert hit.sum() == 1
    facts.loc[hit, "value"] = value


def test_check_passes_a_healthy_pipeline_and_lists_revised_entries_only_with_all(tmp_paths, fixture_facts, capsys):
    """It used to check the fixture-only entries too and exit 1 on seven of them that later releases had revised,
    which taught whoever ran it to ignore FAIL lines."""
    facts = fixture_facts.copy()
    _set_value(facts, "revolving_credit_sa", "ALL_HOLDERS", "2026-05-31", 1347.8447)  # fixture-only, since revised
    write_facts(facts, tmp_paths.facts_csv)

    assert cmd_check(tmp_paths) == 0
    out = capsys.readouterr().out
    assert "g19_revolving_sa_2026_05" not in out and "FAIL" not in out
    assert " passed, 0 failed (live entries; --all lists the fixture-only ones too)" in out

    assert cmd_check(tmp_paths, include_all=True) == 0
    out = capsys.readouterr().out
    assert "REVISED g19_revolving_sa_2026_05: got 1,347.84, expected 1,347.7 +/-0.06" in out
    assert ", 0 failed, 1 revised since first published (fixture-only, not counted as failures)" in out


def test_check_still_fails_on_a_live_mismatch(tmp_paths, fixture_facts, capsys):
    facts = fixture_facts.copy()
    _set_value(facts, "revolving_credit_sa", "ALL_HOLDERS", "2025-12-31", 1325.0)  # live entry: 1324.3
    write_facts(facts, tmp_paths.facts_csv)
    for include_all in (False, True):
        assert cmd_check(tmp_paths, include_all=include_all) == 1
        out = capsys.readouterr().out
        assert "FAIL    g19_revolving_sa_2025_12: got 1,325.00, expected 1,324.3 +/-0.06" in out
        assert ", 1 failed" in out
