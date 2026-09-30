from __future__ import annotations

import math
from typing import Any


def estimate_tokens(text: str) -> int:
    """Conservative mixed-language estimate without third-party tokenizers."""
    encoded = text.encode("utf-8")
    return max(math.ceil(len(encoded) / 3), math.ceil(len(text) / 4))


def _clean(value: object, limit: int | None = None) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = text.replace("<", "(").replace(">", ")")
    if limit is not None and len(text) > limit:
        return text[: max(0, limit - 1)].rstrip() + "…"
    return text


def _render(index: dict[str, Any], description_chars: int) -> str:
    skills = index.get("skills", [])
    lines = [
        '<skills_instructions source="codex-skill-gate">',
        "Coding session detected. The complete compact skill catalog is available below.",
        "Read a skill's SKILL.md completely before applying it. Use only skills that match the task.",
    ]
    if not skills:
        lines.append("No file-backed skills were found.")
    else:
        lines.append("Available skills:")
        ordered = sorted(
            (skill for skill in skills if isinstance(skill, dict)),
            key=lambda item: (str(item.get("scope", "")) != "user", str(item.get("name", "")).lower()),
        )
        for skill in ordered:
            name = _clean(skill.get("name"), 120)
            description = _clean(skill.get("description"), description_chars) if description_chars else ""
            path = _clean(skill.get("path"), 1000)
            if description:
                lines.append(f"- {name}: {description}")
            else:
                lines.append(f"- {name}")
            lines.append(f"  read: {path}")
    lines.append("</skills_instructions>")
    return "\n".join(lines)


def render_catalog(index: dict[str, Any], *, max_tokens: int, description_chars: int) -> str:
    requested = max(0, int(description_chars))
    candidates = [requested, 100, 80, 60, 40, 20, 0]
    best = _render(index, 0)
    for cap in candidates:
        if cap > requested:
            continue
        text = _render(index, cap)
        best = text
        if estimate_tokens(text) <= max_tokens:
            return text
    return best
