from __future__ import annotations

import json
from pathlib import Path

MAX_TRANSCRIPT_BYTES = 2 * 1024 * 1024


def _content_text(content: object) -> str:
    if not isinstance(content, list):
        return ""
    chunks: list[str] = []
    for item in content:
        if isinstance(item, str):
            chunks.append(item)
            continue
        if not isinstance(item, dict):
            continue
        value = item.get("text")
        if isinstance(value, str):
            chunks.append(value)
    return "\n".join(chunks)


def recent_user_messages(
    transcript_path: str | Path | None,
    *,
    limit: int,
    exclude_text: str = "",
) -> list[str]:
    if not transcript_path:
        return []
    path = Path(transcript_path)
    if not path.is_file() or limit <= 0:
        return []

    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - MAX_TRANSCRIPT_BYTES))
            raw = handle.read()
    except OSError:
        return []

    messages: list[str] = []
    for raw_line in raw.splitlines():
        try:
            event = json.loads(raw_line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict) or payload.get("type") != "message":
            continue
        if payload.get("role") != "user":
            continue
        text = _content_text(payload.get("content"))
        if not text.strip():
            continue
        if "<environment_context>" in text and len(text) < 1500:
            continue
        if exclude_text and text.strip() == exclude_text.strip():
            continue
        messages.append(text)

    return messages[-limit:]
