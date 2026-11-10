"""Task 8 check: were the last scheduled refresh runs green for every source?

For each recent run of the refresh workflow (scheduled by default; --event push for the push-triggered ones) this
finds the bot commit THAT run pushed, reads every source's status from that commit's health.json, and says whether
the newest N consecutive runs were all green. A run that committed nothing, failed before committing, or has a
source that is not 'ok' breaks the streak.

How a run is matched to its commit (REVIEW.md R2-1):
1. By name. Since 2026-11-10 every bot commit says which run made it, in 'Run-Id:' and 'Run-Attempt:' trailers
   (and health.json carries the same in "run"). A rerun makes a second commit for the same run id; the attempt the
   API reports as the run's latest decides.
2. For older commits, which name no run, by the JOB's window: from when a runner started the refresh job to when it
   finished (the jobs API), with no slack. Runs in the 'refresh' concurrency group never execute at the same time,
   so one stamp at most falls inside. Without the jobs API, the run's own window (run_started_at to updated_at, no
   slack) and the newest stamp inside it. The window used to run from created_at to 5 minutes past updated_at and
   take the newest stamp, which credited a run with the NEXT run's commit; and a run that queued behind another
   reports created_at and run_started_at as the time it was queued, not the time it ran.

It runs `git fetch origin main` first (a clone even one commit behind used to report a green run as 'no bot
commit found'), and fails closed: no runs, or no bot commits on the ref, is exit 1. Needs `gh`, authenticated.

    uv run python checks/verify_releases.py            # the last 5 scheduled runs, verdict on the newest 2
    uv run python checks/verify_releases.py --event push --limit 8
    uv run python checks/verify_releases.py --limit 1 --need 1 --max-age-hours 30   # last night's run, if any
    python3 checks/verify_releases.py --watch 30     # the daily watch workflow: did a scheduled run happen at all?
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys

OWNER_REPO = "SamuelJWebber/credit-card-data"
WORKFLOW = "refresh.yml"
JOB = "refresh"
GREEN = "ok"


def sh(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True, encoding="utf-8").stdout


def runs(event: str, limit: int) -> list[dict]:
    out = sh(
        "gh", "api", f"repos/{OWNER_REPO}/actions/workflows/{WORKFLOW}/runs",
        "-X", "GET", "-f", f"event={event}", "-f", f"per_page={limit}",
    )
    return json.loads(out)["workflow_runs"]


def job_window(run_id: int) -> tuple[dt.datetime, dt.datetime | None] | None:
    """When a runner started and finished the refresh job of this run, or None if the jobs API cannot say."""
    try:
        jobs = json.loads(sh("gh", "api", f"repos/{OWNER_REPO}/actions/runs/{run_id}/jobs"))["jobs"]
    except (subprocess.CalledProcessError, KeyError, ValueError):
        return None
    job = next((j for j in jobs if j.get("name") == JOB), jobs[0] if len(jobs) == 1 else None)
    if not job or not job.get("started_at"):
        return None
    return _ts(job["started_at"]), (_ts(job["completed_at"]) if job.get("completed_at") else None)


def _trailer(body: str, key: str) -> int | None:
    m = re.search(rf"^{key}:\s*(\d+)\s*$", body, flags=re.M)
    return int(m.group(1)) if m else None


def bot_commits(ref: str) -> list[dict]:
    """Every 'refresh:' commit on `ref`, newest first: sha, health.json at that commit, the stamp it carries and the
    run that made it (from the commit's trailers, else from health.json; None for commits older than both)."""
    log = sh("git", "log", ref, "--format=%H%x1f%cI%x1f%s%x1f%b%x1e", "--committer=carddash-bot", "-n", "200")
    out = []
    for record in log.split("\x1e"):
        fields = record.strip("\n").split("\x1f")
        if len(fields) < 4 or not fields[2].startswith("refresh:"):
            continue
        sha, _when, _subject, body = fields[:4]
        try:
            health = json.loads(sh("git", "show", f"{sha}:data/health.json"))
        except (subprocess.CalledProcessError, ValueError):
            health = None
        named = (health or {}).get("run") or {}
        run_id = _trailer(body, "Run-Id") or named.get("id")
        attempt = _trailer(body, "Run-Attempt") or named.get("attempt")
        stamp = _ts(health["generated_at"]) if health and health.get("generated_at") else None
        out.append({"sha": sha, "health": health, "stamp": stamp,
                    "run_id": int(run_id) if run_id else None, "attempt": int(attempt) if attempt else None})
    return out


def _ts(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def by_run_id(run: dict, commits: list[dict]) -> dict | None:
    """The commit that names this run; of a rerun's commits, the one of the attempt the API calls the latest."""
    mine = [c for c in commits if c["run_id"] == run["id"]]
    latest = [c for c in mine if c["attempt"] == run.get("run_attempt")]
    return (latest or mine or [None])[0]


def by_window(run: dict, commits: list[dict], window) -> tuple[dict | None, str]:
    """For commits older than run names: the newest stamp inside the job window, else inside the run window."""
    how = "job window"
    if window is None:
        how = "run window"
        window = (_ts(run.get("run_started_at") or run["created_at"]), _ts(run["updated_at"]))
    start, end = window[0], window[1] or _ts(run["updated_at"])
    # a commit that names a run is never another run's
    inside = [c for c in commits if c["run_id"] is None and c["stamp"] and start <= c["stamp"] <= end]
    return (inside[0], how) if inside else (None, "none")


def match(run: dict, commits: list[dict], window=None) -> tuple[dict | None, str]:
    """The bot commit `run` pushed, and how it was found ('run id', 'job window', 'run window' or 'none').
    `window` is the job's (started, completed), or a function returning it, called only when no commit names the run."""
    commit = by_run_id(run, commits)
    if commit:
        return commit, "run id"
    return by_window(run, commits, window() if callable(window) else window)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# conclusions of a run that ended without running its steps, so its own failure step never opened an issue
STOPPED = {"cancelled", "skipped", "timed_out", "startup_failure", "stale"}


def watch(hours: float) -> int:
    """For .github/workflows/watch.yml: did a scheduled refresh run in the last `hours`, and run its steps?

    Only one run can wait in the 'refresh' concurrency group, and a newer one cancels the one waiting; a cancelled
    run executes no step, so it opens no failure issue, and GitHub can skip a schedule outright. Either way the v1
    count would simply stop with nothing said (REVIEW.md bigger improvement 1). A run that FAILED is not reported
    here: it opened the failure issue itself. An amber run is the attention issue's business."""
    newest = runs("schedule", 1)
    if not newest:
        print(f"MISSING: no scheduled run of {WORKFLOW} at all")
        return 1
    run = newest[0]
    created = run["created_at"][:16].replace("T", " ")
    age = (_now() - _ts(run["created_at"])).total_seconds() / 3600
    if age > hours:
        print(f"MISSING: the newest scheduled run, {run['id']}, was created {created} UTC, {age:.1f} hours ago "
              f"(more than {hours:g}). Last night's run did not happen. {run.get('html_url', '')}".rstrip())
        return 1
    if run.get("conclusion") in STOPPED:
        print(f"STOPPED: the newest scheduled run, {run['id']} ({created} UTC), ended '{run['conclusion']}' without "
              f"running its steps, so it opened no failure issue. {run.get('html_url', '')}".rstrip())
        return 1
    print(f"OK: scheduled run {run['id']} created {created} UTC, {age:.1f} hours ago: "
          f"{run.get('conclusion') or run.get('status')}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--event", default="schedule", help="workflow trigger to inspect (schedule, push, workflow_dispatch)")
    p.add_argument("--limit", type=int, default=5, help="how many recent runs to list")
    p.add_argument("--need", type=int, default=2, help="how many consecutive newest runs must be all green")
    p.add_argument("--ref", default="origin/main", help="git ref carrying the bot commits")
    p.add_argument("--no-fetch", action="store_true", help="do not run `git fetch origin main` first")
    p.add_argument("--max-age-hours", type=float, default=None,
                   help="also fail when the newest run is older than this (a night with no scheduled run at all)")
    p.add_argument("--watch", type=float, metavar="HOURS", default=None,
                   help="only say whether a scheduled run was created in the last HOURS and ran its steps (exit 1 if "
                        "not); reads no commits. For .github/workflows/watch.yml")
    args = p.parse_args(argv)

    if args.watch is not None:
        return watch(args.watch)
    if not args.no_fetch:
        sh("git", "fetch", "--quiet", "origin", "main")
    commits = bot_commits(args.ref)
    if not commits:
        print(f"no bot commits on {args.ref}: is this a clone of {OWNER_REPO}, and did the fetch work?")
        return 1
    rows = []
    for run in runs(args.event, args.limit):
        commit, how = match(run, commits, lambda rid=run["id"]: job_window(rid))
        health = (commit or {}).get("health") or {}
        statuses = {s: d.get("status") for s, d in health.get("sources", {}).items()}
        all_green = bool(statuses) and all(v == GREEN for v in statuses.values()) and run["conclusion"] == "success"
        rows.append((run, commit, statuses, all_green))
        stamp = run["created_at"][:16].replace("T", " ")
        summary = ", ".join(f"{s}={v}" for s, v in sorted(statuses.items())) or "no bot commit found"
        sha = (commit or {}).get("sha") or ""
        print(f"{run['id']}  {stamp} UTC  {run['event']:9s} {run['conclusion'] or run['status']:9s} "
              f"{sha[:7]:7s} {'GREEN' if all_green else 'not green'}  {summary}"
              + (f"  (matched by {how})" if commit else ""))
    if not rows:
        print(f"no {args.event} runs of {WORKFLOW} yet")
        return 1
    if args.max_age_hours is not None:
        age = _now() - _ts(rows[0][0]["created_at"])
        if age > dt.timedelta(hours=args.max_age_hours):
            print(f"\nMISSING: the newest {args.event} run was created {age.total_seconds() / 3600:.1f} hours ago, "
                  f"more than {args.max_age_hours:g}")
            return 1
    newest = rows[: args.need]
    ok = len(newest) == args.need and all(r[3] for r in newest)
    print(
        f"\n{'PASS' if ok else 'NOT YET'}: newest {args.need} {args.event} run(s) all green with every source ok"
        + ("" if ok else f" (have {sum(1 for r in newest if r[3])} of {args.need})")
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
