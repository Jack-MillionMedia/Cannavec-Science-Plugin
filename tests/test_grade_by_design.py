"""GRADE certainty is derived from each citation's OWN study design (§VII).

Constitution §VII: "Single primary studies cap at Level B (pre-registered
powered RCT in major journal) or Level C (observational). Level A requires a
Cochrane/AHRQ/NICE systematic review or ≥ 2 independent high-quality RCTs in
alignment."

Before this battery, ``populations.to_claim`` stamped *every* citation with a
single tier derived from the curator's ``highest_grade_anchor`` and set
``pre_registered``/``adequately_powered`` uniformly. The visible defect:
Lennox-Gastaut syndrome (LGS) carried a second citation — Gaston 2017, an
open-label PK / drug-interaction study (PMID 28782097) — that was stamped a
flagship RCT and counted as a second confirmatory RCT, so LGS escaped the
single-RCT A→B cap and graded **Level A**, while Dravet and TSC — resting on
the *same* single NEJM pivotal RCT — graded **Level B**. Inversely, the three
real systematic reviews backing chronic neuropathic pain (Mücke Cochrane,
Stockings SR/MA, Whiting JAMA SR/MA) were stamped tier-2 JOURNAL_RCT instead of
tier-1 SR_FLAGSHIP.

These tests pin the fixed behaviour: each citation is tiered by its declared
``role`` (study design), the single-study cap is gated on *genuine confirmatory
RCTs or a real SR/MA* (not raw PMID count), and a non-RCT is never auto-stamped
``pre_registered + adequately_powered``.

Pure-offline and deterministic (Constitution §III, §X).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.evidence import (  # noqa: E402
    Claim,
    ClaimType,
    EvidenceLevel,
    Source,
    SourceTier,
)
from cannavec_science.populations import (  # noqa: E402
    PopulationCitation,
    all_populations,
)


def _by_label(label: str):
    for p in all_populations():
        if p.label == label:
            return p
    raise AssertionError(f"population {label!r} not found in registry")


def _supportable(label: str) -> EvidenceLevel:
    return _by_label(label).supportable_claim_grade()


def _sources_by_pmid(label: str) -> dict[str, Source]:
    claim = _by_label(label).to_claim()
    return {s.pmid: s for s in claim.sources if s.pmid}


# ── The headline defect: identical single-RCT evidence must grade identically ──


class SingleRctConsistencyTests(unittest.TestCase):
    """LGS, Dravet, and TSC all rest on a single pivotal NEJM RCT → all Level B."""

    def test_dravet_single_rct_grades_b(self) -> None:
        self.assertEqual(_supportable("paediatric Dravet syndrome"),
                         EvidenceLevel.B)

    def test_tsc_single_rct_grades_b(self) -> None:
        self.assertEqual(
            _supportable("paediatric tuberous sclerosis complex (TSC)"),
            EvidenceLevel.B,
        )

    def test_lgs_grades_same_as_dravet_and_tsc(self) -> None:
        # The regression: LGS used to grade Level A because Gaston 2017 (an
        # open-label PK study) was miscounted as a second confirmatory RCT.
        lgs = _supportable("paediatric Lennox-Gastaut syndrome")
        self.assertEqual(
            lgs, EvidenceLevel.B,
            "LGS rests on one pivotal RCT (Devinsky 2018) plus an open-label "
            "PK study (Gaston 2017); a single confirmatory RCT caps at Level B",
        )
        self.assertEqual(lgs, _supportable("paediatric Dravet syndrome"))
        self.assertEqual(
            lgs, _supportable("paediatric tuberous sclerosis complex (TSC)"))


# ── Per-citation tiering by declared role / study design ──────────────────────


class PerCitationTierTests(unittest.TestCase):
    """Each citation carries its true tier, derived from its own role."""

    def test_pivotal_rct_is_journal_rct_prereg_powered(self) -> None:
        s = _sources_by_pmid("paediatric Lennox-Gastaut syndrome")["29768152"]
        self.assertEqual(s.tier, SourceTier.JOURNAL_RCT)
        self.assertTrue(s.pre_registered)
        self.assertTrue(s.adequately_powered)

    def test_open_label_pk_study_is_lower_tier_not_an_rct(self) -> None:
        # Gaston 2017 — open-label PK / interaction study. Must NOT be a
        # flagship RCT and must NOT be auto-stamped pre-reg + powered.
        s = _sources_by_pmid("paediatric Lennox-Gastaut syndrome")["28782097"]
        self.assertEqual(s.tier, SourceTier.SINGLE_ARM_OR_MECH)
        self.assertFalse(
            s.pre_registered,
            "an open-label PK study must not be stamped pre_registered",
        )
        self.assertFalse(
            s.adequately_powered,
            "an open-label PK study must not be stamped adequately_powered",
        )

    def test_systematic_reviews_are_sr_flagship(self) -> None:
        # Mücke (Cochrane), Stockings (SR/MA), Whiting (JAMA SR/MA) all carry
        # role=systematic_review and must tier to SR_FLAGSHIP, not JOURNAL_RCT.
        srcs = _sources_by_pmid("adult chronic neuropathic pain")
        for pmid in ("29513392", "29847469", "26103030"):
            self.assertEqual(
                srcs[pmid].tier, SourceTier.SR_FLAGSHIP,
                f"systematic-review PMID {pmid} must tier to SR_FLAGSHIP",
            )

    def test_narrative_review_is_not_auto_stamped_rct(self) -> None:
        # MacCallum 2018 is a practical-prescribing narrative review, not a
        # pre-registered powered RCT. It must not be stamped as one.
        s = _sources_by_pmid("adult MS spasticity")["29307505"]
        self.assertFalse(s.pre_registered)
        self.assertFalse(s.adequately_powered)
        self.assertNotEqual(s.tier, SourceTier.SR_FLAGSHIP)


# ── The Level-A floor: SR/MA or ≥2 confirmatory RCTs ──────────────────────────


class LevelAFloorTests(unittest.TestCase):
    """Rows backed by a real SR/MA reach Level A; a single RCT cannot."""

    def test_sr_backed_pain_row_reaches_a(self) -> None:
        # Chronic neuropathic pain cites three SR/MA flagships → the body of
        # evidence supports Level A even though the curator anchored it at B.
        self.assertEqual(
            _supportable("adult chronic neuropathic pain"),
            EvidenceLevel.A,
            "a row backed by Cochrane + JAMA SR/MA must reach Level A",
        )

    def test_single_sr_flagship_floors_at_a(self) -> None:
        s = Source(title="Cochrane CBD epilepsy SR",
                   tier=SourceTier.SR_FLAGSHIP, doi="10.x/cochrane")
        c = Claim(text="t", claim_type=ClaimType.EDUCATIONAL, sources=(s,))
        self.assertEqual(c.best_supportable_grade(), EvidenceLevel.A,
                         "one genuine SR/MA flagship is a Level-A floor")

    def test_two_confirmatory_rcts_floor_at_a(self) -> None:
        rct = lambda p: Source(  # noqa: E731
            title="RCT", tier=SourceTier.JOURNAL_RCT, pmid=p,
            pre_registered=True, adequately_powered=True)
        c = Claim(text="t", claim_type=ClaimType.EDUCATIONAL,
                  sources=(rct("1"), rct("2")))
        self.assertEqual(c.best_supportable_grade(), EvidenceLevel.A,
                         "two aligned confirmatory RCTs are a Level-A floor")

    def test_one_rct_plus_a_non_rct_cocite_stays_b(self) -> None:
        # The defect mechanism: a single confirmatory RCT plus any second
        # PMID (here an open-label / mechanism cite) must NOT escape the
        # A→B cap. Only genuine confirmatory RCTs count.
        rct = Source(title="pivotal RCT", tier=SourceTier.JOURNAL_RCT,
                     pmid="1", pre_registered=True, adequately_powered=True)
        pk = Source(title="open-label PK", tier=SourceTier.SINGLE_ARM_OR_MECH,
                    pmid="2")
        c = Claim(text="t", claim_type=ClaimType.EDUCATIONAL,
                  sources=(rct, pk))
        self.assertEqual(c.best_supportable_grade(), EvidenceLevel.B,
                         "a non-RCT co-citation must not lift a single RCT to A")

    def test_one_rct_plus_a_bare_journal_rct_without_prereg_stays_b(self) -> None:
        # A second JOURNAL_RCT source that is NOT pre-registered + powered is
        # not a "genuine confirmatory RCT" and must not trip the Level-A floor.
        confirmatory = Source(title="pivotal RCT", tier=SourceTier.JOURNAL_RCT,
                              pmid="1", pre_registered=True,
                              adequately_powered=True)
        weak = Source(title="small open RCT", tier=SourceTier.JOURNAL_RCT,
                      pmid="2")
        c = Claim(text="t", claim_type=ClaimType.EDUCATIONAL,
                  sources=(confirmatory, weak))
        self.assertEqual(c.best_supportable_grade(), EvidenceLevel.B)


# ── Role-to-tier mapping is exhaustive and honest ─────────────────────────────


class RoleTierMappingTests(unittest.TestCase):
    """Tier each PopulationCitation role to the right SourceTier."""

    def _tier_for(self, role: str) -> SourceTier:
        from cannavec_science.populations import _tier_for_role
        return _tier_for_role(role)[0]

    def _prereg_for(self, role: str) -> bool:
        from cannavec_science.populations import _tier_for_role
        return _tier_for_role(role)[1]

    def test_systematic_review_maps_to_flagship(self) -> None:
        self.assertEqual(self._tier_for("systematic_review"),
                         SourceTier.SR_FLAGSHIP)
        self.assertEqual(self._tier_for("meta_analysis"),
                         SourceTier.SR_FLAGSHIP)

    def test_primary_rct_maps_to_journal_rct_prereg(self) -> None:
        self.assertEqual(self._tier_for("primary"), SourceTier.JOURNAL_RCT)
        self.assertTrue(self._prereg_for("primary"))

    def test_replication_rct_maps_to_journal_rct_prereg(self) -> None:
        self.assertEqual(self._tier_for("replication"), SourceTier.JOURNAL_RCT)
        self.assertTrue(self._prereg_for("replication"))

    def test_observational_roles_map_to_single_arm_no_prereg(self) -> None:
        for role in ("open_label", "pharmacokinetic", "observational",
                     "mechanism", "narrative_review"):
            self.assertEqual(self._tier_for(role),
                             SourceTier.SINGLE_ARM_OR_MECH,
                             f"role {role!r} should be SINGLE_ARM_OR_MECH")
            self.assertFalse(self._prereg_for(role),
                            f"role {role!r} must not be stamped pre-registered")

    def test_unknown_role_is_conservative_single_arm(self) -> None:
        # An unrecognised role must never be auto-promoted to a flagship RCT.
        self.assertEqual(self._tier_for("totally_unknown_role"),
                         SourceTier.SINGLE_ARM_OR_MECH)
        self.assertFalse(self._prereg_for("totally_unknown_role"))


# ── The curator anchor stays as informational metadata ────────────────────────


class CuratorAnchorPreservedTests(unittest.TestCase):
    """The deterministic grade may differ from the curator anchor — by design."""

    def test_anchor_field_unchanged(self) -> None:
        self.assertEqual(
            _by_label("paediatric Lennox-Gastaut syndrome").highest_grade_anchor,
            EvidenceLevel.A,
            "the curator anchor remains Level A as structured metadata",
        )

    def test_supportable_is_at_most_the_anchor_for_seizure_rows(self) -> None:
        # The honest deterministic grade for a single-RCT seizure row sits
        # one level below the Level-A curator anchor.
        for label in ("paediatric Dravet syndrome",
                      "paediatric Lennox-Gastaut syndrome",
                      "paediatric tuberous sclerosis complex (TSC)"):
            self.assertLess(
                _by_label(label).supportable_claim_grade().rank,
                _by_label(label).highest_grade_anchor.rank,
            )


if __name__ == "__main__":
    unittest.main()
