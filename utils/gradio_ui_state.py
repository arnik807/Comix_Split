"""Восстановление и сохранение UI Gradio из utils/ui_state."""

from __future__ import annotations

from typing import Any

import gradio as gr

from utils.anim_config import normalize_upscale_backend
from utils.gradio_upscale_ui import upscale_controls_update
from utils.ui_state import load_ui_state, patch_ui_state, reset_ui_section

ANIM_MODES_STANDARD = [
    ("Zoom (OpenCV)", "opencv_zoom"),
    ("Shake (OpenCV)", "opencv_shake"),
    ("Статичный кадр", "static"),
]
ANIM_MODES_ALL = ANIM_MODES_STANDARD + [
    ("Parallax (DepthFlow)", "depthflow"),
    ("TPSMM (медленно, driving MP4)", "tpsmm"),
]

TAB_IDS = ("split", "upscale", "video")


def initial_tab_selected() -> str:
    tab = load_ui_state()["global"].get("active_tab", "split")
    return tab if tab in TAB_IDS else "split"


def save_tab_from_select(evt: gr.SelectData) -> None:
    idx = evt.index if evt.index is not None else 0
    tab = TAB_IDS[idx] if 0 <= idx < len(TAB_IDS) else "split"
    patch_ui_state(global_={"active_tab": tab})


def _mode_badge(active_preset: str) -> str:
    if active_preset == "quality":
        return "**MODE: QUALITY** — точный режим, доступны расширенные настройки."
    return "**MODE: STANDARD** — быстрый режим, минимум настроек."


def _quality_visibility(active_preset: str) -> bool:
    return active_preset == "quality"


def restore_gradio_ui() -> tuple[Any, ...]:
    """Возвращает gr.update для всех полей, сохраняемых в ui_state."""
    st = load_ui_state()
    g = st["global"]
    s = st["split"]
    u = st["upscale"]
    v = st["video"]
    is_q = _quality_visibility(g.get("active_preset", "standard"))
    mode_choices = ANIM_MODES_ALL if is_q else ANIM_MODES_STANDARD

    up_ui = upscale_controls_update(
        u.get("backend", "realesrgan"),
        u.get("model", "animevideov3"),
        u.get("scale", 2),
        u.get("cugan_noise", -1),
        u.get("cugan_syncgap", 3),
    )
    vid_ui = upscale_controls_update(
        v.get("backend", "realesrgan"),
        v.get("model", "animevideov3"),
        v.get("scale", 2),
        v.get("cugan_noise", -1),
        v.get("cugan_syncgap", 3),
    )

    vid_mode = v.get("mode", "opencv_zoom")
    if not is_q and vid_mode in ("depthflow", "tpsmm"):
        vid_mode = "opencv_zoom"
    show_df = is_q and vid_mode == "depthflow"
    show_tps = is_q and vid_mode == "tpsmm"

    return (
        gr.update(value=s.get("source_path", "")),
        gr.update(value=s.get("folder_path", "")),
        gr.update(value=s.get("output_dir", "output")),
        gr.update(value=s.get("panel_detector", "comic")),
        gr.update(value=bool(s.get("use_sam")), visible=is_q),
        gr.update(value=s.get("reading_order", True)),
        gr.update(value=bool(s.get("rtl"))),
        gr.update(value=float(s.get("confidence_threshold", 0.35))),
        gr.update(value=float(s.get("iou_threshold", 0.45))),
        gr.update(value=u.get("panels_dir", "")),
        gr.update(value=u.get("output_dir", "output_upscaled")),
        up_ui[1],
        gr.update(value=u.get("backend", "realesrgan"), visible=is_q),
        up_ui[0],
        up_ui[2],
        up_ui[3],
        up_ui[4],
        gr.update(visible=is_q),
        gr.update(value=v.get("panels_dir", "")),
        gr.update(value=v.get("output_dir", "story_out")),
        gr.update(value=vid_mode, choices=mode_choices),
        gr.update(value=bool(v.get("upscale_enabled", True))),
        vid_ui[1],
        gr.update(value=v.get("backend", "realesrgan"), visible=is_q),
        vid_ui[0],
        vid_ui[2],
        vid_ui[3],
        vid_ui[4],
        gr.update(value=int(v.get("gpu_id", 0)), visible=is_q),
        gr.update(value=v.get("harmonize_mode", "auto"), visible=is_q),
        gr.update(value=float(v.get("harmonize_blur_sigma", 60)), visible=is_q),
        gr.update(value=float(v.get("harmonize_vignette", 0.7)), visible=is_q),
        gr.update(value=float(v.get("intensity", 0.3)), visible=is_q),
        gr.update(value=v.get("depthflow_animation", "zoom"), visible=show_df),
        gr.update(value=v.get("tpsmm_driving_video", ""), visible=show_tps),
        gr.update(value=float(v.get("duration", 3))),
        gr.update(value=int(v.get("fps", 24))),
        gr.update(value=bool(v.get("do_concat", True))),
        gr.update(visible=is_q),
        gr.update(value=bool(g.get("preset_persist", False))),
        gr.update(value=_mode_badge(g.get("active_preset", "standard"))),
        gr.update(selected=initial_tab_selected()),
    )


def save_split_ui(
    source_path: str,
    folder_path: str,
    output_dir: str,
    panel_detector: str,
    use_sam: bool,
    reading_order: bool,
    rtl: bool,
    conf: float,
    iou: float,
) -> None:
    patch_ui_state(
        split={
            "source_path": source_path if source_path is not None else "",
            "folder_path": folder_path if folder_path is not None else "",
            "output_dir": output_dir if output_dir is not None else "",
            "panel_detector": panel_detector,
            "use_sam": use_sam,
            "reading_order": reading_order,
            "rtl": rtl,
            "confidence_threshold": conf,
            "iou_threshold": iou,
        }
    )


def save_upscale_ui(
    panels_dir: str,
    output_dir: str,
    scale: int,
    backend: str,
    model: str,
    gpu: int,
    cugan_noise: int,
    cugan_syncgap: int,
) -> None:
    patch_ui_state(
        upscale={
            "panels_dir": panels_dir if panels_dir is not None else "",
            "output_dir": output_dir if output_dir is not None else "",
            "scale": int(scale),
            "backend": normalize_upscale_backend(backend),
            "model": model,
            "gpu_id": int(gpu),
            "cugan_noise": int(cugan_noise),
            "cugan_syncgap": int(cugan_syncgap),
        }
    )


def save_video_ui(
    panels_dir: str,
    output_dir: str,
    mode: str,
    upscale_enabled: bool,
    scale: int,
    duration: float,
    fps: int,
    do_concat: bool,
    backend: str,
    model: str,
    gpu: int,
    cugan_noise: int,
    cugan_syncgap: int,
    harm_mode: str,
    harm_blur: float,
    harm_vig: float,
    intensity: float,
    df_anim: str,
    tpsmm_driving: str,
) -> None:
    patch_ui_state(
        video={
            "panels_dir": panels_dir if panels_dir is not None else "",
            "output_dir": output_dir if output_dir is not None else "",
            "mode": mode,
            "upscale_enabled": upscale_enabled,
            "scale": int(scale),
            "duration": float(duration),
            "fps": int(fps),
            "do_concat": do_concat,
            "backend": normalize_upscale_backend(backend),
            "model": model,
            "gpu_id": int(gpu),
            "cugan_noise": int(cugan_noise),
            "cugan_syncgap": int(cugan_syncgap),
            "harmonize_mode": harm_mode,
            "harmonize_blur_sigma": float(harm_blur),
            "harmonize_vignette": float(harm_vig),
            "intensity": float(intensity),
            "depthflow_animation": df_anim,
            "tpsmm_driving_video": tpsmm_driving if tpsmm_driving is not None else "",
        }
    )


def save_global_ui(active_preset: str, preset_persist: bool) -> None:
    patch_ui_state(
        global_={
            "active_preset": active_preset,
            "preset_persist": preset_persist,
        }
    )


def reset_gradio_section(section: str) -> tuple[Any, ...]:
    reset_ui_section(section)  # type: ignore[arg-type]
    return restore_gradio_ui()
