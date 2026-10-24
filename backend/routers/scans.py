import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from PIL import Image, UnidentifiedImageError

from utils import similarity
from utils.blob_storage import image_bytes, image_fields
from utils.config import SIMILAR_K
from utils.database import get_patients_collection, get_reference_collection, get_scans_collection, next_id, now_utc
from utils.logger import logger
from utils.model_service import classify, embedding_key, model_version
from utils.report_generator import generate_docx_report
from utils.security import get_current_user
from utils.views import case_view, explanation_for, scan_view, study_sizes

# Create Router
router = APIRouter(prefix="/api/scans", tags=["Scans"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
LOW_CONFIDENCE = 0.7


def _get_scan(scan_id: str) -> dict:
    scan = get_scans_collection().find_one({"id": scan_id})
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


def _with_embedding(scan: dict) -> dict:
    """Makes sure the scan has an embedding from the deployed model. Scans classified before similar-case
    search existed, or by an earlier model, are re-analysed once from their stored image."""
    if scan.get("embedding") and scan.get("embedding_model") == embedding_key():
        return scan
    data = image_bytes(scan, "image")
    if data is None:
        raise HTTPException(status_code=409, detail="This scan has no stored image to analyse")
    try:
        result = classify(Image.open(io.BytesIO(data)))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Model is not available yet: {e}")
    if result.get("embedding") is None:
        raise HTTPException(status_code=503, detail="The deployed model does not provide embeddings for similar-case search")
    update = {"embedding": result["embedding"], "embedding_model": embedding_key(),
              "heatmap": similarity.heatmap_grid(result.get("heatmap"))}
    get_scans_collection().update_one({"id": scan["id"]}, {"$set": update})
    return {**scan, **update}


def _find_case(case_id: str) -> tuple[dict, str]:
    """A comparison target: a reference-library case (REF-...) or a reviewed patient scan (S-...)."""
    if case_id.startswith("REF-"):
        doc, source = get_reference_collection().find_one({"id": case_id}), "reference"
    else:
        doc, source = get_scans_collection().find_one({"id": case_id}), "patient"
    if doc is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return doc, source


def _search(scan: dict, k: int) -> tuple[list, str]:
    return similarity.find_similar(scan["embedding"], embedding_key(), k, exclude_id=scan["id"])


def require_patient(patient_id: str) -> None:
    if get_patients_collection().find_one({"id": patient_id}) is None:
        raise HTTPException(status_code=404, detail="Patient not found")


async def read_upload(file: UploadFile) -> Image.Image:
    """Reads one uploaded MRI slice; rejects files over 10 MB and anything that is not an image."""
    name = f" ({file.filename})" if file.filename else ""
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Image is larger than 10 MB{name}")
    try:
        image = Image.open(io.BytesIO(contents))
        image.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail=f"The file is not a valid image{name}")
    return image


async def classify_and_store(image: Image.Image, patient_id: str, user: dict, scan_date: str = "", sequence: str = "",
                             notes: str = "", study_id: str | None = None, slice_index: int | None = None) -> dict:
    """Classifies one slice, builds its heatmap and embedding, stores the images and saves the scan record.
    Used for single uploads and for every slice of a multi-slice study."""
    try:
        result = await run_in_threadpool(classify, image)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Model is not available yet: {e}")

    has_heatmap = result["gradcam"] is not None
    scan_id = next_id("S-" + now_utc().strftime("%Y"))

    # Evidence from similar confirmed cases (never blocks the classification itself)
    agreement = None
    if result.get("embedding"):
        try:
            hits, _ = await run_in_threadpool(similarity.find_similar, result["embedding"], embedding_key(), SIMILAR_K)
            agreement = similarity.agreement(result["prediction"], hits) if hits else None
        except Exception as e:
            logger.warning(f"Similar-case search failed: {e}")

    images = await run_in_threadpool(lambda: {
        **image_fields(image, f"scans/{scan_id}/image.jpg", "image"),
        **image_fields(result["gradcam"], f"scans/{scan_id}/gradcam.jpg", "gradcam"),
    })
    doc = {
        "id": scan_id,
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
        "explanation": explanation_for(result["prediction"], result["confidence"], has_heatmap, agreement),
        "similar_agreement": agreement,
        "embedding": result.get("embedding"),
        "embedding_model": embedding_key() if result.get("embedding") else None,
        "heatmap": similarity.heatmap_grid(result.get("heatmap")),
        **images,
    }
    if study_id:
        doc.update(study_id=study_id, slice_index=slice_index)
    get_scans_collection().insert_one(doc)
    logger.info(f"Scan {doc['id']}: {doc['prediction']} ({doc['confidence']:.3f})" + (f" · study {study_id}" if study_id else ""))
    return doc


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
    require_patient(patient_id)
    image = await read_upload(file)
    logger.info(f"Classify request for patient {patient_id} ({file.filename})")
    doc = await classify_and_store(image, patient_id, user, scan_date, sequence, notes)
    return scan_view(doc)


@router.get("/{scan_id}")
async def get_scan(scan_id: str, user: dict = Depends(get_current_user)):
    return scan_view(_get_scan(scan_id))


@router.post("/{scan_id}/review")
async def mark_reviewed(scan_id: str, user: dict = Depends(get_current_user)):
    scan = _get_scan(scan_id)
    # Once reviewed, the predicted class counts as confirmed and the scan joins the similar-case search space
    get_scans_collection().update_one({"id": scan_id}, {"$set": {
        "status": "Reviewed", "label": scan["prediction"], "reviewed_by": str(user["_id"]), "reviewed_at": now_utc()}})
    return scan_view(_get_scan(scan_id))


@router.get("/{scan_id}/report")
async def download_report(scan_id: str, user: dict = Depends(get_current_user)):
    """Generates the scan's report (DOCX) on demand."""
    scan = _get_scan(scan_id)
    image_data, gradcam_data = await run_in_threadpool(lambda: (image_bytes(scan, "image"), image_bytes(scan, "gradcam")))
    image = io.BytesIO(image_data) if image_data else None
    gradcam = io.BytesIO(gradcam_data) if gradcam_data else None
    report = await run_in_threadpool(
        generate_docx_report, image, scan["prediction"], scan["probabilities"], scan["patient_id"], scan["id"],
        scan.get("model_version", ""), gradcam, None, scan.get("study_id"), scan.get("slice_index"),
        study_sizes([scan]).get(scan.get("study_id")))
    headers = {"Content-Disposition": f'attachment; filename="NeuroLens_{scan["id"]}.docx"'}
    return StreamingResponse(report, headers=headers,
                             media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@router.get("/{scan_id}/similar")
async def similar_cases(scan_id: str, k: int = SIMILAR_K, user: dict = Depends(get_current_user)):
    """The k confirmed cases whose embeddings are closest to this scan's (cosine similarity)."""
    k = max(1, min(k, 20))
    scan = await run_in_threadpool(_with_embedding, _get_scan(scan_id))
    hits, method = await run_in_threadpool(_search, scan, k)
    n_reference, n_patient = await run_in_threadpool(similarity.search_space, embedding_key())
    sizes = study_sizes([h["doc"] for h in hits])
    cases = [case_view(h["doc"], h["source"], h["similarity"], similarity.case_label(h["doc"], h["source"]), sizes) for h in hits]
    return {
        "query": scan_view(scan),
        "search_space": f"{n_reference:,} reference cases + {n_patient:,} reviewed patient scans",
        "method": method,
        "k": k,
        "agreement": similarity.agreement(scan["prediction"], hits) if hits else "0 / 0",
        "cases": cases,
    }


@router.get("/{scan_id}/compare/{case_id}")
async def compare_cases(scan_id: str, case_id: str, user: dict = Depends(get_current_user)):
    """Side-by-side comparison of a scan with one confirmed case: embedding similarity, heatmap overlap,
    focus region, class agreement, and template-based reasons built from those numbers."""
    scan = await run_in_threadpool(_with_embedding, _get_scan(scan_id))
    ref, source = _find_case(case_id)
    if source == "patient":
        ref = await run_in_threadpool(_with_embedding, ref)
    elif ref.get("embedding_model") != embedding_key():
        raise HTTPException(status_code=409, detail="This reference case was analysed with a different model — reload the reference library")

    sim = round(max(float(sum(a * b for a, b in zip(scan["embedding"], ref["embedding"]))), 0.0) * 100, 1)
    label = similarity.case_label(ref, source)
    heat = similarity.compare_heatmaps(scan.get("heatmap"), ref.get("heatmap"))
    source_text = ref.get("source_dataset", "reference library") if source == "reference" else "reviewed NeuroLens scan"
    return {
        "query": scan_view(scan),
        "reference": {**case_view(ref, source, sim / 100, label), "probabilities": ref.get("probabilities", {}),
                      "source_dataset": source_text},
        "similarity": sim,
        "same_class": scan["prediction"] == label,
        "heatmap_iou": heat["iou"],
        "focus_region": heat["region"],
        "focus_distance_px": heat["distance"],
        "lesion_extent": heat["extent"],
        "explanation": similarity.explain_comparison(sim, heat, scan, label, source_text),
    }
