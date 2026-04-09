from __future__ import annotations

from py_inf.data.repo import MediaRepository


class TagService:
    def __init__(self, repo: MediaRepository) -> None:
        self.repo = repo

    def list_tags(self) -> list[str]:
        return self.repo.list_tags()

    def add_tags(self, media_id: int, names: list[str]) -> None:
        self.repo.add_tags(media_id, names)

    def add_tags_by_path(self, path: str, names: list[str], thumb_path: str | None = None) -> int:
        return self.repo.add_tags_by_path(path, names, thumb_path)
