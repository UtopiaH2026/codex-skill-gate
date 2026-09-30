from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from skill_gate.catalog import estimate_tokens, render_catalog


class CatalogTests(unittest.TestCase):
    def test_catalog_keeps_every_skill_name(self) -> None:
        index = {
            "skills": [
                {
                    "name": f"skill-{number}",
                    "description": "x" * 300,
                    "path": f"/tmp/skill-{number}/SKILL.md",
                    "scope": "user",
                }
                for number in range(30)
            ]
        }
        text = render_catalog(index, max_tokens=800, description_chars=120)
        self.assertLessEqual(estimate_tokens(text), 800)
        for number in range(30):
            self.assertIn(f"skill-{number}", text)

    def test_catalog_reports_empty_index(self) -> None:
        text = render_catalog({"skills": []}, max_tokens=500, description_chars=100)
        self.assertIn("No file-backed skills", text)


if __name__ == "__main__":
    unittest.main()
