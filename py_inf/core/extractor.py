from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi"}


@dataclass
class MediaMetadata:
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    model: str | None = None
    sampler: str | None = None
    seed: str | None = None
    steps: int | None = None
    cfg: float | None = None
    raw_json: str | None = None


def classify_media(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return None


def extract_metadata(path: Path) -> MediaMetadata:
    kind = classify_media(path)
    if kind == "image":
        return _extract_image_metadata(path)
    if kind == "video":
        return _extract_video_metadata(path)
    return MediaMetadata()


def _extract_image_metadata(path: Path) -> MediaMetadata:
    with Image.open(path) as image:
        info = image.info or {}
        metadata = MediaMetadata(width=image.width, height=image.height)
        parameter_text = None
        for key in ("parameters", "prompt", "Comment"):
            if isinstance(info.get(key), str) and info.get(key):
                parameter_text = info[key]
                break
        if parameter_text:
            _apply_parameter_text(metadata, parameter_text)
        sidecar = path.with_suffix(".json")
        if sidecar.exists():
            raw = sidecar.read_text(encoding="utf-8", errors="ignore")
            metadata.raw_json = raw
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {}
            metadata.prompt = metadata.prompt or _pick(data, "prompt", "Prompt")
            metadata.negative_prompt = metadata.negative_prompt or _pick(data, "negative_prompt", "Negative prompt")
            metadata.model = metadata.model or _pick(data, "model", "sd_model_name", "Model")
            metadata.sampler = metadata.sampler or _pick(data, "sampler", "Sampler")
            metadata.seed = metadata.seed or _pick(data, "seed", "Seed")
            metadata.steps = metadata.steps or _as_int(_pick(data, "steps", "Steps"))
            metadata.cfg = metadata.cfg or _as_float(_pick(data, "cfg_scale", "CFG scale"))
        return metadata


def _extract_video_metadata(path: Path) -> MediaMetadata:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=width,height:format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        payload = json.loads(result.stdout)
    except Exception:
        return MediaMetadata()
    streams = payload.get("streams", [])
    stream = streams[0] if streams else {}
    duration = payload.get("format", {}).get("duration")
    return MediaMetadata(
        width=_as_int(stream.get("width")),
        height=_as_int(stream.get("height")),
        duration=_as_float(duration),
        raw_json=json.dumps(payload, ensure_ascii=False),
    )


def _apply_parameter_text(metadata: MediaMetadata, text: str) -> None:
    metadata.raw_json = text
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return
    metadata.prompt = lines[0]
    if len(lines) > 1 and lines[1].lower().startswith("negative prompt:"):
        metadata.negative_prompt = lines[1].split(":", 1)[1].strip()
    for match in re.finditer(r"([A-Za-z ]+):\s*([^,\n]+)", text):
        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        if key == "model":
            metadata.model = value
        elif key == "sampler":
            metadata.sampler = value
        elif key == "seed":
            metadata.seed = value
        elif key == "steps":
            metadata.steps = _as_int(value)
        elif key in {"cfg scale", "cfg"}:
            metadata.cfg = _as_float(value)


def _pick(data: dict, *keys: str):
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def _as_int(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _as_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
