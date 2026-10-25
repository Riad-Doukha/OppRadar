"""Document upload (onboarding step 1 · "Upload your CV").

Upload -> stored in the private bucket -> processed in the background
(read -> extract) with live `document:progress` events -> the wizard shows the
"Here is what we found" card from GET /documents/{id} (`prefill`).
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

import pymupdf
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool

from app.auth import User, Writer
from app.config import get_settings
from app.models import Document, DocumentDetail, DocumentKind
from app.repositories import NotFoundError, Repository, get_repository
from app.services import ai
from app.sockets import emit_to_user

logger = logging.getLogger(__name__)

router = APIRouter()
Repo = Annotated[Repository, Depends(get_repository)]

PDF_MAGIC = b"%PDF-"


def _page_count(data: bytes) -> int | None:
    """Pages in the PDF, or None when it cannot be opened (processing then fails cleanly)."""
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            return doc.page_count
    except Exception:
        return None


@router.post("", response_model=Document, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    user: Writer,
    repo: Repo,
    background: BackgroundTasks,
    file: Annotated[UploadFile, File(description="PDF, max 5 MB")],
    consent_ai_processing: Annotated[bool, Form()] = False,
    kind: Annotated[DocumentKind, Form()] = "cv",
) -> Any:
    """Accept a PDF and start extracting it.

    Progress: poll GET /documents/{id} or listen to the `document:progress` socket event.
    """
    if not consent_ai_processing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Your CV is processed by an AI service. Please accept that before uploading, "
            "or fill in your profile manually.",
        )
    max_bytes = get_settings().upload_max_bytes
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"That file is larger than {get_settings().upload_max_mb} MB.",
        )
    if not data.startswith(PDF_MAGIC):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only PDF files are supported.")
    pages = _page_count(data)
    if pages and pages > get_settings().upload_max_pages:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"That PDF has {pages} pages. Please upload at most {get_settings().upload_max_pages}.",
        )

    repo.ensure_profile(user.id, user.full_name)
    repo.grant_consent(user.id, "ai_cv_processing")
    document_id = str(uuid.uuid4())
    storage_path = f"{user.id}/{document_id}.pdf"
    repo.put_file(storage_path, data, "application/pdf")
    row = repo.create_document(
        {
            "id": document_id,
            "user_id": user.id,
            "kind": kind,
            "file_name": Path(file.filename or "document.pdf").name[:200],
            "storage_path": storage_path,
            "size_bytes": len(data),
        }
    )
    background.add_task(process_document, repo, user.id, document_id, kind, data)
    return row


async def process_document(
    repo: Repository, user_id: str, document_id: str, kind: str, data: bytes
) -> None:
    """Read + extract one document off the event loop, reporting each stage."""

    async def stage(status_: str, **fields: Any) -> None:
        repo.update_document(document_id, {"status": status_, **fields})
        await emit_to_user(
            user_id,
            "document:progress",
            {"id": document_id, "status": status_, "error": fields.get("error")},
        )

    tmp = Path(tempfile.mkdtemp()) / f"{document_id}.pdf"
    try:
        tmp.write_bytes(data)
        await stage("reading")
        content = await run_in_threadpool(ai.read, tmp)
        await stage("extracting", read_method=content.method, warnings=content.warnings)
        extraction = await run_in_threadpool(ai.extract, kind, content)
        await stage("done", extraction=extraction.model_dump(mode="json"))
    except ai.LLMError:
        logger.exception("AI extraction failed for document %s", document_id)
        await stage(
            "failed",
            error="The AI service is busy right now. Try again in a minute, or fill in manually.",
        )
    except ValueError as exc:
        await stage("failed", error=f"We could not read this file: {exc}")
    except Exception:
        logger.exception("unexpected failure processing document %s", document_id)
        await stage("failed", error="Something went wrong while reading this file.")
    finally:
        # Windows: PyMuPDF can hold the handle of a file it failed to open.
        shutil.rmtree(tmp.parent, ignore_errors=True)


@router.get("", response_model=list[Document])
def list_documents(user: User, repo: Repo) -> Any:
    return repo.list_documents(user.id)


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(user: User, repo: Repo, document_id: UUID) -> Any:
    """One document; for a finished CV, `prefill` holds the values for the onboarding steps."""
    row = repo.get_document(user.id, str(document_id))
    if row is None:
        raise NotFoundError(f"document {document_id}")
    detail = DocumentDetail.model_validate(row)
    if row["kind"] == "cv" and row["status"] == "done" and row.get("extraction"):
        detail.prefill = ai.cv_prefill(row["extraction"])
    return detail


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(user: Writer, repo: Repo, document_id: UUID) -> Response:
    row = repo.delete_document(user.id, str(document_id))
    repo.delete_file(row["storage_path"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)
