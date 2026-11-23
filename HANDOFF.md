# carddash handoff

Rewritten **2026-11-23**. Read `CLAUDE.md` first for the rules, then this for what is true now.
**Rewrite this file at the end of every session, never append.** Under 150 lines.

## State

- The repo is `SamuelJWebber/credit-card-data` (public) and the site https://samueljwebber.github.io/credit-card-data/.
- **The nightly refresh has been green every night from 2026-11-11 to 2026-11-23** (all 14 sources `ok`).
- **All non-thesis Fable review findings (`REVIEW.md`) are now fixed on `main`:**
  - `credit-B-1` (with `credit-A-12`) & `credit-A-3` (`autoescape=True`) — 2026-11-21.
  - `credit-B-3` (`" in dollars"` on dollar-level record flags), `credit-A-4` (six charge-off peaks since 1985), `credit-A-5` (FR 2835 vs FR 2835a), `credit-B-2` (NY Fed Aug 2026 charged-off caveat on all four stock delinquency views + state map), `credit-A-6` (SA vs NSA cross-source disclosures across all mixed charts including `effective_rate` and `card_volume_vs_retail`), `credit-B-9` (`VIEW_NOTES` covering every non-`facts` `(view, field)` including `v_offered_vs_paid.top25_spread_pct_pts`).
  - `credit-A-2` (`TCCP_TOP25` matched statutory offered APR panel + `_tccp_respondent_note` >20% swing flag), `credit-A-7` (`max_age_days=85` on Census, expected lag 48d), `credit-A-9 (#1–#8)`, `credit-A-10`, `credit-A-11`, `credit-A-13` (root MIT `LICENSE` + `LICENSE-uPlot`), `credit-B-4`, `credit-B-8`, `credit-B-11`, and fail-closed hardening of `checks/verify_g19.py` & `checks/verify_releases.py`.
  - Rejected by owner (2026-11-22): `credit-A-1` (no history rewrite).
  - Untouched dated artifacts: thesis notes (`credit-B-5`, `credit-B-6`, `credit-B-7`).

## Audit of November 2026 releases

1. **NY Fed HHDC 2026 Q3 (`2026-09-30`):** loaded cleanly on `2026-11-11` (`03998a9`, +68 rows, 0 revisions, all goldens green).
2. **Census Monthly Retail Trade (`2026-09-30`):** tripped 76-day limit on `11-16`/`11-17` (now fixed by `max_age_days=85`), loaded cleanly on `2026-11-18` (`d3ed125`, +12 rows, 22 revisions) and recovered to `ok`.
3. **FDIC 2026 Q3 (`2026-09-30`):** still at `2026-06-30` as of `2026-11-22` (within normal 50–58d lag window around `2026-11-19`).

## Verified, and how

- Full offline `pytest` suite passes after merging PR #2 and PR #3 cleanly (`test_render.py`, `test_tccp.py`, `test_verify_g19.py`, `test_verify_releases.py`, `test_bea.py`, `test_secrets.py`, `test_docs.py`).
- Zero local `data/` or `docs/` churn committed; GitHub Actions rebuilds rendered outputs on push.

## Next, in order

1. **FDIC 2026 Q3 and BEA October PIO (due ~2026-11-25):** confirm both load cleanly on the nightly refresh.
2. **Early December G.19 release:** run `python checks/verify_g19.py`; inspect diffs with `--provenance --dry-run` before approving `--rebase`.
3. Optional: author a new dated thesis note superseding the 2026-09-11 note (`credit-B-5`, `B-6`, `B-7`).

## Needs the user

- `credit-A-1`: **decided 2026-11-22, no history rewrite** (commits since `2026-09-14` carry noreply; optional GitHub Settings -> Emails -> "Keep my email addresses private").

## Traps that have already cost time

- **`checks/verify_releases.py` reads the LOCAL clone.** `git fetch` first.
- **Do not push while a run is in flight** (`gh run list -R SamuelJWebber/credit-card-data --limit 3`).
- Do not commit local `data/` CRLF churn or `docs/` PNGs on Windows; leave both directories to the Actions runner.
- Push as SamuelJWebber with `GH_TOKEN=$(gh auth token --user SamuelJWebber)` per command. Never `gh auth switch`.
