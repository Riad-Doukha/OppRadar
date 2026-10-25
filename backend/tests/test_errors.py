# Unexpected errors must still reach the browser as JSON with CORS headers;
# otherwise the frontend only sees "Failed to fetch".

from app.repositories.memory import MemoryRepository


class BrokenRepo(MemoryRepository):
    def list_notifications(self, *args, **kwargs):
        raise RuntimeError("column notifications.dismissed_at does not exist")


def test_crash_returns_json_500_with_cors(client, auth):
    from app.main import app
    from app.repositories import get_repository

    app.dependency_overrides[get_repository] = BrokenRepo
    response = client.get("/me/notifications", headers={**auth, "Origin": "http://localhost:3000"})
    assert response.status_code == 500
    assert response.json() == {"detail": "Something went wrong on our side. Please try again."}
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
