from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from skill_gate.catalog import render_catalog
from skill_gate.classifier import classify
from skill_gate.config import load_config
from skill_gate.indexer import build_index, index_is_stale, load_index
from skill_gate.paths import RuntimePaths, append_log
from skill_gate.state import load_state, reset_state, save_state
from skill_gate.transcript import recent_user_messages


def _noop_output() -> dict[str, Any]:
    return {"continue": True, "suppressOutput": True}


def run_hook(payload: dict[str, Any], *, runtime_paths: RuntimePaths | None = None) -> dict[str, Any]:
    paths = runtime_paths or RuntimePaths.discover()
    config = load_config(paths.config_file, create=True)

    event_name = str(payload.get("hook_event_name", ""))
    if event_name and event_name != "UserPromptSubmit":
        return _noop_output()

    prompt = str(payload.get("prompt", ""))
    session_id = str(payload.get("session_id", ""))
    transcript_path = str(payload.get("transcript_path") or "")
    cwd = Path(str(payload.get("cwd") or os.getcwd())).expanduser().resolve()

    previous = load_state(paths, session_id, transcript_path)
    classifier_config = config.get("classifier", {})
    lookback = int(classifier_config.get("lookback_user_messages", 2))
    history = recent_user_messages(transcript_path, limit=lookback, exclude_text=prompt)

    if os.environ.get("SKILL_GATE_FORCE_MODE") in {"coding", "non_coding"}:
        forced = os.environ["SKILL_GATE_FORCE_MODE"]
        decision = classify(
            "进入编程模式" if forced == "coding" else "非编程模式",
            recent_messages=history,
            cwd=cwd,
            classifier_config=classifier_config,
        )
    else:
        decision = classify(
            prompt,
            recent_messages=history,
            cwd=cwd,
            classifier_config=classifier_config,
        )

    sticky = bool(classifier_config.get("sticky", True))
    explicit_non_coding = decision.score <= -100
    if previous.get("mode") == "coding" and sticky and not explicit_non_coding:
        mode = "coding"
        evidence = tuple(previous.get("evidence", [])) + ("sticky-session",)
    else:
        mode = decision.mode
        evidence = decision.evidence

    if mode == "coding":
        save_state(paths, session_id, mode, evidence, transcript_path)
    elif explicit_non_coding or previous:
        reset_state(paths, session_id, transcript_path)

    if mode != "coding":
        return _noop_output()

    index = load_index(paths.index_file)
    if index_is_stale(index):
        try:
            index = build_index(cwd=cwd, runtime_paths=paths, config=config)
        except Exception as exc:  # pragma: no cover - defensive fail-open path
            append_log(paths.log_file, f"index rebuild failed: {exc!r}")
            return _noop_output()

    catalog_config = config.get("catalog", {})
    context = render_catalog(
        index,
        max_tokens=int(catalog_config.get("max_tokens", 4000)),
        description_chars=int(catalog_config.get("description_chars", 120)),
    )
    return {
        "continue": True,
        "suppressOutput": True,
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        },
    }


def main(runtime_paths: RuntimePaths | None = None) -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}
        output = run_hook(payload, runtime_paths=runtime_paths)
        sys.stdout.write(json.dumps(output, ensure_ascii=False))
        return 0
    except Exception as exc:  # fail open, never block the user prompt
        paths = runtime_paths or RuntimePaths.discover()
        append_log(paths.log_file, f"hook failed: {exc!r}")
        sys.stdout.write(json.dumps(_noop_output(), ensure_ascii=False))
        return 0
