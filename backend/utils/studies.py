"""Multi-slice studies: several 2D slices from the same MRI scan, classified together.

The model still classifies one 2D slice at a time. A study combines the per-slice results: the class
probabilities are averaged, the combined prediction is the class with the highest average, and the study is
flagged for review when any slice disagrees or the average confidence is low. The model does not see the
scan in 3D — combining is done after classification.
"""
from utils.config import CLASS_LABELS

MIN_SLICES, MAX_SLICES = 2, 10
LOW_CONFIDENCE = 0.7


def combine_slices(slices: list[dict]) -> dict:
    """slices: scan records with "prediction" and "probabilities". Returns the study's combined result."""
    if not slices:
        raise ValueError("A study needs at least one slice")
    classes = list(slices[0]["probabilities"])
    n = len(slices)
    probabilities = {c: sum(s["probabilities"].get(c, 0.0) for s in slices) / n for c in classes}
    prediction = max(probabilities, key=probabilities.get)
    confidence = probabilities[prediction]
    agreeing = sum(1 for s in slices if s["prediction"] == prediction)
    flagged = agreeing < n or confidence < LOW_CONFIDENCE
    return {
        "prediction": prediction,
        "confidence": confidence,
        "probabilities": probabilities,
        "slice_count": n,
        "slice_agreement": f"{agreeing} / {n}",
        "status": "Flagged" if flagged else "Awaiting review",
        "explanation": study_explanation(slices, prediction, confidence, agreeing),
    }


def study_explanation(slices: list[dict], prediction: str, confidence: float, agreeing: int) -> str:
    label = CLASS_LABELS.get(prediction, prediction)
    n = len(slices)
    parts = [f"Combined result of {n} slices: {label}, with an average confidence of {confidence * 100:.1f}%."]
    if agreeing == n:
        parts.append(f"All {n} slices predict {label}.")
    else:
        others = sorted({CLASS_LABELS.get(s["prediction"], s["prediction"]) for s in slices if s["prediction"] != prediction})
        parts.append(f"{agreeing} of {n} slices predict {label}; the others predict {', '.join(others)}. "
                     "The slices disagree, so this study is flagged for careful review.")
    if confidence < LOW_CONFIDENCE:
        parts.append("The average confidence is below 70%, so the result should be reviewed with particular care.")
    parts.append("Each slice is classified on its own and the results are averaged; the model does not analyse the scan in 3D.")
    return " ".join(parts)
