# November 25, 2026 BEA disposable-income revision

Run `uv run python checks/replays/bea_2026_11_25/replay.py` from the repository root. The script checks the SHA-256 of all four inputs before reading the official comparison cells and recomputing the changes. It works offline after dependencies are installed.

| Input | Source and vintage |
|---|---|
| pi0926-hist.xlsx | September 2026 Personal Income and Outlays, October 29 release. The “PIOhist_M” sheet, G9:H9, prints the April change. [BEA workbook](https://www.bea.gov/sites/default/files/2026-10/pi0926-hist.xlsx) |
| pi1026-hist.xlsx | October 2026 Personal Income and Outlays, November 25 release. The “pi-hist” sheet, E9:F9, prints the January change. [BEA workbook](https://www.bea.gov/sites/default/files/2026-11/pi1026-hist.xlsx) |
| NipaDataM-subset.txt | September-vintage NIPA flat-file subset retained in tests/fixtures/bea. |
| NipaDataM-2026-10-revised-months.txt | April–October rows from the BEA flat file at repository revision 24185efb970b1ff5ad138475402e88a99d430387. The earlier fixture supplies the unchanged months. [Archived NIPA subset](https://github.com/SamuelJWebber/credit-card-data/blob/24185efb970b1ff5ad138475402e88a99d430387/data/raw/bea/latest/NipaDataM-subset.txt) |

Monthly changes are in billions of dollars at seasonally adjusted annual rates. The source flat file records levels in millions. The October workbook supports the January anchor, while the flat-file values establish the revised April change.
