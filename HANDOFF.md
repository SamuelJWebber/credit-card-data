# carddash handoff

Rewritten **2026-11-22**. Read `CLAUDE.md` first for the rules, then this for what is true now.
**Rewrite this file at the end of every session, never append.** Under 150 lines.

## State

- The repo is `SamuelJWebber/credit-card-data` (public) and the site https://samueljwebber.github.io/credit-card-data/.
- **The nightly refresh has been green every night from 2026-11-11 to 2026-11-22** (`92df06b`, run `44974148449`, all 14 sources `ok`), so the v1 definition of done (two consecutive green scheduled runs) has held since 11-12.
- **Merged on 2026-11-21:** the sixteen commits of review round 2 (`R2-1` to `R2-6` and improvements 1, 2 and 5).
- **Fixed from the independent Fable review of 2026-11-10** (`REVIEW.md`):
  - On 2026-11-21: `credit-B-1` (with `credit-A-12`, BEA nonmortgage interest labelled as modelled) and `credit-A-3` (`autoescape=True` for `index.html.j2`).
  - On 2026-11-22: `credit-B-3` (`" in dollars"` on record/multi-year flags for dollar-level headlines), `credit-A-4` (six charge-off peaks since 1985 against unemployment in `LABOR_NOTE`), `credit-A-5` (FR 2835 vs FR 2835a panels and definitions on `consumer_loan_rates`), `credit-B-2` (the NY Fed's August 2026 charged-off caveat on `dq_by_loan_type`, `state_card_dq_range`, `state_card_dq_selected` and the state map `#statemap`), `credit-A-6` (method disclosure of the five cross-source charts that draw NSA series against an SA benchmark, plus explicit SA/NSA series labels), and `credit-B-9` (`VIEW_NOTES` and `_view_scope_note` so every SQL view field carries its own "About this chart" scope note rather than its first input's `series.csv` note).
  - Rejected on 2026-11-22: `credit-A-1` (no history rewrite; see below).
  - Still open: `credit-A-2` (needs a matched-panel or top-25 TCCP series drawn), `credit-B-4` and `credit-B-8` (LOW after re-grading), and the dated thesis notes (`credit-B-5`, `credit-B-6`, `credit-B-7`).

## Audit of the three releases during the 2026-11-11 to 2026-11-22 window

1. **NY Fed HHDC 2026 Q3 (`2026-09-30`):** loaded cleanly on `2026-11-11T01:51:15Z` (`03998a9`), advancing `last_period_end` from `2026-06-30` to `2026-09-30` (6,744 to 6,812 rows, +68 rows across 68 series, 0 prior values revised). Status stayed `ok` (`status_since: 2026-11-09T22:55:23Z`) and all live HHDC goldens passed without going amber.
2. **Census Monthly Retail Trade (`2026-09-30`, September data released 2026-11-17):** turned amber (`stale`, 77 and 78 days old against the 76-day default limit, `credit-A-7`) on `2026-11-16T01:50:07Z` (`d64d869`) and `2026-11-17T04:27:36Z` (`4164df3`), then loaded `2026-09-30` on `2026-11-18T03:38:11Z` (`d3ed125`, 4,992 to 5,004 rows, +12 rows across 12 series, 22 revisions) and recovered to `ok` (`status_since: 2026-11-18T03:38:11Z`) with all live Census goldens passing. (The MRTS workbook published in mid-November carries September 2026; the advance October MARTS estimate is not in the workbook.)
3. **FDIC 2026 Q3 (`2026-09-30`):** as of `2026-11-22T02:05:48Z` (`92df06b`), `fdic` is still at `last_period_end: 2026-06-30` (`status: ok`, 28,942 rows, 216 series, 28 revisions logged on `2026-11-17`, all 35 charter names matching); 2026 Q3 call-report data had not yet appeared in the FDIC API (typical lag 50-58 days after quarter end, inside the 7-day grace window around `2026-11-19`).

## Verified, and how

- Fixture-proven: 488 tests (`python -m uv run pytest -q`), including six new regression tests in `tests/test_render.py` covering `credit-B-3`, `credit-A-4`, `credit-A-5`, `credit-B-2`, `credit-A-6` and `credit-B-9`.
- Seen on the committed data: `carddash check` (45 passed, 0 failed), `carddash check --all` (62 passed, 0 failed, 8 fixture-only revised), `carddash health --fail-on-red` (14 `ok`), `carddash attention` (empty, exit 0).
- **Not seen live at the time of writing:** the re-rendered `docs/` on GitHub Pages with the six new review fixes (left to the runner on merge, so local PNGs and CRLF CSVs are not committed).

## Next, in order

1. **FDIC 2026 Q3 and BEA October PIO (due 2026-11-25):** confirm both load cleanly on the nightly refresh.
2. **Early December: the G.19 release.** Run `python checks/verify_g19.py`; on a FAIL, `--rebase` prints the re-based entry.
3. **Remaining deferred findings:** `credit-A-2` (draw the top-25 or matched-panel TCCP offered APR series), `credit-A-7` (`max_age_days: 85` on the 12 Census rows in `crosswalks/series.csv` so normal mid-month release dates do not trip the 76-day staleness limit), and a new dated thesis note addressing `credit-B-5`, `credit-B-6` and `credit-B-7`.

## Needs the user

- `credit-A-1`. **Decided 2026-11-22: no history rewrite.** 73 commits from `2026-09-07` to `2026-09-14` carry a personal address; none since. A rewrite would not purge cached objects on GitHub without Support and would break every cited commit hash and clone. Reverse at any time with `git filter-repo --mailmap` and a force push. Recommended owner setting: GitHub Settings -> Emails -> "Keep my email addresses private" and "Block command line pushes that expose my email".

## Traps that have already cost time

- **`checks/verify_releases.py` reads the LOCAL clone.** `git fetch` first, every time.
- **Do not push while a run is in flight** (`gh run list -R SamuelJWebber/credit-card-data --limit 3`). Every code push starts a refresh run that pushes a bot commit; `git pull --rebase origin main` before each push.
- A local `carddash render` rewrites all 78 PNGs, and a local refresh rewrites the CFPB CSVs with CRLF endings: both are noise. `git checkout -- data docs` and leave both directories to the runner.
- Push as SamuelJWebber with `GH_TOKEN=$(gh auth token --user SamuelJWebber)` per command. Never `gh auth switch`.
- Write any file with backslashes using the file tool, never a Git Bash heredoc.
