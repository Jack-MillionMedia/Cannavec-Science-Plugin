"""Offline regression guard for known-bad curated citations.

The unit suite is offline (network calls use injected fetchers), so a
*well-formed-but-wrong* PMID — one that resolves to a real paper that is **not**
the paper the registry claims — passes every other test. The online check that
catches this class is ``evals/audit_pmids.py`` (it cross-checks each PMID's real
authors against the citation label via live NCBI). But that audit needs outbound
network to PubMed, which some execution environments block, so it cannot be the
*only* line of defence.

This test is the offline floor: a denylist of PMIDs that were positively
confirmed (against live PubMed) to point at the wrong paper and have since been
re-cited to the verified identifier. It asserts the bad identifiers never return
and the verified replacements stay in place. Add a row here whenever a
wrong-paper citation is fixed, so the exact regression can never ship twice.

Confirmed via PubMed cross-check on 2026-06-02:

  28815401  → 28782097   "Gaston 2017" rows actually pointed at Conti et al.,
                          "Abdominal infection reveals a rare disease" (Intern
                          Emerg Med 2017). Correct paper: Gaston TE et al.,
                          "Interactions between cannabidiol and commonly used
                          antiepileptic drugs," Epilepsia 2017. (Was propagated
                          to 8 citation sites across 4 registries.)
  19429692  → 19918051   "Long 2009 / JZL195" pointed at D'Ambrogio et al.,
                          TDP-43/hnRNP RNA biology. Correct: Long JZ et al.,
                          "Dual blockade of FAAH and MAGL...," PNAS 2009.
  25801039  → 25865737   cultivation "chemical phenotype" cite pointed at a
                          Wharton's-jelly umbilical-cord-cell paper. Correct:
                          Onofri C et al., Phytochemistry 2015.
  31867754  → 31469934   cultivation "flower maturation" cite pointed at a
                          helical-nanographene chemistry paper. Correct:
                          Livingston SJ et al., Plant J 2019/2020.
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
_PMID_RE = re.compile(r'pmid\s*=\s*["\'](\d{4,9})["\']')

# pmid that shipped wrong  ->  verified replacement it was corrected to.
_WRONG_TO_RIGHT = {
    "28815401": "28782097",
    "19429692": "19918051",
    "25801039": "25865737",
    "31867754": "31469934",
}


def _all_pmids() -> dict[str, list[str]]:
    """Map each PMID literal to the basenames of the modules that cite it."""
    out: dict[str, list[str]] = {}
    for path in sorted(glob.glob(os.path.join(_PKG, "*.py"))):
        text = open(path, encoding="utf-8").read()
        for pmid in set(_PMID_RE.findall(text)):
            out.setdefault(pmid, []).append(os.path.basename(path))
    return out


class CitationIntegrityGuard(unittest.TestCase):
    def setUp(self) -> None:
        self.pmids = _all_pmids()

    def test_known_bad_pmids_never_return(self) -> None:
        for bad, right in _WRONG_TO_RIGHT.items():
            where = self.pmids.get(bad)
            self.assertIsNone(
                where,
                msg=(
                    f"Known-wrong PMID {bad} reappeared in {where}; it points at "
                    f"the wrong paper and must be {right}. See this file's header."
                ),
            )

    def test_verified_replacements_present(self) -> None:
        # The corrected identifiers must stay in the tree, so a careless revert
        # of the fix is caught here rather than re-shipping the wrong paper.
        for right in _WRONG_TO_RIGHT.values():
            self.assertIn(
                right,
                self.pmids,
                msg=f"Verified replacement PMID {right} is missing from the registries.",
            )


if __name__ == "__main__":
    unittest.main()
