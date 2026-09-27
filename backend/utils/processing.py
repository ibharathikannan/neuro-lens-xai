import numpy as np
from PIL import Image

from utils.config import IMG_SIZE
from utils.logger import logger


def preprocess_image(image: Image.Image) -> np.ndarray:
    """
    Prepares an uploaded MRI slice exactly like the validation/test images in the training notebook:
    1. Convert to RGB (grey MRI values are copied into all three channels).
    2. Resize to IMG_SIZE (224 x 224).
    3. Scale pixel values to [0, 1].
    4. Add a batch dimension -> shape (1, 224, 224, 3).

    Any backbone-specific scaling (e.g. [-1, 1] for MobileNetV2) is built into the saved model itself,
    so every model takes this same input.
    """
    logger.info(f"Preprocessing image of size: {image.size} and mode: {image.mode}")
    if image.mode != "RGB":
        image = image.convert("RGB")

    image = image.resize(IMG_SIZE)
    img_array = np.asarray(image, dtype="float32") / 255.0
    return np.expand_dims(img_array, axis=0)
