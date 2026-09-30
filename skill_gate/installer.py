from __future__ import annotations

import json
import re
import shlex
import shutil
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skill_gate.config import load_config, save_default_config
from skill_gate.indexer import build_index, load_index
from skill_gate.paths import RuntimePaths, atomic_write_text, default_codex_home

BEGIN_MARKER = "# BEGIN CODEX SKILL GATE"
END_MARKER = "# END CODEX SKILL GATE"
INCLUDE_RE = re.compile(r"^\s*include_instructions\s*=")


@dataclass(frozen=True)
class InstallPlan:
    scope: str
    config_path: Path
    data_root: Path
    hook_script: Path
    runtime_dir: Path


def _scope_paths(scope: str, *, project_root: Path, codex_home: Path | None = None) -> InstallPlan:
    if scope == "user":
        home = (codex_home or default_codex_home()).resolve()
        data_root = home / "skill-gate"
        config_path = home / "config.toml"
    elif scope == "project":
        root = project_root.resolve()
        data_root = root / ".skill-gate"
        config_path = root / ".codex" / "config.toml"
    else:
        raise ValueError("scope must be 'user' or 'project'")
    return InstallPlan(
        scope=scope,
        config_path=config_path,
        data_root=data_root,
        hook_script=data_root / "runtime" / "run_hook.py",
        runtime_dir=data_root / "runtime",
    )


def _remove_managed_block(text: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    inside = False
    for line in lines:
        if line.strip() == BEGIN_MARKER:
            inside = True
            continue
        if line.strip() == END_MARKER:
            inside = False
            continue
        if not inside:
            output.append(line)
    return "\n".join(output).rstrip() + ("\n" if output else "")


def _find_skills_span(lines: list[str]) -> tuple[int, int] | None:
    start = None
    for index, line in enumerate(lines):
        if line.strip() == "[skills]":
            start = index
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            end = index
            break
    return start, end


def _set_include_instructions_false(text: str) -> tuple[str, str | None, bool]:
    lines = text.rstrip("\n").splitlines()
    span = _find_skills_span(lines)
    previous: str | None = None
    created = span is None

    if span is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(["[skills]", "include_instructions = false"])
        return "\n".join(lines).rstrip() + "\n", previous, created

    start, end = span
    for index in range(start + 1, end):
        if INCLUDE_RE.match(lines[index]):
            raw = lines[index].split("=", 1)[1].strip()
            previous = raw
            lines[index] = "include_instructions = false"
            return "\n".join(lines).rstrip() + "\n", previous, created

    lines.insert(start + 1, "include_instructions = false")
    return "\n".join(lines).rstrip() + "\n", previous, created


def _restore_include_instruction(text: str, previous: str | None) -> str:
    lines = text.rstrip("\n").splitlines()
    span = _find_skills_span(lines)
    if span is None:
        return text
    start, end = span
    keys = [index for index in range(start + 1, end) if INCLUDE_RE.match(lines[index])]
    for index in reversed(keys):
        if previous is None:
            del lines[index]
        else:
            lines[index] = f"include_instructions = {previous}"
            previous = None
    return "\n".join(lines).rstrip() + ("\n" if lines else "")


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _hook_block(plan: InstallPlan) -> str:
    python = sys.executable
    posix_command = shlex.join([python, str(plan.hook_script)])
    windows_command = f'"{python}" "{plan.hook_script}"'
    return "\n".join(
        [
            BEGIN_MARKER,
            "[[hooks.UserPromptSubmit]]",
            'matcher = ""',
            "[[hooks.UserPromptSubmit.hooks]]",
            'type = "command"',
            f"command = {_toml_string(posix_command)}",
            f"commandWindows = {_toml_string(windows_command)}",
            "timeoutSec = 5",
            END_MARKER,
            "",
        ]
    )


def _copy_runtime(package_dir: Path, runtime_dir: Path) -> None:
    destination = runtime_dir / "skill_gate"
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(package_dir, destination, dirs_exist_ok=True, ignore=ignore)
    atomic_write_text(
        runtime_dir / "run_hook.py",
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "from pathlib import Path",
                "",
                "from skill_gate.hook import main",
                "",
                "",
                "if __name__ == '__main__':",
                "    raise SystemExit(main())",
                "",
            ]
        ),
    )


def _read_install_state(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def install(
    *,
    scope: str,
    project_root: Path,
    package_dir: Path,
    codex_home: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    plan = _scope_paths(scope, project_root=project_root, codex_home=codex_home)
    runtime_paths = RuntimePaths(plan.data_root)
    existing_install_state = _read_install_state(runtime_paths.install_state_file)
    config_existed = plan.config_path.exists()
    original_text = plan.config_path.read_text(encoding="utf-8") if config_existed else ""
    if not config_existed:
        original_text = ""
    config_without_managed = _remove_managed_block(original_text)
    updated, previous_include, created_skills_table = _set_include_instructions_false(
        config_without_managed
    )
    updated = updated.rstrip() + "\n\n" + _hook_block(plan)
    try:
        tomllib.loads(updated)
    except tomllib.TOMLDecodeError as exc:
        raise RuntimeError(f"refusing to write invalid TOML: {exc}") from exc

    plan_summary = {
        "scope": scope,
        "config_path": str(plan.config_path),
        "data_root": str(plan.data_root),
        "hook_script": str(plan.hook_script),
        "dry_run": dry_run,
    }
    if dry_run:
        return plan_summary

    runtime_paths.backup_dir.mkdir(parents=True, exist_ok=True)
    if config_existed:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        shutil.copy2(plan.config_path, runtime_paths.backup_dir / f"config-{stamp}.toml")

    _copy_runtime(package_dir, plan.runtime_dir)
    plan.config_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(plan.config_path, updated)

    config = save_default_config(runtime_paths.config_file)
    build_index(cwd=project_root, runtime_paths=runtime_paths, config=config, codex_home=codex_home or default_codex_home())

    if existing_install_state:
        install_state = existing_install_state
        install_state.update(plan_summary)
    else:
        install_state = {
            **plan_summary,
            "created_skills_table": created_skills_table,
            "previous_include_instructions": previous_include,
            "installed_at": time.time(),
        }
    atomic_write_text(
        runtime_paths.install_state_file,
        json.dumps(install_state, ensure_ascii=False, indent=2) + "\n",
    )
    return install_state


def uninstall(*, scope: str, project_root: Path, codex_home: Path | None = None) -> dict[str, Any]:
    plan = _scope_paths(scope, project_root=project_root, codex_home=codex_home)
    runtime_paths = RuntimePaths(plan.data_root)
    state = _read_install_state(runtime_paths.install_state_file)
    changed = False

    if plan.config_path.exists():
        text = plan.config_path.read_text(encoding="utf-8")
        updated = _remove_managed_block(text)
        previous = state.get("previous_include_instructions")
        updated = _restore_include_instruction(updated, previous)
        tomllib.loads(updated)
        atomic_write_text(plan.config_path, updated)
        changed = True

    for path in (plan.runtime_dir, runtime_paths.state_dir):
        if path.exists():
            shutil.rmtree(path)
            changed = True

    for path in (runtime_paths.index_file,):
        try:
            path.unlink()
            changed = True
        except FileNotFoundError:
            pass

    return {"scope": scope, "config_path": str(plan.config_path), "changed": changed}


def doctor(*, scope: str, project_root: Path, codex_home: Path | None = None) -> dict[str, Any]:
    plan = _scope_paths(scope, project_root=project_root, codex_home=codex_home)
    runtime_paths = RuntimePaths(plan.data_root)
    config_text = plan.config_path.read_text(encoding="utf-8") if plan.config_path.exists() else ""
    index = load_index(runtime_paths.index_file)
    checks = {
        "config_exists": plan.config_path.is_file(),
        "include_instructions_disabled": bool(
            re.search(r"(?m)^\s*include_instructions\s*=\s*false\s*$", config_text)
        ),
        "hook_installed": BEGIN_MARKER in config_text and END_MARKER in config_text,
        "runtime_installed": plan.hook_script.is_file(),
        "index_exists": runtime_paths.index_file.is_file(),
        "skill_count": len(index.get("skills", [])),
    }
    checks["ok"] = all(
        bool(checks[key])
        for key in (
            "config_exists",
            "include_instructions_disabled",
            "hook_installed",
            "runtime_installed",
            "index_exists",
        )
    )
    return checks

