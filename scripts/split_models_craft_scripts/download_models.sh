#!/usr/bin/env bash
set -e  # прерывать при любой ошибке

MODEL_DIR="models"
mkdir -p "$MODEL_DIR"

# -----------------------------------------------------------------
# 1️⃣ YOLOv11n‑seg (комикс‑панель detection)
#    Репозиторий: levihua/comic-yolo-v11n-seg
# -----------------------------------------------------------------
YOLO_URL="https://huggingface.co/levihua/comic-yolo-v11n-seg/resolve/main/yolo_v11n_seg.onnx"

# 2️⃣ MobileSAM (tiny) – 40 MB
#    Репозиторий: ChaoningZhang/MobileSAM
# -----------------------------------------------------------------
SAM_URL="https://huggingface.co/ChaoningZhang/MobileSAM/resolve/main/mobile_sam.onnx"

# Функция загрузки с токеном, если он есть в переменной HF_HUB_TOKEN
download () {
    local url=$1
    local out=$2
    if [[ -n "$HF_HUB_TOKEN" ]]; then
        echo "📥 Скачивание $out с аутентификацией..."
        curl -L -H "Authorization: Bearer $HF_HUB_TOKEN" -o "$out" "$url"
    else
        echo "⚠️ HF_HUB_TOKEN не найден – пробуем обычный curl"
        curl -L -o "$out" "$url"
    fi
}

# Скачиваем модели
download "$YOLO_URL" "$MODEL_DIR/yolo.onnx"
download "$SAM_URL" "$MODEL_DIR/mobilesam.onnx"

echo "✅ Все модели загружены в $MODEL_DIR"