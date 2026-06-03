"""
Benchmark NCNN upscale backends (Real-ESRGAN, Real-CUGAN, SPAN).

Uses production path anim.upscale.upscale_image.

Usage:
    python scripts/benchmark_upscale.py
    python scripts/benchmark_upscale.py --quick
    python scripts/benchmark_upscale.py --backends realesrgan,span
    python scripts/benchmark_upscale.py --input exam_img/standart_split/test_page/001_p001_panel.png
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import cv2
    import numpy as np

    from anim.io_utils import imread as _imread_bgr
except ImportError:
    cv2 = None
    np = None
    _imread_bgr = None

from anim.upscale import upscale_image  # noqa: E402
from utils.anim_config import AnimConfig, UpscaleConfig, get_anim_config  # noqa: E402
from utils.models_registry import check_backend  # noqa: E402

DEFAULT_INPUTS = [
    ROOT / "exam_img" / "standart_split" / "test_page" / "001_p001_panel.png",
    ROOT / "test_page.jpg",
]


@dataclass
class BenchCase:
    backend: str
    model: str
    scale: int
    gpu_id: int = 0
    tile: int = 0
    cugan_noise: int = -1
    cugan_syncgap: int = 3

    @property
    def tag(self) -> str:
        gpu = "gpu0" if self.gpu_id == 0 else f"cpu{self.gpu_id}"
        t = f"_t{self.tile}" if self.tile else ""
        return f"{self.backend}_{self.model}_s{self.scale}_{gpu}{t}"


def find_input(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.is_file():
            p = ROOT / explicit
        if p.is_file():
            return p
        raise FileNotFoundError(f"Input not found: {explicit}")
    for cand in DEFAULT_INPUTS:
        if cand.is_file():
            return cand
    raise FileNotFoundError("No benchmark input image; pass --input path/to/panel.png")


def grid_artifact_score(path: Path, block: int = 64) -> float | None:
    """Higher score ≈ more tile-boundary discontinuity (scrambled NCNN output)."""
    if cv2 is None or np is None or _imread_bgr is None or not path.is_file():
        return None
    img = _imread_bgr(path)
    if img is None:
        return None
    h, w = img.shape[:2]
    if h < block * 2 or w < block * 2:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    seams: list[float] = []
    for x in range(block, w, block):
        seams.append(float(np.mean(np.abs(gray[:, x - 1] - gray[:, x]))))
    for y in range(block, h, block):
        seams.append(float(np.mean(np.abs(gray[y - 1, :] - gray[y, :]))))
    return float(np.mean(seams)) if seams else None


def classify(score: float | None, ok_file: bool) -> str:
    if not ok_file:
        return "FAIL"
    if score is None:
        return "OK?"
    if score >= 38.0:
        return "BAD"
    if score >= 28.0:
        return "WARN"
    return "OK"


def _cfg_for_case(case: BenchCase, base: AnimConfig) -> AnimConfig:
    up = UpscaleConfig(
        enabled=True,
        scale=case.scale,
        model=case.model,
        backend=case.backend,
        gpu_id=case.gpu_id,
        tile_size=case.tile,
        cugan_noise=case.cugan_noise,
        cugan_syncgap=case.cugan_syncgap,
    )
    return AnimConfig(
        upscale=up,
        harmonize=base.harmonize,
        animation=base.animation,
        render=base.render,
        paths=base.paths,
    )


def run_case(inp: Path, out: Path, case: BenchCase, base_cfg: AnimConfig) -> tuple[float, str]:
    out.parent.mkdir(parents=True, exist_ok=True)
    cfg = _cfg_for_case(case, base_cfg)
    t0 = time.perf_counter()
    try:
        upscale_image(inp, out, cfg)
        elapsed = time.perf_counter() - t0
        score = grid_artifact_score(out)
        return elapsed, classify(score, out.is_file())
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        return elapsed, f"FAIL ({str(exc)[:72]})"


def build_cases(quick: bool, backends_filter: list[str] | None) -> list[BenchCase]:
    want = set(backends_filter) if backends_filter else None
    cases: list[BenchCase] = []

    def add(case: BenchCase) -> None:
        if want and case.backend not in want:
            return
        if not check_backend(case.backend).installed:
            return
        cases.append(case)

    if quick:
        add(BenchCase("realesrgan", "animevideov3", 2))
        add(BenchCase("realesrgan", "animevideov3", 4))
        add(BenchCase("realesrgan", "anime_6B", 4))
        add(BenchCase("realcugan", "cugan_se", 2))
        add(BenchCase("span", "span_x4_ch48", 4))
        add(BenchCase("span", "span_x2_ch48", 2))
        return cases

    for g in (0, -1):
        for t in (0, 128):
            add(BenchCase("realesrgan", "animevideov3", 2, g, t))
            add(BenchCase("realesrgan", "animevideov3", 4, g, t))
            add(BenchCase("realesrgan", "anime_6B", 4, g, t))
            add(BenchCase("realcugan", "cugan_se", 2, g, t))
            add(BenchCase("realcugan", "cugan_se", 4, g, t))
            add(BenchCase("span", "span_x2_ch48", 2, g, t))
            add(BenchCase("span", "span_x4_ch48", 4, g, t))
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark NCNN upscale backends")
    parser.add_argument("--input", help="Panel PNG/JPG")
    parser.add_argument("--out-dir", default="exam_img/_upscale_benchmark")
    parser.add_argument("--quick", action="store_true", help="Smoke: one case per backend/model")
    parser.add_argument(
        "--backends",
        help="Comma-separated: realesrgan,realcugan,span (default: all installed)",
    )
    args = parser.parse_args()

    backends_filter = None
    if args.backends:
        backends_filter = [b.strip() for b in args.backends.split(",") if b.strip()]

    if not check_backend("realesrgan").installed:
        print("[FAIL] realesrgan not installed (download_animate_models.ps1)", file=sys.stderr)
        return 1

    inp = find_input(args.input)
    out_root = ROOT / args.out_dir
    out_root.mkdir(parents=True, exist_ok=True)
    cases = build_cases(args.quick, backends_filter)
    if not cases:
        print("[FAIL] No benchmark cases (install backends or fix --backends)", file=sys.stderr)
        return 1

    base_cfg = get_anim_config()

    print(f"Input: {inp}")
    print(f"Output: {out_root}")
    print(f"Cases: {len(cases)}")
    print()
    print(
        f"{'Backend':<12} {'Model':<18} {'S':>2} {'GPU':>4} {'T':>4} "
        f"{'Time':>7} {'Grid':>6} {'Status':<14} Output"
    )
    print("-" * 110)

    for case in cases:
        out = out_root / f"{case.tag}.png"
        elapsed, status = run_case(inp, out, case, base_cfg)
        score = grid_artifact_score(out) if out.is_file() else None
        grid_s = f"{score:.1f}" if score is not None else "—"
        gpu_lbl = "0" if case.gpu_id == 0 else str(case.gpu_id)
        print(
            f"{case.backend:<12} {case.model:<18} {case.scale:>2} {gpu_lbl:>4} {case.tile:>4} "
            f"{elapsed:>6.1f}s {grid_s:>6} {status:<14} {out.name}"
        )

    print()
    print("Legend: Grid = seam heuristic at 64px (mainly Real-ESRGAN tiles). BAD>=38 often scramble.")
    print("Compare PNGs visually for CUGAN/SPAN quality.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
