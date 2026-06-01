"""Render frames to MP4 and concat clips via ffmpeg."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import List

import cv2
import numpy as np

from utils.anim_config import AnimConfig, get_anim_config, resolve_ffmpeg_exe


def _ffmpeg(cfg: AnimConfig | None = None) -> str:
    if cfg is not None:
        return cfg.paths.ffmpeg_exe
    return resolve_ffmpeg_exe()


def frames_to_video(
    frames: List[np.ndarray],
    output_path: str | Path,
    fps: int = 24,
    cfg: AnimConfig | None = None,
) -> Path:
    if not frames:
        raise ValueError("No frames to encode")
    cfg = cfg or get_anim_config()
    ffmpeg = _ffmpeg(cfg)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    h, w = frames[0].shape[:2]

    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-s",
        f"{w}x{h}",
        "-pix_fmt",
        "bgr24",
        "-r",
        str(fps),
        "-i",
        "-",
        "-an",
        "-vcodec",
        cfg.render.codec,
        "-pix_fmt",
        cfg.render.pix_fmt,
        str(out),
    ]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None
    for frame in frames:
        if frame.shape[0] != h or frame.shape[1] != w:
            frame = cv2.resize(frame, (w, h))
        proc.stdin.write(frame.astype(np.uint8).tobytes())
    proc.stdin.close()
    stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
    code = proc.wait()
    if code != 0 or not out.is_file():
        raise RuntimeError(f"ffmpeg encode failed: {stderr[-500:]}")
    return out


def concat_videos(
    video_paths: List[str | Path],
    output_path: str | Path,
    cfg: AnimConfig | None = None,
) -> Path:
    cfg = cfg or get_anim_config()
    ffmpeg = _ffmpeg(cfg)
    paths = [Path(p) for p in video_paths if Path(p).is_file()]
    if not paths:
        raise ValueError("No video files to concat")
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".txt",
        delete=False,
        encoding="utf-8",
    ) as f:
        for p in paths:
            safe = str(p.resolve()).replace("'", "'\\''")
            f.write(f"file '{safe}'\n")
        list_path = f.name

    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        list_path,
        "-c",
        "copy",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    Path(list_path).unlink(missing_ok=True)
    if result.returncode != 0 or not out.is_file():
        raise RuntimeError(f"ffmpeg concat failed: {(result.stderr or '')[-500:]}")
    return out
