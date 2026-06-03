"""
Verify NCNN Vulkan upscale backends (Real-ESRGAN, Real-CUGAN, SPAN).

Usage:
    python scripts/verify_upscale_backends.py
    python scripts/verify_upscale_backends.py --backend realcugan
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.models_registry import check_all_backends, check_backend, resolve_path  # noqa: E402

DEFAULT_INPUTS = [
    ROOT / "exam_img" / "standart_split" / "test_page" / "001_p001_panel.png",
    ROOT / "test_page.jpg",
]

GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"


def find_input() -> Path:
    for p in DEFAULT_INPUTS:
        if p.is_file():
            return p
    raise FileNotFoundError("No test panel; add exam_img/.../001_p001_panel.png")


def run_cmd(
    cmd: list[str],
    timeout: int = 300,
    cwd: Path | None = None,
) -> tuple[bool, str, float]:
    t0 = time.perf_counter()
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(cwd or ROOT),
        )
        elapsed = time.perf_counter() - t0
        ok = r.returncode == 0
        err = (r.stderr or r.stdout or "").strip()
        return ok, err, elapsed
    except subprocess.TimeoutExpired:
        return False, "timeout", time.perf_counter() - t0


def verify_realesrgan(inp: Path, out_dir: Path) -> bool:
    exe = resolve_path("models/anim/upscale/realesrgan-ncnn-vulkan.exe")
    out = out_dir / "realesr_v3_x2.png"
    cmd = [
        str(exe),
        "-i",
        str(inp),
        "-o",
        str(out),
        "-n",
        "realesr-animevideov3",
        "-s",
        "2",
        "-g",
        "0",
    ]
    ok, err, sec = run_cmd(cmd)
    if ok and out.is_file():
        print(f"  {GREEN}[OK]{RESET}   realesrgan animevideov3 x2 ({sec:.1f}s)")
        return True
    print(f"  {RED}[FAIL]{RESET} realesrgan: {err[:200]}")
    return False


def verify_realcugan(inp: Path, out_dir: Path) -> bool:
    base = resolve_path("models/anim/upscale/realcugan")
    exe = base / "realcugan-ncnn-vulkan.exe"
    out = out_dir / "realcugan_x2.png"
    models_se = base / "models-se"
    model_path = "models-se" if models_se.is_dir() else "models-pro"
    cmd = [
        str(exe),
        "-i",
        str(inp),
        "-o",
        str(out),
        "-s",
        "2",
        "-n",
        "-1",
        "-m",
        model_path,
        "-g",
        "0",
    ]
    ok, err, sec = run_cmd(cmd, cwd=base)
    if ok and out.is_file():
        print(f"  {GREEN}[OK]{RESET}   realcugan {model_path} x2 ({sec:.1f}s)")
        return True
    print(f"  {RED}[FAIL]{RESET} realcugan: {err[:200]}")
    return False


def verify_span(inp: Path, out_dir: Path) -> bool:
    base = resolve_path("models/anim/upscale/span")
    exe = base / "span-ncnn-vulkan.exe"
    out = out_dir / "span_x4.png"
    cmd = [
        str(exe),
        "-m",
        "models",
        "-n",
        "spanx4_ch48",
        "-s",
        "4",
        "-i",
        str(inp),
        "-o",
        str(out),
        "-g",
        "0",
    ]
    ok, err, sec = run_cmd(cmd, cwd=base)
    if ok and out.is_file():
        print(f"  {GREEN}[OK]{RESET}   span spanx4_ch48 x4 ({sec:.1f}s)")
        return True
    print(f"  {RED}[FAIL]{RESET} span: {err[:200]}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify upscale NCNN backends")
    parser.add_argument(
        "--backend",
        choices=["realesrgan", "realcugan", "span", "all"],
        default="all",
    )
    args = parser.parse_args()

    print(f"\n{CYAN}==> Registry install check{RESET}")
    backends = check_all_backends()
    for st in backends:
        if st.installed:
            print(f"  {GREEN}[OK]{RESET}   {st.backend_id}: {st.exe.name}")
        else:
            print(f"  {RED}[FAIL]{RESET} {st.backend_id}: missing {st.missing}")

    inp = find_input()
    out_dir = ROOT / "exam_img" / "_verify_upscale"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n{CYAN}==> Smoke upscale (input: {inp.name}){RESET}")

    runners = {
        "realesrgan": verify_realesrgan,
        "realcugan": verify_realcugan,
        "span": verify_span,
    }
    targets = list(runners.keys()) if args.backend == "all" else [args.backend]

    results: list[bool] = []
    for bid in targets:
        st = check_backend(bid)
        if not st.installed:
            print(f"  {RED}[SKIP]{RESET} {bid}: not installed")
            results.append(False)
            continue
        results.append(runners[bid](inp, out_dir))

    print("")
    if all(results):
        print(f"{GREEN}All requested backends passed.{RESET}")
        return 0
    print(f"{RED}Some checks failed.{RESET}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
