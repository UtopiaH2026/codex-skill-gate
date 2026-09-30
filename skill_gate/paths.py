from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePaths:
    """Filesystem locations owned by one Skill Gate installation."""

    data_root: Path

    @property
    def config_file(self) -> Path:
        return self.data_root / "config.json"

    @property
    def index_file(self) -> Path:
        return self.data_root / "index.json"

    @property
    def state_dir(self) -> Path:
        return self.data_root / "state"

    @property
    def backup_dir(self) -> Path:
        return self.data_root / "backups"

    @property
    def runtime_dir(self) -> Path:
        return self.data_root / "runtime"

    @property
    def runtime_package_dir(self) -> Path:
        return self.runtime_dir / "skill_gate"

    @property
    def hook_script(self) -> Path:
        return self.runtime_dir / "run_hook.py"

    @property
    def install_state_file(self) -> Path:
        return self.data_root / "install-state.json"

    @property
    def log_file(self) -> Path:
        return self.data_root / "skill-gate.log"

    @classmethod
    def discover(cls, data_root: str | os.PathLike[str] | None = None) -> "RuntimePaths":
        if data_root is not None:
            return cls(Path(data_root).expanduser().resolve())

        explicit = os.environ.get("SKILL_GATE_HOME")
        if explicit:
            return cls(Path(explicit).expanduser().resolve())

        codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
        return cls((codex_home / "skill-gate").resolve())


def default_codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser().resolve()


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding=encoding)
    os.replace(temporary, path)


def append_log(path: Path, message: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")
    except OSError:
        pass
