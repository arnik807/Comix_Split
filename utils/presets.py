"""Quality presets: standard / quality — load, apply, UI payload."""

from __future__ import annotations

import copy
import pathlib
from typing import Any, Dict, List, Optional

import yaml

from utils.anim_config import (
    AnimConfig,
    DEFAULT_ANIM_CONFIG_PATH,
    get_anim_config,
    load_anim_config,
    save_anim_config,
)
from utils.config import (
    AppConfig,
    DEFAULT_CONFIG_PATH,
    apply_config_to_pipeline,
    get_config,
    load_config,
    save_config,
)

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
PRESETS_PATH = ROOT_DIR / "config" / "presets.yaml"
USER_PRESETS_PATH = ROOT_DIR / "config" / "presets.user.yaml"

VALID_PRESETS = ("standard", "quality")


def _merge_presets(base: dict, overlay: dict) -> dict:
    out = copy.deepcopy(base)
    for name, body in (overlay or {}).items():
        if name not in out:
            out[name] = body
            continue
        for section, values in (body or {}).items():
            if isinstance(values, dict) and isinstance(out[name].get(section), dict):
                out[name][section] = {**out[name][section], **values}
            else:
                out[name][section] = values
    return out


def load_presets_file() -> dict[str, Any]:
    raw: dict[str, Any] = {}
    if PRESETS_PATH.is_file():
        with open(PRESETS_PATH, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    if USER_PRESETS_PATH.is_file():
        with open(USER_PRESETS_PATH, encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}
        raw = _merge_presets(raw, user)
    return raw


def list_presets() -> List[dict[str, str]]:
    data = load_presets_file()
    items = []
    for key in VALID_PRESETS:
        if key in data:
            items.append(
                {
                    "id": key,
                    "label": str(data[key].get("label", key)),
                    "description": str(data[key].get("description", "")),
                }
            )
    return items


def get_preset(name: str) -> dict[str, Any]:
    if name not in VALID_PRESETS:
        raise KeyError(f"Unknown preset: {name}. Use: {VALID_PRESETS}")
    data = load_presets_file()
    if name not in data:
        raise KeyError(f"Preset not in file: {name}")
    return copy.deepcopy(data[name])


def preset_ui_payload(name: str) -> dict[str, Any]:
    """Flat dict for Gradio / web forms."""
    p = get_preset(name)
    sp = p.get("split") or {}
    an = p.get("anim") or {}
    up = an.get("upscale") or {}
    hm = an.get("harmonize") or {}
    anim = an.get("animation") or {}
    rn = an.get("render") or {}
    use_sam = sp.get("use_sam")
    if use_sam is None:
        use_sam = sp.get("quality_mode") == "accurate"
    return {
        "preset": name,
        "label": p.get("label", name),
        "description": p.get("description", ""),
        "split": {
            "use_sam": bool(use_sam),
            "reading_order": bool(sp.get("reading_order", True)),
            "rtl": sp.get("reading_direction", "ltr") == "rtl",
            "quality_mode": str(sp.get("quality_mode", "fast")),
            "confidence_threshold": float(sp.get("confidence_threshold", 0.35)),
            "iou_threshold": float(sp.get("iou_threshold", 0.45)),
            "overlap_filter_threshold": float(
                sp.get("overlap_filter_threshold", 0.7)
            ),
        },
        "anim": {
            "upscale_enabled": bool(up.get("enabled", True)),
            "upscale_scale": int(up.get("scale", 2)),
            "upscale_model": str(up.get("model", "animevideov3")),
            "gpu_id": int(up.get("gpu_id", 0)),
            "harmonize_mode": str(hm.get("mode", "auto")),
            "harmonize_blur_sigma": int(hm.get("blur_sigma", 60)),
            "harmonize_vignette": float(hm.get("vignette_strength", 0.7)),
            "mode": str(anim.get("mode", "opencv_zoom")),
            "duration": float(anim.get("duration", 3.0)),
            "fps": int(anim.get("fps", 24)),
            "intensity": float(anim.get("intensity", 0.3)),
            "depthflow_animation": str(anim.get("depthflow_animation", "zoom")),
            "do_concat": bool(rn.get("concat_panels", True)),
        },
    }


def apply_split_preset(split: dict[str, Any], persist: bool = False) -> AppConfig:
    cfg = get_config()
    cfg.quality_mode = str(split.get("quality_mode", cfg.quality_mode))
    if "use_sam" in split:
        cfg.quality_mode = "accurate" if split["use_sam"] else "fast"
    cfg.reading_order = bool(split.get("reading_order", cfg.reading_order))
    if "reading_direction" in split:
        cfg.reading_direction = str(split["reading_direction"])
    elif "rtl" in split:
        cfg.reading_direction = "rtl" if split["rtl"] else "ltr"
    cfg.confidence_threshold = float(
        split.get("confidence_threshold", cfg.confidence_threshold)
    )
    cfg.iou_threshold = float(split.get("iou_threshold", cfg.iou_threshold))
    cfg.overlap_filter_threshold = float(
        split.get("overlap_filter_threshold", cfg.overlap_filter_threshold)
    )
    apply_config_to_pipeline()
    if persist:
        save_config(cfg)
    return cfg


def apply_anim_preset(anim_root: dict[str, Any], persist: bool = False) -> AnimConfig:
    cfg = get_anim_config()
    up = anim_root.get("upscale") or {}
    hm = anim_root.get("harmonize") or {}
    anim = anim_root.get("animation") or {}
    rn = anim_root.get("render") or {}

    if up:
        cfg.upscale.enabled = bool(up.get("enabled", cfg.upscale.enabled))
        cfg.upscale.scale = int(up.get("scale", cfg.upscale.scale))
        cfg.upscale.model = str(up.get("model", cfg.upscale.model))
        cfg.upscale.gpu_id = int(up.get("gpu_id", cfg.upscale.gpu_id))
    if hm:
        cfg.harmonize.enabled = bool(hm.get("enabled", cfg.harmonize.enabled))
        cfg.harmonize.mode = str(hm.get("mode", cfg.harmonize.mode))
        cfg.harmonize.blur_sigma = int(hm.get("blur_sigma", cfg.harmonize.blur_sigma))
        cfg.harmonize.vignette_strength = float(
            hm.get("vignette_strength", cfg.harmonize.vignette_strength)
        )
    if anim:
        cfg.animation.mode = str(anim.get("mode", cfg.animation.mode))
        cfg.animation.duration = float(anim.get("duration", cfg.animation.duration))
        cfg.animation.fps = int(anim.get("fps", cfg.animation.fps))
        cfg.animation.intensity = float(anim.get("intensity", cfg.animation.intensity))
        cfg.animation.depthflow_animation = str(
            anim.get("depthflow_animation", cfg.animation.depthflow_animation)
        )
    if rn:
        cfg.render.concat_panels = bool(rn.get("concat_panels", cfg.render.concat_panels))

    if persist:
        save_anim_config(cfg)
    return cfg


def apply_preset(name: str, persist: bool = False) -> dict[str, Any]:
    """Apply preset to in-memory config (+ optional YAML on disk). Returns UI payload."""
    p = get_preset(name)
    apply_split_preset(p.get("split") or {}, persist=persist)
    apply_anim_preset(p.get("anim") or {}, persist=persist)
    return preset_ui_payload(name)


def snapshot_from_configs() -> dict[str, Any]:
    """Current runtime settings as UI-shaped dict (for compare / export)."""
    cfg = get_config()
    ac = get_anim_config()
    return {
        "split": {
            "use_sam": cfg.use_sam,
            "reading_order": cfg.reading_order,
            "rtl": cfg.rtl,
            "quality_mode": cfg.quality_mode,
            "confidence_threshold": cfg.confidence_threshold,
            "iou_threshold": cfg.iou_threshold,
            "overlap_filter_threshold": cfg.overlap_filter_threshold,
        },
        "anim": {
            "upscale_enabled": ac.upscale.enabled,
            "upscale_scale": ac.upscale.scale,
            "upscale_model": ac.upscale.model,
            "gpu_id": ac.upscale.gpu_id,
            "harmonize_mode": ac.harmonize.mode,
            "harmonize_blur_sigma": ac.harmonize.blur_sigma,
            "harmonize_vignette": ac.harmonize.vignette_strength,
            "mode": ac.animation.mode,
            "duration": ac.animation.duration,
            "fps": ac.animation.fps,
            "intensity": ac.animation.intensity,
            "depthflow_animation": ac.animation.depthflow_animation,
            "do_concat": ac.render.concat_panels,
        },
    }
