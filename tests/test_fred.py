"""FRED fetcher: parsing checked-in raw files, period mapping, scaling, missing values, and failing without
publishing the API key."""

from __future__ import annotations

import http.server
import socket
import threading

import pandas as pd

import datetime as dt

import pytest
import requests

from carddash.cli import write_health
from carddash.fetchers import fred
from carddash.loader import refresh_source
from carddash.schema import empty_facts, shift_period
from conftest import FIXTURES, PULLED_AT

FAKE_KEY = "fake0key0for0tests0only0abcdef12"  # 32 characters like a real one; not a real key


class _BadRequest(http.server.BaseHTTPRequestHandler):
    """Answers every request the way FRED answers a bad key: HTTP 400 and a JSON error."""

    def do_GET(self):  # noqa: N802 - the name http.server dispatches on
        body = b'{"error_code":400,"error_message":"Bad Request.  The value for variable api_key is not registered."}'
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def bad_request_url():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _BadRequest)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}/fred/series/observations"
    finally:
        srv.shutdown()
        srv.server_close()


def _closed_port_url() -> str:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"http://127.0.0.1:{port}/fred/series/observations"  # nothing listens here once the socket closes


@pytest.mark.parametrize("failure", ["http_400", "connection_refused"])
def test_a_failed_fred_request_never_writes_the_api_key(failure, bad_request_url, monkeypatch, meta, tmp_paths):
    """requests puts the whole URL, query string included, into the text of an HTTPError or ConnectionError, and FRED
    takes its key in the query string. The loader stores that text in health.json, which the job commits to this
    public repository and the page prints. GitHub masks secrets in the Actions log only, not in committed files."""
    monkeypatch.setenv("FRED_API_KEY", FAKE_KEY)
    monkeypatch.setattr(fred, "API_URL", bad_request_url if failure == "http_400" else _closed_port_url())
    _, health, _ = refresh_source("fred", empty_facts(), meta, fred.fetch, tmp_paths.raw / "fred",
                                  requests.Session(), dt.date(2026, 9, 8), PULLED_AT, set())
    assert health.status == "failed"
    text = " | ".join(health.messages)
    assert "REVOLSL" in text  # the message still says which series failed
    assert FAKE_KEY not in text and "api_key=" not in text
    if failure == "http_400":
        assert "HTTP 400" in text and "is not registered" in text  # and why, in FRED's own words
    write_health(tmp_paths, {"fred": health}, PULLED_AT)
    written = tmp_paths.health_json.read_text(encoding="utf-8")
    assert "REVOLSL" in written and FAKE_KEY not in written and "api_key=" not in written


def _row(meta, sid):
    return meta[(meta["source"] == "fred") & (meta["source_id"] == sid)].iloc[0]


def test_revolsl_month_end_and_billions(meta):
    obs = fred.parse_fredgraph((FIXTURES / "fred" / "REVOLSL.csv").read_text())
    facts = fred.to_facts(obs, _row(meta, "REVOLSL"), PULLED_AT)
    assert facts["metric"].unique().tolist() == ["revolving_credit_sa"]
    assert facts["period_type"].unique().tolist() == ["M"]
    assert facts["entity_type"].unique().tolist() == ["aggregate"]
    june = facts[facts["period_end"] == pd.Timestamp("2026-06-30")]
    assert len(june) == 1
    # G.19 release table (2026-09-08) shows June 2026 revolving, SA = $1,354.4 bn (revised from 1,351.1 on 2026-08-07)
    assert abs(june["value"].iloc[0] - 1354.4) < 0.06
    # every period_end is a month end
    assert (facts["period_end"] == facts["period_end"] + pd.offsets.MonthEnd(0)).all()


def test_quarterly_survey_month_maps_to_quarter_end(meta):
    obs = fred.parse_fredgraph((FIXTURES / "fred" / "TERMCBCCALLNS.csv").read_text())
    facts = fred.to_facts(obs, _row(meta, "TERMCBCCALLNS"), PULLED_AT)
    q2 = facts[facts["period_end"] == pd.Timestamp("2026-06-30")]
    assert len(q2) == 1 and abs(q2["value"].iloc[0] - 20.94) < 0.006
    q1 = facts[facts["period_end"] == pd.Timestamp("2026-03-31")]
    assert len(q1) == 1 and abs(q1["value"].iloc[0] - 21.00) < 0.006
    # blank padding rows (non-survey months) must not become facts
    assert not facts.duplicated(["period_end"]).any()


def test_rate_surveys_must_sit_in_the_middle_month_of_the_quarter():
    """v_apr_spread pairs the card rate with the prime rate of its survey month, so a reading FRED dated to another
    month must stop the fetch instead of shifting that pairing silently."""
    for sid in fred.MID_QUARTER_SURVEYS:
        obs = fred.parse_fredgraph((FIXTURES / "fred" / f"{sid}.csv").read_text())
        assert set(obs["date"].dt.month) == fred.MID_QUARTER_MONTHS, sid
        fred.check_survey_months(sid, obs)  # the whole history passes
    moved = pd.DataFrame({"date": pd.to_datetime(["2026-05-01", "2026-09-01"]), "value": [22.15, 22.36]})
    with pytest.raises(ValueError, match="2026-09"):
        fred.check_survey_months("TERMCBCCINTNS", moved)
    fred.check_survey_months("REVOLSL", moved)  # a monthly series is not a survey: no constraint


def test_sloos_is_dated_to_the_quarter_it_asks_about(meta):
    """FRED dates the July 2026 survey to 2026-07-01 (Q3); it asks about April to June, so it lands on 2026-06-30."""
    obs = fred.parse_fredgraph((FIXTURES / "fred" / "DRTSCLCC.csv").read_text())
    row = _row(meta, "DRTSCLCC")
    assert int(row["period_offset"]) == -1
    assert obs[obs["date"] == pd.Timestamp("2026-07-01")]["value"].iloc[0] == 6.7
    facts = fred.to_facts(obs, row, PULLED_AT).set_index("period_end")["value"]
    assert facts[pd.Timestamp("2026-06-30")] == 6.7
    assert facts[pd.Timestamp("2026-03-31")] == 2.0
    assert facts[pd.Timestamp("1995-12-31")] == 25.0  # the January 1996 survey describes 1995 Q4
    assert facts.index.max() == pd.Timestamp("2026-06-30")  # nothing dated to a quarter that has not ended
    assert (facts.index == facts.index + pd.offsets.QuarterEnd(0)).all()
    # only the four SLOOS series carry an offset; every other FRED series keeps its dating
    offset = meta.loc[(meta["source"] == "fred") & (meta["period_offset"] != 0), "source_id"].tolist()
    assert sorted(offset) == ["DEMCC", "DRTSCLCC", "SUBLPDCLCDLGNQ", "SUBLPDCLCDOTHNQ"]


def test_sloos_demand_is_the_net_of_the_release_table(meta):
    """July 2026 SLOOS Table 1, question 24: 13.3% moderately stronger minus 11.1% moderately weaker = 2.2, dated Q2."""
    for sid, expected in (("DEMCC", 2.2), ("SUBLPDCLCDLGNQ", 0.0), ("SUBLPDCLCDOTHNQ", 3.8)):
        obs = fred.parse_fredgraph((FIXTURES / "fred" / f"{sid}.csv").read_text())
        facts = fred.to_facts(obs, _row(meta, sid), PULLED_AT).set_index("period_end")["value"]
        assert facts[pd.Timestamp("2026-06-30")] == expected, sid
        assert facts.index.max() == pd.Timestamp("2026-06-30")
        assert facts.index.min() == pd.Timestamp("2011-03-31")  # the April 2011 survey describes 2011 Q1


def test_g19_holders_are_billions_nsa_and_sum_below_the_total(meta):
    """The G.19 holder table (NSA, billions): depository 1,219.7, credit unions 88.3, finance companies 16.3 at end-2025."""
    total = 0.0
    for sid, expected in (("REVOLNDI", 1219.7), ("REVOLNCU", 88.3), ("REVOLNFC", 16.3)):
        obs = fred.parse_fredgraph((FIXTURES / "fred" / f"{sid}.csv").read_text())
        row = _row(meta, sid)
        assert row["metric"] == "revolving_credit_nsa" and not row["sa"]
        facts = fred.to_facts(obs, row, PULLED_AT).set_index("period_end")["value"]
        assert abs(facts[pd.Timestamp("2025-12-31")] - expected) < 0.06, sid
        total += facts[pd.Timestamp("2025-12-31")]
    # the three holders are most of revolving credit (nonfinancial business and the federal government are the rest)
    assert 1300 < total < 1400


@pytest.mark.parametrize(
    "date, pt, n, expected",
    [
        (dt.date(2026, 7, 1), "Q", -1, dt.date(2026, 6, 30)),
        (dt.date(2026, 9, 30), "Q", -1, dt.date(2026, 6, 30)),
        (dt.date(2026, 1, 15), "Q", -1, dt.date(2025, 12, 31)),
        (dt.date(2026, 1, 15), "Q", 0, dt.date(2026, 3, 31)),
        (dt.date(2026, 1, 15), "Q", 2, dt.date(2026, 9, 30)),
        (dt.date(2026, 11, 3), "M", 2, dt.date(2027, 1, 31)),
        (dt.date(2025, 12, 31), "H", -1, dt.date(2025, 6, 30)),
        (dt.date(2026, 6, 30), "T", 1, dt.date(2026, 10, 31)),  # a survey wave shifts to the next wave month
        (dt.date(2026, 6, 30), "T", -3, dt.date(2025, 6, 30)),  # three waves back is a year
        (dt.date(2026, 2, 28), "T", -1, dt.date(2025, 10, 31)),
        (dt.date(2026, 5, 1), "A", -2, dt.date(2024, 12, 31)),
        (dt.date(2026, 8, 26), "W", -1, dt.date(2026, 8, 19)),
        (dt.date(2026, 8, 26), "D", 3, dt.date(2026, 8, 29)),
    ],
)
def test_shift_period(date, pt, n, expected):
    assert shift_period(date, pt, n) == expected


def test_weekly_keeps_its_date(meta):
    obs = fred.parse_fredgraph((FIXTURES / "fred" / "CCLACBW027SBOG.csv").read_text())
    facts = fred.to_facts(obs, _row(meta, "CCLACBW027SBOG"), PULLED_AT)
    assert facts["period_type"].unique().tolist() == ["W"]
    last = facts.sort_values("period_end").iloc[-1]
    assert last["period_end"] == pd.Timestamp("2026-08-26")
    assert abs(last["value"] - 1089.7912) < 1e-6
    assert last["period_end"].day_name() == "Wednesday"


def test_weekly_claims_are_thousands_on_their_saturday(meta):
    """DOL weekly claims release of 2026-09-10: initial claims 206,000 in the week ending September 5 (advance)."""
    obs = fred.parse_fredgraph((FIXTURES / "fred" / "ICSA.csv").read_text())
    facts = fred.to_facts(obs, _row(meta, "ICSA"), PULLED_AT)
    assert facts["period_type"].unique().tolist() == ["W"]
    last = facts.iloc[-1]
    assert last["period_end"] == pd.Timestamp("2026-09-05") and last["period_end"].day_name() == "Saturday"
    assert abs(last["value"] - 206.0) < 1e-9
    cont = fred.to_facts(fred.parse_fredgraph((FIXTURES / "fred" / "CCSA.csv").read_text()), _row(meta, "CCSA"), PULLED_AT)
    assert cont.iloc[-1]["period_end"] == pd.Timestamp("2026-08-29") and abs(cont.iloc[-1]["value"] - 1774.0) < 1e-9


def test_missing_markers_are_dropped():
    text = "observation_date,X\n2020-01-01,1.5\n2020-02-01,.\n2020-03-01,\n2020-04-01,2.5\n"
    obs = fred.parse_fredgraph(text)
    assert obs["value"].tolist() == [1.5, 2.5]


def test_fredgraph_rejects_html():
    try:
        fred.parse_fredgraph("<!DOCTYPE html><html></html>")
    except ValueError:
        return
    raise AssertionError("expected ValueError on HTML input")


def test_api_json_snapshot_is_date_independent():
    a = '{"realtime_start":"2026-09-07","realtime_end":"2026-09-07","count":1,"observations":[{"realtime_start":"2026-09-07","realtime_end":"2026-09-07","date":"2020-01-01","value":"1.5"}]}'
    b = a.replace("2026-09-07", "2026-09-08")
    assert fred.normalize_api_json(a) == fred.normalize_api_json(b)
    assert '"date":"2020-01-01","value":"1.5"' in fred.normalize_api_json(a)
    assert fred.parse_api_json(fred.normalize_api_json(a))["value"].tolist() == [1.5]
    # the same number formatted two ways by different FRED servers must snapshot identically
    c = a.replace('"1.5"', '"1247630.0500000000"')
    d = a.replace('"1.5"', '"1247630.05"')
    assert fred.normalize_api_json(c) == fred.normalize_api_json(d)
    assert '"value":"1247630.05"' in fred.normalize_api_json(c)
    assert '"value":"1000"' in fred.normalize_api_json(a.replace('"1.5"', '"1000.000"'))  # no scientific notation
    assert '"value":"."' in fred.normalize_api_json(a.replace('"1.5"', '"."'))


def test_api_json_parse():
    text = '{"observations":[{"date":"2020-01-01","value":"1.5"},{"date":"2020-02-01","value":"."}]}'
    obs = fred.parse_api_json(text)
    assert obs["value"].tolist() == [1.5]
    assert obs["date"].iloc[0] == pd.Timestamp("2020-01-01")
