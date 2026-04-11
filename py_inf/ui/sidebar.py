from __future__ import annotations

import customtkinter as ctk

SIDEBAR_BG = "#1d1b20"
ACCENT = "#4a4458"


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_filter_change, on_folder_change, **kwargs):
        super().__init__(master, fg_color=SIDEBAR_BG, corner_radius=24, **kwargs)
        self.on_filter_change = on_filter_change
        self.on_folder_change = on_folder_change
        self.resize_after_id = None
        self.last_width: int | None = None
        self.content_shift = 0.0
        self.settle_after_id = None

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.place(relx=0, rely=0, relwidth=1, relheight=1, x=0, y=0)
        self.content.grid_rowconfigure(6, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.kind_var = ctk.StringVar(value="all")
        ctk.CTkLabel(self.content, text="类型").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        self.kind_menu = ctk.CTkOptionMenu(self.content, values=["all", "image", "video"], variable=self.kind_var, command=self._on_kind_change, button_color=ACCENT, button_hover_color="#5d576b", corner_radius=16)
        self.kind_menu.grid(row=1, column=0, sticky="ew", padx=10)

        self.favorite_var = ctk.BooleanVar(value=False)
        self.favorite_check = ctk.CTkCheckBox(self.content, text="仅收藏", variable=self.favorite_var, command=self._on_favorite_change, hover_color=ACCENT)
        self.favorite_check.grid(row=2, column=0, sticky="w", padx=10, pady=10)

        ctk.CTkLabel(self.content, text="当前目录").grid(row=3, column=0, sticky="w", padx=10, pady=(8, 4))
        self.folder_var = ctk.StringVar(value="")
        self.folder_menu = ctk.CTkOptionMenu(self.content, values=[""], variable=self.folder_var, command=self._on_folder_change, button_color=ACCENT, button_hover_color="#5d576b", corner_radius=16)
        self.folder_menu.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.bind("<Configure>", self._on_resize)

    def set_folders(self, folders: list[str], current: str | None = None) -> None:
        values = folders or [""]
        self.folder_menu.configure(values=values)
        self.folder_var.set(current if current in values else values[0])

    def _on_kind_change(self, _value: str) -> None:
        flash = getattr(self.master, "_flash_option_menu", None)
        if callable(flash):
            flash(self.kind_menu)
        self.on_filter_change()

    def _on_favorite_change(self) -> None:
        flash = getattr(self.master, "_flash_checkbox", None)
        if callable(flash):
            flash(self.favorite_check)
        self.on_filter_change()

    def _on_folder_change(self, _value: str) -> None:
        flash = getattr(self.master, "_flash_option_menu", None)
        if callable(flash):
            flash(self.folder_menu)
        self.on_folder_change()

    def _on_resize(self, event) -> None:
        if event.widget is not self:
            return
        if self.last_width is None:
            self.last_width = event.width
            return
        delta = event.width - self.last_width
        self.last_width = event.width
        if abs(delta) < 6:
            return
        self.content.place_configure(x=0)
        self.content_shift = max(-8.0, min(8.0, delta * 0.1))
        if self.settle_after_id is not None:
            self.after_cancel(self.settle_after_id)
        self.settle_after_id = self.after(120, self._animate_resize_settle)

    def _animate_resize_settle(self) -> None:
        self.settle_after_id = None
        if abs(self.content_shift) < 0.5:
            self.content_shift = 0.0
            self.content.place_configure(x=0)
            self.resize_after_id = None
            return
        self.content.place_configure(x=int(round(self.content_shift)))
        self.content_shift *= 0.45
        self.resize_after_id = self.after(32, self._animate_resize_settle)
