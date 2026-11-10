# credit-V: verification of the US credit card data dashboard

Given: `findings\credit-A.md` (1 HIGH, 5 MEDIUM, 7 LOW) and `findings\credit-B.md` (2 HIGH, 7 MEDIUM, 2 LOW).
Snapshot `3584f52f2bbaa50c0f396b1331e1251aa8d8efbb`. Verified 2026-11-10.

State of the public surface when I checked: live page and `latest.txt` fetched 2026-11-10 17:49 UTC
(`Last-Modified: Tue, 10 Nov 2026 04:07:31 GMT`), byte-identical to `docs/` in the snapshot (`cmp`). GitHub `main` is
still at the snapshot SHA (`gh api repos/SamuelJWebber/credit-card-data/commits/main`). Nothing below has been fixed
since the reviewers read it.

How I checked. My own scripts, in `work\credit-V\`, read `docs/data/facts.csv`, `data/raw/tccp/tccp_products.csv`
and the live page's embedded JSON; none imports carddash or reuses a reviewer's script. Outside sources were fetched
again by me: government and Fed hosts with `curl -A "carddash/0.1.0"` (the project's form, `http.py:31`, contact left
empty), one request a second, into `work\credit-V\gov\`; other pages with WebFetch. sec.gov was not contacted.

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

## Per finding

### credit-A-1: UPHELD as fact, re-graded HIGH to MEDIUM

- Claim: the address kept as the Actions secret `CARDDASH_CONTACT` is the author e-mail on 73 public commits.
- What would make it false: the author address differing from the secret, or the count being wrong, or the commits
  not being served publicly.
- What I did: `work\credit-V\email_check.py` hashes each author and committer address from `git log` and compares
  with the `CARDDASH_CONTACT` line of the real project's untracked `.env`, printing hashes and True/False only.
  - `HEAD`: 202 commits. Authors: 103 and 26 on `users.noreply.github.com`, 73 on a personal gmail address, dated
    2026-09-07 to 2026-09-14; the committer field is the same on all 73.
  - Contact hash equals the gmail author hash: `True`. (The Actions secret itself cannot be read; the local `.env`
    is the value the README says to set.)
  - `curl https://api.github.com/repos/SamuelJWebber/credit-card-data/commits/cea48ed` with no token returns an
    author e-mail on gmail.com. The repo is public (`visibility: public`).
  - `work\credit-V\email_check2.py`: the address is in no tracked file, no diff (`git log --all -S`) and no commit
    message. So `REVIEW.md:292` ("in any commit on any ref") is right about content and silent on metadata.
  - The same address is the author on commits in two other public repos, abs-risk and ski-rentals-2027; the prior
    write-up (line 83) already lists scrubbing those two as an owner decision. credit-card-data is not on that list.
- Is it a real exposure: it is the ordinary fact that a public repo shows its author's commit e-mail. What makes it
  worth a finding is that the project says otherwise (`redact.py:22`: "not public"; the scan reports clean), and
  that the owner switched to noreply on 2026-09-14, so the intent was to keep it private. It is an address, not a
  credential; the pipeline also sends it to every source in a request header nightly. That is MEDIUM, not HIGH.
- The proposed fix needs care: a history rewrite here changes every SHA cited in `REVIEW.md` and `HANDOFF.md`, has to
  be done with the nightly bot paused, leaves old objects reachable by SHA on GitHub until support purges them, and
  does nothing about the other two public repos. A cheaper fix does what the guard is for: point `CARDDASH_CONTACT`
  at a dedicated alias, so the guarded value is again one that is not public. Decide the scrub once for all three.

### credit-A-2: UPHELD, MEDIUM

- Claim: the 2025 H2 fall in the "offered" APR medians is mostly new respondents, not prices.
- What would make it false: the same institutions showing the same fall.
- What I did: `work\credit-V\tccp_check.py` on `data/raw/tccp/tccp_products.csv` (stdlib, names normalised by me).
  - Institutions: 123 in the June 2025 file, 195 in December 2025 (equal to the page's `tccp_issuer_count`). New in
    December: 90, of which 83 have "credit union" in the name, 76 never in any earlier file. The reviewer's 111, 174,
    79 and 73 come from a different name match; the conclusion does not depend on it.
  - New entrants' products, median APR: 17.99 (619 or less), 16.0 (620 to 719), 12.99 (720 and up).
  - Same 105 institutions: 620 to 719, 28.24 to 27.74 (-0.50) against all products 28.24 to 26.74 (-1.50); 720 and
    up, 22.24 to 22.24 against 22.2 to 19.99. Top-25 flag: 28.99 to 28.49 and 24.24 to 23.99.
  - Prime fell from 7.50 (June 2025) to 6.83 (December average; 6.75 by January 2026) in `facts.csv`, so like for
    like the offered margin widened slightly. Paid APR (G.19): 22.25 in 2025 Q2, 22.30 in Q4.
- Addition the reviewer missed: `docs/design/thesis-2026-09-08.html` (section 4) quotes the drawn fall ("from 28.2 to
  26.7 percent ... from 22.2 to 20.0") and concludes competition "is showing up in acquisition pricing". That
  inference rests on the composition change.
- Verdict: upheld. The fix (draw the top-25 or matched median, print the institution count) is sound.

### credit-A-3: UPHELD, MEDIUM

- Claim: autoescape is off, so fetch-error text carrying upstream bytes reaches the page raw.
- What would make it false: escaping being on for `index.html.j2`, or messages being escaped before the template.
- What I did: read `render.py:2531`, `templates/index.html.j2:381`, `loader.py:288`, the fetchers; ran
  `work\credit-V\escape_check.py` with Jinja from credit-A's virtualenv (my script, not theirs).
  - `select_autoescape(["html"])("index.html.j2")` is `False`; for `index.html` it is `True`.
  - `{{ m }}` for a health message is the only upstream-fed text printed without `| safe` or JSON encoding; the
    payload JSON is guarded (`.replace("</", "<\\/")`, `render.py:2516`).
  - The messages hold `resp.content[:40]!r` to `[:80]!r` (for example `nyfed_sce.py:282`, `cfpb_cct.py:243`,
    `fdic.py:442`) and up to 200 characters of a FRED API reply (`fred.py:68`, `:133`). `repr` does not escape `<`.
  - A complete external script tag is 38 bytes. Rendered through the real template line under the real template
    name it comes out intact; under `index.html` it is escaped.
- Could a source's error page inject script: an ordinary error page, no. Each fetcher calls `raise_for_status()`
  first, and a normal page starts with `<!DOCTYPE html>` or `<html><head>`, which only garbles the note. It takes a
  source host (or its CDN) answering HTTP 200 with a body whose first 40 to 80 bytes are a script tag: a compromised
  or hostile upstream. All 14 sources are government, Fed or SEC hosts over TLS. The page has no Content Security
  Policy. There are no cookies or logins to steal; the harm is defacement, redirect or phishing of readers.
- Verdict: upheld at MEDIUM. Latent, one-line fix (`autoescape=True`), and a render test with `<script>` in a message.

### credit-A-4: UPHELD, MEDIUM

- Claim: "every past charge-off peak followed an unemployment peak within a few quarters" holds for none of six.
- What would make it false: most charge-off peaks dated one to four quarters after an unemployment peak.
- What I did: `work\credit-V\peaks_check.py` on `card_nco_rate_sa` and `unemployment_rate_sa` in `facts.csv`; a peak
  is the maximum of a window of 8 quarters either side (24 months for unemployment, with a rise of a point or more).

      1992 Q1  4.91   unemployment peak Jun 1992 (7.8)    charge-offs first, by 3 months
      1997 Q3  5.50   unemployment 4.9, down 0.7 in 2 yrs  no unemployment peak
      2002 Q1  7.65   unemployment peak Jun 2003 (6.3)    charge-offs first, by 15 months
      2005 Q4  6.09   unemployment 4.9, down 0.8           no unemployment peak
      2009 Q4 10.54   unemployment peak Oct 2009 (10.0)   same quarter
      2024 Q3  4.69   unemployment 4.1                     no unemployment peak

  The 2020 unemployment peak (14.8) has no charge-off peak after it at all.
- Fairness: the charitable reading is one of six (2009, where charge-offs stayed at 10.4 to 10.5 for two more
  quarters). A narrower window finds a secondary peak in 2003 Q4, six months after June 2003. "Every" is false
  either way, and three of six peaks came with unemployment low or falling.
- Verdict: upheld. The next sentence in the note ("underwriting, not the economy, is the cause") leans on it.

### credit-A-5: UPHELD, MEDIUM

- Claim: card, personal-loan and car rates are not from "the same survey of the same banks".
- What I did: fetched https://www.federalreserve.gov/releases/g19/about.htm (2026-11-10). Car and personal loan
  rates: form FR 2835, the "most common rate", "about 75 banks report regularly". Card rates: FR 2835a, "a sample of
  50 credit card issuing banks", finance charges over balances.
- Addition: the second thesis note repeats it ("Same survey, same banks, 2026 Q2").
- Verdict: upheld.

### credit-A-6: UPHELD, MEDIUM

- Claim: "never compared across that line" is untrue.
- What I did: read `index.html.j2:396` and the chart definitions at `render.py:867-883`, `:935-941`, `:1044-1050`:
  unadjusted credit union and issuer rates are drawn against `card_nco_rate_sa` and `card_dq_rate_sa`. Fetched the
  Fed's two tables: card charge-offs 2024:3 are 4.37 unadjusted and 4.69 adjusted; 2025:1, 4.67 and 4.44.
- Verdict: upheld for the three charts I read (I did not check the below-prime chart). Two of them label the Fed
  line "SA", so the crossing is visible; the method sentence is still false as written.

### credit-B-1: UPHELD, HIGH

- Claim: the chart divides BEA interest by the Fed credit total BEA builds it from, so it returns an assumption.
- What would make it false: BEA measuring interest paid from lender or household records, or benchmarking to them.
- What I did: fetched BEA's NIPA Handbook chapter 14 (dated December 2023) and FAQ 1407 myself.
  - Annual method, p. 14-10: non-mortgage interest paid by persons is "a weighted average interest rate ...
    multiplied by total consumer credit outstanding", both from Fed data. The rate covers autos, personal loans,
    revolving loans, student loans, mobile homes, RVs and boats.
  - Quarterly method, p. 14-14: the same, "as in the annual estimates". Table 14A line 17: Fed credit outstanding
    times an FRB "blended" rate. FAQ 1407 says the same of the monthly figures. No benchmark to observed interest.
  - So the reviewer's reading is right. It is about all consumer credit; BEA does not estimate card interest
    separately, and the revolving rate is one input to the blend. BEA does not publish the weights.
  - The numerator is also wider than the denominator (credit-A-12, now confirmed): line 17 adds interest on
    security purchases (margin loans), life insurance policy loans, farmers' consumer loans and interest paid to
    government.
  - The series behaves like a model in the page's own data (`work\credit-V\bea_check.py`): interest drops from
    $349bn to $295bn between February and April 2020 and jumps from $511.5bn to $556.8bn in September 2023, the
    two student-loan adjustments FAQ 1407 describes.
  - The note's premise is false in the page's own data: the "effective rate" did not stay flat while the APR rose.
    It went 8.39% (December 2019) to 11.83% (September 2026) as the APR went 16.88 to 22.36.
  - Size, not confirmed: if every revolving dollar is charged the G.19 APR, the implied rate on the rest is 8.1 to
    8.5%, which is plausible, so the blend looks like the full APR on all card balances. The CFPB's 2025 card
    market report (fetched) counts $160bn of card interest in 2024 on balances over $1.2trn, about 13%, not 22%.
- The page's exact words: title "Interest households actually pay on consumer credit, against the card APR"; note:
  BEA interest over G.19 credit "is the rate households actually pay on all consumer credit, cards, auto and student
  loans together"; the gap is "the cheaper non-card debt and the card balances that pay no interest at all"; "The
  APR rising while the effective rate stays flat means the repricing is landing on fewer dollars." The page does not
  claim a card-only figure.
- How I tried to break it: looked for any observed-interest benchmark in chapter 14 (none); checked whether a
  headline reading or thesis test uses the chart (none does).
- Verdict: upheld, HIGH at the low end. The number (11.83%) is a correct division of two official series. The title
  and both inference sentences claim a measurement the source does not make. The sibling chart, interest as a share
  of income, is a standard use of the BEA series and needs only the "modelled" caveat.

### credit-B-2: WEAKENED, HIGH to MEDIUM

- Claim: the map, two state charts, the loan-type chart and two thesis sections read the stock of 90+ day balances
  as current distress, and the NY Fed says the recent rise is stale charged-off debt.
- What would make it false: the post not saying that, or saying it about another product, or the state series
  using a different definition.
- What I did: fetched and read the post (Liberty Street Economics, 2026-08-11, URL as in credit-B).
  - It says it, about cards: the stock rate is rising "because of a pool of stale, charged-off debts" reported for
    longer. Charged-off debt still reported a year later: about 40% in 2004-12, 80% by 2024. With charged-off
    balances removed, all measures are "stable after 2024". For how households are doing now, use the flow.
  - It is national. The word "state" does not occur in the analysis. The state file uses the same stock definition
    from the same panel, so the mechanism applies by construction, but its size by state is not published.
  - The post dates the divergence from early 2024. Before that, stock and flow rose together.
  - `work\credit-V\stock_check.py`, page data: national stock 11.35 to 12.70 over 2025 with flow 7.18 to 7.13.
    States, 2021 to 2024: all 51 rose, least +1.56. States, 2024 to 2025: all 51 rose, +0.34 to +1.75, median +0.98.
    Range across states: 6.04 (2019), 6.91 (2024), 8.25 (2025).
- What survives and what does not:
  - "The deterioration was national" (2021 to 2025) survives: it holds on 2021 to 2024 alone and the flow confirms it.
  - Does not survive: any reading of the 2024 to 2025 rise as worsening distress; "the range ... widened, from 6.0
    points in 2019 to 8.3" (1.3 of the 2.2 points came in 2025, the artefact year); the thesis note's "best-performing
    state in 2025, at 8.03 percent, is worse than the median state was in 2019" (7.42; the margin is smaller than the
    2025 rise); "thirteen times more likely to be seriously delinquent than a mortgage" (stock 12.92 / 0.99 = 13.1;
    flow 6.97 / 1.52 = 4.6), which the note calls its "strongest single piece of evidence".
  - The reviewer overstated the loan-type point: the page draws the same comparison in flow terms on the next chart
    ("Flow into 90+ day delinquency, by loan type"). The stock chart's "comparable" sentence still needs the caveat.
- Exact wording on the page: map heading "Card distress by state", measure "90+ days delinquent", described as "Share
  of credit card balances 90 or more days delinquent, at the fourth quarter of each year". State chart note: "Card
  delinquency rose in every one of the 51 areas between 2021 and 2025, by 2.3 points in the state that moved least,
  so the deterioration was national ... The range across states also widened, from 6.0 points in 2019 to 8.3 in
  2025." Loan-type note: "measured the same way by the same panel, so the lines are comparable".
- Why MEDIUM: every number is the NY Fed's, labelled as what it is; the headline reading and the thesis tests use
  the flow; the page already cites this post on the four-measures chart; the main conclusion stands. What is wrong
  is a missing caveat on four charts and three sentences, two of them in the thesis note.

### credit-B-3 (and credit-A-8): UPHELD, MEDIUM

- What I did: `stock_check.py`: nominal $1,368.5bn in September 2026; in September 2026 dollars the peak is $1,604.8bn
  in February 2008, 14.7% higher. The nominal level was itself a record in 50 of the last 120 months. WalletHub's
  figure (via longisland.com, 2026-09-14) confirmed: about $1.37trn, "around 12% below the record high". CFPB report
  section 1.4 confirmed.
- Addition: `docs/design/thesis-2026-09-08.html` says the record headline "is true in nominal dollars and misleading
  in every other unit". The page's first line and `latest.txt` print exactly that headline. credit-A graded this
  LOW; credit-B's MEDIUM is the better grade.

### credit-B-4: WEAKENED, MEDIUM to LOW

- What I did: `stock_check.py`: $1,209bn to $1,263bn (+4.47%); less the 90+ share, $1,061bn to $1,100bn (+3.69%);
  the pool goes $148bn to $163bn, 28% of the year's growth. Arithmetic upheld.
- Why weaker: the reading is labelled "Card balances on credit reports (NY Fed)" and is the NY Fed's own headline
  figure. TransUnion's total (fetched: $1.16trn, Q3 2026) also grew 4.5%, so "every other measure grew less" is not
  so. That Equifax excludes charged-off accounts is the reviewer's inference; I could not verify it. A one-clause
  caveat is a fair request, nothing more.

### credit-B-5: UPHELD, MEDIUM

- What I did: read the note's own table and recomputed from `facts.csv`: flow into 90+, 2024 Q4 to 2026 Q2, card
  7.18 to 6.97, other 5.63 to 5.19. NY Fed press release of 2026-08-11 fetched: headline "Credit Card Delinquency
  Transition Rates Remained Steady"; cards "remain at elevated levels".
- Addition: on flows cards are not the worst either: student loans 7.83 against 6.97. "Worst by far" needs the stock.
- These phrases are in the thesis note only; the main page does not repeat them.

### credit-B-6: WEAKENED, MEDIUM

- The two reviewers disagree and credit-A is right: test 1 (flow under 7.5%) cannot fail short of a new high (the
  peak was 7.18), but test 2 (charge-offs under 4.2%) sits below five straight quarters of the surge (4.40, 4.56,
  4.69, 4.57, 4.44), so a return would trip it. credit-B's "both pass at any level short of a new high" is wrong.
- What stands: the flow is 6.97 against a 2015-19 average of 4.36, so "washed out" describes charge-offs (3.82
  against 3.40), not the flow. NY Fed, 2026-11-10 (fetched): macroeconomic conditions "were likely the main
  contributing factor"; the same post's chart is titled "The Effect of the Pandemic-Era Vintage is Waning". So the
  outside work backs "vintage effect, fading" and contradicts the first note's "not a macroeconomic one".

### credit-B-7: UPHELD, MEDIUM

- What I did: `work\credit-V\spread_check.py`: margin over survey-month prime 10.75 (2015-19 average), 12.13 (2019
  Q4), 13.19 (2021 Q4), 14.25 (2023 Q4), 15.61 (2026 Q3). Of 4.86 points, 2.44 were in place by 2021 Q4, when
  charge-offs were 1.63%. CFPB blog of 2024-02-22 fetched: issuers "began to gradually increase APR margin in 2016".
- Note: the first thesis note's own table says the five points were added "between 2015 and today"; its opening
  sentence and the page's claim ("the repricing that came with it") say otherwise.

### credit-B-8: WEAKENED, MEDIUM to LOW

- Upheld: the page charts only balance-weighted delinquency. TransUnion Q3 2026 (press-release copy, fetched):
  balance-level 90+ 1.99% from 2.05%; borrower-level 2.50%, up 13 basis points.
- Against it: the page's own account-weighted Y-14 series, which the reviewer wants charted, fell with the balance
  series: 90+ share of accounts 0.74 (2025 Q2) to 0.70 (2026 Q2); 30+ share 1.60 to 1.55. Large banks only, accounts
  not borrowers. The proposed fix would show agreement, not the divergence. It is one outside series in another
  universe; worth a sentence in a note.

### credit-B-9: UPHELD, MEDIUM

- What I did: `work\credit-V\payload_check.py` on the live page's JSON. Confirmed for four charts: the FDIC noncurrent
  line carries "Net charge-offs of credit card plan loans during the quarter"; the three credit union rate lines
  carry "charged off, YEAR TO DATE ..., billions"; "Credit limit per account" carries "Credit card balances
  outstanding ..., billions". I did not open the issuer chart.

## Us against the outside work

| Question | Ours | Theirs (who) | Do definitions match | Who is more correct, and why |
| --- | --- | --- | --- | --- |
| What rate do households pay on consumer credit | 11.83%, "actually pay" | BEA Handbook ch. 14: credit times a blended Fed rate | Same series | BEA: it is a model. Ours mislabels it. |
| What does card interest come to | implied 22% on all revolving | CFPB 2025 report: $160bn in 2024 on over $1.2trn, about 13% | CFPB measures it from issuers | CFPB |
| Is card distress still rising (stock) | stock up in all 51 areas in 2025 | NY Fed, 2026-08-11: stale charged-off debt; use the flow | Same panel and definition | NY Fed; our headline flow reading already agrees |
| Card balances and flow, 2026 Q2 | $1,263bn; 6.97% | NY Fed release: $1.26trn; steady | Yes | Equal |
| Is the level a record | "highest on record" | WalletHub: about 12% below the record after inflation; CFPB section 1.4 | Same G.19 series | Theirs is the fuller statement; our charts agree with them |
| Offered APRs, 2025 H2 | 28.24 to 26.74 | CFPB TCCP files, same institutions: 28.24 to 27.74 | Same files | The matched panel |
| When did the margin widen | "came with" the 2022-24 losses | CFPB, 2024: from 2016, with charge-offs low | Same G.19 method | CFPB |
| Why did delinquency rise | vintage, "not macroeconomic" | NY Fed, 2026-11-10: macro "likely the main" factor, vintage effect waning; Boston Fed 2025: 2022-23 effect "only temporary" | They have cohort data; we have none | Theirs on cause; ours on "fading" |
| Who falls behind | balance-weighted, falling | TransUnion Q3 2026: borrower-level 2.50%, +13bp | No: all lenders, borrowers | Not comparable; our Y-14 account series fell |
| New accounts under 660, large banks | 18.52% (16.08%) | Philly Fed 2026 Q2: 16.1 to 18.5 percent; $500 to $600 | Yes | Equal |
| Total card balances growth, large banks | (Y-14) | Philly Fed: +3.4%, revolving +1.5% | Yes | Equal; they lead with the split |
| Card and other bank rates | "same survey of the same banks" | Fed G.19 About: FR 2835 and FR 2835a | n/a | The Fed |

## Fix first

1. Retitle the "Interest households actually pay" chart as BEA's modelled nonmortgage interest over consumer credit,
   and delete the two sentences about interest-free balances and "fewer dollars".
2. Put the NY Fed's charged-off caveat on the state map, both state charts and the stock loan-type chart, and
   correct the three sentences that compare stock levels across years or loan types ("range widened", "worse than
   the median state was in 2019", "thirteen times").
3. Set `autoescape=True` at `render.py:2531` and add a render test with a script tag in a health message.

Next in line: draw the top-25 or matched-panel offered APR; say "in dollars" on the record flag; rewrite the
charge-off and unemployment sentence; decide the commit e-mail question once for all three public repos.

## What the published work gets right

- The live page equals the snapshot, and the numbers I re-read against the publishers match: NY Fed 2026 Q2
  balances and flows by loan type (press release), the Fed's adjusted and unadjusted charge-off tables (3.82 for
  2026:2), Philly Fed 2026 Q2 (16.1 to 18.5 percent, $500 to $600, +3.4%), the margin over prime (14.27 in 2023 Q3
  against the CFPB's 14.3).
- The page's headline delinquency reading uses the flow (6.97%, +0.04 on the year), which is the measure the NY Fed
  recommends, and its four-measures note already cites the NY Fed post.
- "The deterioration was national" holds on 2021 to 2024 alone, in all 51 areas.
- The payload JSON is escaped against `</script>`; no secret value is in any tracked file, diff or commit message.
- The page draws nominal, real and share-of-income views of revolving credit; outside aggregators mostly show one.
- The "vintage effect, fading" half of the thesis has outside support the page does not yet cite (NY Fed
  2026-11-10, Boston Fed 2025).

## Not checked

- LOW findings, except credit-A-8 and credit-A-12 (above). The tier-order point in credit-A-9 is plainly right
  (720 and up is the lowest median in the published series).
- Equifax's totals and its treatment of charged-off accounts; VantageScore; the FEDS Note of 2025-11-24; the CFPB
  cohort blog. TransUnion was read through a press-release copy, not its own PDF.
- BEA's blend weights (unpublished), so the size of the overstatement in credit-B-1 stays an estimate.
- The Actions secret itself; I compared against the local `.env` value only.
- Tonight's rebuild (NY Fed 2026 Q3, new CFPB files) had not run when I read the page.
