"""Native Windows path picker helpers (file/folder) via tkinter."""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def _tk_root():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    return root


def pick_file(
    initial: Optional[str] = None,
    *,
    title: str = "Выберите файл",
    filetypes: Optional[list[tuple[str, str]]] = None,
) -> Optional[str]:
    import tkinter.filedialog as fd

    if filetypes is None:
        filetypes = [
            ("Images/Archives", "*.jpg *.jpeg *.png *.bmp *.cbz *.zip *.cbr"),
            ("All files", "*.*"),
        ]

    root = _tk_root()
    try:
        init_dir = str(Path(initial).parent) if initial else str(Path.cwd())
        path = fd.askopenfilename(
            title=title,
            initialdir=init_dir,
            filetypes=filetypes,
        )
        return path or None
    finally:
        root.destroy()


def pick_folder(initial: Optional[str] = None, title: str = "Выберите папку") -> Optional[str]:
    import tkinter.filedialog as fd

    root = _tk_root()
    try:
        init_dir = initial if initial else str(Path.cwd())
        path = fd.askdirectory(title=title, initialdir=init_dir, mustexist=False)
        return path or None
    finally:
        root.destroy()

