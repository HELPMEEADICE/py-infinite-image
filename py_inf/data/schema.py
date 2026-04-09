SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS migrations (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    dir TEXT NOT NULL,
    filename TEXT NOT NULL,
    ext TEXT NOT NULL,
    kind TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    width INTEGER,
    height INTEGER,
    duration REAL,
    created_ts INTEGER,
    modified_ts INTEGER,
    favorite INTEGER NOT NULL DEFAULT 0,
    added_ts INTEGER NOT NULL,
    thumb_path TEXT,
    thumb_ready INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS genmeta (
    media_id INTEGER PRIMARY KEY,
    prompt TEXT,
    negative_prompt TEXT,
    model TEXT,
    sampler TEXT,
    seed TEXT,
    steps INTEGER,
    cfg REAL,
    raw_json TEXT,
    FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS media_tags (
    media_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (media_id, tag_id),
    FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE,
    FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS text_fts USING fts5(
    media_id UNINDEXED,
    text
);

CREATE INDEX IF NOT EXISTS idx_media_dir ON media(dir);
CREATE INDEX IF NOT EXISTS idx_media_kind ON media(kind);
CREATE INDEX IF NOT EXISTS idx_media_modified ON media(modified_ts DESC);
CREATE INDEX IF NOT EXISTS idx_media_favorite ON media(favorite);
"""
