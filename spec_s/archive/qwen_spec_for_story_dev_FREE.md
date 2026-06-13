# 🆓 Полностью бесплатная реализация Story Analyzer

Да, это **абсолютно реально**! Есть три стратегии, от "честно бесплатно" до "почти бесплатно". Разберу каждую.

---

## 📊 Сравнение трёх стратегий

| Стратегия | Стоимость | Качество | Скорость | Сложность |
|-----------|-----------|----------|----------|-----------|
| **A. 100% локально** | $0 | ⭐⭐ | Медленно | Средняя |
| **B. Гибрид (бесплатные API + локально)** | $0 | ⭐⭐⭐ | Быстро | Низкая |
| **C. Почти бесплатно** | ~$0.10/комикс | ⭐⭐⭐⭐ | Очень быстро | Низкая |

---

## 🎯 Стратегия B: Гибрид (РЕКОМЕНДУЮ для старта)

Используем **бесплатные модели SiliconFlow** + **локальный TTS**.

### Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│  STAGE 1: LOCAL PREPROCESSING (уже есть в ComicSplit)      │
│  └─ Panel Split (YOLO INT8) → panels/*.png                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 2: OCR (БЕСПЛАТНЫЙ API)                             │
│  └─ DeepSeek-OCR (SiliconFlow, FREE)                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 3: TRANSLATION (БЕСПЛАТНЫЙ API)                     │
│  └─ Hunyuan-MT-7B (SiliconFlow, FREE)                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 4: STORY UNDERSTANDING (БЕСПЛАТНЫЙ API)             │
│  └─ Qwen2.5-7B-Instruct (SiliconFlow, FREE)                │
│     ⚠️ Качество ниже, чем у Qwen3, но работает             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 5: VOICE SYNTHESIS (ЛОКАЛЬНО, БЕСПЛАТНО)            │
│  └─ CosyVoice2-0.5B (ONNX CPU, ~2GB RAM)                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 6: VIDEO ASSEMBLY (уже есть в ComicSplit)           │
│  └─ FFmpeg + существующий anim_pipeline.py                 │
└─────────────────────────────────────────────────────────────┘
```

### Модели для каждого этапа

#### 1. OCR: DeepSeek-OCR (FREE)

**Почему подходит:**
- ✅ Полностью бесплатно на SiliconFlow (помечена как "限免")
- ✅ Специализирована на OCR документов
- ✅ Конвертирует в Markdown
- ⚠️ Не специализирована на комиксах, но справится

**Ссылки:**
- SiliconFlow: https://cloud.siliconflow.cn/models (ищите "DeepSeek-OCR")
- HuggingFace: https://huggingface.co/deepseek-ai/DeepSeek-OCR

**Интеграция:**

```python
# story_analyzer/providers/ocr/deepseek_free.py
import base64
import requests
from typing import Dict

class DeepSeekOCRFreeProvider:
    """Бесплатный OCR через DeepSeek-OCR"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.siliconflow.cn/v1/chat/completions"
    
    def extract_text(self, image_path: str) -> Dict:
        """Извлечение текста из панели"""
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode()
        
        response = requests.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-ai/DeepSeek-OCR",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_b64}"
                                }
                            },
                            {
                                "type": "text",
                                "text": """Extract all text from this comic panel. 
                                Focus on speech bubbles and narration boxes.
                                Return JSON format:
                                {
                                    "bubbles": [
                                        {"text": "...", "type": "speech|narration"}
                                    ]
                                }"""
                            }
                        ]
                    }
                ],
                "max_tokens": 1024
            }
        )
        
        result = response.json()["choices"][0]["message"]["content"]
        # Парсинг JSON из ответа
        import json
        try:
            return json.loads(result)
        except:
            return {"bubbles": [{"text": result, "type": "unknown"}]}
```

#### 2. Translation: Hunyuan-MT-7B (FREE)

**Почему подходит:**
- ✅ Полностью бесплатно (помечена как "限免")
- ✅ Лидер WMT25 (30/31 языковых пар - 1 место)
- ✅ 33 языка + 5 китайских диалектов
- ✅ 32K контекст

**Ссылки:**
- SiliconFlow: https://cloud.siliconflow.cn/models (ищите "Hunyuan-MT-7B")
- HuggingFace: https://huggingface.co/tencent/Hunyuan-MT-7B

**Интеграция:**

```python
# story_analyzer/providers/translation/hunyuan_free.py
import requests

class HunyuanMTFreeProvider:
    """Бесплатный перевод через Hunyuan-MT-7B"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.siliconflow.cn/v1/chat/completions"
    
    def translate(self, text: str, source_lang: str = "auto", target_lang: str = "ru") -> str:
        """Перевод текста"""
        response = requests.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
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
```

#### 3. Story Understanding: Qwen2.5-7B-Instruct (FREE)

**Почему подходит:**
- ✅ Полностью бесплатно (помечена как "Free")
- ✅ 7B параметров - достаточно для базового анализа
- ⚠️ Это Qwen 2.5, не Qwen 3 - качество ниже
- ⚠️ Может терять контекст на длинных томах

**Ссылки:**
- SiliconFlow: https://cloud.siliconflow.cn/models (ищите "Qwen2.5-7B-Instruct")
- HuggingFace: https://huggingface.co/Qwen/Qwen2.5-7B-Instruct

**Интеграция:**

```python
# story_analyzer/providers/story/qwen_free.py
import requests
import json
from typing import List, Dict

class QwenStoryFreeProvider:
    """Бесплатный анализ сюжета через Qwen2.5-7B"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.siliconflow.cn/v1/chat/completions"
    
    def analyze_panels(self, panels_data: List[Dict]) -> Dict:
        """Анализ сюжета"""
        panels_text = json.dumps(panels_data, ensure_ascii=False, indent=2)
        
        prompt = f"""Analyze this comic panels and extract:
1. Characters (list with descriptions)
2. Plot summary (2-3 sentences)
3. Key events (list)
4. Emotional tone

Panels data:
{panels_text}

Return JSON:
{{
    "characters": [
        {{"name": "...", "description": "...", "role": "protagonist|antagonist|supporting"}}
    ],
    "plot_summary": "...",
    "key_events": ["...", "..."],
    "emotional_tone": "..."
}}"""
        
        response = requests.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "Qwen/Qwen2.5-7B-Instruct",
                "messages": [
                    {"role": "system", "content": "You are a comic book analyst."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 2048,
                "temperature": 0.3
            }
        )
        
        result = response.json()["choices"][0]["message"]["content"]
        try:
            return json.loads(result)
        except:
            return {"plot_summary": result, "characters": [], "key_events": []}
    
    def generate_script(self, story_analysis: Dict, panels_data: List[Dict]) -> Dict:
        """Генерация сценария"""
        prompt = f"""Based on this comic analysis, create a video script.

Story Analysis:
{json.dumps(story_analysis, ensure_ascii=False, indent=2)}

Create scene-by-scene script with:
1. Narrator text
2. Character dialogues
3. Duration (seconds)

Return JSON:
{{
    "title": "Comic Title",
    "scenes": [
        {{
            "scene_id": 1,
            "narrator": "...",
            "dialogues": [
                {{"character": "...", "text": "...", "emotion": "..."}}
            ],
            "duration_seconds": 5.0
        }}
    ]
}}"""
        
        response = requests.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "Qwen/Qwen2.5-7B-Instruct",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4096,
                "temperature": 0.5
            }
        )
        
        result = response.json()["choices"][0]["message"]["content"]
        try:
            return json.loads(result)
        except:
            return {"title": "Unknown", "scenes": []}
```

#### 4. TTS: CosyVoice2-0.5B (ЛОКАЛЬНО, БЕСПЛАТНО)

**Почему подходит:**
- ✅ Полностью бесплатно (локально)
- ✅ 0.5B параметров - влезет в RAM
- ✅ ONNX CPU inference
- ✅ Поддержка эмоций и клонирования голоса
- ⚠️ Медленно на CPU (~1-3 сек на предложение)

**Ссылки:**
- HuggingFace: https://huggingface.co/FunAudioLLM/CosyVoice2-0.5B
- GitHub: https://github.com/FunAudioLLM/CosyVoice

**Установка локально:**

```bash
# 1. Установка зависимостей
pip install onnxruntime
pip install soundfile
pip install numpy

# 2. Скачивание модели
# Вариант A: Через HuggingFace CLI
pip install huggingface_hub
huggingface-cli download FunAudioLLM/CosyVoice2-0.5B --local-dir models/cosyvoice2

# Вариант B: Вручную
# https://huggingface.co/FunAudioLLM/CosyVoice2-0.5B/tree/main
# Скачать все файлы в models/cosyvoice2/
```

**Интеграция:**

```python
# story_analyzer/providers/voice/cosyvoice_local.py
import onnxruntime as ort
import numpy as np
import soundfile as sf
from pathlib import Path

class CosyVoiceLocalProvider:
    """Локальный TTS через CosyVoice2-0.5B"""
    
    def __init__(self, model_dir: str = "models/cosyvoice2"):
        self.model_dir = Path(model_dir)
        
        # Загрузка ONNX сессий
        self.session = ort.InferenceSession(
            str(self.model_dir / "cosyvoice2.onnx"),
            providers=['CPUExecutionProvider']
        )
        
        # Загрузка конфигурации
        self.sample_rate = 22050
    
    def synthesize(self, text: str, voice_id: str = "alloy", emotion: str = "neutral") -> bytes:
        """Синтез речи"""
        # Препроцессинг текста
        input_data = self._preprocess_text(text, voice_id, emotion)
        
        # Инференс
        outputs = self.session.run(None, input_data)
        
        # Постпроцессинг
        audio = self._postprocess_audio(outputs)
        
        # Конвертация в MP3 bytes
        import io
        buffer = io.BytesIO()
        sf.write(buffer, audio, self.sample_rate, format='WAV')
        buffer.seek(0)
        
        # Конвертация WAV → MP3 через ffmpeg
        import subprocess
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as wav_file:
            wav_file.write(buffer.getvalue())
            wav_path = wav_file.name
        
        mp3_path = wav_path.replace('.wav', '.mp3')
        subprocess.run([
            'ffmpeg', '-i', wav_path,
            '-codec:a', 'libmp3lame', '-qscale:a', '2',
            mp3_path
        ], check=True, capture_output=True)
        
        with open(mp3_path, 'rb') as f:
            mp3_bytes = f.read()
        
        # Очистка
        Path(wav_path).unlink()
        Path(mp3_path).unlink()
        
        return mp3_bytes
    
    def _preprocess_text(self, text: str, voice_id: str, emotion: str) -> dict:
        """Препроцессинг текста для модели"""
        # Упрощённая версия - реальная реализация зависит от модели
        # Нужно токенизировать текст и создать input tensor
        # См. документацию CosyVoice2
        raise NotImplementedError("Требуется реализация согласно документации CosyVoice2")
    
    def _postprocess_audio(self, outputs: list) -> np.ndarray:
        """Постпроцессинг аудио"""
        # Извлечение аудио из outputs
        # Реальная реализация зависит от архитектуры модели
        raise NotImplementedError("Требуется реализация согласно документации CosyVoice2")
```

**⚠️ Важно:** Локальный запуск CosyVoice2 требует дополнительной работы по интеграции. Есть более простой альтернативный вариант:

**Альтернатива: Edge TTS (Microsoft, бесплатно)**

```python
# story_analyzer/providers/voice/edge_tts.py
import edge_tts
import asyncio
from pathlib import Path

class EdgeTTSProvider:
    """Бесплатный TTS через Microsoft Edge"""
    
    def __init__(self):
        self.voices = {
            "narrator": "ru-RU-DmitryNeural",  # Мужской голос
            "hero": "ru-RU-IvanNeural",         # Молодой мужской
            "heroine": "ru-RU-SvetlanaNeural",  # Женский
            "villain": "ru-RU-PavelNeural"      # Зловещий мужской
        }
    
    async def synthesize_async(self, text: str, voice_id: str = "narrator") -> bytes:
        """Асинхронный синтез речи"""
        voice = self.voices.get(voice_id, self.voices["narrator"])
        
        communicate = edge_tts.Communicate(text, voice)
        
        import io
        buffer = io.BytesIO()
        
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])
        
        buffer.seek(0)
        return buffer.getvalue()
    
    def synthesize(self, text: str, voice_id: str = "narrator") -> bytes:
        """Синхронный синтез речи"""
        return asyncio.run(self.synthesize_async(text, voice_id))

# Установка
# pip install edge-tts
```

**Преимущества Edge TTS:**
- ✅ Полностью бесплатно
- ✅ Не требует загрузки моделей
- ✅ Высокое качество (Microsoft Neural TTS)
- ✅ Поддержка русского языка
- ✅ Быстро (облачный сервис)
- ⚠️ Требует интернет
- ⚠️ Нет клонирования голоса

---

## 🎯 Стратегия A: 100% локально (без интернета)

Если нужна полная автономность:

### Модели

| Этап | Модель | Размер | RAM | Скорость |
|------|--------|--------|-----|----------|
| OCR | PaddleOCR (классический, не VL) | ~100 MB | ~500 MB | ~1 сек/панель |
| Translation | Hunyuan-MT-7B (Ollama) | ~14 GB | ~14 GB | ~5-10 сек/предложение |
| Story | Qwen3-8B (Ollama) | ~6 GB | ~8 GB | ~30-60 сек/страница |
| TTS | CosyVoice2-0.5B (ONNX) | ~1 GB | ~2 GB | ~1-3 сек/предложение |

**Установка Ollama:**

```bash
# 1. Установка Ollama
winget install Ollama.Ollama

# 2. Загрузка моделей
ollama pull qwen3:8b
ollama pull hunyuan-mt:7b

# 3. Проверка
ollama run qwen3:8b "Привет!"
```

**Интеграция Ollama:**

```python
# story_analyzer/providers/story/qwen_local.py
import ollama
import json
from typing import List, Dict

class QwenLocalProvider:
    """Локальный анализ сюжета через Ollama"""
    
    def __init__(self, model: str = "qwen3:8b"):
        self.model = model
    
    def analyze_panels(self, panels_data: List[Dict]) -> Dict:
        """Анализ сюжета"""
        panels_text = json.dumps(panels_data, ensure_ascii=False, indent=2)
        
        prompt = f"""Analyze this comic panels and extract:
1. Characters (list with descriptions)
2. Plot summary (2-3 sentences)
3. Key events (list)

Panels data:
{panels_text}

Return JSON."""
        
        response = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        result = response["message"]["content"]
        try:
            return json.loads(result)
        except:
            return {"plot_summary": result, "characters": [], "key_events": []}
```

**Проблемы локальной стратегии:**
- ❌ Очень медленно (3-5 часов на 100-страничный комикс)
- ❌ Качество Qwen3-8B ниже, чем у облачных Qwen3.5-122B
- ❌ Hunyuan-MT-7B занимает 14 GB RAM - почти вся память
- ❌ Нужно 20 GB свободного места на диске

---

## 🎯 Стратегия C: Почти бесплатно (оптимальное качество)

Если готовы потратить ~$0.10-0.50 на комикс:

### Модели

| Этап | Модель | Цена | Качество |
|------|--------|------|----------|
| OCR | DeepSeek-OCR | FREE | ⭐⭐⭐ |
| Translation | Hunyuan-MT-7B | FREE | ⭐⭐⭐⭐⭐ |
| Story | Qwen3.5-122B-A10B | ~$0.04/комикс | ⭐⭐⭐⭐ |
| TTS | CosyVoice2-0.5B (API) | ~$0.05/комикс | ⭐⭐⭐⭐ |
| **Итого** | | **~$0.09** | **Отлично** |

Это **лучшее соотношение цена/качество**.

---

## 📋 Пошаговый план внедрения (Стратегия B)

### Фаза 1: Подготовка (1 день)

1. **Регистрация на SiliconFlow:**
   - https://cloud.siliconflow.cn/
   - Получить API ключ
   - Проверить доступ к бесплатным моделям

2. **Установка зависимостей:**
```bash
pip install edge-tts
pip install requests
pip install pillow
```

3. **Создание структуры модуля:**
```
story_analyzer/
├── __init__.py
├── pipeline.py
├── providers/
│   ├── __init__.py
│   ├── base.py
│   ├── ocr/
│   │   └── deepseek_free.py
│   ├── translation/
│   │   └── hunyuan_free.py
│   ├── story/
│   │   └── qwen_free.py
│   └── voice/
│       └── edge_tts.py
└── utils/
    ├── audio_mixer.py
    └── video_assembler.py
```

### Фаза 2: MVP (3-5 дней)

1. **Реализовать провайдеры** (код выше)
2. **Создать pipeline.py** - оркестратор
3. **Тест на 5-10 панелях**
4. **Добавить вкладку "Story" в Gradio**

### Фаза 3: Интеграция с Video (2-3 дня)

1. **Аудио-микшер** (объединение narrator + characters)
2. **Синхронизация с видео** (использовать существующий `anim_pipeline.py`)
3. **Финальная сборка MP4**

### Фаза 4: UI и документация (2 дня)

1. **Gradio вкладка "Story Analyzer"**
2. **Настройки провайдеров**
3. **Пресеты ECONOMY / QUALITY**
4. **Документация пользователя**

---

## 💡 Рекомендации по снижению требований к качеству

Если использовать **бесплатные модели**, качество будет ниже. Вот как компенсировать:

### 1. OCR: Улучшение через постобработку

```python
def postprocess_ocr(ocr_result: Dict) -> Dict:
    """Улучшение результатов OCR"""
    # Исправление частых ошибок
    text = ocr_result.get("text", "")
    
    # Замена типичных ошибок OCR
    replacements = {
        "l": "I",  # Путает I и l
        "0": "O",  # Путает 0 и O
        "5": "S",  # Путает 5 и S
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    # Удаление лишних пробелов
    text = " ".join(text.split())
    
    return {"text": text, "confidence": 0.8}
```

### 2. Story: Разбиение на главы

Вместо анализа всего тома сразу:

```python
def analyze_by_chapter(pages: List[Dict], pages_per_chapter: int = 20):
    """Анализ по главам для улучшения качества"""
    chapters = []
    
    for i in range(0, len(pages), pages_per_chapter):
        chapter_pages = pages[i:i+pages_per_chapter]
        chapter_analysis = story_provider.analyze_panels(chapter_pages)
        chapters.append(chapter_analysis)
    
    # Финальная сборка
    full_analysis = merge_chapter_analyses(chapters)
    return full_analysis
```

### 3. TTS: Использование разных голосов

```python
voice_mapping = {
    "narrator": "ru-RU-DmitryNeural",
    "male_hero": "ru-RU-IvanNeural",
    "female_hero": "ru-RU-SvetlanaNeural",
    "villain": "ru-RU-PavelNeural",
    "child": "ru-RU-KirillNeural",
    "old_man": "ru-RU-DmitryNeural",  # Тот же, но медленнее
}
```

### 4. Video: Упрощение анимации

Использовать `opencv_zoom` вместо `depthflow` для ускорения.

---

## 🎬 Финальная рекомендация

**Начните со Стратегии B (гибрид):**

1. ✅ Бесплатно
2. ✅ Быстро (30-60 минут на комикс)
3. ✅ Приемлемое качество
4. ✅ Минимум настройки

**Позже улучшите:**

- Замените `Qwen2.5-7B` на `Qwen3-8B` локально (лучшее качество)
- Или перейдите на Стратегию C (~$0.10/комикс, отличное качество)

**Стоимость 100-страничного комикса:**

| Стратегия | Время | Стоимость | Качество |
|-----------|-------|-----------|----------|
| B (гибрид) | 30-60 мин | **$0** | ⭐⭐⭐ |
| C (почти бесплатно) | 15-30 мин | **$0.10** | ⭐⭐⭐⭐ |
| Из прошлой спеки | 10-20 мин | **$0.50** | ⭐⭐⭐⭐⭐ |

Готов помочь с реализацией любого из вариантов! С какого этапа начнём? 🚀