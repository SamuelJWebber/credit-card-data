"""Spot-check golden entries against the Fed's own G.19 release pages, parsed directly (no FRED, no LLM).

    uv run python checks/verify_g19.py                # every G.19 entry against the CURRENT release
    uv run python checks/verify_g19.py --provenance   # every G.19 entry against the dated release it cites
    uv run python checks/verify_g19.py --rebase       # as the default, and print a re-based entry for each FAIL

Reads checks/golden.yaml, parses the HTML tables of the page, maps each golden period to a table column, and prints
PASS/FAIL. Exit code 1 on any failure. --rebase writes nothing: it prints, for each entry the current release no
longer matches, the same entry with the current value, the current release's date and its dated page, ready to
replace the old one in golden.yaml once a person has read the number on that page (REVIEW.md bigger improvement 3:
the re-basings after the 2026 annual revisions were done by hand after a month of amber).

The two modes answer different questions. The default asks whether a golden still holds in the newest release
(after each G.19 release: a revision that moves a LIVE entry turns fred amber until it is re-based). --provenance
asks whether the release each entry cites (its origin_url, a dated archive page such as /releases/g19/20260908/,
which never changes) states that number, so it must pass for fixture-only entries too, forever (REVIEW.md R1-11:
origin_url used to be the 'current' page, which stops showing a number one release later).

It fails closed (REVIEW.md R2-4). A page that does not answer 200, or carries no 'Release Date', is an error, not
a release with nothing in it: that once turned an 'Access Denied' page into 13 SKIPs, "all checked entries match"
and exit 0. The last line counts what was compared, and the exit code is 1 when nothing was, or when more entries
were skipped than checked (the page's layout has probably changed).
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import math
import re
import sys
from pathlib import Path

import yaml

from carddash.cli import load_dotenv
from carddash.http import CheckFailed, fetch_or_die, make_session

G19_URL = "https://www.federalreserve.gov/releases/g19/current/default.htm"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# golden metric -> (row label on the page, which table). Series that exist per holder are keyed on (metric, entity)
# and read from the 'by major holder' table, where each holder label appears three times (total, revolving,
# nonrevolving); the revolving block is the second occurrence.
ROW_FOR_METRIC = {
    "revolving_credit_sa": ("Revolving", "level_sa"),
    "card_apr_all_accounts": ("All accounts", "rates"),
    "card_apr_assessed_interest": ("Accounts assessed interest", "rates"),
    ("revolving_credit_nsa", "DEPOSITORY_INSTITUTIONS"): ("Depository institutions", "holder_revolving"),
    ("revolving_credit_nsa", "CREDIT_UNIONS"): ("Credit unions", "holder_revolving"),
    ("revolving_credit_nsa", "FINANCE_COMPANIES"): ("Finance companies", "holder_revolving"),
}


def _cells(row_html: str) -> list[tuple[str, int]]:
    """(text, colspan) for each cell."""
    out = []
    for m in re.finditer(r"<t([dh])([^>]*)>(.*?)</t[dh]>", row_html, flags=re.I | re.S):
        attrs, inner = m.group(2), m.group(3)
        span = re.search(r'colspan\s*=\s*"?(\d+)', attrs, flags=re.I)
        text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", inner)).split())
        out.append((text, max(1, int(span.group(1))) if span else 1))
    return out


def parse_tables(page: str) -> list[dict[str, dict[str, str]]]:
    """Each table -> {row label: {column key: value}}. Column keys look like '2025', 'Q1 2026', 'Jun 2026'."""
    tables = []
    for tbl in re.findall(r"<table[^>]*>(.*?)</table>", page, flags=re.I | re.S):
        rows = [_cells(r) for r in re.findall(r"<tr[^>]*>(.*?)</tr>", tbl, flags=re.I | re.S)]
        rows = [r for r in rows if r]
        # find the header row with period labels (Q1, Apr, 2024 ...) and the year row just above it
        col_keys: list[str] | None = None
        data: dict[str, dict[str, str]] = {}
        for i, r in enumerate(rows):
            labels = [c[0] for c in r]
            if col_keys is None and sum(bool(re.fullmatch(r"(Q[1-4]|[A-Z][a-z]{2}|20\d\d)( [rp])?", x)) for x in labels) >= 6:
                years: list[str] = []
                if i > 0:
                    for text, span in rows[i - 1]:
                        years.extend([text] * span)
                keys = []
                period_cols = [x for x in labels if x != ""]
                # the year row aligns to period columns from the right (label cell is unspanned on the left)
                years = ([""] * max(0, len(period_cols) - len(years)) + years)[-len(period_cols):]
                for lab, yr in zip(period_cols, years):
                    lab = re.sub(r" [rp]$", "", lab)
                    keys.append(lab if re.fullmatch(r"20\d\d", lab) else f"{lab} {yr}".strip())
                if len(set(keys)) == len(keys):
                    col_keys = keys
                continue
            if col_keys and len(labels) >= 2:
                name = labels[0]
                vals = labels[1:]
                if len(vals) == len(col_keys) and name:
                    data.setdefault(name, {})
                    # a table can hold several 'Revolving' rows (pct change, flow, level); keep them all, in order
                    n_same = sum(k == name or k.startswith(f"{name}#") for k in data)
                    key = name if not data[name] else f"{name}#{n_same}"
                    data[key] = dict(zip(col_keys, vals))
        if data:
            tables.append(data)
    return tables


def find_row(tables, label: str, kind: str) -> dict[str, str] | None:
    if kind == "holder_revolving":
        # the outstanding-by-holder table (Total above $4,000bn), not the flows table with the same row labels
        for t in tables:
            total = [n for n in (_num(v) for v in t.get("Total", {}).values()) if n is not None]
            if total and max(total) > 4000 and f"{label}#1" in t:
                return t[f"{label}#1"]
        return None
    for t in tables:
        for name, row in t.items():
            if not name.split("#")[0] == label:
                continue
            nums = [_num(v) for v in row.values()]
            nums = [n for n in nums if n is not None]
            if not nums:
                continue
            if kind == "level_sa" and max(nums) > 500:  # levels in $bn, first (SA) table wins
                return row
            if kind == "rates" and max(nums) < 100:
                return row
    return None


def _num(s: str) -> float | None:
    s = s.replace(",", "").strip()
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def columns_for(period_end: dt.date, period_type: str) -> list[str]:
    """Candidate column labels, most specific first. A quarter-end month can appear as its month, its
    quarter, or (December) its year; the level tables show the end-of-period value under each."""
    y, m = period_end.year, period_end.month
    if period_type == "M":
        cands = [f"{MONTHS[m - 1]} {y}"]
        if m % 3 == 0:
            cands.append(f"Q{m // 3} {y}")
        if m == 12:
            cands.append(str(y))
        return cands
    if period_type == "Q":
        return [f"Q{(m - 1) // 3 + 1} {y}"]
    raise ValueError(period_type)


def oldest_month(row: dict[str, str]) -> dt.date | None:
    """The end of the oldest month column ('Jul 2026') a page row prints, or None if it prints no month."""
    months = []
    for key in row:
        m = re.fullmatch(r"([A-Z][a-z]{2}) (20\d\d)", key)
        if m and m.group(1) in MONTHS:
            y, mo = int(m.group(2)), MONTHS.index(m.group(1)) + 1
            months.append(dt.date(y + mo // 12, mo % 12 + 1, 1) - dt.timedelta(days=1))
    return min(months) if months else None


def release_date(page: str) -> dt.date | None:
    """The 'Release Date: September 8, 2026' line every G.19 page carries."""
    plain = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())
    m = re.search(r"Release Date(?:\s*\*)?\s*:\s*([A-Z][a-z]+ \d{1,2}, \d{4})", plain)
    if not m:
        return None
    try:
        return dt.datetime.strptime(m.group(1), "%B %d, %Y").date()
    except ValueError:
        return None


def rebased_entry(e: dict, value: float, column: str, released: dt.date) -> dict:
    """The entry with the value the current release prints, citing that release's dated page."""
    out = dict(e)
    old_release = re.search(r"release of (\d{4}-\d\d-\d\d)", str(e.get("origin", "")))
    was = f"{e['expected']} in the {old_release.group(1)} release" if old_release else f"was {e['expected']}"
    out["expected"] = value
    out["origin"] = f"Fed G.19 release of {released.isoformat()}, '{column}' column ({was}; re-based by verify_g19.py --rebase)"
    out["origin_url"] = f"https://www.federalreserve.gov/releases/g19/{released:%Y%m%d}/default.htm"
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    p.add_argument("--provenance", action="store_true", help="check each entry against the dated page it cites")
    p.add_argument("--rebase", action="store_true", help="print a re-based YAML candidate for each FAIL on the current page")
    args = p.parse_args(sys.argv[1:] if argv is None else argv)
    if args.provenance and args.rebase:
        p.error("--rebase cannot be combined with --provenance")
    provenance = args.provenance
    rebase = args.rebase
    candidates: list[dict] = []
    root = Path(__file__).resolve().parents[1]
    golden_path = root / "checks" / "golden.yaml"
    try:
        raw_entries = yaml.safe_load(golden_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"ERROR could not read {golden_path}: {exc}")
        return 1
    entries = [] if raw_entries is None else raw_entries
    if not isinstance(entries, list):
        print(f"ERROR {golden_path} must be a YAML list, not {type(entries).__name__}")
        return 1
    load_dotenv(root / ".env")  # CARDDASH_CONTACT, for the pipeline's own User-Agent
    session = make_session()
    pages: dict[str, list] = {}

    released: dict[str, dt.date] = {}

    def tables_for(url: str) -> list:
        if url not in pages:
            page = fetch_or_die(session, url).text
            when = release_date(page)
            if when is None:
                raise CheckFailed(f"{url} carries no 'Release Date': not a G.19 release page")
            pages[url] = parse_tables(page)
            released[url] = when
        return pages[url]

    bad = passed = aged = missing = 0
    try:
        for e in entries:
            if not isinstance(e, dict):
                raise CheckFailed(f"malformed entry in {golden_path}: expected mapping, got {type(e).__name__}")
            if "/releases/g19/" not in str(e.get("origin_url", "")):
                continue
            try:
                eid = str(e["id"])
                metric = str(e["metric"])
                entity = str(e["entity"])
                period_type = str(e["period_type"])
                period_end = dt.date.fromisoformat(str(e["period_end"]))
                expected = float(e["expected"])
                tolerance = float(e.get("tolerance", 0))
            except (KeyError, TypeError, ValueError) as exc:
                raise CheckFailed(f"malformed G.19 golden entry {e.get('id', '?')}: {exc}") from exc
            if not (math.isfinite(expected) and math.isfinite(tolerance) and tolerance >= 0):
                raise CheckFailed(f"malformed expected/tolerance in {eid}")
            key = (metric, entity) if (metric, entity) in ROW_FOR_METRIC else metric
            if key not in ROW_FOR_METRIC:
                missing += 1
                print(f"MISSING {eid}: no page row mapped for {key} in ROW_FOR_METRIC")
                continue
            url = e["origin_url"] if provenance else G19_URL
            tables = tables_for(url)
            label, kind = ROW_FOR_METRIC[key]
            row = find_row(tables, label, kind)
            cands = columns_for(period_end, period_type)
            col, got = None, None
            for c in cands:
                got = _num(row.get(c, "")) if row else None
                if got is not None:
                    col = c
                    break
            if got is None:
                if provenance:  # the cited release must show the cited period: not finding it is a broken citation
                    bad += 1
                    print(f"FAIL {eid}: none of {cands} on {url}")
                    continue
                oldest = oldest_month(row) if row else None
                if oldest and period_end < oldest:
                    # the page prints only its last few months (and quarter and year ends): an older month has aged
                    # off it, which is expected, and --provenance still checks it against the release it cites
                    aged += 1
                    print(f"SKIP {eid}: {cands[0]} is older than the page's oldest month ({oldest:%b %Y})")
                    continue
                missing += 1  # the row or the column should be there and is not: the layout may have changed
                where = f"no '{label}' row" if not row else f"none of {cands}, though the page runs from {oldest:%b %Y}" \
                    if oldest else f"none of {cands}"
                print(f"MISSING {eid}: {where} on the current page")
                continue
            ok = abs(got - expected) <= tolerance
            bad += 0 if ok else 1
            passed += 1 if ok else 0
            where = url.split("/releases/g19/")[1].split("/")[0]
            print(f"{'PASS' if ok else 'FAIL'} {eid}: page {got} vs golden {e['expected']} (column {col}, {where})")
            if rebase and not ok:
                candidates.append(rebased_entry(e, got, col, released[url]))
    except CheckFailed as exc:
        print(f"ERROR {exc}. Nothing after this was checked.")
        return 1
    what = "the release each entry cites" if provenance else "the current release page"
    checked = passed + bad
    print(f"{checked} checked ({passed} PASS, {bad} FAIL), {aged} aged off the page, {missing} missing")
    if checked == 0:
        print("0 entries checked: nothing was compared, so nothing is known to match")
        return 1
    if missing:
        print(f"{missing} entr{'y' if missing == 1 else 'ies'} could not be found on {what}: has its layout changed?")
        return 1
    if not provenance and aged > checked:
        print(f"too many entries aged off the page ({aged} skipped vs {checked} checked): has its layout changed?")
        return 1
    print(f"all checked entries match {what}" if not bad else f"{bad} mismatch(es)")
    if candidates:
        print("\n# Re-based entries for checks/golden.yaml. Read each number on the page first; if a LIVE entry sits")
        print("# inside the revision window (golden.MIN_LIVE_AGE_MONTHS), make it fixture-only instead.")
        print(yaml.safe_dump(candidates, sort_keys=False, allow_unicode=True, width=200))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
