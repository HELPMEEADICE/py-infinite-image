from __future__ import annotations

from collections import OrderedDict
import hashlib
from pathlib import Path

from py_inf.services.settings import THUMB_DIR


class ImageCache:
    def __init__(self, limit: int = 256) -> None:
        self.limit = limit
        self._items: OrderedDict[str, object] = OrderedDict()

    def get(self, key: str):
        if key not in self._items:
            return None
        value = self._items.pop(key)
        self._items[key] = value
        return value

    def set(self, key: str, value: object) -> None:
        if key in self._items:
            self._items.pop(key)
        self._items[key] = value
        if len(self._items) > self.limit:
            self._items.popitem(last=False)


class ThumbPaths:
    def __init__(self, base_dir: Path = THUMB_DIR) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def for_path(self, media_path: str) -> Path:
        digest = hashlib.sha1(media_path.encode("utf-8", errors="ignore")).hexdigest()
        shard = digest[:2]
        target_dir = self.base_dir / shard
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / f"{digest}.png"
