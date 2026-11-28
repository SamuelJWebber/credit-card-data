# November 28, 2026 thesis watch

Run `uv run python checks/replays/thesis_2026_11_28/replay.py --verify-source` from the repository root. This reads the historical provider files from Git, checks their SHA-256 hashes, verifies the four stored observations, and evaluates the same SQL spread and thesis rules as the dashboard. A shallow checkout without the source commit can run without the flag using the bundled four-row extract, or fetch revision `24185efb970b1ff5ad138475402e88a99d430387` before performing full source verification.

The extract preserves the four [fact rows' source snapshot](https://github.com/SamuelJWebber/credit-card-data/blob/24185efb970b1ff5ad138475402e88a99d430387/data/facts.csv), including original pull timestamps. The SHA-256 of the full facts file is `334516606e75e47fad22e31e26d67d5bbdd9ca4d57589942a89f962596394351`. The script records hashes for the extract and all four raw files.

| Test input | Provider artifact at the source revision |
|---|---|
| Q3 flow into serious card delinquency, 6.87% | New York Fed, Household Debt and Credit, “Page 14 Data”, A100/C100, quarter 26:Q3 and credit cards. [Workbook](https://github.com/SamuelJWebber/credit-card-data/blob/24185efb970b1ff5ad138475402e88a99d430387/data/raw/nyfed_hhdc/latest/HHD_C_Report.xlsx) |
| Q2 annualized charge-offs, 3.82% | FRED CORCCACBS, 2026-04-01 quarter. [Feed](https://github.com/SamuelJWebber/credit-card-data/blob/24185efb970b1ff5ad138475402e88a99d430387/data/raw/fred/latest/CORCCACBS.json) |
| Q3 assessed-interest APR, 22.36% | FRED TERMCBCCINTNS, survey month 2026-08-01. [Feed](https://github.com/SamuelJWebber/credit-card-data/blob/24185efb970b1ff5ad138475402e88a99d430387/data/raw/fred/latest/TERMCBCCINTNS.json) |
| August prime rate, 6.75% | FRED MPRIME, 2026-08-01. The spread is the assessed APR less prime in the survey month. [Feed](https://github.com/SamuelJWebber/credit-card-data/blob/24185efb970b1ff5ad138475402e88a99d430387/data/raw/fred/latest/MPRIME.json) |

Source: New York Fed Consumer Credit Panel/Equifax. Data are subject to the Terms of Use at newyorkfed.org. The FRED API notice and original publisher acknowledgments are in the repository README.
