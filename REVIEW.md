# Independent Fable review, 2026-11-10 (not a pipeline round)

An outside check of what was pushed on 2026-11-09, by a different model from the one that built and
reviewed it: first-line reviewers attacked the work and compared it with other people's, then a
second reviewer tried to refute each HIGH and MEDIUM finding. Only the verified result is below.
Full reports, with commands and sources: `reviews/fable-2026-11-10/` (`credit-V.md` is the verification;
the others are the first-line reports, including claims the verifier narrowed or rejected).
**Nothing here has been implemented.** Mark each row Fixed / Rejected / Deferred as it is handled.

## Verdict table

| Finding | Their severity | Verdict | My severity | Corrected one-line statement |
| --- | --- | --- | --- | --- |
| credit-A-1 contact address in commit history | HIGH | UPHELD as fact, WEAKENED on grade | MEDIUM | The guarded contact is the author and committer address on 73 public commits; it is an ordinary commit e-mail, not a credential, and the same address is public in two other repos. |
| credit-A-2 offered APR fall is new respondents | MEDIUM | UPHELD | MEDIUM | Same institutions: 28.24 to 27.74 (620 to 719) against the drawn 28.24 to 26.74; the first thesis note also builds an argument on the drawn fall. |
| credit-A-3 HTML escaping off | MEDIUM | UPHELD | MEDIUM | Autoescape is off; a source answering HTTP 200 with a body that starts with a 38-byte script tag would run script on the public page. |
| credit-A-4 charge-off peaks and unemployment | MEDIUM | UPHELD | MEDIUM | Of six charge-off peaks, none followed an unemployment peak: three had none nearby, two came first, one (2009) coincided. |
| credit-A-5 "same survey of the same banks" | MEDIUM | UPHELD | MEDIUM | Two Fed forms, two panels, two definitions (FR 2835 and FR 2835a); the sentence is also in the second thesis note. |
| credit-A-6 SA never compared with NSA | MEDIUM | UPHELD | MEDIUM | The promise is false for at least the three charts I read; the Fed's two tables differ by up to 0.32 points. |
| credit-B-1 "interest households actually pay" | HIGH | UPHELD | HIGH | BEA builds the series as Fed consumer credit times a blended Fed rate, for all consumer credit, at every frequency; the chart returns that rate. |
| credit-B-2 stock delinquency read as distress | HIGH | WEAKENED | MEDIUM | The NY Fed post says it, about cards, nationally; it says nothing on states. "National" survives; the 2024 to 2025 leg, most of the "range widened" and two thesis-note sentences do not. |
| credit-B-3 "highest on record" without "nominal" | MEDIUM | UPHELD | MEDIUM | True in dollars, 14.7% below the 2008 peak in today's dollars; the project's own thesis note calls this headline misleading. Same as credit-A-8, which was under-graded. |
| credit-B-4 $1,263bn includes about $163bn 90+ | MEDIUM | WEAKENED | LOW | Arithmetic right (+4.47% with the pool, +3.69% without); the label "on credit reports" is correct and it is the NY Fed's own headline. |
| credit-B-5 "cards the only improving debt" | MEDIUM | UPHELD | MEDIUM | The thesis note's own table has "Other" improving twice as much; on flows cards are not even the worst (student loans 7.83). Thesis note only, not the main page. |
| credit-B-6 thesis tests cannot fail | MEDIUM | WEAKENED | MEDIUM | True of test 1 only; test 2 (4.2%) sits below five quarters of the surge. The NY Fed (2026-11-10) does put macro conditions first, against the note's "not a macroeconomic one". |
| credit-B-7 the repricing is misdated | MEDIUM | UPHELD | MEDIUM | 2.44 of the 4.86 points of extra margin were in place by 2021 Q4; CFPB dates the widening from 2016. |
| credit-B-8 only balance-weighted measures | MEDIUM | WEAKENED | LOW | TransUnion's borrower rate did rise; the page's own account-weighted Y-14 rate fell (0.74 to 0.70), so the proposed fix would not show the pattern. |
| credit-B-9 five "About" notes describe another quantity | MEDIUM | UPHELD | MEDIUM | Four of the five read in the live JSON; each derived line carries its first input's note. |
| credit-A-12 (LOW, PLAUSIBLE) wider numerator | LOW | UPHELD, now CONFIRMED | folds into credit-B-1 | BEA's line also holds margin interest, policy-loan interest and interest paid to government. |

Counts: 11 UPHELD (one re-graded down), 4 WEAKENED, 0 REFUTED, 0 UNVERIFIABLE, plus one LOW upgraded from PLAUSIBLE.
After re-grading: 1 HIGH, 12 MEDIUM, 2 LOW among the 15 HIGH and MEDIUM findings.

## Fix first

1. Retitle the "Interest households actually pay" chart as BEA's modelled nonmortgage interest over consumer credit,
   and delete the two sentences about interest-free balances and "fewer dollars".
2. Put the NY Fed's charged-off caveat on the state map, both state charts and the stock loan-type chart, and
   correct the three sentences that compare stock levels across years or loan types ("range widened", "worse than
   the median state was in 2019", "thirteen times").
3. Set `autoescape=True` at `render.py:2531` and add a render test with a script tag in a health message.

Next in line: draw the top-25 or matched-panel offered APR; say "in dollars" on the record flag; rewrite the
charge-off and unemployment sentence; decide the commit e-mail question once for all three public repos.

---

# Review round 2 (2026-11-09)

Adversarial review of carddash at `188ad9f` (origin/main, the 00:16 UTC bot refresh after the end of review round 1),
run on 2026-11-10 between 00:17 and about 01:00 UTC, which is still the evening of 2026-11-09 in New York. This file
reports; it changes no code. Round 1 is in this file's git history (`git log -p -- REVIEW.md`, commits `a6bae15` to
`5fc16ce`).

**Round 1, re-checked:** all 16 findings marked Fixed were re-run with their own checks (table under "Checked and
solid"). None regressed. R1-11's verify step, run over every golden entry rather than only the ones R1-11 changed,
finds a broken link that predates round 1 (R2-3).

**Counts: 0 HIGH, 4 MEDIUM, 2 LOW.** No wrong number was found on the page: every headline was re-derived from
`data/raw/` without carddash code and matches.

Context that differs from the brief this round was given: the repository is `SamuelJWebber/credit-card-data` since
2026-11-09 (`git remote -v`; `gh repo view User5017/credit-card-data` resolves to it; CLAUDE.md "GitHub account").
`make_session()` no longer sends the URL-form User-Agent (fixed in `2998aa5`, R1-14). The four credit unions are no
longer reported as missing (R1-15), but the issuer dimension is still bank-only (bigger improvement 6).

What was run, on Windows, against a fetched clone:

- `python -m uv run pytest`: **440 passed**, exit 0, 3 min 59 s.
- `carddash check`: 45 passed, 0 failed, exit 0. `check --all`: 63 passed, 7 REVISED, exit 0.
- `carddash health --fail-on-red`: 14 `ok`, exit 0. `carddash issuers`: 28 of 28 TCCP names matched, exit 0.
  `carddash attention`: empty, exit 0. `carddash scan-secrets data docs checks/restatement_ack.yaml` with both secrets
  loaded: 0 findings, exit 0.
- `checks/verify_g19.py --provenance`: 13 PASS, exit 0. Default mode: 12 PASS, 1 SKIP, exit 0.
- `checks/verify_releases.py --limit 6` (after `git fetch`): NOT YET, 0 of 2, exit 1, as expected after the outage.
  `--event push --limit 6`: PASS, but with a wrong match (R2-1).
- The `audit` skill's four personas, run inline (this session has no tool to start subagents): Silent Wrong Answer
  produced R2-1 and R2-4. Stranger, Leak Hunter and Bad Actor found nothing real; see "Checked and solid".

---

## Findings

### R2-1 MEDIUM: `verify_releases.py` can grade a run by another run's bot commit

**In plain words.** The script that grades the v1 definition of done ("two consecutive green scheduled runs") looks
for a bot commit stamped inside each run's time window. The window runs 5 minutes past the run's end, and it takes the
newest commit that fits. When a second run's commit lands in that window, the first run is graded by the second run's
health.json. This is already happening to push runs.

- **Evidence.** `checks/verify_releases.py:62` sets the window to `[created_at, updated_at + 5 min]`. `:63-68` walks
  the bot commits newest first (`git log`, `:42`) and returns the first stamp inside the window.
- **Reproduced.** `git fetch; GH_TOKEN=$(gh auth token --user SamuelJWebber) python -m uv run python
  checks/verify_releases.py --event push --limit 6` prints two different runs against the same commit:

      42724802764  2026-11-09 23:59 UTC  push      success   be474c9 GREEN  bea=ok, ...
      42724326075  2026-11-09 23:55 UTC  push      success   be474c9 GREEN  bea=ok, ...

  `gh api repos/SamuelJWebber/credit-card-data/actions/runs/42724326075` shows that run was created at 23:55:35 and
  updated at 23:58:19, so its window runs to 00:03:19. Its own commit is `ffbc225` (health.json `generated_at`
  23:57:30). The next run's commit `be474c9` (00:02:12) also falls inside the window, and it is found first.
- **Failure scenario for the measure.** Scheduled runs start between 00:55 and 03:25 UTC, which is when sessions on this
  project push (round 1 pushed code at 00:11 UTC tonight). Take a scheduled run that ends with census amber, and a push
  run queued behind it whose all-`ok` commit lands within 5 minutes. The scheduled run is graded GREEN. The reverse also
  happens: a green night is graded "not green" because a later push run had a red source. The result feeds HANDOFF
  "Next" step 1 tonight. There is no test file for this script.
- **Fix.** Match each run to its own commit. The workflow should write the run into the bot commit, for example
  `git commit -m "refresh: $(date -u +%Y-%m-%dT%H:%MZ) run ${{ github.run_id }}"`, and also into health.json. Then
  `match()` should use that and fall back to the window only for older commits. The fallback window should run from
  `run_started_at` to `updated_at`, with no slack, and take the earliest stamp inside it, not the newest. Add
  `tests/test_verify_releases.py` with two overlapping runs, built from these two real runs.
- **Verify.** The push listing above shows `ffbc225` against 42724326075 and `be474c9` against 42724802764. The new test
  fails on the current `match()`.

### R2-2 MEDIUM: the page omits two notices that its data licences require (FRED API, NY Fed SCE)

**In plain words.** Two publishers set conditions on reusing their data. Both conditions are explicit and both are
unmet. Both licences say the right to use the data ends automatically on non-compliance. R1-8 fixed the copyright
credit for the Michigan and Bankrate series that come through FRED. It did not cover these two.

- **FRED API.** The nightly uses the API: `fetchers/fred.py` `_api_get`, with `FRED_API_KEY` set in `refresh.yml`. FRED's
  API Terms of Use (fred.stlouisfed.org/docs/api/terms_of_use.html, read 2026-11-10 with the pipeline's own User-Agent)
  list, under "Requirements: You must", a notice to be placed prominently on the application. The notice says the
  product uses the FRED API and is not endorsed or certified by the Federal Reserve Bank of St. Louis. The same page says
  the rights "terminate automatically" on violation. `grep -c "not endorsed" docs/index.html` returns 0. The README does
  not carry the notice either.
- **NY Fed Survey of Consumer Expectations.** The `License` sheet in `data/raw/nyfed_sce_monthly/latest/frbny-sce-data.xlsx`
  requires an attribution and disclaimer with any publication or presentation of SCE data. It is a source line with the
  FRBNY copyright, 2013-2026, and a sentence disclaiming FRBNY responsibility for the analysis. The `Disclaimer` sheet
  and the credit-access workbook carry the same clause. The licence "terminates automatically if a user fails to
  comply".
  - `grep -c "FRBNY\|©\|disclaim" docs/index.html` returns 0.
  - `crosswalks/series.csv` has 88 SCE series (`nyfed_sce`, `nyfed_sce_monthly`), none with a `rights` value.
  - The PNG captions, for example `docs/img/card_access.png` and `miss_payment_expectation.png`, say "Source: Federal
    Reserve Bank of New York, Survey of Consumer Expectations ...". That meets the licence's short form for a figure,
    but nothing on the page carries the full attribution and disclaimer.
- **Fix.**
  1. Print the FRED notice in the page's "Data and method" block (`templates/index.html.j2`, after the Sources
     paragraph) and in the README.
  2. Copy the SCE attribution and disclaimer verbatim from the License sheet into the same block.
  3. Set `rights` on the 88 SCE rows of series.csv to the licence's figure line ("Source: Survey of Consumer
     Expectations, New York Fed"), so each SCE chart's notes and PNG carry it.
  4. Add a render test: the page carries the FRED notice, and it carries the SCE disclaimer whenever an SCE source is in
     health.json.
- **Verify.** Run `grep -c "not endorsed or certified" docs/index.html` and `grep -c "FRBNY disclaims" docs/index.html`;
  each should return 1 or more after a render. Open `docs/img/card_access.png`.

### R2-3 MEDIUM: a live golden's provenance link is a 404, and two BEA entries link a page without their numbers

**In plain words.** The project's promise is that every checked number traces to its release. For the one Capital One
entry that pins the Discover-merger month, the link printed on the page goes nowhere. The number itself is right, but
the link names the wrong filing.

- **Evidence.** `checks/golden.yaml:894` (`cof_8k_nco_rate_2025_06_combined`, live) links
  `.../edgar/data/927628/000092762825000212/ex991june2025creditmetrics.htm`. Checked with
  `curl -s -o /dev/null -w "%{http_code}" -A "carddash/0.1.0 $CARDDASH_CONTACT" <url>`:

      404 https://www.sec.gov/Archives/edgar/data/927628/000092762825000212/ex991june2025creditmetrics.htm
      200 https://www.sec.gov/Archives/edgar/data/927628/000092762825000241/ex991june2025creditmetrics.htm

  The exhibit is in accession 0000927628-25-000241: `data/raw/issuer_8k/index/000092762825000241.json` lists it, and
  the EDGAR directory shows it filed 2025-07-22, the date the entry cites. That page states "Domestic Card ... 4.96". The
  wrong accession dates from `e88bc47` (2026-09-11). The page prints the link as "the release" under the Capital One
  charts.
- **Two more.** `golden.yaml:650` (`bea_pce_change_2026_08`, 193.6) and `:664` (`bea_pce_change_2026_07`, 50.6) say
  their numbers come from the "Historical Comparisons workbook (pi0926-hist.xlsx)", but they link the news page. The news
  page contains neither number. The workbook's sheet `PIOhist_M` does ("2026M08 | 193.6 | 2026M07 | 50.6"). Both
  entries are fixture-only.
- **How it was found: R1-11's verify step over all 57 non-G.19 entries.** The script fetched each `origin_url` with the
  pipeline's User-Agent and searched the HTML, PDF text (pdftotext) or XLSX cells for the expected value.
  - 52 entries: the number is in the linked document.
  - 2 entries: derived by design. `hhdc_debt_current_2026_q2` is 95.3 = 100 - 4.7. `dfa_deposits_2025` is the sum of
    two Z.1 lines.
  - 2 entries: link the wrong page (the two BEA entries above).
  - 1 entry: 404 (the Capital One link above).
  - The 13 G.19 entries all pass `verify_g19.py --provenance`.
  - The 82 unique external URLs on the page, in series.csv and in golden.yaml: 81 answer 200.
- **Fix.**
  1. Change the accession in `golden.yaml:894` to `000092762825000241`.
  2. Point `:650` and `:664` at `https://www.bea.gov/sites/default/files/2026-10/pi0926-hist.xlsx`.
  3. Add an offline test to `tests/test_golden.py`: for every `sec.gov/Archives` origin_url, the accession's cached index
     under `data/raw/issuer_8k/index/` lists the document name. It needs no network and fails on today's file.
- **Verify.** The new test passes. A HEAD of each corrected URL answers 200.

### R2-4 MEDIUM: `verify_g19.py` says "all checked entries match" when the Fed's page did not load

**In plain words.** HANDOFF tells the next session to run this after the December G.19 release. If the Fed's server
answers with an error page that day, the script checks nothing, prints that everything matches and exits 0. That is
the opposite of the truth.

- **Evidence.** `checks/verify_g19.py:177` reads `session.get(url).text` with no status check. With no tables, every
  entry falls through `:201-207` to a SKIP in the default and `--rebase` modes. `:216` then prints "all checked entries
  match" because nothing failed, and `:221` returns 0. There is no count of what was actually checked.
- **Reproduced without network.** `make_session` was replaced by a stub that answers 403 with an "Access Denied" page,
  and `main()` was called in each mode:

      == mode ['default']      -> 13 SKIP lines, "all checked entries match the current release page", exit code 0
      == mode ['--rebase']     -> 13 SKIP lines, "all checked entries match the current release page", exit code 0
      == mode ['--provenance'] -> "13 mismatch(es)", exit code 1

- **Fix.** `resp.raise_for_status()` in `tables_for`, and require `release_date(page)` to parse. Count PASS plus FAIL
  and exit 1 with "0 entries checked" when the count is 0, or when SKIPs outnumber checks on the current page. Add the
  stub above as a test in `tests/test_verify_g19.py`.
- **Verify.** The new test exits 1 in all three modes. The live run still prints 12 PASS and 1 SKIP.

### R2-5 LOW: docs and comments that now say something the code does not do

- **Evidence.**
  - `CLAUDE.md:59-64` (fetcher contract) still calls issuer_8k the "ONE EXCEPTION" whose SEC User-Agent differs from
    "ours". Since `2998aa5` every request sends `carddash/<version> <contact>` (`http.py:22-32`), which is what
    AGENTS.md says. The two files given to both assistants now contradict each other. R1-14's fix did not touch
    CLAUDE.md.
  - `fetchers/tccp.py:8-9` says the CFPB edge accepts "'carddash/<version> (+repo url)'". That agent is no longer sent.
  - `fetchers/issuer_8k.py:111-116`, `:515` and `:534` say the retired Amex series "ends in March 2026" and that the two
    bases "overlap" for February and March. In `data/facts.csv`, `ISSUER:AMEX_US_CONSUMER_LOANS` ends at 2026-01-31.
    The planner fills February and March from the newer filing and never downloads the old-basis March filing. The
    page note (`render.py` AMEX_NOTE: "the older one ends at January 2026") is right, and the module comments are
    wrong.
  - `templates/index.html.j2:372`, on the page: "Each source is fetched in full every run." bea is not, since `d166e30`
    (an HTTP 304 parses the saved subset). ncua and issuer_8k are not either; both are documented exceptions in
    CLAUDE.md.
  - CLAUDE.md "Old links still work": the old site's root redirects, but deep links such as
    `https://user5017.github.io/credit-card-data/latest.txt` and `.../img/sentiment.png` answer **HTTP 404** with a
    script redirect. Browsers follow it. curl, scripts that downloaded `data/facts.csv`, and link-preview crawlers get
    a 404.
  - HANDOFF "Next 3" says "Four hhdc live goldens are Q2 2026". Three are Q2 2026, and the fourth is Q2 2025.
- **Fix.**
  - Rewrite the CLAUDE.md paragraph as "every fetcher sends `http.user_agent()`; issuer_8k only insists the contact is
    set".
  - Drop the URL form from `tccp.py`.
  - Change the three Amex comments to "ends at January 2026: the newer filing covers February and March, so the
    old-basis March filing is never downloaded".
  - Change the page sentence to "Each source is fetched every run (BEA only when its file changed; NCUA and the 8-K
    filings only for missing periods and the newest two)".
  - Say in CLAUDE.md that old deep links redirect in browsers only.
  - Fix the HANDOFF count when it is next rewritten.
- **Verify.** `git grep -n "ONE EXCEPTION\|(+repo url)\|ends in March 2026\|fetched in full every run"` finds nothing.

### R2-6 LOW: the failure banner and the "due" line name a source by the words before its first comma

- **Evidence.** `render.py:2519` builds `red_sources = [r["label"].split(",")[0] ...]`. The due line in
  `templates/index.html.j2:204` uses `r.label.split(',')[0]`.
  - issuer_8k's label begins "Capital One, Synchrony, Bread Financial and American Express, ...". If Amex's parser fails,
    the banner reads "1 source failed to load in the latest run (Capital One)".
  - The three NY Fed sources all shorten to "Federal Reserve Bank of New York".
  - On the live page today: "Due in the next two weeks: Federal Reserve Bank of New York 2026 Q3 around 2026-11-11; ...".
  - The render test covers only an FDIC failure.
- **Fix.** Add a `SOURCE_SHORT` map, for example "NY Fed Household Debt and Credit", "NY Fed SCE credit access" and
  "Issuer 8-K filings (Capital One, Synchrony, Bread, Amex)". Use it in both places and in the attention issue.
- **Verify.** Run a render test with `issuer_8k` and `nyfed_sce` failed and assert both names appear in full.

---

## Bigger improvements (ranked)

1. **Run identity in every bot commit.** Put `run_id`, event and `run_started_at` in the commit message and in
   health.json, and grade on them (R2-1).
   - With that, a small second workflow at about 12:00 UTC can run `verify_releases.py --limit 1` and open an issue when
     the night has no scheduled run at all.
   - Only one run can wait in the `refresh` concurrency group. GitHub's documented behaviour is that a newer queued run
     cancels the waiting one. A cancelled waiting run executes no step, so it opens no failure issue, and the v1 count
     just stops.
   - Not seen live yet: no scheduled run has been cancelled; the only cancelled runs are two push runs.
2. **One provenance checker for every golden, run weekly in Actions.** Generalise `verify_g19.py --provenance` to every
   `origin_url`: HTML, PDF through pypdf, XLSX cells. The script used for R2-3 did this in under 100 lines. Run it
   weekly, not nightly (it reads 22 documents from 9 hosts), and open an issue on a 404 or a missing number. Keep the
   offline SEC accession test from R2-3 in the suite.
3. **A notices registry instead of one-off lines.** List each publisher's required notices in one table: FRED API,
   NY Fed SCE, Michigan, Bankrate, NY Fed CCP/Equifax. The page footer, chart notes and PNG captions should be built
   from it. A test should require every source in health.json to resolve to its notices (R2-2), so the next source
   cannot arrive without them.
4. **Fail-closed manual checkers.** `checks/` should share a `fetch_or_die()` that raises on a non-200 response
   and on an empty parse. Each checker should end with "N checked" and exit 1 when N is 0 (R2-4). The same pattern is
   worth applying to `verify_releases.py` when `gh` returns no runs.
5. **Short, unambiguous source names wherever one line names a source**: the banner, the due line, and the attention
   and failure issues (R2-6).
6. **Carried over from round 1, still open, both decisions for the user.**
   - Improvement 6: publish one copy of `facts.csv` and `revisions.csv`. GitHub reports the repository at 46 MB; the
     local `.git` shows 95 MiB because its objects are not yet packed.
   - Improvement 7: put credit unions in the issuer dimension. The false alarm is gone (R1-15), but Navy Federal, PenFed,
     BECU and America First still appear only on the NCUA charts.

---

## Checked and solid

### Round 1 findings re-checked (0 regressed)

| Finding | Re-check run this round | Result |
| --- | --- | --- |
| R1-1 key leak | Local server answering 400 with the full request path echoed in FRED's `error_message` (worse than FRED), plus a refused port, through `loader.refresh_source` and `cli.write_health`. `scan-secrets` with both secrets loaded. | Holds. Message reads `...api_key=[redacted]...`; the key is in neither health.json. 0 scan findings. |
| R1-2 APR spread | Recomputed from `TERMCBCCINTNS` and `MPRIME` raw JSON | Holds. 2026 Q3 15.61 (old join 15.49); 2020 Q1 11.86; 2015-19 average 10.7475. The page prints 15.61. |
| R1-3 failure loud | `gh issue view 1` | Holds, seen live. Opened by dispatch 42716371879, closed by push 42717110744 with "Recovered". The attention issue is still fixture-proven only. |
| R1-4 BEA goldens | golden.yaml plus the BEA workbook | Holds. July and August are fixture-only. The live April DPI +12.7 is in `pi0926-hist.xlsx` (read this round). |
| R1-5 revised marks | `grep` of the page | Holds. 2 `check-revised` items reading "1,347.7 as first published ..., since revised to 1,347.84". The one ✗ on the page is in the method note. No `%g` in the template. |
| R1-6 `check` | `carddash check`, `check --all` | Holds. 45 pass, exit 0; 63 pass and 7 REVISED, exit 0. |
| R1-7 HANDOFF | Read it | Holds. Rewritten 2026-11-10 00:15 UTC with the correct push form. One small miscount (R2-5). |
| R1-8 publisher credit | `docs/img/sentiment.png`, page text | Holds. "University of Michigan, via FRED" with Michigan's line; "Copyright Bankrate, LLC." on the APR chart. FRED tags both series "Copyrighted: Citation Required", which the credit satisfies. SCE notices are a separate gap (R2-2). |
| R1-9 8-K churn | `git show --stat be474c9 188ad9f`; `no_metrics.json` | Holds, seen live. Neither bot commit touches `data/raw/issuer_8k`. 8 entries, 8 distinct. |
| R1-10 red health strip | Render tests | Holds, fixture-proven only: no source has been red since the fix. |
| R1-11 dated provenance | `verify_g19.py --provenance` (13 PASS); census archive PDF | Holds for every link it changed. Its verify step over all entries finds R2-3, which predates round 1. |
| R1-12 docs | Read README, AGENTS.md, CLAUDE.md | Holds for the listed items. A new stale paragraph came from R1-14's change (R2-5). |
| R1-13 profile paths | `git grep` for user-profile and AppData paths | Holds. No such path. The only matches are the test's own regex, REVIEW.md, and the word "OneDrive" in prose. |
| R1-14 User-Agent | `git grep` for User-Agent strings; tests | Holds. `http.user_agent()` is the only one sent. Docstring remnants in R2-5. |
| R1-15 credit-union names | `carddash issuers` | Holds. 28 of 28 matched (24 bank, 4 credit union). |
| R1-16 pinned actions | `gh api repos/<action>/git/ref/tags/<tag>` | Holds. v5.1.0 is `fbc6f39...` and v6.8.0 is `d0cc045...`, matching the workflow. The pull step is present. |

### Headlines re-derived from `data/raw/` with plain json, csv, zipfile and openpyxl (no carddash import)

All 16 lines of `docs/latest.txt` and the 3 thesis tests match:

- Revolving $1,368.45bn in Sep 2026, +4.25% on the year, a record since Jan 1968.
- NY Fed card balances 1.263 trillion in 2026 Q2 against 1.209, +4.47% (`HHD_C_Report.xlsx`, Page 3 Data).
- APR 22.36%, -0.47 pp on the year, 2015-19 average 14.93; margin 15.61.
- Card 30+ delinquency 2.85%, -0.19, average 2.39, lowest since 2023 Q2 (2.75).
- Charge-offs 3.82%, -0.37, average 3.40.
- NY Fed card flow into 90+ 6.97%, +0.04, average 4.36 over 20 quarters (Page 14 Data).
- SLOOS 4.0 (October survey, dated 2026 Q3) against 4.2 a year earlier.
- Debt service 5.28%, -0.02, average 5.71.
- Claims 189,000 against 228,000 (2025-11-01), -17.1%.
- Unemployment 4.1%, October 2025 absent, average 4.42.
- Philly Fed minimum-only share 10.15%, -0.57, average 9.58.
- SCE card refusals 15.39%, -6.82, average 17.44.
- Lender closed an account 7.03%, -0.99, average 5.29.
- Chance of missing a payment 13.78%, +0.67, average 12.31.
- CFPB new cards 8.27 million, +11.4%.
- DFA bottom-half consumer credit $2,644bn, +2.63%, a record since 1989 Q3.
- FDIC 2026 Q2 card loans from raw `LNCRCD`: Capital One 250.519, JPMorgan 216.172, Citi 176.013, as charted.
- Capital One's September 2026 exhibit: NCO 3.66, 30+ 3.74, average $257,744mn, period-end $260,252mn, equal to facts.

### Goldens and links

- 52 of 57 non-G.19 goldens are stated in the document they link, and 13 of 13 G.19 entries pass on their dated pages.
  The other five are explained in R2-3.
- 81 of 82 external URLs answer 200 to the pipeline's User-Agent.

### Secrets and unsafe input

- **Secrets.** Neither `.env` value appears in a tracked file, in any commit on any ref (`git log --all -S`), or in a
  commit message. The values were never printed. `.env` is ignored.
- **Stranger, Leak Hunter and Bad Actor.**
  - No absolute paths.
  - `uv.lock` and `.python-version` pin the environment, and the tests touch no network and read no wall clock.
  - `yaml.safe_load` throughout; no `eval`, `exec`, `shell=True`, `pickle` or `extractall`.
  - SQL is built from code constants with parameterised paths.
  - The page puts only repo-authored strings into `innerHTML`, and the URL hash is used only as a lookup key.

### The page in a browser

The live site was opened in the built-in browser:

- 78 charts drew; the console was clean.
- The red banner was absent; the stale banner was hidden (stamp 2026-11-10T00:15:08Z).
- The stale banner's own script was run against altered stamps: hidden at 12 hours, "40 hours" at 40, "4 days" at 100.
  This is the first time it has been seen in a real browser; HANDOFF had it as run under node only.
- The old repository URL answers 301 and the old site's root redirects.

### Not exercised (the data is not out yet)

- HHDC 2026 Q3 (about 2026-11-11). Three live goldens sit on 2026 Q2.
- Census September workbook (about 2026-11-14 to 17).
- FDIC 2026 Q3 with Comenity Bank's final report (about 2026-11-19). `quarter_end_before(2026-10-01)` is 2026-09-30,
  as the pending branch expects.
- BEA October PIO (2026-11-25).
- The first scheduled run after the fix (tonight). Grade it with R2-1 in mind: a push close to it can be credited to it.
