from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any


class JobService:
    def __init__(self, max_workers: int = 4, thumb_workers: int | None = None) -> None:
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.thumb_executor = ThreadPoolExecutor(max_workers=thumb_workers or max_workers)

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any):
        return self.executor.submit(fn, *args, **kwargs)

    def submit_thumb(self, fn: Callable[..., Any], *args: Any, **kwargs: Any):
        return self.thumb_executor.submit(fn, *args, **kwargs)

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.thumb_executor.shutdown(wait=False, cancel_futures=True)
