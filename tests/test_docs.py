"""What the working agreements, the comments and the page say must still be what the code does (REVIEW.md R2-5).

CLAUDE.md went on calling issuer_8k the 'ONE EXCEPTION' to the User-Agent rule after R1-14 gave every host the same
agent, so the two files both assistants read contradicted each other. The page said every source is fetched in full
every run after BEA stopped being, and the Amex notes on the page and in the fetcher described an overlap the page
does not draw. Each phrase below was true once; this keeps it from coming back.
"""

from __future__ import annotations

from conftest import REPO

STALE = {
    "ONE EXCEPTION": "every request sends http.user_agent() since R1-14; no fetcher has its own",
    "(+repo url)": "the URL-form User-Agent is not sent any more (the SEC refuses it)",
    "normal User-Agent": "there is one User-Agent, not a normal one and an SEC one",
    "ends in March 2026": "the retired Amex series ends at January 2026 on the page",
    "overlap for February and March": "the page's two Amex lines do not overlap",
    "the two overlapping months": "the page's two Amex lines do not overlap",
    "fetched in full every run": "BEA, NCUA and the 8-K filings are not",
}


def _files():
    yield from (REPO / name for name in ("CLAUDE.md", "AGENTS.md", "README.md"))
    yield from (REPO / ".github" / "workflows").glob("*.yml")
    yield from (REPO / "src" / "carddash").rglob("*.py")
    yield from (REPO / "src" / "carddash" / "templates").glob("*.j2")
    yield from (REPO / "crosswalks").glob("*.csv")
    yield from (REPO / "checks").glob("*.py")


def test_nothing_says_what_the_code_stopped_doing():
    found = []
    for path in _files():
        text = path.read_text(encoding="utf-8")
        for phrase, why in STALE.items():
            if phrase in text:
                found.append(f"{path.relative_to(REPO)}: '{phrase}' ({why})")
    assert not found, "\n".join(found)


def test_both_working_agreements_name_the_one_user_agent():
    for name in ("CLAUDE.md", "AGENTS.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert "carddash/<version> <CARDDASH_CONTACT>" in text and "http.user_agent()" in text, name


def test_the_page_says_which_sources_are_not_fetched_in_full():
    template = (REPO / "src" / "carddash" / "templates" / "index.html.j2").read_text(encoding="utf-8")
    lede = template.split('<h2 id="health">')[1].split("</p>")[0]
    assert "BEA" in lede and "NCUA" in lede and "8-K" in lede
