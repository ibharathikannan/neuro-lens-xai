"""Similar-case search and case comparison.

Every classified scan and every reference case stores an embedding: the feature vector the classifier's final
layer receives, scaled to unit length. Similar cases are the nearest embeddings by cosine similarity.

Search space
- reference_cases: confirmed cases from a labelled dataset (loaded with scripts/load_reference_library.py)
- scans: patient scans a clinician has marked as reviewed (their predicted class counts as confirmed)
Only embeddings produced by the currently deployed model are compared.

MongoDB Atlas Vector Search is used when the cluster supports it; otherwise (local MongoDB, tests, or while
the Atlas index is still building) an exact cosine search runs inside the API — same results, just slower
for very large libraries.
"""
import numpy as np
from PIL import Image

from utils.config import CLASS_LABELS, IMG_SIZE, USE_ATLAS_VECTOR_SEARCH
from utils.database import get_reference_collection, get_scans_collection
from utils.logger import logger

VECTOR_INDEX = "embedding_index"
HEATMAP_GRID = 28                   # heatmaps are stored as 28 x 28 grids for comparison
FOCUS_THRESHOLD = 0.5               # heatmap values >= 50% of the maximum count as the model's focus region
NO_VECTORS = {"embedding": 0, "heatmap": 0, "image_jpeg": 0, "gradcam_jpeg": 0}


# --- Stored heatmaps ---

def heatmap_grid(heatmap) -> list | None:
    """Stores a 0-1 heatmap as a small grid (list of lists) so two cases can be compared later."""
    if heatmap is None:
        return None
    img = Image.fromarray(np.asarray(heatmap, dtype="float32")).resize((HEATMAP_GRID, HEATMAP_GRID), Image.BILINEAR)
    return np.clip(np.asarray(img), 0, 1).round(3).tolist()


# --- Atlas Vector Search index ---

def _index_definition(dims: int, with_status: bool) -> dict:
    fields = [{"type": "vector", "path": "embedding", "numDimensions": dims, "similarity": "cosine"},
              {"type": "filter", "path": "embedding_model"}]
    if with_status:
        fields.append({"type": "filter", "path": "status"})
    return {"fields": fields}


def ensure_vector_indexes(dims: int) -> None:
    """Creates (or resizes) the Atlas Vector Search indexes. Does nothing outside Atlas."""
    if not USE_ATLAS_VECTOR_SEARCH:
        return
    from pymongo.operations import SearchIndexModel
    for collection, with_status in ((get_reference_collection(), False), (get_scans_collection(), True)):
        definition = _index_definition(dims, with_status)
        try:
            db = collection.database
            if collection.name not in db.list_collection_names():
                db.create_collection(collection.name)
            existing = list(collection.list_search_indexes(VECTOR_INDEX))
            if not existing:
                collection.create_search_index(SearchIndexModel(definition=definition, name=VECTOR_INDEX, type="vectorSearch"))
                logger.info(f"Atlas Vector Search index requested for '{collection.name}' ({dims} dimensions)")
            elif existing[0].get("latestDefinition", {}).get("fields") != definition["fields"]:
                collection.update_search_index(VECTOR_INDEX, definition)
                logger.info(f"Atlas Vector Search index updated for '{collection.name}' ({dims} dimensions)")
        except Exception as e:
            logger.info(f"Atlas Vector Search not available for '{collection.name}' — exact search will be used ({e})")


def index_status() -> str:
    try:
        indexes = list(get_scans_collection().list_search_indexes(VECTOR_INDEX))
        return indexes[0].get("status", "unknown").capitalize() if indexes else "Not created"
    except Exception:
        return "Not available"


# --- Search ---

def _filters(model_key: str) -> list:
    return [
        ("reference", get_reference_collection(), {"embedding_model": model_key}),
        ("patient", get_scans_collection(), {"embedding_model": model_key, "status": "Reviewed"}),
    ]


def _vector_search(collection, embedding, query_filter, k) -> list:
    pipeline = [
        {"$vectorSearch": {"index": VECTOR_INDEX, "path": "embedding", "queryVector": embedding,
                           "numCandidates": max(100, 20 * k), "limit": k,
                           "filter": {f: {"$eq": v} for f, v in query_filter.items()}}},
        {"$addFields": {"_score": {"$meta": "vectorSearchScore"}}},
        {"$project": NO_VECTORS},
    ]
    # Atlas reports cosine as (1 + cos) / 2 — convert back to cosine similarity
    return [(2 * d.pop("_score") - 1, d) for d in collection.aggregate(pipeline)]


def _exact_search(collection, embedding, query_filter, k) -> list:
    docs = list(collection.find(query_filter, {"heatmap": 0, "image_jpeg": 0, "gradcam_jpeg": 0}))
    docs = [d for d in docs if len(d.get("embedding") or []) == len(embedding)]
    if not docs:
        return []
    sims = np.asarray([d.pop("embedding") for d in docs], dtype="float64") @ np.asarray(embedding, dtype="float64")
    return [(float(sims[i]), docs[i]) for i in np.argsort(-sims)[:k]]


def find_similar(embedding: list, model_key: str, k: int, exclude_id: str | None = None) -> tuple[list, str]:
    """Returns ([{similarity, source, doc}], method description) for the k nearest confirmed cases."""
    hits, exact_used = [], False
    for source, collection, query_filter in _filters(model_key):
        found = None
        if USE_ATLAS_VECTOR_SEARCH:
            try:
                found = _vector_search(collection, embedding, query_filter, k + 1)
                # An empty answer while matching cases exist means the index is still being built
                if not found and collection.count_documents(query_filter, limit=1):
                    found = None
            except Exception:
                found = None                  # not Atlas, or no index yet
        if found is None:
            found, exact_used = _exact_search(collection, embedding, query_filter, k + 1), True
        hits += [{"similarity": sim, "source": source, "doc": doc} for sim, doc in found if doc.get("id") != exclude_id]
    hits.sort(key=lambda h: h["similarity"], reverse=True)
    method = "Cosine similarity · " + ("exact search in the API" if exact_used else "MongoDB Atlas Vector Search")
    return hits[:k], method


def search_space(model_key: str) -> tuple[int, int]:
    """(reference cases, reviewed patient scans) available for the current model."""
    return tuple(collection.count_documents(query_filter) for _, collection, query_filter in _filters(model_key))


def case_label(doc: dict, source: str) -> str:
    return doc["label"] if source == "reference" else doc.get("label") or doc["prediction"]


def agreement(prediction: str, hits: list) -> str:
    same = sum(1 for h in hits if case_label(h["doc"], h["source"]) == prediction)
    return f"{same} / {len(hits)}"


# --- Comparison ---

def _focus(grid) -> dict:
    arr = np.asarray(grid if grid is not None else [[0.0]], dtype="float64")
    mask = arr >= FOCUS_THRESHOLD * arr.max() if arr.max() > 0 else np.zeros_like(arr, dtype=bool)
    if not mask.any():
        return {"mask": mask, "area": 0.0, "centre": None}
    ys, xs = np.nonzero(mask)
    weights = arr[mask]
    centre = (float(np.average(ys, weights=weights) + 0.5) / arr.shape[0],
              float(np.average(xs, weights=weights) + 0.5) / arr.shape[1])
    return {"mask": mask, "area": float(mask.mean()), "centre": centre}


def region_name(centre) -> str:
    if centre is None:
        return "No clear focus"
    row = ["Upper", "Middle", "Lower"][min(int(centre[0] * 3), 2)]
    col = ["left", "centre", "right"][min(int(centre[1] * 3), 2)]
    return "Centre" if (row, col) == ("Middle", "centre") else f"{row} {col}"


def compare_heatmaps(query_grid, reference_grid) -> dict:
    q, r = _focus(query_grid), _focus(reference_grid)
    same_shape = q["mask"].shape == r["mask"].shape
    union = (q["mask"] | r["mask"]).sum() if same_shape else 0
    iou = float((q["mask"] & r["mask"]).sum() / union) if union else 0.0
    if q["centre"] and r["centre"]:
        distance = int(round(np.hypot(q["centre"][0] - r["centre"][0], q["centre"][1] - r["centre"][1]) * IMG_SIZE[0]))
    else:
        distance = None
    if not q["area"] or not r["area"]:
        extent = "not comparable"
    else:
        ratio = q["area"] / r["area"]
        extent = "similar" if 0.67 <= ratio <= 1.5 else ("larger in query" if ratio > 1.5 else "smaller in query")
    return {"iou": round(iou, 2), "region": region_name(q["centre"]), "distance": distance, "extent": extent}


def explain_comparison(similarity: float, heat: dict, query: dict, ref_label: str, ref_source: str) -> list[str]:
    """Plain-language reasons built from the measured values with fixed templates (no free-text generation)."""
    q_label, r_label = CLASS_LABELS.get(query["prediction"], query["prediction"]), CLASS_LABELS.get(ref_label, ref_label)
    strength = "very similar" if similarity >= 90 else "similar" if similarity >= 75 else "only partly similar"
    lines = [f"The model represents both scans with {strength} internal features ({similarity:.1f}% embedding similarity)."]

    if heat["region"] == "No clear focus":
        lines.append("The query heatmap has no clear focus region, so the highlighted areas cannot be compared.")
    elif heat["iou"] >= 0.5:
        lines.append(f"In both scans the model focuses on the same area ({heat['region'].lower()} of the image; heatmap overlap {heat['iou']:.0%}).")
    elif heat["iou"] >= 0.2:
        lines.append(f"The model's focus areas partly overlap ({heat['iou']:.0%}); the query focus is in the {heat['region'].lower()} of the image.")
    else:
        apart = f", focus points {heat['distance']} px apart" if heat["distance"] is not None else ""
        lines.append(f"The model focuses on different areas in the two scans (overlap {heat['iou']:.0%}{apart}) — compare the images carefully.")

    if query["prediction"] == ref_label:
        lines.append(f"Both are {q_label}: the query is predicted {q_label} ({query['confidence'] * 100:.1f}%) "
                     f"and the reference is confirmed {r_label} ({ref_source}).")
    else:
        lines.append(f"The classes differ: the query is predicted {q_label} but the reference is confirmed {r_label} "
                     "— treat the prediction with extra care.")

    if heat["extent"] == "similar":
        lines.append("The highlighted regions have a similar size, suggesting findings of comparable extent.")
    elif heat["extent"] in ("larger in query", "smaller in query"):
        lines.append(f"The highlighted region is {heat['extent'].replace(' in query', '')} in the query scan than in the reference case.")
    return lines
