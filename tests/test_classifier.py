from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from skill_gate.classifier import classify


class ClassifierTests(unittest.TestCase):
    def test_fix_python_bug_is_coding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = classify("Fix the Python bug in this function", cwd=Path(directory))
        self.assertEqual(result.mode, "coding")

    def test_plain_writing_is_non_coding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = classify("写一篇关于秋天的散文", cwd=Path(directory))
        self.assertEqual(result.mode, "non_coding")
        self.assertEqual(result.evidence, ("default-non-coding",))

    def test_repo_context_alone_is_not_coding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            result = classify("帮我写一份周报", cwd=root)
        self.assertEqual(result.mode, "non_coding")

    def test_explicit_override_wins(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = classify(
                "退出编程模式，帮我整理会议记录",
                recent_messages=["fix this Python bug"],
                cwd=Path(directory),
            )
        self.assertEqual(result.mode, "non_coding")
        self.assertLess(result.score, 0)

    def test_continuation_uses_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = classify(
                "继续",
                recent_messages=["Refactor this TypeScript component and fix the failing test"],
                cwd=Path(directory),
            )
        self.assertEqual(result.mode, "coding")


if __name__ == "__main__":
    unittest.main()
