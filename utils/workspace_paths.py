"""Resolve workspace project paths for API handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from story_analyzer.paths import (
    ensure_project_layout,
    panels_dir,
    project_layout_payload,
    resolve_video_input_dir,
    sanitize_project_name,
    upscale_dir,
    video_dir,
)
from utils.path_resolve import ROOT, resolve_dir_path


def resolve_project_name(raw: Optional[str]) -> Optional[str]:
    name = (raw or "").strip()
    if not name:
        return None
    return sanitize_project_name(name)


def layout_for_project(project_name: str) -> dict[str, str]:
    return project_layout_payload(project_name)


def resolve_upscale_dirs(
    project_name: Optional[str],
    panels_dir_raw: str,
    output_dir_raw: str,
) -> tuple[Path, Path]:
    if project_name:
        ensure_project_layout(project_name)
        return panels_dir(project_name), upscale_dir(project_name)
    return resolve_dir_path(panels_dir_raw, ROOT), resolve_dir_path(output_dir_raw, ROOT)


def resolve_video_dirs(
    project_name: Optional[str],
    panels_dir_raw: str,
    output_dir_raw: str,
) -> tuple[Path, Path]:
    if project_name:
        ensure_project_layout(project_name)
        return resolve_video_input_dir(project_name), video_dir(project_name)
    return resolve_dir_path(panels_dir_raw, ROOT), resolve_dir_path(output_dir_raw, ROOT)


def resolve_export_output_dir(
    project_name: Optional[str],
    output_dir_raw: str,
) -> Path:
    if project_name:
        ensure_project_layout(project_name)
        return panels_dir(project_name)
    return resolve_dir_path(output_dir_raw, ROOT)
