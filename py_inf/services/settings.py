from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BASE_DIR / ".app"
DATA_DIR = APP_DIR / "data"
THUMB_DIR = APP_DIR / "thumbs"
LOG_DIR = APP_DIR / "logs"
SETTINGS_FILE = DATA_DIR / "settings.json"


@dataclass
class AppSettings:
    scan_roots: list[str] = field(default_factory=list)
    page_size: int = 60
    thumb_size: int = 220
    preview_size: int = 640
    last_query: str = ""
    theme: str = "dark"


class SettingsService:
    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        THUMB_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._settings = self.load()

    def load(self) -> AppSettings:
        if not SETTINGS_FILE.exists():
            settings = AppSettings()
            self.save(settings)
            return settings
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return AppSettings(**data)

    def save(self, settings: AppSettings | None = None) -> None:
        if settings is not None:
            self._settings = settings
        SETTINGS_FILE.write_text(
            json.dumps(asdict(self._settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @property
    def settings(self) -> AppSettings:
        return self._settings

    def add_root(self, path: str) -> bool:
        normalized = str(Path(path))
        if normalized in self._settings.scan_roots:
            return False
        self._settings.scan_roots.append(normalized)
        self.save()
        return True
