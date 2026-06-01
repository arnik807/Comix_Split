"""Simple OpenCV animation effects (no ML)."""

from __future__ import annotations

import math
from typing import List

import cv2
import numpy as np

from utils.anim_config import AnimationConfig, get_anim_config


def _frame_count(duration: float, fps: int) -> int:
    return max(1, int(round(duration * fps)))


def shake_frames(
    frame: np.ndarray,
    duration: float = 3.0,
    fps: int = 24,
    intensity: float = 0.3,
    cfg: AnimationConfig | None = None,
) -> List[np.ndarray]:
    cfg = cfg or get_anim_config().animation
    n = _frame_count(duration, fps)
    amp = max(1, int(5 + 15 * intensity))
    h, w = frame.shape[:2]
    rng = np.random.default_rng(42)
    frames: List[np.ndarray] = []
    for _ in range(n):
        dx = int(rng.integers(-amp, amp + 1))
        dy = int(rng.integers(-amp, amp + 1))
        m = np.float32([[1, 0, dx], [0, 1, dy]])
        frames.append(cv2.warpAffine(frame, m, (w, h), borderMode=cv2.BORDER_REPLICATE))
    return frames


def zoom_pulse_frames(
    frame: np.ndarray,
    duration: float = 3.0,
    fps: int = 24,
    intensity: float = 0.3,
    cfg: AnimationConfig | None = None,
) -> List[np.ndarray]:
    cfg = cfg or get_anim_config().animation
    n = _frame_count(duration, fps)
    max_zoom = 1.0 + 0.05 + 0.1 * intensity
    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2
    frames: List[np.ndarray] = []
    for i in range(n):
        t = i / max(n - 1, 1)
        scale = 1.0 + (max_zoom - 1.0) * math.sin(math.pi * t)
        m = cv2.getRotationMatrix2D((cx, cy), 0, scale)
        frames.append(cv2.warpAffine(frame, m, (w, h), borderMode=cv2.BORDER_REPLICATE))
    return frames


def static_frames(
    frame: np.ndarray,
    duration: float = 3.0,
    fps: int = 24,
) -> List[np.ndarray]:
    n = _frame_count(duration, fps)
    return [frame.copy() for _ in range(n)]


def animate_opencv(
    frame: np.ndarray,
    mode: str = "opencv_zoom",
    duration: float = 3.0,
    fps: int = 24,
    intensity: float = 0.3,
) -> List[np.ndarray]:
    if mode in ("opencv_shake", "shake"):
        return shake_frames(frame, duration, fps, intensity)
    if mode in ("opencv_zoom", "zoom", "zoom_pulse"):
        return zoom_pulse_frames(frame, duration, fps, intensity)
    if mode == "static":
        return static_frames(frame, duration, fps)
    raise ValueError(f"Unknown OpenCV animation mode: {mode}")
