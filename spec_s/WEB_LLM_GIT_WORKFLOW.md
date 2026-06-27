# Web-LLM + Git: workflow разработки Comix_Split

**Обновлено:** июнь 2026  
**Репозиторий:** [GitHub arnik807/Comix_Split](https://github.com/arnik807/Comix_Split) · [Sourcecraft sparky/comixsplitter](https://git.sourcecraft.dev/sparky/comixsplitter)

Документ для работы с **web-LLM без доступа к локальным файлам**: LLM «видит» код через Git, пользователь на ПК применяет правки и пушит на сервер.

---

## 1. Идея процесса

```
┌─────────────┐     REPO_MAP.md + raw URLs      ┌──────────────┐
│  Web-LLM    │ ◄────────────────────────────── │   GitHub /   │
│  (браузер)  │     читает файлы по ссылкам     │  Sourcecraft │
└──────┬──────┘                                 └──────▲───────┘
       │ патчи / diff текстом                          │ push
       ▼                                               │
┌─────────────┐     generate_repo_map.py        ┌──────┴───────┐
│ Пользователь│ ──► правки локально ──► commit │  Локальный   │
│  (Cursor)   │                                 │     git      │
└─────────────┘                                 └──────────────┘
```

1. **LLM** получает `REPO_MAP.md` (дерево + ссылки на raw-файлы) и при необходимости — handoff: [LLM_HANDOFF_CONTEXT.md](LLM_HANDOFF_CONTEXT.md).
2. LLM изучает архитектуру, по задаче читает конкретные файлы по **GitHub Raw** URL.
3. LLM выдаёт **готовые правки** (diff, фрагменты файлов, инструкции).
4. **Пользователь** вносит изменения локально (IDE / Cursor).
5. Перед коммитом: `python scripts/generate_repo_map.py` → обновить `REPO_MAP.md`.
6. `git commit` → **push на оба remote** (GitHub + Sourcecraft).

LLM выступает как «удалённый разработчик»; финальное одобрение и push — у вас на машине.

---

## 2. Два сервера: remotes в этом проекте

| Remote | URL | Назначение |
|--------|-----|------------|
| **`github`** | `https://github.com/arnik807/Comix_Split.git` | GitHub (основной для Raw-ссылок LLM) |
| **`origin`** | `https://git.sourcecraft.dev/sparky/comixsplitter.git` | Sourcecraft (зеркало, CI/бэкап) |
| `Sparky` | = GitHub | дубликат |
| `comixsplitter` | = Sourcecraft (SSH-форма URL) | дубликат |

**Проверка:**

```powershell
git remote -v
git branch -vv
```

Оба сервера должны указывать на **одну ветку `main`** с одинаковой историей после каждого релиза правок.

### GitHub vs Sourcecraft — отличия

| | GitHub | Sourcecraft |
|---|--------|-------------|
| **Raw-файлы для LLM** | `https://raw.githubusercontent.com/arnik807/Comix_Split/main/<path>` | `https://raw.sourcecraft.tech/raw/sparky/comixsplitter/<full_commit_sha>/<path>` |
| **Стабильность ссылки** | Ветка `main` — всегда последний push | **Полный** commit hash (40 символов); короткий (`bf9b6e7`) → Not Found |
| **Клонирование HTTPS** | `https://github.com/arnik807/Comix_Split.git` | `https://git@git.sourcecraft.dev/sparky/comixsplitter.git` |
| **UI** | github.com | git.sourcecraft.dev |
| **Для web-LLM** | **Предпочтительно** (проще, ветка в URL) | Запасной канал, тот же код после push |

> **Практика:** LLM кормите ссылками **GitHub Raw** из `REPO_MAP.md`. Sourcecraft — зеркало для git push и просмотра в их UI.

---

## 3. REPO_MAP.md — карта проекта

Файл в **корне репозитория**. Генерируется скриптом, **коммитится в git**.

```powershell
cd D:\DEVELOP\COMICS\SPLIT_PANELS_DEV
python scripts/generate_repo_map.py
# или: python generate_map.py
```

Что делает скрипт:

- обходит проект (исключая `models/`, `venv_*`, `output/`, `exam_img*` и т.д.);
- группирует файлы по папкам;
- для каждого `.py`, `.js`, `.html`, `.md`, `.yaml`, … пишет пару ссылок GitHub + Sourcecraft.

**Когда перегенерировать:** перед коммитом, если добавили/удалили/переименовали файлы, или после merge.

**Что отправить LLM в начале сессии:**

1. `REPO_MAP.md` (вставить текст или дать raw-ссылку на GitHub).
2. Кратко: [LLM_HANDOFF_CONTEXT.md](LLM_HANDOFF_CONTEXT.md) или [ARCHITECTURE.md](ARCHITECTURE.md).
3. Формулировку задачи.

---

## 4. Канонические git-команды (PowerShell)

Все команды — из **корня репозитория**.

### Статус и история

```powershell
git status
git diff
git diff --staged
git log --oneline -10
git log -1 --format=full
```

### Получить изменения с сервера

```powershell
git fetch origin
git fetch github
git pull origin main
# или одним remote, если main tracking origin:
git pull
```

### Локальная работа — один файл или много

**Git не коммитит «по одному файлу».** Один `git commit` = один снимок всего, что вы положили в **staging** (`git add`).

```powershell
# Один файл
git add frontend/story_2a.js

# Несколько файлов явно
git add frontend/story_2a.js api/story_stage_2a.py spec_s/ARCHITECTURE.md

# Вся папка (десятки файлов)
git add frontend/
git add spec_s/

# Все изменённые отслеживаемые файлы в проекте (осторожно: проверьте git status!)
git add .

# Все изменения в уже отслеживаемых файлах, без новых untracked
git add -u
```

После `git add` смотрите **`git status`**: в блоке «Changes to be committed» — всё, что попадёт в **следующий один** коммит. Это может быть 1 файл или 200.

```powershell
git status
git commit -m "feat: ExText + правки API и доков"
```

**Не путать:** два коммита в workflow ниже — это не «коммит на файл», а **два логических шага** (код → обновление `REPO_MAP` после push). Обычную задачу от LLM (много `.py`, `.js`, `.md`) делайте **одним** коммитом через `git add .` или `git add frontend/ api/ …`.

### Коммит

```powershell
git commit -m "feat: краткий заголовок" -m "Подробное описание изменений."
```

### Push на оба сервера (стандарт после коммита)

```powershell
git push github main
git push origin main
```

Одной строкой:

```powershell
git push github main; git push origin main
```

### Проверка синхронизации

```powershell
git fetch github; git fetch origin
git log github/main -1 --oneline
git log origin/main -1 --oneline
# хеши должны совпадать
```

### Ветки (если понадобится feature-branch)

```powershell
git checkout -b feature/my-task
git push -u github feature/my-task
git push -u origin feature/my-task
```

Слияние в `main` — через PR на GitHub или локально `git checkout main; git merge feature/my-task`.

### Отмена локальных правок (осторожно)

```powershell
git restore .                    # все unstaged → как в последнем commit
git reset --hard HEAD            # жёсткий сброс к последнему commit
git reset --hard origin/main     # как на Sourcecraft (потеря локальных коммитов!)
```

---

## 5. Типовой цикл «задача от LLM»

### 5.1. Обычная правка (много файлов → один коммит)

```powershell
cd D:\DEVELOP\COMICS\SPLIT_PANELS_DEV
git pull origin main

# … правки в Cursor / IDE …

python scripts/generate_repo_map.py

git add .
git status
git commit -m "fix: описание задачи от LLM"
git push github main; git push origin main
```

Перед `git add .` убедитесь, что в списке **нет** `.env`, `exam_imgs/`, `models/` — они не должны попасть в коммит.

### 5.2. После изменения только `generate_repo_map.py` / REPO_MAP (два коммита)

Sourcecraft Raw привязан к **hash коммита**. Поэтому иногда нужно:

1. Закоммитить **код/скрипт/доки** (без финального REPO_MAP или с промежуточным).
2. **Push** — hash появился на сервере.
3. Перегенерировать `REPO_MAP.md` с актуальным hash.
4. Второй коммит только для карты + push.

**Выполнять сверху вниз, по одной строке** (в PowerShell многострочная вставка с `>>` может выполниться в обратном порядке):

```powershell
cd D:\DEVELOP\COMICS\SPLIT_PANELS_DEV
git add scripts/generate_repo_map.py spec_s/WEB_LLM_GIT_WORKFLOW.md
git status
git commit -m "fix: описание изменения"
git push github main; git push origin main
python scripts/generate_repo_map.py
git add REPO_MAP.md
git status
git commit -m "docs: refresh REPO_MAP Sourcecraft commit hash"
git push github main; git push origin main
```

> **Зачем два коммита:** в `REPO_MAP` в Sourcecraft-URL подставляется hash **текущего** `HEAD`. После первого push hash известен; второй коммит обновляет ссылки в карте. Для **GitHub Raw** это не критично (там в URL ветка `main`).

### 5.3. Старый упрощённый цикл (один коммит)

Тот же §5.1: `generate_repo_map` → `git add .` → один `commit` → dual push. Подходит для большинства задач.

---

## 6. Raw-URL — как LLM читает файл

**GitHub** (ветка `main`, после push):

```
https://raw.githubusercontent.com/arnik807/Comix_Split/main/frontend/story_2a.js
```

**Sourcecraft** (полный commit из `REPO_MAP.md`, 40 hex):

```
https://raw.sourcecraft.tech/raw/sparky/comixsplitter/6a44eae084590d42044c087fbfd76618d8e6b0ba/frontend/story_2a.js
```

Web-LLM с доступом в интернет открывает URL и получает текст файла.

---

## 7. Что не попадает в REPO_MAP

Как в `.gitignore`: `models/**`, `venv_*`, `output/`, `story_out/`, `.env`, бинарники, тестовые прогоны `exam_img/`.  
LLM не увидит локальные веса и секреты — это нормально.

---

## 8. Аутентификация

| Сервер | Push |
|--------|------|
| **GitHub** | HTTPS + PAT / Git Credential Manager / SSH |
| **Sourcecraft** | PAT или SSH ([документация Sourcecraft](https://sourcecraft.dev/portal/docs/en/sourcecraft/operations/repo-clone)) |

Если `git push` просит пароль — используйте **Personal Access Token**, не пароль аккаунта.

---

## 9. Связанные документы

| Файл | Зачем LLM / вам |
|------|-----------------|
| [REPO_MAP.md](../REPO_MAP.md) | Дерево + raw-ссылки |
| [LLM_HANDOFF_CONTEXT.md](LLM_HANDOFF_CONTEXT.md) | Контекст проекта одним файлом |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Стек и API |
| [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) | Что уже сделано |
| [webLLM+ GitHub= devWorkFlow.md](webLLM+ GitHub= devWorkFlow.md) | Черновик идеи (исторический) |

---

## 10. Чеклист перед push

- [ ] Код запускается / тесты по возможности
- [ ] Нет `.env`, `models/`, `exam_img/` в `git add`
- [ ] `python scripts/generate_repo_map.py` если менялась структура файлов
- [ ] `git push github main` **и** `git push origin main`
- [ ] Хеши `github/main` и `origin/main` совпадают
