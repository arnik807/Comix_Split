"""Upscale panels via realesrgan-ncnn-vulkan."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from utils.anim_config import AnimConfig, get_anim_config


def upscale_image(
    input_path: str | Path,
    output_path: str | Path,
    cfg: AnimConfig | None = None,
) -> Path:
    cfg = cfg or get_anim_config()
    up = cfg.upscale
    exe = cfg.paths.esrgan_exe
    if not exe.is_file():
        raise FileNotFoundError(f"NCNN upscale not found: {exe}")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    inp = Path(input_path)
    if not inp.is_file():
        raise FileNotFoundError(f"Input image not found: {inp}")

    cmd = [
        str(exe),
        "-i",
        str(inp),
        "-o",
        str(out),
        "-n",
        up.ncnn_model_name,
        "-s",
        str(up.scale),
        "-g",
        str(up.gpu_id),
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    if result.returncode != 0 or not out.is_file():
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Upscale failed ({inp.name}): {err}")

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
    for src in list_images(input_dir):
        dst = out_root / src.name
        results.append(upscale_image(src, dst, cfg))
        print(f"[upscale] {src.name}", file=sys.stderr)
    return results
