# diagnose.py
import onnxruntime as ort
import numpy as np
import pathlib

MODEL_DIR = pathlib.Path("models")

for model_name in ["yolo_comic_int8.onnx", "mobilesam_encoder_int8.onnx", "mobilesam_decoder_int8.onnx"]:
    path = MODEL_DIR / model_name
    if not path.exists():
        print(f"❌ {model_name} не найден\n")
        continue

    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])

    print(f"{'='*60}")
    print(f"📦 {model_name}")
    print(f"  INPUTS:")
    for inp in sess.get_inputs():
        print(f"    name={inp.name!r:35s} shape={inp.shape}  dtype={inp.type}")
    print(f"  OUTPUTS:")
    for out in sess.get_outputs():
        print(f"    name={out.name!r:35s} shape={out.shape}  dtype={out.type}")
    print()