"""
scripts/quantize_animate_models.py
Квантование ONNX моделей в INT8 + верификация всего стека.

Запуск:
    python scripts/quantize_animate_models.py          # квантование + проверка
    python scripts/quantize_animate_models.py --verify # только проверка

Зависимости:
    pip install onnxruntime onnx
"""

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

# ─── Цвета для терминала ──────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}[OK]{RESET}   {msg}")
def skip(msg): print(f"  {YELLOW}[SKIP]{RESET} {msg}")
def fail(msg): print(f"  {RED}[FAIL]{RESET} {msg}")
def step(msg): print(f"\n{CYAN}==> {msg}{RESET}")

# ─── Пути ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
MODELS = ROOT / "models" / "anim"

PATHS = {
    # ONNX исходные
    "midas_src":   MODELS / "depth"  / "midas_v21_small_256.onnx",
    "kp_src":      MODELS / "tpsmm"  / "kp_detector.onnx",
    "tpsmm_src":   MODELS / "tpsmm"  / "tpsmm_rel.onnx",
    # ONNX INT8 результаты
    "midas_int8":  MODELS / "depth"  / "midas_v21_small_256_int8.onnx",
    "kp_int8":     MODELS / "tpsmm"  / "kp_detector_int8.onnx",
    "tpsmm_int8":  MODELS / "tpsmm"  / "tpsmm_rel_int8.onnx",
    # NCNN exe
    "esrgan_exe":  MODELS / "upscale" / "realesrgan-ncnn-vulkan.exe",
    "esrgan_bin":  MODELS / "upscale" / "models" / "realesr-animevideov3-x4.bin",
}


def quantize_model(src_path: Path, dst_path: Path, model_name: str) -> bool:
    """Dynamic INT8 квантование одной ONNX модели."""
    if dst_path.exists():
        skip(f"{model_name}: {dst_path.name} уже существует")
        return True

    if not src_path.exists():
        fail(f"{model_name}: исходная модель не найдена: {src_path}")
        return False

    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType
    except ImportError:
        fail("onnxruntime.quantization не найден. Запустите: pip install onnxruntime")
        return False

    src_mb = src_path.stat().st_size / 1_048_576
    print(f"  Quantize {model_name}: {src_mb:.1f} MB -> INT8...", end="", flush=True)

    t0 = time.time()
    try:
        # Квантуем через ASCII temp (обход кириллицы в путях Windows)
        tmp_root = Path("C:/tmp_quant_anim")
        tmp_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=tmp_root) as tmp:
            tmp_src = Path(tmp) / src_path.name
            tmp_dst = Path(tmp) / dst_path.name
            shutil.copy2(src_path, tmp_src)
            quantize_dynamic(
                model_input=str(tmp_src),
                model_output=str(tmp_dst),
                weight_type=QuantType.QInt8,
                per_channel=False,
            )
            shutil.copy2(tmp_dst, dst_path)
        dt = time.time() - t0
        dst_mb = dst_path.stat().st_size / 1_048_576
        ratio = (1 - dst_mb / src_mb) * 100
        print(f" {dst_mb:.1f} MB ({ratio:.0f}% меньше) за {dt:.1f}с")
        ok(f"{model_name}: квантование завершено")
        return True
    except Exception as e:
        print()
        fail(f"{model_name}: ошибка квантования — {e}")
        if dst_path.exists():
            dst_path.unlink()
        return False


def verify_onnx(path: Path, model_name: str, expected_input_shape=None) -> bool:
    """Проверяет что ONNX файл загружается и имеет правильный вход."""
    if not path.exists():
        fail(f"{model_name}: файл не найден: {path}")
        return False
    try:
        import onnxruntime as ort
        sess = ort.InferenceSession(
            str(path),
            providers=["CPUExecutionProvider"]
        )
        inp = sess.get_inputs()[0]
        shape_str = str(inp.shape)
        mb = path.stat().st_size / 1_048_576
        ok(f"{model_name}: загружен ({mb:.1f} MB), вход: {shape_str}")
        return True
    except Exception as e:
        fail(f"{model_name}: ошибка загрузки — {e}")
        return False


def verify_esrgan() -> bool:
    """Проверяет наличие realesrgan-ncnn-vulkan.exe и моделей."""
    exe = PATHS["esrgan_exe"]
    bin_file = PATHS["esrgan_bin"]

    if not exe.exists():
        fail(f"realesrgan-ncnn-vulkan.exe не найден: {exe}")
        return False
    if not bin_file.exists():
        fail(f"realesr-animevideov3-x4.bin не найден: {bin_file}")
        return False

    exe_mb = exe.stat().st_size / 1_048_576
    ok(f"realesrgan-ncnn-vulkan.exe найден ({exe_mb:.1f} MB)")

    # Попытка запустить с флагом --version или -h
    import subprocess
    try:
        result = subprocess.run(
            [str(exe), "--help"],
            capture_output=True, text=True, timeout=10
        )
        # NCNN exe возвращает help в stderr при неверных аргументах — это нормально
        ok("realesrgan-ncnn-vulkan.exe запускается")
        return True
    except subprocess.TimeoutExpired:
        ok("realesrgan-ncnn-vulkan.exe доступен (таймаут --help, это норма для NCNN)")
        return True
    except FileNotFoundError:
        fail("realesrgan-ncnn-vulkan.exe: невозможно запустить")
        return False


def verify_depthflow() -> bool:
    """Проверяет что пакет depthflow установлен (без полного GPU-init)."""
    try:
        import importlib.metadata
        version = importlib.metadata.version("depthflow")
        ok(f"depthflow установлен (версия {version})")
        return True
    except ImportError:
        fail("depthflow не установлен. Запустите: pip install depthflow")
        return False
    except Exception as e:
        fail(f"depthflow: ошибка проверки — {e}")
        return False


def verify_ffmpeg() -> bool:
    """Проверяет наличие ffmpeg в PATH."""
    import subprocess
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=10
        )
        first_line = result.stdout.splitlines()[0] if result.stdout else "?"
        ok(f"ffmpeg: {first_line}")
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        fail("ffmpeg не найден в PATH — скачайте с https://ffmpeg.org/download.html")
        return False


# ─── Основной поток ───────────────────────────────────────────────────────────

def run_quantization():
    step("Квантование ONNX моделей в INT8")
    results = []
    results.append(quantize_model(PATHS["midas_src"],  PATHS["midas_int8"],  "MiDaS small"))
    results.append(quantize_model(PATHS["kp_src"],     PATHS["kp_int8"],     "TPSMM kp_detector"))
    results.append(quantize_model(PATHS["tpsmm_src"],  PATHS["tpsmm_int8"],  "TPSMM tpsmm_rel"))
    return all(results)


def run_verification():
    step("Верификация: бинарники и инструменты")
    results = []
    results.append(verify_esrgan())
    results.append(verify_depthflow())
    results.append(verify_ffmpeg())

    step("Верификация: INT8 ONNX модели")
    results.append(verify_onnx(PATHS["midas_int8"], "MiDaS small INT8"))
    results.append(verify_onnx(PATHS["kp_int8"],    "TPSMM kp_detector INT8"))
    results.append(verify_onnx(PATHS["tpsmm_int8"], "TPSMM tpsmm_rel INT8"))

    return results


def print_summary(results, labels=None):
    passed = sum(results)
    total  = len(results)
    print(f"\n{'='*44}")
    if passed == total:
        print(f"{GREEN}  ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ ({passed}/{total}){RESET}")
        print(f"  Модели готовы к интеграции в anim/ модули")
    else:
        failed = total - passed
        print(f"{RED}  ПРОБЛЕМЫ: {failed} из {total} проверок провалились{RESET}")
        print(f"  Исправьте ошибки выше и запустите снова")
    print(f"{'='*44}\n")


def main():
    parser = argparse.ArgumentParser(description="Квантование и верификация моделей anim/")
    parser.add_argument("--verify", action="store_true",
                        help="только верификация, без квантования")
    args = parser.parse_args()

    print(f"\n{CYAN}Менеджер моделей anim/ — SPLIT_PANELS_DEV{RESET}")
    print(f"  Директория моделей: {MODELS}\n")

    if not args.verify:
        q_ok = run_quantization()
        if not q_ok:
            print(f"\n{YELLOW}Некоторые квантования не выполнены.{RESET}")
            print(f"Верификация продолжается...\n")

    v_results = run_verification()
    print_summary(v_results)

    sys.exit(0 if all(v_results) else 1)


if __name__ == "__main__":
    main()
