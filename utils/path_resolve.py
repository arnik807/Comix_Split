"""Resolve file paths on Windows (Cyrillic, mojibake, relative to project root)."""

from __future__ import annotations

import pathlib
from typing import List, Optional

ROOT = pathlib.Path(__file__).resolve().parent.parent


def path_variants(raw: str) -> List[str]:
    """Build candidate path strings (fix UTF-8 misread as latin-1/cp1252)."""
    raw = raw.strip().strip('"').strip("'")
    if not raw:
        return []

    variants: List[str] = [raw]
    for enc in ("latin-1", "cp1252", "cp1251"):
        try:
            fixed = raw.encode(enc).decode("utf-8")
            if fixed not in variants:
                variants.append(fixed)
        except (UnicodeDecodeError, UnicodeEncodeError):
            continue
    return variants


def resolve_file_path(
    raw: str,
    root: Optional[pathlib.Path] = None,
    *,
    must_exist: bool = True,
) -> pathlib.Path:
    """
    Resolve a local file path.

    - Tries raw path and mojibake fixes
    - Tries relative to project root (e.g. exam_imgs/page.jpg)
    """
    root = root or ROOT
    last = pathlib.Path(raw.strip())

    for candidate in path_variants(raw):
        for p in (pathlib.Path(candidate), root / candidate):
            try:
                resolved = p.resolve()
            except OSError:
                continue
            if not must_exist or resolved.is_file():
                return resolved
            # pathlib.is_file() can fail on some Unicode paths; try open
            try:
                with open(resolved, "rb"):
                    return resolved
            except OSError:
                continue

    if must_exist:
        return last.resolve() if last.is_absolute() else (root / last).resolve()
    return last


def resolve_dir_path(raw: str, root: Optional[pathlib.Path] = None) -> pathlib.Path:
    """Same as resolve_file_path but for output directories (may not exist yet)."""
    root = root or ROOT
    for candidate in path_variants(raw):
        for p in (pathlib.Path(candidate), root / candidate):
            try:
                return p.resolve()
            except OSError:
                continue
    p = pathlib.Path(raw.strip())
    return p.resolve() if p.is_absolute() else (root / p).resolve()
