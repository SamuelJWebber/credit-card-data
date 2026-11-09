# US credit card data dashboard

[![Nightly refresh](https://github.com/SamuelJWebber/credit-card-data/actions/workflows/refresh.yml/badge.svg?event=schedule)](https://github.com/SamuelJWebber/credit-card-data/actions/workflows/refresh.yml?query=event%3Aschedule)

A static page that refreshes itself daily from public sources and shows where card balances are growing,
what borrowers are charged, and how card credit is performing. Every number traces to a government release
and the pipeline checks a set of hand-copied headline figures on every run.

Live page: https://samueljwebber.github.io/credit-card-data/

## How it works

    fetchers/*.py -> validate -> replace-by-source into data/facts.csv -> sql/views.sql -> render -> docs/index.html

- One fetcher per source, each producing rows in one long `facts` table (metric x entity x tier x period).
- Series metadata (unit, cadence, scope note, sanity ranges) is hand-maintained in `crosswalks/series.csv`.
- The loader validates, logs revisions to `data/revisions.csv`, and refuses wholesale restatements until acknowledged.
- `checks/golden.yaml` holds numbers copied by hand from release pages; the pipeline must reproduce them.
- GitHub Actions runs the refresh daily and commits `data/` and `docs/`. GitHub Pages serves `docs/`.

## Run it locally

    python -m uv sync
    copy .env.example .env          # then fill in CARDDASH_CONTACT (required for the SEC) and, optionally, FRED_API_KEY
    python -m uv run pytest
    python -m uv run carddash refresh
    start docs/index.html

`CARDDASH_CONTACT` is a contact email: every request names the pipeline as `carddash/<version> <contact>`, the form
the SEC asks for, and without it the `issuer_8k` source fails. `FRED_API_KEY` is optional; without it the `fred`
source uses FRED's keyless CSV endpoint. Other commands: `carddash check` (the live golden checks; `--all` lists the
fixture-only ones too), `carddash health`, `carddash attention` (sources amber for a week), `carddash issuers`.

Design and rationale: `PLAN.md`, `design/PLAN-review.md`. Task board: `TASKS.md`. Working agreement: `CLAUDE.md`.
Current state: `HANDOFF.md`.

## What the page shows

Latest readings computed from the data (no model), a dated thesis with the tests that would prove it wrong, then 78
charts in eight panels: Growth (how much card credit is outstanding and who holds it), Pricing (what borrowers are
charged and what issuers advertise), Access (who applies, who is approved, who is shut out), Performance (charge-offs
and delinquency, by bank and by issuer, and bank lending standards), Borrowers (how households use and service card
credit), Distribution (the Fed's household balance sheet by wealth, income and age), Spend (what the cards buy) and
Context (the cost of household debt, the buffer behind it, sentiment). Then a tile map of card distress by state, a
browser for every series loaded, what changed in the last run, and the health of each source. Every chart opens on
the last five years with the full history one click away, shades NBER recessions, names the publisher of each series
and its cadence, shows when its data was loaded, and lists the release numbers it was checked against.

## Sources

Fourteen sources: Federal Reserve Board series via FRED (G.19 consumer credit, H.8 bank credit, charge-off and
delinquency rates, SLOOS, debt service), with a few BLS, BEA, Labor Department, University of Michigan and Bankrate
series from FRED credited to their publishers; CFPB Terms of Credit Card Plans; CFPB Consumer Credit Trends;
Philadelphia Fed large-bank credit card data (FR Y-14M); New York Fed Household Debt and Credit, State Level
Household Debt Statistics and Survey of Consumer Expectations (credit access and monthly); FDIC call-report data;
NCUA credit union call reports; Fed Distributional Financial Accounts; BEA personal consumption expenditures and
income; Census monthly retail trade; and the monthly charge-off and delinquency metrics Capital One, Synchrony, Bread
Financial and American Express file with the SEC. `CLAUDE.md` lists them with what each carries.

## License

Code: MIT. Data: as published by the respective agencies; see the notes under each chart.
