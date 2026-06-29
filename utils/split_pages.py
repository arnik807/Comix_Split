"""List comic pages from folder, archive, or single image (Split batch UI)."""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path
from typing import List

from utils.io_helpers import SUPPORTED_IMAGE_EXTS
from utils.path_resolve import ROOT, resolve_dir_path, resolve_file_path


def _is_image_path(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_IMAGE_EXTS


def _cache_dir_for_archive(archive: Path) -> Path:
    digest = hashlib.sha1(str(archive.resolve()).encode("utf-8")).hexdigest()[:12]
    return ROOT / "story_out" / ".split_cache" / f"{archive.stem}_{digest}"


def _extract_archive_pages(archive: Path) -> Path:
    cache = _cache_dir_for_archive(archive)
    marker = cache / ".extracted"
    if marker.is_file():
        return cache
    if cache.exists():
        shutil.rmtree(cache, ignore_errors=True)
    cache.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "r") as zf:
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            if info.is_dir():
                continue
            if Path(info.filename).suffix.lower() not in SUPPORTED_IMAGE_EXTS:
                continue
            target = cache / Path(info.filename).name
            if target.exists():
                stem = Path(info.filename).stem
                ext = Path(info.filename).suffix
                n = 2
                while target.exists():
                    target = cache / f"{stem}_{n}{ext}"
                    n += 1
            with zf.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())
    marker.write_text("ok", encoding="utf-8")
    return cache


def list_split_pages(source_path: str) -> dict:
    """
    Return page file paths for Split navigation.
    pages: list of absolute path strings usable as image_path in /api/process.
    """
    raw = (source_path or "").strip()
    if not raw:
        raise ValueError("source_path is required")

    p = Path(raw)
    try:
        if p.is_dir() or (not p.is_file() and (ROOT / raw).is_dir()):
            folder = resolve_dir_path(raw, ROOT)
            pages = sorted(
                str(f.resolve())
                for f in folder.iterdir()
                if f.is_file() and _is_image_path(f)
            )
            if not pages:
                raise FileNotFoundError(f"Нет изображений в папке: {raw}")
            return {
                "pages": pages,
                "resolved_path": str(folder.resolve()),
                "source_kind": "folder",
            }
    except OSError:
        pass

    try:
        file_path = resolve_file_path(raw, ROOT)
    except OSError as exc:
        raise FileNotFoundError(str(exc)) from exc

    ext = file_path.suffix.lower()
    if ext in SUPPORTED_IMAGE_EXTS:
        return {
            "pages": [str(file_path.resolve())],
            "resolved_path": str(file_path.resolve()),
            "source_kind": "file",
        }
    if ext in {".cbz", ".zip"}:
        cache = _extract_archive_pages(file_path)
        pages = sorted(
            str(f.resolve())
            for f in cache.iterdir()
            if f.is_file() and _is_image_path(f)
        )
        if not pages:
            raise FileNotFoundError(f"Нет изображений в архиве: {raw}")
        return {
            "pages": pages,
            "resolved_path": str(file_path.resolve()),
            "source_kind": "archive",
            "cache_dir": str(cache.resolve()),
        }
    raise ValueError(f"Неподдерживаемый источник: {raw}")
