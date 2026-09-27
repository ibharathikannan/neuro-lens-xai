"""Loads the reference library for similar-case search.

Every image in a labelled dataset folder is classified by the deployed model (same settings as the API: .env,
Hugging Face model, Blob Storage, MongoDB). Its embedding, heatmap, image and confirmed label are stored in the
`reference_cases` collection, where the similar-case search finds them.

Folder layout — one sub-folder per class, named exactly like CLASS_NAMES:
    <data-dir>/glioma/*.jpg   <data-dir>/meningioma/*.jpg   <data-dir>/notumor/*.jpg   <data-dir>/pituitary/*.jpg

Run from the backend folder, e.g. with the Kaggle training images:
    python scripts/load_reference_library.py --data-dir "C:/data/brain-tumor-mri/Training" --per-class 250 \
        --source "Kaggle Brain Tumor MRI v1 (training split)"

Use the TRAINING split, never the test images used to report the model's accuracy.
Running it again skips images already loaded for the current model; --replace removes this model's
existing reference cases first. After switching to a new model, run it again: cases from the old model are
ignored by the search automatically.
"""
import argparse
import hashlib
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, UnidentifiedImageError  # noqa: E402

from utils.blob_storage import image_fields  # noqa: E402
from utils.config import CLASS_NAMES  # noqa: E402
from utils.database import ensure_indexes, get_reference_collection, next_id, now_utc  # noqa: E402
from utils.model_service import classify, embedding_key, load_model  # noqa: E402
from utils.similarity import heatmap_grid  # noqa: E402

IMAGE_TYPES = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")


def load_case(path: str, label: str, source: str, model_key: str, file_hash: str) -> dict:
    image = Image.open(path)
    image.load()
    result = classify(image)
    if result["embedding"] is None:
        raise RuntimeError("The model does not provide embeddings")
    case_id = next_id("REF", width=5)
    return {
        "id": case_id,
        "label": label,                               # confirmed label from the dataset
        "source_dataset": source,
        "file_name": os.path.basename(path),
        "file_md5": file_hash,
        "prediction": result["prediction"],
        "confidence": result["confidence"],
        "probabilities": result["probabilities"],
        "embedding": result["embedding"],
        "embedding_model": model_key,
        "heatmap": heatmap_grid(result["heatmap"]),
        "created_at": now_utc(),
        **image_fields(image, f"reference/{case_id}/image.jpg", "image"),
        **image_fields(result["gradcam"], f"reference/{case_id}/gradcam.jpg", "gradcam"),
    }


def main():
    parser = argparse.ArgumentParser(description="Load labelled images into the NeuroLens reference library")
    parser.add_argument("--data-dir", required=True, help="folder with one sub-folder per class")
    parser.add_argument("--per-class", type=int, default=250, help="images per class (random sample; 0 = all)")
    parser.add_argument("--source", default="Reference dataset", help="dataset name shown in the dashboard")
    parser.add_argument("--replace", action="store_true", help="remove this model's existing reference cases first")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if load_model() is None:
        sys.exit("The model could not be loaded — check HF_REPO_ID / HF_MODEL_FILENAME in .env")
    model_key = embedding_key()
    ensure_indexes()
    collection = get_reference_collection()
    print(f"Model: {model_key}")

    if args.replace:
        removed = collection.delete_many({"embedding_model": model_key}).deleted_count
        print(f"Removed {removed} existing reference cases for this model")
    loaded_hashes = {d["file_md5"] for d in collection.find({"embedding_model": model_key}, {"file_md5": 1}) if "file_md5" in d}

    folders = {name: os.path.join(args.data_dir, name) for name in CLASS_NAMES}
    missing = [n for n, f in folders.items() if not os.path.isdir(f)]
    if missing:
        sys.exit(f"Missing class folders in {args.data_dir}: {', '.join(missing)} (expected: {', '.join(CLASS_NAMES)})")

    rng = random.Random(args.seed)
    total, start = 0, time.time()
    for label, folder in folders.items():
        files = sorted(f for f in os.listdir(folder) if f.lower().endswith(IMAGE_TYPES))
        rng.shuffle(files)
        if args.per_class:
            files = files[:args.per_class]
        added = skipped = failed = 0
        for name in files:
            path = os.path.join(folder, name)
            with open(path, "rb") as fh:
                file_hash = hashlib.md5(fh.read()).hexdigest()
            if file_hash in loaded_hashes:
                skipped += 1
                continue
            try:
                collection.insert_one(load_case(path, label, args.source, model_key, file_hash))
                loaded_hashes.add(file_hash)
                added += 1
            except (UnidentifiedImageError, OSError, RuntimeError) as e:
                failed += 1
                print(f"  skipped {name}: {e}")
            if added and added % 25 == 0:
                print(f"  {label}: {added}/{len(files)} ({time.time() - start:.0f} s)")
        total += added
        print(f"{label}: {added} added, {skipped} already loaded, {failed} failed")

    print(f"Done: {total} reference cases added in {time.time() - start:.0f} s — "
          f"{collection.count_documents({'embedding_model': model_key})} available for {model_key}")


if __name__ == "__main__":
    main()
