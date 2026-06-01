"""Tests for pharmacovigilance disproportionality (spec 023).

PRR / ROR / Yates χ² pinned against a direct computation; the MHRA/Evans signal
criterion (PRR ≥ 2, χ² ≥ 4, a ≥ 3) exercised at each boundary.
"""

import contextlib
import io
import json
import unittest

from cannavec_science import disproportionality as dp


class MeasureTests(unittest.TestCase):
    def test_pinned_signal_case(self):
        r = dp.disproportionality(25, 1000, 70, 9000)
        self.assertAlmostEqual(r.prr, 3.160, places=2)
        self.assertAlmostEqual(r.ror, 3.214, places=2)
        self.assertAlmostEqual(r.chi_squared, 25.70, places=1)
        self.assertTrue(r.signal)
        self.assertFalse(r.corrected)

    def test_ror_ci_formula(self):
        import math
        r = dp.disproportionality(25, 1000, 70, 9000)
        se = math.sqrt(1 / 25 + 1 / 1000 + 1 / 70 + 1 / 9000)
        self.assertAlmostEqual(r.ror_ci[0],
                               math.exp(math.log(r.ror) - 1.959963984540054 * se),
                               places=4)

    def test_caveat_present(self):
        r = dp.disproportionality(25, 1000, 70, 9000)
        self.assertIn("not", r.rationale.lower())
        self.assertIn("causation", r.rationale.lower())


class SignalCriterionTests(unittest.TestCase):
    def test_min_a_gate(self):
        # a = 2 < 3 → no signal even with a high PRR.
        r = dp.disproportionality(2, 10, 5, 9000)
        self.assertGreaterEqual(r.prr, 2.0)
        self.assertFalse(r.signal)
        self.assertIn("a = 2 < 3", r.rationale)

    def test_chi2_gate(self):
        # High PRR but χ² < 4 (sparse) → no signal.
        r = dp.disproportionality(1, 200, 5, 9000)
        self.assertLess(r.chi_squared, 4.0)
        self.assertFalse(r.signal)

    def test_prr_gate(self):
        # PRR < 2 → no signal even with a large χ².
        r = dp.disproportionality(50, 1000, 480, 9000)
        self.assertLess(r.prr, 2.0)
        self.assertFalse(r.signal)


class CorrectionTests(unittest.TestCase):
    def test_zero_cell_triggers_continuity_correction(self):
        r = dp.disproportionality(4, 50, 0, 9000)
        self.assertTrue(r.corrected)
        self.assertTrue(r.ror > 0)            # finite, thanks to +0.5
        self.assertIn("continuity correction", r.rationale)

    def test_no_correction_when_all_cells_positive(self):
        self.assertFalse(dp.disproportionality(5, 50, 5, 900).corrected)


class GuardTests(unittest.TestCase):
    def test_negative_cell_refuses(self):
        with self.assertRaises(dp.DisproportionalityError):
            dp.disproportionality(-1, 50, 5, 900)

    def test_zero_margin_refuses(self):
        with self.assertRaises(dp.DisproportionalityError):
            dp.disproportionality(0, 0, 5, 900)       # no reports on the drug


class ShapeTests(unittest.TestCase):
    def test_to_dict_deterministic(self):
        a = dp.disproportionality(25, 1000, 70, 9000).to_dict()
        b = dp.disproportionality(25, 1000, 70, 9000).to_dict()
        self.assertEqual(json.dumps(a, sort_keys=True),
                         json.dumps(b, sort_keys=True))
        self.assertEqual(a["table"]["a"], 25)
        self.assertTrue(a["signal"])

    def test_render(self):
        text = dp.render_disproportionality(
            dp.disproportionality(25, 1000, 70, 9000))
        self.assertIn("disproportionality", text.lower())
        self.assertIn("PRR", text)
        self.assertIn("ROR", text)


class CliTests(unittest.TestCase):
    def _run(self, args):
        from cannavec_science.__main__ import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(args)
        return code, buf.getvalue()

    def test_cli_markdown(self):
        code, out = self._run(["signal", "--drug-event", "25", "--drug-other",
                               "1000", "--other-event", "70", "--other-other",
                               "9000"])
        self.assertEqual(code, 0)
        self.assertIn("disproportionality", out.lower())
        self.assertIn("YES", out)

    def test_cli_json(self):
        code, out = self._run(["signal", "--drug-event", "25", "--drug-other",
                               "1000", "--other-event", "70", "--other-other",
                               "9000", "--json"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["signal"])

    def test_cli_bad_margin_nonzero(self):
        code, _ = self._run(["signal", "--drug-event", "0", "--drug-other", "0",
                             "--other-event", "5", "--other-other", "100"])
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
