import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from routers.scans import classify_and_store, read_upload, require_patient
from utils.blob_storage import image_bytes
from utils.database import get_scans_collection, get_studies_collection, next_id, now_utc
from utils.logger import logger
from utils.model_service import model_version
from utils.report_generator import generate_study_report
from utils.security import get_current_user
from utils.studies import MAX_SLICES, MIN_SLICES, combine_slices
from utils.views import DETAIL_PROJECTION, study_view

# Create Router
router = APIRouter(prefix="/api/studies", tags=["Multi-slice studies"])


def _get_study(study_id: str) -> tuple[dict, list[dict]]:
    study = get_studies_collection().find_one({"id": study_id})
    if study is None:
        raise HTTPException(status_code=404, detail="Study not found")
    slices = list(get_scans_collection().find({"study_id": study_id}, DETAIL_PROJECTION).sort("slice_index", 1))
    return study, slices


# --- Routes ---

@router.post("/classify", status_code=status.HTTP_201_CREATED)
async def classify_study(
    files: list[UploadFile] = File(...),
    patient_id: str = Form(...),
    scan_date: str = Form(""),
    sequence: str = Form(""),
    notes: str = Form(""),
    user: dict = Depends(get_current_user),
):
    """Classifies several 2D slices from the same MRI scan together. Each slice is classified and stored as a normal
    scan; the study combines them (average probabilities) and is flagged when the slices disagree."""
    require_patient(patient_id)
    if not MIN_SLICES <= len(files) <= MAX_SLICES:
        raise HTTPException(status_code=400, detail=f"Upload between {MIN_SLICES} and {MAX_SLICES} slices of the same scan")
    images = [await read_upload(f) for f in files]          # check every file before classifying any of them

    study_id = next_id("ST-" + now_utc().strftime("%Y"))
    logger.info(f"Study {study_id}: {len(images)} slices for patient {patient_id}")
    slices = []
    for index, image in enumerate(images, start=1):
        slices.append(await classify_and_store(image, patient_id, user, scan_date, sequence, notes,
                                               study_id=study_id, slice_index=index))

    study = {
        "id": study_id,
        "patient_id": patient_id,
        "created_at": now_utc(),
        "created_by": str(user["_id"]),
        "scan_date": scan_date,
        "sequence": sequence,
        "notes": notes,
        "scan_ids": [s["id"] for s in slices],
        "model_version": model_version(),
        **combine_slices(slices),
    }
    get_studies_collection().insert_one(study)
    logger.info(f"Study {study_id}: {study['prediction']} ({study['confidence']:.3f}), slices agree {study['slice_agreement']}")
    return study_view(study, slices)


@router.get("/{study_id}")
async def get_study(study_id: str, user: dict = Depends(get_current_user)):
    return study_view(*_get_study(study_id))


@router.post("/{study_id}/review")
async def mark_study_reviewed(study_id: str, user: dict = Depends(get_current_user)):
    """Confirms the study's combined result. All its slices come from one scan, so every slice is confirmed with the
    combined class and joins the similar-case search space."""
    study, _ = _get_study(study_id)
    reviewed = {"status": "Reviewed", "reviewed_by": str(user["_id"]), "reviewed_at": now_utc()}
    get_studies_collection().update_one({"id": study_id}, {"$set": reviewed})
    get_scans_collection().update_many({"study_id": study_id}, {"$set": {**reviewed, "label": study["prediction"]}})
    return study_view(*_get_study(study_id))


@router.get("/{study_id}/report")
async def download_study_report(study_id: str, user: dict = Depends(get_current_user)):
    """Generates the study's report (DOCX) on demand: combined result, per-slice table, slices and heatmaps."""
    study, slices = _get_study(study_id)

    def load():
        out = []
        for scan in slices:
            image, heatmap = image_bytes(scan, "image"), image_bytes(scan, "gradcam")
            out.append((scan, io.BytesIO(image) if image else None, io.BytesIO(heatmap) if heatmap else None))
        return out

    report = await run_in_threadpool(lambda: generate_study_report(study, load()))
    headers = {"Content-Disposition": f'attachment; filename="NeuroLens_{study_id}.docx"'}
    return StreamingResponse(report, headers=headers,
                             media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
