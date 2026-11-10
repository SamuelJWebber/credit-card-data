"""checks/verify_provenance.py offline: how it reads a page, a PDF and a workbook, how it finds a number, and that it
fails on a dead link, a number the document does not state and a derivation that does not add up (REVIEW.md R2-3,
bigger improvement 2). Run live on 2026-11-10 it found all 70 entries in their 22 documents."""

from __future__ import annotations

import importlib.util
import io

import openpyxl
import pytest
import yaml

from conftest import REPO


@pytest.fixture(scope="module")
def vp():
    spec = importlib.util.spec_from_file_location("verify_provenance", REPO / "checks" / "verify_provenance.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pdf(text: str) -> bytes:
    """A one-page PDF that says `text`, assembled by hand with a correct cross-reference table."""
    content = f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 144] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


def _xlsx(rows) -> bytes:
    wb = openpyxl.Workbook()
    for row in rows:
        wb.active.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_it_reads_a_page_a_pdf_and_a_workbook(vp):
    text, numbers = vp.document_text(b"<p>Domestic&#160;Card <b>4.96</b></p><script>var x = 1.5;</script>", "a.htm")
    assert vp._normalise(text) == "Domestic Card 4.96" and numbers == []
    text, _ = vp.document_text(_pdf("Credit card loans 1,189,601"), "https://www.fdic.gov/qbp.pdf")
    assert "1,189,601" in text
    text, numbers = vp.document_text(_xlsx([["PCE", 113.1, "2026M08", 193.6]]),
                                     "https://www.bea.gov/sites/default/files/2026-10/pi0926-hist.xlsx")
    assert "2026M08" in text and numbers == [113.1, 193.6]


def test_a_number_is_found_as_printed_and_only_whole(vp):
    shown = vp.renderings(4.12, 0.001)
    assert shown[0] == "4.12" and "4.120" in shown  # copied with two decimals; the tolerance implies three
    assert "119,800" in vp.renderings(119.8, 0.0006)  # Census prints millions; the golden is in billions
    assert vp.found_in(4.12, 0.001, "Net Charge-Offs Rate 4.12 %", []) == "4.12"
    assert vp.found_in(4.12, 0.001, "rates of 14.12 and 4.123", []) is None  # never part of another number
    assert vp.found_in(1347.7, 0.06, "Revolving 1,347.7 1,354.4", []) == "1,347.7"
    assert vp.found_in(193.6, 0.06, "", [113.1, 193.6]) == "cell 193.6"
    assert vp.found_in(-0.47, 0.006, "down 0.47 percentage points", []) == "0.47"


def test_a_derived_entry_needs_its_arithmetic_and_its_stated_numbers(vp):
    entry = {"id": "x", "expected": 95.3, "tolerance": 0.06, "derived": "100 - 4.7", "stated": [4.7]}
    assert vp.check_entry(entry, "4.7% of outstanding debt was in some stage of delinquency", [])[0]
    assert not vp.check_entry(entry, "4.8% of outstanding debt", [])[0]
    assert not vp.check_entry({**entry, "derived": "100 - 4.8"}, "4.7% and 4.8%", [])[0]
    assert not vp.check_entry({**entry, "stated": []}, "4.7%", [])[0]
    with pytest.raises(ValueError):
        vp._arith("__import__('os').getcwd()")


def test_every_derived_golden_adds_up():
    """The entries no release states directly: the arithmetic and the numbers it starts from are in golden.yaml."""
    spec = importlib.util.spec_from_file_location("verify_provenance", REPO / "checks" / "verify_provenance.py")
    vp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vp)
    derived = [e for e in yaml.safe_load((REPO / "checks" / "golden.yaml").read_text(encoding="utf-8")) if "derived" in e]
    assert {e["id"] for e in derived} == {"hhdc_debt_current_2026_q2", "dfa_deposits_2025", "sce_monthly_miss_payment_2026_07"}
    for e in derived:
        assert e["stated"] and abs(vp._arith(e["derived"]) - e["expected"]) <= e["tolerance"], e["id"]


class _Session:
    def __init__(self, pages):
        self.pages = pages

    def get(self, url):
        status, body = self.pages.get(url, (404, b"Not Found"))

        class R:
            status_code = status
            content = body
            headers = {"Content-Type": "text/html"}

        return R()


def _main(vp, monkeypatch, tmp_path, entries, pages, *args):
    root = tmp_path / "repo"
    (root / "checks").mkdir(parents=True, exist_ok=True)
    (root / "checks" / "golden.yaml").write_text(yaml.safe_dump(entries, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(vp, "make_session", lambda: _Session(pages))
    monkeypatch.setattr(vp, "load_dotenv", lambda path: None)
    monkeypatch.setattr(vp, "__file__", str(root / "checks" / "verify_provenance.py"))
    monkeypatch.setattr(vp, "SEC_PAUSE", 0)
    return vp.main(list(args))


GOOD = "https://www.sec.gov/Archives/edgar/data/927628/000092762825000241/ex991june2025creditmetrics.htm"
DEAD = "https://www.sec.gov/Archives/edgar/data/927628/000092762825000212/ex991june2025creditmetrics.htm"
ENTRY = {"id": "cof_8k_nco_rate_2025_06_combined", "source": "issuer_8k", "expected": 4.96, "tolerance": 0.001,
         "origin_url": GOOD}


def test_a_dead_link_or_a_missing_number_fails_the_run(vp, monkeypatch, tmp_path, capsys):
    pages = {GOOD: (200, b"<td>Domestic Card</td><td>4.96</td>")}
    assert _main(vp, monkeypatch, tmp_path, [ENTRY], pages) == 0
    assert "1 checked against 1 documents: 1 PASS, 0 FAIL" in capsys.readouterr().out
    # R2-3: the accession this entry linked for two months answers 404
    assert _main(vp, monkeypatch, tmp_path, [{**ENTRY, "origin_url": DEAD}], pages) == 1
    assert f"FAIL cof_8k_nco_rate_2025_06_combined: {DEAD} answered HTTP 404, not 200" in capsys.readouterr().out
    assert _main(vp, monkeypatch, tmp_path, [{**ENTRY, "expected": 5.29}], pages) == 1
    assert "5.29 is not in it" in capsys.readouterr().out
    assert _main(vp, monkeypatch, tmp_path, [ENTRY], pages, "--source", "bea") == 1  # nothing checked is a failure
    assert "0 entries checked" in capsys.readouterr().out
