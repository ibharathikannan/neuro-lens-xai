import os

from fastapi import APIRouter

from utils.database import ping
from utils.model_service import MODEL_INFO

# Create Router
router = APIRouter(prefix="/api", tags=["System"])


# --- Routes ---

@router.get("/health")
async def health():
    """Service status (used by the dashboard's Model & System page and the container health check)."""
    return {
        "status": "ok",
        "database": "connected" if ping() else "unavailable",
        "model": MODEL_INFO.get("status", "unknown"),
        "version": os.getenv("APP_VERSION", "dev"),   # git commit the image was built from
    }
