import os
import zipfile
from pathlib import Path
from typing import List, Tuple

import numpy as np
import cv2

# Optional rar handling – requires `unrar` installed on the system.
try:
    import rarfile
except ImportError:  # pragma: no cover
    rarfile = None

SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}

def _load_image_bytes(data: bytes) -> np.ndarray:
    """Decode image bytes into a ``numpy.ndarray`` (BGR)."""
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img

def _iter_archive(zip_obj) -> List[Tuple[str, np.ndarray]]:
    """Iterate over supported images inside a zip/rar archive.

    Returns a list of tuples ``(filename, image_array)`` preserving the
    archive order (alphabetical)."""
    images = []
    for info in sorted(zip_obj.infolist(), key=lambda i: i.filename):
        ext = Path(info.filename).suffix.lower()
        if ext in SUPPORTED_IMAGE_EXTS:
            with zip_obj.open(info) as f:
                data = f.read()
                img = _load_image_bytes(data)
                images.append((info.filename, img))
    return images

def read_cbz(path: str) -> List[Tuple[str, np.ndarray]]:
    """Read a CBZ (ZIP) archive and return all supported images.

    ``path`` can be a ``str`` or ``Path``. The function raises ``FileNotFoundError``
    if the file does not exist or ``zipfile.BadZipFile`` for invalid archives.
    """
    with zipfile.ZipFile(path, "r") as zip_obj:
        return _iter_archive(zip_obj)

def read_cbr(path: str) -> List[Tuple[str, np.ndarray]]:
    """Read a CBR (RAR) archive and return all supported images.

    Requires the ``rarfile`` package and the external ``unrar`` utility to be
    available on the system. If ``rarfile`` is not importable, a ``RuntimeError``
    is raised.
    """
    if rarfile is None:
        raise RuntimeError("rarfile package is not installed; cannot read CBR files.")
    with rarfile.RarFile(path, "r") as r:
        images = []
        for info in sorted(r.infolist(), key=lambda i: i.filename):
            ext = Path(info.filename).suffix.lower()
            if ext in SUPPORTED_IMAGE_EXTS:
                data = r.read(info)
                img = _load_image_bytes(data)
                images.append((info.filename, img))
        return images

def read_folder(path: str) -> List[Tuple[str, np.ndarray]]:
    """Read all supported image files from a directory (non‑recursive)."""
    p = Path(path)
    if not p.is_dir():
        raise NotADirectoryError(f"{path} is not a directory")
    images = []
    for f in sorted(p.iterdir()):
        if f.suffix.lower() in SUPPORTED_IMAGE_EXTS and f.is_file():
            arr = np.fromfile(str(f), dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                continue
            images.append((f.name, img))
    return images

def load_single_image(path: str) -> List[Tuple[str, np.ndarray]]:
    """Load one image file from disk."""
    p = Path(path)
    arr = np.fromfile(str(p), dtype=np.uint8)
    if arr.size == 0:
        raise FileNotFoundError(path)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Cannot decode image: {path}")
    return [(p.name, img)]


def load_source(source_path: str) -> List[Tuple[str, np.ndarray]]:
    """Dispatch loader based on file extension.

    Returns a list of ``(relative_name, image)`` where ``relative_name`` is the
    filename inside the archive or the basename of a file on disk.
    """
    ext = Path(source_path).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}:
        return load_single_image(source_path)
    if ext in {".cbz", ".zip"}:
        return read_cbz(source_path)
    if ext == ".cbr":
        return read_cbr(source_path)
    if os.path.isdir(source_path):
        return read_folder(source_path)
    raise ValueError(f"Unsupported source type: {source_path}")
