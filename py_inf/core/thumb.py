from __future__ import annotations

import subprocess
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from py_inf.core.extractor import classify_media


class ThumbnailService:
    def load_image(self, media_path: str, size: tuple[int, int], *, fit: str = "contain") -> Image.Image | None:
        path = Path(media_path)
        kind = classify_media(path)
        if kind == "image":
            with Image.open(path) as image:
                return self._prepare_image(image.convert("RGB"), size, fit)
        if kind == "video":
            command = [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(path),
                "-vf",
                f"thumbnail,scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease",
                "-frames:v",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "png",
                "-",
            ]
            try:
                result = subprocess.run(command, capture_output=True, check=True)
                with Image.open(BytesIO(result.stdout)) as image:
                    return self._prepare_image(image.convert("RGB"), size, fit)
            except Exception:
                return None
        return None

    def _prepare_image(self, image: Image.Image, size: tuple[int, int], fit: str) -> Image.Image:
        if fit == "contain":
            thumb = image.copy()
            thumb.thumbnail(size)
            return ImageOps.pad(thumb, size, color=(36, 36, 36), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        preview = image.copy()
        preview.thumbnail(size)
        return preview
