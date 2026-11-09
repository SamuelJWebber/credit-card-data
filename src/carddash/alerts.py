"""What the nightly job says out loud, beyond the page.

From 2026-10-08 to 2026-11-09 every scheduled run failed (33 in a row) and bea and census sat amber, and nothing told
anyone: amber shows as success in the Actions UI, and nobody reads the page to look for pipeline health (REVIEW.md
R1-3). The workflow therefore opens one GitHub issue when a run fails and closes it when one succeeds, and keeps a
second issue open while any source has been amber for a week. This module writes that second report from health.json;
the issue calls are in .github/workflows/refresh.yml.

A red source fails the job and is covered by the failure issue, so the attention report lists amber sources only.
"""

from __future__ import annotations

import datetime as dt

from .loader import AMBER, SourceHealth
from .redact import redact

ATTENTION_DAYS = 7
MAX_MESSAGE = 300


def _parse(stamp: str) -> dt.datetime:
    return dt.datetime.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)


def stamp_status_since(health: dict[str, SourceHealth], before: dict[str, tuple[str, str | None]], now: str) -> None:
    """Carry each source's status_since over from the previous health.json while its status holds; restart it at
    `now` when the status changes or the source is new. `before` is name -> (status, status_since) as read at the
    start of the run."""
    for name, h in health.items():
        prev_status, prev_since = before.get(name, (None, None))
        h.status_since = prev_since if (prev_status == h.status and prev_since) else now


def needing_attention(health: dict[str, SourceHealth], now: dt.datetime, days: int = ATTENTION_DAYS) -> list[str]:
    """One markdown line per source that has been amber for at least `days`, longest first. Empty when none."""
    rows = []
    for name, h in health.items():
        if h.status not in AMBER or not h.status_since:
            continue
        age = (now - _parse(h.status_since)).days
        if age < days:
            continue
        first = " ".join(redact(h.messages[0]).split())[:MAX_MESSAGE] if h.messages else ""
        line = f"- **{name}** has been `{h.status}` since {h.status_since[:10]} ({age} days)"
        rows.append((age, name, line + (f": {first}" if first else "")))
    return [line for _, _, line in sorted(rows, key=lambda r: (-r[0], r[1]))]
