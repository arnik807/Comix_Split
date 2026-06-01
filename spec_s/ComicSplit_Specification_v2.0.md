# ComicSplit — Техническая Спецификация v2.0
### Документ для реализации через Claude Code

> **Для текущей сборки MVP** см. [ComicSplit_Documentation.md](ComicSplit_Documentation.md) и [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).  
> Этот файл — **целевая** архитектура (Go, Wails, gRPC); фактическая реализация — Python MVP + частичный Go.

---

**Проект:** ComicSplit — десктопная утилита автоматического сплитирования панелей комиксов  
**Версия спецификации:** 2.0 (документ не менялся по сути; **статус фаз** обновлён май 2026)  
**Дата:** 2026  
**Статус реализации (31.05.2026):** Split MVP + Anim MVP (CLI/Gradio/:8000); фазы 1–2 **частично**; Wails/gRPC **не начаты**. Детали: [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

---

## Содержание

1. [Контекст и цель проекта](#1-контекст-и-цель-проекта)
2. [Аппаратная база и ограничения](#2-аппаратная-база-и-ограничения)
3. [Что строим — полное описание](#3-что-строим--полное-описание)
4. [Архитектура системы](#4-архитектура-системы)
5. [ML-пайплайн — детальное описание](#5-ml-пайплайн--детальное-описание)
6. [Интерактивный редактор масок](#6-интерактивный-редактор-масок)
7. [Технологический стек](#7-технологический-стек)
8. [Структура проекта](#8-структура-проекта)
9. [Roadmap с задачами](#9-roadmap-с-задачами)
10. [Риски и митигация](#10-риски-и-митигация)
11. [Глоссарий](#11-глоссарий)

---

## 1. Контекст и цель проекта

### 1.1 Зачем это нужно

Комикс — это последовательность страниц, каждая из которых разбита на **панели** (отдельные кадры с изображением). Для множества задач нужно работать не со страницей целиком, а с отдельными панелями:

- **Чтение на телефоне** — приложения типа "Panel View" показывают по одной панели, увеличивая её на весь экран
- **Конвертация в видео** — каждая панель становится отдельным кадром видеоролика
- **Озвучка** — текст из каждой панели озвучивается по очереди
- **Обучение нейросетей** — дата-сеты требуют отдельных панелей, а не целых страниц
- **Архивирование и каталогизация** — поиск по содержимому конкретной сцены

Вручную вырезать панели из комикса на 200 страниц — это часы монотонной работы. Существующие инструменты либо требуют GPU и облака, либо работают только с простыми прямоугольными сетками, либо не обрабатывают сложные случаи: наслаивающиеся панели, диагональные границы, круглые вставки, splash-страницы.

### 1.2 Что представляет собой результат

Пользователь перетаскивает файл (CBZ, CBR, ZIP) или папку в окно приложения. Утилита:
1. Анализирует каждую страницу и находит все панели
2. Показывает страницы с наложенными цветными полигонами поверх каждой найденной панели
3. Даёт пользователю возможность вручную скорректировать любую маску (потянуть за вершину полигона, добавить/удалить точку, нарисовать новый сектор)
4. После подтверждения — вырезает каждую панель в отдельный PNG-файл и сохраняет в указанную папку

### 1.3 Название и идентификация

- **Кодовое имя:** ComicSplit
- **Целевая ОС:** Windows 11 (primary), Windows 10 (совместимость)
- **Язык интерфейса:** Русский (с возможностью расширения)

---

## 2. Аппаратная база и ограничения

Это **критически важный раздел**. Все технологические решения приняты с учётом конкретного железа разработчика и целевой аудитории.

### 2.1 Характеристики машины разработчика

| Компонент | Характеристика | Значение для проекта |
|---|---|---|
| CPU | AMD Ryzen 5 5600H, 6 ядер / 12 потоков, 3.3 GHz (Zen 3) | Основная вычислительная мощность. 12 потоков хорошо утилизируются ONNX Runtime и воркер-пулом Go |
| GPU | AMD Radeon Graphics (iGPU, RDNA2, ~1 GB shared VRAM) | **Практически бесполезен для ML.** 1 GB shared memory недостаточно даже для MobileSAM inference. Используется только для отрисовки UI |
| RAM | 16 GB DDR4-3200 | Главный ресурсный constraint. Модели + Python runtime + Go + UI не должны суммарно превышать ~10–12 GB |
| Диск | 477 GB SSD | Достаточно. Важна скорость чтения при распаковке CBZ/CBR |
| ОС | Windows 11 | ROCm (AMD GPU ML framework) на Windows поддерживается крайне ограниченно и нестабильно — исключён из рассмотрения |

### 2.2 Почему GPU не используется

**AMD Radeon iGPU и ML:**
- ROCm (аналог CUDA для AMD) официально поддерживает только дискретные GPU серии RX 6000+ и RX 7000+
- Мобильные APU (встроенная графика в Ryzen 5000H) в список поддерживаемых устройств ROCm не входят
- На Windows ROCm поддерживается ещё хуже — AMD фактически прекратила его развитие для Windows после версии 5.x
- DirectML работает с AMD через Direct3D 12, но реальное ускорение минимально, стабильность нестабильна

**Вывод:** всё ML-вычисление делается на CPU через ONNX Runtime с многопоточной оптимизацией. CPU-only режим — это не временный костыль, а основной режим работы утилиты.

---

## 3. Что строим — полное описание

### 3.1 Основной пользовательский сценарий (Happy Path)

```
1. Пользователь запускает ComicSplit.exe
2. Перетаскивает файл "SpiderMan_Vol1.cbz" в окно приложения
3. Нажимает "Анализировать" — запускается ML-пайплайн
4. На каждой странице появляются цветные полупрозрачные полигоны поверх панелей
5. Пользователь просматривает результат постранично
6. На странице 12 YOLO неправильно разбил splash-панель — тянет вершину полигона, исправляя границу
7. На странице 47 лишний сектор — кликает на него, нажимает Delete
8. Нажимает "Экспортировать", выбирает папку назначения
9. Утилита вырезает каждую панель: SpiderMan_Vol1/001_p01_panel_01.png ...
10. Открывается проводник с результатами
```

### 3.2 Входные форматы

| Формат | Описание | Техническая реализация |
|---|---|---|
| `.cbz` | Comic Book ZIP — архив ZIP с изображениями внутри | `archive/zip` стандартная библиотека Go |
| `.cbr` | Comic Book RAR — архив RAR с изображениями | `github.com/nwaples/rardecode` |
| `.zip` | Обычный ZIP с изображениями | То же, что CBZ |
| Папка | Директория с PNG/JPG файлами | `os.ReadDir` Go |

Порядок страниц определяется **лексикографической сортировкой** имён файлов внутри архива.

### 3.3 Выходной формат

```
{output_dir}/
└── {comic_title}/
    ├── 001_p001_panel_01.png
    ├── 002_p001_panel_02.png
    ├── 003_p002_panel_01.png
    ...
```

- Первые 3 цифры — **глобальный порядковый номер** (сквозной через весь комикс, нужен для сортировки в медиаплеерах)
- `pXXX` — номер страницы
- `panel_NN` — порядковый номер панели на странице в правильном порядке чтения

### 3.4 Edge Cases, которые нужно обрабатывать

- **Splash page** — одна большая панель на всю страницу → выдаётся как одна панель
- **Overlapping panels** — панели физически наслаиваются → требует polygon masks, не bbox
- **Borderless panels** — без явной рамки, граница по контрасту контента
- **Blank/transition pages** — пустые страницы без панелей → пропускаются
- **Double-page spreads** — панель на два разворота → определяется по соотношению сторон

---

## 4. Архитектура системы

### 4.1 Общая схема

Система состоит из двух процессов, взаимодействующих через IPC:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Go Process (основной)                         │
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────────────┐  │
│  │  File Reader  │    │  Worker Pool  │    │   Wails UI        │  │
│  │  CBZ/CBR/dir  │───▶│  N goroutines │◀──▶│   React + Konva   │  │
│  └──────────────┘    └──────┬───────┘    └───────────────────┘  │
└─────────────────────────────┼───────────────────────────────────┘
                              │ gRPC / subprocess IPC
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Python Process (ML worker)                        │
│                                                                   │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────┐             │
│  │   OpenCV   │  │ YOLOv11n-seg │  │  MobileSAM  │             │
│  │  fast path │─▶│   ONNX CPU   │─▶│  ONNX CPU   │             │
│  └────────────┘  └──────────────┘  └──────┬──────┘             │
└─────────────────────────────────────────────┼───────────────────┘
                                              │ JSON: [{panel_id, polygon, confidence}]
                                              ▼
                              ┌─────────────────────┐
                              │  Python OpenCV Crop  │
                              │  Polygon → PNG       │
                              └─────────────────────┘
```

### 4.2 Почему два процесса (Go + Python), а не один

**Python нельзя убрать:** ONNX Runtime, Ultralytics YOLO, MobileSAM — это Python-экосистема. Биндинги для Go существуют, но значительно беднее и хуже документированы.

**Go нельзя убрать:** нативный параллелизм, лёгкое потребление памяти, быстрая сборка в EXE, нативная интеграция с Wails для desktop UI.

**Разделение ответственности:**
- Go: файловая система, очередь задач, параллелизм, UI-события, сохранение результатов
- Python: всё, что связано с моделями и numpy

### 4.3 IPC стратегия по фазам

**Фаза 1–2 (PoC → Go core):** subprocess IPC. Go запускает `python worker.py`, передаёт base64 JSON через stdin, получает JSON из stdout. Просто, без зависимостей.

**Фаза 3–4 (интеграция → UI):** gRPC. Python поднимает gRPC-сервер на localhost, Go — клиент.

```protobuf
message AnalyzeRequest {
  bytes image_data = 1;
  string image_format = 2;
  float confidence_threshold = 3;
}

message Panel {
  int32 id = 1;
  repeated Point polygon = 2;
  float confidence = 3;
  int32 reading_order = 4;
}

message AnalyzeResponse {
  repeated Panel panels = 1;
  float processing_time_ms = 2;
  string mode_used = 3;  // "opencv_only", "yolo", "yolo+sam"
}
```

### 4.4 Параллелизм

Worker pool в Go: количество воркеров = `min(runtime.NumCPU()/2, 4)`. При 12 потоках Ryzen 5600H — 4 воркера. 4 параллельных Python-процесса с загруженными моделями займут ~4–6 GB RAM — при 16 GB приемлемо. Если памяти не хватает — fallback на 2 воркера через автодетекцию: `maxWorkers = min(4, freeRAM_GB / 3)`.

---

## 5. ML-пайплайн — детальное описание

### 5.1 Трёхуровневый каскад

Ключевая идея: **не гонять тяжёлые модели на простых страницах**. Каскад — три уровня, каждый следующий запускается только если предыдущего недостаточно.

```
Страница комикса
      │
      ▼
┌─────────────────────────────────────────────┐
│         Уровень 1: OpenCV Fast Path          │
│  grayscale → adaptive threshold → dilate    │
│  → find contours → filter → reading order  │
│  Скорость: 20–80ms    Покрытие: ~75%        │
└────────────────────┬────────────────────────┘
                     │ confidence < 0.7 OR < 2 панелей OR overlapping
                     ▼
┌─────────────────────────────────────────────┐
│         Уровень 2: YOLOv11n-seg              │
│  resize to 640x640 → ONNX inference         │
│  → NMS → polygon masks → reading order     │
│  Скорость: 80–250ms   Покрытие: ~92%        │
└────────────────────┬────────────────────────┘
                     │ confidence < 0.6 OR overlapping OR irregular
                     ▼
┌─────────────────────────────────────────────┐
│         Уровень 3: MobileSAM refinement      │
│  bbox от YOLO → SAM encoder (1 раз/стр)    │
│  → decoder для каждой панели → pixel mask  │
│  Скорость: +300–800ms  Покрытие: ~98%      │
└─────────────────────────────────────────────┘
```

### 5.2 Уровень 1: OpenCV Fast Path

Чисто классический computer vision, без ML. Работает за миллисекунды.

**Алгоритм:**
1. Конвертировать в grayscale
2. `cv2.adaptiveThreshold` — лучше обычного для неравномерного освещения
3. `cv2.dilate` — утолщаем границы панелей (делаем их непрерывными)
4. `cv2.findContours` — находим замкнутые контуры
5. Фильтрация: контуры < 2% площади страницы = шум; ratio > 20:1 = линии, не панели
6. Слияние перекрывающихся bbox
7. Reading order: кластеризация в горизонтальные полосы → сортировка

**Когда достаточно:** равномерные прямоугольные панели с белыми промежутками. Типичный western comic.

**Когда недостаточно:** диагональные границы, отсутствующие рамки, наслоения, круглые панели.

### 5.3 Уровень 2: YOLOv11n-seg

YOLO — нейросеть для детекции объектов. Версия `v11n-seg` — самая лёгкая с **instance segmentation**: выдаёт polygon маску произвольной формы, не просто bbox.

**Почему nano-версия:** модель ~3 MB, 80–200ms на CPU. Если качества не хватит — апгрейд до `s` (small) без изменения кода.

**Проблема:** стандартный YOLOv11 обучен на COCO (люди, машины) — не на комиксах. Варианты решения:
1. Взять готовую fine-tuned модель с HuggingFace (поиск: `comic panel detection yolo segmentation`)
2. Дообучить на датасете DCM772 (772 страницы с аннотациями) или Manga109
3. Использовать Magiv3 как детектор с экспортом в ONNX

```python
model = YOLO("comic_panels_v11n.onnx")
results = model(image, imgsz=640, conf=0.5, iou=0.45)
for result in results:
    for mask, box, conf in zip(result.masks.xy, result.boxes.xyxy, result.boxes.conf):
        # mask — polygon points в координатах оригинального изображения
        # box — bbox [x1, y1, x2, y2]
        # conf — уверенность модели 0..1
```

### 5.4 Уровень 3: MobileSAM

SAM (Segment Anything Model) — foundation model для сегментации. Принимает промпт (bbox) и возвращает pixel-perfect маску.

**Почему MobileSAM, а не SAM2:** SAM2 (ViT-B) ~300 MB weights, тяжёлый inference. MobileSAM ~40 MB, в 60x быстрее, качество незначительно хуже. На CPU с 16 GB RAM — единственный реальный вариант.

**Как используется:**
1. YOLO нашёл панели → bbox как box prompt в MobileSAM
2. SAM encoder обрабатывает изображение **один раз на страницу** (самая тяжёлая операция)
3. SAM decoder для каждой панели отдельно (лёгкая операция)
4. Бинарная маска → `cv2.findContours` → polygon coordinates

### 5.5 Reading Order Algorithm

**Для LTR (западный комикс):**
```
1. Кластеризуем панели в "строки" (overlap по Y > 30% → одна строка)
2. Сортируем строки сверху вниз по median Y
3. Внутри строки — сортируем слева направо по X
```

**Для RTL (манга):**
```
То же самое, но внутри строки — справа налево
Автодетекция RTL: текстовые блоки содержат японские символы (UTF-8 range U+3040–U+9FFF)
```

### 5.6 Вырезка панели по маске

**Простой случай (прямоугольная панель):**
```python
x1, y1, x2, y2 = bbox
panel_image = original_image[y1:y2, x1:x2]
```

**Сложный случай (нестандартная форма / наслоение):**
```python
# Создаём маску того же размера, что страница
mask = np.zeros(original_image.shape[:2], dtype=np.uint8)
cv2.fillPoly(mask, [polygon_points], 255)

# Применяем маску — прозрачность там, где форма нестандартная
panel_rgba = cv2.cvtColor(original_image, cv2.COLOR_RGB2RGBA)
panel_rgba[:, :, 3] = mask  # alpha channel = маска

# Кропаем по bbox полигона и сохраняем с прозрачностью
x, y, w, h = cv2.boundingRect(polygon_points)
panel_cropped = panel_rgba[y:y+h, x:x+w]
cv2.imwrite("panel.png", panel_cropped)
```

Прозрачный фон в PNG — важно для наслаивающихся панелей с нестандартной геометрией.

### 5.7 Quantization

```python
from onnxruntime.quantization import quantize_dynamic, QuantType

quantize_dynamic(
    "comic_panels_v11n.onnx",
    "comic_panels_v11n_int8.onnx",
    weight_type=QuantType.QInt8
)
# Ожидаемый результат: 1.5–2x ускорение, 2–4x снижение размера
```

---

## 6. Интерактивный редактор масок

Ключевая UI-фича. ML-модели не идеальны — пользователь должен иметь возможность исправить ошибки перед экспортом.

### 6.1 Концепция

После завершения анализа каждая страница отображается с наложенными цветными полупрозрачными полигонами. Каждый полигон — **редактируемая маска** панели. Вершины полигона — перетаскиваемые точки.

```
┌──────────────────────────────────────────────────────────────┐
│  Страница 12 из 48                       [◀ Пред] [След ▶]  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   ╔══════════════╗    ╔═══════════════╗                      │
│   ║  ПАНЕЛЬ 1    ║    ║   ПАНЕЛЬ 2    ║                      │
│   ║  (синий 25%) ║    ║  (зелён. 25%) ║                      │
│   ║              ║    ║               ║                      │
│   ╚════•════•════╝    ╚════•═════•════╝                      │
│             ↑                                                │
│        вершина — перетаскиваема                              │
│                                                              │
│   ╔══════════════════════════════════════════╗               │
│   ║              ПАНЕЛЬ 3 (оранжевый 25%)    ║               │
│   ╚══════════════════════════════════════════╝               │
│                                                              │
│  [✏ Добавить панель]  [↺ Авто-анализ]  [✓ Принять страницу] │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 Технология: React + Konva.js

**Konva.js** — canvas-библиотека для React с поддержкой интерактивных Shape-объектов.

Почему Konva, а не SVG:
- Canvas API быстрее SVG при рендеринге изображений высокого разрешения
- Draggable shapes встроены нативно — минимум кастомного кода
- Хорошо документирован, активно поддерживается

```jsx
import { Stage, Layer, Image, Line, Circle } from 'react-konva';

function PanelEditor({ pageImage, panels, onPanelsChange }) {
  return (
    <Stage width={canvasWidth} height={canvasHeight}>

      {/* Слой 1: страница комикса как фон */}
      <Layer>
        <Image image={pageImage} />
      </Layer>

      {/* Слой 2: редактируемые полигоны */}
      <Layer>
        {panels.map(panel => (
          <EditablePolygon
            key={panel.id}
            points={panel.polygon}
            color={PANEL_COLORS[panel.id % PANEL_COLORS.length]}
            onPointDrag={(newPoints) => updatePanel(panel.id, newPoints)}
            onDelete={() => deletePanel(panel.id)}
          />
        ))}
      </Layer>

    </Stage>
  );
}

function EditablePolygon({ points, color, onPointDrag, onDelete }) {
  return (
    <>
      {/* Полупрозрачная заливка полигона */}
      <Line
        points={points.flat()}
        closed={true}
        fill={color + "40"}    // 40 hex = 25% opacity
        stroke={color}
        strokeWidth={2}
        onClick={handleSelect}
      />

      {/* Перетаскиваемые вершины */}
      {points.map((point, i) => (
        <Circle
          key={i}
          x={point[0]} y={point[1]}
          radius={6}
          fill="white" stroke={color} strokeWidth={2}
          draggable
          onDragMove={(e) => {
            const newPoints = [...points];
            newPoints[i] = [e.target.x(), e.target.y()];
            onPointDrag(newPoints);
          }}
        />
      ))}
    </>
  );
}
```

### 6.3 Полный набор операций редактора

| Операция | Как выполняется | Техническая реализация |
|---|---|---|
| **Переместить вершину** | Перетащить круглую точку | `draggable` Circle с `onDragMove` обновляет points |
| **Добавить вершину** | Двойной клик на ребре полигона | Находим ближайшее ребро, вставляем точку в середину отрезка |
| **Удалить вершину** | ПКМ на вершине → "Удалить точку" | Удаляем точку из массива (минимум 3 точки в полигоне) |
| **Удалить панель** | Клик → клавиша Del или кнопка | Удаляем panel из state |
| **Добавить панель** | Кнопка "Добавить" → рисуем кликами | Режим рисования: клики создают точки, двойной клик замыкает полигон |
| **Переместить панель** | Перетащить за центр | `draggable` на Line, смещаем все точки |
| **Изменить порядок** | Drag-and-drop в боковой панели | Массив panels переупорядочивается, reading_order обновляется |
| **Undo** | Ctrl+Z | Стек предыдущих состояний (до 50 шагов) |
| **Redo** | Ctrl+Y / Ctrl+Shift+Z | Стек следующих состояний |
| **Принять страницу** | Кнопка или Ctrl+Enter | Страница помечается reviewed, переход к следующей |
| **Принять всё** | Кнопка | Все страницы без ручной проверки → сразу экспорт |
| **Авто-перезапуск** | Кнопка "Авто-анализ" | Повторный ML-анализ с другими параметрами confidence |

### 6.4 TypeScript типы данных

```typescript
interface Point { x: number; y: number; }

interface Panel {
  id: string;                    // UUID
  polygon: Point[];              // вершины в координатах оригинала
  confidence: number;            // уверенность модели (0..1)
  reading_order: number;         // порядок чтения
  source: 'opencv' | 'yolo' | 'yolo+sam' | 'manual';
  reviewed: boolean;
}

interface PageState {
  page_number: number;
  image_url: string;             // локальный URL для Wails
  original_width: number;
  original_height: number;
  panels: Panel[];
  reviewed: boolean;
}

interface AppState {
  pages: PageState[];
  current_page: number;
  history: PageState[][];        // для undo
  history_index: number;
}
```

### 6.5 Масштабирование координат

Страница комикса может быть 2000×3000px, canvas в UI — 600×900px. Нужна явная трансформация:

```typescript
const scaleX = originalWidth / canvasWidth;
const scaleY = originalHeight / canvasHeight;

// Оригинал → Canvas (для отображения)
const displayPolygon = panel.polygon.map(p => ({ x: p.x / scaleX, y: p.y / scaleY }));

// Canvas → Оригинал (при сохранении правок)
const savePolygon = displayPolygon.map(p => ({ x: p.x * scaleX, y: p.y * scaleY }));
```

---

## 7. Технологический стек

### 7.1 Полная таблица технологий

| Категория | Технология | Версия | Функционал | Обоснование | Документация |
|---|---|---|---|---|---|
| **Язык — ядро** | Go | 1.22+ | Оркестрация, файловая система, воркер-пул, CLI | Нативный параллелизм, минимальная память, один EXE без зависимостей | [go.dev/doc](https://go.dev/doc/) |
| **Язык — ML** | Python | 3.11 | Inference моделей, numpy, OpenCV, post-processing | Единственная экосистема для ONNX Runtime + YOLO + SAM. Python 3.11 быстрее 3.10 на ~25% | [docs.python.org/3.11](https://docs.python.org/3.11/) |
| **Детекция панелей** | YOLOv11n-seg | latest | Обнаружение панелей + polygon маски | 3 MB модель, 80–200ms на CPU, instance segmentation встроена | [docs.ultralytics.com/models/yolo11](https://docs.ultralytics.com/models/yolo11/) |
| **Уточнение масок** | MobileSAM | 1.0 | Pixel-perfect сегментация по bbox-промпту | 40 MB vs 2.4 GB SAM2, в 60x быстрее, реально работает на CPU | [github.com/ChaoningZhang/MobileSAM](https://github.com/ChaoningZhang/MobileSAM) |
| **CV preprocessing** | OpenCV | 4.10+ | Grayscale, threshold, morphology, contours, crop, PNG export | Уровень 1 каскада — быстрый путь без ML для простых страниц | [docs.opencv.org/4.10.0](https://docs.opencv.org/4.10.0/) |
| **CV вспомогательное** | scikit-image | 0.24+ | Canny edges, connected components, region merging | Дополняет OpenCV для топологической обработки edge cases | [scikit-image.org/docs](https://scikit-image.org/docs/stable/) |
| **ML Runtime** | ONNX Runtime | 1.18 (CPU) | Исполнение .onnx моделей, multi-thread CPU inference | Единый рантайм для всех моделей. INT8 quantization встроена | [onnxruntime.ai/docs](https://onnxruntime.ai/docs/) |
| **Числа / матрицы** | NumPy | 1.26+ | Пиксельные массивы, маски, трансформации | Стандарт для всех ML-операций в Python | [numpy.org/doc](https://numpy.org/doc/) |
| **IPC v1** | subprocess + JSON | stdlib | Передача задач Go → Python (PoC фаза) | Нулевые зависимости, base64 для изображений | stdlib |
| **IPC v2** | gRPC + Protobuf | grpc-go 1.64 | Типизированный бинарный протокол Go↔Python | Эффективная передача bytes, типизация | [grpc.io/docs](https://grpc.io/docs/languages/go/quickstart/) |
| **CBZ reader** | archive/zip | Go stdlib | Чтение CBZ в memory stream | CBZ = ZIP, встроено в Go | [pkg.go.dev/archive/zip](https://pkg.go.dev/archive/zip) |
| **CBR reader** | rardecode | 1.1+ | Чтение CBR архивов | CBR = RAR. Чистый Go, без CGO | [github.com/nwaples/rardecode](https://github.com/nwaples/rardecode) |
| **UI framework** | Wails | v2 | Desktop window с Go backend и React фронтендом | Go-нативный: нет Node.js в runtime, бандл ~10 MB | [wails.io/docs](https://wails.io/docs/introduction) |
| **Canvas редактор** | Konva.js + react-konva | 9.x | Интерактивные полигоны с draggable вершинами | Canvas-based (быстрее SVG), draggable встроен | [konvajs.org/docs](https://konvajs.org/docs/react/) |
| **UI компоненты** | React + TypeScript | 18+ | Компонентная архитектура фронтенда | Стандарт для Wails v2 | [react.dev](https://react.dev/) |
| **State management** | Zustand | 4.x | Глобальный state редактора (страницы, панели, undo) | Минималистичен, без boilerplate, работает с TypeScript | [github.com/pmndrs/zustand](https://github.com/pmndrs/zustand) |
| **UI прототип** | Gradio | 4.x | Web-интерфейс для тестирования ML (только PoC) | 10 строк кода для визуализации масок | [gradio.app/docs](https://www.gradio.app/docs/) |
| **Quantization** | ONNX quantization tools | — | INT8/FP16 конвертация моделей | 1.5–2x ускорение на CPU, 2–4x снижение RAM | [onnxruntime.ai/quantization](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html) |
| **Terminal UI** | bubbletea | 0.26+ | Progress bar в CLI-режиме | Современный TUI для Go | [github.com/charmbracelet/bubbletea](https://github.com/charmbracelet/bubbletea) |
| **Packaging Python** | PyInstaller | 6.x | Python ML-воркер → standalone EXE | Пользователь не устанавливает Python | [pyinstaller.org](https://pyinstaller.org/en/stable/) |
| **Тестирование Python** | pytest | 8.x | Unit + integration тесты ML-пайплайна | Стандарт Python-тестирования | [docs.pytest.org](https://docs.pytest.org/) |
| **Тестирование Go** | go test | stdlib | Unit тесты координатной логики, file reader, IPC | Встроен в Go | stdlib |

### 7.2 Python зависимости (requirements.txt)

```
# Core ML
torch==2.3.0+cpu
onnxruntime==1.18.0
ultralytics==8.2.0

# MobileSAM
git+https://github.com/ChaoningZhang/MobileSAM.git
timm==0.9.16

# Computer Vision
opencv-python==4.10.0.84
scikit-image==0.24.0
numpy==1.26.4
Pillow==10.3.0

# gRPC (Фаза 3+)
grpcio==1.64.0
grpcio-tools==1.64.0
protobuf==5.27.0

# PoC UI (Фаза 1 only)
gradio==4.36.0

# Quantization
onnx==1.16.0
```

### 7.3 Go зависимости (go.mod)

```go
module comicsplit

go 1.22

require (
    github.com/nwaples/rardecode       v1.1.3
    github.com/wailsapp/wails/v2       v2.8.0
    google.golang.org/grpc             v1.64.0
    github.com/charmbracelet/bubbletea v0.26.0
    github.com/charmbracelet/bubbles   v0.18.0
    github.com/google/uuid             v1.6.0
)
```

---

## 8. Структура проекта

```
comicsplit/
├── README.md
├── go.mod
├── go.sum
│
├── cmd/
│   └── comicsplit/
│       └── main.go                    # точка входа Go
│
├── internal/
│   ├── reader/
│   │   ├── cbz.go                     # CBZ/ZIP читалка
│   │   ├── cbr.go                     # CBR/RAR читалка
│   │   └── folder.go                  # папка с изображениями
│   │
│   ├── worker/
│   │   ├── pool.go                    # worker pool goroutines
│   │   └── ipc.go                     # subprocess (v1) / gRPC (v2)
│   │
│   ├── export/
│   │   ├── png.go                     # сохранение PNG
│   │   └── naming.go                  # генерация имён файлов
│   │
│   └── proto/                         # сгенерированный protobuf код
│       └── comicsplit.pb.go
│
├── frontend/                          # Wails React frontend
│   ├── package.json
│   └── src/
│       ├── App.tsx
│       ├── components/
│       │   ├── PanelEditor/
│       │   │   ├── PanelEditor.tsx    # основной canvas-редактор
│       │   │   ├── EditablePolygon.tsx
│       │   │   └── Toolbar.tsx
│       │   ├── PageList/              # боковая панель со списком страниц
│       │   └── ExportDialog/
│       ├── types/
│       │   └── panels.ts              # TypeScript типы
│       └── store/
│           └── editorStore.ts         # Zustand state
│
├── ml_worker/                         # Python ML подсистема
│   ├── requirements.txt
│   ├── main.py                        # subprocess mode entry point
│   ├── server.py                      # gRPC server (Фаза 3+)
│   ├── pipeline/
│   │   ├── cascade.py                 # главный каскад
│   │   ├── opencv_path.py             # Уровень 1
│   │   ├── yolo_detector.py           # Уровень 2
│   │   ├── sam_refiner.py             # Уровень 3
│   │   └── reading_order.py
│   ├── models/                        # .onnx файлы (в .gitignore, скачиваются отдельно)
│   │   └── download_models.py
│   └── tests/
│       ├── test_opencv_path.py
│       ├── test_yolo_detector.py
│       └── fixtures/                  # тестовые страницы (20–30 шт.)
│
├── proto/
│   └── comicsplit.proto
│
└── scripts/
    ├── build_windows.bat
    ├── quantize_models.py
    └── benchmark.py
```

---

## 9. Roadmap с задачами

### Обзор фаз

| # | Фаза | Название | Статус (май 2026) | Ключевой результат |
|---|---|---|---|---|
| 0 | — | Исследование и спецификация | ✅ Выполнено | Этот документ |
| 1 | PoC | Python ML-пайплайн | 🟡 ~80% | `pipeline.py`, `benchmark.py`, Gradio; критерий &lt;600 ms/стр. не закрыт |
| 2 | Core | Go-оркестратор + CLI | 🟡 Частично | `comicsplit.exe`, `ml_worker`, CBZ/папка; без CBR в Go |
| 3 | Integration | Полный пайплайн Go+Python | ⬜ Не начато | gRPC, единый worker pool |
| 4 | UI | Wails + редактор масок | 🟡 Частично | Gradio 3 вкладки; Konva `:8000` (Split/Upscale/Video); не Wails |
| — | Anim (отд. спека) | Оживление панелей | 🟡 MVP | `anim_pipeline`, NCNN, DepthFlow; TPSMM не в UI |

---

### ✅ Фаза 0 — Исследование и спецификация

Выполнено. Проанализированы 5 технологий, выбран стек, написана спецификация.

---

### 🟡 Фаза 1 — Python PoC (в работе / в основном готово)

**Цель:** убедиться что модели работают на реальном железе (Ryzen 5 5600H). Только Python, никакого Go, никакого UI.

**Факт (май 2026):** реализованы `yolo_test.py`, `sam_test.py`, `benchmark.py`, `process_source`, Gradio (`main.py`), pytest; OpenCV fast-path и полный edge-case QA — нет; на больших страницах `exam_imgs` время &gt; 600 ms.

**Установка окружения:**
```bash
python -m venv .venv
.venv\Scripts\activate

pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install onnxruntime ultralytics opencv-python scikit-image gradio numpy Pillow timm
pip install git+https://github.com/ChaoningZhang/MobileSAM.git
```

**Задачи:**

1. Собрать тестовый датасет — 10–15 страниц разных стилей (манга, Marvel, webtoon). Источники: DCM772, Manga109-s.
2. Написать `yolo_test.py` — загрузить модель, прогнать на тестовых страницах, замерить скорость.
3. Найти comic-specific fine-tuned YOLO модель на HuggingFace. Если нет — тестировать стандартную и оценить качество.
4. Написать `sam_test.py` — взять bbox от YOLO → MobileSAM → pixel mask.
5. Сделать Gradio демо — загрузить страницу, увидеть наложенные полигоны.
6. Написать `benchmark.py` — замер времени каждого этапа, вывести CSV.
7. Реализовать `reading_order.py` — тест на манге (RTL) и западном комиксе (LTR).
8. Написать `crop.py` — вырезать панели по polygon masks в PNG с прозрачностью.
9. Тест edge cases: splash page, overlapping panels, borderless panels.

**Критерий перехода:** YOLO обнаруживает > 85% панелей визуально, скорость < 600ms/страница, вырезанные PNG выглядят корректно.

---

### 📋 Фаза 2 — Go-оркестратор

**Цель:** CLI-программа на Go, читает CBZ/CBR, вызывает Python PoC для каждой страницы, сохраняет результаты.

**Задачи:**

1. `go mod init comicsplit`, структура директорий согласно разделу 8.
2. `internal/reader/cbz.go` — открыть ZIP, вернуть `[]PageData` с bytes и метаданными.
3. `internal/reader/cbr.go` — то же через `rardecode`.
4. `internal/reader/folder.go` — читать PNG/JPG с лексикографической сортировкой.
5. `internal/worker/ipc.go` — subprocess IPC. Go запускает `python ml_worker/main.py`, stdin/stdout JSON.

   ```json
   // stdin → Python
   {"image": "<base64>", "format": "png", "confidence": 0.5}

   // stdout ← Python  
   {"panels": [{"id": 0, "polygon": [[x,y],...], "confidence": 0.87, "order": 0}], "time_ms": 342}
   ```

6. `internal/worker/pool.go` — N goroutines, каждый со своим Python subprocess.
7. `internal/export/png.go` — принять bytes панели, сохранить файл.
8. `internal/export/naming.go` — `{global:03d}_p{page:03d}_panel_{n:02d}.png`.
9. CLI: `comicsplit.exe --input SpiderMan.cbz --output ./panels --workers 4 --confidence 0.5`
10. Progress bar через bubbletea.

**Критерий перехода:** CBZ 50 страниц обрабатывается без ошибок, worker pool стабилен, PNG корректны.

---

### 📋 Фаза 3 — Интеграция ML + Go

**Цель:** gRPC вместо subprocess, INT8 quantization, обработка всех edge cases, benchmark.

**Задачи:**

1. `proto/comicsplit.proto` — AnalyzeRequest / Panel / AnalyzeResponse.
2. Кодогенерация: `protoc --go_out=. --python_out=. proto/comicsplit.proto`.
3. `ml_worker/server.py` — gRPC сервер на `localhost:50051`.
4. `internal/worker/ipc.go` — обновить на gRPC клиент.
5. `scripts/quantize_models.py` — INT8 YOLO + MobileSAM.
6. Fallback логика в `pipeline/cascade.py` — логировать какой уровень каскада использован.
7. Edge cases: splash page (площадь > 85% → одна панель), blank page (skip), overlap resolution.
8. Benchmark на 50-страничном датасете: страниц/сек, RAM usage, распределение по уровням каскада.
9. Проверить точность coordinate scaling между 640×640 (YOLO input) и оригинальным разрешением.

**Критерий перехода:** CBZ 50 страниц → PNG за < 5 минут, RAM < 10 GB при 4 воркерах, визуальное качество 90%+.

---

### 📋 Фаза 4 — Wails UI + Редактор масок

**Цель:** полноценная desktop-утилита с интерактивным редактором.

**Задачи:**

1. `wails init -n comicsplit -t react-ts`.
2. Go → Frontend bindings: `OpenFile()`, `StartAnalysis()`, `GetPagePanels()`, `UpdatePanels()`, `ExportPanels()`.
3. Drag-and-drop зона для CBZ/CBR/папки.
4. `PageList` компонент — боковая панель, статус каждой страницы (не проверена / ок / ошибка).
5. `PanelEditor` с Konva.js — реализовать все операции из раздела 6.3.
6. `Toolbar` — Select, Add Panel (draw mode), Delete, Undo, Redo.
7. Sidebar порядка панелей — drag-and-drop для изменения reading_order.
8. Progress overlay во время анализа.
9. `ExportDialog` — папка, формат (PNG/JPEG), качество, naming pattern.
10. Settings — confidence threshold, SAM on/off, workers count, RTL toggle.
11. Keyboard shortcuts: `→`/`←` страницы, `Del` панель, `Ctrl+Z`/`Y` undo/redo, `Ctrl+Enter` принять страницу.
12. Build script `scripts/build_windows.bat`:
    ```bat
    python scripts/quantize_models.py
    pyinstaller --onefile --name ml_worker ml_worker/server.py
    wails build -platform windows/amd64
    copy dist\ml_worker.exe build\bin\
    ```
13. Тестирование на 10+ реальных комиксах разных стилей.
14. `README.md` с инструкцией по установке и запуску.

**Критерий релиза:** EXE собирается на чистой Windows, drag-and-drop работает, редактор масок корректно пересчитывает координаты, экспорт 200-страничного комикса завершается без ошибок.

---

## 10. Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|---|---|---|---|
| YOLOv11n не хватает качества без fine-tune | Средняя | Высокое | Искать comic fine-tuned модель на HuggingFace. Альтернатива — дообучить на DCM772 / Manga109 или использовать Magiv3 с ONNX экспортом |
| MobileSAM слишком медленный на CPU | Низкая | Среднее | Использовать только для явных edge cases. Для 90% страниц YOLO polygon достаточно. Fallback — FastSAM |
| GoCV (CGO) сложен в сборке на Windows | Средняя | Низкое | В Фаза 2–3: вырезать через Python OpenCV. GoCV — опциональная оптимизация Фазы 4 |
| 16 GB RAM переполняется при 4 воркерах | Низкая | Высокое | INT8 quantization + автолимит воркеров: `maxWorkers = min(4, freeRAM_GB / 3)` |
| Konva.js drag performance на больших изображениях | Средняя | Среднее | Работать с preview max 1200px, хранить координаты в оригинальном масштабе |
| CBR с RAR5 форматом | Низкая | Низкое | `rardecode` поддерживает RAR5. Fallback: вызов системного `unrar.exe` |
| Reading order некорректен для нестандартных layouts | Средняя | Среднее | Дать пользователю drag-and-drop порядка. Алгоритм best-effort, ручная коррекция всегда доступна |

---

## 11. Глоссарий

| Термин | Определение |
|---|---|
| **Панель** | Отдельный кадр в комиксе, ограниченный рамкой |
| **Сплитирование** | Разбиение страницы комикса на отдельные панели |
| **Маска** | Бинарное изображение: белые пиксели = область панели, чёрные = фон |
| **Полигон** | Набор координат вершин, описывающих форму панели |
| **Bbox** | Bounding box — ограничивающий прямоугольник `[x1, y1, x2, y2]` |
| **Instance Segmentation** | ML-задача: точная маска для каждого экземпляра объекта (не просто bbox) |
| **ONNX** | Open Neural Network Exchange — формат ML-моделей, независимый от фреймворка |
| **Inference** | Запуск обученной ML-модели на новых данных |
| **Confidence** | Уверенность модели в предсказании (0.0–1.0) |
| **NMS** | Non-Maximum Suppression — удаление дублирующихся детекций YOLO |
| **Reading Order** | Правильный порядок чтения панелей (LTR — западные, RTL — манга) |
| **Splash Page** | Страница с одной панелью на весь лист |
| **CBZ / CBR** | Comic Book Archive: CBZ = ZIP, CBR = RAR с изображениями |
| **Worker Pool** | Пул параллельных горутин для одновременной обработки страниц |
| **gRPC** | Google Remote Procedure Call — бинарный протокол межпроцессного взаимодействия |
| **INT8 Quantization** | Снижение точности весов модели с float32 до int8 для ускорения CPU inference |
| **Wails** | Go-фреймворк для desktop-приложений с web-фронтендом |
| **Konva.js** | JavaScript Canvas библиотека для интерактивной 2D графики |
| **LTR / RTL** | Left-To-Right / Right-To-Left — направление чтения |

---

*ComicSplit Specification v2.0 · 2026 · Готово к реализации в Claude Code*
