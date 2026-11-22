# carddash handoff

Rewritten **2026-11-21** (Claude Code). Read `CLAUDE.md` first for the rules, then this for what is true now.
**Rewrite this file at the end of every session, never append.** Under 150 lines.

## State

- The repo is `SamuelJWebber/credit-card-data` (public) and the site https://samueljwebber.github.io/credit-card-data/.
- **The nightly refresh has been green every night from 2026-11-11 to 2026-11-21** (`gh run list`), so the v1
  definition of done (two consecutive green scheduled runs) has held since 11-12.
- **Merged on 2026-11-21:** the sixteen commits of review round 2 that had sat on the local branch
  `wip/paused-2026-11-10` since the pause (rebased onto `main`, 482 tests pass). They bring: `verify_releases.py`
  grading each run by the commit that run made (R2-1); the notices the FRED API terms and the SCE licence require,
  on the page and on each PNG (R2-2); golden provenance links (R2-3); **`checks/verify_g19.py` failing closed when
  the Fed's page does not load** (R2-4); two new workflows, `watch.yml` (daily 12:41 UTC: opens an issue after a
  night with no scheduled refresh run) and `provenance.yml` (Mondays 12:17 UTC: every golden against the document
  it cites); and the failure issue naming the sources that failed.
- **Fixed on 2026-11-21, from the independent review of 2026-11-10** (`REVIEW.md`, top table and the status table
  under it): credit-B-1, the chart that was titled "Interest households actually pay" now says it is BEA's modelled
  series; credit-A-3, HTML escaping is on for the whole page. Thirteen other findings are deferred, listed there.

## Verified, and how

- Fixture-proven: 482 tests (`.venv\Scripts\python.exe -m pytest -q`, about 12 minutes on a busy machine), including a
  script tag rendered through a health message and the new chart title.
- Seen on the committed data: the page rendered from `data/` into a scratch folder before and after turning
  escaping on differs only in apostrophes and URL ampersands; with the merge it carries the Notices block and no
  escaped tag outside the scripts.
- **Not seen live at the time of writing:** the page on GitHub Pages with the new title and Notices block (the push
  starts a refresh run that re-renders `docs/`); the first runs of `watch.yml` and `provenance.yml`. Both new
  workflows can open issues, which notify the owner.

## Next, in order

1. After the push's refresh run finishes: open the live page, find the chart `effective_rate`, and confirm its title
   starts "BEA's modelled nonmortgage interest". Check `gh run list` for `watch` (after 12:41 UTC) and `provenance`
   (the next Monday).
2. **Early December: the G.19 release.** Run `python checks/verify_g19.py`; on a FAIL, `--rebase` prints the re-based
   entry. It now exits non-zero when the Fed's page did not load, instead of passing.
3. The deferred review findings, cheapest first: credit-B-3 ("in dollars" on the record flag), credit-A-4 (one
   sentence), credit-A-5, credit-B-2 (the NY Fed's charged-off caveat on four charts), credit-A-6, credit-B-9,
   credit-A-2 (needs a new series). The thesis notes (B-5, B-6, B-7) are edited by hand and dated.
4. Dates from the old handoff that passed while everything was paused and were not graded: NY Fed HHDC 2026 Q3
   (about 11-11), FDIC 2026 Q3 (about 11-19), Census October (11-17). The nightly stayed green through all three;
   nobody has read whether a golden went amber and recovered. `carddash attention` and the open issues say.
5. BEA October PIO is due 2026-11-25.

## Needs the user

- credit-A-1. **Decided 2026-11-22: no history rewrite** (the owner said "make the decision and do it"). 73
  commits here carry a personal address, none since 2026-09-14; the repo has no forks. A rewrite would not remove
  the address from GitHub (old commits stay reachable by hash until GitHub Support purges them, and public push-
  event archives keep author addresses), and it would change every commit hash these review and handoff files cite
  and break every clone and the scheduled jobs' pushes. The leak is already stopped: every commit since uses the
  noreply address, held by the hook and tests. Reverse by running `git filter-repo --mailmap` and force-pushing;
  nothing done today prevents it. One account setting would also stop it at the source and is the owner's own:
  GitHub Settings, Emails, "Keep my email addresses private" and "Block command line pushes that expose my email".

## Traps that have already cost time

- **`checks/verify_releases.py` reads the LOCAL clone.** `git fetch` first, every time.
- **Do not push while a run is in flight** (`gh run list -R SamuelJWebber/credit-card-data --limit 3`). Every push
  that touches code (anything but data/, docs/ and *.md) starts a full refresh run, which then pushes a bot commit:
  `git pull --rebase origin main` before each push, and expect commit hashes to change in that rebase.
- The cron is `0 22 * * *` but recent scheduled runs started between 00:55 and 03:25 UTC. Only `schedule` events
  count. Amber shows as success in the Actions UI; the `source-attention` issue is what says so now.
- `workflow_dispatch` with `fail_on_purpose: true` tests the failure issue without fetching anything, but it notifies
  the owner's phone. Use it only to test that path.
- A local `carddash render` rewrites all 78 PNGs, and a local refresh rewrites the CFPB CSVs with CRLF endings: both
  are noise. `git checkout -- data docs` and leave both directories to the runner.
- Push as SamuelJWebber with `GH_TOKEN=$(gh auth token --user SamuelJWebber)` per command. Never `gh auth switch`:
  it changes the account for every session on the machine.
- Git Bash heredocs un-double backslashes and turn `\n` into line breaks (it bit four times this round, once as a
  backspace inside a regex). Write any file with backslashes using the file tool.
