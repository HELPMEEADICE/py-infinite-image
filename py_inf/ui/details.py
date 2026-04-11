from __future__ import annotations

import customtkinter as ctk

PANEL_BG = "#1d1b20"
PANEL_FLASH = "#36343b"
PREVIEW_BG = "#2b2930"
PREVIEW_FLASH = "#4f378b"
TEXTBOX_BG = "#141218"
TEXTBOX_FLASH = "#4f378b"


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


class DetailsPanel(ctk.CTkFrame):
    def __init__(self, master, image_cache, thumb_service, **kwargs):
        super().__init__(master, fg_color=PANEL_BG, corner_radius=24, **kwargs)
        self.image_cache = image_cache
        self.thumb_service = thumb_service
        self.preview_after_id = None
        self.text_after_id = None
        self.resize_after_id = None
        self.panel_flash_after_id = None
        self.last_width: int | None = None
        self.content_shift = 0.0
        self.settle_after_id = None

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.place(relx=0, rely=0, relwidth=1, relheight=1, x=0, y=0)
        self.content.grid_rowconfigure(1, weight=1)
        self.preview_label = ctk.CTkLabel(self.content, text="未选择项目", fg_color=PREVIEW_BG, corner_radius=16)
        self.preview_label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.text = ctk.CTkTextbox(self.content, width=280, fg_color=TEXTBOX_BG, corner_radius=12)
        self.text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.text.configure(state="disabled")

        self.bind("<Configure>", self._on_resize)

    def show_detail(self, item: dict | None) -> None:
        self._cancel_preview_animation()
        self._cancel_text_animation()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        if not item:
            self.preview_label.configure(text="未选择项目", image=None, fg_color=PREVIEW_BG)
            self.text.configure(fg_color=TEXTBOX_BG)
            self.text.insert("1.0", "")
            self.text.configure(state="disabled")
            return
        cache_key = f"detail:{item['path']}"
        image = self.image_cache.get(cache_key)
        if image is None:
            pil_image = self.thumb_service.load_image(item["path"], (280, 280), fit="preview")
            if pil_image is not None:
                image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=pil_image.size)
                self.image_cache.set(cache_key, image)
        if image is not None:
            self.preview_label.configure(text="", image=image)
        else:
            self.preview_label.configure(text="无预览", image=None)
        tags = item.get("tags") or ""
        lines = [
            f"路径: {item.get('path', '')}",
            f"类型: {item.get('kind', '')}",
            f"尺寸: {item.get('width') or '-'} x {item.get('height') or '-'}",
            f"时长: {item.get('duration') or '-'}",
            f"模型: {item.get('model') or '-'}",
            f"采样器: {item.get('sampler') or '-'}",
            f"种子: {item.get('seed') or '-'}",
            f"Steps: {item.get('steps') or '-'}",
            f"CFG: {item.get('cfg') or '-'}",
            f"标签: {tags}",
            "",
            "Prompt:",
            item.get('prompt') or "",
            "",
            "Negative Prompt:",
            item.get('negative_prompt') or "",
        ]
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")
        self._animate_preview_flash()
        self._animate_text_flash()

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
        self.content_shift = max(-8.0, min(8.0, -delta * 0.1))
        if self.settle_after_id is not None:
            self.after_cancel(self.settle_after_id)
        self.settle_after_id = self.after(120, self._animate_resize_settle)
        if abs(delta) >= 40:
            self._animate_panel_flash()

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

    def _animate_panel_flash(self, step: int = 0) -> None:
        phases = [0.22, 0.1, 0.0]
        if self.panel_flash_after_id is not None and step == 0:
            self.after_cancel(self.panel_flash_after_id)
            self.panel_flash_after_id = None
        if step >= len(phases):
            self.configure(fg_color=PANEL_BG)
            self.panel_flash_after_id = None
            return
        self.configure(fg_color=_mix_color(PANEL_BG, PANEL_FLASH, phases[step]))
        self.panel_flash_after_id = self.after(34, lambda: self._animate_panel_flash(step + 1))

    def _animate_preview_flash(self, step: int = 0) -> None:
        phases = [1.0, 0.72, 0.44, 0.2, 0.0]
        if step >= len(phases):
            self.preview_label.configure(fg_color=PREVIEW_BG)
            self.preview_after_id = None
            return
        self.preview_label.configure(fg_color=_mix_color(PREVIEW_BG, PREVIEW_FLASH, phases[step]))
        self.preview_after_id = self.after(42, lambda: self._animate_preview_flash(step + 1))

    def _animate_text_flash(self, step: int = 0) -> None:
        phases = [1.0, 0.82, 0.55, 0.28, 0.0]
        if step >= len(phases):
            self.text.configure(fg_color=TEXTBOX_BG)
            self.text_after_id = None
            return
        self.text.configure(fg_color=_mix_color(TEXTBOX_BG, TEXTBOX_FLASH, phases[step]))
        self.text_after_id = self.after(38, lambda: self._animate_text_flash(step + 1))

    def _cancel_preview_animation(self) -> None:
        if self.preview_after_id is not None:
            self.after_cancel(self.preview_after_id)
            self.preview_after_id = None

    def _cancel_text_animation(self) -> None:
        if self.text_after_id is not None:
            self.after_cancel(self.text_after_id)
            self.text_after_id = None
