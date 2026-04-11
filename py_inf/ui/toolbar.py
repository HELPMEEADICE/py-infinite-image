from __future__ import annotations

import customtkinter as ctk

TOOLBAR_BG = "#1d1b20"
BUTTON_COLOR = "#4a4458"
BUTTON_HOVER = "#5d576b"
ENTRY_BG = "#36343b"
ENTRY_BORDER = "#938f99"


class Toolbar(ctk.CTkFrame):
    def __init__(self, master, on_add_folder, on_refresh, on_search, **kwargs):
        super().__init__(master, fg_color=TOOLBAR_BG, corner_radius=24, **kwargs)
        self.grid_columnconfigure(1, weight=1)
        self.add_button = ctk.CTkButton(self, text="添加目录", command=on_add_folder, width=96, fg_color=BUTTON_COLOR, hover_color=BUTTON_HOVER, corner_radius=20)
        self.add_button.grid(row=0, column=0, padx=(8, 6), pady=8)
        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(self, textvariable=self.search_var, placeholder_text="搜索当前目录文件名", fg_color=ENTRY_BG, border_color=ENTRY_BORDER, corner_radius=20)
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=8)
        self.search_entry.bind("<Return>", lambda _event: on_search())
        self.refresh_button = ctk.CTkButton(self, text="刷新目录", command=on_refresh, width=96, fg_color=BUTTON_COLOR, hover_color=BUTTON_HOVER, corner_radius=20)
        self.refresh_button.grid(row=0, column=2, padx=6, pady=8)
