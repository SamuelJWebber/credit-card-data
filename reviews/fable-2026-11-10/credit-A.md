# credit-A: US credit card data dashboard, internal attack

Snapshot `3584f52f2bbaa50c0f396b1331e1251aa8d8efbb` (bot refresh of 2026-11-10 04:04 UTC), reviewed 2026-11-10
17:15 to 20:30 UTC. The live page, `latest.txt`, `data/facts.csv` and `data/revisions.csv` at
https://samueljwebber.github.io/credit-card-data/ were fetched with curl and are byte-identical to `docs/` in the
snapshot (`cmp`), so every `file:line` below is also what the public reads.

What was run. Work folder `<review-scratch>/work\credit-A\`: `scripts\` holds
every script named below, `src-dl\` every primary-source download, `repo\` a clone of the snapshot used for the test
and pipeline runs (nothing was changed in the snapshot or the real project).

- `python -m uv run pytest -q -p no:cacheprovider` in the clone, single process: **440 passed, 0 failed**, exit 0.
- Primary sources fetched today with curl, User-Agent `carddash/0.1.0` (the project's own form, `http.py:32`, with the
  contact left empty, which is the fallback `make_session` uses at `http.py:62`), one request at a time, 0.6 s apart.
- `scripts\recompute.py`, `recompute2.py`, `payload_check.py`, `primary_rederive.py`: every headline, 13 derived
  series as plotted, and the numbers written into chart notes, recomputed without importing carddash.
- `carddash refresh --source nyfed_hhdc`, `carddash check`, `carddash render` in the clone against the NY Fed release
  of today; `scripts\sim_cct.py` for the CFPB files of today through the project's own fetcher and loader.
- Read-only `gh` for the Actions history and the run log of 42753165803.

## Verdict

- The numbers are right. All 16 "Latest readings" and the 3 thesis readings reproduce from the publishers' own pages
  or files as they stood at the 04:04 UTC build; all 13 derived series checked match a recomputation.
- Two sources published after that build (NY Fed household debt 2026 Q3 and the CFPB card files, both today). The
  project's parser and loader take both cleanly: tonight's page should read $1,285bn for 2026 Q3 and 8.20 million new
  cards for April, with 45 of 45 live reference checks still passing.
- What is wrong is prose and one chart: several hand-written sentences in chart notes state patterns the page's own
  data contradicts, and the "offered APR" chart draws a 1.5 to 3.5 point fall that is mostly new survey respondents.
- Two hygiene problems on the public surface: the address the pipeline guards as a secret is in the public commit
  history, and HTML escaping is off in the page template.
- Confidence: high on the numbers (two independent paths each); high on findings 1 to 6 (each reproduced).

Counts: 1 HIGH, 5 MEDIUM, 7 LOW, plus 4 known-but-live one-liners.

## Findings

### credit-A-1 [HIGH] [CONFIRMED] [new] The contact address the pipeline treats as a secret is public in the commit history

- Where it shows: the public repository's history. 73 commits on `main`, dated 2026-09-07 (`c676812`) to 2026-09-14
  (`cea48ed`), carry a personal gmail address as author and committer. Later commits use a noreply address.
- Evidence:
  - `git log HEAD --format=%ae | sort | uniq -c` in the snapshot: 73 gmail, 103 and 26 noreply.
  - The same address is the value of `CARDDASH_CONTACT`: compared in memory against the real project's untracked
    `.env`, printing only `True` (the address itself was never printed and is not quoted here).
  - GitHub serves it without a token: `curl https://api.github.com/repos/SamuelJWebber/credit-card-data/commits/cea48ed`
    answered 200 with `commit.author.email` on gmail.com (2026-11-10).
  - The pipeline goes out of its way to keep this value out of the repo: it is an Actions secret
    (`refresh.yml:64,73`) and `carddash scan-secrets` blocks any commit containing it (`refresh.yml:77`; run log
    "checked 2 secret value(s)"). REVIEW.md "Secrets" checked diffs with `git log --all -S`, which does not look at
    author metadata.
- How I tried to refute it: the GitHub profile publishes no e-mail (`gh api users/SamuelJWebber`: `email` null), so
  it is not public by choice elsewhere; the switch to noreply on 2026-09-14 says the exposure was not intended. It
  is an address, not a credential: the harm is spam and phishing, and the false assurance of the scan.
- Why it matters: same class as the "scrub your personal email" decision already open for two other repos, but this
  repo is not on that list, and its secret scan reports clean.
- Fix: owner's call. Either accept it and stop treating the contact as secret, or rewrite the 73 commits' author
  fields (`git filter-repo --mailmap`) and force-push, knowing forks and GitHub's cached commit views keep the old
  objects for a while. In both cases make `scan-secrets` say what it does not cover.

### credit-A-2 [MEDIUM] [CONFIRMED] [new] The fall in "offered" card APRs in 2025 H2 is mostly 79 new survey respondents, not prices

- Where it shows: Pricing, chart "Card APR offered vs APR paid" (`render.py:603-627`). It draws the median offered to
  scores 620 to 719 falling from 28.24% to 26.74%, the band's low edge from 22.24% to 19.99%, and "Offered to 620-719
  minus paid" narrowing from 5.99 to 4.44 points between 2025 H1 and 2025 H2.
- Evidence (`data/raw/tccp/tccp_products.csv`, the project's own product table; script inline in my log, pandas only):
  - Institutions in the CFPB file: 111 in June 2025, 174 in December 2025. 79 are new; 73 of the 79 have "Credit
    Union" in the name. Their products' median APRs are 16.0% (620 to 719), 18.0% (619 or less), 13.0% (720 and up).
  - Same 95 institutions in both files: 28.24 to 27.74 (620 to 719), 27.90 to 27.74 (619 or less), 22.24 to 22.24
    (720 and up). The page's all-product medians move -1.50, -3.50 and -2.25.
  - The page's own stable series agrees: `TCCP_TOP25` (the 25 issuers that must file) moves 28.99 to 28.49, 28.62 to
    28.24 and 24.24 to 23.99; `tccp_issuer_count` goes 123 to 195 (facts.csv).
  - Prime fell from 7.50 to 6.75 between the two survey dates (facts.csv `prime_rate`: 7.50 in June, 6.75 by
    January), so on a like-for-like basis offered margins over prime were flat to slightly wider, not lower.
  - Paid APR (G.19) was 22.25 in 2025 Q2 and 22.30 in Q4, so the like-for-like gap goes 5.99 to 5.44, not to 4.44.
- Why it matters: a reader sees issuers cutting offered rates by 1.5 to 3.5 points and the offered-over-paid gap
  closing by a quarter. On a like-for-like basis offered rates fell less than prime and the gap closed by about half
  a point. The median is unweighted across products, so it moves whenever small issuers enter or leave.
- Fix: draw the top-25 medians (a fixed panel by law) or a matched-institution median, keep the all-product median as
  a dashed line, and print the institution count per half-year in the note. Add a test that fails when the number of
  institutions changes by more than, say, 20% between files without the chart saying so.

### credit-A-3 [MEDIUM] [CONFIRMED] [new] HTML escaping is off in the page template, and failed-fetch messages carry raw bytes from the source

- Where it shows: `render.py:2531` builds the Jinja environment with `select_autoescape(["html"])`. The template is
  `index.html.j2`, which does not end in `.html`, so escaping is disabled. `templates/index.html.j2:381` prints every
  health message as `<li>{{ m }}</li>`, above the script blocks at `:407-408`.
- Evidence:
  - `select_autoescape(['html'])('index.html.j2')` returns `False` (`'index.html'` returns `True`); the live page has
    zero `&#39;` although it prints many apostrophes.
  - Eleven fetchers put the first 40 to 80 bytes of an unexpected response into the error text, for example
    `cfpb_cct.py:243`, `fred.py:171`, `phillyfed.py:181`, `fdic.py:442`, `nyfed_sce.py:282`. The loader stores it in
    `data/health.json` (`loader.py:288`), which the page prints.
  - Reproduced in the clone (`scripts\inject_test.py`, then `carddash render`): a cfpb_cct message built exactly as
    line 243 builds it from a body starting `<html><head><title>Service unavailable</title><script>window` is in
    `docs/index.html` raw; the escaped form is absent; a parser then sees the 51,081-character uPlot block swallowed
    into the injected script (script sizes go from `[119, 285, 51081, ...]` to `[119, 285, 60717, ...]`), so no
    chart would draw.
  - Already seen live in a harmless form: during the October outage the page printed the Philly Fed message
    containing `<660 Credit Score` unescaped (`git show cde7866:data/health.json`).
- How I tried to refute it: I fetched the two real "missing file" pages that answer HTTP 200 today. NY Fed's first 40
  bytes end at `<head` and Philly Fed's first 60 end at `<titl`, two bytes short of an open `<title>`. With those
  exact pages the damage is a garbled note, not a dead page. So this is latent, which is why it is not HIGH.
- Why it matters: the day a source fails is the day the page is meant to explain itself, and that is when unescaped
  upstream bytes land above the scripts. A hostile or compromised upstream could also run script on the public page.
- Fix: `autoescape=True` (or `select_autoescape(["html", "j2"])`), keep `| safe` only on the three vendored or
  JSON blocks that already have it, and add a render test with `<script>` in a health message.

### credit-A-4 [MEDIUM] [CONFIRMED] [new] "Every past charge-off peak followed an unemployment peak within a few quarters" is false in the page's own two series

- Where it shows: Performance, chart "Card charge-offs against unemployment", note (`render.py:287-291`).
- Evidence (`scripts\recompute.py`, facts.csv, the chart's own series `card_nco_rate_sa` and `unemployment_rate_sa`):

      NCO peak 4.91 in 1992 Q1   unemployment peak 7.8 in Jun 1992   charge-offs peaked first
      NCO peak 5.50 in 1997 Q3   unemployment 4.9 and falling        no unemployment peak
      NCO peak 7.65 in 2002 Q1   unemployment peak 6.3 in Jun 2003   charge-offs peaked five quarters first
      NCO peak 6.09 in 2005 Q4   unemployment 4.9                    no unemployment peak (bankruptcy law)
      NCO peak 10.54 in 2009 Q4  unemployment peak 10.0 in Oct 2009  same quarter
      NCO peak 4.69 in 2024 Q3   unemployment 4.1                    no unemployment peak

  The 2020 unemployment peak (14.8) had no charge-off peak at all. The claim holds for none of six peaks; one coincides.
- Why it matters: the next sentence ("charge-offs well above what the labour market implies is the signal that
  underwriting, not the economy, is the cause") and the thesis's "vintage event" reading lean on it.
- Fix: replace with what the series show: of six peaks since 1985, three came in or beside a recession and three
  (1997, 2005, 2024) came with unemployment low.

### credit-A-5 [MEDIUM] [CONFIRMED] [new] The three bank rates do not come from "the same survey of the same banks", and they are not measured the same way

- Where it shows: Pricing, chart "What banks charge by loan type: card, personal loan, new car", note
  (`render.py:554-557`): "All three rates come from the same quarterly survey of the same banks, so the gap between
  them is a pricing decision and not a difference in measurement."
- Evidence: the Fed's G.19 About page, https://www.federalreserve.gov/releases/g19/about.htm, read 2026-11-10. Car
  and personal loan rates come from form FR 2835 ("most common rate", "about 75 banks report regularly"). Card rates
  come from FR 2835a, "a sample of 50 credit card issuing banks". Footnote 5 of today's release says the car and
  personal rates are "simple unweighted averages of each bank's most common rate" on new loans, while the card rate on
  accounts assessed interest is total finance charges over the balances they were assessed on.
- Why it matters: one is a quoted rate on new loans averaged across banks, the other a balance-weighted yield on the
  existing book. The gap between them moves for measurement reasons, so the note's inference is not supported.
- Fix: say they are two Fed surveys with different panels and definitions, and drop "not a difference in measurement".

### credit-A-6 [MEDIUM] [CONFIRMED] [new] "Never compared across that line" (SA against NSA) is untrue for five charts

- Where it shows: Data and method, `templates/index.html.j2:396`: "Series are labeled SA or NSA and are never compared
  across that line."
- Evidence (PANELS in `render.py`): `credit_union_card_losses` (`:1044-1050`, credit union rates not adjusted, against
  "Commercial banks (Fed, SA)"), `issuer_monthly_nco` and `issuer_monthly_dq` (`:867-883`, issuers' unadjusted monthly
  rates against the Fed's adjusted quarterly line, whose label does not say SA), `dq_triangulation` (`:935-941`),
  `cct_below_prime_share` (CFPB adjusted against Y-14 unadjusted). Size of the effect, from the Fed's own two tables
  read today (`chargeoff/chgallnsa.htm` and `chgallsa.htm`): card charge-offs 2024 Q3 4.37 unadjusted against 4.69
  adjusted; 2025 Q1 4.67 against 4.44. The unadjusted series peaks in 2024 Q2, the adjusted one in 2024 Q3.
- Why it matters: a quarter's move of up to 0.3 points in the gap between credit unions or an issuer and "the
  industry" can be the calendar. The page promises this cannot happen.
- Fix: load the Fed's unadjusted series (`CORCCACBN`, `DRCCLACBN`) for those charts, or change the sentence to say
  which charts cross the line and why.

### credit-A-7 [LOW] [CONFIRMED] [new] Census turns amber "stale" on Census's normal calendar

- Where it shows: source health and the three retail charts' status badge.
- Evidence: the rule is 2 x 31 + 14 = 76 days for a monthly series with no `max_age_days` (`loader.py:224-227`;
  census rows in series.csv have none). The Census workbook's newest month is two months back, so it is 77 or more
  days old whenever the release falls on or after the 16th. It already happened: `git show 5293e56:data/health.json`
  and `f3bfef6` (2026-09-15 and 09-16) have `census=stale ... 78 days old (limit 76)`. Census's schedule
  (census.gov/retail/release_schedule.html, read today) puts September data on 2026-11-17, so the runs dated
  2026-11-16 and 11-17 will be amber again, then 12-16, then 2027-02-15 to 02-17.
- Why it matters: a false alarm on the page that promises "never silently stale", two nights most months.
- Fix: `max_age_days` 85 on the 12 census rows. The health strip's "Sep 2026 data expected around 2026-11-14" is
  also three days early for the same reason (`RELEASE_RHYTHM` census lag 45).

### credit-A-8 [LOW] [CONFIRMED] [new] "Highest on record" is a nominal record, and the headline does not say so

- Where it shows: first line of the page and of `latest.txt`: "$1,368bn in Sep 2026 ... highest on record (since Jan
  1968)". Tonight the second line gains the same flag.
- Evidence (`scripts\recompute.py`): at the September 2026 price level the peak is $1,605bn in February 2008; today is
  14.7% below it. As a share of disposable income it is 5.65% against a peak of 9.47% in 2008 Q1.
- Why it matters: `latest.txt` is written to be pasted into posts, away from the two charts that give this context.
- Fix: say "highest on record in dollars; 15% below the 2008 peak after inflation" or drop the flag for levels.

### credit-A-9 [LOW] [CONFIRMED] [new] Eight more hand-written sentences in chart notes are wrong or have gone stale

All are fixed text in `render.py` or `series.csv`, on a page that says "No model writes any of it" and "The page above
is mechanical".

- `render.py:986`: "The oldest borrowers are the only age band whose card delinquency has kept rising." True at 2026
  Q2; false with the NY Fed data released today (70+ falls 6.34 to 6.09; ages 50 to 59 have risen four quarters
  running, 5.99 to 6.47). Tonight's page will carry it against the chart.
- `render.py:610-612` and `views.sql:96`: "The sub-620 median is usually the lowest of the three." It is never the
  lowest: in all six half-years the 720-and-up median is (21.74, 23.24, 21.24, 21.74, 22.24, 19.99).
- `render.py:270-273`: prices "rose about 25 percent between 2020 and 2026". CPI: +28.2% (2020 average to 2026 so
  far), +29.8% (January 2020 to September 2026).
- `render.py:332-337` and the note under "Nonmortgage interest payments": the debt service ratio is "published about
  five months after the quarter ... the slowest series on the page". The Fed's release page
  (federalreserve.gov/releases/dsr/, "Release date: September 22, 2026") and the load stamp (2026-09-23) put 2026 Q2
  at 12 weeks. The Y-14, TCCP and CFPB originations series are slower.
- `render.py:298-305`: the payment-rate "accounting identity" omits interest and fees added to balances (about 3.9% of
  the opening balance a quarter: $666bn revolving at 22%), and leaving charge-offs in overstates by about 1.3 points
  (5.0% annualised), not "a few tenths". Net, the plotted rate (103.5% in 2026 Q2) is about 2.5 points too low.
- `render.py:1446`: "payment rates and full-payer shares set records". The full-payer share is at a record (36.9%);
  the page's payment rate peaked at 112.0% in 2022 Q2.
- `render.py:353-358`: the monthly survey "leads every lender-reported series on the page by a quarter or more". The
  issuer 8-K series on the same page are lender-reported, monthly, and two to three weeks late.
- `series.csv:2` (REVOLSL scope note) lists "nonfinancial businesses" as a holder; the Fed retired that sector in July
  2025 (G.19 About page). One scope note prints a stray backslash on the page ("the CFPB\'s proxy").
- Fix: compute the ones that can be computed (which age bands are at a high, the CPI change, which tier is lowest) and
  date the rest, as the Amex note already does ("in July 2026").

### credit-A-10 [LOW] [CONFIRMED] [new] Two headline readings are printed to a precision their samples do not have

- "Banks tightening card standards, net (SLOOS): 4.00% ... -0.20 pp on the year". The Fed's October 2026 table 1,
  question 18: 3 banks tightened, 1 eased, of 50. The year's change is no bank at all.
- "Card applications refused ... 15.39% in Jun 2026, -6.82 pp on the year". The workbook's own counts: 895 respondents,
  29.9% applied, so about 268 applicants; a simple-random-sample standard error of about 2.2 points per wave and 3.4
  on the difference, before weighting. The page says "about 1,000" and "about 1,100" household heads; the last four
  waves had 971, 919, 923 and 895.
- Fix: one decimal, and "(3 of 50 banks)" and "(about 270 applicants)" in the two labels.

### credit-A-11 [LOW] [CONFIRMED] [new] The first thesis test cannot fail short of a reading worse than the surge it is about

- Where it shows: Thesis watch, "Flow into 90+ day delinquency stays below 7.5%".
- Evidence: the series' highest reading since 2012 is 7.18 (2024 Q2), the peak of the 2022-24 surge. A full return
  to that peak would still read "Holds". The charge-off test (4.2 against a 4.69 peak) would catch it.
- Fix: set the line inside the surge's range (7.1 or so) or say plainly that this test only trips on a new high.

### credit-A-12 [LOW] [PLAUSIBLE] [new] "Effective rate on all consumer credit" may divide a wider interest total by a narrower debt total

- Where it shows: Pricing, "Interest households actually pay on consumer credit": 11.83% in September 2026 (BEA
  personal interest payments $617.9bn over G.19 consumer credit $5,224bn; reproduced).
- Reasoning: a rough build-up from the page's own rates (cards about $890bn revolving at 22%, autos $1.59tn at 8%,
  student $1.88tn at 5.5%, other at 12%) gives about $480bn, 9%. The $140bn gap suggests BEA's line covers household
  nonmortgage debt outside the G.19 (margin and other loans). Not confirmed.
- What would confirm it: BEA's NIPA Handbook definition of "personal interest payments" (Table 2.1 line 30).
- Fix if confirmed: label it "nonmortgage interest over consumer credit" and drop "the rate households actually pay".

### credit-A-13 [LOW] [CONFIRMED] [new] README says "Code: MIT" but the repository has no licence file

- Evidence: no `LICENSE*` in the snapshot root; `gh api repos/SamuelJWebber/credit-card-data` returns
  `license: null`. The vendored `src/carddash/vendor/uPlot.iife.min.js` carries only a URL banner; uPlot's MIT terms
  ask for its copyright and permission notice to travel with copies.
- Fix: add `LICENSE` (MIT) and `src/carddash/vendor/LICENSE-uPlot`.

### Known and still live on the public page (REVIEW.md round 2, no status line on main)

- R2-2 [known-but-live]: `grep -c "not endorsed or certified"` and `"disclaims"` on the live page both return 0.
- R2-3 [known-but-live]: the 404 Capital One link (accession `000092762825000212`) is printed twice on the live page.
- R2-5 [known-but-live]: "Each source is fetched in full every run" is still on the page; old deep links
  (`user5017.github.io/credit-card-data/latest.txt`, `data/facts.csv`, `img/*.png`) answer HTTP 404 with a script
  redirect, so browsers follow but hot-linked chart images and scripted downloads from the old address are dead.
- R2-6 [known-but-live]: "Due in the next two weeks: Federal Reserve Bank of New York 2026 Q3 ..." (which NY Fed
  source is not said).

## Checked and found right

Headlines against the publisher (not the feed), all read 2026-11-10:

| Reading on the page | Primary source | Result |
| --- | --- | --- |
| Revolving $1,368bn Sep 2026, +4.2% | G.19 current release: 1,368.5; Sep 2025 1,312.7 | match (+4.25%) |
| APR 22.36% 2026 Q3; all accounts 21.19 | same release, Q3 column | match |
| Margin over prime 15.61 | 22.36 less August prime 6.75 (FRED MPRIME) | match; 2015-19 mean 10.7475 |
| Card delinquency 2.85%, -0.19, lowest since 2023 Q2 | Fed `chargeoff/delallsa.htm`: 2.85, 3.04 a year ago, 2.75 in 2023 Q2 | match |
| Charge-offs 3.82%, -0.37 | Fed `chargeoff/chgallsa.htm`: 3.82, 4.19 | match |
| NY Fed balances $1,263bn 2026 Q2; flow 6.97% | `HHD_C_Report_2026Q2.xlsx` refetched, identical to the snapshot's | match (superseded today, below) |
| Minimum payers 10.15%, average 9.58 | Philly Fed `26Q2-CreditCardBalances.csv` refetched, identical; column "Share of Accounts Making the Minimum Payment" | match |
| Card refusals 15.39%; closed by lender 7.03% | NY Fed credit access workbook refetched, identical; `CCRejected`, `Lenderclosedatleastoneacct` | match |
| Chance of missing a payment 13.78% Oct 2026 | NY Fed SCE workbook refetched, identical | match |
| Unemployment 4.1% Oct 2026, no year-ago figure | BLS API `LNS14000000`: 4.1; October 2025 "unavailable due to the 2025 lapse" | match |
| SLOOS 4.0, dated 2026 Q3 | Fed October 2026 survey, table 1 Q18: 6.0 less 2.0; "generally corresponds to the third quarter" | match |
| Bottom-half consumer credit $2,644bn, +2.6% | Fed `dfa.zip` refetched, identical: 2,643,874 and 2,576,235 | match |
| Claims 189,000 week ending Oct 31 | DOL release of 2026-11-05 (oui.doleta.gov) | match |
| New cards 8.27 million Mar 2026 | CFPB file as of the build | matched then; CFPB replaced the file at 15:33 GMT today (below) |

- Debt service 5.28%: matches FRED `CDSP`; the Fed's own table is script-loaded, so only its release date was read.
- Census workbook, NY Fed state workbook: refetched, identical to the snapshot. BEA flat file: `Last-Modified` still
  Wed, 04 Nov 2026 14:23:02 GMT, the value the run's 304 line reports.
- 13 derived series as plotted on the live page equal my recomputation from facts.csv (`scripts\payload_check.py`):
  year-on-year, share of income, real balances, credit union share, effective rate, interest share of income, the
  three per-account figures, payment rate, revolving share, bottom-half share, below-prime share, online share, card
  volume and retail growth, offered-minus-paid.
- Note numbers that hold: state notes (0.34, 2.3, 6.0 to 8.3), Amex note (1.1, 3.5, 4.2, 5.4 in July 2026; $110.8bn),
  Y-14 "about three quarters" (Y-14 is 77% of NY Fed card balances; Philly Fed says "roughly three-fourths"), Navy
  Federal at the 18% cap, sentiment "near historic lows" (second lowest of 677 months), "joint accounts are counted
  twice" (the NY Fed's own note on the account sheet), card losses "several times the all-loan rate".
- Delinquency labels: every chart and headline says 30+ or 90+, stock or flow, and whose books. The top-100 split is
  on its own two charts, all adjusted and annualised, labelled.
- Actions: one scheduled run since the fix, 42753165803, 2026-11-10 04:01 UTC, success. Its log shows all 14 sources
  `ok` with the same series counts as `series.csv` (770 of 770 series have rows; none skipped). BEA took the 304 path
  and says so. 33 scheduled failures from 2026-10-08 to 11-09 before it. The cron is 22:00 UTC; the last four runs
  started between 01:15 and 04:01 UTC.
- Next release, tested for real: the NY Fed posted 2026 Q3 today (press release dated 2026-11-10, a day earlier
  than the page expects). `carddash refresh --source nyfed_hhdc` in the clone: `ok`, 68 new rows, 0 of 6,744 earlier
  values revised, `carddash check` 45 passed, render clean. Card balances $1,285bn (+4.2%), flow into 90+ 6.87%; the
  thesis still holds. The CFPB replaced all six card files today (Last-Modified 15:33 GMT): through the project's
  fetcher and loader, `ok`, 4,127 revised values (3 over 5%), 26 new rows, headline 8.20 million in April (+8.3%).
- Workflow file: no pull-request trigger, actions pinned to commits, secrets only in `env`, no untrusted input in
  `run:` lines. Nothing in it breaks on a release; the tests it runs first read no clock and no network.
- Old links: `github.com/User5017/credit-card-data` and file paths under it answer 301 to the new repo;
  `raw.githubusercontent.com/User5017/...` answers 200; the old site root redirects by meta refresh and script.

## Not checked

- FDIC per-bank figures, NCUA, and BEA values against the publisher (FDIC 2026 Q3 is not in the API yet: one probe,
  `total: 0`). Round 2 re-derived these from the raw files; I did not repeat it.
- SEC filings from sec.gov: the SEC asks for a contact in the User-Agent and I sent none. Bread Financial's September
  exhibit was read from the committed copy instead (5.99%, matches).
- The Fed's debt service table values, the CFPB's "FICO 8" and "1-in-48" descriptions, and the NY Fed blog post the
  delinquency note cites.
- The rendered page in a browser (browser tools were off limits); the page was read as HTML, text and JSON.
- `design/thesis-2026-09-11.html` and the story the page tells (credit-B's brief).
- `www.dol.gov/ui/data.pdf` answered 403 to the project User-Agent, and one unauthenticated `github.com` `.patch`
  request answered 429; neither was retried. The DOL figure came from oui.doleta.gov instead.
