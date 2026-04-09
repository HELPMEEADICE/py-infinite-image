from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable

from py_inf.core.extractor import MediaMetadata, classify_media
from py_inf.data.db import Database


class MediaRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def ensure_media_entry(self, path: Path, thumb_path: str | None = None) -> int:
        existing = self.get_media_by_path(str(path))
        if existing:
            return existing["id"]
        stat = path.stat()
        kind = classify_media(path) or "unknown"
        cursor = self.db.conn.execute(
            """
            INSERT INTO media (
                path, dir, filename, ext, kind, size_bytes, created_ts, modified_ts, added_ts, thumb_path, thumb_ready
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(path),
                str(path.parent),
                path.name,
                path.suffix.lower(),
                kind,
                stat.st_size,
                int(stat.st_ctime),
                int(stat.st_mtime),
                int(time.time()),
                thumb_path,
                1 if thumb_path else 0,
            ),
        )
        media_id = cursor.lastrowid
        self.db.conn.execute(
            """
            INSERT INTO genmeta (media_id, prompt, negative_prompt, model, sampler, seed, steps, cfg, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (media_id, None, None, None, None, None, None, None, None),
        )
        self.db.conn.commit()
        return media_id

    def get_media_by_path(self, path: str):
        return self.db.conn.execute("SELECT * FROM media WHERE path = ?", (path,)).fetchone()

    def upsert_media(self, path: Path, metadata: MediaMetadata, thumb_path: str | None) -> int:
        stat = path.stat()
        kind = classify_media(path)
        now = int(time.time())
        existing = self.get_media_by_path(str(path))
        values = (
            str(path),
            str(path.parent),
            path.name,
            path.suffix.lower(),
            kind,
            stat.st_size,
            metadata.width,
            metadata.height,
            metadata.duration,
            int(stat.st_ctime),
            int(stat.st_mtime),
            now,
            thumb_path,
            1 if thumb_path else 0,
        )
        if existing:
            self.db.conn.execute(
                """
                UPDATE media
                SET dir=?, filename=?, ext=?, kind=?, size_bytes=?, width=?, height=?, duration=?,
                    created_ts=?, modified_ts=?, thumb_path=?, thumb_ready=?
                WHERE path=?
                """,
                (
                    str(path.parent),
                    path.name,
                    path.suffix.lower(),
                    kind,
                    stat.st_size,
                    metadata.width,
                    metadata.height,
                    metadata.duration,
                    int(stat.st_ctime),
                    int(stat.st_mtime),
                    thumb_path,
                    1 if thumb_path else 0,
                    str(path),
                ),
            )
            media_id = existing["id"]
        else:
            cursor = self.db.conn.execute(
                """
                INSERT INTO media (
                    path, dir, filename, ext, kind, size_bytes, width, height, duration,
                    created_ts, modified_ts, added_ts, thumb_path, thumb_ready
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            media_id = cursor.lastrowid
        self.db.conn.execute("DELETE FROM genmeta WHERE media_id = ?", (media_id,))
        self.db.conn.execute(
            """
            INSERT INTO genmeta (media_id, prompt, negative_prompt, model, sampler, seed, steps, cfg, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                media_id,
                metadata.prompt,
                metadata.negative_prompt,
                metadata.model,
                metadata.sampler,
                metadata.seed,
                metadata.steps,
                metadata.cfg,
                metadata.raw_json,
            ),
        )
        self._update_fts(media_id)
        self.db.conn.commit()
        return media_id

    def _update_fts(self, media_id: int) -> None:
        row = self.db.conn.execute(
            """
            SELECT media.filename, genmeta.prompt, genmeta.model,
                   GROUP_CONCAT(tags.name, ' ') AS tags
            FROM media
            LEFT JOIN genmeta ON genmeta.media_id = media.id
            LEFT JOIN media_tags ON media_tags.media_id = media.id
            LEFT JOIN tags ON tags.id = media_tags.tag_id
            WHERE media.id = ?
            GROUP BY media.id
            """,
            (media_id,),
        ).fetchone()
        text = " ".join(
            part for part in [row["filename"], row["prompt"], row["model"], row["tags"]] if part
        ) if row else ""
        self.db.conn.execute("DELETE FROM text_fts WHERE media_id = ?", (media_id,))
        self.db.conn.execute("INSERT INTO text_fts (media_id, text) VALUES (?, ?)", (media_id, text))

    def query_media(
        self,
        query: str = "",
        folder: str | None = None,
        kind: str | None = None,
        favorite_only: bool = False,
        limit: int = 120,
        offset: int = 0,
    ) -> list[dict]:
        clauses = ["1=1"]
        params: list[object] = []
        join_fts = False
        if folder:
            clauses.append("media.dir = ?")
            params.append(folder)
        if kind:
            clauses.append("media.kind = ?")
            params.append(kind)
        if favorite_only:
            clauses.append("media.favorite = 1")
        if query:
            join_fts = True
            clauses.append("text_fts.text MATCH ?")
            params.append(query)
        sql = """
        SELECT media.*, genmeta.prompt, genmeta.model
        FROM media
        LEFT JOIN genmeta ON genmeta.media_id = media.id
        """
        if join_fts:
            sql += " JOIN text_fts ON text_fts.media_id = media.id "
        sql += f" WHERE {' AND '.join(clauses)} ORDER BY media.added_ts DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self.db.conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def get_media_detail(self, media_id: int):
        row = self.db.conn.execute(
            """
            SELECT media.*, genmeta.prompt, genmeta.negative_prompt, genmeta.model,
                   genmeta.sampler, genmeta.seed, genmeta.steps, genmeta.cfg,
                   GROUP_CONCAT(tags.name, ', ') AS tags
            FROM media
            LEFT JOIN genmeta ON genmeta.media_id = media.id
            LEFT JOIN media_tags ON media_tags.media_id = media.id
            LEFT JOIN tags ON tags.id = media_tags.tag_id
            WHERE media.id = ?
            GROUP BY media.id
            """,
            (media_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_folders(self) -> list[str]:
        rows = self.db.conn.execute("SELECT DISTINCT dir FROM media ORDER BY dir COLLATE NOCASE").fetchall()
        return [row[0] for row in rows]

    def list_tags(self) -> list[str]:
        rows = self.db.conn.execute("SELECT name FROM tags ORDER BY name COLLATE NOCASE").fetchall()
        return [row[0] for row in rows]

    def set_favorite(self, media_id: int, favorite: bool) -> None:
        self.db.conn.execute("UPDATE media SET favorite = ? WHERE id = ?", (1 if favorite else 0, media_id))
        self.db.conn.commit()

    def set_favorite_by_path(self, path: str, favorite: bool, thumb_path: str | None = None) -> int:
        media_id = self.ensure_media_entry(Path(path), thumb_path)
        self.set_favorite(media_id, favorite)
        return media_id

    def add_tags(self, media_id: int, names: Iterable[str]) -> None:
        for name in names:
            clean = name.strip()
            if not clean:
                continue
            self.db.conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (clean,))
            tag_id = self.db.conn.execute("SELECT id FROM tags WHERE name = ?", (clean,)).fetchone()[0]
            self.db.conn.execute(
                "INSERT OR IGNORE INTO media_tags (media_id, tag_id) VALUES (?, ?)",
                (media_id, tag_id),
            )
        self._update_fts(media_id)
        self.db.conn.commit()

    def add_tags_by_path(self, path: str, names: Iterable[str], thumb_path: str | None = None) -> int:
        media_id = self.ensure_media_entry(Path(path), thumb_path)
        self.add_tags(media_id, names)
        return media_id

    def move_media(self, media_id: int, new_path: str) -> None:
        path = Path(new_path)
        self.db.conn.execute(
            "UPDATE media SET path = ?, dir = ?, filename = ? WHERE id = ?",
            (str(path), str(path.parent), path.name, media_id),
        )
        self.db.conn.commit()

    def get_state_by_path(self, path: str) -> dict | None:
        row = self.db.conn.execute(
            """
            SELECT media.id, media.favorite,
                   GROUP_CONCAT(tags.name, ', ') AS tags
            FROM media
            LEFT JOIN media_tags ON media_tags.media_id = media.id
            LEFT JOIN tags ON tags.id = media_tags.tag_id
            WHERE media.path = ?
            GROUP BY media.id
            """,
            (path,),
        ).fetchone()
        return dict(row) if row else None

    def move_media_by_path(self, old_path: str, new_path: str) -> None:
        row = self.get_media_by_path(old_path)
        if not row:
            return
        self.move_media(row["id"], new_path)
