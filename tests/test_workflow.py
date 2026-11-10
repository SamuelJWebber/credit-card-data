"""The nightly workflow's safety properties, read from .github/workflows/refresh.yml itself."""

from __future__ import annotations

import yaml

from conftest import REPO

WORKFLOW = REPO / ".github" / "workflows" / "refresh.yml"


def _steps() -> dict[str, dict]:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return {s.get("name", s.get("uses", "")): s for s in doc["jobs"]["refresh"]["steps"]}


def test_the_commit_step_scans_for_secrets_before_it_adds_anything():
    step = _steps()["Commit data and site"]
    script = step["run"]
    assert "carddash scan-secrets data docs checks/restatement_ack.yaml" in script
    assert script.index("carddash scan-secrets") < script.index("git add")
    # the scan looks for the exact secret values, so it needs them; and the step runs whatever happened before
    assert set(step["env"]) == {"FRED_API_KEY", "CARDDASH_CONTACT"}
    assert step["if"] == "always()"
    # everything the step adds is what the scan covered
    add_line = next(line.strip() for line in script.splitlines() if line.strip().startswith("git add"))
    assert add_line == "git add data docs checks/restatement_ack.yaml"


def _doc() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_a_failed_run_says_so_in_an_issue_and_a_good_run_closes_it():
    """REVIEW.md R1-3: 33 scheduled runs failed in a row and nothing told anyone."""
    assert _doc()["permissions"] == {"contents": "write", "issues": "write"}
    names = list(_steps())
    opener, closer = _steps()["Open or update the failure issue"], _steps()["Close the failure issue"]
    assert opener["if"] == "failure()" and closer["if"] == "success()"
    assert names.index("Open or update the failure issue") > names.index("Fail the job if any source is red")
    assert names[-1] == "Close the failure issue"  # success() must see every step that can fail the job
    script = opener["run"]
    assert "gh issue create" in script and "gh issue edit" in script and "@${OWNER}" in script
    assert opener["env"]["OWNER"] == "${{ github.repository_owner }}"
    assert "gh issue close" in closer["run"] and "--label refresh-failure" in closer["run"]
    for step in (opener, closer, _steps()["Open or close the attention issue"]):
        assert step["continue-on-error"] is True  # an API hiccup must never fail a data run
        assert step["env"]["GH_TOKEN"] == "${{ github.token }}"


def test_a_source_amber_for_a_week_keeps_an_issue_open():
    step = _steps()["Open or close the attention issue"]
    assert step["if"] == "always() && steps.install.outcome == 'success'"
    assert _steps()["Install"]["id"] == "install"
    assert "uv run carddash attention --days 7" in step["run"]
    assert "gh issue create" in step["run"] and "gh issue close" in step["run"] and "@${OWNER}" in step["run"]


def test_the_failure_issue_can_be_tested_without_fetching_anything():
    """A manual run with fail_on_purpose stops before the refresh, so the failure path can be seen working."""
    on = _doc()[True]  # PyYAML reads the bare key `on` as True
    assert on["workflow_dispatch"]["inputs"]["fail_on_purpose"]["default"] is False
    names = list(_steps())
    step = _steps()["Fail on purpose"]
    assert step["if"] == "github.event_name == 'workflow_dispatch' && inputs.fail_on_purpose"
    assert names.index("Fail on purpose") < names.index("Refresh data and render")
    assert "exit 1" in step["run"]


def test_actions_are_pinned_to_commits():
    """REVIEW.md R1-16: tags can be moved, and the refresh job holds contents: write and both secrets. Every workflow
    pins, and one action is pinned to the same commit everywhere."""
    import re

    pins: dict[str, set[str]] = {}
    for path in sorted(WORKFLOW.parent.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        uses = re.findall(r"^\s*-?\s*uses:\s*(\S+)(.*)$", text, flags=re.M)
        assert uses, f"{path.name}: no actions found"
        for ref, comment in uses:
            name, _, version = ref.partition("@")
            assert re.fullmatch(r"[0-9a-f]{40}", version), f"{path.name}: {name} is pinned to {version!r}, not a commit"
            assert re.search(r"#\s*v\d", comment), f"{path.name}: {name}: say which release the commit is"
            pins.setdefault(name, set()).add(version)
    assert all(len(v) == 1 for v in pins.values()), pins


def test_a_weekly_run_checks_every_golden_against_its_document():
    """REVIEW.md R2-3 and bigger improvement 2: a golden link answered 404 for two months and nothing noticed."""
    doc = yaml.safe_load((WORKFLOW.parent / "provenance.yml").read_text(encoding="utf-8"))
    assert doc[True]["schedule"][0]["cron"].endswith("* * 1") and "workflow_dispatch" in doc[True]
    assert doc["permissions"] == {"contents": "read", "issues": "write"}  # it never writes to the repository
    steps = {s.get("name", s.get("uses", "")): s for s in doc["jobs"]["provenance"]["steps"]}
    check = steps["Every golden against the document it cites"]["run"]
    assert "checks/verify_provenance.py" in check and "checks/verify_g19.py --provenance" in check
    assert "exit $status" in check
    opener, closer = steps["Open or update the provenance issue"], steps["Close the provenance issue"]
    # a manual run can switch the issue off; a scheduled run has no inputs, and GitHub compares null with false as
    # 0 == 0, so the condition must test the event, never `inputs.open_issue != false`
    manual = "(github.event_name != 'workflow_dispatch' || inputs.open_issue)"
    assert opener["if"] == f"failure() && steps.install.outcome == 'success' && {manual}"
    assert closer["if"] == f"success() && {manual}"
    assert doc[True]["workflow_dispatch"]["inputs"]["open_issue"]["default"] is True
    assert opener["continue-on-error"] is True and closer["continue-on-error"] is True
    assert "gh issue create" in opener["run"] and "gh issue edit" in opener["run"] and "gh issue close" in closer["run"]
    # the owner is mentioned once, when the issue opens, not on every weekly rewrite
    assert opener["run"].count("@${OWNER}") == 1 and "first.md" in opener["run"]


def test_each_bot_commit_names_the_run_that_made_it(tmp_path, monkeypatch):
    """REVIEW.md R2-1: checks/verify_releases.py matched runs to commits by time and credited a run with the next run's
    commit. The commit now carries the run in trailers. This makes a commit the way the workflow does, in a scratch
    repository with real git, and reads it back with the script's own parser."""
    import importlib.util
    import json
    import shlex
    import subprocess

    script = _steps()["Commit data and site"]["run"]
    line = next(x.strip() for x in script.splitlines() if x.strip().startswith("git commit"))
    for trailer in ('--trailer "Run-Id: ${GITHUB_RUN_ID}"', '--trailer "Run-Attempt: ${GITHUB_RUN_ATTEMPT}"',
                    '--trailer "Event: ${GITHUB_EVENT_NAME}"'):
        assert trailer in line
    env = {"GITHUB_RUN_ID": "42724326075", "GITHUB_RUN_ATTEMPT": "2", "GITHUB_EVENT_NAME": "schedule"}
    args = shlex.split(line.replace("$(date -u +%Y-%m-%dT%H:%MZ)", "2026-11-10T02:13Z")
                       .replace("${GITHUB_RUN_ID}", env["GITHUB_RUN_ID"])
                       .replace("${GITHUB_RUN_ATTEMPT}", env["GITHUB_RUN_ATTEMPT"])
                       .replace("${GITHUB_EVENT_NAME}", env["GITHUB_EVENT_NAME"]))
    assert "$" not in " ".join(args)

    monkeypatch.chdir(tmp_path)
    git = ["git", "-c", "user.name=carddash-bot", "-c", "user.email=carddash-bot@users.noreply.github.com",
           "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "init", "-q"], check=True)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "health.json").write_text(json.dumps({"generated_at": "2026-11-10T02:10:00Z"}), encoding="utf-8")
    subprocess.run(["git", "add", "data"], check=True)
    subprocess.run(git + args[1:], check=True, capture_output=True)

    spec = importlib.util.spec_from_file_location("verify_releases", REPO / "checks" / "verify_releases.py")
    vr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vr)
    (commit,) = vr.bot_commits("HEAD")
    assert (commit["run_id"], commit["attempt"]) == (42724326075, 2)
    run = {"id": 42724326075, "run_attempt": 2, "created_at": "2026-11-10T03:00:00Z", "updated_at": "2026-11-10T03:05:00Z"}
    assert vr.match(run, [commit]) == (commit, "run id")  # named, so found although its stamp is outside the window


def test_a_queued_run_starts_from_the_newest_main():
    """REVIEW.md R1-16: a run queued behind another checked out the commit it was triggered on, a refresh behind."""
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["refresh"]["steps"]
    names = [s.get("name") or s.get("uses", "") for s in steps]
    assert names[0].startswith("actions/checkout@")
    assert names[1] == "Start from the newest main" and steps[1]["run"] == "git pull --ff-only origin main"
    assert names.index("Start from the newest main") < names.index("Install") < names.index("Refresh data and render")


def test_a_daily_watch_notices_a_night_with_no_scheduled_run():
    """REVIEW.md bigger improvement 1: a cancelled waiting run executes no step and opens no failure issue."""
    doc = yaml.safe_load((WORKFLOW.parent / "watch.yml").read_text(encoding="utf-8"))
    assert doc[True]["schedule"][0]["cron"].endswith("* * *") and "workflow_dispatch" in doc[True]
    assert doc["permissions"] == {"actions": "read", "contents": "read", "issues": "write"}
    steps = {s.get("name", s.get("uses", "")): s for s in doc["jobs"]["watch"]["steps"]}
    check = steps["Did the nightly refresh run?"]["run"]
    assert "python3 checks/verify_releases.py --watch 30" in check and "exit $status" in check
    opener, closer = steps["Open or update the missing-run issue"], steps["Close the missing-run issue"]
    assert opener["if"] == "failure()" and closer["if"] == "success()"
    assert opener["continue-on-error"] is True and closer["continue-on-error"] is True
    assert opener["run"].count("@${OWNER}") == 1 and "gh issue close" in closer["run"]
    # the script it runs needs nothing but the standard library: there is no install step
    source = (REPO / "checks" / "verify_releases.py").read_text(encoding="utf-8")
    imports = {line.split()[1].split(".")[0] for line in source.splitlines() if line.startswith(("import ", "from "))}
    assert imports <= {"__future__", "argparse", "datetime", "json", "re", "subprocess", "sys"}, imports
