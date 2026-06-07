"""Cross-source convergence must work on PRODUCTION rows, not only behind the
``_compound``/``_condition`` test seam (critical-path #5a, §IX).

Root defect: ``synthesis._row_compound`` treated "CBD" and "cannabidiol" as
different cluster keys, and ``_row_condition`` did not recognise "Dravet", so
three genuinely-converging CBD/Dravet rows from real lanes clustered as three
singletons → ``WEAK`` instead of ``STRONG``. Only test fixtures injecting
``_compound``/``_condition`` reached ``STRONG``. The fix canonicalises the
compound (synonyms collapse) and the condition (reusing ``intent`` so the
epilepsy family — seizure / Dravet / LGS / TSC — clusters together) on the
heuristic path that production rows actually take.

Stdlib only, offline, deterministic.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.synthesis import Convergence, synthesize


class TestProductionConvergenceNoSeam(unittest.TestCase):
    """Real lane rows carry a title (and maybe abstract), never the
    ``_compound``/``_condition`` seam. Convergence must still resolve."""

    def test_three_cbd_epilepsy_sources_converge_strong(self):
        rows = {
            "pubmed": [{
                "pmid": "28538134",
                "title": "Cannabidiol in the Dravet syndrome",
                "abstract": "cannabidiol significantly reduced convulsive seizures",
            }],
            "ctgov": [{
                "nct_id": "NCT02091375",
                "title": "CBD for drug-resistant seizures in Dravet syndrome",
            }],
            "biorxiv": [{
                "doi": "10.1101/2020.05.01.000001",
                "title": "Cannabidiol reduces seizure frequency in an epilepsy model",
            }],
        }
        block = synthesize("CBD for Dravet syndrome", rows)
        self.assertEqual(
            block.convergence, Convergence.STRONG,
            f"3 converging CBD/epilepsy sources should be STRONG, got "
            f"{block.convergence}",
        )

    def test_two_synonym_sources_converge_mixed(self):
        # "Cannabidiol" (pubmed) + "CBD" (ctgov), same condition, 2 sources → MIXED.
        rows = {
            "pubmed": [{"pmid": "1", "title": "Cannabidiol for Lennox-Gastaut seizures"}],
            "ctgov": [{"nct_id": "NCT2", "title": "CBD in Lennox-Gastaut syndrome"}],
        }
        block = synthesize("CBD Lennox-Gastaut", rows)
        self.assertEqual(block.convergence, Convergence.MIXED)

    def test_distinct_subjects_do_not_manufacture_convergence(self):
        # Different compound AND condition → separate clusters, no false STRONG/MIXED.
        rows = {
            "pubmed": [{"pmid": "1", "title": "CBD for anxiety"}],
            "ctgov": [{"nct_id": "2", "title": "THC for chronic neuropathic pain"}],
            "biorxiv": [{"doi": "10.1/x", "title": "CBG antibacterial activity in vitro"}],
        }
        block = synthesize("cannabinoids", rows)
        self.assertNotEqual(block.convergence, Convergence.STRONG)
        self.assertNotEqual(block.convergence, Convergence.MIXED)

    def test_same_compound_different_condition_does_not_converge(self):
        # CBD for epilepsy vs CBD for anxiety — same compound, different condition.
        # Must NOT collapse into one cluster (no false agreement across indications).
        rows = {
            "pubmed": [{"pmid": "1", "title": "Cannabidiol for Dravet seizures"}],
            "ctgov": [{"nct_id": "2", "title": "CBD for generalized anxiety disorder"}],
        }
        block = synthesize("CBD", rows)
        self.assertNotEqual(block.convergence, Convergence.STRONG)
        self.assertNotEqual(block.convergence, Convergence.MIXED)


if __name__ == "__main__":
    unittest.main()
