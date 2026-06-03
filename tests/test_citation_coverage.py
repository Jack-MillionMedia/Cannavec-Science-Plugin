"""Citation–compound coverage gate (Constitution §I).

The v0.6 audit found one review (Pertwee 2008, PMID 17828291 — which
characterises only Δ⁹-THC, CBD and Δ⁹-THCV) reused as a generic receptor
anchor on cannabinoids it never studied (CBN, CBG, Δ⁸-THC). §I forbids
anchoring a claim to a source that does not support it.

This gate encodes, for the receptor-pharmacology anchors we have explicitly
verified against PubMed, *which compounds each one actually covers*. Any
curated row that cites one of these anchors for a compound outside its
coverage set fails the build. Citations not in the map are ignored (we only
gate anchors whose coverage we have verified), so the gate is strict where it
knows and silent where it does not — no false positives.

Verified coverage (PubMed abstracts):
- 17828291 Pertwee 2008 — Δ⁹-THC, CBD, Δ⁹-THCV (the paper's three subjects).
- 28120231 Turner 2017 — THC, THCV, CBN, CBD, CBDV, CBG, CBC (the seven it reviews).
- 29977202 Navarro 2018 — CBG (CB1/CB2 + heteromers).
- 35523678 Tagen 2022 — Δ⁸-THC (comparative pharmacology with Δ⁹-THC).

Offline + deterministic (Constitution §III, §X).
"""

from __future__ import annotations

import unittest

from cannavec_science.major_cannabinoids import all_major_cannabinoids
from cannavec_science.minor_cannabinoids import all_minor_cannabinoids


# pmid -> set of canonical compound names (entry.name) the paper actually covers.
_COVERS: dict[str, set[str]] = {
    "17828291": {"THC", "CBD", "THCV"},                       # Pertwee 2008
    "28120231": {"THC", "THCV", "CBN", "CBD", "CBDV", "CBG", "CBC"},  # Turner 2017
    "29977202": {"CBG"},                                       # Navarro 2018
    "35523678": {"Δ⁸-THC"},                                    # Tagen 2022
    "16258853": {"CBD"},                                       # Russo 2005 (5-HT1A)
    "11606325": {"CBD"},                                       # Bisogno 2001 (TRPV1)
    "25363799": {"THCV"},                                      # Cascio 2015 (5-HT1A)
    "20002104": {"CBG"},                                       # Cascio 2010 (α2 / 5-HT1A)
}

# pmid -> set of receptor targets the paper actually characterises. Only
# single-target-class primaries are listed: a paper here may anchor a receptor
# row ONLY for a target in its set. This catches the subtler defect of a
# CB1/CB2 paper (Pertwee 2008, Navarro 2018) standing in for a 5-HT1A / TRPV1 /
# α2 row. Broad multi-target reviews are deliberately omitted.
_RECEPTOR_TARGET_COVERAGE: dict[str, set[str]] = {
    "17828291": {"CB1", "CB2"},                               # Pertwee 2008
    "29977202": {"CB1", "CB2"},                               # Navarro 2018
    "16258853": {"5-HT1A"},                                   # Russo 2005
    "11606325": {"TRPV1"},                                    # Bisogno 2001
    "25363799": {"5-HT1A"},                                   # Cascio 2015
    "20002104": {"α2-adrenoceptor", "5-HT1A"},               # Cascio 2010
}


def _all_citation_groups(entry):
    """Yield (context, citations-tuple) for every cited row on an entry."""
    for r in getattr(entry, "receptor_activity", ()) or ():
        yield f"receptor:{r.target}", getattr(r, "citations", ()) or ()
    for r in getattr(entry, "clinical_evidence", ()) or ():
        yield f"clinical:{r.indication}", getattr(r, "citations", ()) or ()
    for r in getattr(entry, "preclinical_evidence", ()) or ():
        yield f"preclinical:{r.indication_or_model}", getattr(r, "citations", ()) or ()
    yield "cross-cutting", getattr(entry, "citations", ()) or ()


class CitationCoverageTests(unittest.TestCase):
    def test_characterised_anchors_only_cite_compounds_they_cover(self) -> None:
        offenders = []
        registry = list(all_major_cannabinoids()) + list(all_minor_cannabinoids())
        for entry in registry:
            for context, cites in _all_citation_groups(entry):
                for c in cites:
                    pmid = getattr(c, "pmid", None)
                    if pmid in _COVERS and entry.name not in _COVERS[pmid]:
                        offenders.append(
                            f"{entry.name} [{context}] cites PMID {pmid}, "
                            f"which only covers {sorted(_COVERS[pmid])}"
                        )
        self.assertEqual(
            offenders, [],
            "§I citation–compound mismatch:\n  " + "\n  ".join(offenders),
        )

    def test_receptor_rows_cite_a_source_that_studied_that_target(self) -> None:
        """A characterised single-target primary may anchor a receptor row
        only for the target it actually studied (§I, receptor-target precision).
        Guards against a CB1/CB2 paper standing in for a 5-HT1A / TRPV1 / α2 row.
        """
        offenders = []
        registry = list(all_major_cannabinoids()) + list(all_minor_cannabinoids())
        for entry in registry:
            for r in getattr(entry, "receptor_activity", ()) or ():
                for c in getattr(r, "citations", ()) or ():
                    pmid = getattr(c, "pmid", None)
                    targets = _RECEPTOR_TARGET_COVERAGE.get(pmid)
                    if targets is not None and r.target not in targets:
                        offenders.append(
                            f"{entry.name} {r.target} cites PMID {pmid}, "
                            f"which only characterises {sorted(targets)}"
                        )
        self.assertEqual(
            offenders, [],
            "§I receptor-target mismatch:\n  " + "\n  ".join(offenders),
        )

    def test_pertwee_2008_never_anchors_an_uncovered_cannabinoid(self) -> None:
        """Direct guard for the exact v0.6 regression."""
        registry = list(all_major_cannabinoids()) + list(all_minor_cannabinoids())
        for entry in registry:
            for context, cites in _all_citation_groups(entry):
                pmids = {getattr(c, "pmid", None) for c in cites}
                if "17828291" in pmids:
                    self.assertIn(
                        entry.name, _COVERS["17828291"],
                        f"Pertwee 2008 re-attached to {entry.name} [{context}] "
                        "— it only characterises Δ⁹-THC, CBD, Δ⁹-THCV",
                    )


if __name__ == "__main__":
    unittest.main()
