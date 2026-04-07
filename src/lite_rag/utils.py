from __future__ import annotations

import json
from pathlib import Path

from .config import SUPPORTED_TEXT_EXTENSIONS


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def ensure_text_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() not in SUPPORTED_TEXT_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {path.suffix}. OCR/PDF/image parsing is not supported yet."
        )


def read_text_file(path: Path) -> str:
    ensure_text_file(path)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig")


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []

    paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
    if not paragraphs:
        paragraphs = [normalized]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
        current = paragraph

        while len(current) > chunk_size:
            chunks.append(current[:chunk_size])
            start = max(0, chunk_size - chunk_overlap)
            current = current[start:]

    if current:
        chunks.append(current)

    return [chunk for chunk in chunks if chunk.strip()]


def dump_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)
