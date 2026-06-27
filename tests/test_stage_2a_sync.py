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


def test_resolve_panel_display_path_prefers_source_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STORY_PROJECTS_ROOT", tmp_path / "projects")

    source = tmp_path / "source"
    source.mkdir()
    proj = "mix_test"
    panels = paths.panels_dir(proj)
    panels.mkdir(parents=True)

    old = np.zeros((10, 10, 3), dtype=np.uint8)
    new = np.zeros((10, 10, 3), dtype=np.uint8)
    new[:] = (0, 0, 255)
    cv2.imwrite(str(panels / "001_panel.png"), old)
    cv2.imwrite(str(source / "001_panel.png"), new)

    from story_analyzer.schemas import Panel2a

    panel = Panel2a(panel_id="001_panel", image_path="panels/001_panel.png", bubbles=[])
    from_project = proc.resolve_panel_display_path(proj, panel)
    from_source = proc.resolve_panel_display_path(proj, panel, source_dir=source)
    assert from_project is not None
    assert from_source is not None
    assert from_project.resolve() == (panels / "001_panel.png").resolve()
    assert from_source.resolve() == (source / "001_panel.png").resolve()


def test_resolve_panel_display_path_source_only_no_stale_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STORY_PROJECTS_ROOT", tmp_path / "projects")

    source = tmp_path / "source"
    source.mkdir()
    proj = "stale_mix"
    panels = paths.panels_dir(proj)
    panels.mkdir(parents=True)

    stale = np.zeros((10, 10, 3), dtype=np.uint8)
    stale[:] = (255, 0, 0)
    cv2.imwrite(str(panels / "002_panel.png"), stale)

    from story_analyzer.schemas import Panel2a

    panel = Panel2a(panel_id="002_panel", image_path="panels/002_panel.png", bubbles=[])
    mixed = proc.resolve_panel_display_path(proj, panel, source_dir=source, source_only=False)
    strict = proc.resolve_panel_display_path(proj, panel, source_dir=source, source_only=True)
    assert mixed is not None
    assert mixed.resolve() == (panels / "002_panel.png").resolve()
    assert strict is None


def test_init_project_empty_bubbles(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STORY_PROJECTS_ROOT", tmp_path / "projects")

    source = tmp_path / "panels_in"
    source.mkdir()
    img = np.zeros((20, 30, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    buf.tofile(str(source / "001_panel.png"))

    doc = proc.init_project_from_panels_dir(source, "manual_proj")
    assert doc.project == "manual_proj"
    assert len(doc.panels) == 1
    assert doc.panels[0].bubbles == []


def test_ocr_panel_bubbles(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "STORY_PROJECTS_ROOT", tmp_path / "projects")

    proj = "ocr_panel_test"
    panels = paths.panels_dir(proj)
    panels.mkdir(parents=True, exist_ok=True)
    img_path = panels / "001_panel.png"
    img = np.zeros((40, 60, 3), dtype=np.uint8)
    img[5:35, 5:55] = 255
    ok, buf = cv2.imencode(".png", img)
    assert ok
    buf.tofile(str(img_path))

    json_path = paths.stage_2a_json_path(proj)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        '{"project":"ocr_panel_test","panels":[{"panel_id":"001_panel",'
        '"image_path":"panels/001_panel.png","bubbles":[{"bubble_id":"001_panel_b1",'
        '"bbox":[10,5,50,30],"raw_text":"","corrected_text":"","type":"speech","reading_order":1}]}]}',
        encoding="utf-8",
    )

    def fake_ocr(crop, cfg):
        return "HELLO", 2.0, "siliconflow"

    monkeypatch.setattr(proc, "ocr_bubble_crop", fake_ocr)

    panel, count, ocr_ms, eng = proc.ocr_panel_bubbles(proj, "001_panel")
    assert count == 1
    assert panel.bubbles[0].raw_text == "HELLO"
    assert eng == "siliconflow"
    assert ocr_ms >= 2.0


def test_bbox_iou():
    from story_analyzer.stages.stage_2a_processor import _bbox_iou

    a = [0, 0, 10, 10]
    b = [5, 5, 15, 15]
    assert _bbox_iou(a, b) > 0.1
    assert _bbox_iou(a, [20, 20, 30, 30]) == 0.0
