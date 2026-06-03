"""GRADE-consistency gates (Constitution §VII).

Two invariants an expert reviewer would check on sight:

1. **Single-study cap.** A per-study clinical/preclinical row anchored to a
   single primary study may not be graded Level A. §VII: "single primary
   studies cap at Level B; Level A requires a Cochrane/AHRQ/NICE systematic
   review or ≥2 independent high-quality RCTs in alignment." The
   *body-of-evidence* aggregate (``clinical_grade``) MAY be Level A — that is
   the whole point of the body-vs-study distinction — but no individual row
   may claim it.

2. **No internal contradiction on the flagship brief.** The CBD/Dravet brief
   must not show the same indication at two different grades (the v0.6 defect:
   headline "Level B" while the monograph row read "Level A").

These gates are pure-offline and deterministic (Constitution §III, §X).
"""

from __future__ import annotations

import unittest

from cannavec_science.major_cannabinoids import all_major_cannabinoids
from cannavec_science.minor_cannabinoids import (
    all_minor_cannabinoids,
    MinorCannabinoidEvidenceClass as Grade,
)
from cannavec_science.answer import compose_answer


# A design string that names a synthesis (≥2 studies pooled) — these rows are
# allowed to reach Level A because they are not single primary studies.
_AGGREGATE_MARKERS = (
    "systematic review", "meta-analysis", "meta analysis",
    "pooled", "network meta", "cochrane",
)


def _is_single_study(row) -> bool:
    design = (getattr(row, "design", "") or "").lower()
    if any(m in design for m in _AGGREGATE_MARKERS):
        return False
    # 0 or 1 primary citations → a single-study (or anecdotal) row.
    return len(getattr(row, "citations", ()) or ()) <= 1


class SingleStudyCapTests(unittest.TestCase):
    """§VII: a single primary study cannot be graded Level A."""

    def test_no_single_study_row_is_level_a(self) -> None:
        offenders = []
        registry = list(all_major_cannabinoids()) + list(all_minor_cannabinoids())
        for entry in registry:
            for row in getattr(entry, "clinical_evidence", ()) or ():
                if row.grade is Grade.A and _is_single_study(row):
                    offenders.append(
                        f"{entry.name}: clinical row '{row.indication}' is "
                        f"Level A on a single study ({row.design})"
                    )
            for row in getattr(entry, "preclinical_evidence", ()) or ():
                if getattr(row, "grade", None) is Grade.A and _is_single_study(row):
                    offenders.append(
                        f"{entry.name}: preclinical row "
                        f"'{row.indication_or_model}' is Level A on a single study"
                    )
        self.assertEqual(
            offenders, [],
            "§VII single-study cap violated:\n  " + "\n  ".join(offenders),
        )


class FlagshipBriefConsistencyTests(unittest.TestCase):
    """The CBD/Dravet brief must be internally grade-consistent."""

    def _brief(self):
        return compose_answer("CBD evidence in Dravet syndrome", retraction_policy="strict")

    def test_headline_claim_is_level_b(self) -> None:
        d = self._brief().to_dict()
        grades = {c.get("grade") for c in d.get("claims", [])}
        # The Dravet-specific claim rests on one pivotal RCT → Level B.
        self.assertIn("Level B", grades)
        self.assertNotIn("Level A", grades,
                         "Dravet claim must not be Level A (single pivotal RCT)")

    def test_no_per_study_row_renders_level_a(self) -> None:
        md = self._brief().to_markdown()
        # The aggregate header may say "body-of-evidence grade: Level A";
        # no per-study row line ("**Grade:** Level A") may.
        self.assertNotIn("**Grade:** Level A", md,
                         "a per-study monograph row still renders Level A")

    def test_body_of_evidence_label_present(self) -> None:
        md = self._brief().to_markdown()
        self.assertIn("body-of-evidence grade:", md,
                      "monograph clinical header must be labelled as the "
                      "aggregate, not a bare per-study grade")


if __name__ == "__main__":
    unittest.main()
