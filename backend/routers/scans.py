import base64
import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from PIL import Image, UnidentifiedImageError

from utils.database import get_patients_collection, get_scans_collection, next_id, now_utc
from utils.logger import logger
from utils.model_service import classify, model_version
from utils.report_generator import generate_docx_report
from utils.security import get_current_user
from utils.views import explanation_for, image_to_jpeg_b64, scan_view

# Create Router
router = APIRouter(prefix="/api/scans", tags=["Scans"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
LOW_CONFIDENCE = 0.7


def _get_scan(scan_id: str) -> dict:
    scan = get_scans_collection().find_one({"id": scan_id})
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


# --- Routes ---

@router.post("/classify", status_code=status.HTTP_201_CREATED)
async def classify_scan(
    file: UploadFile = File(...),
    patient_id: str = Form(...),
    scan_date: str = Form(""),
    sequence: str = Form(""),
    notes: str = Form(""),
    user: dict = Depends(get_current_user),
):
    """Classifies an uploaded MRI slice, builds the heatmap, and saves the scan to the patient's record."""
    if get_patients_collection().find_one({"id": patient_id}) is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image is larger than 10 MB")
    try:
        image = Image.open(io.BytesIO(contents))
        image.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="The file is not a valid image")

    logger.info(f"Classify request for patient {patient_id} ({file.filename})")
    try:
        result = await run_in_threadpool(classify, image)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Model is not available yet: {e}")

    has_heatmap = result["gradcam"] is not None
    doc = {
        "id": next_id("S-" + now_utc().strftime("%Y")),
        "patient_id": patient_id,
        "created_at": now_utc(),
        "created_by": str(user["_id"]),
        "scan_date": scan_date,
        "sequence": sequence,
        "notes": notes,
        "prediction": result["prediction"],
        "confidence": result["confidence"],
        "probabilities": result["probabilities"],
        "status": "Flagged" if result["confidence"] < LOW_CONFIDENCE else "Awaiting review",
        "model_version": model_version(),
        "inference_seconds": result["inference_seconds"],
        "explanation": explanation_for(result["prediction"], result["confidence"], has_heatmap),
        "image_jpeg": image_to_jpeg_b64(image),
        "gradcam_jpeg": image_to_jpeg_b64(result["gradcam"]) if has_heatmap else None,
    }
    get_scans_collection().insert_one(doc)
    logger.info(f"Scan {doc['id']}: {doc['prediction']} ({doc['confidence']:.3f})")
    return scan_view(doc)


@router.get("/{scan_id}")
async def get_scan(scan_id: str, user: dict = Depends(get_current_user)):
    return scan_view(_get_scan(scan_id))


@router.post("/{scan_id}/review")
async def mark_reviewed(scan_id: str, user: dict = Depends(get_current_user)):
    _get_scan(scan_id)
    get_scans_collection().update_one({"id": scan_id}, {"$set": {"status": "Reviewed", "reviewed_by": str(user["_id"]), "reviewed_at": now_utc()}})
    return scan_view(_get_scan(scan_id))


@router.get("/{scan_id}/report")
async def download_report(scan_id: str, user: dict = Depends(get_current_user)):
    """Generates the scan's report (DOCX) on demand."""
    scan = _get_scan(scan_id)
    image = io.BytesIO(base64.b64decode(scan["image_jpeg"])) if scan.get("image_jpeg") else None
    gradcam = io.BytesIO(base64.b64decode(scan["gradcam_jpeg"])) if scan.get("gradcam_jpeg") else None
    report = await run_in_threadpool(
        generate_docx_report, image, scan["prediction"], scan["probabilities"], scan["patient_id"], scan["id"],
        scan.get("model_version", ""), gradcam)
    headers = {"Content-Disposition": f'attachment; filename="NeuroLens_{scan["id"]}.docx"'}
    return StreamingResponse(report, headers=headers,
                             media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@router.get("/{scan_id}/similar")
async def similar_cases(scan_id: str, k: int = 5, user: dict = Depends(get_current_user)):
    _get_scan(scan_id)
    raise HTTPException(status_code=501, detail="Similar-case search is not available yet — the reference library has not been loaded.")


@router.get("/{scan_id}/compare/{case_id}")
async def compare_cases(scan_id: str, case_id: str, user: dict = Depends(get_current_user)):
    raise HTTPException(status_code=501, detail="Case comparison is not available yet — the reference library has not been loaded.")
