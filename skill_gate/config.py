from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from skill_gate.paths import atomic_write_text

DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "classifier": {
        "threshold": 4.0,
        "sticky": True,
        "lookback_user_messages": 2,
        "extra_strong_patterns": [],
        "extra_medium_patterns": [],
    },
    "catalog": {
        "max_tokens": 4000,
        "description_chars": 120,
    },
    "index": {
        "extra_roots": [],
        "exclude_roots": [],
        "include_disabled_plugins": False,
    },
}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path, *, create: bool = False) -> dict[str, Any]:
    if not path.exists():
        config = copy.deepcopy(DEFAULT_CONFIG)
        if create:
            save_config(path, config)
        return config

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(DEFAULT_CONFIG)

    if not isinstance(raw, dict):
        return copy.deepcopy(DEFAULT_CONFIG)
    return _merge(DEFAULT_CONFIG, raw)


def save_config(path: Path, config: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")


def save_default_config(path: Path) -> dict[str, Any]:
    config = copy.deepcopy(DEFAULT_CONFIG)
    save_config(path, config)
    return config
