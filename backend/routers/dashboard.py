import csv
import os
from datetime import timedelta

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from utils.config import CLASS_NAMES, CLASS_LABELS, COMPARISON_CSV, IMG_SIZE
from utils.database import get_patients_collection, get_scans_collection, get_studies_collection, now_utc, ping
from utils import blob_storage, similarity
from utils.model_service import MODEL_INFO, MODEL_DISPLAY_NAME, embedding_key
from utils.security import get_current_user
from utils.views import LIST_PROJECTION, fmt_date, scan_view, study_sizes

# Create Router
router = APIRouter(prefix="/api", tags=["Dashboard"])

NO_IMAGES = LIST_PROJECTION


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
    recent_sizes = study_sizes(scans[:5])
    return {
        "patients": patients_col.count_documents({}),
        "patients_this_month": patients_col.count_documents({"created_at": {"$gte": month_start}}),
        "scans": total,
        "scans_this_month": sum(1 for s in scans if aware(s["created_at"]) >= month_start),
        "reports": len(report_rows(scans)),
        "avg_inference_seconds": round(sum(s.get("inference_seconds", 0) for s in scans) / total, 2) if total else 0,
        "weekly": weekly,
        "distribution": distribution,
        "low_confidence": sum(1 for s in scans if s["confidence"] < 0.7),
        "recent": [scan_view(s, with_images=False, sizes=recent_sizes) for s in scans[:5]],
    }


def report_rows(scans: list[dict]) -> list[dict]:
    """One report per single-slice scan and one combined report per multi-slice study (newest first).
    A study's row links to its first slice, whose result page shows the whole study."""
    studies = {st["id"]: st for st in get_studies_collection().find(
        {"id": {"$in": list({s["study_id"] for s in scans if s.get("study_id")})}}, {"id": 1, "prediction": 1, "slice_count": 1})}
    first_slice = {}
    for s in scans:
        sid = s.get("study_id")
        if sid and (sid not in first_slice or s.get("slice_index", 0) < first_slice[sid].get("slice_index", 0)):
            first_slice[sid] = s
    rows, seen = [], set()
    for s in scans:
        sid = s.get("study_id")
        if sid in seen:
            continue
        if sid:
            seen.add(sid)
            st = studies.get(sid, {})
            rows.append({
                "id": "R-" + sid,
                "patient_id": s["patient_id"],
                "scan_id": first_slice[sid]["id"],
                "result": st.get("prediction", s["prediction"]),
                "study_id": sid,
                "slice_index": None,
                "slice_count": st.get("slice_count"),
                "created": fmt_date(s["created_at"], with_time=True),
                "blob_path": f"/api/studies/{sid}/report",
                "size": "DOCX",
            })
        else:
            rows.append({
                "id": "R-" + s["id"].split("-")[-1],
                "patient_id": s["patient_id"],
                "scan_id": s["id"],
                "result": s["prediction"],
                "study_id": None,
                "slice_index": None,
                "slice_count": None,
                "created": fmt_date(s["created_at"], with_time=True),
                "blob_path": f"/api/scans/{s['id']}/report",
                "size": "DOCX",
            })
    return rows


@router.get("/reports")
async def list_reports(user: dict = Depends(get_current_user)):
    """Reports are generated on demand: GET /api/scans/{id}/report or, for a multi-slice study, /api/studies/{id}/report."""
    return report_rows(list(get_scans_collection().find({}, NO_IMAGES).sort("created_at", -1)))


def load_comparison() -> list[dict]:
    """Rows of the notebook's final comparison (best configuration of each model, test set), highest macro-F1 first.
    The deployed model is marked by matching MODEL_DISPLAY_NAME, e.g. "Fibonacci-Net (lr=0.001)"."""
    if not os.path.exists(COMPARISON_CSV):
        return []
    with open(COMPARISON_CSV, newline="", encoding="utf8") as fh:
        rows = list(csv.DictReader(fh))
    table = [{
        "model": r["model"],
        "track": r["track"],
        "config": r["config"],
        "accuracy": round(float(r["test_accuracy"]), 4),
        "macro_f1": round(float(r["test_macro_f1"]), 4),
        "glioma_recall": round(float(r["recall_glioma"]), 4),
        "params": f"{float(r['params_M']):.2f} M",
        "latency_ms": round(float(r["cpu_latency_ms"])),
        "selected": f"{r['model']} ({r['config']})" == MODEL_DISPLAY_NAME,
    } for r in rows]
    return sorted(table, key=lambda r: r["macro_f1"], reverse=True)


@router.get("/system/model")
async def system_model(user: dict = Depends(get_current_user)):
    db_ok = ping()
    storage_text, storage_ok = await run_in_threadpool(blob_storage.status)
    search_text, search_ok = "Unavailable", False
    if db_ok:
        n_reference, n_patient = similarity.search_space(embedding_key())
        index = similarity.index_status()
        search_text = f"{n_reference:,} reference + {n_patient:,} reviewed scans · Atlas index: {index}"
        search_ok = n_reference + n_patient > 0
    params = MODEL_INFO.get("params")
    comparison = load_comparison()
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
            {"name": "Similar-case search", "detail": "MongoDB Atlas Vector Search", "status": search_text, "healthy": search_ok},
            {"name": "File storage", "detail": "Azure Blob Storage", "status": storage_text, "healthy": storage_ok},
        ],
        "comparison": comparison,
        "comparison_is_placeholder": not comparison,
    }
