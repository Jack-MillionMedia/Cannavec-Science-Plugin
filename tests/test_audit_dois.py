"""Offline test for the Crossref DOI audit (evals/audit_dois.py)."""

from __future__ import annotations

import os
import sys
import unittest
import urllib.error

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "evals"))

import audit_dois  # noqa: E402


def _msg(family, title, year, journal):
    return {"author": [{"family": family}], "title": [title],
            "issued": {"date-parts": [[year]]}, "container-title": [journal]}

_TRUTH = {
    "10.1111/bcpt.13152": _msg("Damkier", "Interaction between warfarin and cannabis",
                               2018, "Basic Clin Pharmacol Toxicol"),
    # A real DOI that resolves to a DIFFERENT paper than the label claims.
    "10.9999/wrong": _msg("Pollock", "The critical role of clinical pharmacology in "
                          "geriatric psychopharmacology", 2008, "Clin Pharmacol Ther"),
    # Crossref lists the FIRST author (Arnold); the label cites a co-author (Adams).
    "10.1021/multi1942": {"author": [{"family": "Arnold"}, {"family": "Adams"}],
                          "title": ["Synthesis of hexahydrocannabinol"],
                          "issued": {"date-parts": [[1942]]},
                          "container-title": ["J Am Chem Soc"]},
}


def _resolver(doi):
    if doi == "10.0000/network":
        raise urllib.error.URLError("simulated network down")
    if doi == "10.0000/missing":
        return None                      # Crossref 404 — DOI not registered
    return _TRUTH.get(doi)


class DoiAuditLogic(unittest.TestCase):
    def _run(self, claims):
        return audit_dois.find_suspects(claims, resolve=_resolver)

    def test_correct_doi_passes(self) -> None:
        claims = {"10.1111/bcpt.13152": ("interactions.py",
                  "Damkier 2019 — warfarin–cannabis interaction (CBD/THC, INR case)")}
        suspects, inconclusive = self._run(claims)
        self.assertEqual(suspects, [])
        self.assertEqual(inconclusive, 0)

    def test_doi_resolving_to_wrong_paper_is_flagged(self) -> None:
        claims = {"10.9999/wrong": ("pharmacogenomics.py",
                  "Sachse-Seeboth 2009 — CYP2C9 polymorphism and THC pharmacokinetics")}
        suspects, _ = self._run(claims)
        self.assertEqual(len(suspects), 1)
        self.assertEqual(suspects[0][0], "10.9999/wrong")

    def test_unresolvable_doi_is_a_suspect(self) -> None:
        claims = {"10.0000/missing": ("x.py", "Some 2020 — paper")}
        suspects, inconclusive = self._run(claims)
        self.assertEqual(len(suspects), 1)
        self.assertIn("does not resolve", suspects[0][2])
        self.assertEqual(inconclusive, 0)

    def test_network_gap_is_inconclusive(self) -> None:
        claims = {"10.0000/network": ("x.py", "Some 2020 — paper")}
        suspects, inconclusive = self._run(claims)
        self.assertEqual(suspects, [])
        self.assertEqual(inconclusive, 1)

    def test_matches_a_non_first_author(self) -> None:
        # Label cites Adams (a co-author); Crossref lists Arnold first. Matching
        # ALL authors (like the PMID audit) must accept this, not flag it.
        claims = {"10.1021/multi1942": ("minor_cannabinoids.py",
                  "Adams R et al., J Am Chem Soc 1942, synthesis of HHC")}
        suspects, _ = self._run(claims)
        self.assertEqual(suspects, [])


class DoiCollection(unittest.TestCase):
    def test_collects_real_dois_and_skips_synthetic(self) -> None:
        claims = audit_dois.collect_dois()
        self.assertGreater(len(claims), 30)
        self.assertFalse(any(d.startswith("10.99999") for d in claims),
                         "synthetic seed DOI must be excluded")

    def test_multiline_concatenated_label_fully_captured(self) -> None:
        # The NASEM report's label spans several quoted segments; the title part
        # ("The Health Effects of Cannabis...") must be captured, not dropped
        # after the first segment (the bug that false-flagged it in live CI).
        claims = audit_dois.collect_dois()
        self.assertIn("10.17226/24625", claims)
        self.assertIn("health effects", claims["10.17226/24625"][1].lower())


if __name__ == "__main__":
    unittest.main()
