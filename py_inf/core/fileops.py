from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from send2trash import send2trash


class FileOps:
    def move(self, source: str, target_dir: str) -> str:
        src = Path(source)
        dst_dir = Path(target_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / src.name
        shutil.move(str(src), str(dst))
        return str(dst)

    def reveal(self, source: str) -> None:
        subprocess.Popen(["explorer", "/select,", str(Path(source))])

    def trash(self, source: str) -> None:
        send2trash(source)
