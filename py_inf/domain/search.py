from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from py_inf.core.extractor import classify_media
from py_inf.data.repo import MediaRepository


@dataclass
class SearchFilters:
    query: str = ""
    folder: str | None = None
    kind: str | None = None
    favorite_only: bool = False
    limit: int = 120
    offset: int = 0


class SearchService:
    def __init__(self, repo: MediaRepository) -> None:
        self.repo = repo

    def search(self, filters: SearchFilters) -> list[dict]:
        if not filters.folder:
            return []
        folder = Path(filters.folder)
        if not folder.exists() or not folder.is_dir():
            return []
        query = filters.query.lower().strip()
        items: list[dict] = []
        skip_dir_names = {"thumbnails", ".thumbnails", "thumbs", ".thumbs"}
        for path in folder.rglob("*"):
            if any(part.lower() in skip_dir_names for part in path.parts):
                continue
            if not path.is_file():
                continue
            kind = classify_media(path)
            if not kind:
                continue
            if filters.kind and kind != filters.kind:
                continue
            state = self.repo.get_state_by_path(str(path))
            if filters.favorite_only and not (state and state.get("favorite")):
                continue
            relative_name = str(path.relative_to(folder)).lower()
            if query and query not in relative_name:
                continue
            items.append(
                {
                    "path": str(path),
                    "filename": path.name,
                    "relative_path": str(path.relative_to(folder)),
                    "kind": kind,
                    "thumb_path": None,
                    "favorite": state.get("favorite", 0) if state else 0,
                    "tags": state.get("tags", "") if state else "",
                }
            )
        items.sort(key=lambda item: Path(item["path"]).stat().st_mtime, reverse=True)
        return items[filters.offset:filters.offset + filters.limit]
