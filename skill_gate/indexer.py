from __future__ import annotations

import hashlib
import json
import re
import tomllib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from skill_gate.paths import RuntimePaths, atomic_write_text, default_codex_home

FRONTMATTER_KEY = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")
YAML_STRING_PREFIXES = {"|", "|-", "|+", ">", ">-", ">+"}


@dataclass(frozen=True)
class SkillEntry:
    name: str
    description: str
    path: str
    scope: str
    source: str
    mtime_ns: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SkillEntry":
        return cls(
            name=str(payload["name"]),
            description=str(payload.get("description", "")),
            path=str(payload["path"]),
            scope=str(payload.get("scope", "unknown")),
            source=str(payload.get("source", "")),
            mtime_ns=int(payload.get("mtime_ns", 0)),
        )


def _strip_yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.replace("\\n", " ").strip()


def parse_frontmatter(text: str) -> dict[str, str]:
    """Parse the small SKILL.md frontmatter subset needed by the indexer."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    fields: dict[str, str] = {}
    index = 1
    while index < len(lines):
        line = lines[index]
        if line.strip() == "---":
            break

        match = FRONTMATTER_KEY.match(line)
        if match:
            key, raw_value = match.group(1), match.group(2).strip()
            if raw_value in YAML_STRING_PREFIXES:
                continuation: list[str] = []
                index += 1
                while index < len(lines):
                    candidate = lines[index]
                    if candidate.strip() == "---":
                        index -= 1
                        break
                    if candidate and not candidate[0].isspace():
                        index -= 1
                        break
                    continuation.append(candidate.strip())
                    index += 1
                separator = "\n" if raw_value.startswith("|") else " "
                fields[key] = separator.join(part for part in continuation if part).strip()
            else:
                fields[key] = _strip_yaml_scalar(raw_value)
        index += 1

    return fields


def _read_enabled_plugins(codex_home: Path) -> set[str]:
    config_path = codex_home / "config.toml"
    if not config_path.is_file():
        return set()
    try:
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return set()

    result: set[str] = set()
    plugins = payload.get("plugins", {})
    if not isinstance(plugins, dict):
        return result
    for plugin_id, plugin_config in plugins.items():
        if not isinstance(plugin_config, dict):
            continue
        if plugin_config.get("enabled") is True:
            result.add(str(plugin_id).split("@", 1)[0])
    return result


def _plugin_skill_roots(codex_home: Path, include_disabled: bool) -> list[Path]:
    cache_root = codex_home / "plugins" / "cache"
    if not cache_root.is_dir():
        return []

    enabled = _read_enabled_plugins(codex_home)
    roots: list[Path] = []
    for manifest_path in cache_root.rglob("plugin.json"):
        if manifest_path.parent.name != ".codex-plugin":
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = str(manifest.get("name", ""))
        if not include_disabled and name not in enabled:
            continue
        raw_skills = manifest.get("skills", "./skills/")
        if not isinstance(raw_skills, str):
            continue
        skill_root = (manifest_path.parent.parent / raw_skills).resolve()
        if skill_root.is_dir():
            roots.append(skill_root)
    return roots


def _project_skill_roots(cwd: Path, codex_home: Path) -> list[Path]:
    roots: list[Path] = []
    resolved_cwd = cwd.resolve()
    global_roots = {
        (codex_home / "skills").resolve(),
        (Path.home() / ".codex" / "skills").resolve(),
        (Path.home() / ".agents" / "skills").resolve(),
    }
    for parent in (resolved_cwd, *resolved_cwd.parents):
        is_cwd = parent == resolved_cwd
        has_project_marker = any(
            (parent / marker).exists()
            for marker in (".git", ".codex/config.toml", ".agents/plugins/marketplace.json")
        )
        if not is_cwd and not has_project_marker:
            continue

        found_here: list[Path] = []
        for relative in (Path(".codex") / "skills", Path(".agents") / "skills"):
            candidate = (parent / relative).resolve()
            if candidate in global_roots:
                continue
            if candidate.is_dir():
                found_here.append(candidate)
        if found_here:
            roots.extend(found_here)
            break
    return roots


def _root_is_excluded(path: Path, excluded: Iterable[Path]) -> bool:
    resolved = path.resolve()
    for excluded_path in excluded:
        try:
            resolved.relative_to(excluded_path.resolve())
            return True
        except ValueError:
            continue
    return False


def discover_roots(
    *,
    cwd: Path,
    config: dict[str, Any],
    codex_home: Path | None = None,
) -> list[tuple[Path, str, str]]:
    home = (codex_home or default_codex_home()).resolve()
    roots: list[tuple[Path, str, str]] = []
    for user_root in (home / "skills", Path.home() / ".agents" / "skills"):
        if user_root.is_dir():
            source = "CODEX_HOME skills" if user_root == home / "skills" else "global agent skills"
            roots.append((user_root, "user", source))

    for root in _project_skill_roots(cwd, home):
        roots.append((root, "repo", "project skills"))

    include_disabled = bool(config.get("index", {}).get("include_disabled_plugins", False))
    for root in _plugin_skill_roots(home, include_disabled):
        roots.append((root, "system", "plugin skills"))

    for raw_root in config.get("index", {}).get("extra_roots", []):
        candidate = Path(str(raw_root)).expanduser()
        if not candidate.is_absolute():
            candidate = (cwd / candidate).resolve()
        if candidate.is_dir():
            roots.append((candidate, "user", "extra root"))

    excluded = [Path(str(value)) for value in config.get("index", {}).get("exclude_roots", [])]
    deduped: list[tuple[Path, str, str]] = []
    seen: set[Path] = set()
    for root, scope, source in roots:
        resolved = root.resolve()
        if resolved in seen or _root_is_excluded(resolved, excluded):
            continue
        seen.add(resolved)
        deduped.append((resolved, scope, source))
    return deduped


def _scan_skill_file(skill_file: Path, scope: str, source: str) -> SkillEntry | None:
    try:
        text = skill_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    fields = parse_frontmatter(text)
    name = fields.get("name", "").strip()
    if not name:
        return None
    description = re.sub(r"\s+", " ", fields.get("description", "")).strip()
    stat = skill_file.stat()
    return SkillEntry(
        name=name,
        description=description,
        path=str(skill_file.resolve()),
        scope=scope,
        source=source,
        mtime_ns=stat.st_mtime_ns,
    )


def build_index(
    *,
    cwd: Path,
    runtime_paths: RuntimePaths,
    config: dict[str, Any],
    codex_home: Path | None = None,
) -> dict[str, Any]:
    roots = discover_roots(cwd=cwd, config=config, codex_home=codex_home)
    entries: list[SkillEntry] = []
    seen_names: set[str] = set()

    for root, scope, source in roots:
        for skill_file in sorted(root.rglob("SKILL.md")):
            entry = _scan_skill_file(skill_file, scope, source)
            if entry is None or entry.name in seen_names:
                continue
            seen_names.add(entry.name)
            entries.append(entry)

    entries.sort(key=lambda item: (item.scope != "user", item.scope != "repo", item.name.lower()))
    index = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "roots": [{"path": str(root), "scope": scope, "source": source} for root, scope, source in roots],
        "skills": [entry.to_dict() for entry in entries],
    }
    write_index(runtime_paths.index_file, index)
    return index


def load_index(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return {}
    return payload


def write_index(path: Path, index: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(index, ensure_ascii=False, indent=2) + "\n")


def index_is_stale(index: dict[str, Any]) -> bool:
    if not index:
        return True
    try:
        generated = datetime.fromisoformat(str(index["generated_at"]).replace("Z", "+00:00")).timestamp()
    except (KeyError, ValueError):
        return True

    for root in index.get("roots", []):
        root_path = Path(str(root.get("path", "")))
        if not root_path.is_dir():
            return True
        for skill_file in root_path.rglob("SKILL.md"):
            try:
                if skill_file.stat().st_mtime > generated:
                    return True
            except OSError:
                return True
    return False


def content_fingerprint(index: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    for skill in index.get("skills", []):
        digest.update(str(skill.get("name", "")).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(skill.get("mtime_ns", 0)).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()

