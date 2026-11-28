# carddash handoff

Rewritten **2026-11-28**. Read `CLAUDE.md` first for the rules, then this for what is true now.
**Rewrite this file at the end of every session, never append.** Under 150 lines.

## State

- The repo is `SamuelJWebber/credit-card-data` (public) and the site https://samueljwebber.github.io/credit-card-data/.
- The November 28 scheduled run recorded 13 of 14 sources as `ok`. BEA has shown `golden_mismatch` since November 26. See the release audit below.
- **All non-thesis Fable review findings (`REVIEW.md`) are now fixed on `main`:**
  - `credit-B-1` (with `credit-A-12`) & `credit-A-3` (`autoescape=True`) — 2026-11-21.
  - `credit-B-3` (`" in dollars"` on dollar-level record flags), `credit-A-4` (six charge-off peaks since 1985), `credit-A-5` (FR 2835 vs FR 2835a), `credit-B-2` (NY Fed Aug 2026 charged-off caveat on all four stock delinquency views + state map), `credit-A-6` (SA vs NSA cross-source disclosures across all mixed charts including `effective_rate` and `card_volume_vs_retail`), `credit-B-9` (`VIEW_NOTES` covering every non-`facts` `(view, field)` including `v_offered_vs_paid.top25_spread_pct_pts`).
  - `credit-A-2` (`TCCP_TOP25` matched statutory offered APR panel + `_tccp_respondent_note` >20% swing flag), `credit-A-7` (`max_age_days=85` on Census, expected lag 48d), `credit-A-9 (#1–#8)`, `credit-A-10`, `credit-A-11`, `credit-A-13` (root MIT `LICENSE` + `LICENSE-uPlot`), `credit-B-4`, `credit-B-8`, `credit-B-11`, and fail-closed hardening of `checks/verify_g19.py` & `checks/verify_releases.py`.
  - Rejected by owner (2026-11-22): `credit-A-1` (no history rewrite).
  - Untouched dated artifacts: thesis notes (`credit-B-5`, `credit-B-6`, `credit-B-7`).

## Audit of November 2026 releases

1. **NY Fed HHDC 2026 Q3 (`2026-09-30`):** loaded cleanly on `2026-11-11` (`03998a9`, +68 rows, 0 revisions, all goldens green).
2. **Census Monthly Retail Trade (`2026-09-30`):** tripped 76-day limit on `11-16`/`11-17` (now fixed by `max_age_days=85`), loaded cleanly on `2026-11-18` (`d3ed125`, +12 rows, 22 revisions) and recovered to `ok`.
3. **FDIC 2026 Q3:** the November 28 snapshot has `2026-09-30` loaded and the source is `ok`.
4. **BEA October PIO:** BEA revised six months of disposable income. The April change went from +$12.733bn in the September vintage to −$1.156bn. The November 25 historical comparisons workbook prints a January increase of $217.8bn. Both vintages reproduce $217.808bn. The branch keeps April as a fixture check and uses January for nightly validation at the original tolerance. [BEA release](https://www.bea.gov/news/2026/personal-income-and-outlays-october-2026) · [Historical comparisons](https://www.bea.gov/sites/default/files/2026-11/pi1026-hist.xlsx).

## Verified, and how

- Against the November 28 facts, `carddash check` goes from 44 passes and one failure on main to 45 passes. The BEA provenance checker passes seven entries against three source documents. The October fixture replays all 33 revisions. A BEA-only refresh on a copy of the November 28 dataset received HTTP 304 from BEA and parsed all 8,140 cached rows across ten series with status `ok`.
- Zero local `data/` or `docs/` churn committed; GitHub Actions rebuilds rendered outputs on push.

## Next, in order

1. After this branch lands, verify the next scheduled run records BEA as `ok`. The next annual revision could change January as well.
2. **Early December G.19 release:** run `python checks/verify_g19.py`; inspect diffs with `--provenance --dry-run` before approving `--rebase`.
3. Optional: author a new dated thesis note superseding the 2026-09-11 note (`credit-B-5`, `B-6`, `B-7`).

## Needs the user

- `credit-A-1`: **decided 2026-11-22, no history rewrite** (commits since `2026-09-14` carry noreply; optional GitHub Settings -> Emails -> "Keep my email addresses private").

## Traps that have already cost time

- **`checks/verify_releases.py` reads the LOCAL clone.** `git fetch` first.
- **Do not push while a run is in flight** (`gh run list -R SamuelJWebber/credit-card-data --limit 3`).
- Do not commit local `data/` CRLF churn or `docs/` PNGs on Windows; leave both directories to the Actions runner.
- Push as SamuelJWebber with `GH_TOKEN=$(gh auth token --user SamuelJWebber)` per command. Never `gh auth switch`.
