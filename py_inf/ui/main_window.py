from __future__ import annotations

from pathlib import Path
import tkinter.messagebox as messagebox

import customtkinter as ctk

from py_inf.core.extractor import extract_metadata
from py_inf.core.fileops import FileOps
from py_inf.data.db import Database
from py_inf.data.repo import MediaRepository
from py_inf.domain.favorites import FavoriteService
from py_inf.domain.search import SearchFilters, SearchService
from py_inf.domain.tags import TagService
from py_inf.services.cache import ImageCache
from py_inf.services.jobs import JobService
from py_inf.services.settings import SettingsService
from py_inf.core.thumb import ThumbnailService
from py_inf.ui.details import DetailsPanel
from py_inf.ui.dialogs import ask_directory, ask_move_target, ask_tags
from py_inf.ui.grid import MediaGrid
from py_inf.ui.sidebar import Sidebar
from py_inf.ui.toolbar import Toolbar


class MainWindow(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("无边图像浏览 MVP")
        self.geometry("1440x900")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.settings_service = SettingsService()
        self.db = Database()
        self.repo = MediaRepository(self.db)
        self.search_service = SearchService(self.repo)
        self.tag_service = TagService(self.repo)
        self.favorite_service = FavoriteService(self.repo)
        self.thumb_service = ThumbnailService()
        self.jobs = JobService()
        self.file_ops = FileOps()
        self.image_cache = ImageCache(limit=512)
        self.current_items: list[dict] = []
        self.selected_path: str | None = None
        self.current_folder: str | None = None
        self.current_offset = 0
        self.has_more = False

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)

        self.toolbar = Toolbar(self, self.add_folder, self.refresh_media, self.refresh_media)
        self.toolbar.grid(row=0, column=0, columnspan=3, sticky="ew")

        self.sidebar = Sidebar(self, self.refresh_media, self.change_folder, width=240)
        self.sidebar.grid(row=1, column=0, sticky="nsew")

        self.grid_view = MediaGrid(self, self.image_cache, self.thumb_service, self.jobs, self.select_media, self.load_more)
        self.grid_view.grid(row=1, column=1, sticky="nsew", padx=(8, 8), pady=(8, 8))

        self.details = DetailsPanel(self, self.image_cache, self.thumb_service, width=320)
        self.details.grid(row=1, column=2, sticky="nsew", padx=(0, 8), pady=(8, 8))

        self.status_var = ctk.StringVar(value="准备就绪")
        self.status_bar = ctk.CTkLabel(self, textvariable=self.status_var, anchor="w")
        self.status_bar.grid(row=2, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 8))

        self.action_bar = ctk.CTkFrame(self)
        self.action_bar.grid(row=3, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 8))
        self.favorite_button = ctk.CTkButton(self.action_bar, text="收藏切换", command=self.toggle_favorite)
        self.favorite_button.pack(side="left", padx=6, pady=6)
        self.tag_button = ctk.CTkButton(self.action_bar, text="添加标签", command=self.add_tags)
        self.tag_button.pack(side="left", padx=6, pady=6)
        self.move_button = ctk.CTkButton(self.action_bar, text="移动文件", command=self.move_selected)
        self.move_button.pack(side="left", padx=6, pady=6)
        self.reveal_button = ctk.CTkButton(self.action_bar, text="打开所在目录", command=self.reveal_selected)
        self.reveal_button.pack(side="left", padx=6, pady=6)
        self.copy_prompt_button = ctk.CTkButton(self.action_bar, text="复制 Prompt", command=self.copy_prompt)
        self.copy_prompt_button.pack(side="left", padx=6, pady=6)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh_sidebar()
        self.refresh_media()

    def add_folder(self) -> None:
        folder = ask_directory()
        if not folder:
            return
        if self.settings_service.add_root(folder):
            self.status_var.set(f"已添加目录: {folder}")
        if not self.current_folder:
            self.current_folder = folder
        self.refresh_sidebar()
        self.refresh_media(reset=True)

    def change_folder(self) -> None:
        self.current_folder = self.sidebar.folder_var.get() or None
        self.refresh_media(reset=True)

    def refresh_sidebar(self) -> None:
        roots = self.settings_service.settings.scan_roots
        if roots and self.current_folder not in roots:
            self.current_folder = roots[0]
        self.sidebar.set_folders(roots, self.current_folder)

    def refresh_media(self, reset: bool = True) -> None:
        if reset:
            self.current_offset = 0
        if not self.current_folder:
            self.current_items = []
            self.has_more = False
            self.grid_view.render_items([], False)
            self.status_var.set("请先添加并选择目录")
            return
        page_size = self.settings_service.settings.page_size
        filters = SearchFilters(
            query=self.toolbar.search_var.get().strip(),
            folder=self.current_folder,
            kind=None if self.sidebar.kind_var.get() == "all" else self.sidebar.kind_var.get(),
            favorite_only=self.sidebar.favorite_var.get(),
            limit=page_size + 1,
            offset=self.current_offset,
        )
        items = self.search_service.search(filters)
        self.has_more = len(items) > page_size
        visible_items = items[:page_size]
        for item in visible_items:
            self.repo.ensure_media_entry(Path(item["path"]))
        if reset:
            self.current_items = visible_items
        else:
            self.current_items.extend(visible_items)
        self.grid_view.render_items(self.current_items, self.has_more, reset=reset)
        self.status_var.set(f"当前目录已加载 {len(self.current_items)} 个项目（递归子目录）")
        if self.selected_path:
            self.select_media(self.selected_path)

    def load_more(self) -> None:
        if not self.has_more:
            return
        self.current_offset += self.settings_service.settings.page_size
        self.refresh_media(reset=False)

    def select_media(self, path: str) -> None:
        self.selected_path = path
        item = next((entry for entry in self.current_items if entry["path"] == path), None)
        if not item:
            return
        metadata = extract_metadata(Path(path))
        state = self.repo.get_state_by_path(path) or {}
        self.repo.ensure_media_entry(Path(path))
        detail = {
            "path": path,
            "filename": item.get("filename"),
            "kind": item.get("kind"),
            "favorite": state.get("favorite", 0),
            "tags": state.get("tags", ""),
            "width": metadata.width,
            "height": metadata.height,
            "duration": metadata.duration,
            "prompt": metadata.prompt,
            "negative_prompt": metadata.negative_prompt,
            "model": metadata.model,
            "sampler": metadata.sampler,
            "seed": metadata.seed,
            "steps": metadata.steps,
            "cfg": metadata.cfg,
        }
        self.details.show_detail(detail)

    def _selected_detail(self):
        if not self.selected_path:
            messagebox.showinfo("提示", "请先选择一个项目")
            return None
        item = next((entry for entry in self.current_items if entry["path"] == self.selected_path), None)
        if not item:
            return None
        metadata = extract_metadata(Path(self.selected_path))
        state = self.repo.get_state_by_path(self.selected_path) or {}
        return {
            "path": self.selected_path,
            "filename": item.get("filename"),
            "kind": item.get("kind"),
            "favorite": state.get("favorite", 0),
            "tags": state.get("tags", ""),
            "width": metadata.width,
            "height": metadata.height,
            "duration": metadata.duration,
            "prompt": metadata.prompt,
            "negative_prompt": metadata.negative_prompt,
            "model": metadata.model,
            "sampler": metadata.sampler,
            "seed": metadata.seed,
            "steps": metadata.steps,
            "cfg": metadata.cfg,
        }

    def toggle_favorite(self) -> None:
        detail = self._selected_detail()
        if not detail:
            return
        favorite = not bool(detail.get("favorite"))
        self.favorite_service.set_favorite_by_path(detail["path"], favorite)
        self.refresh_media(reset=True)
        self.select_media(detail["path"])

    def add_tags(self) -> None:
        detail = self._selected_detail()
        if not detail:
            return
        tags = ask_tags()
        if not tags:
            return
        self.tag_service.add_tags_by_path(detail["path"], tags)
        self.select_media(detail["path"])

    def move_selected(self) -> None:
        detail = self._selected_detail()
        if not detail:
            return
        target_dir = ask_move_target()
        if not target_dir:
            return
        new_path = self.file_ops.move(detail["path"], target_dir)
        self.repo.move_media_by_path(detail["path"], new_path)
        self.selected_path = new_path
        self.refresh_sidebar()
        self.refresh_media(reset=True)

    def reveal_selected(self) -> None:
        detail = self._selected_detail()
        if not detail:
            return
        self.file_ops.reveal(detail["path"])

    def copy_prompt(self) -> None:
        detail = self._selected_detail()
        if not detail:
            return
        self.clipboard_clear()
        self.clipboard_append(detail.get("prompt") or "")
        self.status_var.set("Prompt 已复制")

    def on_close(self) -> None:
        self.jobs.shutdown()
        self.db.close()
        self.destroy()
