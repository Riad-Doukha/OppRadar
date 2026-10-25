# CV upload (onboarding step 1): validation, background extraction with the
# fake LLM, the "Here is what we found" prefill, deletion.

import uuid

from conftest import AI_DATA, bearer, make_token

CV_PDF = AI_DATA / "samples" / "cv_amine.pdf"


def upload(client, headers, data: bytes, name="amine-benali-cv.pdf", consent=True):
    return client.post(
        "/documents",
        files={"file": (name, data, "application/pdf")},
        data={"kind": "cv", "consent_ai_processing": str(consent).lower()},
        headers=headers,
    )


def test_upload_requires_ai_consent(client, auth):
    response = upload(client, auth, CV_PDF.read_bytes(), consent=False)
    assert response.status_code == 422


def test_rejects_non_pdf(client, auth):
    response = upload(client, auth, b"PK\x03\x04 a docx", name="cv.docx")
    assert response.status_code == 415


def test_rejects_files_over_5_mb(client, auth):
    response = upload(client, auth, b"%PDF-" + b"0" * (5 * 1024 * 1024))
    assert response.status_code == 413


def test_upload_extracts_and_prefills(client, auth, repo, user_id):
    response = upload(client, auth, CV_PDF.read_bytes())
    assert response.status_code == 202, response.text
    doc = response.json()
    assert doc["status"] == "queued"
    assert doc["file_name"] == "amine-benali-cv.pdf"
    assert f"{user_id}/{doc['id']}.pdf" in repo.files

    # TestClient runs background tasks before returning, so it is processed now.
    detail = client.get(f"/documents/{doc['id']}", headers=auth).json()
    assert detail["status"] == "done", detail
    assert detail["read_method"] == "pdf_text"
    assert detail["extraction"]["full_name"]
    prefill = detail["prefill"]
    assert prefill["about"]["full_name"] == detail["extraction"]["full_name"]
    assert prefill["about"]["country"] == "Algeria"

    me = client.get("/me", headers=auth).json()
    assert "ai_cv_processing" in me["consents"]
    assert "alerts.consent.ai_cv_processing" not in me["onboarding"]["missing"]


def test_documents_are_private_and_deletable(client, auth, repo):
    doc = upload(client, auth, CV_PDF.read_bytes()).json()
    stranger = bearer(make_token(str(uuid.uuid4())))
    assert client.get(f"/documents/{doc['id']}", headers=stranger).status_code == 404
    assert client.get("/documents", headers=stranger).json() == []
    assert client.delete(f"/documents/{doc['id']}", headers=stranger).status_code == 404

    assert len(client.get("/documents", headers=auth).json()) == 1
    assert client.delete(f"/documents/{doc['id']}", headers=auth).status_code == 204
    assert client.get("/documents", headers=auth).json() == []
    assert repo.files == {}


def test_unreadable_pdf_is_marked_failed(client, auth):
    doc = upload(client, auth, b"%PDF-1.4 broken").json()
    detail = client.get(f"/documents/{doc['id']}", headers=auth).json()
    assert detail["status"] == "failed"
    assert detail["error"]
    assert detail["prefill"] is None
