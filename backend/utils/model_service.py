import os
import threading
import time
from datetime import datetime, timezone

import numpy as np
from PIL import Image

from utils.config import (REPO_ID, MODEL_FILENAME, HF_REVISION, HF_TOKEN, LOCAL_MODEL_PATH,
                          MODEL_DISPLAY_NAME, CLASS_NAMES)
from utils.logger import logger

# Global model state (loaded once, shared by all requests)
MODEL = None
MODEL_INFO = {"status": "not loaded", "source": None, "revision": None, "loaded_at": None, "error": None}
_lock = threading.Lock()


def load_model():
    """Loads the model from Hugging Face Hub (falls back to the local model_artifacts copy)."""
    global MODEL
    with _lock:
        if MODEL is not None:
            return MODEL
        import tensorflow as tf
        from utils.model_architecture import CUSTOM_OBJECTS   # registers the Fibonacci-Net layers

        MODEL_INFO.update(status="loading", error=None)
        path, source, revision = None, None, None
        try:
            from huggingface_hub import hf_hub_download, model_info
            logger.info(f"Downloading model {REPO_ID}/{MODEL_FILENAME} from Hugging Face...")
            path = hf_hub_download(repo_id=REPO_ID, filename=MODEL_FILENAME, revision=HF_REVISION, token=HF_TOKEN)
            source = f"Hugging Face Hub · {REPO_ID}"
            try:
                revision = (HF_REVISION or model_info(REPO_ID, token=HF_TOKEN).sha or "")[:7]
            except Exception:
                revision = HF_REVISION
        except Exception as e:
            logger.warning(f"Hugging Face download failed ({e}); trying local copy {LOCAL_MODEL_PATH}")
            if os.path.exists(LOCAL_MODEL_PATH):
                path, source = LOCAL_MODEL_PATH, f"Local file · {LOCAL_MODEL_PATH}"

        if path is None:
            MODEL_INFO.update(status="error", error="Model not found on Hugging Face or locally")
            logger.error(MODEL_INFO["error"])
            return None
        try:
            MODEL = tf.keras.models.load_model(path, custom_objects=CUSTOM_OBJECTS, compile=False)
        except Exception as e:
            MODEL_INFO.update(status="error", error=f"Model failed to load: {e}")
            logger.error(MODEL_INFO["error"])
            return None

        outputs = int(MODEL.output_shape[-1])
        expected = 1 if len(CLASS_NAMES) == 2 else len(CLASS_NAMES)
        if outputs not in (expected, len(CLASS_NAMES)):
            logger.warning(f"Model has {outputs} outputs but CLASS_NAMES has {len(CLASS_NAMES)} entries — check CLASS_NAMES")
        MODEL_INFO.update(status="ready", source=source, revision=revision,
                          loaded_at=datetime.now(timezone.utc).isoformat(), params=int(MODEL.count_params()),
                          outputs=outputs)
        logger.info(f"Model loaded ({source}, {MODEL.count_params():,} parameters, {outputs} outputs)")
        return MODEL


def load_model_in_background():
    threading.Thread(target=load_model, daemon=True).start()


def to_probabilities(raw: np.ndarray) -> dict:
    """Turns the model output into {class_name: probability}.
    One sigmoid output (binary model) -> [1 - p, p]; otherwise the softmax vector as is."""
    raw = np.asarray(raw, dtype="float64").ravel()
    if raw.size == 1 and len(CLASS_NAMES) == 2:
        p = float(raw[0])
        return {CLASS_NAMES[0]: 1.0 - p, CLASS_NAMES[1]: p}
    return {name: float(v) for name, v in zip(CLASS_NAMES, raw)}


def classify(image: Image.Image) -> dict:
    """Runs prediction + Grad-CAM for one image. Raises RuntimeError if the model is unavailable."""
    from utils.processing import preprocess_image
    from utils.gradcam import find_last_conv_layer, make_gradcam_heatmap, overlay_heatmap

    model = load_model()
    if model is None:
        raise RuntimeError(MODEL_INFO.get("error") or "Model not loaded")

    start = time.perf_counter()
    x = preprocess_image(image)
    probabilities = to_probabilities(model.predict(x, verbose=0)[0])
    prediction = max(probabilities, key=probabilities.get)

    overlay = None
    try:
        # For a single sigmoid output, explain that output (index 0) — it is the "positive" class score
        pred_index = 0 if model.output_shape[-1] == 1 else CLASS_NAMES.index(prediction)
        heatmap = make_gradcam_heatmap(x, model, find_last_conv_layer(model), pred_index=pred_index)
        if heatmap is not None:
            overlay = overlay_heatmap(image, heatmap)
    except Exception as e:
        logger.warning(f"Grad-CAM generation failed: {e}")

    return {
        "prediction": prediction,
        "confidence": probabilities[prediction],
        "probabilities": probabilities,
        "gradcam": overlay,
        "inference_seconds": round(time.perf_counter() - start, 2),
    }


def model_version() -> str:
    rev = MODEL_INFO.get("revision")
    return f"{MODEL_DISPLAY_NAME} · HF rev {rev}" if rev else MODEL_DISPLAY_NAME
