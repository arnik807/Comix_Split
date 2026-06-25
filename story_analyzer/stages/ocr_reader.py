"""Bubble crop + preprocess + OCR (EasyOCR / PaddleOCR / SiliconFlow VLM)."""

from __future__ import annotations

from typing import List, Sequence, Tuple

import numpy as np

from story_analyzer.config import Stage2aConfig, load_stage_2a_config
from story_analyzer.ocr_engine_ids import normalize_ocr_engine
from story_analyzer.stages.ocr_engines import get_ocr_engine
from story_analyzer.stages.ocr_preprocess import preprocess_bubble_crop

_VLM_OCR_ENGINES = frozenset({"siliconflow"})


def crop_with_padding(
    img: np.ndarray,
    bbox: List[int],
    padding: int = 12,
) -> np.ndarray:
    h, w = img.shape[:2]
    x1, y1, x2, y2 = bbox
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(w, x2 + padding)
    y2 = min(h, y2 + padding)
    if x2 <= x1 or y2 <= y1:
        return np.zeros((1, 1, 3), dtype=np.uint8)
    return img[y1:y2, x1:x2].copy()


def _engine_used(engine, requested: str) -> str:
    return str(getattr(engine, "last_engine_used", requested))


def ocr_bubble_crop(
    crop_bgr: np.ndarray,
    cfg: Stage2aConfig | None = None,
    *,
    languages: Sequence[str] | None = None,
    engine_id: str | None = None,
) -> Tuple[str, float, str]:
    """Preprocess crop and run configured OCR engine. Returns (text, ms, engine_used)."""
    cfg = cfg or load_stage_2a_config()
    langs = languages or cfg.ocr_languages
    engine_name = normalize_ocr_engine(engine_id or cfg.ocr_engine)

    use_preprocess = cfg.ocr_preprocess.enabled and engine_name not in _VLM_OCR_ENGINES
    prepared = preprocess_bubble_crop(crop_bgr, cfg.ocr_preprocess) if use_preprocess else crop_bgr

    sf_block = {
        "base_url": cfg.siliconflow.base_url,
        "vlm_model": cfg.siliconflow.vlm_model,
        "max_tokens": cfg.siliconflow.max_tokens,
        "temperature": cfg.siliconflow.temperature,
        "timeout_sec": cfg.siliconflow.timeout_sec,
    }
    engine = get_ocr_engine(
        engine_name,
        paddle_base_dir=cfg.paddle_ocr_base_dir,
        siliconflow_block=sf_block,
    )
    text, ms = engine.recognize(prepared, langs)
    return text, ms, _engine_used(engine, engine_name)


def ocr_image_crop(
    crop_bgr: np.ndarray,
    languages: Sequence[str],
) -> Tuple[str, float]:
    """Backward-compatible wrapper using current config."""
    text, ms, _ = ocr_bubble_crop(crop_bgr, load_stage_2a_config(), languages=languages)
    return text, ms
