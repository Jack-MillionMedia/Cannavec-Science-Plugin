"""Offline guard for the core UniProt receptor/enzyme accessions (§VI).

The online audit (evals/audit_uniprot.py) resolves *every* accession against
live UniProt in CI. This is the zero-network floor that runs in the normal
suite: it pins the load-bearing cannabinoid-system targets to their correct
gene symbol and fails fast if an accession is ever paired with the *wrong*
gene (e.g. CB1's accession next to "CNR2") — the protein-world equivalent of a
swapped citation.

The anchor map below is the set of targets verified with high confidence and
re-checked against live UniProt by the online audit; the offline guard only
asserts the code never contradicts it.
"""

from __future__ import annotations

import glob
import os
import re
import unittest

_PKG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "cannavec_science",
)

# accession -> canonical HGNC gene symbol (cannabinoid-system core targets).
_ANCHORS = {
    "P21554": "CNR1",    # CB1
    "P34972": "CNR2",    # CB2
    "Q8NER1": "TRPV1",
    "P37231": "PPARG",   # PPARγ
    "O00519": "FAAH",
    "Q99685": "MGLL",    # MAGL
    "P08908": "HTR1A",   # 5-HT1A
    "Q9Y2T6": "GPR55",
    "P35354": "PTGS2",   # COX-2
    "P35372": "OPRM1",   # µ-opioid
}
_ALL_GENES = {g.lower() for g in _ANCHORS.values()}


def _source() -> str:
    return "".join(
        open(p, encoding="utf-8").read()
        for p in glob.glob(os.path.join(_PKG, "*.py"))
    )


class UniProtAnchorIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.src = _source()
        cls.src_lower = cls.src.lower()

    def test_anchor_accessions_present(self) -> None:
        # These receptor/enzyme ids are load-bearing (§VI); their absence would
        # mean a registry stopped naming its target by accession.
        missing = [acc for acc in _ANCHORS if acc not in self.src]
        self.assertEqual(missing, [], f"core accessions absent from registries: {missing}")

    def test_no_accession_paired_with_wrong_gene(self) -> None:
        # The code's explicit gene assignment is "<ACC>; HGNC <GENE>". That
        # pairing is unambiguous, so a swap there (e.g. "P21554; HGNC CNR2") is a
        # real defect. Only this tight pattern is checked — receptor *lists*
        # like "CB1=P21554, TRPV1=Q8NER1" are not pairings and must not flag.
        # (The online audit resolves every accession; this is the swap floor.)
        violations = []
        for acc, gene in _ANCHORS.items():
            for m in re.finditer(
                re.escape(acc) + r"\s*;\s*HGNC\s+([A-Za-z0-9]+)", self.src
            ):
                if m.group(1).upper() != gene:
                    violations.append((acc, f"HGNC {m.group(1)}", f"expected {gene}"))
        self.assertEqual(
            violations, [],
            f"accession paired with the wrong HGNC gene (swap): {violations[:5]}",
        )


if __name__ == "__main__":
    unittest.main()
