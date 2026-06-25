"""Tests for Stage 2a schemas and I/O."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from story_analyzer.paths import sanitize_project_name
from story_analyzer.schemas import Bubble, BubbleType, Panel2a, Stage2aDocument
from story_analyzer.stages.stage_2a_processor import panel_id_from_filename, save_stage_2a


def test_sanitize_project_name():
    assert sanitize_project_name("asterix_01") == "asterix_01"
    assert sanitize_project_name("  test project  ") == "test_project"


def test_panel_id_from_filename():
    assert panel_id_from_filename("001_p001_panel.png") == "001_p001_panel"


def test_stage_2a_document_roundtrip(tmp_path, monkeypatch):
    import story_analyzer.paths as paths

    monkeypatch.setattr(paths, "STORY_PROJECTS_ROOT", tmp_path)

    doc = Stage2aDocument(
        project="demo",
        panels=[
            Panel2a(
                panel_id="001",
                image_path="panels/001.png",
                bubbles=[
                    Bubble(
                        bubble_id="001_b1",
                        bbox=[10, 20, 100, 80],
                        raw_text="Привет",
                        corrected_text="Привет!",
                        type=BubbleType.speech,
                        reading_order=1,
                    )
                ],
            )
        ],
    )
    out = save_stage_2a(doc)
    assert out.is_file()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["panels"][0]["bubbles"][0]["corrected_text"] == "Привет!"
    assert loaded["panels"][0]["bubbles"][0]["reading_order"] == 1


def test_assign_bubble_reading_orders():
    from story_analyzer.stages.stage_2a_processor import assign_bubble_reading_orders

    bubbles = [
        Bubble(bubble_id="a", bbox=[0, 0, 10, 10], raw_text="", corrected_text="", reading_order=None),
        Bubble(bubble_id="b", bbox=[0, 50, 10, 60], raw_text="", corrected_text="", reading_order=None),
    ]
    out = assign_bubble_reading_orders(bubbles)
    assert [b.reading_order for b in out] == [1, 2]


def test_bbox_normalization():
    b = Bubble(
        bubble_id="x_b1",
        bbox=[100, 80, 10, 20],
        raw_text="",
        corrected_text="",
    )
    assert b.bbox == [10, 20, 100, 80]


def test_corrected_text_required():
    with pytest.raises(ValidationError):
        Bubble(
            bubble_id="x_b1",
            bbox=[0, 0, 10, 10],
            raw_text="x",
            type=BubbleType.speech,
        )
