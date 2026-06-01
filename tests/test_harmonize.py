"""Tests for anim.harmonize."""

from __future__ import annotations

import cv2
import numpy as np

from anim.harmonize import harmonize, pick_mode


def test_pick_mode_vertical():
    assert pick_mode(400, 800, "auto") == "dominant_color"


def test_pick_mode_wide_16_9():
    assert pick_mode(1920, 1080, "auto") == "smart_crop"


def test_harmonize_output_size():
    img = np.zeros((600, 400, 3), dtype=np.uint8)
    img[100:500, 50:350] = (0, 128, 255)
    out = harmonize(img, 1920, 1080, mode="blurred_pillarbox")
    assert out.shape == (1080, 1920, 3)


def test_smart_crop_exact_ar():
    img = np.random.randint(0, 255, (900, 1600, 3), dtype=np.uint8)
    out = harmonize(img, 1920, 1080, mode="smart_crop")
    assert out.shape == (1080, 1920, 3)
