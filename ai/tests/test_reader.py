# Reader tests: native text layer, OCR fallback for scans, dispatch + errors.

from pathlib import Path

import pytest

from oppradar_ai.documents.reader import read_document

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"


def test_text_pdf_uses_native_layer() -> None:
    doc = read_document(SAMPLES / "cv_amine.pdf")
    assert doc.method == "pdf_text"
    assert doc.pages == 1
    assert "kaddour" in doc.text.lower()
    assert doc.chars == len(doc.text)
    assert doc.warnings == []


def test_scanned_pdf_falls_back_to_ocr() -> None:
    doc = read_document(SAMPLES / "cv_sara_scanned.pdf")
    assert doc.method == "pdf_ocr"
    assert "SARA BELKACEM" in doc.text.upper()
    assert doc.warnings and "OCR" in doc.warnings[0]


def test_certificate_pdf_has_text() -> None:
    doc = read_document(SAMPLES / "certificate_alx_amine.pdf")
    assert doc.method == "pdf_text"
    assert "CERTIFICATE OF COMPLETION" in doc.text.upper()


def test_docx_paragraphs_and_tables() -> None:
    doc = read_document(SAMPLES / "cv_amine.docx")
    assert doc.method == "docx"
    assert "amine.kaddour@example.org" in doc.text

    portfolio = read_document(SAMPLES / "portfolio_sara.docx")
    assert portfolio.method == "docx"
    assert "sara.belkacem@example.org" in portfolio.text
    assert "github.com/sarab" in portfolio.text


def test_txt_dispatch(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    path.write_text("# hello", encoding="utf-8")
    doc = read_document(path)
    assert doc.method == "text"
    assert doc.text == "# hello"


def test_unsupported_extension_raises(tmp_path: Path) -> None:
    path = tmp_path / "archive.zip"
    path.write_bytes(b"PK")
    with pytest.raises(ValueError, match="unsupported document type"):
        read_document(path)
