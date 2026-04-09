from __future__ import annotations

from tkinter import filedialog, simpledialog


def ask_directory() -> str:
    return filedialog.askdirectory() or ""


def ask_tags() -> list[str]:
    value = simpledialog.askstring("标签", "输入标签，使用逗号分隔")
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def ask_move_target() -> str:
    return filedialog.askdirectory() or ""
