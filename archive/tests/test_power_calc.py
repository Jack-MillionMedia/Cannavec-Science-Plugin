"""Tests for the stdlib-only sample-size / power calculator (spec 002 US2).

The calculator's formula correctness is the load-bearing claim. We
test against worked examples from the canonical textbooks: Cohen (1988)
for the continuous case, Fleiss (1981) for the proportion case. The
calculator must land within ±1 subject of the textbook answer.
"""

import math
import unittest

from cannavec_science.power_calc import (
    PowerCalculation,
    calc_continuous_two_arm,
    calc_odds_ratio_two_arm,
    calc_proportion_two_arm,
    calc_unsupported,
    z_for_alpha,
    z_for_power,
    render_markdown,
)


class CriticalValueTests(unittest.TestCase):
    """Sanity-check the z-table-replacement primitives."""

    def test_z_alpha_two_sided_05(self):
        # z_{0.025} = 1.96
        self.assertAlmostEqual(z_for_alpha(0.05, two_sided=True), 1.96, places=2)

    def test_z_alpha_one_sided_05(self):
        # z_{0.05} = 1.645
        self.assertAlmostEqual(z_for_alpha(0.05, two_sided=False), 1.6449, places=3)

    def test_z_power_80(self):
        # z_{0.20} = 0.8416
        self.assertAlmostEqual(z_for_power(0.80), 0.8416, places=3)

    def test_z_power_90(self):
        # z_{0.10} = 1.2816
        self.assertAlmostEqual(z_for_power(0.90), 1.2816, places=3)


class ContinuousTwoArmTests(unittest.TestCase):
    """Cohen 1988 worked examples."""

    def test_cohen_medium_effect(self):
        # Cohen 1988 §2.4.1: d = 0.5, α = 0.05 two-sided, power = 0.80.
        # Textbook answers across editions: 63 (uncorrected) / 64 (with
        # small-sample +1 correction). Our ceil(63) + 1 = 64 lands on
        # the corrected textbook value.
        out = calc_continuous_two_arm(
            outcome="medium effect", mean_diff=0.5, sd=1.0,
            alpha=0.05, power=0.80,
        )
        self.assertFalse(out.method_not_supported)
        self.assertIn(out.n_per_arm, (63, 64, 65))
        self.assertEqual(out.n_total, out.n_per_arm * 2)

    def test_cohen_small_effect(self):
        # d = 0.2 → very large sample.
        out = calc_continuous_two_arm(
            outcome="small effect", mean_diff=0.2, sd=1.0,
        )
        self.assertGreater(out.n_per_arm, 380)
        self.assertLess(out.n_per_arm, 410)

    def test_cohen_large_effect(self):
        # d = 0.8 → ~25 per group + small-sample correction.
        out = calc_continuous_two_arm(
            outcome="large effect", mean_diff=0.8, sd=1.0,
        )
        self.assertEqual(out.n_per_arm, 26)

    def test_higher_power_increases_n(self):
        low = calc_continuous_two_arm(
            outcome="m", mean_diff=0.5, sd=1.0, power=0.80,
        )
        high = calc_continuous_two_arm(
            outcome="m", mean_diff=0.5, sd=1.0, power=0.90,
        )
        self.assertGreater(high.n_per_arm, low.n_per_arm)

    def test_zero_effect_unsupported(self):
        out = calc_continuous_two_arm(
            outcome="o", mean_diff=0.0, sd=1.0,
        )
        self.assertTrue(out.method_not_supported)
        self.assertIn("zero", out.message.lower())

    def test_zero_sd_unsupported(self):
        out = calc_continuous_two_arm(
            outcome="o", mean_diff=0.5, sd=0.0,
        )
        self.assertTrue(out.method_not_supported)


class ProportionTwoArmTests(unittest.TestCase):
    """Fleiss 1981 worked examples."""

    def test_fleiss_06_vs_04_05_80(self):
        # Fleiss 1981 Table 2.1: p1=0.60, p2=0.40, α=0.05 two-sided,
        # power=0.80 → 107 per arm. Our formula should land within ±1.
        out = calc_proportion_two_arm(
            outcome="p", p1=0.60, p2=0.40, alpha=0.05, power=0.80,
        )
        self.assertFalse(out.method_not_supported)
        self.assertGreaterEqual(out.n_per_arm, 106)
        self.assertLessEqual(out.n_per_arm, 108)

    def test_smaller_diff_larger_sample(self):
        small = calc_proportion_two_arm(
            outcome="p", p1=0.50, p2=0.45,
        )
        big = calc_proportion_two_arm(
            outcome="p", p1=0.50, p2=0.30,
        )
        self.assertGreater(small.n_per_arm, big.n_per_arm)

    def test_equal_proportions_unsupported(self):
        out = calc_proportion_two_arm(
            outcome="p", p1=0.50, p2=0.50,
        )
        self.assertTrue(out.method_not_supported)

    def test_out_of_range_unsupported(self):
        out = calc_proportion_two_arm(
            outcome="p", p1=1.5, p2=0.40,
        )
        self.assertTrue(out.method_not_supported)


class OddsRatioTests(unittest.TestCase):
    def test_or_converts_to_proportions(self):
        out = calc_odds_ratio_two_arm(
            outcome="o", odds_ratio=2.0, baseline_p=0.30,
        )
        self.assertFalse(out.method_not_supported)
        self.assertGreater(out.n_per_arm, 0)
        # Method label retained.
        self.assertEqual(out.method, "odds_ratio_two_arm")

    def test_or_equal_one_unsupported(self):
        out = calc_odds_ratio_two_arm(
            outcome="o", odds_ratio=1.0, baseline_p=0.30,
        )
        self.assertTrue(out.method_not_supported)

    def test_negative_or_unsupported(self):
        out = calc_odds_ratio_two_arm(
            outcome="o", odds_ratio=-1.0, baseline_p=0.30,
        )
        self.assertTrue(out.method_not_supported)

    def test_out_of_range_baseline_unsupported(self):
        out = calc_odds_ratio_two_arm(
            outcome="o", odds_ratio=2.0, baseline_p=1.5,
        )
        self.assertTrue(out.method_not_supported)


class UnsupportedTests(unittest.TestCase):
    def test_calc_unsupported_returns_typed(self):
        out = calc_unsupported(
            outcome="single-arm",
            reason="single-arm design — specify historical control",
        )
        self.assertTrue(out.method_not_supported)
        self.assertEqual(out.method, "unsupported")


class RenderTests(unittest.TestCase):
    def test_render_markdown(self):
        ests = (
            calc_continuous_two_arm(outcome="primary", mean_diff=0.5, sd=1.0),
            calc_unsupported(outcome="exploratory", reason="no data"),
        )
        md = render_markdown(ests)
        self.assertIn("Power calculation", md)
        self.assertIn("primary", md)
        self.assertIn("no data", md)

    def test_render_empty_returns_empty(self):
        self.assertEqual(render_markdown(()), "")


class ToDictTests(unittest.TestCase):
    def test_to_dict_round_trip(self):
        out = calc_continuous_two_arm(outcome="o", mean_diff=0.5, sd=1.0)
        d = out.to_dict()
        self.assertEqual(d["outcome"], "o")
        self.assertEqual(d["method"], "cohens_d_two_arm")
        self.assertEqual(d["n_per_arm"], out.n_per_arm)


if __name__ == "__main__":
    unittest.main()
