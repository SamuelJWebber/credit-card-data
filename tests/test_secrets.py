"""Credentials never reach anything the pipeline writes: the redactor every message passes through, and the
fail-closed scan the workflow runs over data/ and docs/ before it commits."""

from __future__ import annotations

import datetime as dt

import pytest

from carddash.cli import main, write_health
from carddash.loader import SourceHealth, refresh_source
from carddash.redact import redact, scan_paths
from carddash.schema import empty_facts
from conftest import PULLED_AT, REPO

FAKE_KEY = "fake0key0for0tests0only0abcdef12"
FAKE_CONTACT = "someone@example.invalid"


@pytest.fixture
def secrets_set(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", FAKE_KEY)
    monkeypatch.setenv("CARDDASH_CONTACT", FAKE_CONTACT)


def test_redact_removes_secret_values_and_query_credentials(secrets_set):
    text = (f"HTTPError: 400 for url: https://api.example/obs?series_id=REVOLSL&api_key={FAKE_KEY}&file_type=json; "
            f"user agent carddash/0.1.0 {FAKE_CONTACT}; https://x.example/a?token=abc123def456&b=1; apikey=zzz999yyy")
    out = redact(text)
    for secret in (FAKE_KEY, FAKE_CONTACT, "abc123def456", "zzz999yyy"):
        assert secret not in out
    assert "series_id=REVOLSL" in out and "file_type=json" in out and "&b=1" in out  # only the credentials go
    assert redact("nothing to hide: 4 of 28 names, key column period_end") == "nothing to hide: 4 of 28 names, key column period_end"


def test_redact_without_secrets_in_the_environment(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.delenv("CARDDASH_CONTACT", raising=False)
    assert "abc123def456" not in redact("https://x.example/a?api_key=abc123def456")
    assert redact("") == ""


def test_the_loader_redacts_any_fetch_error_not_just_freds(secrets_set, meta, tmp_paths):
    """Defence in depth: a future fetcher that lets a URL with a credential into its exception text is still safe."""
    def leaky_fetch(meta, raw_dir, session, pulled_at):
        raise RuntimeError(f"GET https://data.example/v1?series=A&api_key={FAKE_KEY}&token=abc123def456 failed")

    _, health, _ = refresh_source("fred", empty_facts(), meta, leaky_fetch, tmp_paths.raw / "fred", None,
                                  dt.date(2026, 9, 8), PULLED_AT, set())
    assert health.status == "failed" and "series=A" in health.messages[0]
    assert FAKE_KEY not in health.messages[0] and "abc123def456" not in health.messages[0]


def test_health_json_is_redacted_however_a_message_got_in(secrets_set, tmp_paths):
    h = SourceHealth(source="fred")
    h.messages.append(f"warning: something echoed {FAKE_CONTACT} and ?api_key={FAKE_KEY}")  # appended, not via worsen
    h.worsen("failed", f"fetch error: {FAKE_KEY}")
    write_health(tmp_paths, {"fred": h}, PULLED_AT)
    written = tmp_paths.health_json.read_text(encoding="utf-8")
    assert FAKE_KEY not in written and FAKE_CONTACT not in written and "something echoed" in written


def test_scan_finds_secret_values_and_query_credentials_without_printing_them(secrets_set, tmp_path):
    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "facts.csv").write_text("metric,value\nrevolving_credit_sa,1368.45\n", encoding="utf-8")
    (clean / "page.html").write_text('<a href="https://fred.stlouisfed.org/series/REVOLSL?cid=1">x</a>', encoding="utf-8")
    assert scan_paths([clean]) == []

    dirty = tmp_path / "dirty"
    (dirty / "raw").mkdir(parents=True)
    (dirty / "health.json").write_text(f'{{"messages": ["for url: https://h/x?id=1&api_key={FAKE_KEY}"]}}\n', encoding="utf-8")
    (dirty / "raw" / "blob.png").write_bytes(b"\x89PNG\r\n\x1a\n" + FAKE_CONTACT.encode() + b"\x00\x01")
    (dirty / "page.html").write_text("<p>\n?token=abc123def456\n</p>", encoding="utf-8")
    found = scan_paths([dirty])
    assert {(f.path.name, f.kind) for f in found} == {
        ("health.json", "value of FRED_API_KEY"),
        ("health.json", "credential parameter"),
        ("blob.png", "value of CARDDASH_CONTACT"),
        ("page.html", "credential parameter"),
    }
    assert next(f.line for f in found if f.path.name == "page.html") == 2
    assert not any(FAKE_KEY in str(f) or FAKE_CONTACT in str(f) or "abc123def456" in str(f) for f in found)


def test_scan_secrets_command_fails_closed(secrets_set, tmp_path, capsys):
    (tmp_path / "health.json").write_text(f"api_key={FAKE_KEY}", encoding="utf-8")
    assert main(["scan-secrets", str(tmp_path)]) == 1
    out = capsys.readouterr()
    assert "health.json:1" in out.out + out.err and FAKE_KEY not in out.out + out.err
    (tmp_path / "health.json").write_text("{}", encoding="utf-8")
    assert main(["scan-secrets", str(tmp_path)]) == 0
    assert main(["scan-secrets", str(tmp_path / "does-not-exist")]) == 2  # a typo in the workflow must not pass


def test_the_committed_tree_carries_no_query_credentials(monkeypatch):
    """The same scan the workflow runs before it commits, over the tree as checked out (patterns only: the test run
    has no secret values to look for)."""
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.delenv("CARDDASH_CONTACT", raising=False)
    found = scan_paths([REPO / "data", REPO / "docs", REPO / "checks"])
    assert found == [], "\n".join(str(f) for f in found)
