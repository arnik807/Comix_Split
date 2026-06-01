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


@dataclass
class UpscaleConfig:
    enabled: bool = True
    scale: int = 2
    model: str = "animevideov3"
    backend: str = "ncnn_vulkan"
    gpu_id: int = 0

    @property
    def ncnn_model_name(self) -> str:
        return NCNN_MODELS.get(self.model, "realesr-animevideov3")


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
            backend=str(up.get("backend", "ncnn_vulkan")),
            gpu_id=int(up.get("gpu_id", 0)),
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
