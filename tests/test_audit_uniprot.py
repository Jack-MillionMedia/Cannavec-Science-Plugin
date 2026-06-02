"""Offline unit test for the UniProt accession audit (evals/audit_uniprot.py).

The audit itself needs the network (it resolves accessions against live
UniProt). This test injects a fake resolver so the *logic* — does a swapped or
wrong accession get flagged, does a correct one pass, is a network gap treated
as inconclusive rather than a failure — is verified with zero network, in the
normal offline suite.
"""

from __future__ import annotations

import os
import sys
import unittest
import urllib.error
from unittest import mock

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "evals"))

import audit_uniprot  # noqa: E402
from cannavec_science.uniprot_verify import UniProtRecord  # noqa: E402


def _rec(acc: str, gene: str, name: str) -> UniProtRecord:
    return UniProtRecord(
        accession=acc, protein_name=name, gene_symbol=gene,
        organism="Homo sapiens", organism_taxon_id=9606,
        sequence_length=None, reviewed=True, url="",
    )

# Truth table the fake resolver returns.
_TRUTH = {
    "P21554": _rec("P21554", "CNR1", "Cannabinoid receptor 1"),
    "P34972": _rec("P34972", "CNR2", "Cannabinoid receptor 2"),
}


def _fake_verify(acc, **kwargs):
    if acc == "Q9NETWORK":          # simulate a network gap
        raise urllib.error.URLError("simulated network down")
    if acc == "P99999":             # valid shape, no such entry
        return None
    return _TRUTH.get(acc)


class UniProtAuditLogic(unittest.TestCase):
    def _run(self, claims):
        with mock.patch.object(audit_uniprot, "verify_uniprot", _fake_verify):
            return audit_uniprot.find_suspects(claims)

    def test_correct_accession_passes(self) -> None:
        claims = {"P21554": ("evidence.py", 10,
                             "CB1 (UniProt P21554; HGNC CNR1) signalling")}
        suspects, inconclusive = self._run(claims)
        self.assertEqual(suspects, [])
        self.assertEqual(inconclusive, 0)

    def test_swapped_accession_is_flagged(self) -> None:
        # P34972 (really CNR2/CB2) pasted where the code claims CB1/CNR1.
        claims = {"P34972": ("evidence.py", 10,
                             "CB1 (UniProt P34972; HGNC CNR1) downstream signalling")}
        suspects, _ = self._run(claims)
        self.assertEqual(len(suspects), 1)
        self.assertEqual(suspects[0][0], "P34972")

    def test_passes_when_protein_name_matches_even_without_gene(self) -> None:
        claims = {"P21554": ("x.py", 1,
                             "the cannabinoid receptor (UniProt P21554) couples to Gi")}
        suspects, _ = self._run(claims)
        self.assertEqual(suspects, [])   # "cannabinoid receptor" carries the match

    def test_unknown_accession_is_a_suspect(self) -> None:
        claims = {"P99999": ("x.py", 1, "Foo target (UniProt P99999)")}
        suspects, inconclusive = self._run(claims)
        self.assertEqual(len(suspects), 1)
        self.assertIn("NOT FOUND", suspects[0][3])
        self.assertEqual(inconclusive, 0)

    def test_network_gap_is_inconclusive_not_a_suspect(self) -> None:
        claims = {"Q9NETWORK": ("x.py", 1, "Bar (UniProt Q9NETWORK)")}
        suspects, inconclusive = self._run(claims)
        self.assertEqual(suspects, [])
        self.assertEqual(inconclusive, 1)


class UniProtCollection(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.claims = audit_uniprot.collect_accessions()

    def test_real_receptor_accession_collected(self) -> None:
        self.assertIn("P21554", self.claims)   # CB1, cited in real prose

    def test_comment_example_accession_not_collected(self) -> None:
        # Q9NYW2 (TAS2R8) appears ONLY in the rigor_checks identifier-token
        # comment as a shape example; it is not a citation and must not be
        # audited (this was a live-CI false positive on 2026-06-02).
        self.assertNotIn("Q9NYW2", self.claims)


if __name__ == "__main__":
    unittest.main()
