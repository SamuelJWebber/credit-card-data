# credit-B: US credit card data dashboard, outside comparison

Snapshot `3584f52f2bbaa50c0f396b1331e1251aa8d8efbb` (bot refresh 2026-11-10T04:04Z). Reviewed 2026-11-10.

What I ran. Downloaded the live page with curl and compared it with the snapshot: `cmp` clean, 3,701,623 bytes, so
the page GitHub serves is `docs/index.html` at this SHA. Extracted its visible text, its embedded JSON
(`window.CARDDASH`, 78 charts) and both thesis notes into the work folder
(`work/credit-B/live/page_text.txt`, `charts_compact.txt`, `thesis.txt`, `thesis0908.txt`): that is the full list of
headline numbers, chart titles, chart notes and last readings. Fetched the agencies' own releases with
`curl -A "carddash/0.1.0"` (the project's User-Agent without the contact; never a browser string), at most two
requests a second, into `work/credit-B/gov/`. Read bureau and aggregator pages with WebFetch. Did not run the test
suite (credit-A's job). All figures below were read on 2026-11-10.

## Verdict

- The numbers are right: every headline I put beside its agency release matches to the digit.
- Two readings are wrong by the source agencies' own documents: a BEA model output sold as "interest households
  actually pay", and the NY Fed's stock delinquency rate used as current distress (credit-B-1, credit-B-2).
- The thesis is half right: outside cohort work, including the NY Fed today, backs "vintage event, fading"; it
  does not back "not macroeconomic", the dating of the repricing, or "cards are the only improving debt".
- As a dashboard it is broader and better documented than any outside one I found; it lacks borrower-count measures.
- Confidence: high on the matches and on the evidence for both HIGH findings; medium on the size of the BEA
  overstatement and on why bureau totals sit $100-160bn below the NY Fed's.

## Findings

### credit-B-1 [HIGH] [CONFIRMED] [new] The "interest households actually pay" chart divides a BEA series by the very Fed series BEA builds it from, so it measures a Fed rate assumption, not payments

- Where it shows: https://samueljwebber.github.io/credit-card-data/ , Pricing panel, chart "Interest households
  actually pay on consumer credit, against the card APR" (id `effective_rate`), 11.83% in Sep 2026. Chart note
  (`render.py:404-409`): BEA interest divided by G.19 credit "is the rate households actually pay on all consumer
  credit"; the gap to the APR is "the card balances that pay no interest at all"; "The APR rising while the
  effective rate stays flat means the repricing is landing on fewer dollars." Same wording in
  `crosswalks/series.csv:579` and reused in the Context chart "Nonmortgage interest payments as a share of
  disposable income".
- Evidence:
  - BEA FAQ 1407 (https://www.bea.gov/help/faq/1407): monthly estimates are "the product of total non-mortgage
    consumer credit outstanding and a weighted average interest rate".
  - BEA NIPA Handbook ch. 14 (https://www.bea.gov/resources/methodologies/nipa-handbook/pdf/chapter-14.pdf), annual
    method too: a weighted average rate "multiplied by total consumer credit outstanding, both ... based on FRB
    data"; table 14A: FRB credit outstanding times "an FRB 'blended' rate".
  - So (BEA interest) / (G.19 credit) returns BEA's blended Fed rate plus small extras (margin interest, policy
    loans). It cannot see transactors, promotional balances or any "fewer dollars": the rate is applied to all
    credit outstanding.
  - Consistency check (mine, PLAUSIBLE for the size): revolving is 26.2% of G.19 credit; 0.262 x 22.36 + 0.738 x
    8.1 = 11.8, the page's 11.83. That is the full card APR on every revolving dollar. The CFPB's 2025 card market
    report counts $160bn of card interest actually charged in 2024, about 13% of roughly $1.25trn, not 22%.
    If so the true all-credit rate is nearer 9% than 11.8%.
  - Tried to refute: looked for an annual benchmark to observed interest (none in ch. 14); checked whether the
    thesis notes lean on this chart (they do not).
- Why it matters: the title and note state an observation the BEA does not make, and the inference drawn from the
  gap is produced by the method. The interest-share-of-income chart (2.54% against a 2.02% 2015-19 average)
  inherits the same model and should say so.
- Fix: retitle to "BEA's modelled nonmortgage interest, as an implied rate"; delete the two inference sentences;
  say in the note that BEA computes it as Fed credit outstanding times a blended Fed rate. For what households
  actually pay on cards, cite the CFPB report's interest charges or call-report card interest income over card loans.

### credit-B-2 [HIGH] [CONFIRMED] [new] The state map, two state charts, the loan-type chart and two thesis sections read the NY Fed's stock delinquency rate as current, comparable distress; the NY Fed's own August 2026 post says its recent rise is stale charged-off debt

- Where it shows:
  - "Card distress by state" tile map (`templates/index.html.j2:287`), measure "90+ days delinquent".
  - "Card delinquency by state" note (`render.py:175`): rose in every area "so the deterioration was national";
    range "widened, from 6.0 points in 2019 to 8.3 in 2025".
  - "Balances 90+ days delinquent, by loan type" note (`render.py:181`): the lines "are comparable in a way that
    figures from different regulators are not".
  - `docs/design/thesis-2026-09-11.html:129`: "thirteen times more likely to be seriously delinquent than a
    mortgage balance"; section 5 compares 2025 state levels with 2019.
- Evidence:
  - NY Fed, Liberty Street Economics, 2026-08-11 (released with the Q2 report):
    https://libertystreeteconomics.newyorkfed.org/2026/08/how-distressed-are-consumers-reconciling-diverging-credit-card-delinquency-measures/
    The stock rate rose "because of a pool of stale, charged-off debts" reported for longer, not worse incidence;
    charged-off debt still reported a year later went from about 40% to 80%; for "how are households doing right
    now" use the flow rates. Excluding charged-off balances, the stock rate is flat after 2024.
  - The page's own data (`data/facts.csv`): stock 11.35% (2024 Q4) to 12.70% (2025 Q4), +1.35; flow 7.18% to 7.13%.
  - The map, from the embedded JSON: all 51 areas are higher in 2025 than 2024 (median +0.98, least +0.34 in SD,
    most +1.75 in NV) in a year when the national flow was flat and bank delinquency fell.
  - Rough size (PLAUSIBLE): stock/flow was 8.36/5.32 = 1.57 in 2019 Q4 and 12.70/7.13 = 1.78 in 2025 Q4; at the
    2019 ratio the 2025 stock would be about 11.2, not 12.7, so about a third of the 2019-2025 rise is reporting. The thesis sentence that the
    best state in 2025 (8.03) "is worse than the median state was in 2019" (7.42) does not survive a one-point
    correction.
  - On flows the card-to-mortgage ratio is 6.97 / 1.52 = 4.6, not thirteen.
  - Tried to refute: the page does carry the caveat in the "four measures" chart note (`render.py:253`), where it
    cites this post, and in the all-debt "stage of delinquency" note. 2021 to 2024 is corroborated by the flow
    (3.22% to 7.18%), so "national" holds for the surge. The NY Fed publishes the same stock chart and state file,
    so the numbers are theirs; the readings are not.
- Why it matters: a reader of the map concludes card distress worsened in every state in 2025. The publisher of
  the data says that rise is an artefact. The page knows this and does not say it on the map, the two state
  charts or the loan-type chart.
- Fix: put the charged-off caveat and the post on every chart and map that uses the stock rate; retitle the map
  "Card balances 90+ days late or charged off, by state"; drop "comparable" and the 2019-versus-2025 level
  comparisons; say that no state-level flow is published. In the thesis note, replace "thirteen times" with the
  flow ratio.

### credit-B-3 [MEDIUM] [CONFIRMED] [new] "Highest on record" is stated without "in nominal dollars", while the page's own charts and the best-known aggregator say revolving credit is 12 to 15 percent below its real peak

- Where it shows: Latest readings and `docs/latest.txt` (the text meant for pasting into posts): "$1,368bn in Sep
  2026, +4.2% on the year, highest on record (since Jan 1968)"; same flag on the bottom-half DFA line
  (`render.py:2181`).
- Evidence: the page's chart "Revolving credit, nominal and in today's dollars" peaks at $1,604.8bn in Feb 2008
  against $1,368.5bn now (14.7% lower); "Card debt as a share of disposable income" is 5.65% against 9.47% in 2008
  and a 6.73% 2015-19 average. WalletHub's G.19-based study (syndicated 2026-09-14,
  https://www.longisland.com/news/09-09-26/new-data-29-billion-increase-in-credit-card-debt.html): about $1.37trn,
  inflation-adjusted, "roughly 12% below the record high". The CFPB's 2025 report has a section (1.4) warning that
  nominal aggregates "tend to grow over time due to inflation". The Fed's G.19 text never says "record".
- Why it matters: a nominal stock that grows in most months sets a record in most months. The flag tells a reader
  the burden is unprecedented when the same page shows it is not.
- Fix: for dollar levels print "highest in nominal dollars; x% below the 2008 peak in today's dollars", or drop the
  flag for dollar series and keep it for rates.

### credit-B-4 [MEDIUM] [CONFIRMED] [new] The NY Fed headline balance includes about $163bn of 90+ day and charged-off debt; without it card balances grew 3.7% on the year, not 4.5%

- Where it shows: Latest readings: "Card balances on credit reports (NY Fed): $1,263bn in 2026 Q2, +4.5% on the year".
- Evidence: 12.27% of $1,209bn = $148bn (2025 Q2); 12.92% of $1,263bn = $163bn (2026 Q2). Balances outside that
  pool: $1,061bn to $1,100bn, +3.7%. Outside figures for the same year: Equifax bankcard +3.7% (May 2026, $1.1trn),
  Philly Fed large banks +3.4%, G.19 +4.2%, TransUnion +4.5% (Q3 2026, $1.16trn). At 2025 Q4 the NY Fed total
  ($1,277bn) exceeds Equifax's own published bankcard total ($1.12trn) by $157bn; the 90+ pool was $162bn. Both
  come from Equifax files. (That Equifax leaves charged-off accounts out is my inference from that match,
  PLAUSIBLE; its page does not say.) The NY Fed post in credit-B-2 says it keeps these debts in.
- Why it matters: "how much Americans owe on cards" is $100bn to $160bn higher on this line than on any lender or
  bureau measure, and over a quarter of its yearly growth is old debt accumulating.
- Fix: one clause on the reading and the chart: "includes about 13% that is 90+ days late, mostly charged off and
  no longer on a lender's books".

### credit-B-5 [MEDIUM] [CONFIRMED] [new] The thesis note's "cards are the only improving" debt is contradicted by its own table and by the NY Fed's release wording

- Where it shows: `docs/design/thesis-2026-09-11.html:63,109` (linked from the page's Thesis watch and Method):
  "Cards are the worst consumer asset by far, and the only improving one"; title "Cards turned down while every
  other debt turned up".
- Evidence: the note's own table: flow into 90+, 2024 Q4 to 2026 Q2: card 7.18 to 6.97 (-0.21); "Other (retail
  cards, consumer finance)" 5.63 to 5.19 (-0.44). NY Fed press release 2026-08-11
  (https://www.newyorkfed.org/newsevents/news/research/2026/20260811), year on year: card 6.93% to 6.97%, other
  5.42% to 5.19%, all debt 2.91% to 2.57%; headline "Credit Card Delinquency Transition Rates Remained Steady";
  cards "remain at elevated levels". The card flow has sat between 6.93 and 7.18 for nine quarters.
- Why it matters: the note presents a 0.2-point drift inside a flat range as a turn, and as unique to cards, when
  the closest neighbour improved twice as much. The page's own reading ("+0.04 pp on the year") already disagrees
  with the note it links.
- Fix: correct the section title and sentence; adopt the NY Fed's word ("steady"). Today's Q3 release (7.05% to
  6.87%, year on year) is the first that supports "improving" on this measure.

### credit-B-6 [MEDIUM] [CONFIRMED] [new] The three thesis tests cannot tell "washed out" from "stuck at an elevated plateau", which is what the NY Fed and the Fed Board describe

- Where it shows: Thesis watch, top of the page: "Holds" with three ticks (`render.py:1624-1640`).
- Evidence: test 1 passes while the flow is under 7.5%; the peak of the whole episode was 7.18%, and the 2015-19
  average is 4.36%. Test 2 (charge-offs under 4.2%) sits 0.8 above the 2015-19 average of 3.40%. Both pass at any
  level short of a new high. NY Fed, August: "elevated but ... largely stable since 2024". FEDS Note 2025-11-24
  (https://www.federalreserve.gov/econres/notes/feds-notes/a-note-on-recent-dynamics-of-consumer-delinquency-rates-20251124.html):
  rates "started to flatten". Philly Fed Q2 2026 Insights: the improvement "may partly reflect a shift in
  originations toward less risky borrowers" while stress in some households "remains elevated". NY Fed, 2026-11-10
  (comparison 6): macroeconomic conditions "were likely the main contributing factor", against the first note's
  "not a macroeconomic one" (`docs/design/thesis-2026-09-08.html`). The page has no cohort data at all; the first
  note calls this leg "the softest of the five". Test 3's series dips every first
  quarter (14.13, 14.41, 14.77 in 2024-26 Q1 against 14.9 to 15.6 in Q3), so a seasonal low can trip it.
- Why it matters: a green "Holds" beside "was a vintage event" reads as tested. The tests check that things did
  not get worse than the peak. The claim itself has outside support (comparison 6: CFPB, Boston Fed and NY Fed
  cohort analyses); it is the page's evidence for it that is missing, and "washed out" overstates a flow still 60%
  above its 2015-19 average.
- Fix: add a test the rival reading fails (flow below, say, 6% by a date); compare test 3 year on year; cite the
  outside cohort evidence (credit-B outside comparison 6) instead of inferring vintages by elimination.

### credit-B-7 [MEDIUM] [CONFIRMED] [new] "The repricing that came with it" misdates the margin: half the widening came before the 2022-24 losses, and the CFPB dates it from 2016

- Where it shows: Thesis watch sentence on the main page (`render.py:1624`); first note: issuers "took roughly five
  points of margin over prime during the loss cycle".
- Evidence: the page's own spread series (G.19 assessed-interest APR minus prime): 10.75 (2015-19 average), 12.13
  (2019 Q4), 13.19 (2021 Q4), 14.25 (2023 Q4), 15.61 (2026 Q3). Of the 4.9 points, 2.4 were in place by end 2021,
  before the flow into delinquency turned up. The spread jumps whenever prime falls (2020; late 2024 on) and dips
  when prime rises (12.71 in 2022 Q2): slow pass-through, not a decision taken in the loss cycle. CFPB, 2024-02
  (https://www.consumerfinance.gov/about-us/blog/credit-card-interest-rate-margins-at-all-time-high/), same series:
  issuers "began to gradually increase APR margin in 2016", "despite lower charge-off rates". CFPB 2025 report,
  account-level: margins "have risen consistently over the past ten years", 16.4% in 2024.
- Why it matters: the conclusion ("structural") survives and is stronger; the stated cause (the loss surge) does not.
- Fix: "a decade-long widening of the margin that the loss cycle did not start and has not reversed".

### credit-B-8 [MEDIUM] [CONFIRMED] [new] Every "who falls behind" measure on the page is balance-weighted; the one borrower-count measure published rose over the same year

- Where it shows: Latest readings and Performance panel: Fed 30+ (2.85%, -0.19), charge-offs (-0.37), NY Fed flow,
  Y-14, FDIC; all shares of dollars.
- Evidence: TransUnion Q3 2026 Credit Industry Insights, 2026-11-05 (GlobeNewswire copy:
  https://finviz.com/news/416965/credit-access-expands-as-lenders-pair-growth-with-more-strategic-risk-management):
  balance-level 90+ rate 1.99%, down from 2.05%; borrower-level 90+ rate 2.50%, "rose 13 basis points YoY";
  subprime originations +16.5%. The NY Fed post counts "more than 23 million Americans" with charged-off card debt
  on file. The page's own Y-14 account-based rates are loaded but not charted.
- Why it matters: more people behind on smaller balances is exactly what small-line subprime lending produces, and
  is the pattern the thesis predicts; the page cannot show it and its headlines read as "fewer are falling behind".
- Fix: chart the Y-14 account-share delinquency beside the balance share; say on the readings that they are shares
  of dollars; cite the TransUnion borrower rate in a note (it cannot be redistributed as a series without a licence).

### credit-B-9 [MEDIUM] [CONFIRMED] [new] Five derived series carry an "About this chart" description of a different quantity

- Where it shows (embedded `about` entries on the live page):
  - "Card delinquency, four measures": the FDIC "Noncurrent (90+ or nonaccrual), share of card loans" line is
    described as "Net charge-offs of credit card plan loans during the quarter ... Billions".
  - "Credit union card net charge-off rate": the three rate lines are described as "Credit card loans charged off,
    YEAR TO DATE ..., billions".
  - "Payment rate and the revolving share": the payment rate is described as "Total cycle-end balances ..., billions".
  - "Balances, limits and unused credit per card account": "Credit limit per account" is described as "Credit card
    balances outstanding on credit reports, billions".
  - "Card net charge-off rate by issuer": the all-FDIC rate is described as quarterly dollars.
- Evidence: `work/credit-B/live/carddash.json`, `charts[].about`; the plotted values are the rates (for example
  1.441% noncurrent, 2026 Q2). A derived series inherits the note of its first input.
- Why it matters: the page tells readers to "read the scope note before comparing"; for these the note is wrong,
  and for the FDIC line it names the wrong measure altogether.
- Fix: give each view-derived series its own note; add a render test that a series with a `view` never prints an
  input's note unchanged.

### credit-B-10 [LOW] [CONFIRMED] [new] The derived payment rate leaves interest, fees, cash advances and balance transfers out of its identity, and its stated error is the wrong size and partly the wrong sign

- Where it shows: "Payment rate and the revolving share of balances", 103.5% of opening balance (a quarter);
  note: charge-offs left in payments overstate it "by a few tenths of a point" (`render.py:303`, `sql/views.sql:161-189`).
- Evidence: closing = opening + purchases + interest + fees + cash advances + transfers - payments - charge-offs.
  Charge-offs at the Y-14's own 5.01% annualized are about 1.25 points a quarter, not tenths. Interest and fees
  (CFPB: $160bn and $31bn in 2024 on about $1.25trn) are about 4 points a quarter the other way. Net, by that
  arithmetic, the figure is understated by roughly 3 points a quarter, 1 a month (PLAUSIBLE: not measured).
  CFPB's measured monthly rates at end 2024: 37 percent on general purpose cards, 12 percent on private label; ours
  is 34.5% a month across both, so the level is in the right place.
- Why it matters: level only; the direction is fine. But the chart note under "Consumer sentiment"
  (`render.py:1446`) and the thesis say payment rates "set records": this series peaked at 112 in 2022 Q2, and the
  CFPB says payment rates "have slowly declined" since mid-2022. Only the full-payer share (36.9%) is at a record,
  as the Philly Fed also says.
- Fix: correct the note and both "record" sentences; show the rate per month so it can be read beside the CFPB's.

### credit-B-11 [LOW] [CONFIRMED] [new] Smaller wording points an outside reader would trip on

- "Series are labeled SA or NSA and are never compared across that line" (`index.html.j2:396`), but three charts
  draw the Fed's seasonally adjusted bank rate beside unadjusted series: monthly issuer rates, credit unions against
  "Commercial banks (Fed, SA)", and the four measures. The Fed publishes the unadjusted rates too; use those there.
- Access panel: "the only survey that asks households directly" (`render.py:633`). The Fed's SHED and SCF and the
  CFPB's Making Ends Meet survey ask households about applications and denials. "Only one on this page" is true.
- "Balances carrying interest, share of total" (`render.py:1142`) is the Philly Fed's revolving balances, "balances
  carried over from month to month", which include 0% promotional balances.
- G.19 "revolving credit" names the type of plan; about a third of large-bank card balances are paid in full each
  month (the page's own 68.06% revolving share). The headline label and chart titles say "card debt" for it and
  never say so; the Philly Fed report leads with the distinction (total balances +3.4%, revolving +1.5%).
- The page showed NY Fed 2026 Q2 when read; the NY Fed published 2026 Q3 on 2026-11-10 (card balances $1.285trn,
  flow 6.87%). Timing only: tonight's run should pick it up and is the first live test of that fetcher on a new quarter.

## Outside comparisons

Side by side, same quantity. "Match" means I read both numbers.

| Quantity | This page | Outside | Same definition? |
| --- | --- | --- | --- |
| Card balances, credit reports | $1,263bn, 2026 Q2 | NY Fed press release 2026-08-11: $1.263trn | Match |
| Card balances, bureaus | (none) | TransUnion $1.16trn (Q3 2026); Equifax $1.1trn (May 2026) | No: see credit-B-4 |
| Revolving credit | $1,368.5bn, Sep 2026, +4.2% y/y | Fed G.19 2026-11-06: Q3 +4.1% annual rate | Match (same source) |
| Card balances, 2024 | (history) | CFPB 2025 report: "exceeded $1.2 trillion" | Consistent |
| APR, accounts assessed interest | 22.36%, 2026 Q3 | G.19: 22.36 (August survey); LendingTree quotes the same | Match |
| APR, all accounts | 21.19% | G.19: 21.19 | Match |
| APR, new offers | Bankrate 19.71% (2026-11-04) | Bankrate 19.63% (2026-09-30); LendingTree 23.96% (Oct 2026) | Bankrate same series; LendingTree is midpoints over about 220 cards |
| APR, large issuers | (TCCP medians 19.99-26.74) | CFPB 2025 report: 25.2% general purpose, 31.3% private label (2024) | Different universe, disclosed |
| Margin over prime | 15.61 (2026 Q3); 14.27 (2023 Q3) | CFPB blog: 14.3 (2023); CFPB report 16.4 (2024, account-level) | Match on the G.19 method |
| Delinquency 30+, banks | 2.85% SA, 2026 Q2 | Fed table (updated 2026-08-25): 2.85; FDIC QBP: 2.81% past due and nonaccrual | Match |
| Delinquency 90+, balances | Y-14 1.49%; FDIC 1.44% | TransUnion 1.99% (Q3); Equifax 60+ 2.8% (May) | All lenders against large banks |
| Delinquency 90+, borrowers | (none) | TransUnion 2.50%, rising | Missing here: credit-B-8 |
| Flow into 90+ | 6.97%, 2026 Q2 | NY Fed: 6.97% (Q2); 6.87% (Q3, published today) | Match |
| Charge-offs | 3.82% SA (Fed); 4.00% FDIC | Fed release; QBP all-loan 0.57% | Match |
| Utilisation | 19.31% (Y-14 aggregate) | Equifax 20.3% (May 2026); NY Fed implied 22.7%; VantageScore 30.15% (per consumer, Jul 2026) | Aggregate against per-consumer; say so |
| Full payers / minimum payers | 36.9% / 10.15% of accounts | Philly Fed: "reached 37 percent"; CFPB: about 15% of general purpose cardholders paid only the minimum (2024) | Philly match; CFPB denominator differs |
| Payment rate | 103.5% a quarter (derived) | CFPB: 37% a month, general purpose, end 2024 | Close; see credit-B-10 |
| Revolving share | 68.06% of balances | CFPB: about 50% of accounts revolve | Dollars against accounts |
| Average balance | $1,932 per account; $4,350 per person with a file (2025) | TransUnion $6,678 per borrower with a balance; VantageScore $6.45K; CFPB about $5,300 per cardholder (2024); WalletHub $11,313 per household | No per-borrower figure here |
| New accounts under 660 | 18.52% (16.08% a year earlier) | Philly Fed: 16.1 to 18.5 percent | Match |
| Median new line under 660 | $600 ($500) | Philly Fed: "$500 to $600" | Match |

1. **New York Fed, Household Debt and Credit, 2026 Q2 (2026-08-11) and Q3 (2026-11-10).** Release text:
   https://www.newyorkfed.org/newsevents/news/research/2026/20260811 and .../20261110. Our balances and flow match.
   Their story: transitions "remained steady", "elevated"; ours in the readings agrees, the thesis note overstates
   (credit-B-5). They are more correct on how to read the stock rate (credit-B-2). Change: adopt their wording and caveat.
2. **New York Fed, Liberty Street Economics, 2026-08-11.** Reconciles stock, flow and call-report delinquency. Our
   "four measures" chart makes the same point and cites it; the rest of the page does not apply it. They are right.
3. **Federal Reserve Board, G.19 (2026-11-06) and Charge-off and Delinquency Rates (2026-08-25).** Identical numbers.
   Their notes define the assessed-interest rate as finance charges over the balances charged; our "APR paid by
   revolvers" is a fair label. The Board never calls a level a record. No change beyond credit-B-3.
4. **Philadelphia Fed, Large Bank Credit Card and Mortgage Data, 2026 Q2 Insights (2026-10-07).**
   https://www.philadelphiafed.org/surveys-and-data/2026-q2-large-bank . Same data, same direction: "measured
   expansion rather than a broad easing". They add what we lack: revolving against total balance growth as the
   lead, an inflation remark on credit lines, and the composition caveat on improving delinquency. Equal on numbers,
   they are more careful on the story.
5. **CFPB, The Consumer Credit Card Market, 2025 edition (2025-12-30, data to 2024).**
   https://files.consumerfinance.gov/f/documents/cfpb_consumer-credit-card-market-report_2025.pdf . Deeper (margin
   by tier, payment rates, revolvers, interest dollars: $160bn in 2024) and two years stale. It contradicts nothing
   in our numbers; it corrects the thesis chronology (credit-B-7) and supplies the interest total that exposes
   credit-B-1. We are fresher; they measure things we derive.
6. **Cohort studies (all three read).**
   - CFPB blog, Fulford and Gibbs, 2024:
     https://www.consumerfinance.gov/about-us/blog/credit-card-delinquencies-are-higher-than-in-2019-because-lenders-took-on-more-risk/
     From bureau data by vintage: cards "originated in 2021, 2022, and 2023 went delinquent faster"; standards
     "loosened a bit in 2021 and 2022".
   - Boston Fed, Current Policy Perspectives, 2025, "Are Recently Issued Credit Card Accounts More Risky?"
     https://www.bostonfed.org/publications/current-policy-perspectives/2025/are-recently-issued-credit-card-accounts-risky.aspx
     From Y-14M to December 2024: the faster delinquency of 2022-23 accounts "appears to have been only temporary";
     standards back to their long-run level.
   - FEDS Note 2025-11-24: re-leveraging after stimulus, looser standards and score migration; rates "started to flatten".
   - NY Fed, Liberty Street Economics, 2026-11-10 (published with the Q3 report, after the page's last refresh):
     https://libertystreeteconomics.newyorkfed.org/2026/11/a-look-at-the-wider-divide-in-credit-card-delinquency-by-income/
     Splits the flow into 90+ by origination vintage: the 2020-22 vintage peaked through 2023-24; chart title "The
     Effect of the Pandemic-Era Vintage is Waning"; the episode "may prove to be more of a pandemic-era echo".
     It also says macroeconomic conditions "were likely the main contributing factor".
   These measure cohorts, which our page cannot. They support the thesis's "vintage event, largely resolved"
   reading: on this point the thesis is right and under-evidenced, so cite them. They do not support "not a
   macroeconomic one" (the NY Fed and the FEDS Note both put macro and re-leveraging first), and they name the
   2020-2023 vintages where the note says 2021 and 2022.
6b. **NY Fed, Liberty Street Economics, 2026-11-04, "How Market Position Shapes Credit Card Interest Rates".**
   https://libertystreeteconomics.newyorkfed.org/2026/11/how-market-position-shapes-credit-card-interest-rates/
   On 14 million new cards: lenders "pass through less" of a fall in funding costs where their market share is
   larger. This is the mechanism behind the margin jumping each time prime falls (credit-B-7): it supports "the
   margin is the issuer's choice" and contradicts tying it to the loss cycle.
7. **TransUnion Q3 2026 (2026-11-05), Equifax May 2026 (2026-07-02) and December 2025, VantageScore CreditGauge
   July 2026 (2026-08-25).** Borrower-level and monthly, which we lack; no definitions, no downloads, no revisions.
   Their card totals are about $100bn to $160bn below the NY Fed's (credit-B-4).
8. **Bankrate, LendingTree, WalletHub.** Bankrate is on our page with its method stated correctly. LendingTree's
   23.96% is a different basket and it repeats the same G.19 figures we show. WalletHub leads with the
   inflation-adjusted total, which is the more honest headline than ours (credit-B-3); it does not explain its
   household count.
9. **St. Louis Fed FRED Blog (2023 post on three measures of card debt: nominal, real, share of income; search
   summary only).** Our Growth panel already draws all three. Equal, and we are current.
10. **Other open dashboards.**
    - American Default Research, https://american-default.pages.dev/for-data-users/ : 120 indicators with CSV, JSON
      and dated monthly copies; includes the TransUnion borrower series and a "states above 10%" count built on
      the same stock rate as credit-B-2; no definitions or seasonal labels. Better API, weaker notes.
    - jeremywhittaker.com/dashboards/consumer-credit-household-debt/ : four charts (NY Fed, G.19), daily check,
      uses the flow rate; a search summary had it still on the Q1 2026 NY Fed release. Far narrower.
    - Philly Fed Consumer Credit Explorer (state and metro, from the same panel): better geography than our
      annual state file. CFPB Consumer Credit Trends: our source for originations. `cfpb/consumer-credit-trends-data`
      and a Streamlit repo `adalbertobrant/chargeoff` on GitHub: data or single-series only.
    - I found no open project that joins this many sources with checks against release numbers.

## Where ours is better than the outside work

- One page for 14 sources with the universe of each stated; no agency or aggregator does this.
- Checks against hand-copied release numbers, a revision log (24,236 rows; G.19 revisions shown are under 0.02%),
  "as first published / since revised" marks, and source health. No outside dashboard shows revisions at all.
- Real-dollar and share-of-income views of revolving credit beside the nominal level (most aggregators show nominal only).
- The four-measures delinquency chart, which anticipates the NY Fed's own reconciliation.
- Margin over prime using the survey month's prime rate: reproduces the CFPB's 14.3 for 2023.
- Monthly issuer 8-K series with definitional warnings, and the American Express change of basis drawn as two lines.
- The October 2025 gap in unemployment and CPI drawn as a gap, with the reason.
- Open code and data; the bureaus publish press releases only.

## Checked and found right

- Live page equals snapshot (`cmp`).
- NY Fed 2026 Q2: $1.263trn, +$54bn y/y, flows by loan type (6.97, 7.83, 3.00, 1.52, 1.15, 5.19, 2.57): all match the
  press release table. Workbook Page 12 has 13.12 for 2026 Q1 card stock; the NY Fed post's text says 12.8; the page follows the workbook.
- G.19 release 2026-11-06: 21.19 and 22.36 for Q3 (August); history 22.83, 22.30, 21.52, 22.15 matches the page.
- Fed delinquency table: card 2.85 (2026:2), 2.91 (2026:1).
- Philly Fed Q2 2026: 16.1 to 18.5 percent, $500 to $600, $2,600 to $2,700, $7,000, 37 percent full payers.
- FDIC QBP Q2 2026: card past due and nonaccrual 2.81%, consistent with the Fed's 2.85 and the page's 1.44% noncurrent.
- Bankrate record 20.79% on 2024-08-14 and its method; LendingTree's record quarters (2024 Q3: 21.76, 23.37).
- NY Fed June 2026 credit access survey: rejection rates well below June 2025, applications at a multi-year high
  (third-party summary); the page's direction agrees.
- The 80 percent figure the page quotes from the NY Fed post is in the post.

## Not checked

- Experian's consumer debt study, the S&P/Experian bankcard default index, Fitch/Moody's/KBRA card ABS indices: not reached in the time.
- TransUnion's and VantageScore's own PDFs: read through a press-release copy and a press page; Equifax's treatment of charged-off accounts is inferred.
- The FRED Blog post on three measures of card debt: search summary only.
- BEA's actual blend weights (not published); the size in credit-B-1 is an estimate.
- More web searches: the shared search budget ran out late in the session, so the last items were fetched by
  direct URL only. The dashboard survey (comparison 10) is therefore thinner than I wanted: six items opened.
- Kansas City Fed consumer credit reports (404 at the path tried); Urban Institute "Debt in America" (not opened).
- The page in a browser (tools barred); the test suite and the pipeline (credit-A).
