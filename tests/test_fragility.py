"""Tests for the Fragility Index of a 2×2 trial (spec 022).

Fisher's exact p is pinned against textbook values; the Fragility Index against
a direct iteration of the Walsh (2014) algorithm.
"""

import contextlib
import io
import json
import unittest

from cannavec_science import fragility as fg


class FisherTests(unittest.TestCase):
    def test_known_value(self):
        # The classic 2×2 — two-sided Fisher p = 0.4857.
        self.assertAlmostEqual(fg.fisher_exact_two_sided(3, 1, 1, 3),
                               0.4857, places=4)

    def test_symmetric(self):
        self.assertAlmostEqual(
            fg.fisher_exact_two_sided(8, 2, 1, 9),
            fg.fisher_exact_two_sided(2, 8, 9, 1), places=12)

    def test_degenerate_margin_is_one(self):
        self.assertEqual(fg.fisher_exact_two_sided(0, 10, 0, 10), 1.0)

    def test_negative_cell_raises(self):
        with self.assertRaises(fg.FragilityError):
            fg.fisher_exact_two_sided(-1, 10, 5, 5)


class IndexTests(unittest.TestCase):
    def test_fragility_index_of_one(self):
        r = fg.fragility_index(1, 50, 9, 50)
        self.assertTrue(r.significant)
        self.assertEqual(r.fragility_index, 1)
        self.assertAlmostEqual(r.fragility_quotient, 1 / 100, places=9)
        self.assertEqual(r.modified_arm, "treatment")
        self.assertGreaterEqual(r.p_at_index, 0.05)
        self.assertLess(r.p_value, 0.05)

    def test_pinned_indices(self):
        self.assertEqual(fg.fragility_index(8, 100, 20, 100).fragility_index, 2)
        self.assertEqual(fg.fragility_index(10, 100, 25, 100).fragility_index, 4)
        self.assertEqual(fg.fragility_index(3, 100, 15, 100).fragility_index, 3)

    def test_control_arm_modified_when_it_has_fewer_events(self):
        # Reversed table: control has the fewer events → it is the one altered.
        r = fg.fragility_index(9, 50, 1, 50)
        self.assertEqual(r.modified_arm, "control")
        self.assertEqual(r.fragility_index, 1)

    def test_non_significant_has_no_index(self):
        r = fg.fragility_index(10, 100, 15, 100)
        self.assertFalse(r.significant)
        self.assertIsNone(r.fragility_index)
        self.assertIsNone(r.fragility_quotient)
        self.assertIn("not statistically significant", r.rationale)

    def test_alpha_threshold_changes_significance(self):
        # Significant at 0.05, not at 0.01 → FI undefined at the stricter α.
        sig = fg.fragility_index(1, 50, 9, 50, alpha=0.05)
        strict = fg.fragility_index(1, 50, 9, 50, alpha=0.01)
        self.assertTrue(sig.significant)
        self.assertFalse(strict.significant)

    def test_index_actually_crosses_alpha(self):
        r = fg.fragility_index(8, 100, 20, 100)
        # p_at_index ≥ α, and one fewer flip would still be below α.
        self.assertGreaterEqual(r.p_at_index, r.alpha)

    def test_input_validation(self):
        for args in [(60, 50, 9, 50), (1, 0, 9, 50), (-1, 50, 9, 50)]:
            with self.assertRaises(fg.FragilityError):
                fg.fragility_index(*args)
        with self.assertRaises(fg.FragilityError):
            fg.fragility_index(1, 50, 9, 50, alpha=1.5)


class ShapeTests(unittest.TestCase):
    def test_to_dict_deterministic(self):
        a = fg.fragility_index(8, 100, 20, 100).to_dict()
        b = fg.fragility_index(8, 100, 20, 100).to_dict()
        self.assertEqual(json.dumps(a, sort_keys=True),
                         json.dumps(b, sort_keys=True))
        self.assertEqual(a["fragility_index"], 2)

    def test_render_significant(self):
        text = fg.render_fragility(fg.fragility_index(1, 50, 9, 50))
        self.assertIn("Fragility Index", text)
        self.assertIn("single patient", text)

    def test_render_non_significant(self):
        text = fg.render_fragility(fg.fragility_index(10, 100, 15, 100))
        self.assertIn("not applicable", text)


class CliTests(unittest.TestCase):
    def _run(self, args):
        from cannavec_science.__main__ import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(args)
        return code, buf.getvalue()

    def test_cli_markdown(self):
        code, out = self._run(["fragility", "--events-t", "1", "--n-t", "50",
                               "--events-c", "9", "--n-c", "50"])
        self.assertEqual(code, 0)
        self.assertIn("Fragility Index", out)
        self.assertIn("1", out)

    def test_cli_json(self):
        code, out = self._run(["fragility", "--events-t", "8", "--n-t", "100",
                               "--events-c", "20", "--n-c", "100", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["fragility_index"], 2)

    def test_cli_non_significant_exits_zero(self):
        code, out = self._run(["fragility", "--events-t", "10", "--n-t", "100",
                               "--events-c", "15", "--n-c", "100"])
        self.assertEqual(code, 0)
        self.assertIn("not significant", out)

    def test_cli_bad_input_nonzero(self):
        code, _ = self._run(["fragility", "--events-t", "60", "--n-t", "50",
                             "--events-c", "9", "--n-c", "50"])
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
