"""Harmonize comic panels to 16:9 (1920x1080) using OpenCV."""

from __future__ import annotations

from typing import Literal

import cv2
import numpy as np

HarmonizeMode = Literal[
    "auto",
    "blurred_pillarbox",
    "dominant_color",
    "smart_crop",
]

TARGET_AR = 16 / 9


def pick_mode(width: int, height: int, mode: str = "auto") -> HarmonizeMode:
    if mode != "auto":
        return mode  # type: ignore[return-value]
    ar = width / max(height, 1)
    if abs(ar - TARGET_AR) < 0.2:
        return "smart_crop"
    if ar < 1.0:
        return "dominant_color"
    return "blurred_pillarbox"


def _fit_contain(img: np.ndarray, tw: int, th: int) -> tuple[np.ndarray, int, int, int, int]:
    h, w = img.shape[:2]
    scale = min(tw / w, th / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    x = (tw - nw) // 2
    y = (th - nh) // 2
    return resized, x, y, nw, nh


def _smart_crop(img: np.ndarray, tw: int, th: int) -> np.ndarray:
    h, w = img.shape[:2]
    target_ar = tw / th
    src_ar = w / h
    if src_ar > target_ar:
        new_w = int(h * target_ar)
        x0 = (w - new_w) // 2
        cropped = img[:, x0 : x0 + new_w]
    else:
        new_h = int(w / target_ar)
        y0 = (h - new_h) // 2
        cropped = img[y0 : y0 + new_h, :]
    return cv2.resize(cropped, (tw, th), interpolation=cv2.INTER_AREA)


def _dominant_color_bgr(img: np.ndarray, k: int = 3) -> tuple[int, int, int]:
    sample = img
    h, w = sample.shape[:2]
    if max(h, w) > 256:
        scale = 256 / max(h, w)
        sample = cv2.resize(
            sample,
            (max(1, int(w * scale)), max(1, int(h * scale))),
            interpolation=cv2.INTER_AREA,
        )
    pixels = sample.reshape(-1, 3).astype(np.float32)
    _criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _compact, labels, centers = cv2.kmeans(
        pixels, k, None, _criteria, 3, cv2.KMEANS_PP_CENTERS
    )
    counts = np.bincount(labels.flatten(), minlength=k)
    idx = int(np.argmax(counts))
    c = centers[idx]
    return int(c[0]), int(c[1]), int(c[2])


def harmonize(
    img: np.ndarray,
    target_width: int = 1920,
    target_height: int = 1080,
    mode: str = "auto",
    blur_sigma: int = 60,
    vignette_strength: float = 0.7,
) -> np.ndarray:
    """Return BGR image exactly target_width x target_height."""
    h, w = img.shape[:2]
    chosen = pick_mode(w, h, mode)

    if chosen == "smart_crop":
        return _smart_crop(img, target_width, target_height)

    if chosen == "dominant_color":
        bg = np.full((target_height, target_width, 3), _dominant_color_bgr(img), dtype=np.uint8)
        panel, x, y, nw, nh = _fit_contain(img, target_width, target_height)
        if vignette_strength > 0:
            mask = np.zeros((nh, nw), dtype=np.float32)
            cv2.ellipse(
                mask,
                (nw // 2, nh // 2),
                (max(1, nw // 2), max(1, nh // 2)),
                0,
                0,
                360,
                1.0,
                -1,
            )
            mask = cv2.GaussianBlur(mask, (0, 0), max(nw, nh) * 0.08)
            mask = np.clip(mask, 0, 1)[..., None]
            blend = panel.astype(np.float32) * (
                1 - vignette_strength + vignette_strength * mask
            )
            bg[y : y + nh, x : x + nw] = blend.astype(np.uint8)
        else:
            bg[y : y + nh, x : x + nw] = panel
        return bg

    # blurred_pillarbox (default)
    bg = cv2.resize(img, (target_width, target_height), interpolation=cv2.INTER_LINEAR)
    k = blur_sigma * 2 + 1
    bg = cv2.GaussianBlur(bg, (k, k), blur_sigma)
    panel, x, y, nw, nh = _fit_contain(img, target_width, target_height)
    out = bg.copy()
    out[y : y + nh, x : x + nw] = panel
    return out
