from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skill_gate.config import save_default_config
from skill_gate.hook import run_hook
from skill_gate.indexer import build_index
from skill_gate.paths import RuntimePaths


class HookTests(unittest.TestCase):
    def test_coding_detection_injects_catalog_and_state_sticks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            skill_file = home / "skills" / "demo" / "SKILL.md"
            skill_file.parent.mkdir(parents=True)
            skill_file.write_text(
                "---\nname: demo\ndescription: Demo skill\n---\n",
                encoding="utf-8",
            )
            runtime = RuntimePaths(root / "data")
            config = save_default_config(runtime.config_file)
            with patch.dict("os.environ", {"CODEX_HOME": str(home)}):
                build_index(cwd=root, runtime_paths=runtime, config=config, codex_home=home)
                first = run_hook(
                    {
                        "hook_event_name": "UserPromptSubmit",
                        "prompt": "Fix the Python bug in this function",
                        "session_id": "session-1",
                        "cwd": str(root),
                    },
                    runtime_paths=runtime,
                )
                second = run_hook(
                    {
                        "hook_event_name": "UserPromptSubmit",
                        "prompt": "Write a short poem",
                        "session_id": "session-1",
                        "cwd": str(root),
                    },
                    runtime_paths=runtime,
                )
            self.assertIn("hookSpecificOutput", first)
            self.assertIn("demo", first["hookSpecificOutput"]["additionalContext"])
            self.assertIn("hookSpecificOutput", second)

    def test_non_coding_has_no_skill_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            home.mkdir()
            runtime = RuntimePaths(root / "data")
            save_default_config(runtime.config_file)
            with patch.dict("os.environ", {"CODEX_HOME": str(home)}):
                result = run_hook(
                    {
                        "hook_event_name": "UserPromptSubmit",
                        "prompt": "Write a short article about tea",
                        "session_id": "session-2",
                        "cwd": str(root),
                    },
                    runtime_paths=runtime,
                )
            self.assertNotIn("hookSpecificOutput", result)


if __name__ == "__main__":
    unittest.main()
