from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path

from skill_gate.installer import doctor, install, uninstall


class InstallerTests(unittest.TestCase):
    def test_install_and_uninstall_restore_existing_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            home.mkdir()
            project.mkdir()
            config_path = home / "config.toml"
            config_path.write_text(
                "[skills]\ninclude_instructions = true\nother = 1\n",
                encoding="utf-8",
            )

            result = install(
                scope="user",
                project_root=project,
                package_dir=Path(__file__).resolve().parents[1] / "skill_gate",
                codex_home=home,
            )
            installed = tomllib.loads(config_path.read_text(encoding="utf-8"))
            self.assertFalse(installed["skills"]["include_instructions"])
            self.assertEqual(installed["skills"]["other"], 1)
            self.assertEqual(len(installed["hooks"]["UserPromptSubmit"]), 1)
            health = doctor(scope="user", project_root=project, codex_home=home)
            self.assertTrue(health["ok"], health)

            uninstall(scope="user", project_root=project, codex_home=home)
            restored = tomllib.loads(config_path.read_text(encoding="utf-8"))
            self.assertTrue(restored["skills"]["include_instructions"])
            self.assertNotIn("hooks", restored)
            self.assertEqual(result["scope"], "user")

    def test_project_scope_uses_project_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            home.mkdir()
            project.mkdir()

            install(
                scope="project",
                project_root=project,
                package_dir=Path(__file__).resolve().parents[1] / "skill_gate",
                codex_home=home,
            )
            config_path = project / ".codex" / "config.toml"
            config = tomllib.loads(config_path.read_text(encoding="utf-8"))
            self.assertFalse(config["skills"]["include_instructions"])
            self.assertTrue((project / ".skill-gate" / "runtime" / "run_hook.py").is_file())
    def test_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            home.mkdir()
            result = install(
                scope="user",
                project_root=root,
                package_dir=Path(__file__).resolve().parents[1] / "skill_gate",
                codex_home=home,
                dry_run=True,
            )
            self.assertTrue(result["dry_run"])
            self.assertFalse((home / "config.toml").exists())


if __name__ == "__main__":
    unittest.main()

