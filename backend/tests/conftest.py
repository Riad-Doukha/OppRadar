# Test bootstrap: in-memory repository, HS256 test tokens and the offline fake
# LLM — set BEFORE the app (or oppradar_ai) is imported, so no .env, Supabase
# project or API key is ever touched.

import os
import tempfile
import time
import uuid

os.environ["DATA_BACKEND"] = "memory"
os.environ["SUPABASE_JWT_SECRET"] = "test-secret-at-least-32-bytes-long!!"
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["SUPABASE_ANON_KEY"] = ""
os.environ["DEMO_PASSWORD"] = ""
os.environ["LLM_PROVIDER"] = "fake"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="oppradar-backend-test-")

from pathlib import Path  # noqa: E402

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.repositories import get_repository  # noqa: E402
from app.repositories.memory import MemoryRepository  # noqa: E402

AI_DATA = Path(__file__).resolve().parents[2] / "ai" / "data"


def make_token(
    user_id: str | None = None,
    *,
    email: str = "amine.benali@ensia.edu.dz",
    full_name: str = "Amine Benali",
    demo: bool = False,
    admin: bool = False,
    expires_in: int = 3600,
    secret: str | None = None,
) -> str:
    app_metadata: dict = {"provider": "email"}
    if demo:
        app_metadata["demo"] = True
    if admin:
        app_metadata["role"] = "admin"
    claims = {
        "sub": user_id or str(uuid.uuid4()),
        "aud": "authenticated",
        "role": "authenticated",
        "email": email,
        "exp": int(time.time()) + expires_in,
        "app_metadata": app_metadata,
        "user_metadata": {"full_name": full_name},
    }
    return jwt.encode(claims, secret or os.environ["SUPABASE_JWT_SECRET"], algorithm="HS256")


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def repo() -> MemoryRepository:
    return MemoryRepository()


@pytest.fixture
def client(repo: MemoryRepository):
    app.dependency_overrides[get_repository] = lambda: repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def user_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def auth(user_id: str) -> dict[str, str]:
    """Headers for a regular signed-in user."""
    return bearer(make_token(user_id))
