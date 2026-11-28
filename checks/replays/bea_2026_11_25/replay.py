"""Offline BEA release replay. Run with uv run python checks/replays/bea_2026_11_25/replay.py."""
import csv
import hashlib
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parents[2] / "tests/fixtures/bea"
INPUTS = {
    HERE / "pi0926-hist.xlsx": "6bffbf3caf179d92d3d146ec9ed7ea308d01ef415d9ca0cdee7962aae232ecbc",
    HERE / "pi1026-hist.xlsx": "c732c0c467095724ffb2194a90b46c5157b00dcf99edac15a8b451717dac6432",
    FIXTURES / "NipaDataM-subset.txt": "45f374adf5d34cec6976570719301f2eba733d54c77aca2176487af56cba60d5",
    FIXTURES / "NipaDataM-2026-10-revised-months.txt": "81e3bbca564ea868bf6df57c391dcc6682e31c832cde811ed016c6cb45fa9b14",
}


def dpi_levels(path):
    with path.open() as handle:
        return {month: Decimal(amount.replace(",", "")) / 1000
                for series, month, amount in csv.reader(handle) if series == "A067RC"}


def main():
    for path, digest in INPUTS.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"{path.name}: unexpected input hash")
    sept = load_workbook(HERE / "pi0926-hist.xlsx", read_only=True, data_only=True)["PIOhist_M"]
    octo = load_workbook(HERE / "pi1026-hist.xlsx", read_only=True, data_only=True)["pi-hist"]
    if (sept["G9"].value, sept["H9"].value, octo["E9"].value, octo["F9"].value) != ("2026M04", 12.7, "2026M01", 217.8):
        raise ValueError("Official historical-comparison cells do not match their dates and values")
    old = dpi_levels(FIXTURES / "NipaDataM-subset.txt")
    new = old | dpi_levels(FIXTURES / "NipaDataM-2026-10-revised-months.txt")
    for vintage, amounts, april in [("September", old, "12.733"), ("October", new, "-1.156")]:
        january_change = amounts["2026M01"] - amounts["2025M12"]
        april_change = amounts["2026M04"] - amounts["2026M03"]
        if (january_change, april_change) != (Decimal("217.808"), Decimal(april)):
            raise ValueError(f"Unexpected {vintage} changes")
        print(f"{vintage} vintage, $bn SAAR: January {january_change:+}, April {april_change:+}")


if __name__ == "__main__":
    main()
