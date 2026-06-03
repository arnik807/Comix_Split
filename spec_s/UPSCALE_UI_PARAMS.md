# Параметры апскейла для UI (CUGAN / SPAN)

**Версия:** 1.0 (2 июня 2026)  
**Связано:** [MODELS_SPECIFICATION.md](MODELS_SPECIFICATION.md) §2, [config/models_registry.yaml](../config/models_registry.yaml)

Пресеты `standard` / `quality` по-прежнему используют **Real-ESRGAN**. Ниже — поля для ручного выбора в режиме «Качество».

## Общие (все backend)

| Поле | CLI | UI | Зачем |
|------|-----|-----|--------|
| `backend` | — | dropdown | realesrgan / realcugan / span |
| `scale` | `-s` | ×2 / ×4 (или ×1–×4 для CUGAN) | Степень увеличения |
| `gpu_id` | `-g` | 0 / −1 | Vulkan GPU или CPU |
| `tile_size` | `-t` | число, 0=auto | Меньше — меньше VRAM, при швах на iGPU |

## Real-ESRGAN (`backend: realesrgan`)

| Поле | Значения | Примечание |
|------|----------|------------|
| `model` | `animevideov3`, `anime_6B` | `anime_6B` → только **×4** |

## Real-CUGAN (`backend: realcugan`)

| Поле | CLI | Рекомендация для комиксов |
|------|-----|---------------------------|
| `model` | `-m` папка | `cugan_se` → `models-se` |
| `scale` | `-s` 1–4 | **×2** для баланса; ×4 — тяжелее |
| `cugan_noise` | `-n` −1…3 | **−1** без денойза (цветные панели); 1–2 для шумных сканов |
| `cugan_syncgap` | `-c` 0–3 | **3** (very rough) по умолчанию — быстрее |
| `cugan_weights` | `-m` | `models-se` (в zip) |

## SPAN (`backend: span`)

| Поле | CLI | Примечание |
|------|-----|------------|
| `model` | `-n` | `span_x2_ch48` → scale **2**; `span_x4_ch48` → scale **4** |
| `span_model_name` | `-n` | Дублирует NCNN-имя (`spanx2_ch48`, `spanx4_ch48`) |

Scale для SPAN **фиксируется** по выбранной модели (нельзя ×4 на ×2-весах).

## Не выносим в UI v1

- SPAN multi-GPU `-g -1,0,1`
- CUGAN `-x` (TTA)
- SPAN `-c` cpu-only
