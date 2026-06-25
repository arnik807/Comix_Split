"""Load Stage 2a settings from config/story_stage_2a.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import yaml

from story_analyzer.bubble_detect_config import BubbleDetectConfig
from story_analyzer.env_loader import load_dotenv
from story_analyzer.ocr_engine_ids import normalize_ocr_engine
from story_analyzer.stages.ocr_preprocess import InvertMode, OcrPreprocessConfig

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "story_stage_2a.yaml"


@dataclass(frozen=True)
class SiliconFlowOcrConfig:
    base_url: str = "https://api.siliconflow.com/v1"
    vlm_model: str = "Qwen/Qwen3-VL-8B-Instruct"
    max_tokens: int = 512
    temperature: float = 0.1
    timeout_sec: float = 180.0


@dataclass(frozen=True)
class Stage2aConfig:
    bubble_class_id: int = 1
    confidence_threshold: float = 0.12
    iou_threshold: float = 0.45
    ocr_engine: str = "siliconflow"
    ocr_languages: tuple[str, ...] = ("ru", "en")
    composite_alpha_on_white: bool = True
    crop_padding_px: int = 12
    min_bubble_area_px: int = 32
    paddle_ocr_base_dir: str | None = None
    bubble_detect: BubbleDetectConfig = BubbleDetectConfig()
    siliconflow: SiliconFlowOcrConfig = SiliconFlowOcrConfig()
    ocr_preprocess: OcrPreprocessConfig = OcrPreprocessConfig()


def _parse_preprocess(block: dict) -> OcrPreprocessConfig:
    pp = block.get("ocr_preprocess") or {}
    invert = str(pp.get("invert", "auto")).lower()
    if invert not in ("never", "auto", "always"):
        invert = "auto"
    contrast = str(pp.get("contrast", "clahe")).lower()
    if contrast not in ("none", "clahe"):
        contrast = "clahe"
    return OcrPreprocessConfig(
        enabled=bool(pp.get("enabled", True)),
        upscale_factor=max(1, int(pp.get("upscale_factor", 3))),
        contrast=contrast,  # type: ignore[arg-type]
        invert=invert,  # type: ignore[arg-type]
        dark_background_threshold=int(pp.get("dark_background_threshold", 128)),
    )


def _parse_bubble_detect(block: dict) -> BubbleDetectConfig:
    bd = block.get("bubble_detect") or {}
    return BubbleDetectConfig(
        tiled=bool(bd.get("tiled", True)),
        tile_size=max(320, int(bd.get("tile_size", 640))),
        tile_overlap=float(bd.get("tile_overlap", 0.2)),
        filter_contained=bool(bd.get("filter_contained", False)),
    )


def _parse_siliconflow(block: dict) -> SiliconFlowOcrConfig:
    sf = block.get("siliconflow") or {}
    return SiliconFlowOcrConfig(
        base_url=str(sf.get("base_url", "https://api.siliconflow.com/v1")),
        vlm_model=str(sf.get("vlm_model", "Qwen/Qwen3-VL-8B-Instruct")),
        max_tokens=int(sf.get("max_tokens", 512)),
        temperature=float(sf.get("temperature", 0.1)),
        timeout_sec=float(sf.get("timeout_sec", 180.0)),
    )


def load_stage_2a_config(path: Path | None = None) -> Stage2aConfig:
    load_dotenv()
    path = path or CONFIG_PATH
    if not path.is_file():
        return Stage2aConfig()

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    block = raw.get("stage_2a") or {}
    langs: List[str] = block.get("ocr_languages") or ["ru", "en"]
    return Stage2aConfig(
        bubble_class_id=int(block.get("bubble_class_id", 1)),
        confidence_threshold=float(block.get("confidence_threshold", 0.12)),
        iou_threshold=float(block.get("iou_threshold", 0.45)),
        ocr_engine=normalize_ocr_engine(block.get("ocr_engine")),
        ocr_languages=tuple(str(x) for x in langs),
        composite_alpha_on_white=bool(block.get("composite_alpha_on_white", True)),
        crop_padding_px=int(block.get("crop_padding_px", 12)),
        min_bubble_area_px=int(block.get("min_bubble_area_px", 32)),
        paddle_ocr_base_dir=(
            str(block["paddle_ocr_base_dir"]).strip()
            if block.get("paddle_ocr_base_dir")
            else None
        ),
        bubble_detect=_parse_bubble_detect(block),
        siliconflow=_parse_siliconflow(block),
        ocr_preprocess=_parse_preprocess(block),
    )
