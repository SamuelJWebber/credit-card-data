# carddash handoff

Rewritten **2026-09-14**. Read `CLAUDE.md` first for the rules, then this for what is true now.
**Rewrite this file at the end of every session — never append.** Under 150 lines.

## State

**v1 is done.** Task 8 passed on 2026-09-14: two consecutive green *scheduled* runs with all fourteen sources
ok (runs 34726612722 and the 2026-09-14 00:02 run). 383 tests green. 78 charts in 8 panels plus a state tile
map, 68 goldens, live at https://samueljwebber.github.io/credit-card-data/ .

`TASKS.md` is the board and is 725 lines — it is the archive as much as the plan. **Read this file first and
open TASKS.md only for the task you are actually doing.** Do not read it end to end at session start.

## Next

Nothing is in flight. The scope rule applies: v1 is cut, and the board carries 30-plus tasks queued past it.
Pick one deliberately with the user, do not drift into them.

The one real defect worth fixing first: **`make_session()` still emits a User-Agent containing a URL in
parentheses**, which the SEC refuses. `fetchers/issuer_8k.py` carries a private `_sec_headers()` to work
around it, so nothing is broken today — but the next fetcher that touches sec.gov inherits the bug. Fix the
shared default, delete the workaround.

## Moved to SamuelJWebber (2026-11-09)

The repo is now `SamuelJWebber/credit-card-data` and the site https://samueljwebber.github.io/credit-card-data/.
Every owner reference (http.py, render.py, verify_g19.py, verify_releases.py, README, tests, docs/, CLAUDE.md,
AGENTS.md) and the git remote were updated the same day. Old repo and site URLs redirect (see CLAUDE.md, GitHub account).

## Traps that have already cost a day each

- **`checks/verify_releases.py` reads the LOCAL clone.** One commit behind and it reports "no bot commit
  found", so a green release looks like a failure. It has misled a reading twice. `git fetch` first, always.
- **Do not push while a scheduled run is in flight.** It makes the runner's own push a non-fast-forward.
  Task 48 made the job rebase and retry; still check `gh run list --limit 3`.
- The cron is `0 22 * * *` but GitHub runs scheduled jobs late — recent ones landed 23:54, 23:57, 00:02. Not
  gradable until about 01:00 UTC. Only `schedule` events count. Amber shows as "success" in the Actions UI.
- A local `carddash render` rewrites all 77 PNGs (a Windows/Ubuntu freetype difference). `git status` showing
  every image modified is noise — leave `docs/` to the runner.
- Push as SamuelJWebber (`GH_TOKEN=$(gh auth token --user SamuelJWebber)`); never `gh auth switch`, which changes
  the account for every session on the machine.
