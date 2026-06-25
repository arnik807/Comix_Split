"""Tests for OCR preprocess and engine config."""

from __future__ import annotations

import numpy as np

from story_analyzer.config import load_stage_2a_config
from story_analyzer.ocr_engine_ids import normalize_ocr_engine
from story_analyzer.stages.ocr_engines import (
    _extract_paddle_text,
    resolve_paddle_ocr_base_dir,
)
from story_analyzer.stages.ocr_preprocess import OcrPreprocessConfig, preprocess_bubble_crop


def test_preprocess_upscale_triples_size():
    crop = np.zeros((20, 30, 3), dtype=np.uint8)
    crop[5:15, 5:25] = 255
    cfg = OcrPreprocessConfig(enabled=True, upscale_factor=3, contrast="none", invert="never")
    out = preprocess_bubble_crop(crop, cfg)
    assert out.shape[0] == 60
    assert out.shape[1] == 90


def test_preprocess_auto_invert_on_dark_background():
    dark = np.full((24, 40, 3), 20, dtype=np.uint8)
    cfg = OcrPreprocessConfig(enabled=True, upscale_factor=1, contrast="none", invert="auto")
    out = preprocess_bubble_crop(dark, cfg)
    assert int(out.mean()) > 200


def test_preprocess_no_invert_on_white_bubble():
    bright = np.full((24, 40, 3), 240, dtype=np.uint8)
    cfg = OcrPreprocessConfig(enabled=True, upscale_factor=1, contrast="none", invert="auto")
    out = preprocess_bubble_crop(bright, cfg)
    assert int(out.mean()) > 200


def test_default_engine_is_siliconflow():
    cfg = load_stage_2a_config()
    assert normalize_ocr_engine(cfg.ocr_engine) == "siliconflow"
    assert cfg.siliconflow.vlm_model == "Qwen/Qwen3-VL-8B-Instruct"
    assert cfg.crop_padding_px >= 12
    assert cfg.ocr_preprocess.upscale_factor >= 3
    assert cfg.paddle_ocr_base_dir == "models/paddleocr"


def test_resolve_paddle_base_dir_relative_to_project():
    resolved = resolve_paddle_ocr_base_dir("models/paddleocr")
    assert resolved.endswith("models\\paddleocr") or resolved.endswith("models/paddleocr")
    assert resolve_paddle_ocr_base_dir("D:/cache/paddle").replace("\\", "/") == "D:/cache/paddle"


def test_resolve_paddle_base_dir_rejects_non_ascii_config():
    resolved = resolve_paddle_ocr_base_dir("C:/Users/Николай/.paddleocr")
    assert _path_is_ascii(resolved)


def test_extract_paddle_text_sorts_lines_top_to_bottom():
    fake = [
        [
            ([[0, 40], [10, 40], [10, 50], [0, 50]], ("Second line", 0.9)),
            ([[0, 5], [10, 5], [10, 15], [0, 15]], ("First line", 0.95)),
        ]
    ]
    assert _extract_paddle_text(fake) == "First line\nSecond line"


def _path_is_ascii(path: str) -> bool:
    try:
        path.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False
