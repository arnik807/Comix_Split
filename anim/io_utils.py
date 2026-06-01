"""Image I/O helpers for anim pipeline (Windows-safe paths)."""

from __future__ import annotations

from pathlib import Path
from typing import List

import cv2
import numpy as np

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def imread(path: str | Path) -> np.ndarray | None:
    p = Path(path)
    if not p.is_file():
        return None
    arr = np.fromfile(str(p), dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def imwrite(path: str | Path, img: np.ndarray) -> bool:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    ext = p.suffix.lower() or ".png"
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        return False
    buf.tofile(str(p))
    return True


def list_images(folder: str | Path) -> List[Path]:
    root = Path(folder)
    if not root.is_dir():
        return []
    files = [p for p in root.iterdir() if p.suffix.lower() in IMAGE_EXTS]
    return sorted(files, key=lambda p: p.name.lower())
