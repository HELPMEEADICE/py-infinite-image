from __future__ import annotations

import customtkinter as ctk

TOOLBAR_BG = "#262626"
BUTTON_COLOR = "#35506f"
BUTTON_HOVER = "#4b6f99"
ENTRY_BG = "#1f1f1f"
ENTRY_BORDER = "#406386"


class Toolbar(ctk.CTkFrame):
    def __init__(self, master, on_add_folder, on_refresh, on_search, **kwargs):
        super().__init__(master, fg_color=TOOLBAR_BG, corner_radius=12, **kwargs)
        self.grid_columnconfigure(1, weight=1)
        self.add_button = ctk.CTkButton(self, text="添加目录", command=on_add_folder, width=96, fg_color=BUTTON_COLOR, hover_color=BUTTON_HOVER)
        self.add_button.grid(row=0, column=0, padx=(8, 6), pady=8)
        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(self, textvariable=self.search_var, placeholder_text="搜索当前目录文件名", fg_color=ENTRY_BG, border_color=ENTRY_BORDER)
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=8)
        self.search_entry.bind("<Return>", lambda _event: on_search())
        self.refresh_button = ctk.CTkButton(self, text="刷新目录", command=on_refresh, width=96, fg_color=BUTTON_COLOR, hover_color=BUTTON_HOVER)
        self.refresh_button.grid(row=0, column=2, padx=6, pady=8)
