"""One honest User-Agent for every host (REVIEW.md R1-14)."""

from __future__ import annotations

import re

import pytest

from carddash import __version__
from carddash.http import make_session, require_contact, user_agent
from conftest import REPO


def test_every_session_sends_the_url_free_form_the_sec_accepts(monkeypatch):
    """make_session used to send 'carddash/<v> (+https://github.com/...) <contact>', which the SEC's edge refuses;
    issuer_8k carried its own header to get around it, and the next sec.gov fetcher would have inherited the bug."""
    monkeypatch.setenv("CARDDASH_CONTACT", "someone@example.com")
    ua = make_session().headers["User-Agent"]
    assert ua == f"carddash/{__version__} someone@example.com"
    assert "(" not in ua and "://" not in ua
    monkeypatch.delenv("CARDDASH_CONTACT")
    assert make_session().headers["User-Agent"] == f"carddash/{__version__}"


def test_a_url_is_never_a_contact(monkeypatch):
    with pytest.raises(ValueError, match="not a URL"):
        user_agent("https://example.com")
    monkeypatch.setenv("CARDDASH_CONTACT", "(+https://example.com)")
    assert make_session().headers["User-Agent"] == f"carddash/{__version__}"  # dropped, not sent
    with pytest.raises(ValueError):
        require_contact()


def test_nothing_in_the_code_builds_its_own_user_agent():
    """The one place is http.user_agent; a second string is how the SEC workaround started."""
    offenders = []
    for path in list((REPO / "src").rglob("*.py")) + list((REPO / "checks").glob("*.py")):
        if path.name == "http.py":
            continue
        text = path.read_text(encoding="utf-8")
        # a User-Agent header set to anything but http.user_agent(...)
        if re.search(r"""["']User-Agent["']\s*(?::|\]\s*=)(?!\s*user_agent\()""", text):
            offenders.append(str(path.relative_to(REPO)))
    assert not offenders, offenders
