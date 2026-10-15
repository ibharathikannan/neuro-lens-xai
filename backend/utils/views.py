"""Converts MongoDB documents into the JSON shapes the Angular dashboard expects (see frontend/src/app/models.ts)."""
from utils.blob_storage import image_url
from utils.config import CLASS_LABELS

# Fields never sent in list views (large, or only used for similar-case search)
LIST_PROJECTION = {"image_jpeg": 0, "gradcam_jpeg": 0, "embedding": 0, "heatmap": 0}
DETAIL_PROJECTION = {"embedding": 0, "heatmap": 0}


def fmt_date(dt, with_time=False) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%d %b %Y, %H:%M" if with_time else "%d %b %Y")


def status_of(scan) -> str:
    if scan is None:
        return "Awaiting review"
    return scan.get("status", "Awaiting review")


def explanation_for(prediction: str, confidence: float, has_heatmap: bool, agreement: str | None = None) -> str:
    label = CLASS_LABELS.get(prediction, prediction)
    parts = [f"The model predicts {label} with {confidence * 100:.1f}% confidence."]
    if has_heatmap:
        parts.append("The heatmap shows the regions that influenced the model most (red = strongest).")
    if confidence < 0.7:
        parts.append("Confidence is below 70%, so this result has been flagged for careful review.")
    if agreement:
        same, total = (int(v) for v in agreement.split(" / "))
        if same * 2 > total:
            verdict = "consistent with the prediction."
        elif same * 2 == total:
            verdict = "the case evidence is mixed, so review carefully."
        else:
            verdict = "the case evidence does not support the prediction well."
        parts.append(f"{same} of the {total} most similar confirmed cases are {label} — {verdict}")
    else:
        parts.append("No confirmed cases are available yet for comparison.")
    return " ".join(parts)


def scan_view(s: dict, with_images: bool = True) -> dict:
    return {
        "id": s["id"],
        "patient_id": s["patient_id"],
        "date": fmt_date(s.get("created_at"), with_time=True),
        "prediction": s["prediction"],
        "confidence": s["confidence"],
        "probabilities": s["probabilities"],
        "status": s.get("status", "Awaiting review"),
        "image_url": image_url(s, "image") if with_images else None,
        "gradcam_url": image_url(s, "gradcam") if with_images else None,
        "report_path": f"/api/scans/{s['id']}/report",
        "model_version": s.get("model_version", ""),
        "inference_seconds": s.get("inference_seconds", 0),
        "explanation": s.get("explanation", ""),
        "scan_date": s.get("scan_date"),
        "sequence": s.get("sequence"),
        "similar_agreement": s.get("similar_agreement"),
        "study_id": s.get("study_id"),
        "slice_index": s.get("slice_index"),
    }


def study_view(study: dict, slices: list[dict]) -> dict:
    """A multi-slice study with its combined result and every slice (each slice is a normal scan)."""
    return {
        "id": study["id"],
        "patient_id": study["patient_id"],
        "date": fmt_date(study.get("created_at"), with_time=True),
        "scan_date": study.get("scan_date"),
        "sequence": study.get("sequence"),
        "prediction": study["prediction"],
        "confidence": study["confidence"],
        "probabilities": study["probabilities"],
        "slice_count": study.get("slice_count", len(slices)),
        "slice_agreement": study["slice_agreement"],
        "status": study.get("status", "Awaiting review"),
        "explanation": study.get("explanation", ""),
        "model_version": study.get("model_version", ""),
        "report_path": f"/api/studies/{study['id']}/report",
        "slices": [scan_view(s) for s in slices],
    }


def case_view(doc: dict, source: str, similarity: float, label: str) -> dict:
    """A reference case or reviewed patient scan in the similar-case list."""
    return {
        "case_id": doc["id"],
        "label": label,
        "similarity": round(max(similarity, 0.0) * 100, 1),
        "source": source,
        "patient_id": doc.get("patient_id") if source == "patient" else None,
        "image_url": image_url(doc, "image"),
        "gradcam_url": image_url(doc, "gradcam"),
    }


def patient_view(p: dict, scan_count: int, latest_scan: dict | None) -> dict:
    return {
        "id": p["id"],
        "age": p["age"],
        "sex": p["sex"],
        "registered": fmt_date(p.get("created_at")),
        "scans": scan_count,
        "last_scan": fmt_date(latest_scan["created_at"]) if latest_scan else "—",
        "last_result": latest_scan["prediction"] if latest_scan else None,
        "status": status_of(latest_scan),
        "referring_unit": p.get("referring_unit", ""),
        "notes": p.get("notes", ""),
    }
