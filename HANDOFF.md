# carddash handoff

Rewritten **2026-11-10 00:15 UTC**, at the end of review round 1 (REVIEW.md). Read `CLAUDE.md` first for the rules,
then this for what is true now. **Rewrite this file at the end of every session, never append.** Under 150 lines.

## State

- The repo is `SamuelJWebber/credit-card-data` (public) and the site https://samueljwebber.github.io/credit-card-data/.
  It moved from User5017 on 2026-11-09; the old repo and site URLs redirect (CLAUDE.md, "GitHub account").
- **The nightly was broken from 2026-10-08 to 2026-11-09**: all 33 scheduled runs failed (Philly Fed header spacing,
  the Comenity Bank merger) and bea and census sat amber. `de676d3` fixed it. Every push run since is green, and the
  newest (42724802764, 2026-11-10 00:03 UTC) had all 14 sources `ok`. **No scheduled run has been green since
  2026-10-07**: the first one after the fix is tonight's.
- Review round 1: all 16 findings fixed (2 HIGH, 6 MEDIUM, 8 LOW), each with a test that fails on the old code, and
  REVIEW.md has a status line with the commit under each. Five of the seven bigger improvements are done.
- 440 tests pass (`python -m uv run pytest`, 6 min on this machine while it is busy).

## What this round changed

- R1-1 `7b05d86`: no credential reaches health.json, the page or the repo; `carddash scan-secrets` gates `git add`.
- R1-2 `2e682fd`: the APR-over-prime spread uses the prime rate of the survey month (2026 Q3 is 15.61, not 15.49).
- R1-3 and R1-10 `9ee8310`: a failed run opens a `refresh-failure` issue that @mentions the owner and the next good
  run closes it; a `source-attention` issue stays open while a source is amber for a week (`carddash attention`,
  `status_since` in health.json). A red source reports the rows it still serves.
- R1-4 `03daf33`: live goldens sit outside each source's revision window (`golden.MIN_LIVE_AGE_MONTHS`, tested);
  BEA's live entry is now April 2026's DPI change (+12.7); July and August are fixture-only.
- R1-5 `7290f78`, R1-6 `aabfb42`: revised fixture-only goldens are drawn neutrally, no `%g`; `carddash check` checks
  the live entries (45 pass) and `--all` lists the 7 revised ones as REVISED.
- R1-8 `7a12bf9`: every FRED series is credited to its publisher (series.csv `publisher`, `rights`).
- R1-9 `07d66a3`: the SEC edge's injected script is stripped; issuer_8k files change only when their bytes do.
- R1-11 `9ce46fb`: goldens link dated releases; `checks/verify_g19.py --provenance`; `--rebase` (`087635e`).
- R1-14 `2998aa5`: one User-Agent everywhere, `carddash/<version> <CARDDASH_CONTACT>` (`http.user_agent()`).
- R1-15 `1eb85ce`: the four credit unions the ncua source tracks no longer show as unmatched TCCP names.
- R1-16 `9124f1a`: actions pinned to commits; each run pulls main first. R1-12/13: docs and paths.
- Improvements: page banners and README badge (`37fb078`); BEA conditional GET (`d166e30`, `563118a`).

## Verified, and how

Seen live:
- The failure issue: dispatch run 42716371879 (`fail_on_purpose`) opened issue #1; push run 42717110744 closed it
  with a "Recovered" comment.
- The URL-free User-Agent: 15 host families answered 200 from this machine, and every push run since loaded all 14.
- The page: docs/latest.txt reads "15.61 pp in 2026 Q3"; the sentiment chart says "University of Michigan, via FRED"
  with Michigan's copyright line; revised goldens read "as first published ..., since revised to 1,347.84".
- BEA answers a conditional GET with 304 (both validators). The runner wrote the validators at 23:58 UTC, and a full
  local refresh at 00:08 took the 304 path ("NipaDataM.txt unchanged since Wed, 04 Nov 2026 ... (HTTP 304)").
- issuer_8k: the 00:03 bot commit (`be474c9`) touched no raw issuer file; no_metrics.json is 8 entries, 8 distinct.
- `checks/verify_g19.py --provenance`: 13 of 13 PASS; default mode 12 PASS, 1 SKIP (May 2026 left the page).
- The three census goldens match Table 1 of the 2026-10-15 release PDF (the check REVIEW.md had not run).
- Main commands, 2026-11-10 00:05-00:10 UTC: `carddash check` 45 pass, exit 0; `check --all` 63 pass and 7 REVISED,
  exit 0; `health --fail-on-red` 0; `issuers` all 28 TCCP names matched; `attention` empty; `scan-secrets data docs
  checks/restatement_ack.yaml` 0 findings with both secrets loaded; a full local `refresh --no-render` 14 ok in 67 s;
  `render` exit 0 (both local runs then reverted with `git checkout -- data docs`).
- `checks/verify_releases.py --limit 6`: exit 1, "NOT YET ... 0 of 2". Expected: the six newest scheduled runs are
  outage runs.

Fixture-proven only (not yet seen live):
- The attention issue (nothing has been amber for a week since it shipped).
- The stale-page banner (its script was run under node against a rendered page, not in a browser) and the
  red-source banner (render test).
- BEA keeping its old validators when a new subset fails to parse (fake-server test).

## Next, in order

1. **Grade tonight's scheduled run** after about 03:30 UTC: `git fetch`, then
   `python -m uv run python checks/verify_releases.py --limit 3`. Expect the newest scheduled run green with all 14 `ok`.
   In its log, bea should print the HTTP 304 line unless BEA changed the file; its bot commit should touch nothing under
   data/raw/issuer_8k. If it failed, issue "The refresh is failing" will already be open with the run linked.
2. A second green scheduled run in a row restores the v1 definition of done (task 8's measure).
3. Dates that will move something:
   - about 2026-11-11: NY Fed HHDC 2026 Q3. Four hhdc live goldens are Q2 2026; if the release revises Q2, hhdc goes
     amber: re-base on the new press release.
   - about 2026-11-16: Census posts its own copy of the 2026-10-15 release,
     www2.census.gov/retail/releases/historical/marts/adv2609.pdf. The census goldens link the Internet Archive's copy
     of it; switching to the Census copy once it opens is optional.
   - 2026-11-17: Census October release. The live census goldens (July, revised) do not move.
   - about 2026-11-19: FDIC 2026 Q3, the first night the Comenity "report through Q3" branch (de676d3) runs for real.
   - 2026-11-25: BEA October PIO. July and August are fixture-only now, so bea should stay `ok`.
   - early December: G.19. Run `verify_g19.py`; on a FAIL, `verify_g19.py --rebase` prints the re-based entry.
4. Known open item: the two nyfed_sce goldens link the NY Fed's undated credit-access page; no dated copy exists.
5. Suggestions for the user (the scope rule; REVIEW.md improvements 6 and 7): one published copy of facts.csv and
   revisions.csv (docs/data/ duplicates data/, .git is about 104 MiB), which changes the page's download URLs; and
   credit unions on the issuer charts, which needs a call on mixing NCUA and call-report definitions.

## Needs the user

Nothing. No permission wall was hit this round. One preference worth a look: the alert issues reach the phone only if
GitHub notifications for SamuelJWebber (mentions and issues on this repo) are on.

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
