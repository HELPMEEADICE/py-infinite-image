from __future__ import annotations

import customtkinter as ctk


class Toolbar(ctk.CTkFrame):
    def __init__(self, master, on_add_folder, on_refresh, on_search, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(1, weight=1)
        self.add_button = ctk.CTkButton(self, text="添加目录", command=on_add_folder, width=96)
        self.add_button.grid(row=0, column=0, padx=(8, 6), pady=8)
        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(self, textvariable=self.search_var, placeholder_text="搜索当前目录文件名")
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=8)
        self.search_entry.bind("<Return>", lambda _event: on_search())
        self.refresh_button = ctk.CTkButton(self, text="刷新目录", command=on_refresh, width=96)
        self.refresh_button.grid(row=0, column=2, padx=6, pady=8)
