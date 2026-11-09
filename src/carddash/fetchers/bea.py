"""BEA Personal Consumption Expenditures by type of product: the keyless NIPA monthly flat file.

Publication facts, verified 2026-09-08:
- https://apps.bea.gov/national/Release/TXT/NipaDataM.txt is the whole monthly NIPA dataset as one CSV: a header
  line '%SeriesCode,Period,Value', then one line per series and month, values quoted with thousands commas
  ('DPCERC,2026M07,"22,250,420"'). About 36.7 MB, 2,667 series, 1959M01 to the latest month, no key, no gate.
  SeriesRegister.txt next to it maps codes to table lines (DPCERC is Table 2.4.5U line 1 and many others).
- Levels are millions of dollars at seasonally adjusted annual rates (SAAR). The fetcher scales to billions
  (series.csv scale 0.001) and the metric names carry 'saar' so nobody compares them with a monthly sales figure.
- The release is the Personal Income and Outlays report, about four weeks after the month (July 2026 on August
  26). The release page and its 'historical comparisons' workbook state monthly dollar changes, not levels, so the
  goldens are change-from-prior-month entries (checks/golden.yaml, change_from_prior: true).
- An unknown file name returns an HTML page with status 200, so the first line is checked, not the status.

Raw-snapshot deviation, documented in CLAUDE.md: committing 36.7 MB a day would swamp the repository, so the file
under raw_dir/latest/ is the subset of lines for the series in crosswalks/series.csv (source bea), header included,
in the file's own format. The full file is parsed in memory and never written.

Conditional GET (REVIEW.md bigger improvement 5): the full file was downloaded every night, 36.9 MB, although BEA
changes it a few times a month. The server sends an ETag and a Last-Modified, so the fetcher keeps them next to the
subset (raw_dir/latest/NipaDataM-validators.json, with the series codes the subset was cut for) and asks again with
If-None-Match and If-Modified-Since. A 304 means the file is unchanged since that subset was cut, and the subset is
parsed as it stands. A change to the series list, or a missing subset or validator file, downloads in full.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pandas as pd

from ..schema import FACT_COLUMNS, last_day

SOURCE = "bea"
FILE_URL = "https://apps.bea.gov/national/Release/TXT/NipaDataM.txt"
LANDING_URL = "https://www.bea.gov/data/consumer-spending/main"
RAW_NAME = "NipaDataM-subset.txt"
VALIDATORS_NAME = "NipaDataM-validators.json"  # ETag and Last-Modified of the file the subset was cut from
HEADER = "%SeriesCode,Period,Value"
ENTITY = "US_HOUSEHOLDS"

_PERIOD_RE = re.compile(r"^(\d{4})M(\d{2})$")


def parse_period(text: str) -> pd.Timestamp:
    """'2026M07' -> the last day of July 2026."""
    m = _PERIOD_RE.match(text.strip())
    if not m or not 1 <= int(m.group(2)) <= 12:
        raise ValueError(f"not a YYYYMmm period: {text!r}")
    return pd.Timestamp(last_day(int(m.group(1)), int(m.group(2))))


def parse_value(text: str) -> float:
    """'"22,250,420"' -> 22250420.0. Blank or non-numeric fails."""
    t = text.strip().strip('"').replace(",", "")
    if not t or t.lower() in ("na", "n/a", "..."):
        raise ValueError(f"not a number: {text!r}")
    return float(t)


def subset_lines(text: str, codes: set[str]) -> list[str]:
    """The header plus every line whose series code is in `codes`, in file order."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != HEADER:
        raise ValueError(f"NipaDataM.txt does not start with {HEADER!r}: {lines[:1]!r}")
    out = [HEADER]
    for line in lines[1:]:
        code = line.split(",", 1)[0]
        if code in codes:
            out.append(line)
    return out


def parse_subset(text: str, meta: pd.DataFrame, pulled_at: str) -> pd.DataFrame:
    """Subset text -> facts, one series per crosswalk row. Every code must be present and end on the same month,
    and every series must be consecutive months."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != HEADER:
        raise ValueError(f"subset does not start with {HEADER!r}")
    by_code: dict[str, list[tuple[pd.Timestamp, float]]] = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        code, period, value = line.split(",", 2)
        by_code.setdefault(code, []).append((parse_period(period), parse_value(value)))
    frames = []
    ends = {}
    for _, row in meta.iterrows():
        code = row["source_id"]
        obs = by_code.get(code)
        if not obs:
            raise ValueError(f"{code}: no rows in NipaDataM.txt")
        obs.sort()
        dates = [d for d, _ in obs]
        for a, b in zip(dates, dates[1:]):
            if (b.year * 12 + b.month) - (a.year * 12 + a.month) != 1:
                raise ValueError(f"{code}: months jump from {a.date()} to {b.date()}")
        ends[code] = dates[-1]
        scale = float(row["scale"]) if row["scale"] not in ("", None) else 1.0
        frames.append(
            pd.DataFrame(
                {
                    "metric": row["metric"],
                    "entity": row["entity"],
                    "entity_type": row["entity_type"],
                    "tier": row["tier"],
                    "period_end": dates,
                    "period_type": row["period_type"],
                    "value": [v * scale for _, v in obs],
                    "source": SOURCE,
                    "pulled_at": pulled_at,
                }
            )[FACT_COLUMNS]
        )
    if len(set(ends.values())) != 1:
        raise ValueError(f"series end on different months: {ends}")
    return pd.concat(frames, ignore_index=True)


def _conditional_headers(latest: Path, codes: set[str]) -> dict[str, str]:
    """If-None-Match / If-Modified-Since for the file the subset on disk was cut from, or {} to download in full."""
    path = latest / VALIDATORS_NAME
    if not (path.exists() and (latest / RAW_NAME).exists()):
        return {}
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    if set(saved.get("codes", [])) != codes:
        return {}  # the series list changed: the subset on disk lacks a series, so cut a new one
    headers = {}
    if saved.get("etag"):
        headers["If-None-Match"] = saved["etag"]
    if saved.get("last_modified"):
        headers["If-Modified-Since"] = saved["last_modified"]
    return headers


def fetch(meta: pd.DataFrame, raw_dir: Path, session, pulled_at: str) -> pd.DataFrame:
    codes = set(meta["source_id"])
    latest = raw_dir / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    conditional = _conditional_headers(latest, codes)
    resp = session.get(FILE_URL, headers=conditional) if conditional else session.get(FILE_URL)
    if resp.status_code == 304 and conditional:
        # unchanged since the subset on disk was cut from it: about 37 MB not downloaded
        return parse_subset((latest / RAW_NAME).read_text(encoding="utf-8"), meta, pulled_at)
    resp.raise_for_status()
    lines = subset_lines(resp.text, codes)  # also checks the header, so an HTML error page fails here
    text = "\n".join(lines) + "\n"
    (latest / RAW_NAME).write_text(text, encoding="utf-8", newline="\n")  # saved before parsing, like every fetcher
    facts = parse_subset(text, meta, pulled_at)
    # The validators are written only after the subset parsed: a subset that failed keeps the old validators, which
    # no longer match the server's file, so the next run downloads in full instead of trusting a bad cut.
    validators = {"etag": resp.headers.get("ETag"), "last_modified": resp.headers.get("Last-Modified"),
                  "codes": sorted(codes)}
    path = latest / VALIDATORS_NAME
    if validators["etag"] or validators["last_modified"]:
        body = json.dumps(validators, indent=1) + "\n"
        if not path.exists() or path.read_text(encoding="utf-8") != body:
            path.write_text(body, encoding="utf-8", newline="\n")
    else:
        path.unlink(missing_ok=True)  # nothing to ask with next time
    return facts
