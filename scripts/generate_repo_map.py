"""
Генерация REPO_MAP.md — дерево проекта с Raw-ссылками для web-LLM.

Запуск из корня репозитория:
    python scripts/generate_repo_map.py
    python scripts/generate_repo_map.py --output REPO_MAP.md

После правок кода: перегенерировать → git add REPO_MAP.md → commit → push (github + origin).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GITHUB_OWNER = "arnik807"
GITHUB_REPO = "Comix_Split"
GITHUB_BRANCH = "main"

SOURCECRAFT_ORG = "sparky"
SOURCECRAFT_REPO = "comixsplitter"

IGNORE_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "venv_310",
        "venv_311",
        "__pycache__",
        ".pytest_cache",
        ".idea",
        ".vscode",
        "node_modules",
        "dist",
        "build",
        "models",
        "output",
        "story_out",
        "story_out_pipeline",
        "story_out_sandbox",
        "story_test",
        "out_ui",
        "exam_img",
        "exam_imgs",
        "debug",
        "make_github_snapshot",
        "tmp_comicsplit_manga",
    }
)

IGNORE_FILES = frozenset(
    {
        "REPO_MAP.md",
        "REPO_SNAPSHOT.md",
        ".env",
        ".env.local",
    }
)

INCLUDE_SUFFIXES = frozenset(
    {
        ".py",
        ".go",
        ".md",
        ".yaml",
        ".yml",
        ".json",
        ".html",
        ".js",
        ".css",
        ".ps1",
        ".sh",
        ".toml",
        ".spec",
        ".txt",
        ".gitignore",
        ".gitattributes",
    }
)


def git_head() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip()[:12]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "main"


def git_branch() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip() or GITHUB_BRANCH
    except (subprocess.CalledProcessError, FileNotFoundError):
        return GITHUB_BRANCH


def should_include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in IGNORE_DIRS for part in rel.parts):
        return False
    if rel.name in IGNORE_FILES:
        return False
    if rel.suffix.lower() in {".pyc", ".exe", ".onnx", ".pt", ".bin", ".param", ".png", ".jpg", ".mp4", ".zip"}:
        return False
    if rel.suffix in INCLUDE_SUFFIXES:
        return True
    if rel.name in ("Dockerfile", "Makefile"):
        return True
    return False


def collect_files() -> list[str]:
    files: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        if not should_include(path):
            continue
        files.append(path.relative_to(ROOT).as_posix())
    return files


def github_raw(relpath: str, branch: str) -> str:
    return f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{branch}/{relpath}"


def sourcecraft_raw(relpath: str, commit: str) -> str:
    # https://sourcecraft.dev/portal/docs/en/sourcecraft/operations/raw-content
    return (
        f"https://raw.sourcecraft.tech/raw/{SOURCECRAFT_ORG}/{SOURCECRAFT_REPO}/{commit}/{relpath}"
    )


def group_by_folder(files: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for f in files:
        folder = str(Path(f).parent).replace("\\", "/")
        if folder == ".":
            folder = ""
        groups.setdefault(folder, []).append(f)
    return groups


def write_map(output: Path, files: list[str], branch: str, commit: str) -> None:
    groups = group_by_folder(files)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Карта репозитория Comix_Split",
        "",
        f"**Обновлено:** {now}  ",
        f"**Ветка:** `{branch}` · **Commit:** `{commit}` · **Файлов:** {len(files)}",
        "",
        "Слепок для **web-LLM** без доступа к локальному диску: прикрепите этот файл в чат.",
        "LLM читает исходники по **GitHub Raw** (актуально после `push` на `main`).",
        "",
        "Мануал: [spec_s/WEB_LLM_GIT_WORKFLOW.md](spec_s/WEB_LLM_GIT_WORKFLOW.md)",
        "",
        "---",
        "",
    ]

    folder_order = sorted(groups.keys(), key=lambda x: (x.count("/"), x))
    for folder in folder_order:
        title = "Корень" if folder == "" else folder.replace("\\", "/")
        lines.append(f"## `{title}`")
        lines.append("")
        for relpath in sorted(groups[folder]):
            gh = github_raw(relpath, branch)
            sc = sourcecraft_raw(relpath, commit)
            name = Path(relpath).name
            lines.append(f"- **{relpath}**")
            lines.append(f"  - GitHub: [{name}]({gh})")
            lines.append(f"  - Sourcecraft: [{name}]({sc})")
        lines.append("")

    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate REPO_MAP.md for web-LLM workflow")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "REPO_MAP.md",
        help="Output markdown path (default: REPO_MAP.md in repo root)",
    )
    args = parser.parse_args()

    branch = git_branch()
    commit = git_head()
    files = collect_files()
    out = args.output if args.output.is_absolute() else ROOT / args.output
    write_map(out, files, branch, commit)

    print(f"OK: {out} ({len(files)} files, branch={branch}, commit={commit})")
    print("Next: git add REPO_MAP.md && git commit && git push github main && git push origin main")
    return 0


if __name__ == "__main__":
    sys.exit(main())
