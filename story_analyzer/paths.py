"""Project folder layout for Story Analyzer."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORY_PROJECTS_ROOT = ROOT / "story_out" / "projects"


def sanitize_project_name(name: str) -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", name.strip(), flags=re.UNICODE)
    if not cleaned:
        raise ValueError("Имя проекта не может быть пустым")
    return cleaned


def project_dir(project: str) -> Path:
    return STORY_PROJECTS_ROOT / sanitize_project_name(project)


def panels_dir(project: str) -> Path:
    return project_dir(project) / "panels"


def stage_2a_json_path(project: str) -> Path:
    return project_dir(project) / "stage_2a.json"


def upscale_dir(project: str) -> Path:
    return project_dir(project) / "upscale"


def video_dir(project: str) -> Path:
    return project_dir(project) / "video"


def ensure_project_layout(project: str) -> Path:
    """Create project folders (panels/, upscale/, video/) if missing."""
    base = project_dir(project)
    base.mkdir(parents=True, exist_ok=True)
    panels_dir(project).mkdir(parents=True, exist_ok=True)
    upscale_dir(project).mkdir(parents=True, exist_ok=True)
    video_dir(project).mkdir(parents=True, exist_ok=True)
    return base


def list_workspace_projects() -> list[str]:
    STORY_PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    names = [
        d.name
        for d in STORY_PROJECTS_ROOT.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ]
    return sorted(names, key=str.casefold)


def project_layout_payload(project: str) -> dict[str, str]:
    name = sanitize_project_name(project)
    base = ensure_project_layout(name)
    return {
        "project": name,
        "project_dir": str(base.resolve()),
        "panels": str(panels_dir(name).resolve()),
        "upscale": str(upscale_dir(name).resolve()),
        "video": str(video_dir(name).resolve()),
        "stage_2a_json": str(stage_2a_json_path(name).resolve()),
    }


def panels_dir_is_source(source_dir: Path, project: str) -> bool:
    try:
        return source_dir.resolve() == panels_dir(project).resolve()
    except OSError:
        return False


def upscale_dir_is_source(source_dir: Path, project: str) -> bool:
    try:
        return source_dir.resolve() == upscale_dir(project).resolve()
    except OSError:
        return False


def should_sync_panels(source_dir: Path, project: str, *, copy: bool | None = None) -> bool:
    """True → copy/sync PNG into project/panels; False → read in place."""
    if copy is not None:
        return bool(copy)
    return not panels_dir_is_source(source_dir, project)


def resolve_video_input_dir(project: str) -> Path:
    """Prefer upscale/ when it has images, else panels/."""
    from anim.io_utils import list_images

    up = upscale_dir(project)
    if up.is_dir() and list_images(up):
        return up
    return panels_dir(project)
