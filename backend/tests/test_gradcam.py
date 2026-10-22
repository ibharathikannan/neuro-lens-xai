"""Grad-CAM must not change the model. Needs TensorFlow, so it is skipped in CI (which installs without it).
Run from the backend folder:  pytest -q
"""
import os
import sys

import numpy as np
import pytest

tf = pytest.importorskip("tensorflow")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.gradcam import find_last_conv_layer, make_gradcam_heatmap  # noqa: E402


def test_gradcam_leaves_batchnorm_statistics_unchanged():
    # The saved Fibonacci-Net graph calls a Resizing layer with training=True. Calling such a model without
    # training=False switches the BatchNorm layers after it to training mode, so they update their running
    # statistics and every request shifts the predictions for the next one.
    inputs = tf.keras.Input((32, 32, 3))
    x = tf.keras.layers.Resizing(30, 30)(inputs, training=True)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Conv2D(4, 3)(x)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    model = tf.keras.Model(inputs, tf.keras.layers.Dense(2, activation="softmax")(x))
    image = np.random.default_rng(0).random((1, 32, 32, 3), dtype="float32")

    before = [w.numpy().copy() for w in model.weights]
    heatmap = make_gradcam_heatmap(image, model, find_last_conv_layer(model))

    assert heatmap is not None and heatmap.max() <= 1.0
    assert all(np.array_equal(a, w.numpy()) for a, w in zip(before, model.weights))
