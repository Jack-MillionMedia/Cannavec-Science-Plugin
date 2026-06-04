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


class DirectionTests(unittest.TestCase):
    """The FI must move the table toward the null, by RATE not event count.

    Regression for the direction bug: the conversion arm was chosen by which
    arm held the fewer event *count* (``a <= c``), so when the fewer-count arm
    was the higher-*rate* arm the loop pushed the table *away* from the null,
    p fell, the arm exhausted, and a bogus FI was emitted with a p far below α.
    """

    def test_smoking_gun_converts_the_lower_rate_arm_not_the_fewer_count(self):
        # treatment 8/10 = 80 %, control 30/1000 = 3 %. Treatment has the fewer
        # event COUNT (8 < 30) but the far higher RATE. The old code converted
        # the treatment arm (away from the null); the correct arm is control.
        r = fg.fragility_index(8, 10, 30, 1000)
        self.assertTrue(r.significant)
        self.assertEqual(r.modified_arm, "control")

    def test_smoking_gun_never_reports_an_index_with_p_below_alpha(self):
        # The exact reproduced defect: "FI: 2 ... lifts p to 0.0000 ≥ α = 0.05"
        # while p had actually *dropped* from 7.98e-11 to 2.91e-15. Whenever an
        # FI is reported its p_at_index must genuinely sit at or above α.
        r = fg.fragility_index(8, 10, 30, 1000)
        if r.fragility_index is not None:
            self.assertGreaterEqual(r.p_at_index, r.alpha)
            self.assertIn("≥ α", r.rationale)
            # and the rationale's quoted p must not contradict significance
            self.assertNotIn("lifts p to 0.0000 ≥", r.rationale)

    def test_second_smoking_gun_high_rate_treatment_small_arm(self):
        # treatment 9/10 = 90 %, control 50/1000 = 5 %: again the small,
        # high-rate treatment arm must NOT be the one converted.
        r = fg.fragility_index(9, 10, 50, 1000)
        self.assertTrue(r.significant)
        self.assertEqual(r.modified_arm, "control")
        if r.fragility_index is not None:
            self.assertGreaterEqual(r.p_at_index, r.alpha)

    def test_reported_index_has_p_at_or_above_alpha_over_a_grid(self):
        # Property: across a grid of significant 2×2 tables — including the
        # imbalanced-arm shapes that triggered the direction bug — EVERY
        # reported Fragility Index must have crossed α (p_at_index ≥ α). Under
        # the OLD code the imbalanced rows reported indices with p far below α.
        shapes = (
            (8, 10, 30, 1000), (9, 10, 50, 1000), (7, 10, 20, 500),
            (2, 10, 1, 200), (5, 20, 3, 400), (15, 20, 100, 1000),
            (1, 50, 9, 50), (8, 100, 20, 100), (3, 100, 15, 100),
            (40, 50, 2, 50), (18, 25, 5, 300), (90, 100, 50, 1000),
        )
        checked = 0
        for e_t, n_t, e_c, n_c in shapes:
            r = fg.fragility_index(e_t, n_t, e_c, n_c)
            if not r.significant or r.fragility_index is None:
                continue
            checked += 1
            self.assertGreaterEqual(
                r.p_at_index, r.alpha,
                msg=(f"FI reported with p_at_index < α for "
                     f"({e_t}/{n_t} vs {e_c}/{n_c}): "
                     f"p_at_index={r.p_at_index}"))
        self.assertGreaterEqual(checked, 8)  # the imbalanced rows were exercised

    def test_minimal_index_one_fewer_conversion_stays_significant(self):
        # Minimality on an imbalanced table: removing the last conversion must
        # leave p < α (otherwise the FI is not the *minimum* number).
        r = fg.fragility_index(8, 10, 30, 1000)
        self.assertTrue(r.significant)
        self.assertIsNotNone(r.fragility_index)
        a, b = r.events_t, r.n_t - r.events_t
        c, d = r.events_c, r.n_c - r.events_c
        # rebuild the table one conversion short of the reported index
        if r.modified_arm == "control":
            c, d = c + (r.fragility_index - 1), d - (r.fragility_index - 1)
        else:
            a, b = a + (r.fragility_index - 1), b - (r.fragility_index - 1)
        self.assertLess(fg.fisher_exact_two_sided(a, b, c, d), r.alpha)

    def test_balanced_tables_unchanged_by_the_direction_fix(self):
        # When arm sizes are equal, fewer-count and lower-rate coincide, so the
        # historically pinned indices must be byte-for-byte unchanged.
        self.assertEqual(fg.fragility_index(1, 50, 9, 50).fragility_index, 1)
        self.assertEqual(fg.fragility_index(8, 100, 20, 100).fragility_index, 2)
        self.assertEqual(fg.fragility_index(10, 100, 25, 100).fragility_index, 4)
        self.assertEqual(fg.fragility_index(3, 100, 15, 100).fragility_index, 3)
        self.assertEqual(fg.fragility_index(9, 50, 1, 50).modified_arm,
                         "control")


class UnbreakableTests(unittest.TestCase):
    """The "significance cannot be broken" state is surfaced honestly — never
    as a bogus FI whose ``p_at_index`` is still below α.

    That state is a *defensive invariant*: filling the lower-rate arm to 100 %
    always drives the absolute risk difference to ≤ 0, so p reaches α for any
    genuinely significant 2×2. ``test_guard_is_unreachable_for_real_tables``
    proves this exhaustively. The honest reporting *contract* for the state is
    pinned below by constructing the result directly, rather than fabricating
    an impossible input table.
    """

    @staticmethod
    def _unbreakable_result():
        # The exact shape ``_resolve_significant`` emits on its guard branch:
        # significant, but no index, no quotient, no p_at_index.
        return fg.FragilityResult(
            events_t=8, n_t=10, events_c=30, n_c=1000,
            alpha=0.05, p_value=1e-9, significant=True,
            fragility_index=None, fragility_quotient=None, p_at_index=None,
            modified_arm="control",
            rationale=("Significant at two-sided Fisher p = 0.0000; this "
                       "significance cannot be broken by converting non-events "
                       "to events in the control arm (the lower-rate arm) — "
                       "that arm is exhausted while p is still 0.0000 < "
                       "α = 0.05. The Fragility Index is undefined for this "
                       "operation here."),
        )

    def test_unbreakable_dict_carries_no_index_and_no_p_at_index(self):
        d = self._unbreakable_result().to_dict()
        self.assertTrue(d["significant"])
        self.assertIsNone(d["fragility_index"])
        self.assertIsNone(d["fragility_quotient"])
        self.assertIsNone(d["p_at_index"])

    def test_render_unbreakable_is_distinct_from_non_significant(self):
        text = fg.render_fragility(self._unbreakable_result())
        self.assertIn("cannot be broken", text.lower())
        self.assertNotIn("result is not significant", text)
        # never renders a p_at_index line for the unbreakable state
        self.assertNotIn("p at the index", text)

    def test_guard_is_unreachable_for_real_tables(self):
        # Exhaustive proof over a dense small grid: every significant table is
        # breakable in the correct direction, so a *real* call always yields a
        # concrete index with p_at_index ≥ α. The guard never fires and an FI
        # is never emitted with a sub-α p — the invariant the guard guarantees.
        sig_seen = 0
        for n_t in range(2, 22):
            for n_c in range(2, 22):
                for e_t in range(n_t + 1):
                    for e_c in range(n_c + 1):
                        r = fg.fragility_index(e_t, n_t, e_c, n_c)
                        if not r.significant:
                            continue
                        sig_seen += 1
                        self.assertIsNotNone(
                            r.fragility_index,
                            msg=f"guard fired on {e_t}/{n_t} vs {e_c}/{n_c}")
                        self.assertGreaterEqual(r.p_at_index, r.alpha)
        self.assertGreater(sig_seen, 1000)


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
