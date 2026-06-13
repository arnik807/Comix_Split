"""
Сохранение настроек UI между перезагрузками (веб :8000 и Gradio :7860).

Файл: config/ui_state.user.json (в .gitignore).
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal

from utils.anim_config import load_anim_config
from utils.config import get_config, load_config
from utils.panel_detector import normalize_detector
from utils.upscale_options import normalize_upscale_backend

ROOT_DIR = Path(__file__).resolve().parent.parent
UI_STATE_PATH = ROOT_DIR / "config" / "ui_state.user.json"
UI_STATE_VERSION = 1

SectionName = Literal["split", "upscale", "video", "global", "all"]


def default_global() -> dict[str, Any]:
    return {
        "active_preset": "standard",
        "preset_persist": False,
        "active_tab": "split",
    }


def default_split() -> dict[str, Any]:
    load_config()
    cfg = get_config()
    return {
        "source_path": "exam_imgs\\01_Asterix_the_Gaul_page-0004.jpg",
        "folder_path": "",
        "output_dir": "output",
        "panel_detector": normalize_detector(cfg.panel_detector),
        "use_sam": cfg.quality_mode == "accurate",
        "reading_order": bool(cfg.reading_order),
        "rtl": cfg.reading_direction == "rtl",
        "confidence_threshold": float(cfg.confidence_threshold),
        "iou_threshold": float(cfg.iou_threshold),
        "poly_mode": False,
    }


def default_upscale() -> dict[str, Any]:
    ac = load_anim_config()
    u = ac.upscale
    return {
        "panels_dir": "",
        "output_dir": "output_upscaled",
        "scale": int(u.scale),
        "backend": normalize_upscale_backend(u.backend),
        "model": u.model,
        "gpu_id": int(u.gpu_id),
        "cugan_noise": int(u.cugan_noise),
        "cugan_syncgap": int(u.cugan_syncgap),
    }


def default_video() -> dict[str, Any]:
    ac = load_anim_config()
    u = ac.upscale
    h = ac.harmonize
    a = ac.animation
    r = ac.render
    return {
        "panels_dir": "",
        "output_dir": "story_out",
        "mode": a.mode,
        "upscale_enabled": bool(u.enabled),
        "scale": int(u.scale),
        "backend": normalize_upscale_backend(u.backend),
        "model": u.model,
        "gpu_id": int(u.gpu_id),
        "cugan_noise": int(u.cugan_noise),
        "cugan_syncgap": int(u.cugan_syncgap),
        "harmonize_mode": h.mode,
        "harmonize_blur_sigma": float(h.blur_sigma),
        "harmonize_vignette": float(h.vignette_strength),
        "intensity": float(a.intensity),
        "depthflow_animation": a.depthflow_animation,
        "tpsmm_driving_video": a.tpsmm_driving_video or "",
        "duration": float(a.duration),
        "fps": int(a.fps),
        "do_concat": bool(r.concat_panels),
    }


def default_state() -> dict[str, Any]:
    return {
        "version": UI_STATE_VERSION,
        "global": default_global(),
        "split": default_split(),
        "upscale": default_upscale(),
        "video": default_video(),
    }


def _merge_section(base: dict[str, Any], patch: dict[str, Any] | None) -> dict[str, Any]:
    if not patch:
        return base
    out = deepcopy(base)
    for k, v in patch.items():
        if v is not None:
            out[k] = v
    return out


def load_ui_state() -> dict[str, Any]:
    defaults = default_state()
    if not UI_STATE_PATH.is_file():
        return defaults
    try:
        raw = json.loads(UI_STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return defaults
    if raw.get("version") != UI_STATE_VERSION:
        return defaults
    return {
        "version": UI_STATE_VERSION,
        "global": _merge_section(defaults["global"], raw.get("global")),
        "split": _merge_section(defaults["split"], raw.get("split")),
        "upscale": _merge_section(defaults["upscale"], raw.get("upscale")),
        "video": _merge_section(defaults["video"], raw.get("video")),
    }


def save_ui_state(state: dict[str, Any]) -> None:
    UI_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": UI_STATE_VERSION,
        "global": state.get("global") or default_global(),
        "split": state.get("split") or default_split(),
        "upscale": state.get("upscale") or default_upscale(),
        "video": state.get("video") or default_video(),
    }
    UI_STATE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def patch_ui_state(
    *,
    global_: dict[str, Any] | None = None,
    split: dict[str, Any] | None = None,
    upscale: dict[str, Any] | None = None,
    video: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = load_ui_state()
    if global_:
        state["global"] = _merge_section(state["global"], global_)
    if split:
        state["split"] = _merge_section(state["split"], split)
    if upscale:
        state["upscale"] = _merge_section(state["upscale"], upscale)
    if video:
        state["video"] = _merge_section(state["video"], video)
    save_ui_state(state)
    return state


def reset_ui_section(section: SectionName) -> dict[str, Any]:
    state = load_ui_state()
    if section in ("split", "all"):
        state["split"] = default_split()
    if section in ("upscale", "all"):
        state["upscale"] = default_upscale()
    if section in ("video", "all"):
        state["video"] = default_video()
    if section in ("global", "all"):
        state["global"] = default_global()
    save_ui_state(state)
    return state
