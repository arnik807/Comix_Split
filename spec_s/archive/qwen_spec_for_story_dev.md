# Спецификация: Модуль Story Analyzer для ComicSplit

**Версия документа:** 1.0  
**Дата:** Июнь 2026  
**Статус:** Проект спецификации  
**Связанные документы:** [ARCHITECTURE.md](ARCHITECTURE.md), [MODELS_SPECIFICATION.md](MODELS_SPECIFICATION.md), [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)

---

## Преамбула

### Исходные данные для анализа

Для подготовки данной спецификации были предоставлены:

1. **Документация текущего приложения ComicSplit** (5 файлов):
   - `README.md` — общая структура проекта
   - `ComicSplit_Documentation.md` — пользовательская документация (установка, запуск, UI)
   - `ARCHITECTURE.md` — техническая архитектура MVP
   - `MODELS_SPECIFICATION.md` — спецификация ML-моделей (YOLO, SAM, апскейл, анимация)
   - `IMPLEMENTATION_STATUS.md` — статус реализации компонентов

2. **Диалог о планах развития** — обсуждение с пользователем архитектуры модуля Story Analyzer, который должен:
   - Анализировать раскроенные панели комикса
   - Понимать сюжет, персонажей, диалоги
   - Генерировать повествование (сухое или художественное)
   - Создавать видео с озвучкой (реплики персонажей + закадровый голос)

3. **Список моделей SiliconFlow** (`models_siliconFlow.txt`) — актуальный каталог доступных LLM/VLM/TTS/ASR моделей через API SiliconFlow.

### Целевое железо (hard constraint)

| Параметр | Значение |
|----------|----------|
| CPU | AMD Ryzen 5 5600H (6C/12T, 3.3 GHz) |
| GPU | AMD Radeon iGPU (~1 GB shared VRAM, Vulkan 1.3) |
| RAM | 16 GB DDR4 |
| ОС | Windows 10/11 |
| Ограничения | ❌ Нет CUDA; ❌ Нет NVIDIA GPU |

### Задача

Спроектировать модуль **Story Analyzer**, который:
1. Интегрируется в существующую архитектуру ComicSplit
2. Работает на указанном железе (локально или через API)
3. Превращает папку PNG-панелей в готовое видео с озвучкой
4. Имеет чёткую архитектуру с абстракциями для замены провайдеров
5. Поддерживает два режима: **ECONOMY** (дешёво/быстро) и **QUALITY** (максимум качества)

### Критерии успеха

✅ Модуль принимает папку панелей после split  
✅ Генерирует JSON-сценарий с репликами и таймингами  
✅ Синтезирует речь для персонажей и рассказчика  
✅ Собирает финальное MP4 с видеорядом и аудио  
✅ Работает на Ryzen 5600H + 16GB RAM  
✅ Стоимость обработки 100-страничного комикса < $1 через API  

---

## 1. Обоснование архитектурных решений

### 1.1. Почему гибридная архитектура (локально + облако)

**Проблема чистой локальной схемы:**

Если пытаться анализировать 200 страниц комикса через локальную Vision LLM:
- Qwen2.5-VL-7B требует ~14 GB RAM (влезает, но медленно)
- Обработка 1 страницы = 30-60 секунд на CPU
- 200 страниц = 2-3 часа только на анализ
- Качество понимания сюжета у 7B модели низкое (теряет контекст, персонажей)

**Проблема чистой облачной схемы:**

Если отправлять все 200 страниц в Vision API:
- GPT-4o: ~$15-20 за комикс (image tokens дорогие)
- Qwen-VL через DashScope: ~$2-5 за комикс
- Зависимость от интернета и оплаты

**Решение — гибридная схема:**

```
Локально (дешёво, быстро):
  Panel Split (YOLO) → уже есть ✅
  OCR (PaddleOCR-VL-1.5) → ~$0.001/стр
  Перевод (опционально) → бесплатно

Облако (качественно, дорого):
  Story Understanding → $0.06-0.30 за комикс
  TTS → $0.50-2.00 за комикс
```

**Итоговая стоимость:** ~$1-3 за 100-страничный комикс через SiliconFlow API.

### 1.2. Почему SiliconFlow как основной провайдер

| Критерий | SiliconFlow | DashScope (Alibaba) | OpenRouter |
|----------|-------------|---------------------|------------|
| Работает из РФ | ✅ Да | ❌ Блокировки | ⚠️ Зависит |
| OpenAI-compatible API | ✅ Да | ✅ Да | ✅ Да |
| Бесплатные модели | ✅ DeepSeek-OCR, Hunyuan-MT | ⚠️ Лимиты | ⚠️ Лимиты |
| Qwen модели | ✅ Все версии | ✅ Все версии | ✅ Есть |
| TTS модели | ✅ CosyVoice2 | ✅ Sambert | ❌ Нет |
| Оплата | 💳 Китайские карты | 💳 Китайские карты | 💳 Крипто/карты |

**Вывод:** SiliconFlow — оптимальный выбор для пользователя из РФ. Работает стабильно, есть бесплатные модели, огромный выбор Qwen/GLM/Kimi.

### 1.3. Почему абстракция `Pipeline`

Вместо жёсткой привязки к одному провайдеру создаём интерфейс:

```python
class StoryProvider(ABC):
    @abstractmethod
    def analyze_panels(self, panels_data: List[Dict]) -> Dict:
        """Анализ панелей → сюжет"""
        pass
    
    @abstractmethod
    def generate_script(self, story: Dict) -> Dict:
        """Сюжет → JSON-сценарий"""
        pass

class OCRProvider(ABC):
    @abstractmethod
    def extract_text(self, image_path: str) -> Dict:
        """Извлечение текста из панели"""
        pass

class TranslationProvider(ABC):
    @abstractmethod
    def translate(self, text: str, target_lang: str) -> str:
        """Перевод текста"""
        pass

class VoiceProvider(ABC):
    @abstractmethod
    def synthesize(self, text: str, voice_id: str) -> bytes:
        """Синтез речи → аудио"""
        pass
```

**Преимущества:**
- Можно менять провайдера одной строкой в конфиге
- Легко добавить новый API (OpenRouter, DashScope, OpenAI)
- Локальный fallback всегда доступен
- Тестируемость: моки для unit-тестов

---

## 2. Детальная архитектура пайплайна

### 2.1. Обзор 7 этапов

```
┌─────────────────────────────────────────────────────────────┐
│  STAGE 1: LOCAL PREPROCESSING (уже есть в ComicSplit)      │
│  ├─ Panel Split (YOLO INT8)                                 │
│  ├─ Reading Order (existing pipeline)                       │
│  └─ Panel Metadata JSON                                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 2: OCR + CAPTION (hybrid)                           │
│  ├─ Local: PaddleOCR-VL-1.5 (ONNX CPU)                    │
│  └─ Cloud: DeepSeek-OCR (SiliconFlow, FREE)               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 3: TRANSLATION (optional, hybrid)                   │
│  ├─ Cloud: Hunyuan-MT-7B (SiliconFlow, FREE)              │
│  └─ Local: Hunyuan-MT-7B GGUF (~14GB RAM)                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 4: STORY UNDERSTANDING (CLOUD PRIMARY)              │
│  ├─ Per-chapter: Qwen3.5-122B-A10B или GLM-4.7           │
│  ├─ Full-volume: Qwen3.5-397B-A17B (1M context)           │
│  └─ Local fallback: Qwen3-14B-Q4_K_M via Ollama           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 5: SCRIPT GENERATION                                │
│  ├─ JSON сценарий: narrator + character_1..N + timing      │
│  └─ Та же модель, что Stage 4 (prompt engineering)         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 6: VOICE SYNTHESIS (hybrid)                         │
│  ├─ Cloud: CosyVoice2-0.5B (SiliconFlow)                  │
│  ├─ Cloud: MOSS-TTSD-v0.5 (диалоги двух персонажей)       │
│  └─ Local: CosyVoice2-0.5B (ONNX CPU, реально)            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 7: VIDEO ASSEMBLY (existing anim pipeline)          │
│  ├─ Panel animation (DepthFlow / OpenCV)                   │
│  ├─ Audio mix (narrator + characters + SFX)                │
│  └─ ffmpeg → MP4                                           │
└─────────────────────────────────────────────────────────────┘
```

### 2.2. Поток данных

**Вход:**
```
comic_pages/
├── page_001.png
├── page_002.png
└── ...
```

**После Stage 1 (уже есть):**
```json
{
  "pages": [
    {
      "page_number": 1,
      "panels": [
        {"panel_id": 1, "bbox": [100, 200, 500, 600], "image_path": "panels/page_001_panel_01.png"},
        {"panel_id": 2, "bbox": [520, 200, 900, 600], "image_path": "panels/page_001_panel_02.png"}
      ]
    }
  ]
}
```

**После Stage 2 (OCR):**
```json
{
  "pages": [
    {
      "page_number": 1,
      "panels": [
        {
          "panel_id": 1,
          "ocr": {
            "bubbles": [
              {"text": "We must leave now!", "bbox": [150, 250, 300, 350]},
              {"text": "But the enemy is everywhere...", "bbox": [320, 400, 480, 500]}
            ]
          },
          "caption": "Two characters discuss their escape plan in a tense moment"
        }
      ]
    }
  ]
}
```

**После Stage 4-5 (Story + Script):**
```json
{
  "title": "The Great Escape",
  "chapters": [
    {
      "chapter_id": 1,
      "summary": "Heroes plan their escape from the enemy fortress",
      "scenes": [
        {
          "scene_id": 1,
          "pages": [1, 2],
          "narrator": "In the dark corridors of the fortress, two figures whispered urgently.",
          "dialogues": [
            {"character": "Hero", "text": "We must leave now!", "emotion": "urgent"},
            {"character": "Companion", "text": "But the enemy is everywhere...", "emotion": "fearful"}
          ],
          "duration_seconds": 8.5
        }
      ]
    }
  ]
}
```

**После Stage 6 (TTS):**
```
audio/
├── narrator_scene_001.mp3
├── character_hero_scene_001.mp3
├── character_companion_scene_001.mp3
└── ...
```

**После Stage 7 (Video):**
```
output/
├── final_video.mp4
├── storyboard.mp4
└── metadata.json
```

---

## 3. Детальный разбор технологий по этапам

### 3.1. Stage 1: Local Preprocessing (уже реализовано)

**Статус:** ✅ Готово в ComicSplit MVP

**Технологии:**
- YOLO INT8 (comic/manga детектор)
- MobileSAM INT8 (опционально, для точных масок)
- Reading order algorithm

**Документация:** [MODELS_SPECIFICATION.md](MODELS_SPECIFICATION.md) §1

**Что делает:**
- Находит панели на страницах
- Определяет порядок чтения (LTR/RTL)
- Сохраняет PNG с прозрачным фоном
- Генерирует метаданные (bbox, порядок)

**Обоснование:** Этот этап уже работает отлично на Ryzen 5600H. Скорость ~400-800 мс/страница в режиме Fast. Не требует изменений.

---

### 3.2. Stage 2: OCR + Caption

#### 3.2.1. PaddleOCR-VL-1.5 (рекомендуется)

**Что это:** Vision Language Model (VLM) размером 0.9B параметров, специально обученная для OCR документов.

**Почему подходит:**
- SOTA на OmniDocBench v1.5 (94.5% точность)
- Понимает контекст баблов (отличает реплики от ремарок)
- Поддерживает рукописный текст
- Работает на CPU (ONNX Runtime)
- Очень лёгкая (0.9B параметров)

**Характеристики:**
| Параметр | Значение |
|----------|----------|
| Параметры | 0.9B |
| Контекст | 8K tokens |
| Backend | ONNX CPU / SiliconFlow API |
| Скорость | ~2-5 сек/панель на CPU |
| RAM | ~2 GB |

**Ссылки:**
- Модель: https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5
- Документация SiliconFlow: https://docs.siliconflow.cn/en/api-reference/chat-completions/chat-completions
- OmniDocBench: https://omnidocbench.org/

**Интеграция (Cloud API):**

```python
import requests

def ocr_paddle_cloud(image_path: str, api_key: str) -> Dict:
    """OCR через SiliconFlow API"""
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()
    
    response = requests.post(
        "https://api.siliconflow.cn/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "PaddlePaddle/PaddleOCR-VL-1.5",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                        {"type": "text", "text": "Extract all text from speech bubbles. Return JSON: {\"bubbles\": [{\"text\": \"...\", \"bbox\": [x1,y1,x2,y2]}]}"}
                    ]
                }
            ],
            "max_tokens": 1024
        }
    )
    return response.json()["choices"][0]["message"]["content"]
```

**Интеграция (Local ONNX):**

```python
import onnxruntime as ort

def ocr_paddle_local(image_path: str) -> Dict:
    """OCR локально через ONNX"""
    session = ort.InferenceSession("models/paddleocr_vl_1.5.onnx")
    # Препроцессинг изображения
    input_tensor = preprocess(image_path)
    # Инференс
    outputs = session.run(None, {"input": input_tensor})
    # Постпроцессинг
    return postprocess(outputs)
```

**Стоимость:**
- Cloud: ~$0.001 за панель (очень дёшево)
- Local: бесплатно, но медленно на CPU

#### 3.2.2. DeepSeek-OCR (бесплатная альтернатива)

**Что это:** Специализированная модель для OCR от DeepSeek.

**Почему подходит:**
- **Бесплатно** на SiliconFlow (помечена как "限免")
- Хорошо работает с документами
- Конвертирует в Markdown

**Характеристики:**
| Параметр | Значение |
|----------|----------|
| Параметры | 3B |
| Контекст | 8K tokens |
| Цена | **FREE** |
| Скорость | ~3-7 сек/панель |

**Ссылки:**
- Модель: https://huggingface.co/deepseek-ai/DeepSeek-OCR
- SiliconFlow: https://cloud.siliconflow.cn/models (ищите "DeepSeek-OCR")

**Интеграция:**

```python
def ocr_deepseek(image_path: str, api_key: str) -> str:
    """Бесплатный OCR через DeepSeek"""
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()
    
    response = requests.post(
        "https://api.siliconflow.cn/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "deepseek-ai/DeepSeek-OCR",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                        {"type": "text", "text": "Convert this comic panel to Markdown. Extract all text from speech bubbles and narration boxes."}
                    ]
                }
            ]
        }
    )
    return response.json()["choices"][0]["message"]["content"]
```

**Обоснование выбора:**

| Критерий | PaddleOCR-VL-1.5 | DeepSeek-OCR |
|----------|------------------|--------------|
| Качество | ⭐⭐⭐ SOTA | ⭐⭐ Хорошо |
| Цена | $0.001/панель | **FREE** |
| Скорость | Быстрее | Медленнее |
| Контекст баблов | ✅ Понимает | ⚠️ Базово |

**Рекомендация:** Использовать DeepSeek-OCR для MVP (бесплатно), переключиться на PaddleOCR-VL-1.5 для production (качество).

---

### 3.3. Stage 3: Translation (опционально)

#### 3.3.1. Hunyuan-MT-7B (рекомендуется)

**Что это:** Модель машинного перевода от Tencent, лидер WMT25.

**Почему подходит:**
- **Бесплатно** на SiliconFlow
- 33 языка + 5 китайских диалектов
- 32K контекст (хватает на целую главу)
- SOTA на WMT25 (30 из 31 языковых пар — 1 место)

**Характеристики:**
| Параметр | Значение |
|----------|----------|
| Параметры | 7B |
| Контекст | 32K tokens |
| Языки | 33 + 5 диалектов |
| Цена | **FREE** |
| Скорость | ~1-3 сек/предложение |

**Ссылки:**
- Модель: https://huggingface.co/tencent/Hunyuan-MT-7B
- Документация: https://hunyuan.tencent.com/
- WMT25 результаты: https://www.statmt.org/wmt25/

**Интеграция:**

```python
def translate_hunyuan(text: str, source_lang: str, target_lang: str, api_key: str) -> str:
    """Перевод через Hunyuan-MT-7B"""
    response = requests.post(
        "https://api.siliconflow.cn/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "tencent/Hunyuan-MT-7B",
            "messages": [
                {
                    "role": "user",
                    "content": f"Translate from {source_lang} to {target_lang}:\n\n{text}"
                }
            ],
            "max_tokens": 2048
        }
    )
    return response.json()["choices"][0]["message"]["content"]

# Пример использования
english_text = "We must leave now! But the enemy is everywhere..."
russian_text = translate_hunyuan(english_text, "English", "Russian", api_key)
# Результат: "Мы должны уйти прямо сейчас! Но враги повсюду..."
```

**Локальный fallback:**

Если нет интернета, можно запустить Hunyuan-MT-7B локально через Ollama:

```bash
# Установка Ollama
winget install Ollama.Ollama

# Загрузка модели
ollama pull hunyuan-mt:7b

# Запуск
ollama run hunyuan-mt:7b
```

**Требования к железу:**
- RAM: ~14 GB (влезает в 16 GB, но плотно)
- Скорость: ~5-10 сек/предложение на CPU
- Рекомендуется только для единичных переводов

**Обоснование выбора:**

Hunyuan-MT-7B — единственный бесплатный переводчик уровня SOTA. Альтернативы:
- Google Translate API — платно
- DeepL API — платно
- Qwen3.5-27B с промптом — дороже и медленнее

---

### 3.4. Stage 4: Story Understanding (ключевой этап)

Это самый важный и сложный этап. Модель должна:
1. Понять сюжет по OCR-тексту и описаниям панелей
2. Определить персонажей и их роли
3. Установить причинно-следственные связи
4. Сохранить контекст на протяжении всей главы/тома

#### 3.4.1. Qwen3.5-122B-A10B (рабочая лошадка)

**Что это:** Мультимодальная MoE-модель от Alibaba, 122B параметров (активируется 10B).

**Почему подходит:**
- Отличное соотношение цена/качество
- MoE-архитектура → высокая скорость инференса
- 256K контекст (хватает на 10-20 страниц)
- Поддержка vision (может анализировать картинки панелей)
- 201 язык

**Характеристики:**
| Параметр | Значение |
|----------|----------|
| Параметры | 122B total / 10B active |
| Архитектура | MoE (Mixture of Experts) |
| Контекст | 256K tokens |
| Vision | ✅ Да |
| Цена | ~$0.30 за 1M input tokens |
| Скорость | ~10-20 сек/страница |

**Ссылки:**
- Модель: https://huggingface.co/Qwen/Qwen3.5-122B-A10B
- Документация Qwen: https://qwen.readthedocs.io/
- SiliconFlow: https://cloud.siliconflow.cn/models (ищите "Qwen3.5-122B-A10B")

**Интеграция:**

```python
def analyze_story_qwen(panels_data: List[Dict], api_key: str) -> Dict:
    """Анализ сюжета через Qwen3.5-122B"""
    
    # Формируем промпт с данными панелей
    panels_text = json.dumps(panels_data, ensure_ascii=False, indent=2)
    
    prompt = f"""You are a comic book analyst. Analyze the following panels from a comic and extract:

1. **Characters**: List all characters with their descriptions
2. **Plot**: Summarize the main events
3. **Relationships**: Describe relationships between characters
4. **Emotions**: Note key emotional moments
5. **Setting**: Describe the location and time

Panels data:
{panels_text}

Return JSON format:
{{
  "characters": [
    {{"name": "...", "description": "...", "role": "protagonist/antagonist/supporting"}}
  ],
  "plot_summary": "...",
  "key_events": ["...", "..."],
  "emotional_beats": ["...", "..."],
  "setting": "..."
}}"""

    response = requests.post(
        "https://api.siliconflow.cn/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "Qwen/Qwen3.5-122B-A10B",
            "messages": [
                {"role": "system", "content": "You are an expert comic book analyst."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 4096,
            "temperature": 0.3
        }
    )
    
    result_text = response.json()["choices"][0]["message"]["content"]
    return json.loads(result_text)
```

**Стоимость расчёта:**
- 100 страниц × ~1000 tokens/стр = 100K tokens input
- 100K tokens × $0.30/1M = **$0.03** за комикс
- Output: ~10K tokens × $1.20/1M = **$0.012**
- **Итого: ~$0.04 за 100-страничный комикс**

#### 3.4.2. Qwen3.5-397B-A17B (для длинных томов)

**Что это:** Флагманская MoE-модель Qwen, 397B параметров (активируется 17B).

**Почему подходит:**
- Расширение контекста до **1M tokens** (через YaRN)
- Может обработать весь том комикса за раз
- Лучшее качество понимания сложных сюжетов

**Характеристики:**
| Параметр | Значение |
|----------|----------|
| Параметры | 397B total / 17B active |
| Контекст | 256K → 1M (YaRN) |
| Цена | ~$0.80 за 1M input tokens |
| Скорость | ~20-40 сек/страница |

**Ссылки:**
- Модель: https://huggingface.co/Qwen/Qwen3.5-397B-A17B

**Когда использовать:**
- Том > 100 страниц
- Сложный сюжет с множеством персонажей
- Нужен анализ всего тома целиком (арки, развитие персонажей)

**Интеграция:**

```python
def analyze_full_volume_qwen(all_panels: List[Dict], api_key: str) -> Dict:
    """Анализ всего тома через Qwen3.5-397B"""
    
    # Формируем огромный промпт со всеми панелями
    panels_text = json.dumps(all_panels, ensure_ascii=False)
    
    prompt = f"""Analyze this entire comic volume. Extract:
1. Character arcs (how characters change)
2. Plot structure (beginning, middle, climax, ending)
3. Themes and motifs
4. Key turning points

Panels:
{panels_text}

Return detailed JSON analysis."""

    response = requests.post(
        "https://api.siliconflow.cn/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "Qwen/Qwen3.5-397B-A17B",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8192,
            "temperature": 0.3
        }
    )
    return json.loads(response.json()["choices"][0]["message"]["content"])
```

**Стоимость:**
- 200 страниц × 1000 tokens = 200K tokens
- 200K × $0.80/1M = **$0.16** за том
- Output: ~20K tokens × $3.20/1M = **$0.064**
- **Итого: ~$0.22 за 200-страничный том**

#### 3.4.3. GLM-4.7 (альтернатива для сложных сюжетов)

**Что это:** Флагманская модель от Zhipu AI, 355B параметров (MoE).

**Почему подходит:**
- Отлично справляется с агентными задачами
- Хорошее понимание визуального контекста
- SWE-bench: 73.8% (сильный reasoning)

**Характеристики:**
| Параметр | Значение |
|----------|----------|
| Параметры | 355B total / 32B active |
| Контекст | 200K tokens |
| Цена | ~$0.40 за 1M input tokens |
| Особенности | Улучшенный agent framework |

**Ссылки:**
- Модель: https://huggingface.co/zai-org/GLM-4.7
- Документация: https://bigmodel.cn/

**Когда использовать:**
- Детективные сюжеты (требуют логического вывода)
- Фэнтези/научная фантастика (сложные миры)
- Когда Qwen не справляется с контекстом

#### 3.4.4. Локальный fallback: Qwen3-14B-Q4_K_M

**Что это:** Локальная версия Qwen3-14B в квантовании Q4_K_M.

**Почему подходит:**
- Работает без интернета
- Бесплатно
- Влезает в 16 GB RAM (~10 GB)

**Характеристики:**
| Параметр | Значение |
|----------|----------|
| Параметры | 14B |
| Квантование | Q4_K_M |
| RAM | ~10 GB |
| Скорость | ~30-60 сек/страница на CPU |
| Качество | ⭐⭐ (значительно хуже облачных) |

**Интеграция через Ollama:**

```bash
# Установка
ollama pull qwen3:14b-q4_K_M

# Запуск
ollama run qwen3:14b-q4_K_M
```

```python
def analyze_story_local(panels_data: List[Dict]) -> Dict:
    """Локальный анализ через Ollama"""
    import ollama
    
    panels_text = json.dumps(panels_data, ensure_ascii=False)
    prompt = f"Analyze this comic: {panels_text}"
    
    response = ollama.chat(
        model="qwen3:14b-q4_K_M",
        messages=[{"role": "user", "content": prompt}]
    )
    return json.loads(response["message"]["content"])
```

**Обоснование выбора моделей:**

| Модель | Качество | Скорость | Цена | Контекст | Рекомендация |
|--------|----------|----------|------|----------|--------------|
| Qwen3.5-122B-A10B | ⭐⭐⭐ | ⭐⭐⭐ | $0.04/комикс | 256K | **Основной выбор** |
| Qwen3.5-397B-A17B | ⭐⭐⭐ | ⭐⭐ | $0.22/том | 1M | Длинные тома |
| GLM-4.7 | ⭐⭐⭐ | ⭐⭐ | $0.08/комикс | 200K | Сложные сюжеты |
| Qwen3-14B (local) | ⭐⭐ | ⭐ | FREE | 128K | Fallback без сети |

---

### 3.5. Stage 5: Script Generation

**Что это:** Превращение анализа сюжета в JSON-сценарий для видео.

**Технология:** Та же модель, что в Stage 4 (Qwen3.5-122B-A10B), но с другим промптом.

**Промпт:**

```python
def generate_script(story_analysis: Dict, panels_data: List[Dict], api_key: str) -> Dict:
    """Генерация JSON-сценария"""
    
    prompt = f"""Based on this comic analysis, create a video script.

Story Analysis:
{json.dumps(story_analysis, ensure_ascii=False, indent=2)}

Panels Data:
{json.dumps(panels_data, ensure_ascii=False, indent=2)}

Create a scene-by-scene script with:
1. Narrator text (describes action, setting)
2. Character dialogues (exact text from bubbles)
3. Timing (estimated duration for each scene)
4. Emotions (for voice synthesis)

Return JSON:
{{
  "title": "Comic Title",
  "scenes": [
    {{
      "scene_id": 1,
      "pages": [1, 2],
      "narrator": "In a dark forest, two heroes walked cautiously...",
      "dialogues": [
        {{"character": "Hero", "text": "We must be careful.", "emotion": "serious"}},
        {{"character": "Companion", "text": "I hear something...", "emotion": "fearful"}}
      ],
      "duration_seconds": 8.5,
      "music_mood": "tense"
    }}
  ]
}}"""

    response = requests.post(
        "https://api.siliconflow.cn/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "Qwen/Qwen3.5-122B-A10B",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8192,
            "temperature": 0.5
        }
    )
    return json.loads(response.json()["choices"][0]["message"]["content"])
```

**Пример вывода:**

```json
{
  "title": "The Great Escape",
  "scenes": [
    {
      "scene_id": 1,
      "pages": [1, 2],
      "narrator": "In the dimly lit corridors of the ancient fortress, two figures moved swiftly through the shadows.",
      "dialogues": [
        {
          "character": "Aric",
          "text": "We must leave now, before the guards return.",
          "emotion": "urgent",
          "voice_profile": "male_baritone"
        },
        {
          "character": "Lyra",
          "text": "But the enemy is everywhere... How do we escape?",
          "emotion": "fearful",
          "voice_profile": "female_alto"
        }
      ],
      "duration_seconds": 8.5,
      "music_mood": "tense",
      "camera_movement": "slow_pan"
    }
  ]
}
```

---

### 3.6. Stage 6: Voice Synthesis (TTS)

#### 3.6.1. CosyVoice2-0.5B (рекомендуется)

**Что это:** Современная TTS-модель от Alibaba с поддержкой клонирования голоса.

**Почему подходит:**
- 150ms latency (streaming)
- Поддержка эмоций и диалектов
- Клонирование голоса по 3-секундному образцу
- CN/EN/JP/KR + диалекты
- Работает локально (ONNX CPU)

**Характеристики:**
| Параметр | Значение |
|----------|----------|
| Параметры | 0.5B |
| Latency | 150ms (streaming) |
| Языки | CN, EN, JP, KR + диалекты |
| Эмоции | ✅ Да |
| Клонирование | ✅ 3 сек образца |
| Цена | ~$0.01 за 1K символов |
| RAM (local) | ~2 GB |

**Ссылки:**
- Модель: https://huggingface.co/FunAudioLLM/CosyVoice2-0.5B
- Документация: https://github.com/FunAudioLLM/CosyVoice
- Демо: https://huggingface.co/spaces/FunAudioLLM/CosyVoice2

**Интеграция (Cloud API):**

```python
def synthesize_voice_cosy(text: str, voice_id: str, emotion: str, api_key: str) -> bytes:
    """Синтез речи через CosyVoice2"""
    
    response = requests.post(
        "https://api.siliconflow.cn/v1/audio/speech",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "FunAudioLLM/CosyVoice2-0.5B",
            "input": text,
            "voice": voice_id,  # Например: "alloy", "echo", "fable"
            "speed": 1.0,
            "emotion": emotion  # "neutral", "happy", "sad", "angry", "fearful"
        }
    )
    
    return response.content  # MP3 bytes

# Пример использования
narrator_audio = synthesize_voice_cosy(
    text="In a dark forest, two heroes walked cautiously...",
    voice_id="onyx",  # Глубокий мужской голос
    emotion="neutral",
    api_key=api_key
)

hero_audio = synthesize_voice_cosy(
    text="We must be careful.",
    voice_id="alloy",  # Молодой мужской голос
    emotion="serious",
    api_key=api_key
)

# Сохранение
with open("narrator_scene_001.mp3", "wb") as f:
    f.write(narrator_audio)
```

**Клонирование голоса:**

```python
def clone_voice(reference_audio_path: str, text: str, api_key: str) -> bytes:
    """Клонирование голоса по образцу"""
    
    with open(reference_audio_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode()
    
    response = requests.post(
        "https://api.siliconflow.cn/v1/audio/speech",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "FunAudioLLM/CosyVoice2-0.5B",
            "input": text,
            "voice_clone": {
                "reference_audio": f"data:audio/wav;base64,{audio_b64}",
                "similarity": 0.85
            }
        }
    )
    return response.content
```

**Локальный запуск (ONNX CPU):**

```python
import onnxruntime as ort

def synthesize_local(text: str, voice_id: str) -> bytes:
    """Локальный TTS через ONNX"""
    session = ort.InferenceSession("models/cosyvoice2_0.5b.onnx")
    # Препроцессинг текста
    input_tensor = preprocess_text(text, voice_id)
    # Инференс
    audio = session.run(None, {"input": input_tensor})
    # Постпроцессинг
    return postprocess_audio(audio)
```

**Требования к железу (local):**
- RAM: ~2 GB
- CPU: Ryzen 5600H справится
- Скорость: ~1-3 сек на предложение

**Стоимость:**
- 100 сцен × ~50 символов = 5000 символов
- 5000 × $0.01/1K = **$0.05** за комикс

#### 3.6.2. MOSS-TTSD-v0.5 (для диалогов)

**Что это:** Специализированная модель для синтеза диалогов между двумя персонажами.

**Почему подходит:**
- Генерирует сразу двух говорящих
- Zero-shot клонирование двух голосов
- До 960 секунд аудио за раз
- Естественные паузы и реакции

**Характеристики:**
| Параметр | Значение |
|----------|----------|
| Параметры | 2.05B |
| Макс. длительность | 960 сек |
| Голоса | 2 одновременно |
| Языки | CN, EN |
| Цена | ~$0.02 за 1K символов |

**Ссылки:**
- Модель: https://huggingface.co/fnlp/MOSS-TTSD-v0.5
- Документация: https://github.com/OpenMOSS/MOSS-TTSD

**Интеграция:**

```python
def synthesize_dialogue(dialogue_script: Dict, api_key: str) -> bytes:
    """Синтез диалога двух персонажей"""
    
    # Формируем скрипт диалога
    script_text = ""
    for line in dialogue_script["lines"]:
        script_text += f"[{line['character']}]: {line['text']}\n"
    
    response = requests.post(
        "https://api.siliconflow.cn/v1/audio/speech",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "fnlp/MOSS-TTSD-v0.5",
            "input": script_text,
            "voices": {
                "character_1": {"reference_audio": "voice_samples/hero.wav"},
                "character_2": {"reference_audio": "voice_samples/villain.wav"}
            }
        }
    )
    return response.content
```

**Когда использовать:**
- Сцены с активным диалогом между двумя персонажами
- Когда нужны естественные паузы и реакции
- Для создания "радиоспектакля"

**Обоснование выбора TTS:**

| Модель | Качество | Скорость | Цена | Особенности | Рекомендация |
|--------|----------|----------|------|-------------|--------------|
| CosyVoice2-0.5B | ⭐⭐⭐ | ⭐⭐⭐ | $0.05/комикс | Эмоции, клонирование | **Основной выбор** |
| MOSS-TTSD-v0.5 | ⭐⭐⭐ | ⭐⭐ | $0.10/комикс | Диалоги 2 персонажей | Для диалогов |
| CosyVoice2 (local) | ⭐⭐⭐ | ⭐⭐ | FREE | ONNX CPU | Fallback |

---

### 3.7. Stage 7: Video Assembly

**Статус:** ✅ Частично готово в ComicSplit (есть `anim_pipeline.py`)

**Что нужно добавить:**
1. Аудио-микшер (объединение narrator + characters + SFX)
2. Синхронизация аудио с видеорядом
3. Субтитры (опционально)

**Технологии:**
- FFmpeg (уже есть в ComicSplit)
- PyDub (для аудио-микширования)
- MoviePy (опционально, для сложного монтажа)

**Интеграция:**

```python
from pydub import AudioSegment
import subprocess

def assemble_video(script: Dict, audio_files: Dict, video_clips: List[str], output_path: str):
    """Сборка финального видео"""
    
    # 1. Микширование аудио для каждой сцены
    for scene in script["scenes"]:
        scene_id = scene["scene_id"]
        
        # Загружаем аудио
        narrator = AudioSegment.from_mp3(audio_files[f"narrator_{scene_id}.mp3"])
        character_audios = [
            AudioSegment.from_mp3(audio_files[f"char_{d['character']}_{scene_id}.mp3"])
            for d in scene["dialogues"]
        ]
        
        # Микшируем с таймингами
        mixed = narrator
        current_time = len(narrator) + 500  # 500ms пауза после нарратора
        
        for char_audio in character_audios:
            mixed = mixed.overlay(char_audio, position=current_time)
            current_time += len(char_audio) + 200  # 200ms пауза между репликами
        
        # Сохраняем микс
        mixed.export(f"temp/scene_{scene_id}_audio.mp3", format="mp3")
    
    # 2. Объединяем видео + аудио через FFmpeg
    for scene in script["scenes"]:
        scene_id = scene["scene_id"]
        video_clip = video_clips[scene_id - 1]
        audio_file = f"temp/scene_{scene_id}_audio.mp3"
        
        subprocess.run([
            "ffmpeg", "-i", video_clip,
            "-i", audio_file,
            "-c:v", "copy", "-c:a", "aac",
            "-shortest",
            f"temp/scene_{scene_id}_final.mp4"
        ])
    
    # 3. Конкатенация всех сцен
    concat_list = "temp/concat.txt"
    with open(concat_list, "w") as f:
        for scene in script["scenes"]:
            f.write(f"file 'scene_{scene['scene_id']}_final.mp4'\n")
    
    subprocess.run([
        "ffmpeg", "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c", "copy",
        output_path
    ])
```

**Существующие модули ComicSplit для использования:**
- `anim/upscale.py` — апскейл панелей
- `anim/harmonize.py` — гармонизация 16:9
- `anim/animate_depthflow.py` — parallax-анимация
- `anim/animate_opencv.py` — простые эффекты
- `anim/render.py` — FFmpeg рендеринг

---

## 4. Структура модуля Story Analyzer

### 4.1. Файловая структура

```
SPLIT_PANELS_DEV/
├── story_analyzer/                    # Новый модуль
│   ├── __init__.py
│   ├── pipeline.py                    # Главный оркестратор
│   ├── providers/                     # Абстракции провайдеров
│   │   ├── __init__.py
│   │   ├── base.py                    # ABC классы
│   │   ├── ocr/
│   │   │   ├── __init__.py
│   │   │   ├── paddle_cloud.py        # PaddleOCR-VL-1.5 (Cloud)
│   │   │   ├── deepseek_cloud.py      # DeepSeek-OCR (Cloud, FREE)
│   │   │   └── paddle_local.py        # PaddleOCR (Local ONNX)
│   │   ├── translation/
│   │   │   ├── __init__.py
│   │   │   ├── hunyuan_cloud.py       # Hunyuan-MT-7B (Cloud, FREE)
│   │   │   └── hunyuan_local.py       # Hunyuan-MT (Local Ollama)
│   │   ├── story/
│   │   │   ├── __init__.py
│   │   │   ├── qwen_cloud.py          # Qwen3.5-122B (Cloud)
│   │   │   ├── qwen_long_cloud.py     # Qwen3.5-397B (Cloud, 1M ctx)
│   │   │   ├── glm_cloud.py           # GLM-4.7 (Cloud)
│   │   │   └── qwen_local.py          # Qwen3-14B (Local Ollama)
│   │   └── voice/
│   │       ├── __init__.py
│   │       ├── cosyvoice_cloud.py     # CosyVoice2 (Cloud)
│   │       ├── moss_cloud.py          # MOSS-TTSD (Cloud)
│   │       └── cosyvoice_local.py     # CosyVoice2 (Local ONNX)
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── audio_mixer.py             # Микширование аудио
│   │   ├── video_assembler.py         # Сборка видео
│   │   └── subtitle_generator.py      # Генерация субтитров (опционально)
│   └── config/
│       ├── __init__.py
│       ├── story_config.py            # Конфигурация модуля
│       └── provider_registry.yaml     # Реестр провайдеров
│
├── config/
│   └── story_presets.yaml             # Пресеты ECONOMY / QUALITY
│
├── main.py                            # Добавить вкладку "Story"
├── api/server.py                      # Добавить API эндпоинты
└── frontend/index.html                # Добавить UI для Story Analyzer
```

### 4.2. Конфигурация (`config/story_presets.yaml`)

```yaml
# Пресеты для Story Analyzer

presets:
  economy:
    name: "Economy (Дёшево и быстро)"
    description: "Минимальная стоимость, приемлемое качество"
    providers:
      ocr: "deepseek_cloud"           # FREE
      translation: "hunyuan_cloud"    # FREE
      story: "qwen_cloud"             # Qwen3.5-122B-A10B
      voice: "cosyvoice_cloud"        # CosyVoice2-0.5B
    settings:
      batch_size: 10                  # Обрабатывать по 10 панелей за раз
      max_retries: 3
      timeout: 60
    
  quality:
    name: "Quality (Максимальное качество)"
    description: "Лучшее качество, высокая стоимость"
    providers:
      ocr: "paddle_cloud"             # PaddleOCR-VL-1.5
      translation: "hunyuan_cloud"    # Hunyuan-MT-7B
      story: "qwen_long_cloud"        # Qwen3.5-397B-A17B (1M ctx)
      voice: "cosyvoice_cloud"        # CosyVoice2-0.5B (с клонированием)
    settings:
      batch_size: 5
      max_retries: 5
      timeout: 120
      voice_cloning: true             # Использовать клонирование голоса
    
  local:
    name: "Local (Полностью локально)"
    description: "Без интернета, медленно, но бесплатно"
    providers:
      ocr: "paddle_local"             # PaddleOCR ONNX
      translation: "hunyuan_local"    # Ollama Hunyuan-MT
      story: "qwen_local"             # Ollama Qwen3-14B
      voice: "cosyvoice_local"        # CosyVoice2 ONNX
    settings:
      batch_size: 1
      max_retries: 2
      timeout:300

# Реестр провайдеров
providers:
  ocr:
    deepseek_cloud:
      class: "story_analyzer.providers.ocr.deepseek_cloud.DeepSeekOCRProvider"
      config:
        model: "deepseek-ai/DeepSeek-OCR"
        api_key_env: "SILICONFLOW_API_KEY"
    
    paddle_cloud:
      class: "story_analyzer.providers.ocr.paddle_cloud.PaddleOCRCloudProvider"
      config:
        model: "PaddlePaddle/PaddleOCR-VL-1.5"
        api_key_env: "SILICONFLOW_API_KEY"
    
    paddle_local:
      class: "story_analyzer.providers.ocr.paddle_local.PaddleOCRLocalProvider"
      config:
        model_path: "models/paddleocr_vl_1.5.onnx"
  
  translation:
    hunyuan_cloud:
      class: "story_analyzer.providers.translation.hunyuan_cloud.HunyuanMTCloudProvider"
      config:
        model: "tencent/Hunyuan-MT-7B"
        api_key_env: "SILICONFLOW_API_KEY"
    
    hunyuan_local:
      class: "story_analyzer.providers.translation.hunyuan_local.HunyuanMTLocalProvider"
      config:
        ollama_model: "hunyuan-mt:7b"
  
  story:
    qwen_cloud:
      class: "story_analyzer.providers.story.qwen_cloud.QwenStoryProvider"
      config:
        model: "Qwen/Qwen3.5-122B-A10B"
        api_key_env: "SILICONFLOW_API_KEY"
        temperature: 0.3
    
    qwen_long_cloud:
      class: "story_analyzer.providers.story.qwen_long_cloud.QwenLongStoryProvider"
      config:
        model: "Qwen/Qwen3.5-397B-A17B"
        api_key_env: "SILICONFLOW_API_KEY"
        temperature: 0.3
    
    glm_cloud:
      class: "story_analyzer.providers.story.glm_cloud.GLMStoryProvider"
      config:
        model: "zai-org/GLM-4.7"
        api_key_env: "SILICONFLOW_API_KEY"
        temperature: 0.3
    
    qwen_local:
      class: "story_analyzer.providers.story.qwen_local.QwenLocalStoryProvider"
      config:
        ollama_model: "qwen3:14b-q4_K_M"
  
  voice:
    cosyvoice_cloud:
      class: "story_analyzer.providers.voice.cosyvoice_cloud.CosyVoiceCloudProvider"
      config:
        model: "FunAudioLLM/CosyVoice2-0.5B"
        api_key_env: "SILICONFLOW_API_KEY"
    
    moss_cloud:
      class: "story_analyzer.providers.voice.moss_cloud.MOSSCloudProvider"
      config:
        model: "fnlp/MOSS-TTSD-v0.5"
        api_key_env: "SILICONFLOW_API_KEY"
    
    cosyvoice_local:
      class: "story_analyzer.providers.voice.cosyvoice_local.CosyVoiceLocalProvider"
      config:
        model_path: "models/cosyvoice2_0.5b.onnx"
```

### 4.3. Главный оркестратор (`story_analyzer/pipeline.py`)

```python
"""
Story Analyzer Pipeline
Оркестрирует все этапы: OCR → Translation → Story → Script → Voice → Video
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

from .providers.base import OCRProvider, TranslationProvider, StoryProvider, VoiceProvider
from .utils.audio_mixer import AudioMixer
from .utils.video_assembler import VideoAssembler

logger = logging.getLogger(__name__)


@dataclass
class StoryAnalyzerConfig:
    """Конфигурация Story Analyzer"""
    preset: str = "economy"  # economy | quality | local
    source_lang: str = "auto"  # auto | en | ru | jp | ...
    target_lang: str = "ru"
    enable_translation: bool = True
    enable_subtitles: bool = False
    output_dir: str = "story_output"


class StoryAnalyzerPipeline:
    """Главный пайплайн Story Analyzer"""
    
    def __init__(
        self,
        ocr_provider: OCRProvider,
        translation_provider: Optional[TranslationProvider],
        story_provider: StoryProvider,
        voice_provider: VoiceProvider,
        config: StoryAnalyzerConfig
    ):
        self.ocr = ocr_provider
        self.translation = translation_provider
        self.story = story_provider
        self.voice = voice_provider
        self.config = config
        
        self.audio_mixer = AudioMixer()
        self.video_assembler = VideoAssembler()
        
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def process_comic(self, panels_dir: str, metadata_file: str) -> str:
        """
        Полный цикл обработки комикса
        
        Args:
            panels_dir: Путь к папке с PNG-панелями
            metadata_file: Путь к JSON с метаданными (bbox, порядок)
        
        Returns:
            Путь к финальному MP4
        """
        logger.info(f"Starting Story Analyzer pipeline for {panels_dir}")
        
        # Загружаем метаданные
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        # ========== STAGE 2: OCR ==========
        logger.info("Stage 2: OCR processing")
        panels_with_ocr = self._stage_ocr(panels_dir, metadata)
        
        # ========== STAGE 3: TRANSLATION (optional) ==========
        if self.config.enable_translation and self.translation:
            logger.info("Stage 3: Translation")
            panels_with_ocr = self._stage_translate(panels_with_ocr)
        
        # ========== STAGE 4: STORY UNDERSTANDING ==========
        logger.info("Stage 4: Story understanding")
        story_analysis = self._stage_story_analysis(panels_with_ocr)
        
        # ========== STAGE 5: SCRIPT GENERATION ==========
        logger.info("Stage 5: Script generation")
        script = self._stage_script_generation(story_analysis, panels_with_ocr)
        
        # Сохраняем сценарий
        script_path = self.output_dir / "script.json"
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script, f, ensure_ascii=False, indent=2)
        logger.info(f"Script saved to {script_path}")
        
        # ========== STAGE 6: VOICE SYNTHESIS ==========
        logger.info("Stage 6: Voice synthesis")
        audio_files = self._stage_voice_synthesis(script)
        
        # ========== STAGE 7: VIDEO ASSEMBLY ==========
        logger.info("Stage 7: Video assembly")
        video_clips = self._stage_video_generation(panels_dir, script)
        final_video = self._stage_video_assembly(script, audio_files, video_clips)
        
        logger.info(f"Pipeline completed! Final video: {final_video}")
        return str(final_video)
    
    def _stage_ocr(self, panels_dir: str, metadata: Dict) -> List[Dict]:
        """Stage 2: OCR всех панелей"""
        panels_with_ocr = []
        
        for page in metadata["pages"]:
            for panel in page["panels"]:
                panel_path = Path(panels_dir) / panel["image_path"]
                
                # Вызываем OCR провайдер
                ocr_result = self.ocr.extract_text(str(panel_path))
                
                panel_data = {
                    "page_number": page["page_number"],
                    "panel_id": panel["panel_id"],
                    "image_path": panel["image_path"],
                    "bbox": panel["bbox"],
                    "ocr": ocr_result
                }
                panels_with_ocr.append(panel_data)
        
        # Сохраняем промежуточный результат
        ocr_path = self.output_dir / "ocr_results.json"
        with open(ocr_path, "w", encoding="utf-8") as f:
            json.dump(panels_with_ocr, f, ensure_ascii=False, indent=2)
        
        return panels_with_ocr
    
    def _stage_translate(self, panels_with_ocr: List[Dict]) -> List[Dict]:
        """Stage 3: Перевод текста"""
        for panel in panels_with_ocr:
            if "bubbles" in panel["ocr"]:
                for bubble in panel["ocr"]["bubbles"]:
                    original_text = bubble["text"]
                    translated_text = self.translation.translate(
                        original_text,
                        source_lang=self.config.source_lang,
                        target_lang=self.config.target_lang
                    )
                    bubble["text_translated"] = translated_text
        
        return panels_with_ocr
    
    def _stage_story_analysis(self, panels_with_ocr: List[Dict]) -> Dict:
        """Stage 4: Анализ сюжета"""
        return self.story.analyze_panels(panels_with_ocr)
    
    def _stage_script_generation(self, story_analysis: Dict, panels_with_ocr: List[Dict]) -> Dict:
        """Stage 5: Генерация сценария"""
        return self.story.generate_script(story_analysis, panels_with_ocr)
    
    def _stage_voice_synthesis(self, script: Dict) -> Dict[str, str]:
        """Stage 6: Синтез речи"""
        audio_files = {}
        
        for scene in script["scenes"]:
            scene_id = scene["scene_id"]
            
            # Narrator
            if scene.get("narrator"):
                audio_path = self.output_dir / "audio" / f"narrator_{scene_id}.mp3"
                audio_path.parent.mkdir(parents=True, exist_ok=True)
                
                audio_bytes = self.voice.synthesize(
                    text=scene["narrator"],
                    voice_id="onyx",  # Narrator voice
                    emotion="neutral"
                )
                with open(audio_path, "wb") as f:
                    f.write(audio_bytes)
                audio_files[f"narrator_{scene_id}"] = str(audio_path)
            
            # Characters
            for dialogue in scene.get("dialogues", []):
                character = dialogue["character"]
                text = dialogue["text"]
                emotion = dialogue.get("emotion", "neutral")
                
                audio_path = self.output_dir / "audio" / f"char_{character}_{scene_id}.mp3"
                audio_bytes = self.voice.synthesize(
                    text=text,
                    voice_id=self._get_voice_for_character(character),
                    emotion=emotion
                )
                with open(audio_path, "wb") as f:
                    f.write(audio_bytes)
                audio_files[f"char_{character}_{scene_id}"] = str(audio_path)
        
        return audio_files
    
    def _stage_video_generation(self, panels_dir: str, script: Dict) -> List[str]:
        """Stage 7a: Генерация видео-клипов для каждой сцены"""
        # Используем существующий anim_pipeline
        from anim_pipeline import animate_panels
        
        video_clips = []
        for scene in script["scenes"]:
            # Собираем панели для этой сцены
            scene_panels = []
            for page_num in scene["pages"]:
                page_panels = [p for p in panels_dir if f"page_{page_num:03d}" in p]
                scene_panels.extend(page_panels)
            
            # Генерируем видео-клип
            clip_path = self.output_dir / "video" / f"scene_{scene['scene_id']}.mp4"
            clip_path.parent.mkdir(parents=True, exist_ok=True)
            
            animate_panels(
                input_panels=scene_panels,
                output_video=str(clip_path),
                mode="depthflow",
                duration=scene["duration_seconds"]
            )
            video_clips.append(str(clip_path))
        
        return video_clips
    
    def _stage_video_assembly(self, script: Dict, audio_files: Dict, video_clips: List[str]) -> str:
        """Stage 7b: Сборка финального видео"""
        final_video_path = self.output_dir / "final_video.mp4"
        
        self.video_assembler.assemble(
            script=script,
            audio_files=audio_files,
            video_clips=video_clips,
            output_path=str(final_video_path)
        )
        
        return str(final_video_path)
    
    def _get_voice_for_character(self, character: str) -> str:
        """Маппинг персонажей на голоса"""
        # Простой маппинг, можно расширить
        voice_map = {
            "Hero": "alloy",
            "Villain": "echo",
            "Narrator": "onyx"
        }
        return voice_map.get(character, "fable")
```

---

## 5. План реализации

### 5.1. Фазы разработки

**Фаза 1: MVP (2-3 недели)**
- [ ] Реализовать абстракции провайдеров (`providers/base.py`)
- [ ] Интегрировать DeepSeek-OCR (бесплатный OCR)
- [ ] Интегрировать Qwen3.5-122B-A10B (анализ сюжета)
- [ ] Интегрировать CosyVoice2-0.5B (TTS)
- [ ] Простой видео-ассемблер (FFmpeg)
- [ ] Тест на 10-страничном комиксе

**Фаза 2: Расширение (2 недели)**
- [ ] Добавить PaddleOCR-VL-1.5 (качественный OCR)
- [ ] Добавить Hunyuan-MT-7B (перевод)
- [ ] Добавить Qwen3.5-397B-A17B (длинные тома)
- [ ] Улучшить аудио-микшер (паузы, эмоции)
- [ ] Тест на 100-страничном комиксе

**Фаза 3: UI и локальный режим (2 недели)**
- [ ] Добавить вкладку "Story" в Gradio
- [ ] Добавить API эндпоинты в FastAPI
- [ ] Реализовать локальные провайдеры (Ollama, ONNX)
- [ ] Пресеты ECONOMY / QUALITY / LOCAL
- [ ] Документация пользователя

**Фаза 4: Оптимизация (1-2 недели)**
- [ ] Батчинг запросов (экономия API calls)
- [ ] Кэширование результатов
- [ ] Субтитры (опционально)
- [ ] Клонирование голосов
- [ ] Benchmark и оптимизация стоимости

### 5.2. Зависимости

**Python пакеты (добавить в `requirements.txt`):**
```txt
# Для Story Analyzer
requests>=2.31.0          # API calls
pydub>=0.25.1             # Audio mixing
ollama>=0.1.0             # Local LLM (опционально)
onnxruntime>=1.18.0       # Local ONNX inference
```

**Внешние инструменты:**
- FFmpeg (уже есть в ComicSplit)
- Ollama (опционально, для локальных моделей)

### 5.3. Тестовые данные

**Минимальный тест:**
- 10-страничный комикс (например, `exam_imgs/` из репозитория)
- Ожидаемое время: 5-10 минут
- Ожидаемая стоимость: ~$0.05

**Полный тест:**
- 100-страничный комикс
- Ожидаемое время: 30-60 минут
- Ожидаемая стоимость: ~$0.50-1.00

---

## 6. Оценка стоимости и производительности

### 6.1. Стоимость обработки 100-страничного комикса

| Этап | Модель | Количество | Цена за единицу | Итого |
|------|--------|------------|-----------------|-------|
| OCR | DeepSeek-OCR | 500 панелей | FREE | **$0.00** |
| OCR | PaddleOCR-VL-1.5 | 500 панелей | $0.001 | **$0.50** |
| Translation | Hunyuan-MT-7B | 2000 предложений | FREE | **$0.00** |
| Story | Qwen3.5-122B-A10B | 100K tokens input | $0.30/1M | **$0.03** |
| Story | Qwen3.5-122B-A10B | 10K tokens output | $1.20/1M | **$0.012** |
| Voice | CosyVoice2-0.5B | 5000 символов | $0.01/1K | **$0.05** |
| **Итого (ECONOMY)** | | | | **~$0.09** |
| **Итого (QUALITY)** | | | | **~$0.60** |

### 6.2. Время обработки

| Этап | Cloud (ECONOMY) | Cloud (QUALITY) | Local |
|------|-----------------|-----------------|-------|
| OCR | 5-10 мин | 10-15 мин | 30-60 мин |
| Translation | 2-5 мин | 2-5 мин | 20-40 мин |
| Story | 5-10 мин | 15-30 мин | 60-120 мин |
| Voice | 5-10 мин | 10-15 мин | 30-60 мин |
| Video | 10-20 мин | 10-20 мин | 10-20 мин |
| **Итого** | **30-60 мин** | **50-90 мин** | **3-5 часов** |

### 6.3. Требования к ресурсам

**Cloud режим:**
- RAM: ~2 GB (только Python + API calls)
- CPU: Любое (основная нагрузка на API)
- Интернет: Обязателен
- API ключ: SiliconFlow

**Local режим:**
- RAM: ~14 GB (Ollama Qwen3-14B + CosyVoice2)
- CPU: Ryzen 5600H (медленно, но работает)
- Интернет: Не требуется
- Диск: ~20 GB (модели)

---

## 7. Риски и митигация

### 7.1. Технические риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| SiliconFlow недоступен из РФ | Низкая | Критическое | Локальные fallback провайдеры |
| API лимиты (rate limits) | Средняя | Среднее | Батчинг, кэширование, retry logic |
| Низкое качество OCR на рукописном тексте | Средняя | Среднее | PaddleOCR-VL-1.5 (SOTA), ручная правка |
| TTS не справляется с эмоциями | Средняя | Низкое | Ручная настройка промптов, выбор голосов |
| Локальные модели слишком медленные | Высокая | Среднее | Использовать только как fallback |

### 7.2. Финансовые риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Стоимость API выше ожидаемой | Низкая | Низкое | Мониторинг расходов, лимиты |
| Бесплатные модели станут платными | Средняя | Среднее | Переход на локальные альтернативы |
| Необходимость покупки GPU | Низкая | Высокое | Оптимизация под CPU, квантование |

### 7.3. Юридические риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Нарушение авторских прав на комиксы | Средняя | Высокое | Только для личного использования |
| Нарушение ToS API провайдеров | Низкая | Среднее | Соблюдение лимитов, правильное использование |

---

## 8. Заключение

### 8.1. Ключевые выводы

1. **Гибридная архитектура оптимальна:** Локальная предобработка + облачный анализ даёт лучшее соотношение цена/качество.

2. **SiliconFlow — лучший выбор для РФ:** Работает стабильно, есть бесплатные модели, огромный выбор Qwen/GLM/Kimi.

3. **Qwen3.5-122B-A10B — рабочая лошадка:** Отличное качество за $0.04 на комикс.

4. **CosyVoice2-0.5B — лучший TTS:** Поддержка эмоций, клонирование голоса, низкая латентность.

5. **Локальный fallback возможен:** Ollama + ONNX позволяют работать без интернета, хотя и медленно.

### 8.2. Следующие шаги

1. **Немедленно:**
   - Зарегистрироваться на SiliconFlow (https://cloud.siliconflow.cn/)
   - Получить API ключ
   - Протестировать DeepSeek-OCR и Qwen3.5-122B-A10B на 5-10 панелях

2. **