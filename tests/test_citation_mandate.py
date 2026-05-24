"""Opt-in citation-mandate refusal tests (Plan R5).

Constitution §I (Primary-Source-Or-Refuse) requires every claim to cite
a primary source. The pre-existing constructor checks on Source and
Citation enforce this at object-construction time. The new
``Answer(strict_citation_mandate=True)`` flag adds a compose-time
refusal so a sourceless claim raises
:class:`CitationMissingError` rather than landing as a quiet UNSUPPORTED
row in the brief.

Default behaviour is unchanged (flag defaults to False) so the
existing test suite is not perturbed.
"""

from __future__ import annotations

import unittest

from cannavec_science.answer import Answer
from cannavec_science.evidence import (
    CitationMissingError,
    Claim,
    ClaimType,
    Source,
    SourceTier,
)


def _sourced_claim() -> Claim:
    """A claim that carries a valid primary source."""
    src = Source(
        title="Devinsky et al. (2017) Cannabidiol in Dravet syndrome.",
        pmid="28538134",
        year=2017,
        tier=SourceTier.JOURNAL_RCT,
    )
    return Claim(
        text="Cannabidiol reduces convulsive-seizure frequency in Dravet syndrome.",
        claim_type=ClaimType.CLINICAL_EFFICACY,
        sources=(src,),
    )


def _sourceless_clinical_claim() -> Claim:
    return Claim(
        text="Cannabidiol cures Dravet syndrome.",
        claim_type=ClaimType.CLINICAL_EFFICACY,
        sources=(),
    )


def _sourceless_educational_claim() -> Claim:
    return Claim(
        text="Cannabidiol is one of over 100 phytocannabinoids in C. sativa.",
        claim_type=ClaimType.EDUCATIONAL,
        sources=(),
    )


class CitationMandateDefaultOffTests(unittest.TestCase):
    """Default behaviour MUST be unchanged — sourceless claim is accepted."""

    def test_default_accepts_sourceless_clinical_claim(self):
        a = Answer(prompt="x")
        # The wording guard would normally fire on "cures" — disable
        # it so we isolate the citation-mandate behaviour.
        a.strict_wording = False
        a.add_claim(_sourceless_clinical_claim())
        self.assertEqual(len(a.claims), 1)


class CitationMandateStrictRefusalTests(unittest.TestCase):
    def test_strict_refuses_sourceless_clinical_claim(self):
        a = Answer(prompt="x", strict_citation_mandate=True)
        a.strict_wording = False  # isolate the mandate path
        with self.assertRaises(CitationMissingError) as ctx:
            a.add_claim(_sourceless_clinical_claim())
        msg = str(ctx.exception)
        self.assertIn("clinical_efficacy", msg)
        self.assertIn("primary source", msg)

    def test_strict_accepts_sourced_claim(self):
        a = Answer(prompt="x", strict_citation_mandate=True)
        a.add_claim(_sourced_claim())
        self.assertEqual(len(a.claims), 1)
        # Source rolled into citations as usual.
        self.assertEqual(len(a.citations), 1)
        self.assertEqual(a.citations[0].pmid, "28538134")

    def test_strict_exempts_educational_sourceless_claim(self):
        # EDUCATIONAL claims are the composer-built "Notes" surface and
        # are explicitly exempted (see Answer.add_claim).
        a = Answer(prompt="x", strict_citation_mandate=True)
        a.add_claim(_sourceless_educational_claim())
        self.assertEqual(len(a.claims), 1)


if __name__ == "__main__":
    unittest.main()
