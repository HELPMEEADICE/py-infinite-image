from __future__ import annotations

import customtkinter as ctk


class DetailsPanel(ctk.CTkFrame):
    def __init__(self, master, image_cache, thumb_service, **kwargs):
        super().__init__(master, **kwargs)
        self.image_cache = image_cache
        self.thumb_service = thumb_service
        self.grid_rowconfigure(1, weight=1)
        self.preview_label = ctk.CTkLabel(self, text="未选择项目")
        self.preview_label.grid(row=0, column=0, padx=10, pady=10)
        self.text = ctk.CTkTextbox(self, width=280)
        self.text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.text.configure(state="disabled")

    def show_detail(self, item: dict | None) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        if not item:
            self.preview_label.configure(text="未选择项目", image=None)
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
