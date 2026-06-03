"""Panel detector config and YOLO output parsing."""

import numpy as np
import pytest

from pipeline import _parse_yolo_output
from utils.panel_detector import DETECTORS, get_detector, normalize_detector


def test_normalize_detector():
    assert normalize_detector("manga") == "manga"
    assert normalize_detector("unknown") == "comic"


def test_parse_yolo_single_class():
    raw = np.zeros((1, 5, 10), dtype=np.float32)
    raw[0, 4, :] = 0.9
    cx, cy, w, h, scores = _parse_yolo_output(raw, num_classes=1)
    assert scores.shape == (10,)
    assert float(scores[0]) == pytest.approx(0.9)


def test_parse_yolo26_end2end():
    raw = np.zeros((1, 4, 6), dtype=np.float32)
    raw[0, 0] = [10, 20, 110, 120, 0.9, 0]
    raw[0, 1] = [50, 60, 150, 160, 0.95, 1]
    raw[0, 2:, 5] = 1  # остальные — не panel
    cx, cy, w, h, scores = _parse_yolo_output(raw, num_classes=2, panel_class_id=0)
    assert len(scores) == 1
    assert float(scores[0]) == pytest.approx(0.9)
    assert float(w[0]) == pytest.approx(100.0)


def test_parse_yolo_multi_class_panel_only():
    raw = np.zeros((1, 6, 8), dtype=np.float32)
    raw[0, 4, 0] = 0.8  # panel class
    raw[0, 5, 0] = 0.2  # text class
    raw[0, 4, 1] = 0.1
    raw[0, 5, 1] = 0.95  # text wins — should be filtered by threshold later
    cx, cy, w, h, scores = _parse_yolo_output(raw, num_classes=2, panel_class_id=0)
    assert float(scores[0]) == pytest.approx(0.8)
    assert float(scores[1]) == pytest.approx(0.1)


def test_manga_detector_spec():
    spec = get_detector("manga")
    assert spec.num_classes == 2
    assert spec.panel_class_id == 0
    assert "manga" in spec.onnx_path.name
