"""Tests for Cheng-Prusoff binding-affinity conversion (spec 024)."""

import contextlib
import io
import json
import math
import unittest

from cannavec_science import binding as bd


class ChengPrusoffTests(unittest.TestCase):
    def test_pinned_ki(self):
        self.assertAlmostEqual(bd.cheng_prusoff(10, 1, 2), 6.6666667, places=5)

    def test_zero_ligand_gives_ic50(self):
        # No competing ligand → Ki == IC50.
        self.assertAlmostEqual(bd.cheng_prusoff(10, 0, 2), 10.0, places=9)

    def test_guards(self):
        for args in [(0, 1, 2), (10, 1, 0), (10, -1, 2)]:
            with self.assertRaises(bd.BindingError):
                bd.cheng_prusoff(*args)


class PScaleTests(unittest.TestCase):
    def test_p_affinity_nM(self):
        # 10 nM → 1e-8 M → pIC50 = 8.0
        self.assertAlmostEqual(bd.p_affinity(10, "nM"), 8.0, places=9)

    def test_round_trip(self):
        for unit in ("M", "mM", "uM", "nM", "pM"):
            p = bd.p_affinity(6.667, unit)
            self.assertAlmostEqual(bd.affinity_from_p(p, unit), 6.667, places=6)

    def test_unicode_micromolar(self):
        self.assertAlmostEqual(bd.p_affinity(1, "µM"), bd.p_affinity(1, "uM"),
                               places=12)

    def test_bad_unit(self):
        with self.assertRaises(bd.BindingError):
            bd.p_affinity(10, "molar")


class BindingAffinityTests(unittest.TestCase):
    def test_full_result(self):
        r = bd.binding_affinity(10, 1, 2, unit="nM")
        self.assertAlmostEqual(r.ki, 6.6666667, places=5)
        self.assertAlmostEqual(r.correction_factor, 1.5, places=9)
        self.assertAlmostEqual(r.p_ic50, 8.0, places=6)
        self.assertAlmostEqual(r.p_ki, 8.176, places=2)
        self.assertEqual(r.mode, "radioligand")

    def test_enzyme_mode_same_formula_different_label(self):
        rl = bd.binding_affinity(50, 2, 10, mode="radioligand")
        en = bd.binding_affinity(50, 2, 10, mode="enzyme")
        self.assertAlmostEqual(rl.ki, en.ki, places=9)        # same number
        self.assertIn("[S]/Km", en.rationale)                 # different label
        self.assertIn("[L]/Kd", rl.rationale)

    def test_units_shift_the_p_scale_not_the_ki(self):
        nm = bd.binding_affinity(10, 1, 2, unit="nM")
        um = bd.binding_affinity(10, 1, 2, unit="uM")
        self.assertAlmostEqual(nm.ki, um.ki, places=9)        # Ki unit-relative
        self.assertAlmostEqual(nm.p_ki - um.p_ki, 3.0, places=6)  # nM vs µM = 1000×

    def test_bad_mode(self):
        with self.assertRaises(bd.BindingError):
            bd.binding_affinity(10, 1, 2, mode="functional")


class ShapeTests(unittest.TestCase):
    def test_to_dict_deterministic(self):
        a = bd.binding_affinity(10, 1, 2).to_dict()
        b = bd.binding_affinity(10, 1, 2).to_dict()
        self.assertEqual(json.dumps(a, sort_keys=True),
                         json.dumps(b, sort_keys=True))
        self.assertEqual(a["unit"], "nM")

    def test_render(self):
        text = bd.render_binding(bd.binding_affinity(10, 1, 2))
        self.assertIn("Cheng-Prusoff", text)
        self.assertIn("pKi", text)
        self.assertIn("assay-independent", text)


class CliTests(unittest.TestCase):
    def _run(self, args):
        from cannavec_science.__main__ import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(args)
        return code, buf.getvalue()

    def test_cli_markdown(self):
        code, out = self._run(["affinity", "--ic50", "10", "--ligand", "1",
                               "--kd", "2"])
        self.assertEqual(code, 0)
        self.assertIn("Cheng-Prusoff", out)
        self.assertIn("6.667", out)

    def test_cli_json(self):
        code, out = self._run(["affinity", "--ic50", "10", "--ligand", "1",
                               "--kd", "2", "--json"])
        self.assertEqual(code, 0)
        self.assertAlmostEqual(json.loads(out)["ki"], 6.6666667, places=5)

    def test_cli_bad_input_nonzero(self):
        code, _ = self._run(["affinity", "--ic50", "0", "--ligand", "1",
                             "--kd", "2"])
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
