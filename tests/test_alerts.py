"""Saying it out loud: how long each source has held its status, and which have been amber for a week (R1-3)."""

from __future__ import annotations

import datetime as dt
import json

from carddash import cli
from carddash.alerts import needing_attention, stamp_status_since
from carddash.loader import SourceHealth

NOW = dt.datetime(2026, 11, 9, 22, 0, tzinfo=dt.timezone.utc)


def _h(name, status, since=None, messages=()):
    return SourceHealth(source=name, status=status, status_since=since, messages=list(messages))


def test_status_since_holds_while_the_status_holds_and_restarts_when_it_changes():
    health = {"bea": _h("bea", "golden_mismatch"), "fred": _h("fred", "ok"), "fdic": _h("fdic", "failed"),
              "new": _h("new", "ok")}
    before = {"bea": ("golden_mismatch", "2026-10-03T01:00:00Z"), "fred": ("ok", "2026-09-01T00:00:00Z"),
              "fdic": ("ok", "2026-09-01T00:00:00Z")}
    stamp_status_since(health, before, "2026-11-09T22:00:00Z")
    assert health["bea"].status_since == "2026-10-03T01:00:00Z"  # still amber: the clock keeps running
    assert health["fred"].status_since == "2026-09-01T00:00:00Z"
    assert health["fdic"].status_since == "2026-11-09T22:00:00Z"  # ok -> failed: a new episode
    assert health["new"].status_since == "2026-11-09T22:00:00Z"  # first time seen
    # a health.json written before status_since existed starts the clock now
    old = {"census": _h("census", "stale")}
    stamp_status_since(old, {"census": ("stale", None)}, "2026-11-09T22:00:00Z")
    assert old["census"].status_since == "2026-11-09T22:00:00Z"


def test_only_amber_sources_older_than_a_week_need_attention():
    """Red fails the job and opens the failure issue; amber shows as success in the Actions UI, which is how bea and
    census sat amber from early October 2026 without anyone noticing."""
    health = {
        "bea": _h("bea", "golden_mismatch", "2026-10-03T01:39:00Z",
                  ["golden check failed: bea_pce_change_2026_06: got 68.3, expected 77.4 +/-0.06 (...)"]),
        "census": _h("census", "golden_mismatch", "2026-09-30T02:14:00Z"),
        "tccp": _h("tccp", "stale", "2026-11-05T00:00:00Z"),  # amber, but for four days only
        "fdic": _h("fdic", "failed", "2026-10-08T00:00:00Z"),  # red: the failure issue covers it
        "fred": _h("fred", "ok", "2026-09-01T00:00:00Z"),
    }
    lines = needing_attention(health, NOW, days=7)
    assert len(lines) == 2
    assert lines[0].startswith("- **census** has been `golden_mismatch` since 2026-09-30 (40 days)")
    assert lines[1].startswith("- **bea** has been `golden_mismatch` since 2026-10-03 (37 days): golden check failed")
    assert needing_attention({"fred": health["fred"]}, NOW) == []


def test_the_attention_message_never_carries_a_secret(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "fake0key0for0tests0only0abcdef12")
    health = {"fred": _h("fred", "stale", "2026-10-01T00:00:00Z", ["url ...?api_key=fake0key0for0tests0only0abcdef12"])}
    (line,) = needing_attention(health, NOW)
    assert "fake0key" not in line and "api_key=[redacted]" in line


def test_health_json_round_trips_status_since_and_attention_reads_it(tmp_paths, capsys):
    """Through the command line: health.json carries status_since, and `carddash attention` prints the sources amber
    for at least --days and nothing else."""
    tmp_paths.data.mkdir(parents=True)
    doc = {"generated_at": "2026-11-09T22:00:00Z", "sources": {
        "bea": {"source": "bea", "status": "golden_mismatch", "messages": ["golden check failed: x"],
                "status_since": "2026-10-03T01:39:00Z"},
        "fred": {"source": "fred", "status": "ok", "messages": [], "status_since": "2026-09-01T00:00:00Z"}}}
    tmp_paths.health_json.write_text(json.dumps(doc), encoding="utf-8")
    health = cli.read_health(tmp_paths)
    assert health["bea"].status_since == "2026-10-03T01:39:00Z"
    cli.write_health(tmp_paths, health, "2026-11-09T22:00:00Z")
    assert json.loads(tmp_paths.health_json.read_text(encoding="utf-8"))["sources"]["bea"]["status_since"] == "2026-10-03T01:39:00Z"
    assert cli.cmd_attention(tmp_paths, 7) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1 and out[0].startswith("- **bea** has been `golden_mismatch` since 2026-10-03")


def test_a_refresh_run_starts_and_keeps_the_clock(tmp_paths, monkeypatch, capsys):
    """cmd_refresh stamps status_since on every source it writes: a source that turns red starts a new clock, and
    the next run that finds it still red keeps the first stamp."""
    tmp_paths.data.mkdir(parents=True)
    doc = {"generated_at": "2026-11-01T00:00:00Z", "sources": {
        "fakesrc": {"source": "fakesrc", "status": "ok", "messages": [], "status_since": "2026-09-01T00:00:00Z"}}}
    tmp_paths.health_json.write_text(json.dumps(doc), encoding="utf-8")

    class Fake:  # a source with no series.csv rows fails before it fetches anything
        @staticmethod
        def fetch(meta, raw_dir, session, pulled_at):
            raise AssertionError("never called")

    monkeypatch.setattr(cli, "FETCHERS", {"fakesrc": Fake})
    monkeypatch.setattr(cli, "check_golden", lambda *a, **k: [])
    assert cli.cmd_refresh(tmp_paths, ["fakesrc"], do_render=False) == 0
    first = json.loads(tmp_paths.health_json.read_text(encoding="utf-8"))["sources"]["fakesrc"]
    assert first["status"] == "failed" and first["status_since"] == json.loads(
        tmp_paths.health_json.read_text(encoding="utf-8"))["generated_at"]
    # as though that first failure had been a week ago: the next run must keep its stamp, not restart it
    doc = json.loads(tmp_paths.health_json.read_text(encoding="utf-8"))
    doc["sources"]["fakesrc"]["status_since"] = "2026-11-01T00:00:00Z"
    tmp_paths.health_json.write_text(json.dumps(doc), encoding="utf-8")
    assert cli.cmd_refresh(tmp_paths, ["fakesrc"], do_render=False) == 0
    second = json.loads(tmp_paths.health_json.read_text(encoding="utf-8"))["sources"]["fakesrc"]
    assert second["status"] == "failed" and second["status_since"] == "2026-11-01T00:00:00Z"
