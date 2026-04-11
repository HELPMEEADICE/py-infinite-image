from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
import tkinter as tk
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

STATUS_BASE_COLOR = "#36343b"
STATUS_FLASH_COLOR = "#4f378b"
ACTION_BAR_COLOR = "#1d1b20"
ACTION_BUTTON_COLOR = "#4a4458"
ACTION_BUTTON_HOVER = "#5d576b"
ACTION_BUTTON_PRESS = "#d0bcff"
INPUT_BORDER_COLOR = "#938f99"
INPUT_BORDER_FOCUS = "#d0bcff"
INPUT_BORDER_FLASH = "#eaddff"
OPTION_BUTTON_BASE = "#4a4458"
OPTION_BUTTON_HOVER = "#5d576b"
OPTION_BUTTON_FLASH = "#d0bcff"
CHECKBOX_HOVER = "#4a4458"
CHECKBOX_FLASH = "#d0bcff"


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{max(0, min(255, component)):02x}" for component in rgb)


def _mix_color(start: str, end: str, amount: float) -> str:
    amount = max(0.0, min(1.0, amount))
    start_rgb = _hex_to_rgb(start)
    end_rgb = _hex_to_rgb(end)
    mixed = tuple(int(start_component + (end_component - start_component) * amount) for start_component, end_component in zip(start_rgb, end_rgb))
    return _rgb_to_hex(mixed)


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
        self.image_cache = ImageCache(limit=1024)
        self.page_size = max(1, self.settings_service.settings.page_size)
        self.thumb_size = max(80, self.settings_service.settings.thumb_size)
        self.preview_size = max(120, self.settings_service.settings.preview_size)
        self.search_request_id = 0
        self.pending_search_results: Queue[tuple[int, bool, object]] = Queue()
        self.current_items: list[dict] = []
        self.selected_path: str | None = None
        self.current_folder: str | None = None
        self.current_offset = 0
        self.has_more = False
        self.status_after_id = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)

        self.toolbar = Toolbar(self, self.add_folder, self.refresh_media, self.refresh_media)
        self.toolbar.grid(row=0, column=0, columnspan=3, sticky="ew", padx=8, pady=(8, 0))

        self.sidebar = Sidebar(self, self.refresh_media, self.change_folder, width=240)
        self.sidebar.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(8, 8))

        self.grid_view = MediaGrid(
            self,
            self.image_cache,
            self.thumb_service,
            self.jobs,
            self.select_media,
            self.load_more,
            on_context=self.show_item_context,
            on_open=self.open_media,
            thumb_size=self.thumb_size,
        )
        self.grid_view.grid(row=1, column=1, sticky="nsew", padx=(8, 8), pady=(8, 8))

        self.details = DetailsPanel(self, self.image_cache, self.thumb_service, self.jobs, preview_size=self.preview_size, width=320)
        self.details.grid(row=1, column=2, sticky="nsew", padx=(0, 8), pady=(8, 8))

        self.status_var = ctk.StringVar(value="准备就绪")
        self.status_bar = ctk.CTkLabel(self, textvariable=self.status_var, anchor="w", fg_color=STATUS_BASE_COLOR, corner_radius=16)
        self.status_bar.grid(row=2, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 8))

        self.action_bar = ctk.CTkFrame(self, fg_color=ACTION_BAR_COLOR, corner_radius=24)
        self.action_bar.grid(row=3, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 8))
        self.favorite_button = ctk.CTkButton(self.action_bar, text="收藏切换", command=self.toggle_favorite, corner_radius=20)
        self.favorite_button.pack(side="left", padx=6, pady=6)
        self.tag_button = ctk.CTkButton(self.action_bar, text="添加标签", command=self.add_tags, corner_radius=20)
        self.tag_button.pack(side="left", padx=6, pady=6)
        self.move_button = ctk.CTkButton(self.action_bar, text="移动文件", command=self.move_selected, corner_radius=20)
        self.move_button.pack(side="left", padx=6, pady=6)
        self.reveal_button = ctk.CTkButton(self.action_bar, text="打开所在目录", command=self.reveal_selected, corner_radius=20)
        self.reveal_button.pack(side="left", padx=6, pady=6)
        self.copy_prompt_button = ctk.CTkButton(self.action_bar, text="复制 Prompt", command=self.copy_prompt, corner_radius=20)
        self.copy_prompt_button.pack(side="left", padx=6, pady=6)

        self._style_buttons(
            self.toolbar.add_button,
            self.toolbar.refresh_button,
            self.favorite_button,
            self.tag_button,
            self.move_button,
            self.reveal_button,
            self.copy_prompt_button,
        )
        self._style_entry(self.toolbar.search_entry)
        self._style_option_menu(self.sidebar.kind_menu)
        self._style_option_menu(self.sidebar.folder_menu)
        self._style_checkbox(self.sidebar.favorite_check)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(25, self._drain_search_results)
        self.refresh_sidebar()
        self.refresh_media()

    def add_folder(self) -> None:
        folder = ask_directory()
        if not folder:
            return
        if self.settings_service.add_root(folder):
            self.set_status(f"已添加目录: {folder}")
        if not self.current_folder:
            self.current_folder = folder
        self.refresh_sidebar()
        self.refresh_media(reset=True)

    def change_folder(self) -> None:
        self.current_folder = self.sidebar.folder_var.get() or None
        self._flash_option_menu(self.sidebar.folder_menu)
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
            self.grid_view.set_selected_path(None)
            self.set_status("请先添加并选择目录")
            return
        filters = SearchFilters(
            query=self.toolbar.search_var.get().strip(),
            folder=self.current_folder,
            kind=None if self.sidebar.kind_var.get() == "all" else self.sidebar.kind_var.get(),
            favorite_only=self.sidebar.favorite_var.get(),
            limit=self.page_size + 1,
            offset=self.current_offset,
        )
        self.search_request_id += 1
        request_id = self.search_request_id
        self.set_status("正在加载目录内容...")
        future = self.jobs.submit(self.search_service.search, filters)
        future.add_done_callback(lambda f, rid=request_id, do_reset=reset: self.pending_search_results.put((rid, do_reset, f)))

    def _drain_search_results(self) -> None:
        try:
            while True:
                request_id, reset, future = self.pending_search_results.get_nowait()
                self._apply_search_results(request_id, reset, future)
        except Empty:
            pass
        if self.winfo_exists():
            self.after(25, self._drain_search_results)

    def _apply_search_results(self, request_id: int, reset: bool, future) -> None:
        if not self.winfo_exists() or request_id != self.search_request_id:
            return
        try:
            items = future.result()
        except Exception:
            self.current_items = [] if reset else self.current_items
            self.has_more = False
            self.grid_view.render_items(self.current_items, False, reset=reset)
            self.set_status("目录加载失败")
            return
        self.has_more = len(items) > self.page_size
        visible_items = items[:self.page_size]
        for item in visible_items:
            self.repo.ensure_media_entry(Path(item["path"]))
        if reset:
            self.current_items = visible_items
        else:
            existing = {entry["path"] for entry in self.current_items}
            self.current_items.extend(item for item in visible_items if item["path"] not in existing)
        self.grid_view.render_items(self.current_items, self.has_more, reset=reset)
        self.set_status(f"当前目录已加载 {len(self.current_items)} 个项目（递归子目录）")
        if self.selected_path:
            self.select_media(self.selected_path)
        else:
            self.grid_view.set_selected_path(None)

    def load_more(self) -> None:
        if not self.has_more:
            return
        self.current_offset += self.page_size
        self.refresh_media(reset=False)

    def select_media(self, path: str) -> None:
        self.selected_path = path
        self.grid_view.set_selected_path(path)
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
        self.set_status(f"已更新标签: {Path(detail['path']).name}")

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
        self.set_status(f"已移动: {Path(new_path).name}")

    def reveal_selected(self) -> None:
        detail = self._selected_detail()
        if not detail:
            return
        self.file_ops.reveal(detail["path"])
        self.set_status(f"已定位: {Path(detail['path']).name}")

    def show_item_context(self, path: str, x_root: int, y_root: int) -> None:
        self.selected_path = path
        self.grid_view.set_selected_path(path)
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="删除", command=lambda p=path: self.delete_media(p))
        menu.add_command(label="使用默认应用打开", command=lambda p=path: self.open_media(p))
        menu.add_command(label="使用文件管理器打开", command=lambda p=path: self.reveal_media(p))
        menu.add_command(label="查看 Meta Data", command=lambda p=path: self.select_media(p))
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()

    def delete_media(self, path: str) -> None:
        name = Path(path).name
        if not messagebox.askyesno("删除文件", f"确认将 {name} 移入回收站？"):
            return
        self.file_ops.trash(path)
        if self.selected_path == path:
            self.selected_path = None
            self.grid_view.set_selected_path(None)
            self.details.show_detail(None)
        self.refresh_media(reset=True)
        self.set_status(f"已删除: {name}")

    def open_media(self, path: str) -> None:
        self.file_ops.open_default(path)
        self.set_status(f"已打开: {Path(path).name}")

    def reveal_media(self, path: str) -> None:
        self.file_ops.reveal(path)
        self.set_status(f"已定位: {Path(path).name}")

    def copy_prompt(self) -> None:
        detail = self._selected_detail()
        if not detail:
            return
        self.clipboard_clear()
        self.clipboard_append(detail.get("prompt") or "")
        self.set_status("Prompt 已复制")

    def set_status(self, text: str) -> None:
        self.status_var.set(text)
        self._animate_status_flash()

    def _animate_status_flash(self, step: int = 0) -> None:
        phases = [1.0, 0.8, 0.56, 0.32, 0.12, 0.0]
        if self.status_after_id is not None:
            self.after_cancel(self.status_after_id)
            self.status_after_id = None
        if step >= len(phases):
            self.status_bar.configure(fg_color=STATUS_BASE_COLOR)
            return
        self.status_bar.configure(fg_color=_mix_color(STATUS_BASE_COLOR, STATUS_FLASH_COLOR, phases[step]))
        self.status_after_id = self.after(55, lambda: self._animate_status_flash(step + 1))

    def _style_buttons(self, *buttons) -> None:
        for button in buttons:
            button.configure(fg_color=ACTION_BUTTON_COLOR, hover_color=ACTION_BUTTON_HOVER)
            self._set_animation_state(button, "fg_color", ACTION_BUTTON_COLOR)
            button.bind("<Enter>", lambda _event, btn=button: self._animate_button_state(btn, ACTION_BUTTON_HOVER), add="+")
            button.bind("<Leave>", lambda _event, btn=button: self._animate_button_state(btn, ACTION_BUTTON_COLOR), add="+")
            button.bind("<ButtonPress-1>", lambda _event, btn=button: self._animate_button_state(btn, ACTION_BUTTON_PRESS), add="+")
            button.bind("<ButtonRelease-1>", lambda _event, btn=button: self._restore_button(btn), add="+")

    def _style_entry(self, entry) -> None:
        self._set_animation_state(entry, "border_color", INPUT_BORDER_COLOR)
        entry.bind("<FocusIn>", lambda _event, widget=entry: self._animate_widget_color(widget, "border_color", INPUT_BORDER_FOCUS), add="+")
        entry.bind("<FocusOut>", lambda _event, widget=entry: self._animate_widget_color(widget, "border_color", INPUT_BORDER_COLOR), add="+")
        entry.bind("<Return>", lambda _event, widget=entry: self._flash_entry(widget, INPUT_BORDER_FOCUS, INPUT_BORDER_FLASH), add="+")

    def _style_option_menu(self, option_menu) -> None:
        self._set_animation_state(option_menu, "button_color", OPTION_BUTTON_BASE)
        option_menu.bind("<Enter>", lambda _event, widget=option_menu: self._animate_widget_color(widget, "button_color", OPTION_BUTTON_HOVER), add="+")
        option_menu.bind("<Leave>", lambda _event, widget=option_menu: self._animate_widget_color(widget, "button_color", OPTION_BUTTON_BASE), add="+")

    def _style_checkbox(self, checkbox) -> None:
        checkbox.configure(fg_color=CHECKBOX_HOVER, hover_color=CHECKBOX_FLASH)
        self._set_animation_state(checkbox, "fg_color", CHECKBOX_HOVER)
        checkbox.bind("<Enter>", lambda _event, widget=checkbox: self._animate_widget_color(widget, "fg_color", CHECKBOX_FLASH), add="+")
        checkbox.bind("<Leave>", lambda _event, widget=checkbox: self._animate_widget_color(widget, "fg_color", CHECKBOX_HOVER), add="+")

    def _animate_button_state(self, button, target_color: str) -> None:
        self._animate_widget_color(button, "fg_color", target_color)

    def _restore_button(self, button) -> None:
        pointer_inside = button.winfo_containing(button.winfo_pointerx(), button.winfo_pointery()) == button
        target = ACTION_BUTTON_HOVER if pointer_inside else ACTION_BUTTON_COLOR
        self._animate_button_state(button, target)

    def _flash_entry(self, entry, settle_color: str, flash_color: str) -> None:
        active_settle = INPUT_BORDER_FOCUS if entry.focus_displayof() == entry else settle_color
        self._animate_widget_color(entry, "border_color", flash_color, duration_ms=90, steps=5, followup_color=active_settle)

    def _flash_option_menu(self, option_menu) -> None:
        self._animate_widget_color(option_menu, "button_color", OPTION_BUTTON_FLASH, duration_ms=90, steps=5, followup_color=OPTION_BUTTON_BASE)

    def _flash_checkbox(self, checkbox) -> None:
        self._animate_widget_color(checkbox, "fg_color", CHECKBOX_FLASH, duration_ms=85, steps=4, followup_color=CHECKBOX_HOVER)

    def _animate_widget_color(self, widget, option: str, target_color: str, duration_ms: int = 140, steps: int = 8, followup_color: str | None = None) -> None:
        current_color = self._get_animation_state(widget, option)
        self._cancel_widget_animation(widget, option)
        self._run_color_animation(widget, option, current_color, target_color, duration_ms, steps, followup_color)

    def _run_color_animation(self, widget, option: str, start_color: str, target_color: str, duration_ms: int, steps: int, followup_color: str | None, step: int = 0) -> None:
        if not widget.winfo_exists():
            return
        if step > steps:
            self._apply_widget_color(widget, option, target_color)
            if followup_color is not None and followup_color != target_color:
                self._run_color_animation(widget, option, target_color, followup_color, duration_ms, steps)
            return
        ratio = step / max(steps, 1)
        color = _mix_color(start_color, target_color, ratio)
        self._apply_widget_color(widget, option, color)
        delay = max(10, duration_ms // max(steps, 1))
        after_id = widget.after(delay, lambda: self._run_color_animation(widget, option, start_color, target_color, duration_ms, steps, followup_color, step + 1))
        self._store_widget_animation(widget, option, after_id)

    def _apply_widget_color(self, widget, option: str, color: str) -> None:
        widget.configure(**{option: color})
        self._set_animation_state(widget, option, color)

    def _cancel_widget_animation(self, widget, option: str) -> None:
        animations = getattr(widget, "_anim_after_ids", {})
        after_id = animations.pop(option, None)
        if after_id is not None:
            try:
                widget.after_cancel(after_id)
            except Exception:
                pass
        widget._anim_after_ids = animations

    def _store_widget_animation(self, widget, option: str, after_id: str) -> None:
        animations = getattr(widget, "_anim_after_ids", {})
        animations[option] = after_id
        widget._anim_after_ids = animations

    def _set_animation_state(self, widget, option: str, value: str) -> None:
        state = getattr(widget, "_anim_state", {})
        state[option] = value
        widget._anim_state = state

    def _get_animation_state(self, widget, option: str) -> str:
        state = getattr(widget, "_anim_state", {})
        return state.get(option, widget.cget(option))

    def on_close(self) -> None:
        self.jobs.shutdown()
        self.db.close()
        self.destroy()
