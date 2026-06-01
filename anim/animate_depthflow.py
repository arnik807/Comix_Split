"""DepthFlow parallax animation (DepthScene CLI / in-process)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List

from utils.anim_config import AnimConfig, get_anim_config, resolve_ffmpeg_exe


def _depthflow_env(cfg: AnimConfig | None) -> dict[str, str]:
    """Env for DepthFlow on Windows (no Rich box-drawing, headless GL)."""
    env = os.environ.copy()
    env.setdefault("NO_COLOR", "1")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("WINDOW_BACKEND", "headless")
    env.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

    ffmpeg = resolve_ffmpeg_exe(
        cfg.paths.ffmpeg_exe if cfg and cfg.paths else None
    )
    ff_dir = str(Path(ffmpeg).parent)
    if ff_dir not in env.get("PATH", ""):
        env["PATH"] = ff_dir + os.pathsep + env.get("PATH", "")
    return env


def _map_intensity(value: float) -> str:
    """Map config 0..1 intensity to DepthFlow preset scale (~0..2)."""
    return str(max(0.15, min(2.0, float(value) * 2.5)))


def _build_cli_argv(
    input_path: Path,
    output_path: Path,
    cfg: AnimConfig,
) -> List[str]:
    anim = cfg.animation
    preset = (anim.depthflow_animation or "zoom").strip().lower()
    if preset not in ("zoom", "dolly"):
        preset = "zoom"

    return [
        "input",
        "--image",
        str(input_path.resolve()),
        preset,
        "--intensity",
        _map_intensity(anim.intensity),
        "main",
        "--render",
        "--output",
        str(output_path.resolve()),
        "--time",
        str(float(anim.duration)),
        "--fps",
        str(int(anim.fps)),
    ]


def _run_inprocess(argv: List[str], env: dict[str, str]) -> None:
    for key, val in env.items():
        os.environ[key] = val
    from depthflow.scene import DepthScene

    DepthScene().cli(*argv)


def _run_subprocess(argv: List[str], env: dict[str, str], cwd: str) -> str:
    cmd = [sys.executable, "-m", "depthflow", *argv]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
        cwd=cwd,
        env=env,
    )
    if result.returncode == 0:
        return ""
    parts = [result.stderr or "", result.stdout or ""]
    text = "\n".join(p for p in parts if p.strip()).strip()
    for needle in ("No such command", "Error", "Traceback", "RuntimeError"):
        if needle in text:
            return text
    return text or f"exit code {result.returncode}"


def _tail_error(msg: str, limit: int = 1200) -> str:
    msg = msg.strip()
    if len(msg) <= limit:
        return msg
    return msg[-limit:]


def render_depthflow(
    input_path: str | Path,
    output_path: str | Path,
    cfg: AnimConfig | None = None,
) -> Path:
    cfg = cfg or get_anim_config()
    inp = Path(input_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not inp.is_file():
        raise FileNotFoundError(f"Input not found: {inp}")

    argv = _build_cli_argv(inp, out, cfg)
    env = _depthflow_env(cfg)
    cwd = str(inp.parent.resolve())

    last_err = ""
    try:
        _run_inprocess(argv, env)
        if out.is_file():
            return out
        last_err = "DepthFlow finished but output file was not created"
    except Exception as exc:
        last_err = str(exc)

    last_err = _run_subprocess(argv, env, cwd) or last_err
    if out.is_file():
        return out

    raise RuntimeError(
        f"DepthFlow failed for {inp.name}. {_tail_error(last_err or 'unknown')}"
    )
