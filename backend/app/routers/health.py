"""Health / meta endpoints."""

from fastapi import APIRouter

router = APIRouter()


# HEAD too: uptime monitors (the keep-alive ping on Render's free plan) use it.
@router.api_route("/health", methods=["GET", "HEAD"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "oppradar-backend"}
