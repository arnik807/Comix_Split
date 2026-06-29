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

SectionName = Literal["split", "upscale", "video", "story2a", "global", "all"]

_SPLIT_PATH_KEYS = frozenset({"source_path", "folder_path", "output_dir"})
_UPSCALE_PATH_KEYS = frozenset({"panels_dir", "output_dir"})
_VIDEO_PATH_KEYS = frozenset({"panels_dir", "output_dir", "tpsmm_driving_video"})
_STORY2A_PATH_KEYS = frozenset({"project", "panels_dir", "output_json_path"})


def default_global() -> dict[str, Any]:
    return {
        "active_preset": "standard",
        "preset_persist": False,
        "active_tab": "split",
        "current_project": "",
    }


def default_split() -> dict[str, Any]:
    load_config()
    cfg = get_config()
    return {
        "source_path": "exam_imgs\\01_Asterix_the_Gaul_page-0004.jpg",
        "folder_path": "",
        "output_dir": "output",
        "use_project": False,
        "project": "",
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
        "use_project": False,
        "project": "",
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
        "use_project": False,
        "project": "",
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


def default_story2a() -> dict[str, Any]:
    return {
        "project": "test_2a",
        "panels_dir": "exam_img\\manga_test_1\\manga_test_1_upscaled",
        "workflow_mode": "manual",
        "output_json_path": "",
        "use_project": False,
    }


def default_state() -> dict[str, Any]:
    return {
        "version": UI_STATE_VERSION,
        "global": default_global(),
        "split": default_split(),
        "upscale": default_upscale(),
        "video": default_video(),
        "story2a": default_story2a(),
    }


def _merge_section(base: dict[str, Any], patch: dict[str, Any] | None) -> dict[str, Any]:
    if not patch:
        return base
    out = deepcopy(base)
    for k, v in patch.items():
        if v is not None:
            out[k] = v
    return out


def _merge_section_paths(
    base: dict[str, Any],
    patch: dict[str, Any] | None,
    path_keys: frozenset[str],
    *,
    enum_fields: dict[str, frozenset[str]] | None = None,
) -> dict[str, Any]:
    """Patch секции: пустые строки для path_keys — явная очистка; enum_fields — только допустимые значения."""
    if not patch:
        return base
    out = deepcopy(base)
    enums = enum_fields or {}
    for k, v in patch.items():
        if v is None:
            continue
        if k in enums:
            if v in enums[k]:
                out[k] = v
            continue
        if k in path_keys:
            out[k] = v if isinstance(v, str) else str(v)
            continue
        out[k] = v
    return out


def _merge_story2a(base: dict[str, Any], patch: dict[str, Any] | None) -> dict[str, Any]:
    return _merge_section_paths(
        base,
        patch,
        _STORY2A_PATH_KEYS,
        enum_fields={"workflow_mode": frozenset({"manual", "auto"})},
    )


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
        "story2a": _merge_section(defaults["story2a"], raw.get("story2a")),
    }


def save_ui_state(state: dict[str, Any]) -> None:
    UI_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": UI_STATE_VERSION,
        "global": state.get("global") or default_global(),
        "split": state.get("split") or default_split(),
        "upscale": state.get("upscale") or default_upscale(),
        "video": state.get("video") or default_video(),
        "story2a": state.get("story2a") or default_story2a(),
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
    story2a: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = load_ui_state()
    if global_:
        state["global"] = _merge_section(state["global"], global_)
    if split:
        state["split"] = _merge_section_paths(state["split"], split, _SPLIT_PATH_KEYS)
    if upscale:
        state["upscale"] = _merge_section_paths(state["upscale"], upscale, _UPSCALE_PATH_KEYS)
    if video:
        state["video"] = _merge_section_paths(state["video"], video, _VIDEO_PATH_KEYS)
    if story2a:
        state["story2a"] = _merge_story2a(state["story2a"], story2a)
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
    if section in ("story2a", "all"):
        state["story2a"] = default_story2a()
    if section in ("global", "all"):
        state["global"] = default_global()
    save_ui_state(state)
    return state
