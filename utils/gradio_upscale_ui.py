"""Gradio component updates for upscale backend/model controls."""

from __future__ import annotations

import gradio as gr

from utils.anim_config import X4_ONLY_UPSCALE_MODEL, normalize_upscale_backend
from utils.models_registry import check_backend, format_install_hint
from utils.ui_tooltips import FIELD_TIPS as TIP
from utils.upscale_options import allowed_scales, cpu_gpu_allowed, models_for_backend

UPSCALE_BACKEND_CHOICES = [
    ("Real-ESRGAN", "realesrgan"),
    ("Real-CUGAN", "realcugan"),
    ("SPAN", "span"),
]


def upscale_gpu_control(backend: str, gpu_id: int = 0):
    """Real-ESRGAN: Vulkan only — CPU option disabled (NCNN CPU path is unreliable)."""
    backend = normalize_upscale_backend(backend)
    if not cpu_gpu_allowed(backend):
        return gr.update(
            choices=[("0 — видеокарта (Vulkan)", 0)],
            value=0,
            info="Real-ESRGAN: только GPU (Vulkan). Режим CPU для этого backend недоступен.",
        )
    gid = int(gpu_id)
    if gid not in (0, -1):
        gid = 0
    return gr.update(
        choices=[
            ("0 — видеокарта (Vulkan)", 0),
            ("−1 — CPU (медленно, не рекомендуется)", -1),
        ],
        value=gid,
        info=TIP["up_gpu"],
    )


def upscale_controls_update(
    backend: str,
    model: str,
    scale: int | float = 2,
    cugan_noise: int = -1,
    cugan_syncgap: int = 3,
    gpu_id: int = 0,
):
    """Refresh model list, scale choices, CUGAN fields, install hint."""
    backend = normalize_upscale_backend(backend)
    model_list = [(m["label"], m["id"]) for m in models_for_backend(backend)]
    ids = [x[1] for x in model_list]
    model = str(model)
    if model not in ids and model_list:
        model = ids[0]

    scales = allowed_scales(backend, model)
    sc = int(scale)
    if sc not in scales:
        sc = scales[0]

    st = check_backend(backend)
    hint = "" if st.installed else format_install_hint(st).replace("\n", "  \n")
    cugan = backend == "realcugan"

    scale_info = TIP["up_scale"]
    if backend == "realesrgan" and model == X4_ONLY_UPSCALE_MODEL:
        scale_info += " Для x4plus-anime доступен только ×4."
    if backend == "span":
        scale_info += " Масштаб задаётся выбранной моделью SPAN."
    if backend == "realcugan":
        scale_info += " Real-CUGAN: ×1–×4."

    return (
        gr.update(choices=model_list, value=model),
        gr.update(choices=scales, value=sc, info=scale_info),
        gr.update(visible=cugan, value=int(cugan_noise)),
        gr.update(visible=cugan, value=int(cugan_syncgap)),
        gr.update(value=hint, visible=bool(hint)),
        upscale_gpu_control(backend, gpu_id),
    )
