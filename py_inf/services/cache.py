from __future__ import annotations

from collections import OrderedDict
import hashlib
from pathlib import Path

from py_inf.services.settings import THUMB_DIR


def build_image_cache_key(path: str, *, size: tuple[int, int], variant: str, mtime_ns: int | None = None) -> str:
    if mtime_ns is None:
        try:
            mtime_ns = Path(path).stat().st_mtime_ns
        except OSError:
            mtime_ns = 0
    return f"{variant}:{size[0]}x{size[1]}:{mtime_ns}:{path}"


class ImageCache:
    def __init__(self, limit: int = 1024, limit_bytes: int | None = None) -> None:
        self.limit = limit
        self.limit_bytes = limit_bytes
        self.total_cost = 0
        self._items: OrderedDict[str, tuple[object, int]] = OrderedDict()

    def get(self, key: str):
        if key not in self._items:
            return None
        value, cost = self._items.pop(key)
        self._items[key] = (value, cost)
        return value

    def set(self, key: str, value: object, cost: int | None = None) -> None:
        if cost is None:
            cost = self._estimate_cost(value)
        if key in self._items:
            _old_value, old_cost = self._items.pop(key)
            self.total_cost -= old_cost
        self._items[key] = (value, cost)
        self.total_cost += cost
        self._trim()

    def clear(self) -> None:
        self._items.clear()
        self.total_cost = 0

    def _trim(self) -> None:
        while self._items and ((self.limit_bytes is not None and self.total_cost > self.limit_bytes) or len(self._items) > self.limit):
            _key, (_value, cost) = self._items.popitem(last=False)
            self.total_cost -= cost

    def _estimate_cost(self, value: object) -> int:
        width = getattr(value, "width", None)
        height = getattr(value, "height", None)
        if callable(width) and callable(height):
            try:
                return max(1, int(width()) * int(height()) * 4)
            except Exception:
                return 1
        return 1




def mb_to_bytes(value: int) -> int:
    return max(1, int(value)) * 1024 * 1024


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
