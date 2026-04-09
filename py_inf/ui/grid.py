from __future__ import annotations

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
BG_COLOR = "#2b2b2b"
CARD_COLOR = "#333333"
TEXT_COLOR = "#f1f1f1"
PLACEHOLDER_COLOR = "#3c3c3c"


class MediaGrid(ctk.CTkFrame):
    def __init__(self, master, image_cache, thumb_service, job_service, on_select, on_load_more, **kwargs):
        super().__init__(master, **kwargs)
        self.image_cache = image_cache
        self.thumb_service = thumb_service
        self.job_service = job_service
        self.on_select = on_select
        self.on_load_more = on_load_more

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

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, bg=BG_COLOR, highlightthickness=0, bd=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.scrollbar = ctk.CTkScrollbar(self, orientation="vertical", command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)
        self.canvas.bind("<Button-1>", self._on_click)

        self.after(16, self._ui_tick)

    def render_items(self, items: list[dict], has_more: bool = False, reset: bool = True) -> None:
        if reset:
            self.items = list(items)
            self.last_range = None
            self.load_requested_for_count = -1
            self.canvas.yview_moveto(0)
        else:
            existing = {item["path"] for item in self.items}
            self.items.extend(item for item in items if item["path"] not in existing)
        self.has_more = has_more
        self._recompute_columns()
        self._update_scroll_region()
        self._update_visible_tiles(force=True)

    def _ui_tick(self) -> None:
        self._drain_pending_results()
        self._check_scroll_changes()
        if self.winfo_exists():
            self.after(16, self._ui_tick)

    def _on_canvas_configure(self, _event=None) -> None:
        self._recompute_columns()
        self._update_scroll_region()
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
        self.canvas.yview_scroll(delta, "units")
        self._update_visible_tiles(force=True)
        return "break"

    def _on_click(self, event) -> None:
        current = self.canvas.find_withtag("current")
        if not current:
            return
        item_id = current[0]
        for tile in self.tiles:
            if item_id in tile["canvas_ids"]:
                path = tile.get("bound_path")
                if path:
                    self.on_select(path)
                return

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

        visible_items = self.items[start_index:end_index]
        for tile, item_index in zip(self.tiles, range(start_index, end_index)):
            item = self.items[item_index]
            row = item_index // self.columns
            col = item_index % self.columns
            x = start_x + col * (TILE_WIDTH + H_GAP)
            y = PADDING + row * self.row_height
            self._position_tile(tile, x, y)
            self._assign_tile(tile, item)

        for tile in self.tiles[len(visible_items):]:
            for canvas_id in tile["canvas_ids"]:
                self.canvas.itemconfigure(canvas_id, state="hidden")
            tile["bound_path"] = None

        self._maybe_load_more(top_y, viewport_height, total_height)

    def _position_tile(self, tile: dict, x: int, y: int) -> None:
        self.canvas.coords(tile["rect_id"], x, y, x + TILE_WIDTH, y + TILE_HEIGHT)
        self.canvas.coords(tile["image_bg_id"], x + 10, y + 10, x + 10 + THUMB_SIZE, y + 10 + THUMB_SIZE)
        self.canvas.coords(tile["image_id"], x + 10, y + 10)
        self.canvas.coords(tile["text_id"], x + 10, y + 218)
        for canvas_id in tile["canvas_ids"]:
            self.canvas.itemconfigure(canvas_id, state="normal")

    def _assign_tile(self, tile: dict, item: dict) -> None:
        path = item["path"]
        tile["bound_path"] = path
        self.canvas.itemconfigure(tile["text_id"], text=item.get("filename", ""))
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
