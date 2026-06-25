"""Upscale backend/model options for API and UI."""

from __future__ import annotations

from typing import Any

from utils.anim_config import (
    SPAN_VARIANTS,
    UPSCALE_BACKENDS,
    X4_ONLY_UPSCALE_MODEL,
    normalize_upscale_backend,
    resolve_upscale_scale,
)
from utils.models_registry import check_all_backends, format_install_hint

REALESRGAN_MODELS = [
    {"id": "animevideov3", "label": "Быстрый (animevideov3)", "scales": [2, 4]},
    {
        "id": "anime_6B",
        "label": "Точный (x4plus-anime, только ×4)",
        "scales": [4],
    },
]

CUGAN_MODELS = [
    {"id": "cugan_se", "label": "CUGAN SE (models-se)", "scales": [1, 2, 3, 4]},
]

BACKEND_LABELS = {
    "realesrgan": "Real-ESRGAN",
    "realcugan": "Real-CUGAN",
    "span": "SPAN",
}


def models_for_backend(backend: str) -> list[dict[str, Any]]:
    b = normalize_upscale_backend(backend)
    if b == "realcugan":
        return list(CUGAN_MODELS)
    if b == "span":
        return [
            {"id": vid, "label": label, "scales": [sc]}
            for vid, (_ncnn, sc, label) in SPAN_VARIANTS.items()
        ]
    return list(REALESRGAN_MODELS)


def allowed_scales(backend: str, model: str) -> list[int]:
    b = normalize_upscale_backend(backend)
    for m in models_for_backend(b):
        if m["id"] == model:
            return list(m["scales"])
    if b == "realesrgan" and model == X4_ONLY_UPSCALE_MODEL:
        return [4]
    if b == "realcugan":
        return [1, 2, 3, 4]
    return [2, 4]


def upscale_options_payload() -> dict[str, Any]:
    statuses = {s.backend_id: s for s in check_all_backends()}
    backends = []
    for bid in UPSCALE_BACKENDS:
        st = statuses.get(bid)
        installed = bool(st and st.installed)
        entry: dict[str, Any] = {
            "id": bid,
            "label": BACKEND_LABELS.get(bid, bid),
            "installed": installed,
            "models": models_for_backend(bid),
        }
        if not installed and st:
            entry["install_hint"] = format_install_hint(st)
        backends.append(entry)
    return {"backends": backends}


def cpu_gpu_allowed(backend: str) -> bool:
    """NCNN CPU fallback is unreliable/slow; Real-ESRGAN uses Vulkan only."""
    return normalize_upscale_backend(backend) != "realesrgan"


def normalize_upscale_gpu(backend: str, gpu_id: int | None) -> int:
    gid = int(0 if gpu_id is None else gpu_id)
    if not cpu_gpu_allowed(backend):
        return 0
    return gid


def apply_upscale_fields(
    cfg_upscale,
    *,
    backend: str | None = None,
    model: str | None = None,
    scale: int | None = None,
    gpu_id: int | None = None,
    tile_size: int | None = None,
    cugan_noise: int | None = None,
    cugan_syncgap: int | None = None,
    cugan_weights: str | None = None,
) -> None:
    if backend is not None:
        cfg_upscale.backend = normalize_upscale_backend(backend)
    if model is not None:
        cfg_upscale.model = str(model)
    if scale is not None:
        cfg_upscale.scale = int(scale)
    if gpu_id is not None:
        cfg_upscale.gpu_id = int(gpu_id)
    if tile_size is not None:
        cfg_upscale.tile_size = int(tile_size)
    if cugan_noise is not None:
        cfg_upscale.cugan_noise = int(cugan_noise)
    if cugan_syncgap is not None:
        cfg_upscale.cugan_syncgap = int(cugan_syncgap)
    if cugan_weights is not None:
        cfg_upscale.cugan_weights = str(cugan_weights)
    cfg_upscale.scale = resolve_upscale_scale(
        cfg_upscale.backend, cfg_upscale.model, cfg_upscale.scale
    )
    cfg_upscale.gpu_id = normalize_upscale_gpu(cfg_upscale.backend, cfg_upscale.gpu_id)
