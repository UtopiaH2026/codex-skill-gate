from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from skill_gate.paths import RuntimePaths, atomic_write_text

SAFE_SESSION = re.compile(r"[^A-Za-z0-9_.-]+")


def normalize_session_id(session_id: str, transcript_path: str = "") -> str:
    raw = session_id.strip() if session_id else ""
    if not raw:
        raw = hashlib.sha256(transcript_path.encode("utf-8")).hexdigest()[:24]
    safe = SAFE_SESSION.sub("_", raw)[:128]
    return safe or "default"


def state_path(runtime_paths: RuntimePaths, session_id: str, transcript_path: str = "") -> Path:
    return runtime_paths.state_dir / f"{normalize_session_id(session_id, transcript_path)}.json"


def load_state(runtime_paths: RuntimePaths, session_id: str, transcript_path: str = "") -> dict[str, Any]:
    path = state_path(runtime_paths, session_id, transcript_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_state(
    runtime_paths: RuntimePaths,
    session_id: str,
    mode: str,
    evidence: list[str] | tuple[str, ...],
    transcript_path: str = "",
) -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "mode": mode,
        "evidence": list(evidence),
        "updated_at": time.time(),
    }
    atomic_write_text(
        state_path(runtime_paths, session_id, transcript_path),
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    return payload


def reset_state(runtime_paths: RuntimePaths, session_id: str, transcript_path: str = "") -> None:
    path = state_path(runtime_paths, session_id, transcript_path)
    try:
        path.unlink()
    except FileNotFoundError:
        return
