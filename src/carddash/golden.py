"""Golden checks: hand-copied headline numbers the pipeline must reproduce.

checks/golden.yaml entries trace to a public release page, never to the machine-readable feed itself.
The fixture test runs every entry against checked-in raw files (deterministic). The live run only checks
entries with check_live: true, which should be periods old enough not to be revised routinely.

An entry with `change_from_prior: true` checks the change from the previous period instead of the level, for
releases that state changes and not levels (the BEA Personal Income and Outlays text: 'PCE increased $36.3 billion').
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import yaml

# How many months a live entry's period must sit behind the newest period of its series in the release it was copied
# from (the checked-in fixture) before it may be checked live. A live entry that the next routine release revises
# turns its source amber for no reason, and amber breaks the two-green-runs measure (REVIEW.md R1-4). Each number is
# the revision window seen in data/revisions.csv from 2026-09 to 2026-11, not a guess:
# - bea 4: every month of the newest quarter moves with the next releases (July 2026 moved on 2026-10-01 and
#   again on 2026-10-30); a month of an earlier quarter holds until the annual update.
# - census 1: the newest month is preliminary; the one before it is printed revised ('r') and then holds until the
#   annual revision.
# - fred, monthly G.19 levels 4: May and June 2026 moved by 0.15 and 3.4 within four months of being published.
#   The quarterly G.19 rate surveys and the SLOOS have never been revised here (0).
# - dfa 24: one release moved 2024 and 2025 by up to 133bn (deposits) and 2023 by 0.001bn.
# Sources not listed have shown no revision to a golden period (0). Age does not protect against a source that
# restates its whole history (the Philly Fed's 26Q2 files restated 2012 onward); tolerance does that work there.
MIN_LIVE_AGE_MONTHS: dict[tuple[str, str], int] = {
    ("bea", "M"): 4,
    ("census", "M"): 1,
    ("fred", "M"): 4,
    ("dfa", "Q"): 24,
}


def months_between(earlier: pd.Timestamp, later: pd.Timestamp) -> int:
    return (later.year - earlier.year) * 12 + (later.month - earlier.month)


def load_golden(path: Path) -> list[dict]:
    if not path.exists():
        return []
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return list(doc)


def golden_decimals(expected: float, tolerance: float) -> int:
    """The decimals a golden number is stated to: those of the hand-copied value, or more when its tolerance is finer.

    YAML reads 119.800 as 119.8, but its tolerance of 0.0006 says three decimals were copied (Census prints
    119,800 in millions). 1347.7 with 0.06 is one decimal; 137.0 with 0.6 is a whole number."""
    text = repr(float(expected))
    shown = 0 if ("e" in text or text.endswith(".0") or "." not in text) else len(text.split(".")[1])
    from_tol = 0 if tolerance <= 0 or tolerance >= 0.5 else math.ceil(-math.log10(2 * tolerance) - 1e-9)
    return max(shown, from_tol)


def number_text(value: float, decimals: int) -> str:
    """Fixed point with thousands separators. Never %g: '%.4g' printed 1347.84 as 1348 and 13998.96 as 1.4e+04."""
    return f"{value:,.{max(decimals, 0)}f}"


def check_golden(facts: pd.DataFrame, entries: list[dict], live_only: bool = False) -> list[dict]:
    """One result per entry: ok, actual, expected, live (check_live), the decimals it is stated to, and a message.

    `live` matters to every reader of a failure: a live entry that fails is a real mismatch (the source goes amber),
    while a fixture-only one that no longer matches has been revised by the source since it was copied."""
    results = []
    for e in entries:
        live = bool(e.get("check_live", True))
        if live_only and not live:
            continue
        series = facts[
            (facts["metric"] == e["metric"])
            & (facts["entity"] == e["entity"])
            & (facts["tier"] == e.get("tier", "all"))
            & (facts["period_type"] == e["period_type"])
            & (facts["source"] == e["source"])
        ].sort_values("period_end")
        period_end = pd.Timestamp(str(e["period_end"]))
        sel = series[series["period_end"] == period_end]
        expected = float(e["expected"])
        tol = float(e.get("tolerance", 0.0))
        dec = golden_decimals(expected, tol)
        base = {"id": e["id"], "source": e["source"], "live": live, "expected": expected, "decimals": dec}
        if sel.empty:
            results.append({**base, "ok": False, "actual": None, "message": f"{e['id']}: no value for {e['period_end']}"})
            continue
        actual = float(sel["value"].iloc[0])
        if e.get("change_from_prior"):
            prior = series[series["period_end"] < period_end]
            if prior.empty:
                results.append({**base, "ok": False, "actual": None,
                                "message": f"{e['id']}: no period before {e['period_end']} to take the change from"})
                continue
            actual = actual - float(prior["value"].iloc[-1])
        ok = abs(actual - expected) <= tol
        msg = (f"{e['id']}: got {number_text(actual, dec + 1)}, expected {number_text(expected, dec)} +/-{tol:g} "
               f"({e.get('origin', '')})")
        results.append({**base, "ok": ok, "actual": actual, "message": msg})
    return results
