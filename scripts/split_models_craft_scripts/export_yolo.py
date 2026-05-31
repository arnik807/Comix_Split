import pathlib
from ultralytics import YOLO

def main():
    models_dir = "models"
    pathlib.Path(models_dir).mkdir(exist_ok=True)

    print("🚀 Экспорт YOLOv11n-seg в ONNX...")
    
    # 1. Загружаем официальную nano-модель (она скачается автоматически)
    model = YOLO("yolo11n-seg.pt")

    # 2. Экспортируем в ONNX.
    # Важно: imgsz=640, format='onnx', simplify=True
    # 'task="segment"' явно указывает, что это модель сегментации
    onnx_path = model.export(
        format="onnx", 
        imgsz=640, 
        simplify=True, 
        task="segment" # Явно указываем, что это сегментационная модель
    )
    
    # Переименовываем экспортированный файл в тот, который ожидает pipeline.py
    final_path = pathlib.Path(models_dir) / "yolo_comic.onnx" 
    
    if pathlib.Path(onnx_path).exists():
        if final_path.exists():
            final_path.unlink() # Удаляем старую, если есть
        pathlib.Path(onnx_path).rename(final_path)
        print(f"✅ Модель YOLO успешно экспортирована: {final_path}")
    else:
        print(f"❌ Ошибка экспорта модели. Файл {onnx_path} не найден.")

if __name__ == "__main__":
    main()