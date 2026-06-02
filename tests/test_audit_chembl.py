"""Offline test for the ChEMBL id audit (evals/audit_chembl.py)."""

from __future__ import annotations

import os
import sys
import unittest
import urllib.error

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "evals"))

import audit_chembl  # noqa: E402

_TRUTH = {
    "CHEMBL1651534": {"pref_name": "REDAFAMDASTAT",
                      "molecule_synonyms": [{"molecule_synonym": "PF-04457845"},
                                            {"molecule_synonym": "Redafamdastat"}]},
    # The wrong-compound case that was fixed: this id is really Eganoprost.
    "CHEMBL3989775": {"pref_name": "EGANOPROST",
                      "molecule_synonyms": [{"molecule_synonym": "Eganoprost"}]},
}


def _resolver(cid):
    if cid == "CHEMBL0000NET":
        raise urllib.error.URLError("simulated network down")
    if cid == "CHEMBL0000404":
        return None
    return _TRUTH.get(cid)


class ChemblAuditLogic(unittest.TestCase):
    def _run(self, claims):
        return audit_chembl.find_suspects(claims, resolve=_resolver)

    def test_correct_id_passes(self) -> None:
        claims = {"CHEMBL1651534": ("ecbome_inhibitors.py", "PF-04457845")}
        suspects, inconclusive = self._run(claims)
        self.assertEqual(suspects, [])
        self.assertEqual(inconclusive, 0)

    def test_id_resolving_to_wrong_compound_is_flagged(self) -> None:
        # id really = Eganoprost, but the cite claims BIA 10-2474.
        claims = {"CHEMBL3989775": ("ecbome_inhibitors.py", "BIA 10-2474")}
        suspects, _ = self._run(claims)
        self.assertEqual(len(suspects), 1)
        self.assertIn("eganoprost", suspects[0][2].lower())

    def test_unresolvable_id_is_a_suspect(self) -> None:
        claims = {"CHEMBL0000404": ("x.py", "Foo compound")}
        suspects, inconclusive = self._run(claims)
        self.assertEqual(len(suspects), 1)
        self.assertIn("does not resolve", suspects[0][2])
        self.assertEqual(inconclusive, 0)

    def test_network_gap_is_inconclusive(self) -> None:
        claims = {"CHEMBL0000NET": ("x.py", "Foo compound")}
        suspects, inconclusive = self._run(claims)
        self.assertEqual(suspects, [])
        self.assertEqual(inconclusive, 1)


class ChemblCollection(unittest.TestCase):
    def test_collects_citation_ids_not_comment_examples(self) -> None:
        claims = audit_chembl.collect_chembl()
        # the two real citation ids are present...
        self.assertIn("CHEMBL1651534", claims)
        self.assertIn("CHEMBL3945728", claims)
        # ...and the comment example (CHEMBL218 in rigor_checks) is NOT a citation.
        self.assertNotIn("CHEMBL218", claims)


if __name__ == "__main__":
    unittest.main()
