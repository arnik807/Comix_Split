"""OpenCV preprocessing for comic bubble OCR crops."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np

ContrastMode = Literal["none", "clahe"]
InvertMode = Literal["never", "auto", "always"]


@dataclass(frozen=True)
class OcrPreprocessConfig:
    enabled: bool = True
    upscale_factor: int = 3
    contrast: ContrastMode = "clahe"
    invert: InvertMode = "auto"
    dark_background_threshold: int = 128


def preprocess_bubble_crop(
    crop_bgr: np.ndarray,
    cfg: OcrPreprocessConfig,
) -> np.ndarray:
    """Upscale + mild contrast + optional invert for OCR input."""
    if crop_bgr is None or crop_bgr.size == 0:
        return crop_bgr

    img = crop_bgr
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    factor = max(1, int(cfg.upscale_factor))
    if cfg.enabled and factor > 1:
        h, w = img.shape[:2]
        img = cv2.resize(
            img,
            (max(1, w * factor), max(1, h * factor)),
            interpolation=cv2.INTER_CUBIC,
        )

    if cfg.enabled and cfg.contrast == "clahe":
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l_ch, a_ch, b_ch = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_ch = clahe.apply(l_ch)
        img = cv2.cvtColor(cv2.merge([l_ch, a_ch, b_ch]), cv2.COLOR_LAB2BGR)

    if cfg.enabled and cfg.invert != "never":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if cfg.invert == "always" or float(gray.mean()) < float(cfg.dark_background_threshold):
            img = cv2.bitwise_not(img)

    return img
