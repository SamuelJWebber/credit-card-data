"""Command line: carddash refresh | render | check | health."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

from .alerts import ATTENTION_DAYS, needing_attention, stamp_status_since
from .fetchers import FETCHERS
from .golden import check_golden, load_golden
from .http import make_session
from .issuers import REPORT_PREFIX, crosswalk_report, dimension, load_issuers
from .loader import (
    RED,
    REVISION_COLUMNS,
    SourceHealth,
    append_revisions,
    consume_ack,
    load_acks,
    read_facts,
    refresh_source,
    write_facts,
)
from .paths import REPO_ROOT, Paths
from .redact import redact, scan_paths, secret_values
from .render import render
from .series import load_series


def read_health(paths: Paths) -> dict[str, SourceHealth]:
    if not paths.health_json.exists():
        return {}
    doc = json.loads(paths.health_json.read_text(encoding="utf-8"))
    out = {}
    for name, h in doc.get("sources", {}).items():
        out[name] = SourceHealth(**{k: h.get(k) for k in SourceHealth.__dataclass_fields__ if k in h})
        out[name].messages = list(h.get("messages", []))
    return out


def write_health(paths: Paths, health: dict[str, SourceHealth], generated_at: str) -> None:
    paths.data.mkdir(parents=True, exist_ok=True)
    doc = {"generated_at": generated_at, "sources": {k: v.to_dict() for k, v in sorted(health.items())}}
    paths.health_json.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")


def cmd_refresh(paths: Paths, sources: list[str] | None, do_render: bool) -> int:
    sources = sources or list(FETCHERS)
    unknown = [s for s in sources if s not in FETCHERS]
    if unknown:
        print(f"unknown source(s): {unknown}; known: {list(FETCHERS)}", file=sys.stderr)
        return 2

    facts = read_facts(paths.facts_csv)
    meta = load_series(paths.series_csv)
    session = make_session()
    now = dt.datetime.now(dt.timezone.utc)
    pulled_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    today = now.date()
    acked = load_acks(paths.ack_yaml)
    health = read_health(paths)
    before = {name: (h.status, h.status_since) for name, h in health.items()}
    all_revisions = [pd.DataFrame(columns=REVISION_COLUMNS)]

    for source in sources:
        facts, h, revisions = refresh_source(
            source, facts, meta, FETCHERS[source].fetch, paths.raw / source, session, today, pulled_at, acked
        )
        if source in acked and h.status not in RED:
            consume_ack(paths.ack_yaml, source)
        health[source] = h
        all_revisions.append(revisions)
        print(f"[{source}] {h.status}: {h.rows} rows, {h.n_series} series, latest {h.last_period_end}")
        for m in h.messages:
            print(f"    - {redact(m)}")

    # the unmatched-name report: crosswalk drift is a maintenance item shown in health, never a status change
    for source, lines in crosswalk_report(paths).items():
        if source not in health:
            continue
        health[source].messages = [m for m in health[source].messages if not m.startswith(REPORT_PREFIX)] + lines
        for line in lines:
            print(f"[{source}] {line}")

    for r in check_golden(facts, load_golden(paths.golden_yaml), live_only=True):
        h = health.setdefault(r["source"], SourceHealth(source=r["source"]))
        if not r["ok"]:
            h.worsen("golden_mismatch", "golden check failed: " + r["message"])
            print(f"[{r['source']}] GOLDEN MISMATCH {r['message']}")

    stamp_status_since(health, before, pulled_at)
    write_facts(facts, paths.facts_csv)
    append_revisions(pd.concat(all_revisions, ignore_index=True), paths.revisions_csv)
    write_health(paths, health, pulled_at)
    if do_render:
        out = render(paths)
        print(f"rendered {out}")
    return 0


def cmd_check(paths: Paths, include_all: bool = False) -> int:
    """The golden checks against data/facts.csv: the live entries, which the nightly run checks too.

    Exit 1 only when a live entry fails. With --all the fixture-only entries are listed as well: one that still
    matches is a PASS, and one the source has revised since it was copied prints as REVISED and is not a failure,
    because it was never meant to hold (it is checked against its fixture, tests/test_golden.py)."""
    facts = read_facts(paths.facts_csv)
    results = check_golden(facts, load_golden(paths.golden_yaml), live_only=not include_all)
    bad = revised = 0
    for r in results:
        if r["ok"]:
            print("PASS    " + r["message"])
        elif r["live"]:
            print("FAIL    " + r["message"])
            bad += 1
        else:
            print("REVISED " + r["message"])
            revised += 1
    line = f"{len(results) - bad - revised} passed, {bad} failed"
    if include_all:
        line += f", {revised} revised since first published (fixture-only, not counted as failures)"
    else:
        line += " (live entries; --all lists the fixture-only ones too)"
    print(line)
    return 1 if bad else 0


def cmd_health(paths: Paths, fail_on_red: bool) -> int:
    health = read_health(paths)
    if not health:
        print("no health.json yet")
        return 1 if fail_on_red else 0
    red = 0
    for name, h in sorted(health.items()):
        print(f"{name:12s} {h.status:16s} latest {h.last_period_end} pulled {h.pulled_at}")
        for m in h.messages:
            print(f"    - {redact(m)}")
        red += 1 if h.status in RED else 0
    return 1 if (fail_on_red and red) else 0


def cmd_attention(paths: Paths, days: int) -> int:
    """Print the sources that have been amber for at least `days`, one markdown line each, or nothing.

    The workflow turns this into one open issue while the list is not empty (REVIEW.md R1-3). Always exits 0: an
    amber source is not a failed job, it is a source someone should look at."""
    for line in needing_attention(read_health(paths), dt.datetime.now(dt.timezone.utc), days):
        print(line)
    return 0


def cmd_scan_secrets(targets: list[str]) -> int:
    """Fail closed if anything under `targets` carries a secret value or a credential parameter (redact.py).

    The workflow runs this as the last thing before `git add`, with the secrets in its environment, so a key that
    slipped past every redaction still never reaches the public repository. Prints where, never what."""
    paths = [Path(t) for t in targets]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        print(f"scan-secrets: no such path {missing}", file=sys.stderr)
        return 2
    found = scan_paths(paths)
    for f in found:
        print(f"SECRET {f}", file=sys.stderr)
    n_secrets = len(secret_values())
    print(f"scan-secrets: {len(found)} finding(s) under {', '.join(targets)} "
          f"(checked {n_secrets} secret value(s) and credential-shaped parameters)")
    return 1 if found else 0


def cmd_issuers(paths: Paths) -> int:
    """Print dim_issuer (one line per charter) and the unmatched-name report from the raw files on disk."""
    dim = dimension(load_issuers(paths.issuers_csv))
    for r in dim.itertuples(index=False):
        span = f"{r.valid_from.date()} to {r.valid_to.date() if not pd.isna(r.valid_to) else 'present'}"
        into = f" -> cert {int(r.merged_into)}" if not pd.isna(r.merged_into) else ""
        print(f"{r.fdic_cert:6d} {r.bank_name:46s} {r.kind:8s} {r.issuer_id:12s} rolls up to {r.rollup_issuer_id:12s} {span}{into}")
    for source, lines in crosswalk_report(paths).items():
        for line in lines:
            print(f"[{source}] {line}")
    return 0


def load_dotenv(path) -> None:
    """Load KEY=VALUE lines from a local .env (never committed) into the environment, without overriding."""
    import os

    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main(argv: list[str] | None = None) -> int:
    load_dotenv(REPO_ROOT / ".env")
    p = argparse.ArgumentParser(prog="carddash")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("refresh", help="fetch every source, validate, load, render")
    r.add_argument("--source", action="append", help="limit to one source (repeatable)")
    r.add_argument("--no-render", action="store_true")
    sub.add_parser("render", help="rebuild docs/index.html from data/")
    c = sub.add_parser("check", help="run the live golden checks against data/facts.csv")
    c.add_argument("--all", action="store_true", help="also list fixture-only entries; revised ones print as REVISED")
    sub.add_parser("issuers", help="print dim_issuer and the unmatched-name report")
    h = sub.add_parser("health", help="print source health")
    h.add_argument("--fail-on-red", action="store_true")
    a = sub.add_parser("attention", help="list sources amber for at least --days (markdown, empty when none)")
    a.add_argument("--days", type=int, default=ATTENTION_DAYS)
    s = sub.add_parser("scan-secrets", help="exit 1 if a secret value or credential parameter is under the paths")
    s.add_argument("paths", nargs="+")
    args = p.parse_args(argv)

    paths = Paths.from_root(REPO_ROOT)
    if args.cmd == "refresh":
        return cmd_refresh(paths, args.source, not args.no_render)
    if args.cmd == "render":
        print(f"rendered {render(paths)}")
        return 0
    if args.cmd == "check":
        return cmd_check(paths, args.all)
    if args.cmd == "issuers":
        return cmd_issuers(paths)
    if args.cmd == "health":
        return cmd_health(paths, args.fail_on_red)
    if args.cmd == "attention":
        return cmd_attention(paths, args.days)
    if args.cmd == "scan-secrets":
        return cmd_scan_secrets(args.paths)
    return 2


if __name__ == "__main__":
    sys.exit(main())
