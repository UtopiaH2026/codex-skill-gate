from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from skill_gate.config import DEFAULT_CONFIG
from skill_gate.indexer import build_index, parse_frontmatter
from skill_gate.paths import RuntimePaths


class IndexerTests(unittest.TestCase):
    def test_parse_folded_description(self) -> None:
        fields = parse_frontmatter(
            "---\nname: demo\ndescription: >-\n  First line\n  second line\n---\n"
        )
        self.assertEqual(fields["name"], "demo")
        self.assertEqual(fields["description"], "First line second line")

    def test_indexes_user_and_project_skills(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            user_skill = home / "skills" / "alpha" / "SKILL.md"
            project_skill = root / "project" / ".codex" / "skills" / "beta" / "SKILL.md"
            user_skill.parent.mkdir(parents=True)
            project_skill.parent.mkdir(parents=True)
            user_skill.write_text("---\nname: alpha\ndescription: Alpha skill\n---\n", encoding="utf-8")
            project_skill.write_text("---\nname: beta\ndescription: Beta skill\n---\n", encoding="utf-8")

            runtime = RuntimePaths(root / "runtime")
            index = build_index(
                cwd=root / "project",
                runtime_paths=runtime,
                config=DEFAULT_CONFIG,
                codex_home=home,
            )
            self.assertEqual({item["name"] for item in index["skills"]}, {"alpha", "beta"})
            self.assertTrue(runtime.index_file.is_file())


if __name__ == "__main__":
    unittest.main()
