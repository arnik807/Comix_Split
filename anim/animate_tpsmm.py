"""TPSMM motion transfer (ONNX, CPU). Based on instant-high TPSMM-ONNX demo."""

from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from anim.render import frames_to_video
from utils.anim_config import AnimConfig, MODELS_ANIM

TPSMM_DIR = MODELS_ANIM / "tpsmm"
SIZE = 256


def resolve_tpsmm_paths() -> tuple[Path, Path]:
    kp = TPSMM_DIR / "kp_detector_int8.onnx"
    if not kp.is_file():
        kp = TPSMM_DIR / "kp_detector.onnx"
    rel = TPSMM_DIR / "tpsmm_rel_int8.onnx"
    if not rel.is_file():
        rel = TPSMM_DIR / "tpsmm_rel.onnx"
    missing = [p for p in (kp, rel) if not p.is_file()]
    if missing:
        names = ", ".join(p.name for p in missing)
        raise FileNotFoundError(
            f"TPSMM ONNX не найдены ({names}). "
            "См. scripts/MODELS_SETUP_GUIDE.md и scripts/download_animate_models.ps1"
        )
    return kp, rel


def _keypoint_area(kp: np.ndarray) -> float:
    pts = kp.reshape(-1, 2)
    w = float(pts[:, 0].max() - pts[:, 0].min())
    h = float(pts[:, 1].max() - pts[:, 1].min())
    return max(w * h, 1e-6)


def relative_kp(
    kp_source: np.ndarray,
    kp_driving: np.ndarray,
    kp_driving_initial: np.ndarray,
) -> np.ndarray:
    adapt = np.sqrt(_keypoint_area(kp_source) / _keypoint_area(kp_driving_initial))
    return (kp_driving - kp_driving_initial) * adapt + kp_source


def _prep_frame_bgr(frame_bgr: np.ndarray) -> np.ndarray:
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (SIZE, SIZE))
    x = rgb.astype(np.float32) / 255.0
    return np.transpose(x[np.newaxis], (0, 3, 1, 2))


def _run_kp(session: ort.InferenceSession, tensor: np.ndarray) -> np.ndarray:
    name_in = session.get_inputs()[0].name
    name_out = session.get_outputs()[0].name
    return session.run([name_out], {name_in: tensor})[0]


def _run_tpsmm(
    session: ort.InferenceSession,
    kp_source: np.ndarray,
    source: np.ndarray,
    kp_norm: np.ndarray,
    driving: np.ndarray,
) -> np.ndarray:
    ins = session.get_inputs()
    ort_in = {
        ins[0].name: kp_source,
        ins[1].name: source,
        ins[2].name: kp_norm,
        ins[3].name: driving,
    }
    out = session.run([session.get_outputs()[0].name], ort_in)[0]
    im = np.transpose(out.squeeze(), (1, 2, 0))
    im = np.clip(im, 0.0, 1.0)
    bgr = cv2.cvtColor((im * 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
    return bgr


def estimate_tpsmm_seconds(num_frames: int) -> float:
    """Rough CPU estimate for UI warning (~1.5 s/frame)."""
    return max(5.0, num_frames * 1.5)


def render_tpsmm(
    source_path: Path,
    output_path: Path,
    cfg: AnimConfig,
    driving_video: Path | None = None,
) -> None:
    driving_path = driving_video
    if driving_path is None:
        raw = (cfg.animation.tpsmm_driving_video or "").strip()
        if not raw:
            raise ValueError(
                "Для mode=tpsmm укажите driving video (config animation.tpsmm_driving_video)"
            )
        driving_path = Path(raw)
    if not driving_path.is_file():
        raise FileNotFoundError(f"Driving video не найден: {driving_path}")

    kp_path, tpsmm_path = resolve_tpsmm_paths()
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    providers = ["CPUExecutionProvider"]
    kp_sess = ort.InferenceSession(str(kp_path), sess_options=opts, providers=providers)
    tps_sess = ort.InferenceSession(str(tpsmm_path), sess_options=opts, providers=providers)

    source_bgr = cv2.imdecode(
        np.fromfile(str(source_path), dtype=np.uint8), cv2.IMREAD_COLOR
    )
    if source_bgr is None:
        raise RuntimeError(f"Cannot read source image: {source_path}")

    out_h, out_w = source_bgr.shape[:2]
    source_t = _prep_frame_bgr(source_bgr)
    kp_source = _run_kp(kp_sess, source_t)

    cap = cv2.VideoCapture(str(driving_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open driving video: {driving_path}")

    max_frames = max(1, int(cfg.animation.duration * cfg.animation.fps))
    tpsmm_mode = (cfg.animation.tpsmm_mode or "relative").strip().lower()
    if tpsmm_mode not in ("standard", "relative"):
        tpsmm_mode = "relative"

    ret, first = cap.read()
    if not ret:
        cap.release()
        raise RuntimeError("Driving video has no frames")
    kp_driving_initial = _run_kp(kp_sess, _prep_frame_bgr(first))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    frames: list[np.ndarray] = []
    t0 = time.perf_counter()
    for _ in range(max_frames):
        ret, drv_bgr = cap.read()
        if not ret:
            break
        driving_t = _prep_frame_bgr(drv_bgr)
        kp_driving = _run_kp(kp_sess, driving_t)
        if tpsmm_mode == "standard":
            kp_norm = kp_driving
        else:
            kp_norm = relative_kp(kp_source, kp_driving, kp_driving_initial)
        frame = _run_tpsmm(tps_sess, kp_source, source_t, kp_norm, driving_t)
        if (frame.shape[1], frame.shape[0]) != (out_w, out_h):
            frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
        frames.append(frame)

    cap.release()
    if not frames:
        raise RuntimeError("TPSMM produced no frames")

    elapsed = time.perf_counter() - t0
    print(
        f"  TPSMM: {len(frames)} frames, {elapsed:.1f}s "
        f"({elapsed / len(frames):.2f}s/frame)",
        flush=True,
    )
    frames_to_video(frames, output_path, fps=cfg.animation.fps, cfg=cfg)
