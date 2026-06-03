"""Load config_animate.yaml for the anim pipeline."""

from __future__ import annotations

import pathlib
import shutil
from dataclasses import dataclass
from typing import Any, Optional

import yaml

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_ANIM_CONFIG_PATH = ROOT_DIR / "config_animate.yaml"
MODELS_ANIM = ROOT_DIR / "models" / "anim"

NCNN_MODELS = {
    "animevideov3": "realesr-animevideov3",
    "anime_6B": "realesrgan-x4plus-anime",
}
# Config id anime_6B → NCNN realesrgan-x4plus-anime (not RealESRGAN_x4plus_anime_6B weights).
X4_ONLY_UPSCALE_MODEL = "anime_6B"

UPSCALE_BACKENDS = ("realesrgan", "realcugan", "span")

# variant_id -> (ncnn -n name, forced scale, UI label)
SPAN_VARIANTS: dict[str, tuple[str, int, str]] = {
    "span_x2_ch48": ("spanx2_ch48", 2, "SPAN ×2 ch48"),
    "span_x4_ch48": ("spanx4_ch48", 4, "SPAN ×4 ch48"),
}

CUGAN_WEIGHTS_DIRS = {
    "cugan_se": "models-se",
    "cugan_pro": "models-pro",
}


def normalize_upscale_backend(raw: str) -> str:
    b = str(raw or "realesrgan").strip().lower()
    if b in ("ncnn_vulkan", "realesrgan", "esrgan", ""):
        return "realesrgan"
    if b in ("realcugan", "cugan"):
        return "realcugan"
    if b == "span":
        return "span"
    return "realesrgan"


def resolve_realesrgan_scale(model: str, scale: int) -> int:
    s = int(scale)
    if s not in (2, 3, 4):
        s = 2
    if model == X4_ONLY_UPSCALE_MODEL and s != 4:
        return 4
    return s


def resolve_upscale_scale(backend: str, model: str, scale: int) -> int:
    """Clamp scale per backend/model (x4plus-anime, SPAN weights, etc.)."""
    b = normalize_upscale_backend(backend)
    if b == "realesrgan":
        return resolve_realesrgan_scale(model, scale)
    if b == "span":
        if model in SPAN_VARIANTS:
            return SPAN_VARIANTS[model][1]
        return 4 if int(scale) == 4 else 2
    if b == "realcugan":
        s = int(scale)
        return s if s in (1, 2, 3, 4) else 2
    return 2


def span_ncnn_name(model: str) -> str:
    if model in SPAN_VARIANTS:
        return SPAN_VARIANTS[model][0]
    return str(model) if model.startswith("span") else "spanx4_ch48"


def cugan_model_path(model: str, weights_override: str) -> str:
    if weights_override:
        return weights_override
    return CUGAN_WEIGHTS_DIRS.get(model, "models-se")


@dataclass
class UpscaleConfig:
    enabled: bool = True
    scale: int = 2
    model: str = "animevideov3"
    backend: str = "realesrgan"
    gpu_id: int = 0
    tile_size: int = 0  # 0 = auto (-t 0); try 64/128/256 on AMD iGPU if tile seams
    cugan_noise: int = -1
    cugan_syncgap: int = 3
    cugan_weights: str = "models-se"

    @property
    def ncnn_model_name(self) -> str:
        return NCNN_MODELS.get(self.model, "realesr-animevideov3")

    @property
    def effective_scale(self) -> int:
        return resolve_upscale_scale(self.backend, self.model, self.scale)

    @property
    def normalized_backend(self) -> str:
        return normalize_upscale_backend(self.backend)


@dataclass
class HarmonizeConfig:
    enabled: bool = True
    target_width: int = 1920
    target_height: int = 1080
    mode: str = "auto"
    blur_sigma: int = 60
    vignette_strength: float = 0.7


@dataclass
class AnimationConfig:
    mode: str = "opencv_zoom"
    duration: float = 3.0
    fps: int = 24
    intensity: float = 0.3
    depthflow_animation: str = "zoom"
    tpsmm_driving_video: str = ""
    tpsmm_mode: str = "relative"  # relative | standard


@dataclass
class RenderConfig:
    concat_panels: bool = True
    storyboard_name: str = "storyboard.mp4"
    codec: str = "libx264"
    pix_fmt: str = "yuv420p"


@dataclass
class AnimPaths:
    esrgan_exe: pathlib.Path
    ffmpeg_exe: str


@dataclass
class AnimConfig:
    upscale: UpscaleConfig
    harmonize: HarmonizeConfig
    animation: AnimationConfig
    render: RenderConfig
    paths: AnimPaths


_anim_config: Optional[AnimConfig] = None


def _resolve_esrgan_exe(raw: Any) -> pathlib.Path:
    if raw:
        return pathlib.Path(str(raw))
    return MODELS_ANIM / "upscale" / "realesrgan-ncnn-vulkan.exe"


def resolve_ffmpeg_exe(raw: Any = None) -> str:
    if raw:
        p = pathlib.Path(str(raw))
        if p.is_file():
            return str(p)
    env = shutil.which("ffmpeg")
    if env:
        return env
    bundled = MODELS_ANIM / "ffmpeg" / "bin" / "ffmpeg.exe"
    if bundled.is_file():
        return str(bundled)
    return "ffmpeg"


def load_anim_config(path: Optional[pathlib.Path] = None) -> AnimConfig:
    global _anim_config
    cfg_path = path or DEFAULT_ANIM_CONFIG_PATH
    raw: dict[str, Any] = {}
    if cfg_path.is_file():
        with open(cfg_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    up = raw.get("upscale") or {}
    hm = raw.get("harmonize") or {}
    an = raw.get("animation") or {}
    rn = raw.get("render") or {}
    pt = raw.get("paths") or {}

    _anim_config = AnimConfig(
        upscale=UpscaleConfig(
            enabled=bool(up.get("enabled", True)),
            scale=int(up.get("scale", 2)),
            model=str(up.get("model", "animevideov3")),
            backend=normalize_upscale_backend(str(up.get("backend", "realesrgan"))),
            gpu_id=int(up.get("gpu_id", 0)),
            tile_size=int(up.get("tile_size", 0)),
            cugan_noise=int(up.get("cugan_noise", -1)),
            cugan_syncgap=int(up.get("cugan_syncgap", 3)),
            cugan_weights=str(up.get("cugan_weights", "models-se")),
        ),
        harmonize=HarmonizeConfig(
            enabled=bool(hm.get("enabled", True)),
            target_width=int(hm.get("target_width", 1920)),
            target_height=int(hm.get("target_height", 1080)),
            mode=str(hm.get("mode", "auto")),
            blur_sigma=int(hm.get("blur_sigma", 60)),
            vignette_strength=float(hm.get("vignette_strength", 0.7)),
        ),
        animation=AnimationConfig(
            mode=str(an.get("mode", "opencv_zoom")),
            duration=float(an.get("duration", 3.0)),
            fps=int(an.get("fps", 24)),
            intensity=float(an.get("intensity", 0.3)),
            depthflow_animation=str(an.get("depthflow_animation", "zoom")),
            tpsmm_driving_video=str(an.get("tpsmm_driving_video", "")),
            tpsmm_mode=str(an.get("tpsmm_mode", "relative")),
        ),
        render=RenderConfig(
            concat_panels=bool(rn.get("concat_panels", True)),
            storyboard_name=str(rn.get("storyboard_name", "storyboard.mp4")),
            codec=str(rn.get("codec", "libx264")),
            pix_fmt=str(rn.get("pix_fmt", "yuv420p")),
        ),
        paths=AnimPaths(
            esrgan_exe=_resolve_esrgan_exe(pt.get("esrgan_exe")),
            ffmpeg_exe=resolve_ffmpeg_exe(pt.get("ffmpeg_exe")),
        ),
    )
    return _anim_config


def get_anim_config() -> AnimConfig:
    if _anim_config is None:
        return load_anim_config()
    return _anim_config


def save_anim_config(
    cfg: Optional[AnimConfig] = None, path: Optional[pathlib.Path] = None
) -> None:
    """Write anim settings to config_animate.yaml."""
    cfg = cfg or get_anim_config()
    cfg_path = path or DEFAULT_ANIM_CONFIG_PATH
    data = {
        "upscale": {
            "enabled": cfg.upscale.enabled,
            "scale": cfg.upscale.scale,
            "model": cfg.upscale.model,
            "backend": cfg.upscale.normalized_backend,
            "gpu_id": cfg.upscale.gpu_id,
            "tile_size": cfg.upscale.tile_size,
            "cugan_noise": cfg.upscale.cugan_noise,
            "cugan_syncgap": cfg.upscale.cugan_syncgap,
            "cugan_weights": cfg.upscale.cugan_weights,
        },
        "harmonize": {
            "enabled": cfg.harmonize.enabled,
            "target_width": cfg.harmonize.target_width,
            "target_height": cfg.harmonize.target_height,
            "mode": cfg.harmonize.mode,
            "blur_sigma": cfg.harmonize.blur_sigma,
            "vignette_strength": cfg.harmonize.vignette_strength,
        },
        "animation": {
            "mode": cfg.animation.mode,
            "duration": cfg.animation.duration,
            "fps": cfg.animation.fps,
            "intensity": cfg.animation.intensity,
            "depthflow_animation": cfg.animation.depthflow_animation,
            "tpsmm_driving_video": cfg.animation.tpsmm_driving_video,
            "tpsmm_mode": cfg.animation.tpsmm_mode,
        },
        "render": {
            "concat_panels": cfg.render.concat_panels,
            "storyboard_name": cfg.render.storyboard_name,
            "codec": cfg.render.codec,
            "pix_fmt": cfg.render.pix_fmt,
        },
        "paths": {
            "esrgan_exe": None,
            "ffmpeg_exe": None,
        },
    }
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
