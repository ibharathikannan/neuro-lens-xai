import numpy as np
import tensorflow as tf
from matplotlib import colormaps
from PIL import Image

from utils.logger import logger


def find_last_conv_layer(model):
    """
    Returns the name of the last convolutional layer to explain.
    - Fibonacci-Net / custom CNN: the last DepthwiseSeparableConv or Conv2D layer of the model.
    - Pretrained models (MobileNetV2, EfficientNetB0, Xception): the backbone is a nested model;
      its name is returned and the heatmap is taken from the backbone's output feature map.
    """
    for layer in reversed(model.layers):
        if isinstance(layer, tf.keras.Model):              # nested pretrained backbone
            return layer.name
        if "depthwise_separable_conv" in layer.name or isinstance(layer, tf.keras.layers.Conv2D):
            return layer.name
    return None


def make_gradcam_heatmap(img_array, model, last_conv_layer_name, pred_index=None):
    """
    Generates a Grad-CAM heatmap (values 0-1) for the predicted class, or for `pred_index` if given.
    """
    target = model.get_layer(last_conv_layer_name)

    with tf.GradientTape() as tape:
        if isinstance(target, tf.keras.Model):
            # Pretrained model: input -> rescaling -> backbone -> head is a simple chain, so run the layers
            # one by one and keep the backbone's output (a nested model's .output is not usable here).
            x = tf.convert_to_tensor(img_array)
            last_conv_layer_output = None
            for layer in model.layers:
                if isinstance(layer, tf.keras.layers.InputLayer):
                    continue
                x = layer(x, training=False)
                if layer is target:
                    last_conv_layer_output = x
            preds = x
        else:
            # Fibonacci-Net / custom CNN: the conv layer lives in the model's own graph
            try:
                grad_model = tf.keras.models.Model(model.input, [target.output, model.output])
            except Exception as e:
                logger.error(f"Error creating Grad-CAM model: {e}")
                return None
            last_conv_layer_output, preds = grad_model(img_array)

        if isinstance(preds, list):
            preds = preds[0]
        if pred_index is None:
            pred_index = tf.argmax(preds[0])
        class_channel = preds[:, pred_index]

    # Gradient of the class score with respect to each feature map, averaged per channel
    grads = tape.gradient(class_channel, last_conv_layer_output)
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))

    # Weighted sum of the feature maps
    heatmap = last_conv_layer_output[0] @ pooled_grads[..., tf.newaxis]
    heatmap = tf.squeeze(heatmap)

    # Keep positive evidence only and normalise to 0-1
    heatmap = tf.maximum(heatmap, 0)
    max_value = tf.math.reduce_max(heatmap)
    if float(max_value) == 0.0:
        return np.zeros(heatmap.shape, dtype="float32")
    return (heatmap / max_value).numpy()


def overlay_heatmap(img, heatmap, alpha=0.4):
    """
    Superimposes a Grad-CAM heatmap (jet colours) on the original image and returns a PIL image.
    img: PIL Image or numpy array (0-255); heatmap: numpy array with values 0-1.
    """
    if not isinstance(img, Image.Image):
        img = Image.fromarray(np.uint8(img))
    img = np.asarray(img.convert("RGB"), dtype="float32")

    jet = colormaps["jet"](np.arange(256))[:, :3]                  # 256 x 3 RGB lookup table
    colored = jet[np.uint8(255 * np.clip(heatmap, 0, 1))]            # h x w x 3, values 0-1
    colored = Image.fromarray(np.uint8(colored * 255)).resize((img.shape[1], img.shape[0]), Image.BILINEAR)

    superimposed = np.asarray(colored, dtype="float32") * alpha + img
    superimposed = np.clip(superimposed / superimposed.max() * 255, 0, 255)
    return Image.fromarray(np.uint8(superimposed))
