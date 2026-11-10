"""BEA NIPA flat-file fetcher: the checked-in subset, scaling, continuity, the release-page changes."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from carddash.fetchers import bea
from carddash.series import series_for_source
from conftest import BEA_FIXTURE, PULLED_AT


def test_subset_reproduces_the_release_changes(bea_facts):
    """Personal Income and Outlays, September 2026 (2026-10-29): PCE +113.1bn, goods +35.1bn, services +78.1bn; its
    historical comparisons workbook (pi0926-hist.xlsx): August +193.6bn, July +50.6bn. The fixture was refreshed
    2026-11-09 after the 2026 annual update (August release) revised everything from January 2021."""
    def change(metric, month):
        s = bea_facts[bea_facts["metric"] == metric].set_index("period_end")["value"]
        return s[pd.Timestamp(month)] - s[pd.Timestamp(month) - pd.offsets.MonthEnd(1)]
    assert abs(change("pce_total_saar", "2026-09-30") - 113.1) < 0.06
    assert abs(change("pce_goods_saar", "2026-09-30") - 35.1) < 0.06
    assert abs(change("pce_services_saar", "2026-09-30") - 78.1) < 0.06
    assert abs(change("pce_total_saar", "2026-08-31") - 193.6) < 0.06
    assert abs(change("pce_total_saar", "2026-07-31") - 50.6) < 0.06


def test_series_shape(bea_facts, meta):
    cols = ["metric", "entity", "tier", "period_type"]
    listed = {tuple(r) for r in series_for_source(meta, bea.SOURCE)[cols].itertuples(index=False)}
    loaded = {tuple(r) for r in bea_facts[cols].drop_duplicates().itertuples(index=False)}
    assert loaded == listed and len(loaded) == 10
    interest = bea_facts[bea_facts["metric"] == "hh_interest_payments_saar"].set_index("period_end")["value"]
    assert abs(interest[pd.Timestamp("2026-09-30")] - 617.925) < 0.001  # billions, from '617,925' millions
    dpi = bea_facts[bea_facts["metric"] == "disposable_income_monthly_saar"].set_index("period_end")["value"]
    assert abs(dpi[pd.Timestamp("2026-09-30")] - dpi[pd.Timestamp("2026-08-31")] - 52.7) < 0.06  # the release: DPI +$52.7bn
    total = bea_facts[bea_facts["metric"] == "pce_total_saar"]
    assert total["period_end"].min() == pd.Timestamp("1959-01-31") and total["period_end"].max() == pd.Timestamp("2026-09-30")
    assert abs(total["value"].iloc[-1] - 22452.78) < 0.001  # billions, from '22,452,780' millions
    assert (bea_facts["period_end"] == bea_facts["period_end"] + pd.offsets.MonthEnd(0)).all()
    assert bea_facts["pulled_at"].unique().tolist() == [PULLED_AT]
    # goods plus services is total
    g = bea_facts[bea_facts["metric"] == "pce_goods_saar"].set_index("period_end")["value"]
    s = bea_facts[bea_facts["metric"] == "pce_services_saar"].set_index("period_end")["value"]
    t = total.set_index("period_end")["value"]
    assert ((g + s - t).abs() < 0.01).all()


def test_subset_lines_keep_only_wanted_codes_and_check_the_header():
    text = "%SeriesCode,Period,Value\nA001RC,2020M01,\"1\"\nDPCERC,2020M01,\"2,000\"\nDPCERC,2020M02,\"2,100\"\n"
    assert bea.subset_lines(text, {"DPCERC"}) == ["%SeriesCode,Period,Value", 'DPCERC,2020M01,"2,000"', 'DPCERC,2020M02,"2,100"']
    with pytest.raises(ValueError, match="does not start with"):
        bea.subset_lines("<!DOCTYPE html><html>not found</html>", {"DPCERC"})


def test_parse_subset_fails_on_gaps_missing_codes_and_ragged_ends(meta):
    mine = series_for_source(meta, bea.SOURCE)
    two = mine[mine["source_id"].isin(["DPCERC", "DGDSRC"])]
    good = ("%SeriesCode,Period,Value\n" + "DPCERC,2020M01,\"1,000\"\nDPCERC,2020M02,\"1,100\"\n"
            + "DGDSRC,2020M01,\"300\"\nDGDSRC,2020M02,\"310\"\n")
    df = bea.parse_subset(good, two, PULLED_AT)
    assert len(df) == 4 and df["value"].tolist() == [1.0, 1.1, 0.3, 0.31]
    with pytest.raises(ValueError, match="months jump"):
        bea.parse_subset(good.replace("DPCERC,2020M02", "DPCERC,2020M04"), two, PULLED_AT)
    with pytest.raises(ValueError, match="no rows"):
        bea.parse_subset(good.replace("DGDSRC", "XXXXXX"), two, PULLED_AT)
    with pytest.raises(ValueError, match="end on different months"):
        bea.parse_subset(good.replace("DGDSRC,2020M02,\"310\"\n", ""), two, PULLED_AT)
    with pytest.raises(ValueError, match="not a number"):
        bea.parse_subset(good.replace("\"310\"", "\"...\""), two, PULLED_AT)


def test_fixture_is_the_subset_format():
    text = BEA_FIXTURE.read_text(encoding="utf-8")
    assert text.startswith(bea.HEADER + "\n") and "A001RC" not in text


# --- conditional GET: the 37 MB file is downloaded only when BEA has changed it -----------------------------------

class _FakeBea:
    """apps.bea.gov as it behaves: an ETag and a Last-Modified on every 200, and a 304 when a conditional request
    names the file it already has."""

    def __init__(self, body: str, etag: str = '"50ff270686cdd1:0"', modified: str = "Wed, 04 Nov 2026 14:23:02 GMT"):
        self.body, self.etag, self.modified, self.requests = body, etag, modified, []

    def get(self, url, headers=None):
        headers = dict(headers or {})
        self.requests.append(headers)
        fake = self

        class R:
            def __init__(self, status, text, hdrs):
                self.status_code, self.text, self.headers = status, text, hdrs

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise AssertionError(self.status_code)

        # RFC 9110: with If-None-Match present the server ignores If-Modified-Since
        unchanged = (headers["If-None-Match"] == fake.etag if "If-None-Match" in headers
                     else headers.get("If-Modified-Since") == fake.modified)
        if unchanged:
            return R(304, "", {"ETag": fake.etag})
        return R(200, fake.body, {"ETag": fake.etag, "Last-Modified": fake.modified})


def _full_file() -> str:
    """The checked-in subset plus a series the crosswalk does not load, the shape of the full NipaDataM.txt."""
    return BEA_FIXTURE.read_text(encoding="utf-8") + 'A001RC,2026M01,"1"\n'


def test_an_unchanged_file_is_not_downloaded_again(meta, tmp_path, capsys):
    mine = series_for_source(meta, bea.SOURCE)
    server = _FakeBea(_full_file())
    first = bea.fetch(mine, tmp_path, server, PULLED_AT)
    assert server.requests == [{}]  # nothing on disk yet: a plain GET
    saved = json.loads((tmp_path / "latest" / bea.VALIDATORS_NAME).read_text(encoding="utf-8"))
    assert saved["etag"] == '"50ff270686cdd1:0"' and saved["last_modified"] == "Wed, 04 Nov 2026 14:23:02 GMT"

    subset = (tmp_path / "latest" / bea.RAW_NAME).read_bytes()

    second = bea.fetch(mine, tmp_path, server, PULLED_AT)
    assert server.requests[1] == {"If-None-Match": '"50ff270686cdd1:0"', "If-Modified-Since": "Wed, 04 Nov 2026 14:23:02 GMT"}
    pd.testing.assert_frame_equal(first, second)  # the 304 path parses the subset on disk to the same facts
    assert "unchanged since Wed, 04 Nov 2026 14:23:02 GMT (HTTP 304)" in capsys.readouterr().out
    assert (tmp_path / "latest" / bea.RAW_NAME).read_bytes() == subset

    server.etag, server.modified = '"new:0"', "Wed, 25 Nov 2026 13:30:00 GMT"  # BEA publishes
    bea.fetch(mine, tmp_path, server, PULLED_AT)
    assert len(server.requests) == 3
    saved = json.loads((tmp_path / "latest" / bea.VALIDATORS_NAME).read_text(encoding="utf-8"))
    assert saved["etag"] == '"new:0"' and saved["codes"] == sorted(mine["source_id"])


def test_a_new_series_in_the_crosswalk_forces_a_full_download(meta, tmp_path):
    mine = series_for_source(meta, bea.SOURCE)
    server = _FakeBea(_full_file())
    bea.fetch(mine.iloc[1:], tmp_path, server, PULLED_AT)  # the subset on disk lacks the first series
    bea.fetch(mine, tmp_path, server, PULLED_AT)
    assert server.requests[1] == {}  # not conditional: the subset on disk was cut for another series list
    assert len(server.requests) == 2


def test_a_subset_that_does_not_parse_does_not_become_the_cache(meta, tmp_path):
    mine = series_for_source(meta, bea.SOURCE)
    good = _FakeBea(_full_file())
    bea.fetch(mine, tmp_path, good, PULLED_AT)
    broken = _FakeBea(_full_file().replace("DPCERC,2026M08", "DPCERC,2026M13"), etag='"broken:0"',
                      modified="Wed, 25 Nov 2026 13:30:00 GMT")  # a file that does not parse: there is no 13th month
    with pytest.raises(ValueError):
        bea.fetch(mine, tmp_path, broken, PULLED_AT)
    # the old validators stay, so the next run asks for the old file, gets the new one in full, and fails loudly
    # again rather than parsing a stale subset under the new file's validators
    assert '"broken:0"' not in (tmp_path / "latest" / bea.VALIDATORS_NAME).read_text(encoding="utf-8")
