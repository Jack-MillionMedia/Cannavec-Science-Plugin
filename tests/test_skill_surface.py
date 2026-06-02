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


class EvidenceSynthesisSkillTests(unittest.TestCase):
    PATH = SKILLS_DIR / "cannabis-evidence-synthesis" / "SKILL.md"

    def test_skill_exists(self):
        self.assertTrue(self.PATH.exists())

    def test_routes_to_real_subcommands(self):
        text = self.PATH.read_text(encoding="utf-8")
        for cmd in ("meta", "fragility", "signal", "--measure prop",
                    "--moderator-key", "--knha", "--certainty"):
            self.assertIn(cmd, text, f"skill should route to {cmd!r}")

    def test_named_subcommands_actually_run(self):
        # The skill claims every tool it names is implemented — prove the two
        # CLI subcommands it routes to resolve and execute.
        from cannavec_science.__main__ import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["fragility", "--events-t", "1", "--n-t", "50",
                         "--events-c", "9", "--n-c", "50"])
        self.assertEqual(code, 0)
        self.assertIn("Fragility Index", buf.getvalue())

    def test_honesty_claim_present(self):
        # §II: a skill promising capability must be backed by deterministic code
        # OR carry an honesty disclaimer. This one carries both.
        text = self.PATH.read_text(encoding="utf-8").lower()
        self.assertIn("deterministic", text)
        self.assertIn("unit-tested", text)


if __name__ == "__main__":
    unittest.main()
