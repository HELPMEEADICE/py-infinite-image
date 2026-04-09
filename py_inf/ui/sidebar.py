from __future__ import annotations

import customtkinter as ctk

SIDEBAR_BG = "#252525"
ACCENT = "#3f628b"


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_filter_change, on_folder_change, **kwargs):
        super().__init__(master, fg_color=SIDEBAR_BG, corner_radius=12, **kwargs)
        self.on_filter_change = on_filter_change
        self.on_folder_change = on_folder_change
        self.grid_rowconfigure(6, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.kind_var = ctk.StringVar(value="all")
        ctk.CTkLabel(self, text="类型").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        self.kind_menu = ctk.CTkOptionMenu(self, values=["all", "image", "video"], variable=self.kind_var, command=lambda _v: on_filter_change(), button_color=ACCENT, button_hover_color="#567ca8")
        self.kind_menu.grid(row=1, column=0, sticky="ew", padx=10)

        self.favorite_var = ctk.BooleanVar(value=False)
        self.favorite_check = ctk.CTkCheckBox(self, text="仅收藏", variable=self.favorite_var, command=on_filter_change, hover_color=ACCENT)
        self.favorite_check.grid(row=2, column=0, sticky="w", padx=10, pady=10)

        ctk.CTkLabel(self, text="当前目录").grid(row=3, column=0, sticky="w", padx=10, pady=(8, 4))
        self.folder_var = ctk.StringVar(value="")
        self.folder_menu = ctk.CTkOptionMenu(self, values=[""], variable=self.folder_var, command=lambda _v: on_folder_change(), button_color=ACCENT, button_hover_color="#567ca8")
        self.folder_menu.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 10))

    def set_folders(self, folders: list[str], current: str | None = None) -> None:
        values = folders or [""]
        self.folder_menu.configure(values=values)
        self.folder_var.set(current if current in values else values[0])
