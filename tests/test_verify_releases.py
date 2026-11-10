"""checks/verify_releases.py against the real runs and bot commits of 2026-11-09 (REVIEW.md R2-1).

The script grades the v1 definition of done (two consecutive green scheduled runs), so it must grade each run by
the commit THAT run pushed. These tests replace its one I/O function, `sh` (every gh and git call), with a fake that
serves the GitHub API answers and the git history of two real pairs of runs that the old matching got wrong:

- 42724326075 and 42724802764, push runs created at 23:55 and 23:59 UTC. The first ended at 23:58:19; its window ran
  5 minutes past that, and the second run's commit (health.json generated 00:02:12) fell inside it, so both runs
  were graded by be474c9. The real ffbc225 was all `ok` too; here it carries census `stale`, which is the failure the
  review described: a run that ended amber graded GREEN by the next run's all-`ok` commit.
- 42682387939 and 42682400793, a push run and a workflow_dispatch run both created at 19:20 UTC. The dispatch run
  queued behind the push run for three minutes, and its created_at and run_started_at both say 19:20:29, the time it
  was queued. Any window that starts there holds both commits.

Timings, shas and stamps are the real ones (gh api .../runs/<id> and .../runs/<id>/jobs; git log; health.json).
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess

import pytest

from conftest import REPO

OK = {s: "ok" for s in ("bea", "census", "fdic", "fred")}


def _run(rid, event, created, updated, conclusion="success", attempt=1):
    return {"id": rid, "event": event, "status": "completed", "conclusion": conclusion, "run_attempt": attempt,
            "created_at": created, "run_started_at": created, "updated_at": updated}


RUNS = [  # newest first, as the API lists them
    _run(42724802764, "push", "2026-11-09T23:59:26Z", "2026-11-10T00:03:15Z"),
    _run(42724326075, "push", "2026-11-09T23:55:35Z", "2026-11-09T23:58:19Z"),
    _run(42682400793, "workflow_dispatch", "2026-11-09T19:20:29Z", "2026-11-09T19:27:12Z"),
    _run(42682387939, "push", "2026-11-09T19:20:24Z", "2026-11-09T19:23:53Z"),
]
JOBS = {  # the refresh job's started_at and completed_at: when a runner actually ran it
    42724802764: ("2026-11-09T23:59:28Z", "2026-11-10T00:03:15Z"),
    42724326075: ("2026-11-09T23:55:38Z", "2026-11-09T23:58:18Z"),
    42682400793: ("2026-11-09T19:23:55Z", "2026-11-09T19:27:11Z"),
    42682387939: ("2026-11-09T19:20:28Z", "2026-11-09T19:23:52Z"),
}


def _commit(sha, when, generated, statuses=None, body="", run=None):
    health = {"generated_at": generated, "sources": {s: {"status": v} for s, v in (statuses or OK).items()}}
    if run:
        health["run"] = run
    return {"sha": sha, "when": when, "subject": f"refresh: {when[:16]}Z", "body": body, "health": health}


COMMITS = [  # newest first, as git log lists them
    _commit("be474c96903a538d07d017e556166cb14d06b4ef", "2026-11-10T00:03:08Z", "2026-11-10T00:02:12Z"),
    _commit("ffbc225b8fbde9911b263b84cdb4e7357bf102b6", "2026-11-09T23:58:13Z", "2026-11-09T23:57:30Z",
            {**OK, "census": "stale"}),
    _commit("bdf012aee82a2a89355784e1c4088505b5d12666", "2026-11-09T19:27:05Z", "2026-11-09T19:26:12Z"),
    _commit("7ee6579e2e6440b256f2a0027c90fc3400491db4", "2026-11-09T19:23:45Z", "2026-11-09T19:22:50Z",
            {**OK, "fdic": "failed"}),
]


class FakeShell:
    """Answers the gh and git calls verify_releases.py makes, from the tables above."""

    def __init__(self, runs=RUNS, commits=COMMITS, jobs=JOBS):
        self.runs, self.commits, self.jobs, self.calls = runs, commits, jobs, []

    def __call__(self, *args):
        self.calls.append(args)
        if args[:2] == ("git", "fetch"):
            return ""
        if args[:2] == ("git", "log"):
            fmt = next(a for a in args if a.startswith("--format="))[len("--format="):]
            return "".join(self._format(fmt, c) + "\n" for c in self.commits)
        if args[:2] == ("git", "show"):
            sha, _, path = args[2].partition(":")
            for c in self.commits:
                if c["sha"].startswith(sha) and path == "data/health.json":
                    return json.dumps(c["health"])
            raise subprocess.CalledProcessError(128, args)
        if args[0] == "gh":
            path = args[2]
            if path.endswith("/runs"):
                event = next(a.split("=", 1)[1] for a in args if a.startswith("event="))
                return json.dumps({"workflow_runs": [r for r in self.runs if r["event"] == event]})
            m = re.search(r"/runs/(\d+)/jobs$", path)
            if m:
                rid = int(m.group(1))
                if rid not in self.jobs:
                    raise subprocess.CalledProcessError(1, args)
                started, completed = self.jobs[rid]
                return json.dumps({"jobs": [{"name": "refresh", "started_at": started, "completed_at": completed}]})
        raise AssertionError(f"unexpected command {args}")

    @staticmethod
    def _format(fmt: str, c: dict) -> str:
        out = fmt
        for code, value in (("%x1f", "\x1f"), ("%x1e", "\x1e"), ("%x00", "\x00"), ("%H", c["sha"]),
                            ("%cI", c["when"]), ("%s", c["subject"]), ("%b", c["body"])):
            out = out.replace(code, value)
        return out


@pytest.fixture()
def vr():
    spec = importlib.util.spec_from_file_location("verify_releases", REPO / "checks" / "verify_releases.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _lines(out: str) -> dict[int, str]:
    return {int(line.split()[0]): line for line in out.splitlines() if re.match(r"\d{8,} ", line)}


def test_each_run_is_graded_by_its_own_commit(vr, monkeypatch, capsys):
    monkeypatch.setattr(vr, "sh", FakeShell())
    assert vr.main(["--event", "push", "--limit", "4", "--need", "1"]) == 0
    lines = _lines(capsys.readouterr().out)
    assert " be474c9 GREEN" in lines[42724802764]
    # the old window credited this run with be474c9, the next run's all-ok commit, and called it GREEN
    assert " ffbc225 not green" in lines[42724326075] and "census=stale" in lines[42724326075]
    assert " 7ee6579 not green" in lines[42682387939] and "fdic=failed" in lines[42682387939]


def test_a_run_that_queued_behind_another_is_graded_by_its_own_commit(vr, monkeypatch, capsys):
    """created_at and run_started_at are when the run was queued, three minutes before it ran."""
    monkeypatch.setattr(vr, "sh", FakeShell())
    assert vr.main(["--event", "workflow_dispatch", "--limit", "1", "--need", "1"]) == 0
    assert " bdf012a GREEN" in _lines(capsys.readouterr().out)[42682400793]


def test_without_the_jobs_api_the_run_window_has_no_slack_and_takes_the_newest_stamp(vr, monkeypatch, capsys):
    monkeypatch.setattr(vr, "sh", FakeShell(jobs={}))
    vr.main(["--event", "push", "--limit", "4", "--need", "1"])
    lines = _lines(capsys.readouterr().out)
    assert " ffbc225 " in lines[42724326075] and " be474c9 " in lines[42724802764]
    assert " 7ee6579 " in lines[42682387939]
    vr.main(["--event", "workflow_dispatch", "--limit", "1", "--need", "1"])
    assert " bdf012a " in _lines(capsys.readouterr().out)[42682400793]


def test_a_commit_that_names_its_run_wins_over_any_window(vr, monkeypatch, capsys):
    """Since 2026-11-10 every bot commit says which run made it (a Run-Id trailer, and "run" in health.json). A rerun
    makes a second commit for the same run id; the attempt decides."""
    runs = [_run(50000000002, "schedule", "2026-11-11T01:30:00Z", "2026-11-11T01:40:00Z", attempt=2),
            _run(50000000001, "schedule", "2026-11-10T01:30:00Z", "2026-11-10T01:40:00Z")]
    commits = [
        # attempt 2 of the newer run, committed late: outside every window
        _commit("c" * 40, "2026-11-11T02:30:00Z", "2026-11-11T01:31:00Z",
                body="Run-Id: 50000000002\nRun-Attempt: 2\nEvent: schedule",
                run={"id": 50000000002, "attempt": 2, "event": "schedule"}),
        # attempt 1 of the newer run, amber, inside the newer run's window
        _commit("b" * 40, "2026-11-11T01:35:00Z", "2026-11-11T01:32:00Z", {**OK, "bea": "stale"},
                body="Run-Id: 50000000002\nRun-Attempt: 1\nEvent: schedule"),
        # a commit that names a push run, stamped inside the older scheduled run's window
        _commit("a" * 40, "2026-11-10T01:39:00Z", "2026-11-10T01:35:00Z", {**OK, "fred": "failed"},
                body="Run-Id: 49999999999\nRun-Attempt: 1\nEvent: push"),
        _commit("9" * 40, "2026-11-10T01:38:00Z", "2026-11-10T01:31:00Z",
                body="Run-Id: 50000000001\nRun-Attempt: 1\nEvent: schedule"),
    ]
    monkeypatch.setattr(vr, "sh", FakeShell(runs=runs, commits=commits, jobs={}))
    assert vr.main(["--limit", "2"]) == 0
    lines = _lines(capsys.readouterr().out)
    assert " ccccccc GREEN" in lines[50000000002] and " 9999999 GREEN" in lines[50000000001]


def test_a_night_with_no_run_at_all_is_reported(vr, monkeypatch, capsys):
    """A scheduled run that waited in the concurrency group and was cancelled by a newer one runs no step, so it
    opens no failure issue; GitHub can also skip a schedule. --max-age-hours is what notices the gap."""
    import datetime as dt

    runs = [_run(50000000001, "schedule", "2026-11-10T01:30:00Z", "2026-11-10T01:40:00Z")]
    commits = [_commit("9" * 40, "2026-11-10T01:38:00Z", "2026-11-10T01:31:00Z", body="Run-Id: 50000000001")]
    monkeypatch.setattr(vr, "sh", FakeShell(runs=runs, commits=commits, jobs={}))
    monkeypatch.setattr(vr, "_now", lambda: dt.datetime(2026, 11, 11, 3, 0, tzinfo=dt.timezone.utc))
    assert vr.main(["--limit", "1", "--need", "1", "--max-age-hours", "30"]) == 0
    monkeypatch.setattr(vr, "_now", lambda: dt.datetime(2026, 11, 11, 12, 0, tzinfo=dt.timezone.utc))
    assert vr.main(["--limit", "1", "--need", "1", "--max-age-hours", "30"]) == 1
    assert "MISSING: the newest schedule run was created 34.5 hours ago, more than 30" in capsys.readouterr().out


def test_it_fetches_first_and_fails_closed(vr, monkeypatch, capsys):
    shell = FakeShell()
    monkeypatch.setattr(vr, "sh", shell)
    vr.main(["--event", "push", "--limit", "1", "--need", "1"])
    assert shell.calls[0][:2] == ("git", "fetch")  # a clone one commit behind graded a green run as missing
    monkeypatch.setattr(vr, "sh", FakeShell(runs=[]))
    assert vr.main([]) == 1
    assert "no schedule runs" in capsys.readouterr().out
    monkeypatch.setattr(vr, "sh", FakeShell(commits=[]))
    assert vr.main(["--event", "push"]) == 1
    assert "no bot commits" in capsys.readouterr().out
