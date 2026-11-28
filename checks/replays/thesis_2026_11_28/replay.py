"""Reproduce the Nov 28 thesis watch. Pass --verify-source to audit the four rows against archived provider files."""
import argparse
import hashlib
import json
import subprocess
from datetime import date
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

from carddash.loader import read_facts
from carddash.render import _connect, _thesis_verdict, thesis_status

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REV = "24185efb970b1ff5ad138475402e88a99d430387"
EXTRACT_SHA = "be7f3a60e4e8cff0d06f7cfac6df63c6203453518c3e223c8d3104f040464316"
SOURCES = {
    "TERMCBCCINTNS": ("2026-08-01", "card_apr_assessed_interest", "de76bdc0ab7e77b6ec8cf61aa9ba2f23cc4fb3e8e21c9cb097ae85afbe9ebf19"),
    "MPRIME": ("2026-08-01", "prime_rate", "87d73711d5ca54f2ea380e98c7153ca71abaa84d36237fdeacb23d45c4199546"),
    "CORCCACBS": ("2026-04-01", "card_nco_rate_sa", "70bb8425c331d2e8adeda6c386de49c121286f52a15ceb92aea292c274e279ab"),
}


def archived(path, sha):
    raw = subprocess.check_output(["git", "show", f"{REV}:{path}"], cwd=ROOT)
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError(f"Hash mismatch: {path}")
    return raw


def verify_sources(values):
    for series, (day, metric, sha) in SOURCES.items():
        raw = archived(f"data/raw/fred/latest/{series}.json", sha)
        rows = [float(r["value"]) for r in json.loads(raw)["observations"] if r["date"] == day]
        if rows != [values[metric]]:
            raise ValueError(f"Unexpected {series} observation on {day}")
    raw = archived("data/raw/nyfed_hhdc/latest/HHD_C_Report.xlsx",
                   "f6370608a1e0dcf5e2781afc812fa789ac4d55cae6036361bbf42d41976b72a3")
    sheet = load_workbook(BytesIO(raw), read_only=True, data_only=True)["Page 14 Data"]
    if (sheet["A100"].value, sheet["C100"].value) != ("26:Q3", values["hhdc_card_transition_dq90"]):
        raise ValueError("NY Fed Q3 credit-card flow differs from the extract")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-source", action="store_true")
    args = parser.parse_args()
    extract = HERE / "inputs.csv"
    if hashlib.sha256(extract.read_bytes()).hexdigest() != EXTRACT_SHA:
        raise ValueError("Thesis fact extract hash mismatch")
    facts = read_facts(extract)
    if args.verify_source:
        verify_sources(dict(zip(facts.metric, facts.value, strict=True)))
    connection = _connect(facts, ROOT / "sql/views.sql", issuers_csv=ROOT / "crosswalks/issuers.csv")
    try:
        tests = thesis_status(connection, date(2026, 11, 28))
    finally:
        connection.close()
    if [round(t["value"], 2) for t in tests] != [6.87, 3.82, 15.61] or _thesis_verdict(tests) != "holds":
        raise ValueError("Thesis watch differs from the November 28 result")
    for test in tests:
        print(f"{test['text']}: {test['label']}")
    print("Verdict: holds")


if __name__ == "__main__":
    main()
