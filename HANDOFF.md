# Handoff

## State

- `main` already fixed `credit-B-1` (with `credit-A-12`) and `credit-A-3` from `REVIEW.md`.
- Branch `sprint/credit-a2-and-checks` (branched cleanly off `main`) implements the remaining non-thesis `REVIEW.md` items outside PR #2 (`sprint/review-deferred-fixes`):
  - **`credit-A-2`**: `sql/views.sql` (`v_offered_vs_paid`, `v_tccp_offered_range`) and `src/carddash/render.py` switch the primary offered APR band (`hi`/`lo`), solid `620_719` line, and bounded `top25_spread_pct_pts` to the Top-25 matched statutory panel (`TCCP_TOP25`), keep `TCCP_ALL` `620_719` dashed, and append `_tccp_respondent_note` (half-year respondent counts + `>20%` swing flag).
  - **`credit-A-7`**: `crosswalks/series.csv` sets `max_age_days=85` across all 12 `census` rows; `render.py` (`RELEASE_RHYTHM["census"]`) updates expected lag from `45` to `48` days.
  - **`credit-A-9 (#1–#8)`**: updated `crosswalks/series.csv`, `sql/views.sql`, and `render.py` (`age70_by_loan_type` via `_age_dq_note`, `720-and-up`/sub-620 secured-card note, cumulative CPI-U via `_cpi_note`, `TDSP` ~3-month lag, Y-14 ~2.5–3 pp net flows, `sentiment`, `SCE_MONTHLY_NOTE` monthly 8-Ks, and `REVOLSL` retired nonfinancial-business note / CSV quote cleanup).
  - **`credit-A-10`, `credit-A-11`, `credit-B-4`, `credit-B-8`, `credit-B-11`**: sample sizes on `HEADLINES`, `7.18%` peak context in `THESIS_TESTS`, NY Fed ~13% 90+/charged-off note in `PER_ACCOUNT_NOTE` + `hhdc_card_balances`, balance- vs account-weighted distinction in `DQ_TRIANGULATION_NOTE`, and `"only survey on this page"` in `Access`.
  - **`credit-A-13`**: added root MIT `LICENSE` and `src/carddash/vendor/LICENSE-uPlot`.
  - **Mixed SA/NSA disclosures**: explicit `SA` vs `NSA` labels and explanations on `effective_rate`, `card_volume_vs_retail`, and `cct_below_prime_share` (while leaving `credit-A-6`'s `issuer_monthly_nco`/`issuer_monthly_dq` untouched for PR #2).
  - **Release check hardening**: fail-closed `aged > checked` guard, `allow_abbrev=False` CLI flags, finite/date/table/JSON-null validation in `checks/verify_g19.py` and `checks/verify_releases.py`, plus offline unit tests (`tests/test_verify_g19.py`, `tests/test_verify_releases.py`, `tests/test_bea.py`, `tests/test_tccp.py`, `tests/test_render.py`).
- No local edits to `data/` or `docs/`; GitHub Actions rebuilds rendered outputs on push.

## Verified, and how

- Full offline suite: `PYTHONPATH=src python -m pytest -p no:cacheprovider -v` covering `render`, `checks/verify_g19.py`, `checks/verify_releases.py`, `checks/verify_provenance.py`, `loader`, fetchers (`bea`, `tccp`, `census`), `golden`, `docs`, and `secrets`.
- Run targeted checks offline at any time without network calls; CI workflow (`.github/workflows/watch.yml` / `provenance.yml`) performs live data fetches and builds `docs/`.

## Next, in order

1. **Coordinate PR #2 (`sprint/review-deferred-fixes`) + this branch (`sprint/credit-a2-and-checks`)**: once PR #2 adds `VIEW_NOTES` / removes `VIEW_BOUNDS_UNCHECKED` entries, add a `VIEW_NOTES` explanation for `("v_offered_vs_paid", "top25_spread_pct_pts")` on `main`.
2. **Watch BEA Oct 2026 Personal Income & Outlays release (around `2026-11-25` / window ending `2026-11-27`)**: verify `watch.yml` ingests the new month cleanly via `checks/verify_releases.py`.
3. **Watch Fed December G.19 release**: if the annual benchmark revision rewrites back history beyond `golden.yaml` tolerances, inspect diffs with `python checks/verify_g19.py --provenance --dry-run` before approving any `--rebase`.

## Needs the user

- **`credit-A-1` (contact address in pre-2026-09-14 commit history)**: rejected by the owner on 2026-11-22 because a history rewrite would not purge GitHub-cached refs/forks and would break every cited commit hash; commits since `2026-09-14` do not carry it. To reverse later, run `git filter-repo` across the pre-2026-09-14 range, force-push, and ask GitHub Support to GC cached objects.

## Traps that have already cost time

- Do not commit local `data/` CRLF churn or `docs/` PNGs on Windows; Matplotlib font metrics and line endings differ from the Linux CI runner.
- `_connect(facts, views_sql, products_csv, issuers_csv)` needs `tccp_products.csv` and `crosswalks/issuers.csv` when running `sql/views.sql` because issuer views join `issuers`.
- `tests/test_secrets.py` fails if any tracked file names a local OS user profile path; never write workspace user paths in docs, tests, or notes.
- Set `PYTHONPATH=src` explicitly if running against a shared/sibling `.venv` so `carddash` resolves to the active checkout rather than an editable install elsewhere.
