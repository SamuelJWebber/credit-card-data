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
