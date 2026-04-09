from __future__ import annotations

from py_inf.data.repo import MediaRepository


class FavoriteService:
    def __init__(self, repo: MediaRepository) -> None:
        self.repo = repo

    def set_favorite(self, media_id: int, favorite: bool) -> None:
        self.repo.set_favorite(media_id, favorite)

    def set_favorite_by_path(self, path: str, favorite: bool, thumb_path: str | None = None) -> int:
        return self.repo.set_favorite_by_path(path, favorite, thumb_path)
