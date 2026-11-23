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


class VerifyError(RuntimeError):
    """Fail-closed error when gh/git output or API responses cannot be parsed."""


def _int_or_none(v) -> int | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _ts(s: str) -> dt.datetime:
    if not isinstance(s, str) or not s.strip():
        raise ValueError(f"missing timestamp: {s!r}")
    parsed = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp has no timezone: {s!r}")
    return parsed


def runs(event: str, limit: int) -> list[dict]:
    try:
        out = sh(
            "gh", "api", f"repos/{OWNER_REPO}/actions/workflows/{WORKFLOW}/runs",
            "-X", "GET", "-f", f"event={event}", "-f", f"per_page={limit}",
        )
        doc = json.loads(out)
    except (subprocess.CalledProcessError, OSError, ValueError) as exc:
        raise VerifyError(f"could not read workflow runs from GitHub API: {exc}") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("workflow_runs"), list):
        raise VerifyError("malformed GitHub API runs response: expected object with 'workflow_runs' list")
    items = doc["workflow_runs"]
    if any(not isinstance(r, dict) for r in items):
        raise VerifyError("malformed GitHub API runs response: workflow_runs entry is not an object")
    return items


def job_window(run_id: int) -> tuple[dt.datetime, dt.datetime | None] | None:
    """When a runner started and finished the refresh job of this run, or None if the jobs API cannot say."""
    try:
        doc = json.loads(sh("gh", "api", f"repos/{OWNER_REPO}/actions/runs/{run_id}/jobs"))
        jobs = doc.get("jobs") if isinstance(doc, dict) else None
        if not isinstance(jobs, list):
            return None
        job = next((j for j in jobs if isinstance(j, dict) and j.get("name") == JOB),
                   jobs[0] if len(jobs) == 1 and isinstance(jobs[0], dict) else None)
        if not job or not job.get("started_at"):
            return None
        return _ts(job["started_at"]), (_ts(job["completed_at"]) if job.get("completed_at") else None)
    except (subprocess.CalledProcessError, OSError, KeyError, TypeError, ValueError):
        return None


def _trailer(body: str, key: str) -> int | None:
    m = re.search(rf"^{key}:\s*(\d+)\s*$", body, flags=re.M)
    return int(m.group(1)) if m else None


def bot_commits(ref: str) -> list[dict]:
    """Every 'refresh:' commit on `ref`, newest first: sha, health.json at that commit, the stamp it carries and the
    run that made it (from the commit's trailers, else from health.json; None for commits older than both)."""
    try:
        log = sh("git", "log", ref, "--format=%H%x1f%cI%x1f%s%x1f%b%x1e", "--committer=carddash-bot", "-n", "200")
    except (subprocess.CalledProcessError, OSError) as exc:
        raise VerifyError(f"could not read git log for {ref}: {exc}") from exc
    out = []
    for record in log.split("\x1e"):
        fields = record.strip("\n").split("\x1f")
        if len(fields) < 4 or not fields[2].startswith("refresh:"):
            continue
        sha, _when, _subject, body = fields[:4]
        try:
            health = json.loads(sh("git", "show", f"{sha}:data/health.json"))
        except (subprocess.CalledProcessError, OSError, ValueError):
            health = None
        if not isinstance(health, dict):
            health = None
        named = health.get("run") if isinstance((health or {}).get("run"), dict) else {}
        run_id = _trailer(body, "Run-Id") or _int_or_none(named.get("id"))
        attempt = _trailer(body, "Run-Attempt") or _int_or_none(named.get("attempt"))
        stamp = None
        if health and health.get("generated_at"):
            try:
                stamp = _ts(health["generated_at"])
            except ValueError:
                stamp = None
        out.append({"sha": sha, "health": health, "stamp": stamp, "run_id": run_id, "attempt": attempt})
    return out


def by_run_id(run: dict, commits: list[dict]) -> dict | None:
    """The commit that names this run; of a rerun's commits, the one of the attempt the API calls the latest."""
    mine = [c for c in commits if c["run_id"] == run["id"]]
    latest = [c for c in mine if c["attempt"] == run.get("run_attempt")]
    return (latest or mine or [None])[0]


def by_window(run: dict, commits: list[dict], window) -> tuple[dict | None, str]:
    """For commits older than run names: the newest stamp inside the job window, else inside the run window."""
    try:
        updated = _ts(run["updated_at"])
        how = "job window"
        if window is None:
            how = "run window"
            window = (_ts(run.get("run_started_at") or run["created_at"]), updated)
        start, end = window[0], window[1] or updated
    except (KeyError, TypeError, ValueError) as exc:
        raise VerifyError(f"malformed run timestamps for run {run.get('id', '?')}: {exc}") from exc
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
    try:
        newest = runs("schedule", 1)
    except VerifyError as exc:
        print(f"ERROR {exc}")
        return 1
    if not newest:
        print(f"MISSING: no scheduled run of {WORKFLOW} at all")
        return 1
    run = newest[0]
    try:
        rid = run["id"]
        created_raw = run["created_at"]
        created_ts = _ts(created_raw)
    except (KeyError, TypeError, ValueError) as exc:
        print(f"ERROR malformed scheduled run payload: {exc}")
        return 1
    created = created_raw[:16].replace("T", " ")
    age = (_now() - created_ts).total_seconds() / 3600
    if age > hours:
        print(f"MISSING: the newest scheduled run, {rid}, was created {created} UTC, {age:.1f} hours ago "
              f"(more than {hours:g}). Last night's run did not happen. {run.get('html_url', '')}".rstrip())
        return 1
    if run.get("conclusion") in STOPPED:
        print(f"STOPPED: the newest scheduled run, {rid} ({created} UTC), ended '{run['conclusion']}' without "
              f"running its steps, so it opened no failure issue. {run.get('html_url', '')}".rstrip())
        return 1
    print(f"OK: scheduled run {rid} created {created} UTC, {age:.1f} hours ago: "
          f"{run.get('conclusion') or run.get('status')}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
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
        if args.watch <= 0:
            p.error("--watch must be positive")
        return watch(args.watch)
    if args.limit < 1:
        p.error("--limit must be at least 1")
    if args.need < 1:
        p.error("--need must be at least 1")
    if args.need > args.limit:
        p.error("--need cannot exceed --limit")
    if args.max_age_hours is not None and args.max_age_hours <= 0:
        p.error("--max-age-hours must be positive")

    try:
        if not args.no_fetch:
            try:
                sh("git", "fetch", "--quiet", "origin", "main")
            except (subprocess.CalledProcessError, OSError) as exc:
                raise VerifyError(f"git fetch origin main failed: {exc}") from exc
        commits = bot_commits(args.ref)
        if not commits:
            print(f"no bot commits on {args.ref}: is this a clone of {OWNER_REPO}, and did the fetch work?")
            return 1
        workflow_runs = runs(args.event, args.limit)
        rows = []
        for run in workflow_runs:
            try:
                rid = run["id"]
                created_raw = run["created_at"]
                created_ts = _ts(created_raw)
                event_name = str(run["event"])
                outcome = str(run.get("conclusion") or run["status"])
            except (KeyError, TypeError, ValueError) as exc:
                raise VerifyError(f"malformed workflow run payload: {exc}") from exc
            commit, how = match(run, commits, lambda rid=rid: job_window(rid))
            health = (commit or {}).get("health") or {}
            raw_sources = health.get("sources") if isinstance(health, dict) else None
            statuses = {
                s: (d.get("status") if isinstance(d, dict) else None)
                for s, d in (raw_sources.items() if isinstance(raw_sources, dict) else ())
            }
            all_green = bool(statuses) and all(v == GREEN for v in statuses.values()) and run.get("conclusion") == "success"
            rows.append((run, created_ts, commit, statuses, all_green))
            stamp = created_raw[:16].replace("T", " ")
            summary = ", ".join(f"{s}={v}" for s, v in sorted(statuses.items())) or "no bot commit found"
            sha = (commit or {}).get("sha") or ""
            print(f"{rid}  {stamp} UTC  {event_name:9s} {outcome:9s} "
                  f"{sha[:7]:7s} {'GREEN' if all_green else 'not green'}  {summary}"
                  + (f"  (matched by {how})" if commit else ""))
    except VerifyError as exc:
        print(f"ERROR {exc}")
        return 1
    if not rows:
        print(f"no {args.event} runs of {WORKFLOW} yet")
        return 1
    if args.max_age_hours is not None:
        age = _now() - rows[0][1]
        if age > dt.timedelta(hours=args.max_age_hours):
            print(f"\nMISSING: the newest {args.event} run was created {age.total_seconds() / 3600:.1f} hours ago, "
                  f"more than {args.max_age_hours:g}")
            return 1
    newest = rows[: args.need]
    ok = len(newest) == args.need and all(r[4] for r in newest)
    print(
        f"\n{'PASS' if ok else 'NOT YET'}: newest {args.need} {args.event} run(s) all green with every source ok"
        + ("" if ok else f" (have {sum(1 for r in newest if r[4])} of {args.need})")
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
