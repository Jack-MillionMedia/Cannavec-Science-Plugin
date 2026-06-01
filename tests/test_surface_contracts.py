"""Surface-contract guardrails for the prose surfaces (commands + agents).

These tests encode Constitution invariants that are otherwise only
documented:

- §IV: the slash-command surface is locked at exactly five; a sixth
  requires a constitutional amendment.
- Honest Surface Constraints: a surface that promises orchestration MUST
  be backed by deterministic code OR carry an explicit honesty disclaimer
  in its frontmatter description. We enforce the disclaimer half for any
  agent whose description advertises orchestration / delegation.
- Governance: every agent operates under the Constitution and declares
  valid frontmatter (name == file stem + a description).

Stdlib-only (Constitution §X): frontmatter is parsed with string ops, not
a YAML dependency.
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMMANDS_DIR = ROOT / "commands"
AGENTS_DIR = ROOT / "agents"

EXPECTED_COMMANDS = ["ask.md", "discover.md", "research.md", "rigor.md", "verify.md"]

# An agent description that promises any of these is making an
# orchestration claim under the Constitution's Honest Surface Constraints.
ORCHESTRATION_TRIGGER = re.compile(r"orchestrat|deleg|research team|autonomous", re.IGNORECASE)

# ... and must therefore carry one of these disclaimer markers.
DISCLAIMER_MARKER = re.compile(r"honesty disclaimer|not an autonomous|metaphor", re.IGNORECASE)


def _split_frontmatter(text):
    """Return (frontmatter, body) for a `---\\n...\\n---\\n...` file.

    Returns (None, text) when the file has no leading frontmatter block.
    """
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    return parts[1], parts[2]


class TestCommandSurface(unittest.TestCase):
    def test_exactly_five_slash_commands(self):
        found = sorted(p.name for p in COMMANDS_DIR.glob("*.md"))
        self.assertEqual(
            found,
            EXPECTED_COMMANDS,
            "Constitution §IV locks the slash-command surface at exactly five "
            "(ask / discover / research / rigor / verify). Adding or removing one "
            "requires a constitutional amendment, not just a new file.",
        )


class TestAgentSurface(unittest.TestCase):
    def _agent_files(self):
        agents = sorted(AGENTS_DIR.glob("*.md"))
        self.assertTrue(agents, "expected at least one agent file under agents/")
        return agents

    def test_every_agent_has_valid_frontmatter(self):
        for path in self._agent_files():
            fm, _ = _split_frontmatter(path.read_text(encoding="utf-8"))
            self.assertIsNotNone(fm, f"{path.name}: missing YAML frontmatter block")
            self.assertRegex(
                fm,
                rf"(?m)^\s*name:\s*{re.escape(path.stem)}\s*$",
                f"{path.name}: frontmatter 'name' must equal the file stem",
            )
            self.assertRegex(
                fm,
                r"(?m)^\s*description:\s*\S+",
                f"{path.name}: frontmatter must carry a non-empty 'description'",
            )

    def test_every_agent_operates_under_the_constitution(self):
        for path in self._agent_files():
            text = path.read_text(encoding="utf-8")
            self.assertIn(
                "constitution.md",
                text,
                f"{path.name}: every agent must operate under "
                ".specify/memory/constitution.md (governance clause)",
            )

    def test_orchestration_agents_carry_an_honesty_disclaimer(self):
        for path in self._agent_files():
            fm, _ = _split_frontmatter(path.read_text(encoding="utf-8"))
            if fm and ORCHESTRATION_TRIGGER.search(fm):
                self.assertRegex(
                    fm,
                    DISCLAIMER_MARKER,
                    f"{path.name}: its description promises orchestration/delegation "
                    "but carries no honesty disclaimer. The Constitution's Honest "
                    "Surface Constraints require a deterministic enforcer OR an "
                    "explicit disclaimer in the frontmatter description.",
                )

    def test_research_lead_agent_exists_and_is_compliant(self):
        path = AGENTS_DIR / "cannabis-research-lead.md"
        self.assertTrue(path.exists(), "cannabis-research-lead.md must exist")
        fm, body = _split_frontmatter(path.read_text(encoding="utf-8"))
        self.assertIsNotNone(fm)
        # It is an orchestration agent, so it must trigger AND disclaim.
        self.assertRegex(fm, ORCHESTRATION_TRIGGER)
        self.assertRegex(fm, DISCLAIMER_MARKER)
        # It must name both delegate subagents in its body.
        self.assertIn("cannabis-source-hunter", body)
        self.assertIn("cannabis-research-reviewer", body)


if __name__ == "__main__":
    unittest.main()
