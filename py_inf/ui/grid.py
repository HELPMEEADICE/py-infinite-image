from __future__ import annotations

import ctypes
import math
import tkinter as tk
from queue import Empty, Queue

import customtkinter as ctk

TILE_WIDTH = 220
TILE_HEIGHT = 260
THUMB_SIZE = 200
H_GAP = 16
V_GAP = 16
PADDING = 8
OVERSCAN_ROWS = 2
BG_COLOR = "#0f0d13"
CARD_COLOR = "#2b2930"
CARD_HOVER_COLOR = "#36343b"
CARD_SELECTED_COLOR = "#4f378b"
TEXT_COLOR = "#cac4d0"
TEXT_ACTIVE_COLOR = "#e6e0e9"
PLACEHOLDER_COLOR = "#36343b"
PLACEHOLDER_HIGHLIGHT = "#4a4458"
OUTLINE_COLOR = "#d0bcff"


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


def _get_display_frequency() -> int | None:
    user32 = ctypes.windll.user32
    enum_settings = ctypes.windll.user32.EnumDisplaySettingsW

    class DevMode(ctypes.Structure):
        _fields_ = [
            ("dmDeviceName", ctypes.c_wchar * 32),
            ("dmSpecVersion", ctypes.c_ushort),
            ("dmDriverVersion", ctypes.c_ushort),
            ("dmSize", ctypes.c_ushort),
            ("dmDriverExtra", ctypes.c_ushort),
            ("dmFields", ctypes.c_ulong),
            ("dmOrientation", ctypes.c_short),
            ("dmPaperSize", ctypes.c_short),
            ("dmPaperLength", ctypes.c_short),
            ("dmPaperWidth", ctypes.c_short),
            ("dmScale", ctypes.c_short),
            ("dmCopies", ctypes.c_short),
            ("dmDefaultSource", ctypes.c_short),
            ("dmPrintQuality", ctypes.c_short),
            ("dmColor", ctypes.c_short),
            ("dmDuplex", ctypes.c_short),
            ("dmYResolution", ctypes.c_short),
            ("dmTTOption", ctypes.c_short),
            ("dmCollate", ctypes.c_short),
            ("dmFormName", ctypes.c_wchar * 32),
            ("dmLogPixels", ctypes.c_ushort),
            ("dmBitsPerPel", ctypes.c_ulong),
            ("dmPelsWidth", ctypes.c_ulong),
            ("dmPelsHeight", ctypes.c_ulong),
            ("dmDisplayFlags", ctypes.c_ulong),
            ("dmDisplayFrequency", ctypes.c_ulong),
            ("dmICMMethod", ctypes.c_ulong),
            ("dmICMIntent", ctypes.c_ulong),
            ("dmMediaType", ctypes.c_ulong),
            ("dmDitherType", ctypes.c_ulong),
            ("dmReserved1", ctypes.c_ulong),
            ("dmReserved2", ctypes.c_ulong),
            ("dmPanningWidth", ctypes.c_ulong),
            ("dmPanningHeight", ctypes.c_ulong),
        ]

    dev_mode = DevMode()
    dev_mode.dmSize = ctypes.sizeof(DevMode)
    ENUM_CURRENT_SETTINGS = -1
    if not enum_settings(None, ENUM_CURRENT_SETTINGS, ctypes.byref(dev_mode)):
        return None
    frequency = int(dev_mode.dmDisplayFrequency)
    if frequency <= 1:
        return None
    return frequency


class MediaGrid(ctk.CTkFrame):
    def __init__(self, master, image_cache, thumb_service, job_service, on_select, on_load_more, on_context=None, on_open=None, **kwargs):
        super().__init__(master, **kwargs)
        self.image_cache = image_cache
        self.thumb_service = thumb_service
        self.job_service = job_service
        self.on_select = on_select
        self.on_load_more = on_load_more
        self.on_context = on_context
        self.on_open = on_open

        self.items: list[dict] = []
        self.columns = 4
        self.row_height = TILE_HEIGHT + V_GAP
        self.pending_results: Queue[tuple[int, str, str, object]] = Queue()
        self.pending_paths: set[str] = set()
        self.tiles: list[dict] = []
        self.has_more = False
        self.last_range: tuple[int, int] | None = None
        self.last_scroll_signature: tuple[float, int, int] | None = None
        self.load_requested_for_count = -1
        self.selected_path: str | None = None
        self.hover_path: str | None = None
        self.hover_strengths: dict[str, float] = {}
        self.selected_strengths: dict[str, float] = {}
        self.reveal_strengths: dict[str, float] = {}
        self.loading_phase = 0.0
        self.scroll_target_y = 0.0
        self.scroll_current_y = 0.0
        self.refresh_rate_hz = self._detect_refresh_rate_hz()
        self.tick_interval_ms = max(4, int(round(1000 / self.refresh_rate_hz)))
        self.tick_scale = 60.0 / self.refresh_rate_hz
        self.last_start_x: int | None = None
        self.last_columns = self.columns
        self.resize_anim_pending = False
        self.grid_shift_start = 0.0
        self.grid_shift_current = 0.0
        self.grid_shift_target = 0.0
        self.path_layout_transitions: dict[str, dict[str, float]] = {}
        self.resize_after_id = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, bg=BG_COLOR, highlightthickness=0, bd=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.scrollbar = ctk.CTkScrollbar(self, orientation="vertical", command=self._on_scrollbar)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)

        self.after(self.tick_interval_ms, self._ui_tick)

    def render_items(self, items: list[dict], has_more: bool = False, reset: bool = True) -> None:
        if reset:
            self.items = list(items)
            self.last_range = None
            self.load_requested_for_count = -1
            self.scroll_target_y = 0.0
            self.scroll_current_y = 0.0
            self.last_start_x = None
            self.last_columns = self.columns
            self.grid_shift_start = 0.0
            self.grid_shift_current = 0.0
            self.grid_shift_target = 0.0
            self.path_layout_transitions.clear()
            self.resize_anim_pending = False
            self.canvas.yview_moveto(0)
        else:
            existing = {item["path"] for item in self.items}
            self.items.extend(item for item in items if item["path"] not in existing)
        self.has_more = has_more
        self._recompute_columns()
        self._update_scroll_region()
        self._update_visible_tiles(force=True)

    def set_selected_path(self, path: str | None) -> None:
        self.selected_path = path
        if path is not None:
            self.selected_strengths.setdefault(path, 0.0)
        self._refresh_visible_tile_visuals()

    def _ui_tick(self) -> None:
        self.loading_phase = (self.loading_phase + 0.12 * self.tick_scale) % (math.pi * 2)
        scroll_changed = self._step_smooth_scroll()
        self._drain_pending_results()
        animation_changed = self._step_animation_state()
        layout_changed = self._step_layout_animation()
        self._check_scroll_changes()
        if scroll_changed or animation_changed or layout_changed:
            self._refresh_visible_tile_visuals()
        if self.winfo_exists():
            self.after(self.tick_interval_ms, self._ui_tick)

    def _on_canvas_configure(self, _event=None) -> None:
        self.resize_anim_pending = True
        if self.resize_after_id is not None:
            self.after_cancel(self.resize_after_id)
        self.resize_after_id = self.after(16, self._apply_canvas_resize)

    def _apply_canvas_resize(self) -> None:
        self.resize_after_id = None
        self._recompute_columns()
        self._update_scroll_region()
        self._update_visible_tiles(force=True)

    def _on_scrollbar(self, *args) -> None:
        if not args:
            return
        if args[0] == "moveto" and len(args) >= 2:
            self.canvas.yview_moveto(args[1])
        elif args[0] == "scroll" and len(args) >= 3:
            self.canvas.yview_scroll(int(args[1]), args[2])
        else:
            self.canvas.yview(*args)
        self._sync_scroll_targets()
        self._update_visible_tiles(force=True)

    def _on_mousewheel(self, event) -> str:
        if event.num == 4:
            delta = -3
        elif event.num == 5:
            delta = 3
        elif event.delta > 0:
            delta = -max(1, int(event.delta / 40))
        elif event.delta < 0:
            delta = max(1, int(abs(event.delta) / 40))
        else:
            delta = 0
        self._scroll_by_units(delta)
        return "break"

    def _scroll_by_units(self, delta_units: int) -> None:
        total_height = self._total_scroll_height()
        step = max(24, self.row_height // 3)
        self.scroll_target_y = max(0.0, min(total_height, self.scroll_target_y + delta_units * step))
        if abs(self.scroll_target_y - self.scroll_current_y) < 1:
            self.scroll_current_y = self.scroll_target_y
        self._update_visible_tiles(force=True)

    def _tile_path_at_current_item(self) -> str | None:
        current = self.canvas.find_withtag("current")
        if not current:
            return None
        item_id = current[0]
        for tile in self.tiles:
            if item_id in tile["canvas_ids"]:
                return tile.get("bound_path")
        return None

    def _tile_at_event(self, event) -> dict | None:
        current = self.canvas.find_withtag("current")
        if current:
            item_id = current[0]
            for tile in self.tiles:
                if item_id in tile["canvas_ids"]:
                    return tile
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        overlapping = self.canvas.find_overlapping(x, y, x, y)
        if not overlapping:
            return None
        hit_ids = set(overlapping)
        for tile in self.tiles:
            if hit_ids.intersection(tile["canvas_ids"]):
                return tile
        return None

    def _on_motion(self, event) -> None:
        tile = self._tile_at_event(event)
        path = tile.get("bound_path") if tile else None
        if path != self.hover_path:
            self.hover_path = path
            if path is not None:
                self.hover_strengths.setdefault(path, 0.0)

    def _on_leave(self, _event) -> None:
        self.hover_path = None

    def _on_click(self, event) -> None:
        path = self._tile_path_at_current_item()
        if path:
            self.on_select(path)

    def _on_double_click(self, event) -> None:
        path = self._tile_path_at_current_item()
        if not path:
            return
        self.on_select(path)
        if self.on_open:
            self.on_open(path)

    def _on_right_click(self, event) -> None:
        path = self._tile_path_at_current_item()
        if not path:
            return
        self.on_select(path)
        if self.on_context:
            self.on_context(path, event.x_root, event.y_root)

    def _check_scroll_changes(self) -> None:
        y0, _y1 = self.canvas.yview()
        height = self.canvas.winfo_height()
        width = self.canvas.winfo_width()
        signature = (round(y0, 4), height, width)
        if signature != self.last_scroll_signature:
            self.last_scroll_signature = signature
            self._update_visible_tiles(force=False)

    def _recompute_columns(self) -> None:
        width = max(self.canvas.winfo_width(), TILE_WIDTH + 2 * PADDING)
        usable = max(width - 2 * PADDING, TILE_WIDTH)
        self.columns = max(1, usable // (TILE_WIDTH + H_GAP))

    def _update_scroll_region(self) -> None:
        rows = max(1, math.ceil(len(self.items) / self.columns))
        total_height = PADDING * 2 + rows * self.row_height
        total_width = max(self.canvas.winfo_width(), PADDING * 2 + self.columns * (TILE_WIDTH + H_GAP))
        self.canvas.configure(scrollregion=(0, 0, total_width, total_height))
        self.scroll_target_y = min(self.scroll_target_y, self._total_scroll_height())
        self.scroll_current_y = min(self.scroll_current_y, self._total_scroll_height())

    def _ensure_tile_pool(self) -> None:
        viewport_height = max(self.canvas.winfo_height(), self.row_height)
        visible_rows = max(1, math.ceil(viewport_height / self.row_height))
        desired = (visible_rows + OVERSCAN_ROWS * 2) * self.columns
        while len(self.tiles) < desired:
            tile_index = len(self.tiles)
            rect_id = self.canvas.create_rectangle(0, 0, 0, 0, fill=CARD_COLOR, outline="")
            image_bg_id = self.canvas.create_rectangle(0, 0, 0, 0, fill=PLACEHOLDER_COLOR, outline="")
            image_id = self.canvas.create_image(0, 0, anchor="nw")
            text_id = self.canvas.create_text(0, 0, anchor="nw", fill=TEXT_COLOR, font=("Segoe UI", 11), width=TILE_WIDTH - 20)
            tile = {
                "index": tile_index,
                "canvas_ids": [rect_id, image_bg_id, image_id, text_id],
                "rect_id": rect_id,
                "image_bg_id": image_bg_id,
                "image_id": image_id,
                "text_id": text_id,
                "bound_path": None,
                "base_x": 0,
                "base_y": 0,
            }
            self.tiles.append(tile)

    def _update_visible_tiles(self, force: bool = False) -> None:
        self._ensure_tile_pool()
        if not self.items:
            for tile in self.tiles:
                for canvas_id in tile["canvas_ids"]:
                    self.canvas.itemconfigure(canvas_id, state="hidden")
                tile["bound_path"] = None
            return

        viewport_height = max(self.canvas.winfo_height(), self.row_height)
        scroll_region = self.canvas.cget("scrollregion")
        try:
            _x0, _y0, _x1, total_height = map(float, scroll_region.split())
        except Exception:
            total_height = PADDING * 2 + self.row_height
        top_y = self.canvas.yview()[0] * max(total_height, 1)
        first_row = max(0, int(top_y // self.row_height) - OVERSCAN_ROWS)
        visible_rows = max(1, math.ceil(viewport_height / self.row_height) + OVERSCAN_ROWS * 2)
        start_index = first_row * self.columns
        end_index = min(len(self.items), (first_row + visible_rows) * self.columns)
        visible_range = (start_index, end_index)
        if not force and visible_range == self.last_range:
            self._maybe_load_more(top_y, viewport_height, total_height)
            return
        self.last_range = visible_range

        canvas_width = max(self.canvas.winfo_width(), TILE_WIDTH + 2 * PADDING)
        total_grid_width = self.columns * TILE_WIDTH + max(0, self.columns - 1) * H_GAP
        start_x = max(PADDING, (canvas_width - total_grid_width) // 2)
        previous_positions = {tile.get("bound_path"): (tile.get("base_x", 0), tile.get("base_y", 0)) for tile in self.tiles if tile.get("bound_path")}
        previous_start_x = self.last_start_x if self.last_start_x is not None else start_x
        previous_columns = self.last_columns
        new_positions: dict[str, tuple[int, int]] = {}

        visible_items = self.items[start_index:end_index]
        for tile, item_index in zip(self.tiles, range(start_index, end_index)):
            item = self.items[item_index]
            row = item_index // self.columns
            col = item_index % self.columns
            x = start_x + col * (TILE_WIDTH + H_GAP)
            y = PADDING + row * self.row_height
            new_positions[item["path"]] = (x, y)
            tile["base_x"] = x
            tile["base_y"] = y
            self._assign_tile(tile, item)
            self._position_tile(tile, x, y)

        self._update_resize_animation(previous_positions, new_positions, previous_start_x, start_x, previous_columns)
        self.last_start_x = start_x
        self.last_columns = self.columns

        for tile in self.tiles[len(visible_items):]:
            for canvas_id in tile["canvas_ids"]:
                self.canvas.itemconfigure(canvas_id, state="hidden")
            tile["bound_path"] = None

        self._maybe_load_more(top_y, viewport_height, total_height)

    def _position_tile(self, tile: dict, x: int, y: int) -> None:
        path = tile.get("bound_path")
        x, y = self._layout_position_for_path(path, x, y)
        hover_strength = self.hover_strengths.get(path, 0.0) if path else 0.0
        selected_strength = self.selected_strengths.get(path, 0.0) if path else 0.0
        reveal_strength = self.reveal_strengths.get(path, 0.0) if path else 0.0
        loading_strength = 1.0 if path in self.pending_paths else 0.0

        lift = int(round(hover_strength * 6 + selected_strength * 10 + reveal_strength * 4))
        image_inset = 10 - int(round(reveal_strength * 3))
        image_size = THUMB_SIZE + int(round(reveal_strength * 6))
        top = y - lift

        card_fill = _mix_color(CARD_COLOR, CARD_HOVER_COLOR, min(1.0, hover_strength * 0.85 + reveal_strength * 0.25))
        card_fill = _mix_color(card_fill, CARD_SELECTED_COLOR, min(1.0, selected_strength * 0.95 + reveal_strength * 0.2))

        pulse = (math.sin(self.loading_phase) + 1.0) / 2.0
        placeholder_fill = _mix_color(PLACEHOLDER_COLOR, PLACEHOLDER_HIGHLIGHT, loading_strength * (0.35 + pulse * 0.45))
        placeholder_fill = _mix_color(placeholder_fill, CARD_SELECTED_COLOR, selected_strength * 0.25)

        outline_strength = min(1.0, selected_strength + hover_strength * 0.65 + reveal_strength * 0.4)
        outline_color = _mix_color(CARD_COLOR, OUTLINE_COLOR, outline_strength)
        outline_width = 1 + int(round(outline_strength * 2)) if outline_strength > 0.08 else 0

        self.canvas.coords(tile["rect_id"], x, top, x + TILE_WIDTH, top + TILE_HEIGHT)
        self.canvas.coords(tile["image_bg_id"], x + image_inset, top + image_inset, x + image_inset + image_size, top + image_inset + image_size)
        self.canvas.coords(tile["image_id"], x + image_inset, top + image_inset)
        self.canvas.coords(tile["text_id"], x + 10, top + 218)

        self.canvas.itemconfigure(tile["rect_id"], fill=card_fill, outline=outline_color if outline_width else "", width=outline_width)
        self.canvas.itemconfigure(tile["image_bg_id"], fill=placeholder_fill)
        self.canvas.itemconfigure(tile["text_id"], fill=_mix_color(TEXT_COLOR, TEXT_ACTIVE_COLOR, min(1.0, selected_strength * 0.7 + hover_strength * 0.35 + reveal_strength * 0.4)))
        for canvas_id in tile["canvas_ids"]:
            self.canvas.itemconfigure(canvas_id, state="normal")

    def _assign_tile(self, tile: dict, item: dict) -> None:
        path = item["path"]
        previous_path = tile.get("bound_path")
        tile["bound_path"] = path
        self.canvas.itemconfigure(tile["text_id"], text=item.get("filename", ""))
        if previous_path != path and previous_path == self.hover_path:
            self.hover_path = None
        cache_key = f"grid:{path}"
        image = self.image_cache.get(cache_key)
        if image is not None:
            self.canvas.itemconfigure(tile["image_id"], image=image)
            return
        self.canvas.itemconfigure(tile["image_id"], image="")
        if path in self.pending_paths:
            return
        self.pending_paths.add(path)
        future = self.job_service.submit(self.thumb_service.load_image, path, (THUMB_SIZE, THUMB_SIZE), fit="contain")
        future.add_done_callback(lambda f, tile_id=tile["index"], bound_path=path, key=cache_key: self.pending_results.put((tile_id, bound_path, key, f)))

    def _drain_pending_results(self) -> None:
        while True:
            try:
                tile_id, path, cache_key, future = self.pending_results.get_nowait()
            except Empty:
                break
            self.pending_paths.discard(path)
            self._apply_thumb(tile_id, path, cache_key, future)

    def _apply_thumb(self, tile_id: int, path: str, cache_key: str, future) -> None:
        try:
            pil_image = future.result()
        except Exception:
            pil_image = None
        if pil_image is None:
            return
        image = tk.PhotoImage(master=self.canvas, data=self._pil_to_png_data(pil_image))
        self.image_cache.set(cache_key, image)
        self.reveal_strengths[path] = 1.0
        if tile_id < len(self.tiles):
            tile = self.tiles[tile_id]
            if tile.get("bound_path") == path:
                self.canvas.itemconfigure(tile["image_id"], image=image)
        for tile in self.tiles:
            if tile.get("bound_path") == path:
                self.canvas.itemconfigure(tile["image_id"], image=image)

    def _pil_to_png_data(self, pil_image) -> bytes:
        from io import BytesIO

        buffer = BytesIO()
        pil_image.save(buffer, format="PNG")
        return buffer.getvalue()

    def _maybe_load_more(self, top_y: float, viewport_height: int, total_height: float) -> None:
        if not self.has_more:
            self.load_requested_for_count = -1
            return
        threshold = 2 * self.row_height
        bottom_y = top_y + viewport_height
        if bottom_y >= total_height - threshold and self.load_requested_for_count != len(self.items):
            self.load_requested_for_count = len(self.items)
            self.on_load_more()

    def _step_animation_state(self) -> bool:
        changed = False
        changed |= self._step_strengths(self.hover_strengths, self.hover_path, 0.32 * self.tick_scale, floor=0.0)
        changed |= self._step_strengths(self.selected_strengths, self.selected_path, 0.24 * self.tick_scale, floor=0.0)
        changed |= self._step_reveals()
        return changed or bool(self.pending_paths)

    def _step_strengths(self, strengths: dict[str, float], active_path: str | None, speed: float, floor: float) -> bool:
        changed = False
        paths = set(strengths)
        if active_path:
            paths.add(active_path)
        for path in list(paths):
            current = strengths.get(path, 0.0)
            target = 1.0 if path == active_path else floor
            updated = current + (target - current) * speed
            if abs(updated - target) < 0.03:
                updated = target
            if abs(updated - current) > 0.004:
                changed = True
            if updated <= 0.001 and target == 0.0:
                strengths.pop(path, None)
            else:
                strengths[path] = updated
        return changed

    def _step_reveals(self) -> bool:
        changed = False
        decay = max(0.0, 1.0 - (1.0 - 0.78) * self.tick_scale)
        for path in list(self.reveal_strengths):
            updated = self.reveal_strengths[path] * decay
            if updated < 0.04:
                self.reveal_strengths.pop(path, None)
            else:
                self.reveal_strengths[path] = updated
            changed = True
        return changed

    def _step_layout_animation(self) -> bool:
        changed = False
        if abs(self.grid_shift_target - self.grid_shift_current) > 0.4:
            self.grid_shift_current += (self.grid_shift_target - self.grid_shift_current) * min(0.85, 0.28 * self.tick_scale)
            changed = True
        elif self.grid_shift_current != self.grid_shift_target:
            self.grid_shift_current = self.grid_shift_target
            changed = True
        for path in list(self.path_layout_transitions):
            transition = self.path_layout_transitions[path]
            transition["t"] += min(1.0, 0.22 * self.tick_scale)
            if transition["t"] >= 1.0:
                self.path_layout_transitions.pop(path, None)
            changed = True
        return changed

    def _refresh_visible_tile_visuals(self) -> None:
        for tile in self.tiles:
            if tile.get("bound_path"):
                self._position_tile(tile, tile.get("base_x", 0), tile.get("base_y", 0))

    def _step_smooth_scroll(self) -> bool:
        total_height = self._total_scroll_height()
        self.scroll_target_y = max(0.0, min(total_height, self.scroll_target_y))
        self.scroll_current_y = max(0.0, min(total_height, self.scroll_current_y))
        diff = self.scroll_target_y - self.scroll_current_y
        if abs(diff) < 0.6:
            if abs(diff) > 0:
                self.scroll_current_y = self.scroll_target_y
                self._apply_scroll_position()
                return True
            return False
        self.scroll_current_y += diff * min(0.85, 0.32 * self.tick_scale)
        self._apply_scroll_position()
        return True

    def _update_resize_animation(self, previous_positions: dict[str, tuple[int, int]], new_positions: dict[str, tuple[int, int]], previous_start_x: int, start_x: int, previous_columns: int) -> None:
        if not self.resize_anim_pending:
            return
        self.path_layout_transitions.clear()
        if previous_columns == self.columns:
            shift = previous_start_x - start_x
            self.grid_shift_start = shift
            self.grid_shift_current = shift
            self.grid_shift_target = 0.0
        else:
            self.grid_shift_start = 0.0
            self.grid_shift_current = 0.0
            self.grid_shift_target = 0.0
            for path, (new_x, new_y) in new_positions.items():
                old_x, old_y = previous_positions.get(path, (new_x, new_y - 24))
                self.path_layout_transitions[path] = {
                    "from_x": float(old_x),
                    "from_y": float(old_y),
                    "to_x": float(new_x),
                    "to_y": float(new_y),
                    "t": 0.0,
                }
        self.resize_anim_pending = False

    def _layout_position_for_path(self, path: str | None, x: int, y: int) -> tuple[int, int]:
        if path and path in self.path_layout_transitions:
            transition = self.path_layout_transitions[path]
            t = max(0.0, min(1.0, transition["t"]))
            x = int(round(transition["from_x"] + (transition["to_x"] - transition["from_x"]) * t))
            y = int(round(transition["from_y"] + (transition["to_y"] - transition["from_y"]) * t))
        elif abs(self.grid_shift_current) > 0.4:
            x = int(round(x + self.grid_shift_current))
        return x, y

    def _apply_scroll_position(self) -> None:
        total_height = self._total_scroll_height()
        if total_height <= 0:
            self.canvas.yview_moveto(0)
            return
        self.canvas.yview_moveto(self.scroll_current_y / total_height)

    def _sync_scroll_targets(self) -> None:
        total_height = self._total_scroll_height()
        current_top = self.canvas.yview()[0] * total_height if total_height > 0 else 0.0
        self.scroll_target_y = current_top
        self.scroll_current_y = current_top

    def _detect_refresh_rate_hz(self) -> int:
        try:
            refresh_rate = _get_display_frequency()
        except Exception:
            refresh_rate = None
        if refresh_rate is None:
            return 60
        return max(60, min(240, refresh_rate))

    def _total_scroll_height(self) -> float:
        scroll_region = self.canvas.cget("scrollregion")
        try:
            _x0, _y0, _x1, total_height = map(float, scroll_region.split())
        except Exception:
            total_height = PADDING * 2 + self.row_height
        viewport_height = max(self.canvas.winfo_height(), 1)
        return max(0.0, total_height - viewport_height)
