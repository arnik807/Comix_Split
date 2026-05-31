"""Pipeline unit tests (skip ML if models missing)."""

from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
MODELS_OK = (ROOT / "models" / "yolo_comic_int8.onnx").is_file()


pytestmark = pytest.mark.skipif(not MODELS_OK, reason="ONNX models not in models/")


def test_analyze_page_finds_panels():
    from pipeline import analyze_page

    img_path = ROOT / "test_page.jpg"
    if not img_path.is_file():
        pytest.skip("test_page.jpg missing")
    img = cv2.imdecode(np.fromfile(str(img_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    result = analyze_page(img, use_sam=False, reading_order=True, quiet=True)
    assert "yolo_ms" in result.timings_ms
    assert result.timings_ms["total_ms"] > 0


def test_format_panel_filename():
    from pipeline import format_panel_filename
    from utils.config import AppConfig

    cfg = AppConfig()
    assert format_panel_filename(5, 2, 1, cfg) == "005_page_002_panel_01.png"


def test_process_page_output(tmp_path):
    from pipeline import process_page

    img_path = ROOT / "test_page.jpg"
    if not img_path.is_file():
        pytest.skip("test_page.jpg missing")
    out = tmp_path / "out"
    panels = process_page(str(img_path), str(out), quiet=True)
    comic_dir = out / "test_page"
    if panels:
        assert any(comic_dir.glob("*.png"))
