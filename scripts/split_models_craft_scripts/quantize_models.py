# quantize_models.py
import sys
import shutil
import tempfile
from pathlib import Path

try:
    from onnxruntime.quantization import quantize_dynamic, QuantType
except Exception as exc:
    sys.stderr.write("❌ Установите пакет: pip install onnxruntime\n")
    raise exc


def quantize_model(src: Path, dst: Path) -> None:
    # Копируем во временную папку с ASCII-путём, квантуем там, копируем обратно
    with tempfile.TemporaryDirectory(dir="C:/tmp_quant") as tmp:
        tmp_path = Path(tmp)
        tmp_src = tmp_path / src.name
        tmp_dst = tmp_path / dst.name

        shutil.copy2(src, tmp_src)

        try:
            quantize_dynamic(
                model_input=str(tmp_src),
                model_output=str(tmp_dst),
                weight_type=QuantType.QInt8,
                per_channel=False,
            )
            shutil.copy2(tmp_dst, dst)
            size_kb = dst.stat().st_size // 1024
            print(f"✅ {src.name} → {dst.name}  ({size_kb} KB)")
        except Exception as exc:
            sys.stderr.write(f"⚠️  Не удалось квантовать {src.name}: {exc}\n")


def main() -> None:
    # Создаём C:/tmp_quant заранее (tempfile требует чтобы parent существовал)
    Path("C:/tmp_quant").mkdir(exist_ok=True)

    # model_dir = Path(__file__).resolve().parent / "models"
    model_dir = Path(__file__).resolve().parent.parent / "models"

    if not model_dir.is_dir():
        sys.stderr.write(f"❌ Папка {model_dir} не найдена.\n")
        return

    existing_models = {
        p.name for p in model_dir.iterdir() if p.suffix.lower() == ".onnx"
    }

    to_quantize = [
        "yolo_comic.onnx",
        "yolo_manga.onnx",
        "mobilesam_encoder.onnx",
        "mobilesam_decoder.onnx",
    ]

    for fname in to_quantize:
        if fname not in existing_models:
            sys.stderr.write(f"⚠️  {fname} не найден — пропускаю.\n")
            continue

        src_path = model_dir / fname
        dst_path = model_dir / f"{src_path.stem}_int8.onnx"

        if dst_path.is_file():
            dst_path.unlink()

        print(f"   Квантую {fname}...")
        quantize_model(src_path, dst_path)

    # Чистим временную папку
    shutil.rmtree("C:/tmp_quant", ignore_errors=True)
    print("\n✅ Готово. Модели в:", model_dir)


if __name__ == "__main__":
    main()
