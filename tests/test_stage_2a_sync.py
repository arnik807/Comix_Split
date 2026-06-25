"""Tests for Stage 2a panel sync and re-OCR helpers."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from story_analyzer import paths
from story_analyzer.stages import stage_2a_processor as proc
from story_analyzer.stages.stage_2a_processor import sync_panels_to_project


def test_sync_panels_replace_removes_stale_files(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STORY_PROJECTS_ROOT", tmp_path / "projects")

    project = "test_sync"
    source_a = tmp_path / "source_a"
    source_b = tmp_path / "source_b"
    source_a.mkdir()
    source_b.mkdir()
    (source_a / "001_panel.png").write_bytes(b"x")
    (source_a / "002_panel.png").write_bytes(b"x")
    (source_b / "003_panel.png").write_bytes(b"x")

    sync_panels_to_project(source_a, project, replace=True)
    dest = paths.panels_dir(project)
    assert sorted(p.name for p in dest.glob("*.png")) == ["001_panel.png", "002_panel.png"]

    sync_panels_to_project(source_b, project, replace=True)
    assert sorted(p.name for p in dest.glob("*.png")) == ["003_panel.png"]


def test_reocr_manual_bubble_bbox_and_image_path(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "STORY_PROJECTS_ROOT", tmp_path / "projects")

    proj = "reocr_test"
    panels = paths.panels_dir(proj)
    panels.mkdir(parents=True, exist_ok=True)
    img_path = panels / "001_panel.png"

    img = np.zeros((40, 60, 3), dtype=np.uint8)
    img[5:35, 5:55] = 255
    ok, buf = cv2.imencode(".png", img)
    assert ok
    buf.tofile(str(img_path))
    assert img_path.is_file()

    json_path = paths.stage_2a_json_path(proj)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        '{"project":"reocr_test","panels":[{"panel_id":"001_panel",'
        '"image_path":"panels/001_panel.png","bubbles":[]}]}',
        encoding="utf-8",
    )

    calls = []

    def fake_ocr(crop, cfg):
        calls.append(tuple(crop.shape))
        return "OK", 1.0, "siliconflow"

    monkeypatch.setattr(proc, "ocr_bubble_crop", fake_ocr)

    text, _ms, eng = proc.reocr_bubble(
        proj,
        "001_panel",
        "001_panel_b99",
        [10.4, 5.6, 50.9, 30.1],
        image_path="panels/001_panel.png",
    )
    assert text == "OK"
    assert eng == "siliconflow"
    assert calls


def test_reocr_uses_panel_abs_path(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "STORY_PROJECTS_ROOT", tmp_path / "projects")

    panels = tmp_path / "anywhere"
    panels.mkdir(parents=True, exist_ok=True)
    img_path = panels / "001_panel.png"

    img = np.zeros((40, 60, 3), dtype=np.uint8)
    img[5:35, 5:55] = 255
    ok, buf = cv2.imencode(".png", img)
    assert ok
    buf.tofile(str(img_path))

    calls = []

    def fake_ocr(crop, cfg):
        calls.append(tuple(crop.shape))
        return "ABS", 1.0, "siliconflow"

    monkeypatch.setattr(proc, "ocr_bubble_crop", fake_ocr)

    text, _ms, eng = proc.reocr_bubble(
        "missing_project",
        "001_panel",
        "001_panel_b1",
        [10, 5, 50, 30],
        panel_abs_path=str(img_path),
    )
    assert text == "ABS"
    assert eng == "siliconflow"
    assert calls
