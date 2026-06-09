"""Live-evidence weave (Constitution §IX).

The ``answer --augment-live`` surface attaches unverified live-discovery
hits to a brief. These tests pin the constitutional invariants of that
surface — provenance tagging, provisional grading, de-duplication, and
(critically) that a live finding NEVER changes the curated evidence grade
or auto-promotes into the knowledge base.
"""

import unittest

from cannavec_science.answer import (
    Answer,
    compose_answer,
    live_finding_from_row,
)


class TestAddLiveFinding(unittest.TestCase):

    def test_renders_clearly_tagged_section(self) -> None:
        a = Answer(prompt="CBD frontier")
        a.add_live_finding(
            label="CBD in refractory epilepsy",
            identifier="PMID 99999999",
            source_tag="live_pubmed",
            url="https://pubmed.ncbi.nlm.nih.gov/99999999/",
            year=2025,
        )
        md = a.to_markdown()
        self.assertIn("## Live discovery — provisional, not curated", md)
        self.assertIn("provenance-tagged", md)
        self.assertIn("never auto-promote", md)
        self.assertIn("[live_pubmed]", md)
        self.assertIn("PMID 99999999", md)
        self.assertIn("(2025)", md)

    def test_dedupes_by_identifier(self) -> None:
        a = Answer(prompt="x")
        a.add_live_finding(label="A", identifier="PMID 1", source_tag="live_pubmed")
        a.add_live_finding(label="A again", identifier="PMID 1", source_tag="live_pubmed")
        self.assertEqual(len(a.live_findings), 1)

    def test_to_dict_includes_live_findings(self) -> None:
        a = Answer(prompt="x")
        a.add_live_finding(label="t", identifier="NCT0001", source_tag="live_ctgov")
        d = a.to_dict()
        self.assertIn("live_findings", d)
        self.assertEqual(d["live_findings"][0]["identifier"], "NCT0001")
        self.assertEqual(d["live_findings"][0]["source_tag"], "live_ctgov")

    def test_live_finding_never_changes_curated_grade(self) -> None:
        # The curated answer's grade must be computed from curated claims
        # only; a provisional live finding cannot raise (or lower) it.
        a = compose_answer("CBD evidence in Dravet syndrome")
        before = a.evidence_summary.highest_grade
        a.add_live_finding(
            label="frontier preprint claiming a huge effect",
            identifier="PMID 7",
            source_tag="live_pubmed",
        )
        self.assertEqual(a.evidence_summary.highest_grade, before)
        md = a.to_markdown()
        # Provisional grade is shown as provisional — not as a curated Level.
        self.assertIn("provisional grade: provisional (live, unverified)", md)


class TestLiveFindingFromRow(unittest.TestCase):

    def test_pubmed_row_prefixes_pmid(self) -> None:
        f = live_finding_from_row(
            "pubmed", {"pmid": "12345678", "title": "CBD trial", "year": 2024}
        )
        assert f is not None
        self.assertEqual(f["identifier"], "PMID 12345678")
        self.assertEqual(f["source_tag"], "live_pubmed")
        self.assertEqual(f["label"], "CBD trial")
        self.assertEqual(f["year"], "2024")
        # spec 036 Step 2: an undesigned journal row (no journal, no pubtypes)
        # now carries a real, conservative metadata-only GRADE at the floor
        # (Level D / Very low), with a visible `live · provisional` qualifier —
        # never the old bare "provisional" string, never a curated A/B.
        self.assertEqual(f["grade"], "Level D")
        self.assertEqual(f["certainty"], "Very low")
        self.assertTrue(f["provisional"])
        self.assertIn("live · provisional", f["provisional_grade"])

    def test_preprint_lane_caps_at_level_d(self) -> None:
        f = live_finding_from_row(
            "biorxiv", {"doi": "10.1101/2024.01.01", "title": "preprint", "year": 2024}
        )
        assert f is not None
        self.assertEqual(f["source_tag"], "live_biorxiv")
        # A preprint caps at Level D (Very low) — the clamp is honest and visible.
        self.assertEqual(f["grade"], "Level D")
        self.assertEqual(f["certainty"], "Very low")
        self.assertIn("live · provisional", f["provisional_grade"])

    def test_row_without_identifier_is_dropped(self) -> None:
        # Nothing citable per §I → no finding.
        self.assertIsNone(live_finding_from_row("pubmed", {"title": "no id"}))


if __name__ == "__main__":
    unittest.main()
