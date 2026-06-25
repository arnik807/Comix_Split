"""Tests for tiled bubble detection helpers."""

from __future__ import annotations

import pytest

from story_analyzer.stages.bubble_detector import _tile_origins, merge_boxes_nms


def test_tile_origins_single_tile_when_small():
    assert _tile_origins(500, 640, 512) == [0]


def test_tile_origins_includes_last_window():
    origins = _tile_origins(1586, 640, 512)
    assert 0 in origins
    assert 946 in origins  # 1586 - 640


def test_merge_boxes_nms_dedupes_overlap():
    boxes = [
        [10, 10, 100, 80],
        [12, 12, 98, 78],
        [200, 200, 300, 280],
    ]
    scores = [0.9, 0.7, 0.8]
    merged, merged_scores = merge_boxes_nms(
        boxes, scores, conf_threshold=0.1, iou_threshold=0.45
    )
    assert len(merged) == 2
    assert merged_scores[0] == pytest.approx(0.9)
