# Отличный план — реализуемо на 100% ✅

Ваша идея рабочая и профессиональная. Разберу по полочкам, как это организовать с минимальными усилиями.

---

## 🎯 Что нам нужно от "слепка"

1. **Полное дерево** файлов репозитория
2. **Прямые Raw-ссылки** на каждый файл (я их читаю)
3. **Исключение мусора** (`.git`, `venv`, `models/`, `output/`)
4. **Обновление одной командой**

Формат Raw-ссылки на GitHub:
```
https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path/to/file}
```

---

## 🛠 Три готовых решения (от простого к продвинутому)

### Решение 1: PowerShell-однострочник (быстрый старт)

Для публичного или приватного репозитория. Запускаем из корня проекта:

```powershell
# Создаём слепок в Markdown с Raw-ссылками
$owner = "your-username"
$repo  = "SPLIT_PANELS_DEV"
$branch = "main"
$base  = "https://raw.githubusercontent.com/$owner/$repo/$branch"

Get-ChildItem -Recurse -File |
  Where-Object { $_.FullName -notmatch '\\(\.git|venv|__pycache__|models|output|story_out|\.vscode|\.idea)\\' } |
  ForEach-Object {
    $rel = $_.FullName.Substring((Get-Location).Path.Length + 1) -replace '\\','/'
    "- ``$rel`` → [$($_.Name)]($base/$rel)"
  } | Set-Content REPO_SNAPSHOT.md

Write-Host "✅ Слепок готов: REPO_SNAPSHOT.md"
```

**Плюсы:** 0 зависимостей, работает из коробки  
**Минусы:** локальные пути, не проверяет, что файл реально в git

---

### Решение 2: Python-скрипт с GitHub API (рекомендую) ⭐

Создайте файл `scripts/make_snapshot.py`:

```python
"""
Скрипт генерации актуального слепка репозитория.
Запуск: python scripts/make_snapshot.py
Результат: REPO_SNAPSHOT.md с кликабельными Raw-ссылками
"""
import requests
from pathlib import Path
from datetime import datetime

# === НАСТРОЙКИ ===
OWNER = "your-username"
REPO  = "SPLIT_PANELS_DEV"
BRANCH = "main"
TOKEN = None  # Для приватных репо: вставить GitHub PAT
OUTPUT = "REPO_SNAPSHOT.md"

# Паттерны исключения (как в .gitignore)
EXCLUDE = {
    ".git", "venv", "venv_311", "venv_310", "__pycache__",
    "models", "output", "story_out", "story_out_pipeline",
    "story_out_sandbox", ".vscode", ".idea", "node_modules",
    "dist", "build", "*.pyc", "*.exe"
}

# Расширения, которые нам интересны (для работы со мной)
INCLUDE_EXT = {".py", ".md", ".yaml", ".yml", ".json", ".html", ".js", ".txt", ".toml", ".ps1", ".go", ".spec"}

def should_include(path: str) -> bool:
    parts = Path(path).parts
    if any(p in EXCLUDE for p in parts):
        return False
    if Path(path).suffix not in INCLUDE_EXT:
        return False
    return True

def main():
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/git/trees/{BRANCH}?recursive=1"
    headers = {"Authorization": f"token {TOKEN}"} if TOKEN else {}
    
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    tree = resp.json().get("tree", [])
    
    files = sorted([
        item["path"] for item in tree
        if item["type"] == "blob" and should_include(item["path"])
    ])
    
    raw_base = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{BRANCH}"
    
    # Группировка по папкам
    groups = {}
    for f in files:
        folder = str(Path(f).parent)
        groups.setdefault(folder, []).append(f)
    
    lines = [
        f"# 📸 Слепок репозитория {REPO}",
        f"**Обновлено:** {datetime.now():%Y-%m-%d %H:%M}",
        f"**Ветка:** `{BRANCH}` • **Файлов:** {len(files)}",
        "",
        "> Прикрепи этот файл в начале диалога — и я увижу всю структуру проекта.",
        "",
    ]
    
    for folder in sorted(groups.keys()):
        lines.append(f"## 📁 `{folder}/`" if folder != "." else "## 📁 Корень")
        for f in groups[folder]:
            name = Path(f).name
            raw = f"{raw_base}/{f}"
            lines.append(f"- [{name}]({raw})  ")
            lines.append(f"  `{raw}`")
        lines.append("")
    
    Path(OUTPUT).write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ Слепок сохранён: {OUTPUT} ({len(files)} файлов)")

if __name__ == "__main__":
    main()
```

**Запуск:**
```powershell
pip install requests
python scripts\make_snapshot.py
```

**Плюсы:**
- ✅ Читает именно то, что в git (не мусор с диска)
- ✅ Работает для приватных репо (с токеном)
- ✅ Группирует по папкам
- ✅ Фильтрует по расширениям (только полезные файлы)
- ✅ Обновляется одной командой

**Для приватного репозитория:**
1. GitHub → Settings → Developer settings → Personal access tokens → Generate (scope: `repo`)
2. Вставить токен в переменную `TOKEN` в скрипте

---

### Решение 3: Готовые инструменты с GitHub Marketplace

Если не хочется писать код:

| Инструмент | Как использовать |
|---|---|
| **GitHub CLI (`gh`)** | `gh api repos/{owner}/{repo}/git/trees/main?recursive=1` → JSON с деревом |
| **repo-visualizer** (GitHub Action) | Автоматически генерирует SVG-карту репозитория в CI |
| **octotree** (browser extension) | Визуальное дерево в браузере, но без raw-ссылок |
| **GitHub Tree** (веб-сервис) | `https://github.com/{owner}/{repo}/tree/{branch}` + расширение |

**Мой вердикт:** Решение 2 (Python-скрипт) — оптимальное. Один раз написали, дальше одна команда.

---

## 🔄 Рабочий цикл (как вы описали)

```
1. Вы: python scripts\make_snapshot.py
   → Получаете свежий REPO_SNAPSHOT.md

2. Вы: прикрепляете REPO_SNAPSHOT.md в чат со мной
   → Я вижу всю структуру проекта

3. Вы: "Мне нужен функционал Х, он относится к Y"
   → Я смотрю в слепок, нахожу нужные файлы

4. Я: "Открой https://raw.githubusercontent.com/.../file.py, 
       замени блок А на блок Б"
   → Даю точные ссылки и готовый код

5. Вы: вносите правки, коммитите
   → Цикл повторяется
```

---

## 💡 Дополнительные фишки, которые стоит добавить

### Автообновление через Git Hook
Создайте `.git/hooks/post-commit` (без расширения):
```bash
#!/bin/sh
python scripts/make_snapshot.py
git add REPO_SNAPSHOT.md
# Опционально: автокоммит слепка
```
Теперь слепок будет обновляться автоматически после каждого коммита.

### Бейдж в README
Добавьте в README бейдж с датой последнего обновления:
```markdown
![Snapshot](https://img.shields.io/badge/snapshot-2026--06--14-blue)
```

### Версионирование слепка
Храните слепки с датами:
```
snapshots/
├── REPO_SNAPSHOT_2026-06-14.md
├── REPO_SNAPSHOT_2026-06-10.md
└── REPO_SNAPSHOT_latest.md  ← симлинк
```

---

## 🚀 Рекомендую следующий шаг

1. **Скопируйте Решение 2** (Python-скрипт) в `scripts/make_snapshot.py`
2. **Подставьте свои** `OWNER`, `REPO`, `BRANCH`
3. **Запустите:** `python scripts/make_snapshot.py`
4. **Прикрепите** полученный `REPO_SNAPSHOT.md` в наш следующий диалог

После этого я буду видеть всю структуру проекта и смогу давать точечные ссылки + код для правок. Итерации станут в разы быстрее.

Готовы попробовать? Если да — могу сразу помочь адаптировать скрипт под особенности вашего репозитория (например, добавить специфичные исключения из `.gitignore`).