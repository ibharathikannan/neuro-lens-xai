"""Custom Fibonacci-Net layers (Roy et al. 2025, arXiv:2503.13928).

These must stay IDENTICAL to the definitions in research/BRAIN_TUMOR_CLASSIFICATION.ipynb:
a saved Fibonacci-Net model can only be loaded if the same classes (same names, same config keys)
are registered before tf.keras.models.load_model() is called. Pretrained models (MobileNetV2,
EfficientNetB0, Xception) need nothing from this file.
"""
import tensorflow as tf
from tensorflow.keras import layers


# -------- Avg2Max Pooling --------
@tf.keras.utils.register_keras_serializable()
class Avg2MaxPooling(layers.Layer):
    """Avg-2Max pooling: AveragePooling(x) - 2 * MaxPooling(x)."""
    def __init__(self, pool_size=3, strides=2, padding="same", **kwargs):
        super().__init__(**kwargs)
        self.pool_size, self.strides, self.padding = pool_size, strides, padding
        self.avg_pool = layers.AveragePooling2D(pool_size, strides, padding)
        self.max_pool = layers.MaxPooling2D(pool_size, strides, padding)

    def call(self, inputs):
        return self.avg_pool(inputs) - (self.max_pool(inputs) + self.max_pool(inputs))

    def get_config(self):
        config = super().get_config()
        config.update({"pool_size": self.pool_size, "strides": self.strides, "padding": self.padding})
        return config


# -------- Depthwise Separable Conv --------
@tf.keras.utils.register_keras_serializable()
class DepthwiseSeparableConv(layers.Layer):
    """Depth-wise separable convolution + BatchNorm + ReLU."""
    def __init__(self, filters, kernel_size=3, strides=1, **kwargs):
        super().__init__(**kwargs)
        self.filters, self.kernel_size, self.strides = filters, kernel_size, strides

    def build(self, input_shape):
        self.dw = layers.DepthwiseConv2D(self.kernel_size, self.strides, padding="same")
        self.pw = layers.Conv2D(self.filters, 1, strides=1)
        self.bn = layers.BatchNormalization()
        super().build(input_shape)

    def call(self, inputs):
        return tf.nn.relu(self.bn(self.pw(self.dw(inputs))))

    def get_config(self):
        config = super().get_config()
        config.update({"filters": self.filters, "kernel_size": self.kernel_size, "strides": self.strides})
        return config


CUSTOM_OBJECTS = {
    "Avg2MaxPooling": Avg2MaxPooling,
    "DepthwiseSeparableConv": DepthwiseSeparableConv,
}
