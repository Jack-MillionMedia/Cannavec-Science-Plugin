"""Tests for the verified-tier breadth band woven into the blended brief (§IX).

Verifies the band renders distinctly, serializes only when populated (so no
existing pinned-JSON test moves), never re-grades the curated core, dedups, and
re-checks retraction at composition time (badging + pinning flagged rows last).
Offline and hermetic via a tmp store dir.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science import flywheel as fw  # noqa: E402
from cannavec_science.answer import compose_answer  # noqa: E402
from cannavec_science.ranker import Candidate  # noqa: E402

_ABS = ("In Crohn's disease, cannabidiol-rich cannabis induced clinical "
        "improvement versus placebo over 8 weeks.")
_CLAIM = ("In Crohn's disease, oral cannabidiol-rich cannabis induced clinical "
          "improvement versus placebo.")
_PROMPT = "Is cannabis effective for Crohn's disease?"


def _esummary(pmid: str) -> str:
    return json.dumps({"result": {"uids": [pmid], pmid: {
        "uid": pmid, "pubdate": "2021 Jan 1", "source": "X",
        "authors": [{"name": "A B"}], "title": "Crohn CBD RCT",
        "pubtype": ["Journal Article", "Randomized Controlled Trial"]}}})


class VerifiedBandTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _promote(self, ident="33858011", claim=_CLAIM, abstract=_ABS):
        c = Candidate(identifier=ident, title="Oral CBD-rich cannabis in Crohn's RCT",
                      abstract=abstract, study_types=("Randomized Controlled Trial",),
                      topic="ibd")
        g = fw.gate(c, claim_text=claim, abstract=abstract,
                    verify_fetcher=lambda u, _i=ident: _esummary(_i))
        fw.stage(c, g, store_dir=self.dir)
        res = fw.apply_promotion(ident, approver="curator@lab", store_dir=self.dir)
        self.assertTrue(res.ok, res.reason)

    def test_band_renders_and_serializes(self) -> None:
        self._promote()
        a = compose_answer(_PROMPT, verified=True, verified_store_dir=self.dir)
        self.assertEqual(len(a.verified_findings), 1)
        f = a.verified_findings[0]
        self.assertEqual(f["source_tag"], "verified")
        self.assertEqual(f["grade"], "Level C")
        self.assertEqual(f["approver"], "curator@lab")
        self.assertTrue(f["quote"])
        md = a.to_markdown()
        self.assertIn("## Verified breadth", md)
        self.assertIn("PMID 33858011", md)
        self.assertIn("verified_findings", a.to_dict())

    def test_curated_only_brief_is_unchanged(self) -> None:
        # Default (no verified weave): no band, and the key is absent from JSON.
        a = compose_answer(_PROMPT)
        self.assertEqual(a.verified_findings, [])
        self.assertNotIn("verified_findings", a.to_dict())
        self.assertNotIn("## Verified breadth", a.to_markdown())

    def test_verified_never_regrades_curated_core(self) -> None:
        base = compose_answer(_PROMPT)
        base_grade = base.evidence_summary.highest_grade
        self._promote()
        woven = compose_answer(_PROMPT, verified=True, verified_store_dir=self.dir)
        # Breadth augments; it never raises or lowers the curated grade.
        self.assertEqual(woven.evidence_summary.highest_grade, base_grade)
        self.assertEqual(len(woven.claims), len(base.claims))

    def test_weave_is_idempotent(self) -> None:
        self._promote()
        a = compose_answer(_PROMPT)
        self.assertEqual(fw.weave_verified_findings(a, prompt=_PROMPT, store_dir=self.dir), 1)
        # Second weave dedups by identifier — nothing added.
        self.assertEqual(fw.weave_verified_findings(a, prompt=_PROMPT, store_dir=self.dir), 0)
        self.assertEqual(len(a.verified_findings), 1)

    def test_no_topic_match_attaches_nothing(self) -> None:
        self._promote()  # an IBD verified row
        a = compose_answer("Δ⁹-THC pharmacokinetics and Tmax", verified=True,
                           verified_store_dir=self.dir)
        self.assertEqual(a.verified_findings, [])

    def test_retraction_rechecked_and_pinned_last(self) -> None:
        self._promote("33858011")
        self._promote("31054246",
                      claim="Cannabidiol reduced colonic permeability in vivo.",
                      abstract="Cannabidiol reduced colonic permeability in vivo and in vitro.")
        a = compose_answer(_PROMPT)

        def fake_is_retracted(*, pmid=None, doi=None):
            if pmid == "31054246":
                return mock.Mock(status=mock.Mock(value="retracted"))
            return None

        with mock.patch("cannavec_science.retraction.is_retracted",
                        side_effect=fake_is_retracted):
            fw.weave_verified_findings(a, topic="ibd", store_dir=self.dir)
        # Flagged row is badged and pinned last.
        self.assertEqual(len(a.verified_findings), 2)
        self.assertEqual(a.verified_findings[-1]["identifier"], "PMID 31054246")
        self.assertEqual(a.verified_findings[-1]["retraction_status"], "retracted")
        self.assertIn("⚠ RETRACTED", a.to_markdown())


if __name__ == "__main__":
    unittest.main()
