from __future__ import annotations

import customtkinter as ctk

PREVIEW_BG = "#242424"
PREVIEW_FLASH = "#3e5f88"
TEXTBOX_BG = "#1f1f1f"
TEXTBOX_FLASH = "#324865"


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
        super().__init__(master, **kwargs)
        self.image_cache = image_cache
        self.thumb_service = thumb_service
        self.preview_after_id = None
        self.text_after_id = None
        self.grid_rowconfigure(1, weight=1)
        self.preview_label = ctk.CTkLabel(self, text="未选择项目", fg_color=PREVIEW_BG, corner_radius=12)
        self.preview_label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.text = ctk.CTkTextbox(self, width=280, fg_color=TEXTBOX_BG)
        self.text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.text.configure(state="disabled")

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
