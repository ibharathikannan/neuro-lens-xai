"""Converts MongoDB documents into the JSON shapes the Angular dashboard expects (see frontend/src/app/models.ts)."""
import base64
import io

from PIL import Image

from utils.config import CLASS_LABELS


def fmt_date(dt, with_time=False) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%d %b %Y, %H:%M" if with_time else "%d %b %Y")


def image_to_jpeg_b64(img: Image.Image, size: int = 320) -> str:
    """Small JPEG copy for storage in the scan record (moves to Azure Blob Storage later)."""
    img = img.convert("RGB")
    img.thumbnail((size, size))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def data_url(b64: str | None) -> str | None:
    return f"data:image/jpeg;base64,{b64}" if b64 else None


def status_of(scan) -> str:
    if scan is None:
        return "Awaiting review"
    return scan.get("status", "Awaiting review")


def explanation_for(prediction: str, confidence: float, has_heatmap: bool) -> str:
    label = CLASS_LABELS.get(prediction, prediction)
    parts = [f"The model predicts {label} with {confidence * 100:.1f}% confidence."]
    if has_heatmap:
        parts.append("The heatmap shows the regions that influenced the model most (red = strongest).")
    if confidence < 0.7:
        parts.append("Confidence is below 70%, so this result has been flagged for careful review.")
    parts.append("Similar-case evidence will appear here once the reference library is loaded.")
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
        "image_url": data_url(s.get("image_jpeg")) if with_images else None,
        "gradcam_url": data_url(s.get("gradcam_jpeg")) if with_images else None,
        "report_path": f"/api/scans/{s['id']}/report",
        "model_version": s.get("model_version", ""),
        "inference_seconds": s.get("inference_seconds", 0),
        "explanation": s.get("explanation", ""),
        "scan_date": s.get("scan_date"),
        "sequence": s.get("sequence"),
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
