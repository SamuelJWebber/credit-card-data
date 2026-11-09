"""FRED fetcher: Fed G.19 consumer credit, H.8 bank card loans, charge-off/delinquency rates, SLOOS.

Two transports, same parse:
- with FRED_API_KEY set: the official observations API (JSON)
- without: the public fredgraph.csv endpoint, which needs no key

Series list and metadata come from crosswalks/series.csv (source == "fred").
"""

from __future__ import annotations

import io
import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
import requests

from ..redact import redact
from ..schema import FACT_COLUMNS, period_end, shift_period

SOURCE = "fred"
FREDGRAPH_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
API_URL = "https://api.stlouisfed.org/fred/series/observations"

# The G.19 interest-rate surveys are taken in the middle month of each quarter, and FRED dates each reading to that
# month (2026-08-01 for Q3). to_facts moves them to the quarter end like any quarterly series, and v_apr_spread
# (sql/views.sql) compares the card rate with the prime rate of the month BEFORE the quarter end, its survey month.
# Every reading since 1972 sits in February, May, August or November; if FRED ever dated one differently, that
# pairing would drift by a month without a sound, so the fetch fails instead.
MID_QUARTER_SURVEYS = ("TERMCBCCALLNS", "TERMCBCCINTNS", "TERMCBAUTO48NS", "TERMCBPER24NS")
MID_QUARTER_MONTHS = {2, 5, 8, 11}


def check_survey_months(sid: str, obs: pd.DataFrame) -> None:
    if sid not in MID_QUARTER_SURVEYS or obs.empty:
        return
    odd = sorted({d.strftime("%Y-%m") for d in obs["date"] if d.month not in MID_QUARTER_MONTHS})
    if odd:
        raise ValueError(f"{sid}: survey readings dated outside the middle month of the quarter ({odd[:4]}); "
                         "v_apr_spread pairs each with the prime rate of that middle month")


def parse_fredgraph(text: str) -> pd.DataFrame:
    """fredgraph.csv -> DataFrame[date, value]. Missing values are '.', dropped."""
    df = pd.read_csv(io.StringIO(text), na_values=["."], dtype={0: str})
    if df.shape[1] != 2:
        raise ValueError(f"expected 2 columns from fredgraph, got {list(df.columns)}")
    date_col = df.columns[0]
    if date_col.lower() not in ("observation_date", "date"):
        raise ValueError(f"unexpected first column {date_col!r}")
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col], format="%Y-%m-%d"),
            "value": pd.to_numeric(df.iloc[:, 1], errors="coerce"),
        }
    )
    return out.dropna(subset=["value"]).reset_index(drop=True)


def parse_api_json(text: str) -> pd.DataFrame:
    """FRED API observations JSON -> DataFrame[date, value]."""
    payload = json.loads(text)
    obs = payload.get("observations")
    if obs is None:
        raise ValueError(f"no observations in API response: {str(payload)[:200]}")
    df = pd.DataFrame(obs)
    if df.empty:
        return pd.DataFrame({"date": pd.Series(dtype="datetime64[ns]"), "value": pd.Series(dtype="float64")})
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df["date"], format="%Y-%m-%d"),
            "value": pd.to_numeric(df["value"].replace(".", None), errors="coerce"),
        }
    )
    return out.dropna(subset=["value"]).reset_index(drop=True)


_REQUEST_ECHO_FIELDS = ("realtime_start", "realtime_end")


def normalize_api_json(text: str) -> str:
    """Drop the request-date echo fields the API stamps on every response and every observation.

    They always equal the request date for a non-vintage request, so they carry no data; leaving them in
    would change every raw snapshot every day and bury real revisions in the git history.
    """
    payload = json.loads(text)
    for k in _REQUEST_ECHO_FIELDS:
        payload.pop(k, None)
    for ob in payload.get("observations", []):
        for k in _REQUEST_ECHO_FIELDS:
            ob.pop(k, None)
        # FRED servers format the same number differently ('1247630.0500000000' vs '1247630.05'); canonicalize
        v = ob.get("value")
        if isinstance(v, str) and v not in (".", ""):
            try:
                ob["value"] = format(Decimal(v).normalize(), "f")
            except InvalidOperation:
                pass
    return json.dumps(payload, separators=(",", ":")) + "\n"


def to_facts(obs: pd.DataFrame, meta: pd.Series, pulled_at: str) -> pd.DataFrame:
    """Observations for one series -> facts rows, using the series.csv metadata row."""
    ptype = meta["period_type"]
    scale = float(meta["scale"]) if meta["scale"] not in ("", None) else 1.0
    offset = int(meta.get("period_offset", 0) or 0)  # series.csv: the SLOOS July survey describes Q2, not Q3
    df = pd.DataFrame(
        {
            "metric": meta["metric"],
            "entity": meta["entity"],
            "entity_type": meta["entity_type"],
            "tier": meta["tier"],
            "period_end": [pd.Timestamp(shift_period(d.date(), ptype, offset)) for d in obs["date"]],
            "period_type": ptype,
            "value": obs["value"].astype("float64") * scale,
            "source": SOURCE,
            "pulled_at": pulled_at,
        }
    )
    return df[FACT_COLUMNS]


def _api_error_detail(resp) -> str:
    """FRED's own error_message when it sent one (it names the problem, never the key), else ''."""
    try:
        msg = str(resp.json().get("error_message", "")).strip()
    except ValueError:
        return ""
    return f": {' '.join(redact(msg).split())[:200]}" if msg else ""


def _api_get(session, sid: str, api_key: str):
    """The observations request, with every failure re-raised WITHOUT the URL.

    The key travels in the query string, and requests writes the full URL into the text of an HTTPError
    ('400 Client Error: Bad Request for url: ...&api_key=...') and of a ConnectionError ('Max retries exceeded with
    url: ...'). The loader stores exception text in health.json, which the job commits to this public repository and
    the page prints, so never call raise_for_status() here and never chain the original exception.
    """
    try:
        resp = session.get(
            API_URL,
            params={
                "series_id": sid,
                "api_key": api_key,
                "file_type": "json",
                "observation_start": "1900-01-01",
            },
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"{sid}: FRED API request failed ({type(exc).__name__})") from None
    if not resp.ok:
        raise RuntimeError(f"{sid}: FRED API returned HTTP {resp.status_code}{_api_error_detail(resp)}")
    return resp


def _download(session, sid: str, raw_dir: Path, api_key: str | None) -> pd.DataFrame:
    raw_dir.mkdir(parents=True, exist_ok=True)
    if api_key:
        resp = _api_get(session, sid, api_key)
        (raw_dir / f"{sid}.csv").unlink(missing_ok=True)  # one snapshot per series, whichever transport
        (raw_dir / f"{sid}.json").write_text(normalize_api_json(resp.text), encoding="utf-8", newline="\n")
        return parse_api_json(resp.text)
    resp = session.get(FREDGRAPH_URL.format(sid=sid))
    resp.raise_for_status()
    if not resp.text.lstrip().lower().startswith(("observation_date", "date")):
        raise ValueError(f"{sid}: fredgraph returned something that is not a CSV (first bytes: {resp.text[:60]!r})")
    (raw_dir / f"{sid}.json").unlink(missing_ok=True)
    (raw_dir / f"{sid}.csv").write_text(resp.text, encoding="utf-8", newline="\n")
    return parse_fredgraph(resp.text)


def fetch(meta: pd.DataFrame, raw_dir: Path, session, pulled_at: str) -> pd.DataFrame:
    api_key = os.environ.get("FRED_API_KEY") or None
    frames = []
    for _, row in meta.iterrows():
        obs = _download(session, row["source_id"], raw_dir / "latest", api_key)
        if obs.empty:
            raise ValueError(f"{row['source_id']}: no observations")
        check_survey_months(row["source_id"], obs)
        frames.append(to_facts(obs, row, pulled_at))
    return pd.concat(frames, ignore_index=True)
