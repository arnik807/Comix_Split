"""
Export leoxs22/manga-panel-detector-yolo26n to ONNX INT8 for ComicSplit.

Requires: pip install ultralytics onnxruntime

Usage (from repo root):
    python scripts/export_manga_yolo.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
HF_PT = "https://huggingface.co/leoxs22/manga-panel-detector-yolo26n/resolve/main/manga_panel_detector_fp32.pt"
PT_PATH = MODELS / "yolo_manga.pt"
ONNX_PATH = MODELS / "yolo_manga.onnx"
INT8_PATH = MODELS / "yolo_manga_int8.onnx"
# Ultralytics on Windows ломает пути с кириллицей — экспорт только здесь
ASCII_WORK = Path("C:/tmp_comicsplit_manga")


def download_pt() -> Path:
    MODELS.mkdir(parents=True, exist_ok=True)
    if PT_PATH.is_file() and PT_PATH.stat().st_size > 1_000_000:
        print(f"[SKIP] {PT_PATH.name}")
        return PT_PATH
    print(f"Download {PT_PATH.name}...")
    import urllib.request

    urllib.request.urlretrieve(HF_PT, PT_PATH)
    return PT_PATH


def export_onnx(pt_path: Path) -> Path:
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("pip install ultralytics") from exc

    ASCII_WORK.mkdir(parents=True, exist_ok=True)
    work_pt = ASCII_WORK / "yolo_manga.pt"
    shutil.copy2(pt_path, work_pt)

    print("Export ONNX (640, simplify) [ASCII workdir]...")
    model = YOLO(str(work_pt))
    model.export(format="onnx", imgsz=640, simplify=True, opset=12)
    work_onnx = ASCII_WORK / "yolo_manga.onnx"
    if not work_onnx.is_file():
        raise FileNotFoundError(f"Export failed: {work_onnx}")

    MODELS.mkdir(parents=True, exist_ok=True)
    if ONNX_PATH.exists():
        ONNX_PATH.unlink()
    shutil.copy2(work_onnx, ONNX_PATH)
    print(f"[OK] {ONNX_PATH} ({ONNX_PATH.stat().st_size // 1024} KB)")
    return ONNX_PATH


def quantize_int8(src: Path, dst: Path) -> None:
    from onnxruntime.quantization import QuantType, quantize_dynamic

    print(f"Quantize -> {dst.name}...")
    tmp_root = Path("C:/tmp_quant_split")
    tmp_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=tmp_root) as tmp:
        tmp_src = Path(tmp) / src.name
        tmp_dst = Path(tmp) / dst.name
        shutil.copy2(src, tmp_src)
        quantize_dynamic(
            model_input=str(tmp_src),
            model_output=str(tmp_dst),
            weight_type=QuantType.QInt8,
            per_channel=False,
        )
        shutil.copy2(tmp_dst, dst)
    kb = dst.stat().st_size // 1024
    print(f"[OK] {dst.name} ({kb} KB)")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    pt = download_pt()
    export_onnx(pt)
    if INT8_PATH.is_file():
        INT8_PATH.unlink()
    quantize_int8(ONNX_PATH, INT8_PATH)
    print("\nDone. Set config.yaml: panel_detector: manga")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
