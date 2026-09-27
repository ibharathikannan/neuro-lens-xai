from datetime import timedelta

from fastapi import APIRouter, Depends

from utils.config import CLASS_NAMES, CLASS_LABELS, IMG_SIZE
from utils.database import get_patients_collection, get_scans_collection, now_utc, ping
from utils.model_service import MODEL_INFO, MODEL_DISPLAY_NAME
from utils.security import get_current_user
from utils.views import fmt_date, scan_view

# Create Router
router = APIRouter(prefix="/api", tags=["Dashboard"])

NO_IMAGES = {"image_jpeg": 0, "gradcam_jpeg": 0}


# --- Routes ---

@router.get("/dashboard/summary")
async def dashboard_summary(user: dict = Depends(get_current_user)):
    scans_col, patients_col = get_scans_collection(), get_patients_collection()
    now = now_utc()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    scans = list(scans_col.find({}, NO_IMAGES).sort("created_at", -1))

    def aware(dt):
        return dt if dt.tzinfo else dt.replace(tzinfo=now.tzinfo)

    weekly = []
    for w in range(7, -1, -1):
        start, end = now - timedelta(days=7 * (w + 1)), now - timedelta(days=7 * w)
        in_week = [s for s in scans if start <= aware(s["created_at"]) < end]
        weekly.append({"week": f"W{8 - w}", "counts": {c: sum(1 for s in in_week if s["prediction"] == c) for c in CLASS_NAMES}})

    total = len(scans)
    distribution = {c: round(100 * sum(1 for s in scans if s["prediction"] == c) / total) if total else 0 for c in CLASS_NAMES}
    return {
        "patients": patients_col.count_documents({}),
        "patients_this_month": patients_col.count_documents({"created_at": {"$gte": month_start}}),
        "scans": total,
        "scans_this_month": sum(1 for s in scans if aware(s["created_at"]) >= month_start),
        "reports": total,
        "avg_inference_seconds": round(sum(s.get("inference_seconds", 0) for s in scans) / total, 2) if total else 0,
        "weekly": weekly,
        "distribution": distribution,
        "low_confidence": sum(1 for s in scans if s["confidence"] < 0.7),
        "recent": [scan_view(s, with_images=False) for s in scans[:5]],
    }


@router.get("/reports")
async def list_reports(user: dict = Depends(get_current_user)):
    """One report per scan — generated on demand by GET /api/scans/{id}/report."""
    return [{
        "id": "R-" + s["id"].split("-")[-1],
        "patient_id": s["patient_id"],
        "scan_id": s["id"],
        "result": s["prediction"],
        "created": fmt_date(s["created_at"], with_time=True),
        "blob_path": f"/api/scans/{s['id']}/report",
        "size": "DOCX",
    } for s in get_scans_collection().find({}, NO_IMAGES).sort("created_at", -1)]


@router.get("/system/model")
async def system_model(user: dict = Depends(get_current_user)):
    db_ok = ping()
    params = MODEL_INFO.get("params")
    return {
        "model": {
            "name": MODEL_DISPLAY_NAME,
            "source": MODEL_INFO.get("source") or "—",
            "revision": MODEL_INFO.get("revision") or "—",
            "parameters": f"{params / 1e6:.2f} M" if params else "—",
            "input": f"{IMG_SIZE[0]} × {IMG_SIZE[1]} RGB, pixels / 255",
            "classes": " · ".join(CLASS_LABELS[c] for c in CLASS_NAMES),
            "explanation": "Grad-CAM",
            "loaded": MODEL_INFO.get("loaded_at") or MODEL_INFO.get("status"),
        },
        "services": [
            {"name": "Model", "detail": MODEL_INFO.get("source") or "Hugging Face Hub",
             "status": MODEL_INFO.get("status", "unknown").capitalize(), "healthy": MODEL_INFO.get("status") == "ready"},
            {"name": "Database", "detail": "MongoDB", "status": "Connected" if db_ok else "Unavailable", "healthy": db_ok},
            {"name": "Similar-case search", "detail": "Reference library", "status": "Not loaded yet", "healthy": False},
            {"name": "File storage", "detail": "Azure Blob Storage", "status": "Not configured yet", "healthy": False},
        ],
        "comparison": [],
        "comparison_is_placeholder": True,
    }
