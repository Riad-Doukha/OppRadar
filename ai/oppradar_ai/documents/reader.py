# Turns files (PDF/DOCX/images) into text: native text layer first, rapidocr OCR
# for scans, Gemini vision only as a last resort. Called by: extractors.py,
# notebooks 01/02, and eventually api.parse_documents().

from __future__ import annotations

import base64
import hashlib
import logging
from functools import lru_cache
from pathlib import Path

import numpy as np
import pymupdf

from oppradar_ai.config import get_settings
from oppradar_ai.llm import DiskCache
from oppradar_ai.schemas import DocumentContent

logger = logging.getLogger(__name__)

# Below this many characters per page we consider the text layer empty -> OCR.
MIN_CHARS_PER_PAGE = 80


@lru_cache(maxsize=1)
def _engine():
    """Lazy, cached rapidocr engine (loading models takes ~1s).

    `ocr_text_score` filters low-confidence lines (rapidocr's default 0.5 drops
    whole lines on hard-to-read scans); RapidOCR's own INFO chatter is silenced.
    """
    from rapidocr import RapidOCR

    settings = get_settings()
    logging.getLogger("RapidOCR").setLevel(logging.WARNING)
    return RapidOCR(params={"Global.text_score": settings.ocr_text_score})


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
        text = _cached_ocr_pdf(path)
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
    text = _cached_ocr_image(path)
    warnings: list[str] = ["OCR result — verify names, dates and links"] if text else []
    method = "image_ocr"
    if not text:
        text = _vision_text(path.read_bytes(), "Transcribe every word of this document image.")
        if text:
            method = "gemini_vision"
            warnings = ["OCR found nothing; Gemini vision was used (costs quota)"]
    return DocumentContent(
        file_name=path.name, method=method, text=text, chars=len(text), warnings=warnings
    )


@lru_cache(maxsize=1)
def _ocr_cache() -> DiskCache:
    """OCR results cache (data/cache/ocr/), same content-addressed store as the LLM."""
    return DiskCache(directory=get_settings().cache_dir / "ocr")


def _ocr_key(image_bytes: bytes, dpi: int) -> str:
    """Cache key = sha256(file bytes) + render dpi (via the LLM cache helper)."""
    return DiskCache.key("ocr", str(dpi), hashlib.sha256(image_bytes).hexdigest())


def _cached_ocr_pdf(path: Path) -> str:
    """OCR every page of a PDF; cached on disk by (file bytes, dpi)."""
    dpi = get_settings().ocr_dpi
    key = _ocr_key(path.read_bytes(), dpi)
    if (hit := _ocr_cache().get(key)) is not None:
        logger.info("OCR cache hit for %s", path.name)
        return hit["text"]
    doc = pymupdf.open(path)
    text = "\n".join(_ocr_image(_page_png(page, dpi)) for page in doc)
    doc.close()
    _ocr_cache().put(key, {"text": text})
    return text


def _cached_ocr_image(path: Path) -> str:
    """OCR an image file; cached on disk by (file bytes, dpi)."""
    image_bytes = path.read_bytes()
    key = _ocr_key(image_bytes, get_settings().ocr_dpi)
    if (hit := _ocr_cache().get(key)) is not None:
        logger.info("OCR cache hit for %s", path.name)
        return hit["text"]
    text = _ocr_image(image_bytes)
    _ocr_cache().put(key, {"text": text})
    return text


def _page_png(page: pymupdf.Page, dpi: int) -> bytes:
    """Render one PDF page to PNG bytes at the configured OCR resolution."""
    return page.get_pixmap(dpi=dpi).tobytes("png")


def _vision_pdf(doc: pymupdf.Document) -> str:
    """Ask Gemini to transcribe every page of a PDF (last resort, costs quota)."""
    question = "Transcribe every word of this document page."
    dpi = get_settings().ocr_dpi
    return "\n".join(_vision_text(_page_png(page, dpi), question) for page in doc)


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
