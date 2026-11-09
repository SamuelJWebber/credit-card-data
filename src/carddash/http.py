"""One HTTP session for every fetcher: identifies itself, retries transient failures, never hangs."""

from __future__ import annotations

import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import __version__

DEFAULT_TIMEOUT = 60


class _TimeoutAdapter(HTTPAdapter):
    def send(self, request, **kwargs):  # type: ignore[override]
        kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
        return super().send(request, **kwargs)


def user_agent(contact: str | None = None) -> str:
    """'carddash/<version> <contact>': the pipeline's name and a contact address, nothing else.

    The SEC asks for exactly this form, and its edge answers 403 to any User-Agent holding a URL in parentheses,
    which is what this used to send ('carddash/0.1.0 (+https://github.com/...)'; verified 2026-09-11 on every SEC
    host). One form for every host, so no fetcher needs its own (REVIEW.md R1-14). Never a browser string: the
    CFPB's edge blocks browser-like agents sent from scripts. `contact` defaults to CARDDASH_CONTACT."""
    contact = (os.environ.get("CARDDASH_CONTACT", "") if contact is None else contact).strip()
    if "://" in contact or "(" in contact:
        raise ValueError("CARDDASH_CONTACT must be a contact address, not a URL: the SEC's edge refuses URLs")
    return f"carddash/{__version__} {contact}".rstrip()


def require_contact() -> str:
    """CARDDASH_CONTACT, or a loud failure: the SEC requires a declaring contact and is not defaulted one."""
    contact = os.environ.get("CARDDASH_CONTACT", "").strip()
    if not contact:
        raise RuntimeError(
            "CARDDASH_CONTACT must be set to a contact address (.env locally, an Actions secret in the workflow): "
            "the SEC requires a declaring contact in the User-Agent."
        )
    user_agent(contact)  # the same checks: an address, not a URL
    return contact


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = _TimeoutAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    try:
        session.headers["User-Agent"] = user_agent()
    except ValueError:  # a malformed contact must not take every source down; issuer_8k refuses it loudly
        session.headers["User-Agent"] = user_agent("")
    return session
