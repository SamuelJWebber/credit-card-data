# Review round 1 (2026-11-09)

Adversarial review of carddash at `bdf012a` (origin/main after the two 2026-11-09 bot refreshes that followed
`de676d3`, "Fix the nightly refresh"). No earlier REVIEW.md existed, so there were no previous fixes to re-check.
This file reports; it changes no code.

What was run, locally on Windows, against a fetched and fast-forwarded clone:

- `python -m uv run pytest`: **386 passed** in 172 s.
- `python -m uv run carddash check`: 62 passed, 7 failed, exit 1 (see R1-6).
- `python -m uv run carddash health --fail-on-red`: all 14 sources `ok`, exit 0. `carddash issuers`: runs, exit 0.
- `checks/verify_g19.py` against the live G.19 page: 12 PASS, 1 SKIP, exit 0.
- `checks/verify_releases.py --limit 6` (after `git fetch`): the 6 newest *scheduled* runs are all "not green", exit 1.
- Independent re-derivation of eleven headline numbers straight from `data/raw/` with plain `json`, `csv`,
  `zipfile` and `openpyxl` (no `carddash` import), golden numbers checked against three live release pages, a
  secret scan of the whole history, the keyless FRED path run live, and the published page read as text.

Counts: **2 HIGH, 6 MEDIUM, 8 LOW.**

---

## Findings

### R1-1 HIGH: a FRED HTTP or network error publishes the FRED API key in the public repo and on the Pages site

- **Evidence.** `src/carddash/fetchers/fred.py:111-120` sends the key as a query parameter
  (`params={..., "api_key": api_key, ...}`) and calls `resp.raise_for_status()`. The text of a `requests`
  `HTTPError` or `ConnectionError` carries the full URL, query string included. `src/carddash/loader.py:270`
  stores `f"fetch error: {type(exc).__name__}: {exc}"` in the source's health messages. `cli.py:94` writes them to
  `data/health.json`, `templates/index.html.j2:371-373` prints them on the page, and
  `.github/workflows/refresh.yml:46-51` commits `data` and `docs` with `if: always()`. GitHub masks secrets in
  Actions logs only. It does not mask them in committed files.
- **Reproduced** with a fake key and a local server, through the project's own `loader.refresh_source`:
  `fetch error: HTTPError: 400 Client Error: Bad Request for url: http://127.0.0.1:56252/fred/series/observations?series_id=REVOLSL&api_key=FAKEKEY0123456789&file_type=json&observation_start=1900-01-01`.
  The connection-refused case gives `ConnectionError: ... Max retries exceeded with url: /fred/series/observations?series_id=REVOLSL&api_key=FAKEKEY0123456789...`.
- **Likelihood.** FRED has already failed once on a scheduled run: on 2026-10-22, `health.json` recorded
  `fred failed: fetch error: JSONDecodeError`. That message happened to carry no URL. One 5xx after the four
  retries, a 429 or a timeout would have published the key. `git log --all -S "api_key="` finds nothing, so it
  has not leaked yet.
- **Fix.** (1) In `fred._download`, catch `requests.RequestException` and re-raise
  `RuntimeError(f"{sid}: FRED API HTTP {status}")` from `None`, with no URL. (2) As defence in depth, in
  `loader.refresh_source`, redact `(?i)(api_key|apikey|token|key)=[^&\s]+` from every message before it enters
  `SourceHealth`. (3) In the workflow, before `git add`, add a step that fails closed if
  `grep -rIE 'api_key=|apikey=' data docs` matches anything.
- **Verify.** Add a test to `tests/test_fred.py` that runs a local 400 server and a fake key through
  `refresh_source` and `write_health`. Assert that the key is absent from the messages and from the written
  `health.json`, then repeat the test with a refused connection.

Status: Fixed in 7b05d86. Its two leak tests (a local 400 server and a refused port, through refresh_source and write_health) fail on a6bae15 and pass now; every health message is redacted; the commit step runs `carddash scan-secrets data docs checks/restatement_ack.yaml` before `git add` and fails closed.

### R1-2 HIGH: the APR-over-prime spread subtracts the prime rate from the month after the APR was measured

- **Evidence.** FRED dates `TERMCBCCINTNS` to the middle month of each quarter. The raw JSON reads
  `2026-05-01 22.15`, `2026-08-01 22.36`, and `.` in every other month. `fred.to_facts` moves that observation to
  quarter end (2026-09-30). `sql/views.sql:243-258` (`v_apr_spread`) then joins `MPRIME` on the same date, which
  is September's prime (6.87). August's prime was 6.75. The view's comment says "they meet at quarter ends",
  but the two readings are a month apart.
- **Independent recomputation** from `data/raw/fred/latest/*.json`:

  | Quarter | Spread as built | Spread with the APR-month prime |
  | --- | --- | --- |
  | 2026 Q3 (current) | **15.49** | **15.61** |
  | 2020 Q1 | 12.83 | 11.86 (a 0.97 pp false spike) |
  | 2022 Q2 | 12.27 | 12.71 |

  Fourteen quarters are off by 0.2 pp or more. On the page, the drop from 15.61 to 15.49 shows up as issuers
  narrowing their margin. In fact it comes from a September prime increase that happened after the August
  sample. The thesis test (`render.py:1624-1627`) prints this number in `docs/latest.txt`. The 14-point verdict
  and the 2015-2019 baseline (10.70 as built, 10.75 corrected) do not change today.
- **Fix.** Join the prime for the APR's own month, for example
  `JOIN prime p ON p.period_end = last_day(a.period_end - INTERVAL 1 MONTH)`, or store the observation month.
  Say so in `PRIME_NOTE`.
- **Verify.** Add a view test pinning the spread at 15.61 for 2026 Q3 and about 11.86 for 2020 Q1. Re-render and
  read the `apr_over_prime` chart and the thesis line.

Status: Fixed in 2e682fd. v_apr_spread joins the prime rate of the survey month; the view tests (11.86 for 2020 Q1, 15.61 for 2026 Q3, 2015-19 average 10.75) fail on the old join; the fred fetcher refuses a survey reading outside February, May, August or November.

### R1-3 MEDIUM: 33 scheduled runs failed in a row and nothing told anyone

- **Evidence.** `gh run list --workflow refresh.yml --event schedule` shows every scheduled run from 2026-10-08
  through 2026-11-09 concluded `failure` (33 runs). `de676d3` confirms the cause ("failed every night since
  2026-10-08"). bea and census were also amber (`golden_mismatch`) from early October, and amber "shows as
  success". `refresh.yml` has no failure notification of any kind. The page itself was honest ("4 of 14 sources
  need attention"), but nobody reads the page to look for pipeline health.
- **Fix.** Add a final step with `if: failure()` that opens or comments on a pinned GitHub issue
  (`gh issue create/comment` with `GITHUB_TOKEN` and `permissions: issues: write`). Add a second step with
  `if: always()` that comments when any source has been non-`ok` for more than 7 days. GitHub's mobile app
  surfaces issues, and the user follows the project from a phone.
- **Verify.** Run `workflow_dispatch` with a deliberately failing input, for example a `FAIL_ON_PURPOSE` env
  switch read by a test, and see the issue appear.

Status: Fixed in 9ee8310. A failed run opens one `refresh-failure` issue that @mentions the owner and a good run closes it; a `source-attention` issue stays open while a source is amber for a week (`carddash attention`, health.json `status_since`). Seen live: dispatch run 42716371879 (fail_on_purpose) opened issue #1, and push run 42717110744 closed it with a 'Recovered' comment.

### R1-4 MEDIUM: two live BEA goldens sit inside BEA's routine revision window and will turn bea amber at the next release

- **Evidence.** `checks/golden.yaml:628-653` sets `bea_pce_change_2026_08` (193.6) and `bea_pce_change_2026_07`
  (50.6) to `check_live: true`. `golden.py:4-5` says live entries "should be periods old enough not to be
  revised routinely". `data/revisions.csv` shows what one BEA release does: the 2026-10-30 run (the September
  release) revised `pce_total_saar` for both 2026-07-31 and 2026-08-31. The October release ("expected around
  2026-11-27" on the page) will revise August again, and the tolerance is ±0.06 bn. bea then goes amber.
  `verify_releases.py` counts only all-`ok` runs as green, so the two-green-runs measure breaks too.
- **Fix.** Set `check_live: false` on both entries now. Make a BEA month live only once it is at least four
  months older than the newest month in the file. Encode that rule in `tests/test_golden.py`: for each
  `change_from_prior` live entry, assert it is at least 3 months older than the newest period in its source's
  fixture.
- **Verify.** `pytest` passes, and bea stays `ok` after the October PIO lands.

Status: Fixed in 03daf33. Both entries are fixture-only; bea keeps a live check on April 2026's DPI change (+12.7, pi0926-hist.xlsx); golden.MIN_LIVE_AGE_MONTHS (bea 4) is enforced by a test that fails on the old golden.yaml for exactly these two entries.

### R1-5 MEDIUM: the page marks revised fixture-only goldens with a red ✗, and the number format hides the difference

- **Evidence.** `render.py:1891` runs `check_golden(..., live_only=False)`, and `index.html.j2:268` prints
  ✓ or ✗ using `'%.4g'`. The live page currently shows
  `✗ Revolving credit, SA, May 2026: 1348 per the release (got 1348)` on "Revolving consumer credit, all
  holders". The same entry appears as `✗ Revolving (mostly cards), May 2026: 1348 per the release (got 1348)` on
  "Revolving and nonrevolving consumer credit". That entry,
  `g19_revolving_sa_2026_05`, is fixture-only because the G.19 revised May from 1347.7 to 1347.84.
- **Contradiction with the page's own method note.** The note (`index.html.j2:390`) promises the list is "the
  numbers the pipeline reproduces from the source's own release page on every run". Fixture-only entries are
  not checked on every run.
- **Formatting.** `'%.4g'` also turns any value of 10,000 or more into scientific notation (13999.12 prints as
  `1.4e+04`). It is used in the What-changed list as well (`index.html.j2:346`), which DFA revisions in the tens
  of thousands of billions will reach.
- **Fix.** Draw fixture-only entries neutrally ("as first published 1347.7, since revised to 1347.84"), or leave
  them off the page. Format numbers with the entry's own precision, derived from its tolerance, and never with
  `%g`.
- **Verify.** A render test asserts that no ✗ appears for a `check_live: false` entry and that 1347.7 and
  1347.84 are both printed.

Status: Fixed in 7290f78. A revised fixture-only entry is drawn without a mark as '1,347.7 as first published ..., since revised to 1,347.84'; numbers print to the decimals they were copied with and never with %g; the render test checks both, and that a live mismatch still shows ✗.

### R1-6 MEDIUM: `carddash check` exits 1 on a healthy pipeline

- **Evidence.** `cli.py:103` passes `live_only=False`. `python -m uv run carddash check` gives
  `62 passed, 7 failed`, exit 1. All seven are `check_live: false` entries that later revisions superseded:
  `g19_revolving_sa_2026_05`, the three phillyfed 2026 Q1 entries, `dfa_consumer_credit_2024`,
  `dfa_consumer_credit_2025` and `dfa_deposits_2025`. CLAUDE.md lists this as a main command. As it stands, it
  teaches whoever runs it to ignore FAIL lines.
- **Fix.** By default, check live entries only. Add `--all`, which prints superseded fixture-only entries as
  `REVISED` without counting them as failures.
- **Verify.** `carddash check` exits 0 with 46 live passes. `carddash check --all` lists the seven as `REVISED`.

Status: Fixed in aabfb42. `carddash check` checks the live entries (45 pass, exit 0); `--all` lists the seven revised fixture-only entries as REVISED, not failures (63 pass, exit 0); a live mismatch exits 1.

### R1-7 MEDIUM: HANDOFF.md is two months stale and tells the next agent to run `gh auth switch`

- **Evidence.** `HANDOFF.md:3` reads "Rewritten 2026-09-14", `:8-9` "v1 is done ... 383 tests green", and `:17`
  "Nothing is in flight". The 2026-11-09 fix session (`de676d3`) did not rewrite it, which breaks the project
  rule, even though the refresh had failed 33 scheduled nights in a row. The handoff therefore says nothing
  about the outage or the goldens rebased on BEA and Census annual revisions, and nothing about the two
  transitions due this month (Comenity Bank's final call report and the BEA re-revision).
- **Wrong push instruction.** `HANDOFF.md:43` says "Pushing needs `gh auth switch --user User5017`;
  SamuelJWebber cannot edit this repo's workflows". That is backwards: CLAUDE.md:135-138 and the machine rules
  say SamuelJWebber holds the `workflow` scope and User5017 lacks it. `gh auth switch` also flips the active
  account for every session on the machine.
- **Lower-trust claims.** The fix commit's "manual refresh green" is proven by a push run and a dispatch run.
  No scheduled run has been green since 2026-10-07.
- **Fix.** Rewrite HANDOFF.md:
  - Current state: the outage is fixed, and the first scheduled green run is pending.
  - Risks: R1-1, R1-4, and the FDIC 2026 Q3 load around 2026-11-19, the first night the Comenity "report through
    Q3" branch runs for real.
  - The correct push form: `GH_TOKEN=$(gh auth token --user SamuelJWebber)`, never `gh auth switch`.
- **Verify.** Read it, and run `git log -1 -- HANDOFF.md`.

Status: Fixed in the HANDOFF.md rewrite that closes this round (`git log -1 -- HANDOFF.md`). HANDOFF.md is rewritten for 2026-11-09 (the outage, the fixes, the pending scheduled run, the Comenity and BEA dates) and gives the push form `GH_TOKEN=$(gh auth token --user SamuelJWebber)`, never `gh auth switch`.

### R1-8 MEDIUM: third-party series are credited to the "Federal Reserve Board" on charts and PNGs

- **Evidence.** `render.py:62-63` maps every FRED series to "Federal Reserve Board, via FRED", and that label
  is the chart caption (`render.py:2017`), which `png.py:108-109` prints on every PNG. On the live page:
  - "Consumer sentiment ... Source: Federal Reserve Board, via FRED" (University of Michigan, a copyrighted series)
  - "Advertised on new offers (Bankrate, weekly): Federal Reserve Board, via FRED"
  - Unemployment and CPI (BLS), jobless claims (DOL) and DPI (BEA), all with the same label.

  `git grep -i copyright`, run outside vendored code and raw files, finds no notice for UMich or Bankrate. The
  PNGs exist to be pasted into posts.
- **Fix.** Add a `publisher` column to `crosswalks/series.csv` and build captions as "Source: University of
  Michigan, via FRED". Carry the copyright lines that FRED's series pages give for `UMCSENT` and `BRMCC01`.
- **Verify.** Re-render. No chart drawn only from non-Fed series says "Federal Reserve Board", and the
  `sentiment.png` caption names Michigan.

Status: Fixed in 7a12bf9. series.csv names a publisher for every FRED series and the copyright lines for UMCSENT and BRMCC01; captions read 'University of Michigan, via FRED' and carry the line, which the PNG prints; a render test refuses 'Federal Reserve Board' on a chart drawn only from other publishers' series.

### R1-9 LOW: the issuer_8k raw cache changes every night with no new data

- **Evidence.** Every bot commit from 2026-10-31 on rewrites four kinds of file:
  - `data/raw/issuer_8k/months/2026-09.htm` and `syf/2026-09.htm`
  - `latest/*.htm`
  - `index/no_metrics.json`

  A byte diff of `months/2026-09.htm` between `1544dc5^` and `1544dc5` shows a single change. It is the
  `<script type="text/javascript" src="/xSSjOa/...">` that the SEC edge injects before `</body>`, with a new
  random path in every response. Separately, `no_metrics.json` holds 56 Amex entries but only 8 distinct ones
  (`0000004962-26-000405` appears 18 times). `issuer_8k.py:804` lets the newest `RECHECK_NEWEST` filings
  bypass the skip list, and `:814` appends them again each night. The file grows without bound, two known
  earnings 8-Ks are downloaded every night, and git history gets a daily raw-file commit.
- **Fix.** Strip that injected script tag before parsing and saving, or write the file only when its parsed
  values change. Keep `no_metrics` as a set, and do not re-download an accession already known to have no
  metrics.
- **Verify.** Two runs with no new filings leave `data/raw/issuer_8k` unchanged.

Status: Fixed in 07d66a3. The edge's injected <script> is stripped before parsing and saving, files are written only when their bytes change, and a known no-metrics accession is never fetched again; two tests with a fake SEC (a new script per response) fail on the old fetcher and pass now.

### R1-10 LOW: the health strip misreports a failed source

- **Evidence** from `git show cde7866:docs/index.html`, during the outage:
  - "FDIC ... · Failed ... · 0 series, 0 rows", while 28,942 FDIC rows were still being served.
  - "Philly Fed ... 2026 Q2 data was expected around 2026-10-13 and has not appeared". The 26Q2 files had been
    published on 2026-10-07; it was the parser that failed.

  `render.py:2303-2321` takes rows and series from the failed run's empty `SourceHealth`, and `next_expected`
  (`:2278-2300`) ignores status.
- **Fix.** For a source that failed, show the row and series counts from facts. Word the expectation as "a
  newer release could not be loaded" rather than "has not appeared".
- **Verify.** Add a render test with a `failed` source in `health.json`.

Status: Fixed in 9ee8310. A red source's health reports the rows it still serves, the strip says they are kept from the last good load, and an overdue release of a source that failed reads 'could not be read'.

### R1-11 LOW: golden provenance links point at pages that change every release

- **Evidence.** Ten entries in `checks/golden.yaml` (for example lines 67 and 80) use
  `https://www.federalreserve.gov/releases/g19/current/default.htm`, and the census entries use
  `marts_current.pdf`. `verify_g19.py` already prints `SKIP g19_revolving_sa_2026_05: none of ['May 2026'] on
  the current page`. After the Census release on about 2026-11-17, the July figures cited as the census live
  goldens will no longer be in the linked PDF.
- **Fix.** Link the dated archive copy of each release, for example
  `https://www.federalreserve.gov/releases/g19/20260908/`. Keep the "current" URL only for `verify_g19.py`.
- **Verify.** Opening each `origin_url` shows the cited number.

Status: Fixed in 9ce46fb. G.19 entries link the dated release they cite (`verify_g19.py --provenance`: 13 of 13 PASS live); the census entries link the Internet Archive's 2026-10-22 copy of the 2026-10-15 release, whose Table 1 reproduces all three (Census posts its own adv2609.pdf about 2026-11-16).

### R1-12 LOW: stale or contradictory docs

- **Evidence.**
  - `README.md:30` says "four panels". The page has 8 panels and 78 charts.
  - `README.md:37-41` lists 5 of the 14 sources, and the README never mentions `.env.example`. A fresh clone's
    `carddash refresh` therefore turns issuer_8k red (`_sec_headers` raises because `CARDDASH_CONTACT` is
    unset) while the command still exits 0.
  - `CLAUDE.md:117` says the page is "about 1.4 MB". `docs/index.html` is 3,691,629 bytes.
  - `CLAUDE.md:86` says "issuer_8k carries three issuers". Its body and the code carry four.
  - `fetchers/issuer_8k.py:8,26` say "THREE ISSUERS LOADED ... PARSED BUT NOT LOADED". In the code,
    `HELD_BACK = ()` (`:668`) and Amex is loaded.
  - `AGENTS.md:32` says scheduled runs "landed 23:54, 23:57 and 00:08". The last six started between 01:15 and
    02:11 UTC.
  - `AGENTS.md:35` says "77 PNGs". There are 78.
  - `AGENTS.md:45` says the transfer is "deferred, check with the user". CLAUDE.md:140 says it is wanted and
    blocked on one click.
- **Fix.** Update each of these.
- **Verify.** Read them.

Status: Fixed in cece271 (README, .env.example, CLAUDE.md, AGENTS.md, the issuer_8k docstring); AGENTS.md's transfer line was already corrected in 3c7603f.

### R1-13 LOW: public TASKS.md names the local path of the FRED account credentials file

- **Evidence.** `TASKS.md:668` gives the full Windows path, including the user name, of the file holding the
  FRED account credentials. The file itself is not in the repo: the secret scan below is clean. The machine
  rules, however, put credentials in OneDrive\Documents and never in a code folder.
  `design/handoff-2026-09-07.html:56` also carries a user-profile path.
- **Fix.** Replace both with "kept outside the repo". Moving the file itself is outside this repo and is a
  decision for the user.
- **Verify.** `git grep -n "fred-account\|AppData"` finds nothing.

Status: Fixed in 7519a31. Both lines now say 'kept outside the repo', and a test refuses any user-profile or AppData path in a tracked text file (it finds exactly these two lines on the old tree).

### R1-14 LOW: `make_session()` still sends the URL-form User-Agent (known open item, confirmed)

- **Evidence.** `http.py:35` builds `carddash/{v} (+https://github.com/...) <contact>`, which the SEC refuses.
  issuer_8k works around it with its own `_sec_headers()` (`issuer_8k.py:681-692`), and `verify_g19.py:135`
  hard-codes a third variant (`carddash/0.1 (+https://...)`).
- **Fix.** Make `make_session()` send `carddash/{__version__} {contact}`, delete `_sec_headers`, and move
  `verify_g19.py` to `make_session()`.
- **Verify.** A test asserts that no session User-Agent contains `(` or `://`. Then run one fetch per host
  family.

Status: Fixed in 2998aa5. `http.user_agent()` is the one form, 'carddash/<version> <contact>'; issuer_8k only requires the contact and verify_g19.py uses make_session(). Seen live: 15 host families answered 200 to the new User-Agent from this machine, and push run 42717110744 loaded all 14 sources with it.

### R1-15 LOW: the credit-union crosswalk note is a permanent false alarm (known open item)

- **Evidence.** Every run adds this note to tccp: "4 of 28 top-25 institution names ... not in issuers.csv:
  America First ..., Boeing Employees' ..., Navy Federal ..., Pentagon Federal ...". `issuers.csv` needs an
  FDIC certificate, so these four can never be added. `fetchers/ncua.py:18-19,56-58` already tracks all four
  (charters 5536, 227, 62604 and 24694) and says itself that issuers.csv "cannot match them".
- **Fix.** Let `issuers.crosswalk_report` match TCCP names against the NCUA tracked list as well, or add an
  `ncua_charter` column with `kind=credit_union` rows.
- **Verify.** `carddash issuers` prints no unmatched names.

Status: Fixed in 1eb85ce. The crosswalk report matches the TCCP names against the credit unions the ncua source tracks; `carddash issuers` now reports all 28 names matched (24 bank names, 4 credit union names).

### R1-16 LOW: workflow actions are pinned by tag under `contents: write`, and a queued run starts from a stale checkout

- **Evidence.**
  - `refresh.yml:26,28` use `actions/checkout@v5` and `astral-sh/setup-uv@v6`, both mutable tags, while
    `refresh.yml:15-16` grants `contents: write`.
  - On 2026-11-09, dispatch run 42682400793 queued behind push run 42682387939 and checked out `de676d3`. It
    then recomputed the same 2,446 phillyfed revisions, and its `rebase -X theirs` replaced the first run's
    revision block. In `bdf012a`, `revisions.csv` swapped 2,446 lines and `facts.csv` re-stamped rows from
    19:22:50 to 19:26:12. Nothing was lost this time, but the run recomputed from data a commit behind.
- **Fix.** Pin both actions to commit SHAs. Run `git pull --ff-only origin main` before the refresh step, so a
  queued run starts from the newest data.
- **Verify.** Review the workflow file. Two back-to-back dispatch runs should log each revision once.

Status: Fixed in 9124f1a. Both actions are pinned to the commits of v5.1.0 and v6.8.0, and the job pulls main (fast-forward only) right after the checkout; a workflow test checks both. Run 42715716387 ran green with it.

---

## Bigger improvements (ranked)

1. **Add a secret-safe error path to every fetcher, plus a fail-closed gate before the commit step.** All
   exception text should pass through one redactor in the loader (R1-1). The workflow should refuse to commit if
   `data/` or `docs/` matches a key or token pattern. This turns a one-fetcher fix into a guarantee for every
   future source.
   Status: Done in 7b05d86 (one redactor for every source's messages, and the fail-closed scan before `git add`).
2. **Make failure loud (R1-3).** Open or update one pinned issue when a scheduled run fails or any source has
   been amber for more than 7 days. Show a red banner at the top of the page when the newest scheduled run
   failed. Add a status badge to the README.
   Status: Done in 9ee8310 (the failure and attention issues) and 37fb078 (a banner naming any red source, a stale-page banner after 36 hours by the reader's clock, and the README badge).
3. **Turn the golden policy into tests.** Set a minimum age per source for live entries, from each source's
   observed revision window (BEA 3 months, G.19 2 months, Census 2 months, and so on). Use dated provenance URLs
   (R1-11). Add a `checks/rebase_goldens.py` helper that prints candidate new entries from the release page for
   a person to confirm. The three re-basings in `de676d3` were done by hand after a month of amber.
   Status: Done for G.19: MIN_LIVE_AGE_MONTHS and its test (03daf33), dated provenance links and `verify_g19.py --provenance` (9ce46fb), and `verify_g19.py --rebase` (087635e), which prints each re-based entry with the current value and its dated page for a person to confirm. BEA and Census re-basing is still by hand: their releases state numbers in prose and PDF tables that no helper here reads.
4. **Make derived spreads date-correct by construction.** Store each quarterly survey's observation month next
   to its quarter-end `period_end`, so a view can never pair readings taken a month apart (R1-2). The same issue
   would hit any future join of a mid-quarter survey to a monthly series.
   Status: Done for the one derived spread there is (2e682fd): the fred fetcher refuses a survey reading outside the middle month, so v_apr_spread's month pairing cannot drift.
5. **Be polite with bandwidth.** Use conditional GETs (`If-Modified-Since`/`ETag`) for the large files: the
   BEA flat file is 36.7 MB every night, plus the NCUA zips, the DFA zip and the Census workbook. Today every
   night re-downloads them in full even when nothing changed.
   Status: Done for the largest file in d166e30: BEA answers a conditional GET with 304, seen live, so its 36.9 MB is downloaded only when BEA changes it. The NCUA, DFA (0.9 MB) and Census files are left as they are.
6. **Slow the repo's growth.** `facts.csv` (9.7 MB) and `revisions.csv` (3.4 MB) are committed twice, under
   `data/` and `docs/data/`, and `docs/index.html` (3.7 MB, all data embedded) changes on every data day.
   `.git` is already about 104 MiB after two months. Publish one copy, gzip `revisions.csv`, and consider
   serving the series-browser JSON as a separate file (still static, no CDN).
   Status: Not done. Dropping docs/data/ would break the page's download links and anyone who links to them, and a separate JSON file would break the page from file://; both need a decision about the published URLs.
7. **Put credit unions into the issuer dimension (R1-15).** Then Navy Federal and PenFed can sit on the issuer
   charts beside the banks, which is what the TCCP top-25 list says they are.
   Status: Not done. The crosswalk false alarm is fixed (R1-15), but drawing credit unions on the FDIC issuer charts mixes NCUA and call-report definitions; that is a new chart design under the scope rule, suggested in HANDOFF.

---

## Checked and solid

- **Tests.** 386 pass. They use fixtures with a fixed `TODAY` and contain no wall-clock time bombs. Nothing in
  `tests/` touches the network.
- **Headlines re-derived independently from `data/raw/`**, with no carddash code. Every one matches `docs/latest.txt`:
  - Revolving credit: $1,368bn in Sep 2026, +4.2% (4.25%) on the year, a record since Jan 1968.
  - APR paid by revolvers: 22.36% in 2026 Q3, -0.47 pp on the year, 2015-19 average 14.93.
  - Card 30+ day delinquency: 2.85% in 2026 Q2, -0.19 pp, average 2.39, lowest since 2023 Q2.
  - Card charge-off rate: 3.82%, -0.37 pp, average 3.40.
  - NY Fed card balances: $1,263bn in 2026 Q2, +4.5%.
  - NY Fed 90+ day flow: 6.97%, +0.04 pp, average 4.36.
  - Philly Fed share paying only the minimum: 10.15%, -0.57 pp, average 9.58.
  - CFPB new cards: 8.27 million in Mar 2026, +11.4%.
  - Initial claims: 189 thousand, -17.1% (against 228 thousand on 2025-11-01).
  - Unemployment: 4.10%, average 4.42. October 2025 is genuinely absent from the raw file.
  - DFA consumer credit, bottom 50%: $2,644bn in 2026 Q2, +2.6%, a record since 1989 Q3.
- **Goldens against live release pages**, fetched with the pipeline's own non-browser User-Agent:
  - The BEA September 2026 PIO page states PCE +113.1, goods +35.1, services +78.1 and DPI +52.7.
  - The Philly Fed Q2 2026 report states 16.1% to 18.5%, a 37% full-payment share, +3.4% balances and $6,216 to
    $6,066.
  - The Philly Fed Q1 2026 report states 948.7, 24.0% and 105.5.
  - `verify_g19.py` passes 12 of 12 checkable G.19 entries.

  The Census goldens were **not** checked against the PDF in this review.
- **The 26Q2 Philly Fed parse.** Every score-bucket column of the spaced headers maps to the right tier: the
  2026Q2 facts equal the raw CSV cells (576.98, 1,234.28, 2,549.07, 600, 2,700, 7,000, 18.52, 4.19). The
  fixtures are byte-identical to `data/raw/`.
- **The Comenity merger rule.** There is precedent in the repo's own data: Capital One Bank (USA), merged
  2022-10-03, filed its 2022-09-30 call report. So "report through Q3" is the right expectation for Comenity
  Bank. The pending branch is tested.
- **Secrets.** `.env` was never tracked or committed. The FRED key and the contact address appear nowhere in the
  tree or in any commit (`git grep -F` and `git log --all -S`, run without printing the values).
- **Live fallbacks.** The keyless FRED path (`fredgraph.csv`) works live (`REVOLSL` to 2026-09, 1,368.45).
- **HHDC.** The 2026Q3 workbook is not published yet: the NY Fed returns its HTML not-found page with HTTP 200,
  which `looks_like_xlsx` handles. Tonight's run will read 2026Q2 as expected.
- **Unsafe input handling.** There is no unsafe deserialization (`yaml.safe_load` throughout), no shell or
  `eval`, and no zip extraction to disk. Jinja autoescapes, and the embedded JSON escapes `</`. Every relative
  link on the page resolves.
- **SEC requests** send a contact address and no URL in the User-Agent, and fail loudly without it.

Not exercised, because the data is not published yet: the HHDC 2026 Q3 parse, the FDIC 2026 Q3 load with
Comenity's final report (around 2026-11-19), and the Census September workbook (around 2026-11-17).
