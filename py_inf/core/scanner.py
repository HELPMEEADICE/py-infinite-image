from __future__ import annotations

from pathlib import Path
from typing import Callable

from py_inf.core.extractor import extract_metadata, classify_media
from py_inf.core.thumb import ThumbnailService
from py_inf.data.repo import MediaRepository


class MediaScanner:
    def __init__(self, repo: MediaRepository, thumbs: ThumbnailService) -> None:
        self.repo = repo
        self.thumbs = thumbs

    def scan_roots(self, roots: list[str], progress: Callable[[str], None] | None = None) -> int:
        count = 0
        for root in roots:
            root_path = Path(root)
            if not root_path.exists():
                continue
            for path in root_path.rglob("*"):
                if not path.is_file():
                    continue
                if not classify_media(path):
                    continue
                try:
                    metadata = extract_metadata(path)
                    thumb_path = self.thumbs.ensure_thumbnail(str(path))
                    self.repo.upsert_media(path, metadata, thumb_path)
                    count += 1
                    if progress:
                        progress(str(path))
                except Exception:
                    continue
        return count
