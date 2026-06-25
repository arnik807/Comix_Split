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
