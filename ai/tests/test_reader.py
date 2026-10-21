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


def test_ocr_dpi_setting(monkeypatch) -> None:
    from oppradar_ai.config import Settings

    assert Settings().ocr_dpi == 220  # default
    monkeypatch.setenv("OCR_DPI", "300")
    assert Settings().ocr_dpi == 300  # env override


def test_ocr_is_cached_and_runs_once(monkeypatch, tmp_path, caplog) -> None:
    """The second read of the same scan must come from the disk cache."""
    import oppradar_ai.documents.reader as reader
    from oppradar_ai.llm import DiskCache

    calls = {"n": 0}

    def counting_ocr(image_bytes: bytes) -> str:
        calls["n"] += 1
        return "FAKE OCR LINE"

    monkeypatch.setattr(reader, "_ocr_image", counting_ocr)
    monkeypatch.setattr(reader, "_ocr_cache", lambda: DiskCache(directory=tmp_path / "ocr"))
    with caplog.at_level("INFO", logger="oppradar_ai.documents.reader"):
        first = read_document(SAMPLES / "cv_sara_scanned.pdf")
        second = read_document(SAMPLES / "cv_sara_scanned.pdf")

    assert first.method == "pdf_ocr"
    assert first.text == second.text == "FAKE OCR LINE"
    assert calls["n"] == 1  # OCR ran once; the second read hit the cache
    assert any("OCR cache hit for cv_sara_scanned.pdf" in r.message for r in caplog.records)


def test_scanned_ocr_reads_projects_correctly() -> None:
    """Regression: at the default 220 dpi the long PROJECTS lines must survive OCR."""
    pytest.importorskip("rapidocr")
    doc = read_document(SAMPLES / "cv_sara_scanned.pdf")
    assert "Logistics Tracker - https://github.com/sarab/logistics-tracker" in doc.text
    assert "Design System Starter - https://github.com/sarab/ds-starter" in doc.text
