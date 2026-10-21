# Turns files (PDF/DOCX/images) into text: native text layer first, rapidocr OCR
# for scans, Gemini vision only as a last resort. Called by: extractors.py,
# notebooks 01/02, and eventually api.parse_documents().

from __future__ import annotations

import base64
import logging
from functools import lru_cache
from pathlib import Path

import numpy as np
import pymupdf

from oppradar_ai.config import get_settings
from oppradar_ai.schemas import DocumentContent

logger = logging.getLogger(__name__)

# Below this many characters per page we consider the text layer empty -> OCR.
MIN_CHARS_PER_PAGE = 80


@lru_cache(maxsize=1)
def _engine():
    """Lazy, cached rapidocr engine (loading models takes ~1s)."""
    from rapidocr import RapidOCR

    return RapidOCR()


def read_document(path: str | Path) -> DocumentContent:
    """Read one PDF, DOCX or image file into text.

    Example:
        >>> doc = read_document("data/samples/cv_amine.pdf")
        >>> doc.method, "AMINE KADDOUR" in doc.text
        ('pdf_text', True)
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix == ".docx":
        return _read_docx(path)
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
        return _read_image(path)
    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        return DocumentContent(file_name=path.name, method="text", text=text, chars=len(text))
    raise ValueError(f"unsupported document type: {suffix or '(no extension)'}")


def _read_pdf(path: Path) -> DocumentContent:
    """PDF: use the text layer; fall back to OCR, then to Gemini vision."""
    doc = pymupdf.open(path)
    text = "\n".join(page.get_text() for page in doc)
    pages = len(doc)
    method = "pdf_text"
    warnings: list[str] = []
    if len(text.strip()) < MIN_CHARS_PER_PAGE * pages:
        logger.info("%s: text layer too small (%d chars) — running OCR", path.name, len(text))
        text = _ocr_pdf(doc)
        method = "pdf_ocr"
        warnings.append("text layer missing or too small; OCR was used (verify names/dates)")
        if len(text.strip()) < MIN_CHARS_PER_PAGE * pages:
            vision = _vision_pdf(doc)
            if vision:
                text, method = vision, "gemini_vision"
                warnings.append("OCR found almost nothing; Gemini vision was used (costs quota)")
    doc.close()
    return DocumentContent(
        file_name=path.name,
        method=method,
        text=text,
        pages=pages,
        chars=len(text),
        warnings=warnings,
    )


def _read_docx(path: Path) -> DocumentContent:
    """DOCX: paragraphs plus table cells, in document order."""
    from docx import Document

    doc = Document(path)
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            parts.extend(cell.text.strip() for cell in row.cells if cell.text.strip())
    text = "\n".join(parts)
    return DocumentContent(file_name=path.name, method="docx", text=text, chars=len(text))


def _read_image(path: Path) -> DocumentContent:
    """Image file: OCR, with Gemini vision only if OCR finds nothing."""
    image_bytes = path.read_bytes()
    text = _ocr_image(image_bytes)
    warnings: list[str] = ["OCR result — verify names, dates and links"] if text else []
    method = "image_ocr"
    if not text:
        text = _vision_text(image_bytes, "Transcribe every word of this document image.")
        if text:
            method = "gemini_vision"
            warnings = ["OCR found nothing; Gemini vision was used (costs quota)"]
    return DocumentContent(
        file_name=path.name, method=method, text=text, chars=len(text), warnings=warnings
    )


def _ocr_pdf(doc: pymupdf.Document) -> str:
    """Render every page of a PDF at 150 dpi and OCR the page images."""
    return "\n".join(_ocr_image(page.get_pixmap(dpi=150).tobytes("png")) for page in doc)


def _vision_pdf(doc: pymupdf.Document) -> str:
    """Ask Gemini to transcribe every page of a PDF (last resort, costs quota)."""
    question = "Transcribe every word of this document page."
    return "\n".join(
        _vision_text(page.get_pixmap(dpi=150).tobytes("png"), question) for page in doc
    )


def _ocr_image(image_bytes: bytes) -> str:
    """OCR one image (rapidocr, local models) joined in reading order."""
    import cv2

    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("could not decode image for OCR")
    output = _engine()(image)
    return "\n".join(output.txts or ())


def _vision_text(image_bytes: bytes, question: str) -> str:
    """LAST RESORT: ask Gemini to read an image. Returns "" when not configured
    (fake provider or no key) so offline runs never hit the network."""
    from google import genai

    settings = get_settings()
    if not settings.gemini_key_value or settings.llm_provider == "fake":
        return ""
    client = genai.Client(api_key=settings.gemini_key_value)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=[
            question,
            {
                "mime_type": "image/png",
                "data": base64.b64encode(image_bytes).decode(),
            },
        ],
    )
    return (response.text or "").strip()
