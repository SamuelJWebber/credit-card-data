"""The command line: `carddash check` grades only what the nightly run grades (REVIEW.md R1-6)."""

from __future__ import annotations

import pandas as pd

from carddash.cli import cmd_check
from carddash.loader import write_facts


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
