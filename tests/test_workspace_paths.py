"""Tests for workspace project layout and API helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from story_analyzer import paths
from utils.split_pages import list_split_pages
from utils.workspace_paths import layout_for_project, resolve_project_name


def test_ensure_project_layout_creates_subdirs(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STORY_PROJECTS_ROOT", tmp_path / "projects")
    base = paths.ensure_project_layout("Test_Project")
    assert base.is_dir()
    assert paths.panels_dir("Test_Project").is_dir()
    assert paths.upscale_dir("Test_Project").is_dir()
    assert paths.video_dir("Test_Project").is_dir()


def test_panels_dir_is_source_no_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STORY_PROJECTS_ROOT", tmp_path / "projects")
    src = paths.panels_dir("demo")
    src.mkdir(parents=True)
    assert paths.panels_dir_is_source(src, "demo") is True
    assert paths.should_sync_panels(src, "demo") is False


def test_layout_payload_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STORY_PROJECTS_ROOT", tmp_path / "projects")
    payload = layout_for_project("my_comic")
    assert payload["project"] == "my_comic"
    assert payload["panels"].endswith("panels")
    assert payload["stage_2a_json"].endswith("stage_2a.json")


def test_list_split_pages_folder(tmp_path):
    import cv2
    import numpy as np

    folder = tmp_path / "pages"
    folder.mkdir()
    img = np.zeros((8, 8, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    for name in ("001_a.png", "002_b.png"):
        buf.tofile(str(folder / name))
    result = list_split_pages(str(folder))
    assert len(result["pages"]) == 2
    assert result["source_kind"] == "folder"


def test_resolve_project_name_empty():
    assert resolve_project_name("") is None
    assert resolve_project_name("  ") is None


def test_list_workspace_projects(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STORY_PROJECTS_ROOT", tmp_path / "projects")
    root = paths.STORY_PROJECTS_ROOT
    root.mkdir(parents=True)
    (root / "alpha").mkdir()
    (root / "beta").mkdir()
    assert paths.list_workspace_projects() == ["alpha", "beta"]
