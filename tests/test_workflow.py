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
