"""Upscale panels via NCNN Vulkan backends (Real-ESRGAN, Real-CUGAN, SPAN)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from utils.anim_config import (
    MODELS_ANIM,
    AnimConfig,
    X4_ONLY_UPSCALE_MODEL,
    cugan_model_path,
    get_anim_config,
    normalize_upscale_backend,
    resolve_upscale_scale,
    span_ncnn_name,
)
from utils.models_registry import check_backend, format_install_hint

BACKEND_EXE = {
    "realesrgan": MODELS_ANIM / "upscale" / "realesrgan-ncnn-vulkan.exe",
    "realcugan": MODELS_ANIM / "upscale" / "realcugan" / "realcugan-ncnn-vulkan.exe",
    "span": MODELS_ANIM / "upscale" / "span" / "span-ncnn-vulkan.exe",
}

BACKEND_CWD = {
    "realesrgan": MODELS_ANIM / "upscale",
    "realcugan": MODELS_ANIM / "upscale" / "realcugan",
    "span": MODELS_ANIM / "upscale" / "span",
}


def ensure_upscale_ready(cfg: AnimConfig | None = None) -> str:
    """Return normalized backend id or raise FileNotFoundError with install hint."""
    cfg = cfg or get_anim_config()
    backend = cfg.upscale.normalized_backend
    st = check_backend(backend)
    if not st.installed:
        raise FileNotFoundError(format_install_hint(st))
    return backend


def _run_ncnn(cmd: list[str], cwd: Path | None, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=str(cwd) if cwd else None,
    )


def _upscale_realesrgan(inp: Path, out: Path, cfg: AnimConfig) -> None:
    up = cfg.upscale
    exe = cfg.paths.esrgan_exe if cfg.paths.esrgan_exe.is_file() else BACKEND_EXE["realesrgan"]
    if not exe.is_file():
        raise FileNotFoundError(f"Real-ESRGAN not found: {exe}")

    scale = resolve_upscale_scale(up.backend, up.model, up.scale)
    if up.model == X4_ONLY_UPSCALE_MODEL and int(up.scale) != scale:
        print(
            f"[upscale] WARNING: модель {up.model} (realesrgan-x4plus-anime): "
            f"запрошен scale={up.scale}, используем scale={scale}.",
            file=sys.stderr,
        )

    cmd = [
        str(exe),
        "-i",
        str(inp),
        "-o",
        str(out),
        "-n",
        up.ncnn_model_name,
        "-s",
        str(scale),
        "-g",
        str(up.gpu_id),
        "-t",
        str(max(0, int(up.tile_size))),
    ]
    result = _run_ncnn(cmd, BACKEND_CWD["realesrgan"])
    if result.returncode != 0 or not out.is_file():
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Real-ESRGAN failed ({inp.name}): {err}")


def _upscale_realcugan(inp: Path, out: Path, cfg: AnimConfig) -> None:
    up = cfg.upscale
    exe = BACKEND_EXE["realcugan"]
    cwd = BACKEND_CWD["realcugan"]
    scale = resolve_upscale_scale(up.backend, up.model, up.scale)
    mpath = cugan_model_path(up.model, up.cugan_weights)
    noise = max(-1, min(3, int(up.cugan_noise)))
    syncgap = max(0, min(3, int(up.cugan_syncgap)))

    cmd = [
        str(exe),
        "-i",
        str(inp.resolve()),
        "-o",
        str(out.resolve()),
        "-s",
        str(scale),
        "-n",
        str(noise),
        "-m",
        mpath,
        "-c",
        str(syncgap),
        "-g",
        str(up.gpu_id),
        "-t",
        str(max(0, int(up.tile_size))),
    ]
    result = _run_ncnn(cmd, cwd)
    if result.returncode != 0 or not out.is_file():
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Real-CUGAN failed ({inp.name}): {err}")


def _upscale_span(inp: Path, out: Path, cfg: AnimConfig) -> None:
    up = cfg.upscale
    exe = BACKEND_EXE["span"]
    cwd = BACKEND_CWD["span"]
    scale = resolve_upscale_scale(up.backend, up.model, up.scale)
    name = span_ncnn_name(up.model)

    cmd = [
        str(exe),
        "-m",
        "models",
        "-n",
        name,
        "-s",
        str(scale),
        "-i",
        str(inp.resolve()),
        "-o",
        str(out.resolve()),
        "-g",
        str(up.gpu_id),
        "-t",
        str(max(0, int(up.tile_size))),
    ]
    result = _run_ncnn(cmd, cwd)
    if result.returncode != 0 or not out.is_file():
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"SPAN failed ({inp.name}): {err}")


def upscale_image(
    input_path: str | Path,
    output_path: str | Path,
    cfg: AnimConfig | None = None,
) -> Path:
    cfg = cfg or get_anim_config()
    backend = ensure_upscale_ready(cfg)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    inp = Path(input_path)
    if not inp.is_file():
        raise FileNotFoundError(f"Input image not found: {inp}")

    if backend == "realcugan":
        _upscale_realcugan(inp, out, cfg)
    elif backend == "span":
        _upscale_span(inp, out, cfg)
    else:
        _upscale_realesrgan(inp, out, cfg)

    return out


def upscale_folder(
    input_dir: str | Path,
    output_dir: str | Path,
    cfg: AnimConfig | None = None,
) -> list[Path]:
    from anim.io_utils import list_images

    cfg = cfg or get_anim_config()
    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    results: list[Path] = []
    backend = ensure_upscale_ready(cfg)
    for src in list_images(input_dir):
        dst = out_root / src.name
        results.append(upscale_image(src, dst, cfg))
        print(f"[upscale/{backend}] {src.name}", file=sys.stderr)
    return results
