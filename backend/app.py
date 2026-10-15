import os
import warnings
from contextlib import asynccontextmanager
from pathlib import Path

# Suppress warnings and logs
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
warnings.filterwarnings('ignore')

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn

from routers.routes import router
from routers.auth_routes import router as auth_router
from routers.patients import router as patients_router
from routers.scans import router as scans_router
from routers.studies import router as studies_router
from routers.dashboard import router as dashboard_router
from utils.config import CORS_ORIGINS, JWT_SECRET_KEY, STATIC_DIR
from utils.database import ensure_indexes
from utils.logger import logger
from utils.model_service import load_model_in_background
from utils.security import seed_first_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not JWT_SECRET_KEY:
        logger.error("JWT_SECRET_KEY is not set — login and registration will fail. See .env.example")
    try:
        ensure_indexes()
        seed_first_admin()
    except Exception as e:
        logger.error(f"Could not prepare MongoDB indexes: {e}")
    if os.getenv("SKIP_MODEL_LOAD", "false").lower() != "true":
        load_model_in_background()   # the API answers immediately; classification waits for the model
    yield


app = FastAPI(title="NeuroLens API", lifespan=lifespan)

# Allow a separately hosted dashboard (e.g. `ng serve` on :4200) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routes
app.include_router(router)
app.include_router(auth_router)
app.include_router(patients_router)
app.include_router(scans_router)
app.include_router(studies_router)
app.include_router(dashboard_router)

# Serve the built Angular dashboard from the same URL (present inside the Docker image)
static_root = Path(STATIC_DIR).resolve()
if static_root.is_dir():
    logger.info(f"Serving dashboard from {static_root}")

    # Build files have a content hash in their name (main-XXXX.js), so they can be cached for a long time.
    # index.html must always be revalidated, so a new deployment is picked up on the next page load.
    ASSET_CACHE = {"Cache-Control": "public, max-age=31536000, immutable"}
    PAGE_CACHE = {"Cache-Control": "no-cache"}

    @app.get("/{full_path:path}", include_in_schema=False)
    async def dashboard(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        file = (static_root / full_path).resolve()
        if full_path and file.is_file() and static_root in file.parents:
            hashed = file.suffix in (".js", ".css") and "-" in file.stem
            return FileResponse(file, headers=ASSET_CACHE if hashed else PAGE_CACHE)
        if Path(full_path).suffix:
            # A missing file (e.g. a chunk from a previous deployment) is a real 404, not the dashboard page
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(static_root / "index.html", headers=PAGE_CACHE)   # Angular handles its own routes

if __name__ == "__main__":
    logger.info("Starting NeuroLens API...")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
