"""Every golden number against the document it cites (REVIEW.md bigger improvement 2, after R2-3).

    uv run python checks/verify_provenance.py              # every entry in checks/golden.yaml
    uv run python checks/verify_provenance.py --source bea # one source's entries

For each entry this fetches its origin_url once, with the pipeline's own User-Agent, and looks for the number in what
the document says: the text of an HTML page, the text of a PDF (pypdf), or the cells of a workbook. Round 2 of the
review did this by hand and found a link that answered 404 for two months (Capital One, June 2025) and two entries
that quoted a workbook while linking a news page that states neither number. .github/workflows/provenance.yml runs
this weekly and keeps an issue open while anything fails.

- PASS: the number is in the document, as copied (`1,347.7`), without separators, or at a thousand or a million times
  its scale (a release that prints 119,800 millions for a golden of 119.8 billions).
- FAIL: the document does not load (anything but HTTP 200; fetch_or_die), or does not contain the number.
- An entry derived from numbers the release states carries `derived` (the arithmetic, '100 - 4.7') and `stated` (the
  numbers that must be in the document, [4.7]). It passes when the arithmetic gives `expected` within its tolerance
  and every stated number is found.

The G.19 entries are searched here like any page; checks/verify_g19.py --provenance also reads them by row and column.
A short number can turn up in a long document by coincidence, so this catches a broken or wrong link and a number the
document no longer states, not a misread cell. It fails closed: 0 entries checked is exit 1.
"""

from __future__ import annotations

import argparse
import ast
import html
import io
import math
import operator
import re
import sys
import time
import zipfile
from pathlib import Path

import yaml

from carddash.cli import load_dotenv
from carddash.golden import golden_decimals, number_text
from carddash.http import CheckFailed, fetch_or_die, make_session

SCALES = ((1, 0), (1_000, -3), (0.001, 3), (1_000_000, -6), (0.000_001, 6))  # (factor, change in decimals)
SEC_PAUSE = 0.2  # seconds between requests to sec.gov: its fair-access rule is ten a second


def _arith(expr: str) -> float:
    """Evaluate '100 - 4.7' or '5351.7 + 8780.2': numbers and + - * / only, nothing else is accepted."""
    ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -ev(node.operand)
        raise ValueError(f"not plain arithmetic: {expr!r}")

    return ev(ast.parse(str(expr), mode="eval"))


def document_text(content: bytes, url: str, content_type: str = "") -> tuple[str, list[float]]:
    """(text, numeric cells) of a document: an HTML page, a PDF, an XLSX workbook (or a zip of CSVs)."""
    kind = content_type.lower()
    if content[:4] == b"%PDF" or url.lower().endswith(".pdf") or "pdf" in kind:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        return " ".join(page.extract_text() or "" for page in reader.pages), []
    if content[:2] == b"PK":
        if url.lower().endswith((".xlsx", ".xlsm")) or "spreadsheet" in kind:
            import openpyxl

            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            texts, numbers = [], []
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    for v in row:
                        if isinstance(v, bool) or v is None:
                            continue
                        if isinstance(v, (int, float)):
                            numbers.append(float(v))
                        else:
                            texts.append(str(v))
            wb.close()
            return " ".join(texts), numbers
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            return " ".join(z.read(n).decode("utf-8", "replace") for n in z.namelist() if not n.endswith("/")), []
    page = content.decode("utf-8", "replace")
    page = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", " ", page)
    page = re.sub(r"<[^>]+>", " ", page)
    return html.unescape(page), []


def _normalise(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").replace("−", "-").replace(" ", " ").split())


def renderings(expected: float, tolerance: float) -> list[str]:
    """The ways a release can print the number: as copied, without separators, and at the other common scales."""
    out = []
    # from the decimals the number was copied with (4.12) to those its tolerance implies (4.120 for 0.001)
    copied = golden_decimals(expected, 0.0)
    for decimals in range(copied, max(copied, golden_decimals(expected, tolerance)) + 1):
        for scale, shift in SCALES:
            value, d = abs(expected) * scale, max(0, decimals + shift)
            if d > 6 or value == 0 or not math.isfinite(value):
                continue
            text = number_text(value, d)
            for t in (text, text.replace(",", "")):
                if t not in out:
                    out.append(t)
    return out


def found_in(expected: float, tolerance: float, text: str, numbers: list[float]) -> str | None:
    """How the number appears in the document, or None."""
    for r in renderings(expected, tolerance):
        if re.search(rf"(?<![\d.,]){re.escape(r)}(?![\d])", text):
            return r
    slack = max(float(tolerance), 1e-9)
    for v in numbers:
        for scale, _shift in SCALES:
            if abs(abs(v) * scale - abs(expected)) <= slack:
                return f"cell {v:g}"
    return None


def check_entry(e: dict, text: str, numbers: list[float]) -> tuple[bool, str]:
    expected, tol = float(e["expected"]), float(e.get("tolerance", 0) or 0)
    if e.get("derived"):
        got = _arith(e["derived"])
        if abs(got - expected) > max(tol, 1e-9):
            return False, f"{e['derived']} = {got:g}, not {expected:g}"
        missing = [s for s in e.get("stated") or [] if not found_in(float(s), tol, text, numbers)]
        if not e.get("stated"):
            return False, "a derived entry must list the numbers the document states (`stated`)"
        if missing:
            return False, f"derived as {e['derived']}, but the document does not state {missing}"
        return True, f"{e['derived']}, with {e['stated']} stated"
    how = found_in(expected, tol, text, numbers)
    return (True, f"found as {how}") if how else (False, f"{number_text(expected, golden_decimals(expected, 0.0))} is not in it")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--source", help="only this source's entries")
    args = p.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    entries = yaml.safe_load((root / "checks" / "golden.yaml").read_text(encoding="utf-8")) or []
    if args.source:
        entries = [e for e in entries if e["source"] == args.source]
    load_dotenv(root / ".env")  # CARDDASH_CONTACT, for the pipeline's own User-Agent (the SEC requires one)
    session = make_session()

    docs: dict[str, tuple[str, list[float]] | CheckFailed] = {}
    passed = failed = 0
    for e in entries:
        url = e.get("origin_url", "")
        if url not in docs:
            if "sec.gov" in url:
                time.sleep(SEC_PAUSE)
            try:
                resp = fetch_or_die(session, url)
                text, numbers = document_text(resp.content, url, resp.headers.get("Content-Type", ""))
                docs[url] = (_normalise(text), numbers)
            except CheckFailed as exc:
                docs[url] = exc
            except Exception as exc:  # a document that will not parse is a failure, not a crash halfway through
                docs[url] = CheckFailed(f"{url} could not be read: {type(exc).__name__}: {exc}")
        doc = docs[url]
        if isinstance(doc, CheckFailed):
            failed += 1
            print(f"FAIL {e['id']}: {doc}")
            continue
        ok, how = check_entry(e, *doc)
        passed += ok
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'} {e['id']}: {how} ({url})")
    checked = passed + failed
    print(f"\n{checked} checked against {len(docs)} documents: {passed} PASS, {failed} FAIL")
    if checked == 0:
        print("0 entries checked: nothing was compared, so nothing is known to hold")
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
