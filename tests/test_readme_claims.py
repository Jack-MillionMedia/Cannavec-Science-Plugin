"""README credibility guards — the tool's pitch is that every number is
verifiable, so the README's own claims must be mechanically true.

These convert two rot-prone prose claims into enforced invariants (critical-path
#4): the headline unit-test count and the documented CLI subcommand line. Both
are deterministic + offline (§II/§III). The count is stated as a LOWER BOUND
("N+ unit tests") so adding tests can never make the claim false — it only fails
if coverage is silently removed below the stated floor, or if the CLI doc drifts
from the actual argparse surface.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_ROOT = Path(__file__).resolve().parents[1]
_README = (_ROOT / "README.md").read_text(encoding="utf-8")
_PLUGIN_JSON = (_ROOT / ".claude-plugin" / "plugin.json").read_text(
    encoding="utf-8"
)


class TestPluginJsonTestCountClaim(unittest.TestCase):
    """The marketplace-facing plugin.json description must state the unit-test
    count as a true LOWER BOUND too — it was stale (a precise '1,887') and
    unguarded while the README floor was enforced, so the two surfaces disagreed
    and plugin.json understated reality."""

    def test_plugin_json_states_count_as_lower_bound(self) -> None:
        self.assertRegex(
            _PLUGIN_JSON, r"\b[\d,]+\+\s+unit tests\b",
            "plugin.json must state the unit-test count as a lower bound "
            "('N+ unit tests'), not a precise rotting number.",
        )

    def test_plugin_json_count_meets_suite_and_matches_readme_floor(self) -> None:
        pj = re.search(r"\b([\d,]+)\+\s+unit tests\b", _PLUGIN_JSON)
        rm = re.search(r"\b([\d,]+)\+\s+unit tests\b", _README)
        self.assertIsNotNone(pj, "no 'N+ unit tests' claim found in plugin.json")
        self.assertIsNotNone(rm, "no 'N+ unit tests' claim found in README")
        pj_floor = int(pj.group(1).replace(",", ""))
        rm_floor = int(rm.group(1).replace(",", ""))
        self.assertEqual(
            pj_floor, rm_floor,
            f"plugin.json floor ({pj_floor}) must match the README floor "
            f"({rm_floor}) so the two surfaces never disagree.",
        )
        actual = unittest.defaultTestLoader.discover(
            str(_ROOT / "tests")
        ).countTestCases()
        self.assertGreaterEqual(
            actual, pj_floor,
            f"plugin.json claims {pj_floor}+ unit tests but the suite only has "
            f"{actual}.",
        )


class TestReadmeTestCountClaim(unittest.TestCase):
    """README's "N+ unit tests" must be a true lower bound on the real suite."""

    def test_readme_states_test_count_as_lower_bound(self) -> None:
        # Must be phrased as a lower bound ("1,970+ unit tests"), never a precise
        # count that rots the moment a test is added.
        self.assertRegex(
            _README, r"\b[\d,]+\+\s+unit tests\b",
            "README must state the unit-test count as a lower bound "
            "('N+ unit tests'), not a precise rotting number.",
        )

    def test_suite_meets_or_exceeds_readme_lower_bound(self) -> None:
        m = re.search(r"\b([\d,]+)\+\s+unit tests\b", _README)
        self.assertIsNotNone(m, "no 'N+ unit tests' claim found in README")
        stated = int(m.group(1).replace(",", ""))
        actual = unittest.defaultTestLoader.discover(
            str(_ROOT / "tests")
        ).countTestCases()
        self.assertGreaterEqual(
            actual, stated,
            f"README claims {stated}+ unit tests but the suite only has "
            f"{actual}. Either coverage regressed or the README overstates — "
            f"lower the README floor or restore the tests.",
        )


class TestReadmeCliLineMatchesArgparse(unittest.TestCase):
    """The documented CLI subcommand line must match the real argparse surface,
    so a new/renamed subcommand can never silently desync the docs (kb-audit
    was the omission this guards against)."""

    def _documented_subcommands(self) -> set[str]:
        # Extract the "<a|b|c|...>" group from the README's CLI line.
        m = re.search(
            r"python3 -m cannavec_science\s+`?<([a-z0-9|_-]+)>", _README
        )
        self.assertIsNotNone(m, "no documented CLI subcommand line in README")
        return set(m.group(1).split("|"))

    def _actual_subcommands(self) -> set[str]:
        from cannavec_science.__main__ import _build_parser
        parser = _build_parser()
        choices: set[str] = set()
        for action in parser._actions:  # noqa: SLF001 — argparse introspection
            if isinstance(action, getattr(__import__("argparse"),
                                          "_SubParsersAction")):
                choices.update(action.choices.keys())
        return choices

    def test_documented_matches_actual(self) -> None:
        documented = self._documented_subcommands()
        actual = self._actual_subcommands()
        self.assertEqual(
            documented, actual,
            f"README CLI line is out of sync with argparse. "
            f"Documented-but-missing: {documented - actual or '∅'}; "
            f"real-but-undocumented: {actual - documented or '∅'}.",
        )


if __name__ == "__main__":
    unittest.main()
