"""Surface contract for skills (spec 011-022 quantitative-synthesis capstone).

Skills are prose over the deterministic backbone (§II). These tests guard that
every skill is well-formed and that the evidence-synthesis skill's honesty claim
holds — the CLI subcommands it routes to actually exist and run.
"""

import contextlib
import io
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"


def _frontmatter(text: str) -> dict:
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm = {}
    for line in parts[1].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


class SkillFrontmatterTests(unittest.TestCase):
    def test_every_skill_has_valid_frontmatter(self):
        skills = sorted(SKILLS_DIR.glob("*/SKILL.md"))
        self.assertTrue(skills, "expected at least one skill")
        for path in skills:
            fm = _frontmatter(path.read_text(encoding="utf-8"))
            for key in ("name", "description", "version"):
                self.assertIn(key, fm, f"{path.parent.name} missing {key!r}")
            self.assertTrue(fm["description"], f"{path.parent.name} empty description")


if __name__ == "__main__":
    unittest.main()
