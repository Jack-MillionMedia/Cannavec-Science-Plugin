"""Tests for the endocannabinoidome (eCBome) reference module (spec 002 US6)."""

import unittest

from cannavec_science.ecbome import (
    EcbomeEntry,
    EcbomeRole,
    all_ecbome_entries,
    detect_ecbome_mention,
    ecbome_for_compound,
    find_ecbome_entries,
    render_markdown,
)


class RegistryShapeTests(unittest.TestCase):
    def test_at_least_28_entries(self):
        entries = all_ecbome_entries()
        self.assertGreaterEqual(len(entries), 28)

    def test_every_entry_has_primary_identifier(self):
        for e in all_ecbome_entries():
            self.assertTrue(
                e.uniprot_id or e.hmdb_id,
                f"{e.name} missing both UniProt and HMDB ID",
            )

    def test_every_entry_has_summary(self):
        for e in all_ecbome_entries():
            self.assertTrue(e.summary, f"{e.name} missing summary")

    def test_role_distribution_covers_all_four(self):
        roles = {e.role for e in all_ecbome_entries()}
        for r in (EcbomeRole.MEDIATOR, EcbomeRole.RECEPTOR,
                  EcbomeRole.ENZYME, EcbomeRole.TRANSPORTER):
            self.assertIn(r, roles)


class IdentifierResolutionTests(unittest.TestCase):
    def test_cb1_uniprot(self):
        hits = find_ecbome_entries("CB1")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].uniprot_id, "P21554")

    def test_cb2_uniprot(self):
        hits = find_ecbome_entries("CB2")
        self.assertEqual(hits[0].uniprot_id, "P34972")

    def test_trpv1_uniprot(self):
        hits = find_ecbome_entries("TRPV1")
        self.assertEqual(hits[0].uniprot_id, "Q8NER1")

    def test_pparg_uniprot(self):
        hits = find_ecbome_entries("PPARγ")
        self.assertEqual(hits[0].uniprot_id, "P37231")

    def test_magl_uniprot(self):
        hits = find_ecbome_entries("MAGL")
        self.assertEqual(hits[0].uniprot_id, "Q99685")

    def test_dagla_uniprot(self):
        hits = find_ecbome_entries("DAGLα")
        self.assertEqual(hits[0].uniprot_id, "Q9Y4D2")

    def test_faah_uniprot(self):
        hits = find_ecbome_entries("FAAH")
        self.assertEqual(hits[0].uniprot_id, "O00519")

    def test_aea_hmdb(self):
        hits = find_ecbome_entries("anandamide")
        self.assertTrue(hits[0].hmdb_id.startswith("HMDB"))


class AliasResolutionTests(unittest.TestCase):
    def test_cnr1_resolves_to_cb1(self):
        hits = find_ecbome_entries("CNR1")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].name, "CB1")

    def test_2ag_alias(self):
        hits = find_ecbome_entries("2-AG")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].name, "2-arachidonoylglycerol")


class CompoundBindingTests(unittest.TestCase):
    def test_anandamide_engages_multiple_receptors(self):
        binders = ecbome_for_compound("anandamide")
        names = {e.name for e in binders}
        for receptor in ("CB1", "CB2", "TRPV1"):
            self.assertIn(receptor, names)

    def test_2ag_engages_cb1_cb2(self):
        binders = ecbome_for_compound("2-AG")
        names = {e.name for e in binders}
        self.assertIn("CB1", names)
        self.assertIn("CB2", names)


class DetectionTests(unittest.TestCase):
    def test_detect_mentions_in_prose(self):
        entries = detect_ecbome_mention(
            "FAAH and MAGL are the principal hydrolytic enzymes of "
            "anandamide and 2-AG respectively."
        )
        names = {e.name for e in entries}
        for needle in ("FAAH", "MAGL", "anandamide"):
            self.assertIn(needle, names)

    def test_no_mention_returns_empty(self):
        self.assertEqual(detect_ecbome_mention(""), ())
        self.assertEqual(detect_ecbome_mention("not related to cannabinoids"), ())


class ValidationTests(unittest.TestCase):
    def test_entry_without_identifier_raises(self):
        with self.assertRaises(ValueError):
            EcbomeEntry(
                name="bogus", role=EcbomeRole.RECEPTOR,
                # no uniprot_id, no hmdb_id
            )


class RendererTests(unittest.TestCase):
    def test_markdown_includes_four_role_buckets(self):
        md = render_markdown(all_ecbome_entries())
        for role_label in ("Mediator", "Receptor", "Enzyme", "Transporter"):
            self.assertIn(role_label, md)

    def test_markdown_lists_uniprot(self):
        md = render_markdown(find_ecbome_entries("CB1"))
        self.assertIn("UniProt P21554", md)

    def test_markdown_empty_input_returns_empty(self):
        self.assertEqual(render_markdown(()), "")


class FreshnessFieldTests(unittest.TestCase):
    def test_entries_carry_last_verified_default(self):
        for e in all_ecbome_entries():
            self.assertTrue(e.last_verified)

    def test_entries_extract_watch_pmids_from_citations(self):
        # Mediator entries cite the canonical papers.
        aea = find_ecbome_entries("anandamide")[0]
        self.assertGreater(len(aea.watch_pmids), 0)


if __name__ == "__main__":
    unittest.main()
