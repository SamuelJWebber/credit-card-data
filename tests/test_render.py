"""Rendering: the page is self-contained, embeds the data, opens on the latest readings, and every card carries its
footer, status, notes, checks and PNG where flagged. The numbers asserted come from the checked-in fixtures."""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
import shutil

import pandas as pd
import pytest
from PIL import Image

from carddash.loader import write_facts
from carddash.render import (
    BENCHMARK_LABEL,
    THESIS_NOTE,
    STATE_TILES,
    VIEW_BOUNDS,
    VIEW_BOUNDS_UNCHECKED,
    _check_bounds,
    _connect,
    PANELS,
    _benchmark,
    _missing_periods,
    _new_periods,
    _recessions,
    _health_rows,
    _rel_display,
    headlines,
    pair_texts,
    render,
)
from carddash.schema import SERIES_KEY, coerce_facts
from conftest import FIXTURES, PULLED_AT, REPO

RUN1 = "2026-09-06T00:00:00Z"
RUN2 = "2026-09-07T00:00:00Z"  # the fixtures' pulled_at
TODAY = dt.date(2026, 9, 8)
POST_CHARTS = {"revolving_level", "card_apr", "card_access", "card_nco", "hhdc_dq90_by_age", "debt_service", "dfa_credit_by_wealth"}
ALL_SOURCES = ("fred", "tccp", "phillyfed", "nyfed_hhdc", "fdic", "nyfed_sce", "nyfed_sce_monthly", "bea", "census", "ncua",
               "dfa", "cfpb_cct", "nyfed_state", "issuer_8k")


def _health(generated_at: str, sources=("fred",), status="ok") -> dict:
    return {
        "generated_at": generated_at,
        "sources": {
            s: {"source": s, "status": status, "messages": [], "last_period_end": "2026-08-26", "pulled_at": generated_at,
                "rows": 1, "n_series": 1, "n_revisions": 0}
            for s in sources
        },
    }


def _payload(html: str) -> dict:
    start = html.index("window.CARDDASH = ") + len("window.CARDDASH = ")
    return json.loads(html[start:html.index(";</script>", start)])


@pytest.fixture(scope="session")
def page(session_paths, fixture_facts):
    """The rendered page, built once for the whole session: every test that takes it only reads it."""
    write_facts(fixture_facts, session_paths.facts_csv)
    session_paths.health_json.write_text(json.dumps(_health(RUN2, ALL_SOURCES)), encoding="utf-8")
    html = render(session_paths, today=TODAY).read_text(encoding="utf-8")
    return html, _payload(html)


def test_page_is_self_contained_and_carries_every_chart(page):
    html, payload = page
    assert "uPlot" in html and "<script src=" not in html  # vendored, no runtime fetches
    for panel in PANELS:
        for c in panel["charts"]:
            assert f'data-chart="{c["id"]}"' in html
    assert [p["name"] for p in PANELS] == ["Growth", "Pricing", "Access", "Performance", "Borrowers", "Distribution", "Spend", "Context"]
    assert len(payload["charts"]) == sum(len(p["charts"]) for p in PANELS) == 78
    assert html.index("<h2>Access</h2>") > html.index("<h2>Pricing</h2>")
    assert html.index("<h2>Context</h2>") > html.index("<h2>Borrowers</h2>")
    assert payload["default_years"] == 5 and len(payload["recessions"]) == 8
    # the health strip sits below the charts, a one-line summary sits at the top
    assert html.index('<h2 id="health">Source health</h2>') > html.index("<h2>Context</h2>")
    assert "14 sources OK" in html.split('<h2 id="readings">Latest readings</h2>')[0]
    assert "Sources: FRED, Federal Reserve Bank of St. Louis; CFPB Terms of Credit Card Plans survey" in html


def test_fred_charts(page):
    html, payload = page
    by_id = {c["id"]: c for c in payload["charts"]}
    assert by_id["revolving_level"]["n_points"] > 600
    assert by_id["card_apr"]["n_points"] > 1000 and by_id["card_apr"]["period_type"] is None  # quarterly plus weekly
    assert 400 < by_id["revolving_yoy"]["n_points"] < 700  # v_growth works and the 'since' cut applies
    assert len(by_id["card_apr"]["footer_lines"]) == 3  # two cadences: one line per series
    assert "latest period 2026-09-02" in by_id["card_apr"]["footer"]  # the weekly advertised rate is the newest
    assert by_id["card_apr"]["status"] == "ok" and by_id["card_apr"]["attempted"] is None
    apr_only = by_id["card_nco"]  # one source, one cadence, and it has fixture rows
    assert "data as of 2026-09-07" in apr_only["footer"] and "data as of" not in apr_only["caption"]
    assert apr_only["caption"].startswith("Source: Federal Reserve Board, via FRED · quarterly · latest period 2026 Q2")
    assert apr_only["footer_lines"] == []  # one source, one cadence: nothing to split out
    # SLOOS is dated to the quarter it asks about: the July 2026 survey is 2026 Q2, nothing is in the future
    assert by_id["sloos_cards"]["n_points"] > 100 and "latest period 2026 Q2" in by_id["sloos_cards"]["footer"]


def test_offered_vs_paid_band_and_spread(page):
    html, payload = page
    ovp = {c["id"]: c for c in payload["charts"]}["offered_vs_paid"]
    assert len(ovp["series"]) == 6 and ovp["n_points"] > 10 and ovp["band"] == [1, 2]
    assert [s["unit"] for s in ovp["series"]] == ["pct", "pct", "pct", "pct", "pct", "pp"]
    assert ovp["series"][3]["dash"] and ovp["series"][5]["dash"]
    assert not ovp["series"][2]["dash"] and not ovp["series"][4]["dash"]
    assert "top 25 issuers" in ovp["series"][2]["label"]
    assert "all respondents" in ovp["series"][3]["label"]
    assert "percentage points" in ovp["series"][5]["label"]
    last = lambda k: max(i for i, v in enumerate(ovp["data"][k]) if v is not None)  # noqa: E731
    assert last(6) <= max(last(1), last(2), last(3))  # the spread stops at the last top-25 offered period
    assert last(5) > last(6)  # the paid rate runs on past it
    # the band is the range across the top-25 tiers: hi >= mid >= lo wherever all three exist
    for hi, lo, mid in zip(ovp["data"][1], ovp["data"][2], ovp["data"][3]):
        if hi is not None and lo is not None and mid is not None:
            assert hi >= mid >= lo
    assert len(ovp["footer_lines"]) == 6  # two sources and two cadences: one line per series
    assert "CFPB Terms of Credit Card Plans" in ovp["footer"] and "Federal Reserve Board" in ovp["footer"]
    assert any("secured cards" in n for n in ovp["notes"])
    assert any("720-and-up median is the lowest" in n for n in ovp["notes"])
    assert "sub-620 median is usually the lowest" not in html


def test_new_charts_draw_the_other_sources(page):
    html, payload = page
    by_id = {c["id"]: c for c in payload["charts"]}
    loans = by_id["card_loans_by_issuer"]
    assert [s["label"] for s in loans["series"]][:2] == ["Capital One (with Discover)", "JPMorgan Chase"]
    assert loans["n_points"] == 170 and any(v is not None for v in loans["data"][1])
    rates = by_id["nco_by_issuer"]
    assert len(rates["series"]) == 7 and rates["series"][6]["dash"]
    assert any(v is not None for v in rates["data"][7])  # the industry rate from the aggregate fixture
    tri = by_id["dq_triangulation"]
    assert len(tri["series"]) == 4 and tri["n_points"] > 80
    assert sum(1 for k in range(1, 5) if any(v is not None for v in tri["data"][k])) == 3  # no Fed 30+ fixture
    assert any("charged-off balances" in n.lower() or "charged-off" in n for n in tri["notes"])
    age = by_id["hhdc_dq90_by_age"]
    assert [s["label"] for s in age["series"]] == ["Ages 18-29", "Ages 30-39", "Ages 40-49", "Ages 50-59", "Ages 60-69", "Ages 70+"]
    assert age["n_points"] == 106 and age["post"]
    pay = by_id["y14_payment_behavior"]
    assert len(pay["series"]) == 4 and pay["series"][3]["benchmark"]  # three shares plus the benchmark
    scores = by_id["y14_origination_scores"]
    assert scores["y_zero"] is False and scores["unit"] == "score" and scores["n_points"] > 50
    assert by_id["card_apr"]["y_zero"] is True
    assert {c["id"] for c in payload["charts"] if c["post"]} == POST_CHARTS
    assert 'href="img/hhdc_dq90_by_age.png"' in html and 'href="img/card_dq.png"' in html  # every chart has a PNG


def test_derived_views_draw_the_context_charts(page):
    """The macro series and the views over them: burden, real balances, spread over prime, payment flows."""
    html, payload = page
    by_id = {c["id"]: c for c in payload["charts"]}
    # card debt as a share of income: quarterly points only, from a monthly-keyed view
    burden = by_id["card_debt_burden"]
    assert burden["n_points"] > 200 and len([v for v in burden["data"][1] if v is not None]) > 90
    assert burden["series"][1]["benchmark"]
    # nominal and real on one chart, equal at the latest CPI reading by construction
    real = by_id["revolving_real"]
    nom = [v for v in real["data"][1] if v is not None]
    defl = [v for v in real["data"][2] if v is not None]
    assert abs(len(nom) - len(defl)) <= 1 and len(defl) > 600  # the deflated line needs a CPI month to match
    assert abs(nom[-1] - defl[-1]) / nom[-1] < 0.01  # the base period is the latest CPI month
    assert defl[0] > nom[0] * 3  # 1968 dollars restated at today's prices
    # spread over prime
    spread = by_id["apr_over_prime"]
    assert len(spread["series"]) == 3 and spread["series"][2]["unit"] == "pp" and spread["series"][2]["dash"]
    apr, prime, sp = (spread["data"][k] for k in (1, 2, 3))
    pairs = [(a, p, s) for a, p, s in zip(apr, prime, sp) if a is not None and p is not None and s is not None]
    assert len(pairs) > 100 and all(abs((a - p) - s) < 1e-9 for a, p, s in pairs)
    # payment rate and revolver share from the Y-14 identity
    flows = by_id["y14_payment_flows"]
    assert len([v for v in flows["data"][1] if v is not None]) > 50
    assert all(55 < v < 130 for v in flows["data"][1] if v is not None)  # payment rate, percent of opening balance
    assert all(60 < v < 85 for v in flows["data"][2] if v is not None)  # revolving share of balances
    assert max(v for v in flows["data"][1] if v is not None) > 105  # the 2021-22 payment-rate spike clears 100
    # per-account credit: limit above unused above balance, every quarter
    per = by_id["per_account_credit"]
    rows = [(lim, avail, bal) for lim, avail, bal in zip(per["data"][1], per["data"][2], per["data"][3])
            if None not in (lim, avail, bal)]
    assert len(rows) > 90 and all(lim > avail > bal for lim, avail, bal in rows)
    assert all(abs(lim - avail - bal) < 1e-6 for lim, avail, bal in rows)
    # the Context panel
    assert by_id["debt_service"]["n_points"] == 85 and len(by_id["debt_service"]["series"]) == 2
    assert by_id["sentiment"]["y_zero"] is False and by_id["sentiment"]["unit"] == "index"
    assert by_id["consumer_credit_mix"]["n_points"] > 600
    assert by_id["losses_vs_labor"]["n_points"] > 400 and len(by_id["losses_vs_labor"]["series"]) == 2
    assert len(by_id["card_vs_consumer"]["series"]) == 4


def test_access_panel_draws_the_credit_access_survey(page):
    """The survey's own readings, and the gap between score bands that the aggregate hides."""
    html, payload = page
    by_id = {c["id"]: c for c in payload["charts"]}
    access = by_id["card_access"]
    assert len(access["series"]) == 4 and access["n_points"] == 39
    assert all(s["cadence"] == "every four months" for s in access["series"])
    assert "latest period Jun 2026" in access["footer"]  # a wave is labelled by the month it was fielded in
    rej = by_id["rejection_by_score"]
    labels = [s["label"] for s in rej["series"]]
    assert labels == ["Score under 680", "Score 680 to 760", "Score over 760"]
    sub, mid, top = (next(v for v in reversed(rej["data"][k]) if v is not None) for k in (1, 2, 3))
    assert sub > mid > top and sub > 40 and top < 5  # the June 2026 wave: 46.6, 11.1, 3.3
    # the back door: lender-initiated closures, and the households that never applied
    closures = by_id["lender_closures"]
    assert len(closures["series"]) == 3 and closures["n_points"] == 38  # the score split starts one wave later
    assert any("back door" in n for n in closures["notes"])
    assert any("never appear in any approval" in n for n in by_id["discouraged"]["notes"])
    # every survey chart names its sample-size caveat
    for cid in ("rejection_by_score", "lender_closures", "discouraged"):
        assert any("about 150 respondents" in n for n in by_id[cid]["notes"]), cid
    # the front door, and the size of the line behind it, from the Y-14 series
    mix = by_id["origination_mix"]
    accounts, dollars = (next(v for v in reversed(mix["data"][k]) if v is not None) for k in (1, 2))
    assert accounts > dollars * 3  # subprime is about a fifth of new accounts and a twenty-fifth of new credit lines
    limits = by_id["origination_limits"]
    sub, mid, top = (next(v for v in reversed(limits["data"][k]) if v is not None) for k in (1, 2, 3))
    assert sub < mid < top and limits["unit"] == "usd"


def test_benchmark_is_the_2015_2019_mean_of_the_first_series(page, fixture_facts):
    html, payload = page
    nco = {c["id"]: c for c in payload["charts"]}["card_nco"]
    assert len(nco["series"]) == 4 and nco["series"][3]["benchmark"] and nco["series"][3]["dash"]
    assert nco["series"][3]["label"] == f"All commercial banks, {BENCHMARK_LABEL}"
    line = nco["data"][4]
    assert len(set(line)) == 1
    s = fixture_facts[(fixture_facts["metric"] == "card_nco_rate_sa") & (fixture_facts["entity"] == "COMBANKS_ALL")]
    window = s[(s["period_end"] >= "2015-01-01") & (s["period_end"] <= "2019-12-31")]["value"]
    assert len(window) == 20 and line[0] == pytest.approx(window.mean())
    # a chart whose first series has no fixture rows gets no benchmark line
    dq = {c["id"]: c for c in payload["charts"]}["card_dq"]
    assert not any(s["benchmark"] for s in dq["series"])
    assert _benchmark([dt.date(2014, 12, 31), dt.date(2016, 6, 30), dt.date(2019, 12, 31), dt.date(2020, 3, 31)], [9.0, 1.0, 3.0, 9.0]) == 2.0
    assert _benchmark([dt.date(2021, 1, 1)], [1.0]) is None


def test_checks_list_the_golden_numbers_of_the_chart(page):
    html, payload = page
    by_id = {c["id"]: c for c in payload["charts"]}
    checks = by_id["revolving_level"]["checks"]
    assert len(checks) == 5 and all(c["ok"] for c in checks)
    assert checks[0]["period"] == "Jun 2026" and checks[0]["expected"] == 1354.4  # newest first
    assert checks[0]["origin_url"].startswith("https://www.federalreserve.gov/releases/g19/")
    assert "Checked against the release (5)" in html
    assert {c["id"] for c in by_id["card_apr"]["checks"]} == {
        "g19_card_apr_all_2026_q1", "g19_card_apr_all_2026_q2", "g19_card_apr_assessed_2026_q1", "g19_card_apr_assessed_2026_q2",
    }
    assert by_id["bank_card_loans_weekly"]["checks"] == []


def _set_value(facts: pd.DataFrame, metric: str, entity: str, period_end: str, value: float) -> None:
    hit = (facts["metric"] == metric) & (facts["entity"] == entity) & (facts["period_end"] == pd.Timestamp(period_end))
    assert hit.sum() == 1, (metric, entity, period_end)
    facts.loc[hit, "value"] = value


def test_a_revised_fixture_only_golden_is_drawn_neutrally_with_both_numbers(tmp_paths, fixture_facts):
    """REVIEW.md R1-5: the live page printed '✗ Revolving credit, SA, May 2026: 1348 per the release (got 1348)' for
    g19_revolving_sa_2026_05, which is fixture-only because the G.19 revised May from 1347.7 to 1347.84. A source
    revising a number it was never expected to hold is not a failure, and the format must not hide the difference.
    A LIVE entry that stops matching is still a failure, drawn as one."""
    facts = fixture_facts.copy()
    _set_value(facts, "revolving_credit_sa", "ALL_HOLDERS", "2026-05-31", 1347.8447)  # fixture-only entry, revised
    _set_value(facts, "revolving_credit_sa", "ALL_HOLDERS", "2025-12-31", 1325.0)  # live entry (1324.3), mismatched
    write_facts(facts, tmp_paths.facts_csv)
    tmp_paths.health_json.write_text(json.dumps(_health(RUN2, ALL_SOURCES)), encoding="utf-8")
    html = render(tmp_paths, today=TODAY).read_text(encoding="utf-8")
    charts = {c["id"]: c for c in _payload(html)["charts"]}
    checks = {k["id"]: k for k in charts["revolving_level"]["checks"]}
    may, dec = checks["g19_revolving_sa_2026_05"], checks["g19_revolving_sa_2025_12"]
    assert (may["state"], may["live"], may["expected_text"], may["actual_text"]) == ("revised", False, "1,347.7", "1,347.84")
    assert (dec["state"], dec["live"], dec["expected_text"], dec["actual_text"]) == ("mismatch", True, "1,324.3", "1,325.00")
    label = may["series_label"]
    assert f"{label}, May 2026: 1,347.7 as first published in" in html and "since revised to 1,347.84" in html
    assert not re.search(r"✗[^<]*May 2026", html)  # on neither chart that carries the entry
    assert f"✗ {dec['series_label']}, Dec 2025: 1,324.3 per" in html and "(got 1,325.00)" in html
    assert "e+0" not in html.split('<h2 id="changed">')[0].split("window.CARDDASH")[0]  # no %g notation in the cards


def test_numbers_on_the_page_are_never_in_scientific_notation_and_show_the_difference():
    assert pair_texts(14131.9, 13998.959) == ("14,132", "13,999")  # '%.4g' printed 1.413e+04 -> 1.4e+04
    assert pair_texts(1347.7, 1347.84) == ("1,347.7", "1,347.8")  # '%.4g' printed 1348 -> 1348
    assert pair_texts(0, 13) == ("0", "13") and pair_texts(1252, 1242) == ("1,252", "1,242")
    assert pair_texts(20.93, 20.94) == ("20.93", "20.94") and pair_texts(5.0001, 5.0002) == ("5.0001", "5.0002")


def test_the_health_strip_tells_a_failed_parse_from_a_late_release(fixture_facts):
    """REVIEW.md R1-10, from the page during the October 2026 outage: 'FDIC ... Failed ... 0 series, 0 rows' over
    28,942 rows still served, and 'Philly Fed ... 2026 Q2 data was expected around 2026-10-13 and has not appeared'
    when the files had been out since 2026-10-07 and it was the parser that failed."""
    late = dt.date(2026, 11, 9)  # the fixtures' Philly Fed release is 2026 Q1, so Q2 is overdue by then
    health = {
        "phillyfed": {"source": "phillyfed", "status": "failed", "rows": 0, "n_series": 0,
                      "status_since": "2026-10-08T01:39:00Z", "messages": ["fetch error: ValueError: header"]},
        "nyfed_hhdc": {"source": "nyfed_hhdc", "status": "ok", "rows": 5, "n_series": 2},
    }
    rows = {r["source"]: r for r in _health_rows(health, {}, fixture_facts, late)}
    ph = rows["phillyfed"]
    served = fixture_facts[fixture_facts["source"] == "phillyfed"]
    assert ph["rows"] == len(served) > 0 and ph["n_series"] == served.groupby(SERIES_KEY).ngroups and ph["kept"]
    assert ph["status_label"] == "Failed since 2026-10-08"
    assert ph["next"]["overdue"] and "has not appeared" not in ph["next"]["text"]
    assert ph["next"]["text"].endswith("the source failed to load, so a newer release could not be read")
    ok = rows["nyfed_hhdc"]
    assert (ok["rows"], ok["kept"], ok["status_label"]) == (5, False, "OK")  # an ok source keeps its own counts


def test_every_series_is_credited_to_its_publisher_not_to_the_fed(page):
    """REVIEW.md R1-8: every FRED series was captioned 'Federal Reserve Board, via FRED', on the page and on the PNGs
    made to be pasted into posts, Michigan's copyrighted sentiment index and Bankrate's survey included."""
    html, payload = page
    by_id = {c["id"]: c for c in payload["charts"]}
    sentiment = by_id["sentiment"]
    assert sentiment["caption"].startswith("Source: University of Michigan, via FRED · monthly")
    assert "Copyright, 2016, Surveys of Consumers, University of Michigan. Reprinted with permission." in sentiment["caption"]
    assert "Federal Reserve Board" not in sentiment["caption"]  # the caption is what the PNG prints
    apr = by_id["card_apr"]  # Fed G.19 and Bankrate on one chart: both named, and the separator keeps them apart
    assert apr["caption"].startswith("Source: Bankrate, via FRED; Federal Reserve Board, via FRED · ")
    assert "Copyright Bankrate, LLC." in apr["caption"]
    labor = by_id["losses_vs_labor"]
    assert "Bureau of Labor Statistics, via FRED" in labor["caption"]
    assert "Department of Labor, via FRED" in by_id["jobless_claims"]["caption"]
    for c in payload["charts"]:  # no chart drawn only from other publishers' series credits the Fed
        if all(s["source"] == "fred" and not s["source_label"].startswith("Federal Reserve Board")
               for s in c["series"] if not s["benchmark"]):
            assert "Federal Reserve Board" not in c["caption"], c["id"]
    # the series browser names the publisher too, and its source filter still has one option per source
    browse = {s["metric"]: s for s in payload["browse"]["series"]}
    assert browse["consumer_sentiment"]["source_label"] == "University of Michigan, via FRED"
    options = re.findall(r'<option value="([a-z_0-9]+)">', html)
    assert len(options) == len(set(options))


def test_the_page_says_when_it_has_gone_stale(page):
    """A run that fails before it renders leaves yesterday's page up, and the page cannot know that when it is built,
    so the reader's own clock decides: the banner is shown once the run stamp is more than 36 hours old."""
    html, _ = page
    top = html.split("</header>")[0]
    assert 'id="red-banner"' not in top  # every source is OK in the fixture health file
    assert f'id="stale-banner" role="status" hidden data-generated="{RUN2}"' in top
    script = top.split("<script>(function(){var b=document.getElementById('stale-banner')")[1].split("</script>")[0]
    assert "h<36" in script and "b.hidden=false" in script
    assert "/actions/workflows/refresh.yml" in top


def test_recessions_are_month_ranges():
    rec = _recessions()
    assert len(rec) == 8
    first, last = rec[0], rec[-1]
    epoch = dt.date(1970, 1, 1)
    assert epoch + dt.timedelta(seconds=first[0]) == dt.date(1969, 12, 1)
    assert epoch + dt.timedelta(seconds=first[1]) == dt.date(1970, 11, 30)
    assert epoch + dt.timedelta(seconds=last[0]) == dt.date(2020, 2, 1)
    assert epoch + dt.timedelta(seconds=last[1]) == dt.date(2020, 4, 30)


def test_latest_readings_are_computed_from_the_facts(page, session_paths, fixture_facts):
    html, payload = page
    items = headlines(fixture_facts, TODAY)
    labels = [h["label"] for h in items]
    assert labels[0].startswith("Revolving consumer credit") and len(items) == 15  # no 30+ delinquency fixture
    rev = items[0]["text"]
    # the 2026-09-08 G.19 vintage added July 2026 at $1,357bn, above the October 2024 peak, so the record flag fires
    assert rev == "$1,357bn in Jul 2026, +3.6% on the year, highest on record (since Jan 1968)"
    # the flag logic on a synthetic series: a record, a three-year high, and a value with no flag
    base = fixture_facts[(fixture_facts["metric"] == "revolving_credit_sa")].sort_values("period_end").copy()
    record = base.copy()
    record.loc[record["period_end"] == record["period_end"].max(), "value"] = 9999.0
    assert "highest on record (since Jan 1968)" in headlines(coerce_facts(record), TODAY)[0]["text"]
    low = base.copy()
    low.loc[low["period_end"] == low["period_end"].max(), "value"] = 0.5
    assert "lowest on record (since Jan 1968)" in headlines(coerce_facts(low), TODAY)[0]["text"]
    apr = next(h for h in items if h["label"].startswith("APR paid"))["text"]
    assert apr.startswith("22.15% in 2026 Q2, ") and "pp on the year" in apr and BENCHMARK_LABEL in apr
    sloos = next(h for h in items if h["label"].startswith("Banks tightening"))["text"]
    assert sloos.startswith("6.70% in 2026 Q2") and BENCHMARK_LABEL not in sloos  # a net balance has no benchmark
    assert ('<strong><a href="#revolving_level" title="Go to the chart">Revolving consumer credit, all lenders (Fed G.19, SA)</a>:</strong> $1,357bn in Jul 2026' in html)
    text = (session_paths.docs / "latest.txt").read_text(encoding="utf-8")  # written by the page fixture
    assert text.startswith("US credit card data, latest readings (") and "- Revolving consumer credit" in text
    assert 'href="latest.txt"' in html


def test_card_badge_and_last_attempt_when_a_source_is_not_ok(tmp_paths, fixture_facts):
    write_facts(fixture_facts, tmp_paths.facts_csv)
    health = _health(RUN2, ALL_SOURCES)
    health["sources"]["tccp"]["status"] = "stale"
    health["sources"]["fdic"]["status"] = "failed"
    health["sources"]["fdic"]["pulled_at"] = "2026-09-08T00:00:00Z"
    for source in ("issuer_8k", "nyfed_sce"):  # labels that begin 'Capital One,' and 'Federal Reserve Bank of New York,'
        health["sources"][source]["status"] = "failed"
    tmp_paths.health_json.write_text(json.dumps(health), encoding="utf-8")
    html = render(tmp_paths, today=TODAY).read_text(encoding="utf-8")
    by_id = {c["id"]: c for c in _payload(html)["charts"]}
    assert by_id["card_apr"]["status"] == "ok"
    assert by_id["offered_vs_paid"]["status"] == "stale" and by_id["offered_vs_paid"]["status_label"] == "Stale"
    assert by_id["nco_by_issuer"]["status"] == "failed" and by_id["nco_by_issuer"]["attempted"] == "2026-09-08"
    assert "data as of 2026-09-07" in by_id["nco_by_issuer"]["footer"]  # the data on the chart is still the last good load
    assert '<span class="badge st-failed"' in html and "last fetch attempt 2026-09-08" in html
    assert "4 of 14 sources need attention (Failed)" in html
    # a red source puts a banner at the top of the page, naming it (REVIEW.md bigger improvement 2) by a name that
    # says which source it is: the label cut at its first comma read 'Capital One' for all four issuers' filings and
    # 'Federal Reserve Bank of New York' for three sources (REVIEW.md R2-6)
    top = html.split("</header>")[0]
    assert ('<p class="banner" id="red-banner" role="alert"><strong>3 sources failed to load in the latest run</strong> '
            '(FDIC call reports; Issuer 8-K filings (Capital One, Synchrony, Bread, Amex); NY Fed SCE credit access '
            'survey).') in top


def test_png_export_is_byte_stable_and_carries_no_pull_date(tmp_paths, fixture_facts):
    write_facts(fixture_facts, tmp_paths.facts_csv)
    tmp_paths.health_json.write_text(json.dumps(_health(RUN2)), encoding="utf-8")
    render(tmp_paths, today=TODAY)
    img = tmp_paths.docs / "img"
    assert {p.stem for p in img.glob("*.png")} == {c["id"] for panel in PANELS for c in panel["charts"]}
    assert POST_CHARTS <= {p.stem for p in img.glob("*.png")}
    first = {p.name: p.read_bytes() for p in img.glob("*.png")}
    for name, data in first.items():
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert b"Software" not in data and b"2026-09-07" not in data
        with Image.open(img / name) as im:
            assert im.size == (1200, 675)
    # a second render of unchanged data, with a different health stamp, yields identical bytes
    tmp_paths.health_json.write_text(json.dumps(_health("2026-09-08T00:00:00Z")), encoding="utf-8")
    render(tmp_paths, today=TODAY)
    second = {p.name: p.read_bytes() for p in img.glob("*.png")}
    assert second == first


def test_what_changed_lists_only_the_latest_run(tmp_paths, fixture_facts):
    write_facts(fixture_facts, tmp_paths.facts_csv)
    shutil.copyfile(FIXTURES / "revisions.csv", tmp_paths.revisions_csv)
    tmp_paths.health_json.write_text(json.dumps(_health(RUN2)), encoding="utf-8")
    html = render(tmp_paths, today=TODAY).read_text(encoding="utf-8")
    assert "Latest run 2026-09-07 00:00 UTC" in html
    assert "3 values revised by the source, largest first (2 listed; revisions under 0.1% are only counted)" in html
    assert "Card balances (NY Fed CCP), 2026 Q1: 1,252 → 1,242 (0.80%)" in html
    assert "Issuers with a card above 30% purchase APR, 2025 H2: 0 → 13 (from 0)" in html  # old value 0: no percentage
    changed = html.split('<h2 id="changed">What changed</h2>')[1].split('<h2 id="health">')[0]
    assert "Card APR, all accounts" not in changed  # the 0.05% revision is counted, not listed
    assert "Card balances (Y-14 large banks)" not in changed  # run 1's revision is not shown
    assert 'href="data/revisions.csv"' in html and (tmp_paths.docs / "data" / "revisions.csv").exists()
    # every fixture row carries RUN2, so every source is a first load: new periods are summarized per cadence
    assert "New periods loaded in this run:" in html
    assert "FRED, Federal Reserve Bank of St. Louis: " in html and " monthly periods through Aug 2026" in html
    # keyed on the run: pointing health at run 1 lists run 1, even though run 2's rows are newer in the file
    tmp_paths.health_json.write_text(json.dumps(_health(RUN1)), encoding="utf-8")
    html = render(tmp_paths, today=TODAY).read_text(encoding="utf-8")
    assert "Latest run 2026-09-06 00:00 UTC" in html
    assert "3 values revised by the source, largest first (1 listed" in html
    assert "Card balances (Y-14 large banks), 2026 Q1: 940.0 → 948.7 (0.93%)" in html
    assert "No new periods in this run." in html  # no fixture row carries run 1's stamp
    # no health file yet: the block says so instead of guessing
    tmp_paths.health_json.unlink()
    assert "No refresh run recorded yet." in render(tmp_paths, today=TODAY).read_text(encoding="utf-8")


def test_a_period_that_has_not_ended_is_never_the_latest(tmp_paths, fixture_facts):
    future = fixture_facts[(fixture_facts["metric"] == "sloos_card_standards_net_tightening")].tail(1).copy()
    future["period_end"] = pd.Timestamp("2099-12-31")
    write_facts(pd.concat([fixture_facts, future], ignore_index=True), tmp_paths.facts_csv)
    tmp_paths.health_json.write_text(json.dumps(_health(RUN2)), encoding="utf-8")
    html = render(tmp_paths, today=TODAY).read_text(encoding="utf-8")
    sloos = next(c for c in _payload(html)["charts"] if c["id"] == "sloos_cards")
    assert sloos["series"][0]["last_period"] == "2026 Q2" and "latest period 2026 Q2" in sloos["footer"]
    assert sloos["data"][0][-1] > 4_000_000_000  # the row itself is still drawn, it is just not called latest
    assert "2099" not in html.split('<h2 id="changed">What changed</h2>')[0]  # neither the readings nor the cards call 2099 latest


def test_thesis_watch_evaluates_every_falsification_test(page, session_paths, fixture_facts):
    """The dated note names thresholds; the page checks them from the data and cannot pass one by default."""
    html, payload = page
    from carddash.render import THESIS_TESTS, _connect, thesis_status

    con = _connect(fixture_facts, REPO / "sql" / "views.sql", REPO / "data" / "raw" / "tccp" / "tccp_products.csv",
                   REPO / "crosswalks" / "issuers.csv")
    try:
        status = thesis_status(con, TODAY)
    finally:
        con.close()
    assert len(status) == len(THESIS_TESTS) == 3
    by_label = {t["label"]: t for t in status}
    flow = by_label["Flow into 90+ day delinquency stays below 7.5%"]
    assert flow["value"] == pytest.approx(6.97) and flow["period"] == "2026 Q2" and flow["holds"] is True
    nco = by_label["Card charge-off rate stays below 4.2%"]
    assert nco["value"] == pytest.approx(3.82) and nco["holds"] is True
    spread = by_label["Card APR margin over prime stays above 14 points"]
    assert spread["value"] == pytest.approx(15.40, abs=0.01) and spread["holds"] is True and spread["unit"] == "pp"
    assert all(t["why"] for t in status)
    # the page and the text file both carry it
    assert "Thesis watch" in html and "st-ok" in html.split("Thesis watch")[1][:400]
    assert THESIS_NOTE in html
    text = (session_paths.docs / "latest.txt").read_text(encoding="utf-8")  # written by the page fixture
    assert "Thesis of 2026-09-08 (holds)" in text and text.count("- [ok ]") == 3


def test_a_broken_thesis_test_says_so(tmp_paths, fixture_facts):
    """Push the charge-off rate above its threshold: the page must report the test broken, not quietly pass."""
    facts = fixture_facts.copy()
    latest = facts[(facts["metric"] == "card_nco_rate_sa") & (facts["entity"] == "COMBANKS_ALL")]["period_end"].max()
    hit = (facts["metric"] == "card_nco_rate_sa") & (facts["entity"] == "COMBANKS_ALL") & (facts["period_end"] == latest)
    facts.loc[hit, "value"] = 5.5
    write_facts(coerce_facts(facts), tmp_paths.facts_csv)
    tmp_paths.health_json.write_text(json.dumps(_health(RUN2, ALL_SOURCES)), encoding="utf-8")
    html = render(tmp_paths, today=TODAY).read_text(encoding="utf-8")
    watch = html.split("Thesis watch")[1][:1400]
    assert "st-failed" in watch and "Broken" in watch
    assert "this test has broken" in watch
    text = (tmp_paths.docs / "latest.txt").read_text(encoding="utf-8")
    assert "(BROKEN)" in text and "- [BROKEN]" in text


def test_browse_payload_covers_every_series_and_reconstructs_it(page, fixture_facts):
    """Every series in facts is browsable, and its compact encoding rebuilds the original values exactly."""
    from carddash.render import browse_payload
    from carddash.series import load_series, series_index

    html, payload = page
    b = payload["browse"]
    meta_idx = series_index(load_series(REPO / "crosswalks" / "series.csv"))
    direct = browse_payload(fixture_facts, meta_idx, TODAY)
    keys = {s["key"] for s in b["series"]}
    assert len(b["series"]) == len(direct["series"]) == len(keys)  # keys are unique
    in_facts = {"|".join(str(x) for x in k)
                for k in fixture_facts[SERIES_KEY].drop_duplicates().itertuples(index=False, name=None)}
    assert keys == in_facts  # nothing loaded is missing from the browser
    assert b["grids"] and all(g in b["grids"] for g in {s["grid"] for s in b["series"]})
    # rebuild one series from the grid and compare against facts
    one = next(s for s in b["series"] if s["key"].startswith("y14_card_utilization_active_p50|"))
    grid = b["grids"][one["grid"]]
    xs = grid[one["start"]: one["start"] + len(one["values"])]
    pairs = [(dt.datetime.fromtimestamp(x, dt.timezone.utc).date(), v)
             for x, v in zip(xs, one["values"]) if v is not None]
    src = fixture_facts[(fixture_facts["metric"] == "y14_card_utilization_active_p50")].sort_values("period_end")
    assert len(pairs) == len(src) == one["n"]
    assert [p[0] for p in pairs] == [d.date() for d in src["period_end"]]
    assert [p[1] for p in pairs] == [round(float(v), 6) for v in src["value"]]
    assert one["last_value"] == pytest.approx(float(src["value"].iloc[-1]))
    assert one["cadence"] == "quarterly" and one["unit"] == "pct" and one["note"]
    # the charted flag matches the panels, and most series have no chart
    charted = {s["key"] for s in b["series"] if s["charted"]}
    plotted = {"|".join([x["metric"], x["entity"], x["tier"], x["period_type"], x["source"]])
               for pa in PANELS for c in pa["charts"] for x in c["series"]}
    assert charted == plotted & keys
    assert len(b["series"]) - len(charted) > 100  # the fixtures carry 5 FDIC charters, the live pull carries 35
    # no series is dated into the future
    for s in b["series"]:
        end = b["grids"][s["grid"]][s["start"] + len(s["values"]) - 1]
        assert dt.datetime.fromtimestamp(end, dt.timezone.utc).date() <= TODAY
    # the section is on the page with a working control set
    assert 'id="browse"' in html and 'id="browse-table"' in html and 'id="browse-q"' in html
    assert f'{len(b["series"])} series' in html


def test_browse_payload_is_empty_without_facts(tmp_paths):
    from carddash.render import browse_payload
    assert browse_payload(coerce_facts(pd.DataFrame(columns=SERIES_KEY + ["period_end", "value", "entity_type", "pulled_at"])), {}, TODAY) == {"grids": {}, "series": []}


def test_rel_display_is_capped_when_the_old_value_is_zero():
    assert _rel_display(100.0, 0.0079872) == "0.80%"
    assert _rel_display(0.0, float("inf")) == "from 0"
    assert _rel_display(0.0, 5.0) == "from 0"
    assert _rel_display(2.0, float("nan")) == "from 0"


def test_new_periods_are_the_periods_only_this_run_loaded(fixture_facts):
    facts = fixture_facts.copy()
    facts["pulled_at"] = RUN1
    fred_m = (facts["source"] == "fred") & (facts["period_type"] == "M")
    latest_two = sorted(facts.loc[fred_m, "period_end"].unique())[-2:]
    facts.loc[fred_m & facts["period_end"].isin(latest_two), "pulled_at"] = RUN2  # two new months
    revised = (facts["source"] == "fred") & (facts["period_type"] == "Q") & (facts["period_end"] == pd.Timestamp("2025-12-31"))
    facts.loc[revised, "pulled_at"] = RUN2  # a revised value in an old period is not a new period
    facts.loc[facts["source"] == "tccp", "pulled_at"] = RUN2  # a source loaded for the first time in this run
    out = _new_periods(coerce_facts(facts), RUN2)
    assert [o["source"] for o in out] == ["fred", "tccp"]
    assert out[0]["periods"] == ["Jul 2026, Aug 2026 (monthly)"]
    assert out[1]["periods"] == ["2 semiannual periods through 2025 H2"]  # the two checked-in workbooks
    assert _new_periods(coerce_facts(facts), None) == []
    assert _new_periods(coerce_facts(facts.iloc[0:0]), RUN2) == []


def test_holder_and_sloos_demand_charts(page):
    _, payload = page
    ids = {c["id"]: c for c in payload["charts"]}
    holders = ids["revolving_by_holder"]
    assert [s["label"][:10] for s in holders["series"]] == ["Depository", "Credit uni", "Finance co"]
    share = ids["holder_share"]
    last = [ys[-1] for ys in share["data"][1:]]
    assert 5 < last[0] < 9 and 0.5 < last[1] < 3  # credit unions about 6.5%, finance companies about 1% of the NSA total
    sloos = ids["sloos_cards"]
    assert [s["label"] for s in sloos["series"]][1].startswith("Net % of banks reporting stronger")
    assert sloos["series"][1]["last_period"] == "2026 Q2"
    by_size = ids["sloos_demand_by_size"]
    assert by_size["data"][1][-1] == 0.0 and by_size["data"][2][-1] == 3.8


def test_page_carries_link_previews_nav_and_next_release(page, session_paths, fixture_facts):
    html, payload = page
    head = html.split("</head>")[0]
    assert '<meta property="og:image" content="https://samueljwebber.github.io/credit-card-data/img/revolving_level.png">' in head
    assert '<meta name="description" content="Revolving consumer credit, all lenders: $1,357bn in Jul 2026; ' in head
    assert '<meta name="twitter:card" content="summary_large_image">' in head
    assert '<link rel="icon" href="data:image/svg+xml,' in head
    assert '<nav class="nav" aria-label="Sections">' in html and 'href="#panel-performance"' in html
    assert '<section class="panel" id="panel-growth">' in html
    for panel in PANELS:
        for c in panel["charts"]:
            assert f'<button type="button" class="link" data-link="{c["id"]}"' in html
    # the thesis note is served next to the page, not linked to the repository blob view
    assert (session_paths.docs / THESIS_NOTE).exists()
    assert f'href="{THESIS_NOTE}"' in html and "blob/main/design" not in html
    # the note it revises is kept and linked, so the change of mind stays legible
    assert (REPO / "design" / "thesis-2026-09-08.html").exists()
    assert "thesis-2026-09-08.html" in (REPO / THESIS_NOTE).read_text(encoding="utf-8")
    # the thesis tests link to their charts
    assert '<a class="chartlink" href="#card_nco"' in html
    # next expected release per source, from the newest loaded period plus the typical lag
    health = html.split('<h2 id="health">')[1]
    assert "Aug 2026 data expected around 2026-10-08" in health  # July loaded (2026-09-08 vintage): month end plus 38 days
    assert "2026 Q3 data expected around 2026-11-11" in health  # NY Fed HHDC: quarter end plus 42 days
    assert 'id="theme"' in html and '@media (max-width: 640px)' in html


def test_monthly_sce_charts_and_reading(page):
    html, payload = page
    ids = {c["id"]: c for c in payload["charts"]}
    miss = ids["miss_payment_expectation"]
    assert miss["series"][0]["last_period"] == "Aug 2026" and abs(miss["data"][1][-1] - 13.16) < 0.01
    assert miss["series"][-1]["benchmark"] and 10 < miss["data"][-1][0] < 14
    income = ids["miss_payment_by_income"]
    assert income["data"][1][-1] > income["data"][3][-1]
    harder = ids["credit_harder"]
    assert abs(harder["data"][1][-1] - (15.306 + 30.606)) < 0.01  # much plus somewhat harder, August 2026
    assert "Households&#39; stated chance of missing a debt payment" in html   # escaped since autoescape is on


def test_hhdc_all_debt_charts(page):
    _, payload = page
    ids = {c["id"]: c for c in payload["charts"]}
    stages = ids["debt_by_delinquency_stage"]
    assert len(stages["series"]) == 5 and stages["series"][0]["last_period"] == "2026 Q2"
    assert abs(sum(ys[-1] for ys in stages["data"][1:]) - (100 - 95.27)) < 0.02  # 4.7% in some stage of delinquency
    bk = ids["bankruptcies_foreclosures"]
    assert bk["unit_label"] == "Thousands" and abs(bk["data"][1][-1] - 136.8) < 0.05
    assert abs(ids["collections"]["data"][1][-1] - 4.88) < 0.01
    assert ids["credit_demand_flow"]["unit"] == "millions" and abs(ids["credit_demand_flow"]["data"][1][-1] - 83.021) < 0.01


def test_spend_panel(page):
    html, payload = page
    ids = {c["id"]: c for c in payload["charts"]}
    growth = ids["spend_growth"]
    assert growth["series"][0]["last_period"] == "Aug 2026" and 0 < growth["data"][1][-1] < 10
    retail = ids["retail_growth"]
    assert retail["series"][0]["last_period"] == "Aug 2026"
    share = ids["online_share"]
    assert 15 < share["data"][1][-1] < 22  # nonstore about 18% of retail and food services sales in 2026
    cross = ids["card_volume_vs_retail"]
    assert {s["source"] for s in cross["series"]} == {"phillyfed", "census"} and cross["footer_lines"]
    assert '<section class="panel" id="panel-spend">' in html


def test_credit_union_charts(page):
    _, payload = page
    ids = {c["id"]: c for c in payload["charts"]}
    loans = ids["credit_union_card_loans"]
    assert loans["series"][0]["last_period"] == "2026 Q1" and abs(loans["data"][1][-1] - 86.039) < 0.001
    rates = ids["credit_union_card_rates"]
    navy = [v for v in rates["data"][2] if v is not None]
    assert abs(navy[-1] - 18.0) < 0.001  # Navy Federal on the 18 percent cap (the grid runs to the bank series' 2026 Q2)
    assert {s["source"] for s in rates["series"]} == {"fred", "ncua"}
    losses = ids["credit_union_card_losses"]
    assert len(losses["series"]) == 4 and losses["series"][3]["dash"]
    assert [v for v in losses["data"][4] if v is not None]  # the bank rate draws; the credit union rates need
    # consecutive quarters, which the fixture extracts (2016, 2021, 2023, 2026) do not give: see test_ncua_rates_view


def test_ncua_rates_view(tmp_paths, meta):
    """De-cumulated year-to-date charge-offs, annualized over average loans, and the 60+ day share."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from test_ncua import _cus, _zip
    from carddash.fetchers import ncua
    from carddash.series import series_for_source
    q1 = ncua.extract(_zip("3/31/2026 0:00:00", _cus()), 2026, 1)
    cus = _cus()
    for cu in cus:
        cus[cu].update({"396": 100, "680": 10, "681": 2, "045B": 3})
    q2 = ncua.extract(_zip("6/30/2026 0:00:00", cus), 2026, 2)
    facts = coerce_facts(ncua.to_facts([q1, q2], series_for_source(meta, ncua.SOURCE), RUN2))
    con = _connect(facts, tmp_paths.views_sql, tmp_paths.tccp_products_csv, tmp_paths.issuers_csv)
    rows = con.execute("SELECT period_end, nco_q, nco_rate_annualized, dq_share FROM v_ncua_rates WHERE entity = 'NCUA:BECU' ORDER BY period_end").fetchall()
    con.close()
    assert rows[0][1] == pytest.approx(3e-9) and rows[0][2] is None  # Q1: YTD net 4 - 1 = 3, no prior quarter for the average
    assert rows[1][1] == pytest.approx(5e-9)  # Q2: (10 - 4) - (2 - 1) = 5 dollars, in billions
    assert rows[1][2] == pytest.approx(100 * 4 * 5 / 100)  # 20 percent annualized on average loans of 100
    assert rows[1][3] == pytest.approx(3.0)


def _apr_spread_rows(con) -> dict:
    return {r[0]: r[1:] for r in con.execute(
        "SELECT period_end, apr, prime, spread_over_prime FROM v_apr_spread ORDER BY period_end").fetchall()}


def test_apr_spread_takes_the_prime_rate_of_the_month_the_apr_was_surveyed(fixture_facts, tmp_paths):
    """The G.19 card rate is surveyed in the middle month of the quarter (FRED dates Q3 to 2026-08-01) and loaded at
    the quarter end, so the prime rate it is compared with is the month BEFORE the quarter end, not the quarter-end
    month. March 2020 is the case that shows it: prime fell from 4.75 to 3.78 that month, a fortnight after the
    February survey, and pairing the two drew a 0.97 point jump in issuer margin that never happened."""
    con = _connect(fixture_facts, tmp_paths.views_sql, tmp_paths.tccp_products_csv, tmp_paths.issuers_csv)
    rows = _apr_spread_rows(con)
    con.close()
    apr, prime, spread = rows[dt.date(2020, 3, 31)]
    assert (apr, prime) == (16.61, 4.75) and spread == pytest.approx(11.86)  # 12.83 when March's prime was used
    assert rows[dt.date(2026, 6, 30)][2] == pytest.approx(15.40)  # May 2026: 22.15 - 6.75
    assert len(rows) > 120  # every quarter since 1994 still finds its prime rate
    # the reading the page draws, the 2015-2019 benchmark, uses the corrected pairing too
    bench = [s for d, (_, _, s) in rows.items() if dt.date(2015, 1, 1) <= d <= dt.date(2019, 12, 31)]
    assert len(bench) == 20 and sum(bench) / 20 == pytest.approx(10.75, abs=0.005)


def test_apr_spread_does_not_move_when_prime_changes_after_the_survey(tmp_paths):
    """2026 Q3 as published: the August survey reads 22.36, prime was 6.75 in August and 6.87 in September."""
    rows = [("card_apr_assessed_interest", "2026-09-30", "Q", 22.36), ("prime_rate", "2026-08-31", "M", 6.75),
            ("prime_rate", "2026-09-30", "M", 6.87)]
    facts = coerce_facts(pd.DataFrame([
        {"metric": m, "entity": "COMBANKS_ALL", "entity_type": "aggregate", "tier": "all", "period_end": d,
         "period_type": pt, "value": v, "source": "fred", "pulled_at": RUN2} for m, d, pt, v in rows]))
    con = _connect(facts, tmp_paths.views_sql, tmp_paths.tccp_products_csv, tmp_paths.issuers_csv)
    (apr, prime, spread), = _apr_spread_rows(con).values()
    con.close()
    assert prime == 6.75 and spread == pytest.approx(15.61)  # not 15.49: the September increase came after August


def test_distribution_panel_draws_the_dfa(page):
    html, payload = page
    ids = {c["id"]: c for c in payload["charts"]}
    wealth = ids["dfa_credit_by_wealth"]
    assert wealth["post"] and wealth["series"][0]["last_period"] == "2026 Q1"
    shares = [s[-1] for s in wealth["data"][1:]]
    assert abs(sum(shares) - 100) < 0.01 and 50 < shares[0] < 54  # the bottom half owes about half of all consumer credit
    buffer = ids["dfa_buffer_by_wealth"]
    assert 25 < buffer["data"][1][-1] < 35  # bottom 50%: deposits of about 30 cents per dollar of consumer credit
    ratio = ids["dfa_credit_to_net_worth"]
    assert 55 < ratio["data"][1][-1] < 70  # bottom 50%: consumer credit about 60 percent of net worth
    per_hh = ids["dfa_credit_per_household_age"]
    assert per_hh["unit"] == "usd" and 14000 < per_hh["data"][4][-1] < 18000  # 70 and over: about $16k per household
    income = ids["dfa_credit_by_income"]
    assert abs(sum(s[-1] for s in income["data"][1:]) - 100) < 0.01
    assert '<section class="panel" id="panel-distribution">' in html
    assert "Consumer credit owed by the bottom half of households by wealth" in html


def test_cct_charts(page):
    html, payload = page
    ids = {c["id"]: c for c in payload["charts"]}
    orig = ids["cct_originations"]
    assert orig["series"][0]["last_period"] == "Jan 2026" and 7 < orig["data"][1][-1] < 10
    by_score = ids["cct_lines_by_score"]
    assert abs(sum(s[-1] for s in by_score["data"][1:]) - 100) < 0.01 and 78 < by_score["data"][5][-1] < 86
    below = ids["cct_below_prime_share"]
    assert {s["source"] for s in below["series"]} == {"cfpb_cct", "phillyfed"} and below["footer_lines"]
    vals = [v for v in below["data"][1] if v is not None]
    assert 4 < vals[-1] < 8  # sub-660 borrowers get about 6 percent of new credit line dollars
    ages = ids["cct_lines_by_age"]
    assert abs(sum(s[-1] for s in ages["data"][1:]) - 100) < 0.01
    inq = ids["cct_inquiries"]
    assert inq["series"][0]["last_period"] == "May 2026" and 200 < inq["data"][1][-1] < 250
    tight = ids["cct_tightness"]
    assert tight["unit"] == "index" and tight["series"][0]["last_period"] == "Mar 2026" and 70 < tight["data"][1][-1] < 90
    assert "New credit cards opened in the month, all lenders" in html and " million in Jan 2026" in html


def test_interest_and_claims_charts(page):
    html, payload = page
    ids = {c["id"]: c for c in payload["charts"]}
    eff = ids["effective_rate"]
    assert {s["source"] for s in eff["series"]} == {"bea", "fred"}
    rate = [v for v in eff["data"][1] if v is not None]
    assert 9 < rate[-1] < 14  # about $600bn of interest on about $5.2tn of consumer credit
    share = ids["interest_share_income"]
    v = [x for x in share["data"][1] if x is not None]
    assert 2 < v[-1] < 3.5  # 604 over 23,858: about 2.5 percent of disposable income
    claims = ids["jobless_claims"]
    assert claims["unit"] == "thousands" and claims["period_type"] == "W"
    assert abs(claims["data"][1][-1] - 206.0) < 1e-9 and abs(claims["data"][2][-2] - 1774.0) < 1e-9
    assert " thousand in " in html  # the claims reading


def test_dfa_and_cct_views(page, fixture_facts, tmp_paths):
    """v_dfa_shares and v_cct_shares reproduce the hand arithmetic on the fixture facts."""
    con = _connect(fixture_facts, tmp_paths.views_sql, tmp_paths.tccp_products_csv, tmp_paths.issuers_csv)
    row = con.execute(
        "SELECT share_pct, deposits_to_credit_pct, credit_per_household, credit_to_net_worth_pct FROM v_dfa_shares "
        "WHERE entity = 'WEALTH:BOTTOM50' AND period_end = DATE '2026-03-31'"
    ).fetchone()
    assert row[0] == pytest.approx(100 * 2626.591 / 5073.031, abs=1e-6)
    assert row[1] == pytest.approx(100 * 793.232 / 2626.591, abs=1e-6)
    assert row[2] == pytest.approx(1000 * 2626.591 / 67.573814, abs=1e-3)
    assert row[3] == pytest.approx(100 * 2626.591 / 4266.359, abs=1e-6)
    tiers = con.execute(
        "SELECT tier, share_pct, below_prime_share_pct FROM v_cct_shares WHERE metric = 'cct_card_new_lines_sa' "
        "AND entity = 'CFPB_CCP_ALL' AND period_end = DATE '2026-01-31' ORDER BY tier"
    ).fetchall()
    assert [t[0] for t in tiers] == ["deep_subprime", "near_prime", "prime", "subprime", "superprime"]
    assert sum(t[1] for t in tiers) == pytest.approx(100.0)
    assert len({round(t[2], 9) for t in tiers}) == 1 and 5 < tiers[0][2] < 7
    ages = con.execute(
        "SELECT sum(share_pct) FROM v_cct_shares WHERE metric = 'cct_card_new_lines_nsa' AND entity_type = 'age' "
        "AND period_end = DATE '2026-01-31'"
    ).fetchone()
    assert ages[0] == pytest.approx(100.0)
    con.close()


def test_loan_type_charts_compare_cards_with_the_other_debts(page):
    """The by-loan-type sheets of the same workbook: card distress against auto, mortgage and student."""
    html, payload = page
    ids = {c["id"]: c for c in payload["charts"]}
    stock = ids["dq_by_loan_type"]
    assert len(stock["series"]) == 7 and stock["series"][6]["dash"]
    last = {s["label"]: stock["data"][i + 1][-1] for i, s in enumerate(stock["series"])}
    assert last["Credit card"] > last["Auto loan"] > last["Mortgage"]  # 12.9, 5.5, 1.0 at 2026 Q2
    assert last["Credit card"] > last["All household debt"]
    flow = ids["dq_flow_by_loan_type"]
    assert len(flow["series"]) == 7 and flow["series"][0]["last_period"] == "2026 Q2"
    student = [v for v in flow["data"][2] if v is not None]
    assert len(student) < flow["n_points"]  # student loans start a year late and are not back-filled
    old = ids["age70_by_loan_type"]
    vals = {s["label"]: old["data"][i + 1][-1] for i, s in enumerate(old["series"])}
    assert vals["Credit card"] > vals["Auto loan"] > vals["All debt"]  # the over-70s' problem is card-specific
    banks = ids["bank_losses_by_category"]
    assert len(banks["series"]) == 4 and {s["source"] for s in banks["series"]} == {"fred"}
    card, mortgage = banks["data"][1][-1], banks["data"][4][-1]
    assert card > 10 * mortgage  # card charge-offs are an order of magnitude above mortgage
    by_age = ids["debt_by_age"]
    assert by_age["unit"] == "usd_bn" and len(by_age["series"]) == 6
    assert by_age["n_points"] == 110  # the debt-by-age sheet starts in 1999, a year before the others
    assert ids["student_dq_by_age"]["n_points"] > 80


def test_consumer_loan_rates_chart(page):
    """The G.19 rate survey's three loan types, the test of whether the card margin is a card decision."""
    _, payload = page
    rates = {c["id"]: c for c in payload["charts"]}["consumer_loan_rates"]
    assert len(rates["series"]) == 4 and rates["period_type"] is None  # quarterly plus the monthly prime rate
    card = [v for v in rates["data"][1] if v is not None][-1]
    personal = [v for v in rates["data"][2] if v is not None][-1]
    auto = [v for v in rates["data"][3] if v is not None][-1]
    assert card > personal > auto  # 22.15, 11.86, 7.47
    assert len(rates["footer_lines"]) == 4


def test_state_charts(page):
    """The state-level source: a band from the lowest to the highest state around the national line."""
    html, payload = page
    ids = {c["id"]: c for c in payload["charts"]}
    rng = ids["state_card_dq_range"]
    assert rng["band"] == [1, 2] and rng["period_type"] == "A"
    assert rng["series"][0]["last_period"] == "2025"
    hi, lo, med, nat = (rng["data"][k][-1] for k in (1, 2, 3, 4))
    assert hi > med > lo and lo < nat < hi
    assert hi - lo > 8  # the range across states was 8.3 points in 2025
    picked = ids["state_card_dq_selected"]
    labels = [s["label"] for s in picked["series"]]
    assert labels[0] == "National" and "Nevada" in labels and "Wisconsin" in labels
    nv = picked["data"][labels.index("Nevada") + 1][-1]
    wi = picked["data"][labels.index("Wisconsin") + 1][-1]
    assert nv > wi + 5
    debt = ids["state_card_debt_range"]
    assert debt["unit"] == "usd" and debt["data"][4][-1] == 4350  # the national row, dollars per adult
    assert "rose in every one of the 51 areas" in html

def test_the_page_shares_one_cursor_across_the_charts_on_x_only(page):
    """Hovering any chart marks the same date on every other chart.

    The behaviour is a browser matter and was verified in headless Chrome (task 40): hovering one
    chart at a date inside its window made all 75 read out that date, hovering the weekly chart at
    its newest point left only the 9 charts whose data runs that far, a mouseleave cleared all 75,
    and one mousemove cost 2.65 ms. What a test can hold here is the wiring, and the three ways it
    could go quietly wrong: a shared y scale or series focus would carry one chart's unit onto a
    chart in another unit; a chart answering for a date it does not hold would let uPlot clamp to
    an endpoint and read out a value for the wrong period; and on step charts the nearest period
    end is not the period that contains the date.
    """
    html, _ = page
    cursor = html.split("D.charts.forEach")[1].split("---- browse every series ----")[0]
    assert "sync: { key: SYNC_KEY" in cursor
    assert "scales: ['x', null]" in cursor and "setSeries: false" in cursor
    # a chart outside the hovered date clears its cursor instead of clamping to an endpoint
    assert "xv < xs[0] || xv > xs[n - 1] || xv < sc.min || xv > sc.max" in cursor
    assert "u.setCursor({ left: -10, top: -10 })" in cursor
    # only the cursor is shared: zoom, drag and dblclick stay per chart
    assert "type !== 'mousemove' && type !== 'mouseleave'" in cursor
    # period data reads the period that CONTAINS the date; continuous data keeps uPlot's nearest
    assert "dataIdx: c.step ? containingIdx : null" in cursor
    assert "return closestIdx + 1 < xs.length ? closestIdx + 1 : closestIdx;" in html
    # the series browser keeps its own cursor: it is never on screen with a panel chart
    assert "SYNC_KEY" not in html.split("---- browse every series ----")[1]


def test_every_view_field_a_chart_draws_is_bounded_or_explicitly_exempt():
    """A derived field must not reach a chart without someone having decided what it may contain.

    The loader's per-series vmin/vmax validates facts as they load; view fields are computed in SQL
    afterwards and so were never checked by anything. That gap put a 182.9% annualised charge-off rate
    for Bank of America on the issuer chart for months. This test makes the omissions deliberate: a new
    view field is either given bounds or added to the exempt list with its reason.
    """
    used = {(sr["view"], sr["field"]) for panel in PANELS for c in panel["charts"] for sr in c["series"]}
    unaccounted = used - set(VIEW_BOUNDS) - VIEW_BOUNDS_UNCHECKED
    assert not unaccounted, f"view fields with no bound and no stated exemption: {sorted(unaccounted)}"
    assert not (set(VIEW_BOUNDS) & VIEW_BOUNDS_UNCHECKED)  # a field is bounded or exempt, never both


def test_a_view_field_outside_its_bounds_fails_the_render():
    """The backstop fires, and says what to do about it."""
    s = {"view": "v_fdic_rates", "field": "nco_rate_annualized", "entity": "ISSUER:BOFA", "label": "Bank of America"}
    lo, hi = VIEW_BOUNDS[("v_fdic_rates", "nco_rate_annualized")]
    _check_bounds(s, [(dt.date(2020, 3, 31), 5.0), (dt.date(2020, 6, 30), hi - 0.1)])  # inside: fine
    with pytest.raises(ValueError, match="outside its plausible range"):
        _check_bounds(s, [(dt.date(2001, 12, 31), 182.857)])
    with pytest.raises(ValueError, match="collapsed denominator"):
        _check_bounds(s, [(dt.date(2006, 12, 31), lo - 1.0)])


def test_fdic_ratios_need_a_card_book_worth_dividing_by(tmp_paths):
    """A residual book of a few million produces no rate at all, rather than a rate of a few hundred percent.

    Bank of America's own history is the case: its card book on the Bank of America, N.A. charter sat between
    $2mn and $50mn from 2001 to 2013, because the business was at FIA Card Services, and dividing a real
    quarter of charge-offs by it drew 182.9% for 2001 Q4. Negative rates are kept: a quarter whose recoveries
    beat its charge-offs is real (Citi, 2006 Q4, -4.0% on a $37bn book).
    """
    def row(metric, period_end, value, entity="FDIC_ALL_INSURED"):
        return {"metric": metric, "entity": entity, "entity_type": "industry", "tier": "all",
                "period_end": period_end, "period_type": "Q", "value": value, "source": "fdic",
                "pulled_at": PULLED_AT}

    rows = []
    for i, (end, loans, nco) in enumerate([
        ("2020-03-31", 0.020, 0.006),   # $20mn book: no rate, this is the 182.9% case
        ("2020-06-30", 0.020, 0.006),
        ("2020-09-30", 40.000, 0.400),  # $40bn book: a rate, and a small one
        ("2020-12-31", 40.000, -0.400),  # a genuine net recovery quarter stays negative
    ]):
        rows += [row("fdic_card_loans", end, loans), row("fdic_card_nco_q", end, nco)]
    facts = coerce_facts(pd.DataFrame(rows))
    con = _connect(facts, tmp_paths.views_sql, tmp_paths.tccp_products_csv, tmp_paths.issuers_csv)
    got = con.execute(
        "SELECT period_end, nco_rate_annualized FROM v_fdic_rates "
        "WHERE entity = 'FDIC_ALL_INSURED' ORDER BY period_end"
    ).fetchall()
    rates = {str(d): v for d, v in got}
    assert rates["2020-06-30"] is None, "a $20mn book must carry no rate"
    assert rates["2020-09-30"] is not None and 0 < rates["2020-09-30"] < 10
    assert rates["2020-12-31"] is not None and rates["2020-12-31"] < 0, "a real net recovery quarter is kept"


def test_a_hole_is_drawn_as_a_hole_on_every_chart_but_the_one_that_changed_cadence(page):
    """A missing period means the thing was not measured, so no line is drawn across it.

    The page used to span gaps everywhere while the PNG of the same chart never did, so the two disagreed
    wherever a series had a hole. The default is now False and exactly one chart opts back in:
    consumer_sentiment, whose gaps before 1978 are the survey being quarterly rather than months that went
    unmeasured.
    """
    _, payload = page
    ids = {c["id"]: c for c in payload["charts"]}
    assert ids["nco_by_issuer"]["span_gaps"] is False
    assert any("FIA Card Services" in n for n in ids["nco_by_issuer"]["notes"])

    spanning = [c["id"] for c in payload["charts"] if c["span_gaps"]]
    assert spanning == ["sentiment"], f"only a cadence change may span gaps, got {spanning}"
    assert any("QUARTERLY until January 1978" in n for n in ids["sentiment"]["notes"])


def test_the_shutdown_month_missing_from_the_labour_data_is_left_open(page):
    """October 2025 was never collected, so the unemployment line breaks there rather than joining up.

    The flag alone is not enough and this is the part that actually bites: the x grid is built from the dates
    that HAVE data, so a month no series holds is simply absent and the line joins September to November as
    though they were consecutive. The missing period has to be put on the grid as an explicit null first.
    """
    _, payload = page
    chart = {c["id"]: c for c in payload["charts"]}["losses_vs_labor"]
    assert chart["span_gaps"] is False
    assert any("OCTOBER 2025" in n for n in chart["notes"])

    epoch = dt.date(1970, 1, 1)
    unemployment = {epoch + dt.timedelta(seconds=t): v for t, v in zip(chart["data"][0], chart["data"][2])}
    assert dt.date(2025, 10, 31) in unemployment, "the missing month is not even on the grid"
    assert unemployment[dt.date(2025, 10, 31)] is None
    assert unemployment[dt.date(2025, 9, 30)] is not None
    assert unemployment[dt.date(2025, 11, 30)] is not None


def test_a_series_that_merely_starts_late_is_not_treated_as_having_a_hole():
    """Only periods INSIDE a series' own span are filled, or every chart would grow a run of leading nulls."""
    rows = [(dt.date(2026, 1, 31), 1.0), (dt.date(2026, 2, 28), 2.0), (dt.date(2026, 4, 30), 3.0)]
    assert _missing_periods(rows, "M") == [dt.date(2026, 3, 31)]
    assert _missing_periods(rows[:2], "M") == []
    assert _missing_periods([(dt.date(2026, 3, 31), 1.0)], "M") == []
    # quarterly and annual step by their own cadence, and the four-monthly survey waves are left alone
    quarters = [(dt.date(2025, 3, 31), 1.0), (dt.date(2025, 12, 31), 2.0)]
    assert _missing_periods(quarters, "Q") == [dt.date(2025, 6, 30), dt.date(2025, 9, 30)]
    assert _missing_periods(quarters, "T") == []

def test_the_state_map_covers_every_area_on_a_grid_with_no_collisions(page):
    """A tile-grid cartogram: one equal square per area, so land area never stands in for population."""
    _, payload = page
    m = payload["state_map"]
    codes = [t["code"] for t in m["tiles"]]
    assert len(codes) == len(set(codes)) == len(STATE_TILES) == 52   # 50 states, DC, Puerto Rico
    positions = [(t["row"], t["col"]) for t in m["tiles"]]
    assert len(positions) == len(set(positions)), "two areas share a square"
    assert all(0 <= r < m["rows"] and 0 <= c < m["cols"] for r, c in positions)
    assert [x["key"] for x in m["metrics"]] == ["dq", "debt"]
    assert m["years"] == sorted(m["years"]) and len(m["years"]) >= 20

    dq = m["metrics"][0]
    # every square carries a series, and the national row is kept out of the grid
    assert set(dq["values"]) == set(codes)
    assert "US" not in dq["values"] and "CCP_ALL" not in dq["values"]
    assert dq["national"], "the national reference is missing"


def test_the_state_map_ramp_is_one_hue_defined_in_both_themes(page):
    """Magnitude takes a sequential ramp, and dark is a chosen ramp rather than a flipped light one."""
    html, _ = page
    head = html.split("* { box-sizing: border-box; }")[0]
    # the light ramp sits on bare :root so a viewer with no preference still gets a complete palette
    assert head.count("--seq-0:") == 3       # :root, the media query, and [data-theme="dark"]
    assert head.count("--seq-ink-0:") == 3
    light = head.split("--seq-0:")[1].split(";")[0].strip()
    dark = head.split("--seq-0:")[2].split(";")[0].strip()
    assert light != dark, "dark mode must define its own steps, not reuse the light ramp"
    # the ramp never borrows the identity channel
    for i in range(6):
        assert f"--seq-{i}:" in head and f"--seq-ink-{i}:" in head
    assert "--seq-0:#fdf0e6" in head and "--seq-5:#a3400f" in head          # light: light -> dark
    assert "--seq-0:#3a2317" in head and "--seq-5:#f7a35f" in head          # dark: the anchor flips

    # bins are classes, so the browser resolves the ramp live instead of a colour frozen at draw time
    assert ".tile.b0, .sw.b0 { background: var(--seq-0); }" in html
    assert "el.classList.add('b' + b)" in html


def test_the_state_map_numbers_are_the_ones_the_source_published(page, fixture_facts):
    """Spot values straight from the fixtures, so a broken join shows up as a wrong square."""
    _, payload = page
    dq = payload["state_map"]["metrics"][0]
    rows = fixture_facts[
        (fixture_facts["source"] == "nyfed_state")
        & (fixture_facts["metric"] == "state_card_dq90_rate_balances")
    ]
    latest = max(payload["state_map"]["years"])
    for code in ("NV", "WI", "CA"):
        want = rows[(rows["entity"] == f"STATE:{code}") & (rows["period_end"].astype(str).str.startswith(str(latest)))]
        assert dq["values"][code][str(latest)] == pytest.approx(float(want["value"].iloc[0]))
    # Nevada has been the worst area for the whole history, which is why its square never lightens
    assert dq["values"]["NV"][str(latest)] > dq["values"]["WI"][str(latest)]


def test_puerto_rico_is_shown_but_its_series_stops(page):
    """It is in the source and is not a state; the map draws the gap rather than carrying 2016 forward."""
    _, payload = page
    dq = payload["state_map"]["metrics"][0]
    pr_years = sorted(int(y) for y in dq["values"]["PR"])
    assert max(pr_years) < max(payload["state_map"]["years"]), "Puerto Rico should stop before the newest year"


def test_a_script_tag_in_a_health_message_is_escaped(tmp_paths, fixture_facts):
    """REVIEW.md credit-A-3. Health messages carry the first bytes of an upstream reply. Escaping was off for the whole
    page, because select_autoescape(["html"]) looks at the file extension and the template is index.html.j2, so a source
    answering with a script tag would have run script on the public page."""
    from jinja2 import select_autoescape

    assert select_autoescape(["html"])("index.html.j2") is False        # why the old setting did nothing
    tag = "<script src=//evil.example/x.js></script>"
    health = _health(RUN2)
    health["sources"]["fred"]["status"] = "failed"
    health["sources"]["fred"]["messages"] = [f"unexpected reply: b'{tag}'"]
    write_facts(fixture_facts, tmp_paths.facts_csv)
    tmp_paths.health_json.write_text(json.dumps(health), encoding="utf-8")
    html = render(tmp_paths, today=TODAY).read_text(encoding="utf-8")
    assert tag not in html
    assert "&lt;script src=//evil.example/x.js&gt;&lt;/script&gt;" in html
    assert "evil.example" not in html.replace("&lt;script src=//evil.example/x.js&gt;", "")   # and nowhere else unescaped


def test_the_bea_interest_chart_says_it_is_modelled(page):
    """REVIEW.md credit-B-1: BEA builds the series as Fed credit times a blended Fed rate; it is not interest paid."""
    html, payload = page
    eff = {c["id"]: c for c in payload["charts"]}["effective_rate"]
    assert eff["title"].startswith("BEA's modelled nonmortgage interest as an implied rate")
    assert "actually pay" not in html and "fewer dollars" not in html and "pay no interest at all" not in html
    assert "modelled, not measured from what households paid" in html
    assert html.count("NIPA Handbook chapter 14") >= 2                  # on the implied-rate chart and the income-share chart


def test_the_page_carries_the_notices_its_publishers_require(page):
    """REVIEW.md R2-2: the FRED API terms and the NY Fed's SCE licence each require a notice, and each ends the right
    to use the data automatically without it. Neither was on the page; the README carried neither."""
    from carddash.notices import FRED_API

    html, payload = page
    assert html.count(FRED_API) == 1
    assert html.count("FRBNY disclaims any responsibility or legal liability for this analysis") == 1
    assert "Source: Survey of Consumer Expectations, © 2013-2026 Federal Reserve Bank of New York (FRBNY)." in html
    assert "© 2026 Federal Reserve Bank of New York. Content from the New York Fed subject to the Terms of Use" in html
    assert '<a href="#notices">Notices</a>' in html and '<h2 id="notices">Notices</h2>' in html
    assert html.index('<h2 id="notices">') > html.index('<h2 id="method">')
    by_id = {c["id"]: c for c in payload["charts"]}
    for cid in ("card_access", "lender_closures", "miss_payment_expectation", "credit_harder"):
        # the licence's own form for a figure, on the page and on the PNG
        assert by_id[cid]["caption"].startswith("Source: Survey of Consumer Expectations, New York Fed · "), cid


def test_a_png_carries_its_sources_notices_in_a_caption_area_that_fits_them(page):
    """A PNG is made to be pasted into a post, without the page's Notices block. The caption area was a fixed 7% of
    the height, which holds two lines; five captions already wrapped to three or four and ran into the axis."""
    from carddash.notices import NYFED, SCE, png_notices
    from carddash.png import CAPTION_MIN, caption_area, caption_text

    _, payload = page
    by_id = {c["id"]: c for c in payload["charts"]}
    years = {"nyfed_sce": 2026, "nyfed_hhdc": 2026}
    window = " · last 5 years shown, full history on the page"
    notes = png_notices({s["source"] for s in by_id["card_access"]["series"]}, years)
    assert notes == [SCE.replace("{year}", "2026")]
    text = caption_text(by_id["card_access"], window, notes)
    assert text.startswith("Source: Survey of Consumer Expectations, New York Fed") and "FRBNY disclaims" in text
    assert caption_area(text) > CAPTION_MIN
    assert png_notices({s["source"] for s in by_id["hhdc_dq90_by_age"]["series"]}, years) == [NYFED.replace("{year}", "2026")]
    plain = caption_text(by_id["revolving_level"], window)
    assert png_notices({"fred"}, years) == [] and len(plain.splitlines()) <= 2
    assert caption_area(plain) == CAPTION_MIN  # an unchanged two-line caption keeps its layout, and its PNG its bytes
    long = caption_text(by_id["dq_triangulation"], window)  # four sources: it wraps to four lines
    assert len(long.splitlines()) >= 3 and caption_area(long) > CAPTION_MIN


def test_every_source_has_a_distinct_short_name_and_the_due_line_uses_it(page):
    """REVIEW.md R2-6: the 'Due in the next two weeks' line cut each label at its first comma, and the live page read
    'Federal Reserve Bank of New York 2026 Q3 around 2026-11-11', which is any of three sources."""
    from carddash.sources import SOURCE_LABELS, SOURCE_SHORT

    assert set(SOURCE_SHORT) == set(SOURCE_LABELS)
    assert len(set(SOURCE_SHORT.values())) == len(SOURCE_SHORT)
    html, _ = page
    due = html.split('<p class="due">Due in the next two weeks: ')[1].split("</p>")[0]
    assert any(due.startswith(short) or f"; {short} " in due for short in SOURCE_SHORT.values()), due
    assert "Federal Reserve Bank" not in due and "Capital One " not in due


def test_credit_a2_offered_apr_top25_and_respondent_swing_guard(page, fixture_facts):
    """REVIEW.md credit-A-2: offered_vs_paid draws the fixed top-25 statutory panel as its primary band/line,
    keeps all respondents dashed, prints per-half-year institution counts, and flags >20% respondent swings."""
    from carddash.loader import read_facts
    from carddash.render import _tccp_respondent_note

    html, payload = page
    ovp = {c["id"]: c for c in payload["charts"]}["offered_vs_paid"]
    notes = " ".join(ovp["notes"])
    assert "Responding institutions per half-year" in notes
    assert "2023 H1: 140" in notes and "2025 H2: 195" in notes
    assert "changed by more than 20%" in notes and "+39%" in notes

    # Guard on the committed live dataset too: if tccp_issuer_count swings >20% between consecutive half-years
    # (123 in 2025 H1 -> 195 in 2025 H2, +59%), the chart note must name the half-years and flag the >20% swing.
    live_facts = read_facts(REPO / "data" / "facts.csv")
    con = _connect(live_facts, REPO / "sql" / "views.sql", REPO / "data" / "raw" / "tccp" / "tccp_products.csv",
                   REPO / "crosswalks" / "issuers.csv")
    try:
        live_note = _tccp_respondent_note(con, dt.date(2026, 11, 22))
        counts = con.execute(
            "SELECT period_end, value FROM facts WHERE metric = 'tccp_issuer_count' AND entity = 'TCCP_ALL' "
            "AND source = 'tccp' ORDER BY period_end"
        ).fetchall()
    finally:
        con.close()
    assert live_note is not None
    assert "2025 H1: 123" in live_note and "2025 H2: 195" in live_note
    for (d0, n0), (d1, n1) in zip(counts, counts[1:]):
        if n0 > 0 and abs(n1 - n0) / n0 > 0.20:
            assert "changed by more than 20%" in live_note
            assert f"{int(round(n0))} to {int(round(n1))}" in live_note

    # Synthetic <=20% change: counts still printed, no >20% swing alarm
    calm = fixture_facts.copy()
    calm.loc[(calm["metric"] == "tccp_issuer_count") & (calm["period_end"] == pd.Timestamp("2025-12-31")), "value"] = 150.0
    con_calm = _connect(
        calm,
        REPO / "sql" / "views.sql",
        REPO / "data" / "raw" / "tccp" / "tccp_products.csv",
        REPO / "crosswalks" / "issuers.csv",
    )
    try:
        calm_note = _tccp_respondent_note(con_calm, TODAY)
    finally:
        con_calm.close()
    assert calm_note is not None and "2023 H1: 140, 2025 H2: 150." == calm_note.split("line): ")[1]


def test_effective_rate_and_card_volume_vs_retail_label_mixed_sa_and_nsa(page, meta):
    """Cross-review follow-up on credit-A-6: mixed SA/NSA charts outside credit-A-6's PR #2 charts explicitly label SA vs NSA."""
    from carddash.render import _key
    from carddash.series import series_index

    _, payload = page
    by_id = {c["id"]: c for c in payload["charts"]}
    idx = series_index(meta)

    eff = by_id["effective_rate"]
    assert "SA" in eff["series"][0]["label"] and "NSA" in eff["series"][1]["label"]
    assert any("SAAR/SA" in n and "(NSA)" in n for n in eff["notes"])

    cvr = by_id["card_volume_vs_retail"]
    assert "NSA" in cvr["series"][0]["label"] and "SA" in cvr["series"][1]["label"]
    assert any("not seasonally adjusted" in n and "seasonally adjusted" in n for n in cvr["notes"])

    cct = by_id["cct_below_prime_share"]
    assert "SA" in cct["series"][0]["label"] and "NSA" in cct["series"][1]["label"]
    assert any("seasonally adjusted" in n and "not seasonally adjusted" in n for n in cct["notes"])

    # issuer_monthly_nco and issuer_monthly_dq are covered under credit-A-6 in separate PR #2
    pr2_credit_a6_ids = {"issuer_monthly_nco", "issuer_monthly_dq"}
    mixed_ids = []
    for panel in PANELS:
        for spec in panel["charts"]:
            sas = {bool(idx[_key(s)]["sa"]) for s in spec["series"] if _key(s) in idx}
            if len(sas) > 1:
                mixed_ids.append(spec["id"])
                if spec["id"] not in pr2_credit_a6_ids:
                    chart = by_id[spec["id"]]
                    assert any("SA" in s["label"] for s in chart["series"] if not s["benchmark"]), spec["id"]
    assert {"effective_rate", "card_volume_vs_retail", "cct_below_prime_share"} <= set(mixed_ids)


def test_remaining_review_notes_census_max_age_and_licenses(page, meta, tmp_paths, fixture_facts):
    """REVIEW.md credit-A-7, credit-A-9, credit-A-10, credit-A-11, credit-A-13, credit-B-4, credit-B-8, credit-B-11."""
    from carddash import loader
    from carddash.render import RELEASE_RHYTHM, _age_dq_note, _cpi_note, next_expected

    html, payload = page
    by_id = {c["id"]: c for c in payload["charts"]}

    # credit-A-7: census max_age_days=85 prevents false stale alarms on normal release dates (~day 77-78)
    census_meta = meta[meta["source"] == "census"].copy()
    assert set(census_meta["max_age_days"]) == {85.0}
    assert RELEASE_RHYTHM["census"][3] == 48
    # Simulate census with Aug 31 data checked on Nov 17 (78 days old): stays ok, not stale
    aug_only = fixture_facts[fixture_facts["source"] == "census"].copy()
    _, h_cen, _ = loader.refresh_source(
        "census", aug_only, census_meta, lambda m, r, s, p: aug_only, None, None, dt.date(2026, 11, 17), PULLED_AT, set()
    )
    assert h_cen.status == "ok"

    # credit-A-9: 8 stale/inaccurate prose claims replaced or computed mechanically
    assert "oldest borrowers are the only age band" not in html
    assert "about 25 percent" not in html
    assert "five months" not in html
    assert "few tenths of a point" not in html
    assert "payment rates and full-payer shares set records" not in html
    assert "leads every lender-reported series" not in html
    assert "nonfinancial businesses" not in " ".join(meta["scope_note"].fillna(""))
    assert "\\'" not in " ".join(meta["scope_note"].fillna(""))
    assert "only survey that asks households directly" not in html
    assert "only survey on this page that asks households directly" in html

    # Computed CPI and age-band notes match fixture facts and live facts
    assert any("Consumer prices (CPI-U) rose 28.4% between Jan 2020 and Jul 2026" in n for n in by_id["revolving_real"]["notes"])
    assert any("70+ card flow into 90+ day delinquency was 6.34%" in n for n in by_id["age70_by_loan_type"]["notes"])
    live_con = _connect(
        loader.read_facts(REPO / "data" / "facts.csv"),
        REPO / "sql" / "views.sql",
        REPO / "data" / "raw" / "tccp" / "tccp_products.csv",
        REPO / "crosswalks" / "issuers.csv",
    )
    try:
        assert "30.2%" in (_cpi_note(live_con, dt.date(2026, 11, 22)) or "")
        live_age = _age_dq_note(live_con, dt.date(2026, 11, 22)) or ""
        assert "6.09%" in live_age and "50-59 (6.47%" in live_age
    finally:
        live_con.close()

    # credit-A-10, credit-A-11, credit-B-4, credit-B-8
    assert "about 50 banks" in html and "about 270 applicants" in html
    assert "7.18%, so this test trips only on a new high" in html
    assert any("90+ day delinquent and stale charged-off accounts" in n for n in by_id["per_account_credit"]["notes"])
    assert any("balance-weighted shares of dollars" in n for n in by_id["dq_triangulation"]["notes"])

    # credit-A-13: root MIT LICENSE and vendored uPlot MIT notice
    root_lic = (REPO / "LICENSE").read_text(encoding="utf-8")
    uplot_lic = (REPO / "src" / "carddash" / "vendor" / "LICENSE-uPlot").read_text(encoding="utf-8")
    assert "MIT License" in root_lic and "SamuelJWebber" in root_lic
    assert "MIT License" in uplot_lic and "Leon Sorokin" in uplot_lic

    # BEA Oct PIO due Nov 25 calendar expectation transitions (pre-due, grace window, overdue)
    pre_due = next_expected(fixture_facts, "bea", dt.date(2026, 11, 22))
    grace = next_expected(fixture_facts, "bea", dt.date(2026, 11, 28))
    overdue = next_expected(fixture_facts, "bea", dt.date(2026, 12, 5))
    assert pre_due is not None and pre_due["due"] == "2026-11-27" and not pre_due["overdue"]
    assert "expected around 2026-11-27" in pre_due["text"]
    assert grace is not None and not grace["overdue"] and "expected any day" in grace["text"]
    assert overdue is not None and overdue["overdue"] and "has not appeared" in overdue["text"]
