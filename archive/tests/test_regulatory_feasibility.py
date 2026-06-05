"""Tests for the regulatory-feasibility advisory module (spec 002 US6)."""

import unittest

from cannavec_science.regulatory_feasibility import (
    Jurisdiction,
    RegulatoryFeasibilityAdvisory,
    Schedule,
    WATERMARK,
    assess_feasibility,
    render_markdown,
)


class WatermarkTests(unittest.TestCase):
    """Every advisory MUST carry the watermark — non-negotiable per spec."""

    def test_watermark_on_us_thc(self):
        adv = assess_feasibility("Δ⁹-THC", "us")
        self.assertEqual(adv.watermark, WATERMARK)
        self.assertIn("not legal advice", adv.watermark)

    def test_watermark_on_every_jurisdiction(self):
        for j in ("us", "eu", "ca", "uk"):
            adv = assess_feasibility("CBD", j)
            self.assertEqual(adv.watermark, WATERMARK)

    def test_watermark_on_unknown_compound(self):
        adv = assess_feasibility("totally-made-up-cannabinoid-XYZ", "us")
        self.assertEqual(adv.watermark, WATERMARK)

    def test_watermark_on_unsupported_jurisdiction(self):
        adv = assess_feasibility("Δ⁹-THC", "antarctica")
        self.assertEqual(adv.watermark, WATERMARK)

    def test_render_watermark_on_line_one(self):
        adv = assess_feasibility("Δ⁹-THC", "us")
        md = render_markdown(adv)
        first_line = [ln for ln in md.split("\n") if ln.strip()][0]
        self.assertEqual(first_line, WATERMARK)


class USScheduleTests(unittest.TestCase):
    def test_delta_9_thc_schedule_i(self):
        adv = assess_feasibility("Δ⁹-THC", "us")
        self.assertEqual(adv.schedule, Schedule.SCHEDULE_I)
        self.assertIn("DEA Schedule I", adv.licensing_path)

    def test_delta_8_thc_gray_zone(self):
        adv = assess_feasibility("Δ⁸-THC", "us")
        self.assertEqual(adv.schedule, Schedule.GRAY_ZONE)
        self.assertGreater(len(adv.gray_zone_notes), 0)
        self.assertIn("AK Futures", str(adv.gray_zone_notes))

    def test_hhc_gray_zone(self):
        adv = assess_feasibility("HHC", "us")
        self.assertEqual(adv.schedule, Schedule.GRAY_ZONE)

    def test_thco_gray_zone(self):
        adv = assess_feasibility("THCO", "us")
        self.assertEqual(adv.schedule, Schedule.GRAY_ZONE)

    def test_thcp_gray_zone(self):
        adv = assess_feasibility("THCP", "us")
        self.assertEqual(adv.schedule, Schedule.GRAY_ZONE)

    def test_cbd_descheduled(self):
        adv = assess_feasibility("CBD", "us")
        self.assertEqual(adv.schedule, Schedule.DESCHEDULED)


class EUTests(unittest.TestCase):
    def test_thc_eu_schedule_i_member_state(self):
        adv = assess_feasibility("Δ⁹-THC", "eu")
        self.assertEqual(adv.schedule, Schedule.SCHEDULE_I)
        self.assertIn("Clinical Trial Application", adv.licensing_path)

    def test_hhc_eu_novel_food(self):
        adv = assess_feasibility("HHC", "eu")
        self.assertEqual(adv.schedule, Schedule.NOVEL_FOOD)
        self.assertGreater(len(adv.gray_zone_notes), 0)

    def test_cbd_eu_novel_food(self):
        adv = assess_feasibility("CBD", "eu")
        self.assertEqual(adv.schedule, Schedule.NOVEL_FOOD)


class CanadaTests(unittest.TestCase):
    def test_canada_uniform_schedule_ii(self):
        adv = assess_feasibility("Δ⁹-THC", "ca")
        self.assertEqual(adv.schedule, Schedule.SCHEDULE_II)
        self.assertIn("Health Canada", adv.licensing_path)
        self.assertIn("Cannabis Research Licence", adv.licensing_path)


class UKTests(unittest.TestCase):
    def test_thc_uk_schedule_i(self):
        adv = assess_feasibility("Δ⁹-THC", "uk")
        self.assertEqual(adv.schedule, Schedule.SCHEDULE_I)
        self.assertIn("Home Office", adv.licensing_path)

    def test_cbd_uk_uncontrolled(self):
        adv = assess_feasibility("CBD", "uk")
        self.assertEqual(adv.schedule, Schedule.UNCONTROLLED)


class UnsupportedJurisdictionTests(unittest.TestCase):
    def test_antarctica_unknown(self):
        adv = assess_feasibility("Δ⁹-THC", "antarctica")
        self.assertEqual(adv.schedule, Schedule.UNKNOWN)
        self.assertIn("not supported", adv.licensing_path.lower())

    def test_unknown_compound_returns_unknown(self):
        adv = assess_feasibility("totally-made-up-XYZ", "us")
        self.assertEqual(adv.schedule, Schedule.UNKNOWN)


class CompoundAliasTests(unittest.TestCase):
    def test_thc_alias_resolves_to_delta_9(self):
        adv = assess_feasibility("THC", "us")
        self.assertEqual(adv.schedule, Schedule.SCHEDULE_I)

    def test_dronabinol_resolves_to_delta_9(self):
        adv = assess_feasibility("dronabinol", "us")
        self.assertEqual(adv.schedule, Schedule.SCHEDULE_I)

    def test_cannabidiol_resolves_to_cbd(self):
        adv = assess_feasibility("cannabidiol", "us")
        self.assertEqual(adv.schedule, Schedule.DESCHEDULED)


class RendererTests(unittest.TestCase):
    def test_markdown_contains_jurisdiction_label(self):
        adv = assess_feasibility("Δ⁹-THC", "us")
        md = render_markdown(adv)
        self.assertIn("(US)", md)

    def test_markdown_contains_schedule(self):
        adv = assess_feasibility("Δ⁹-THC", "us")
        md = render_markdown(adv)
        self.assertIn("schedule_i", md.lower())

    def test_markdown_contains_sources(self):
        adv = assess_feasibility("Δ⁹-THC", "us")
        md = render_markdown(adv)
        self.assertIn("CFR", md)

    def test_to_dict_round_trip(self):
        adv = assess_feasibility("Δ⁹-THC", "us")
        d = adv.to_dict()
        self.assertEqual(d["compound"], "Δ⁹-THC")
        self.assertEqual(d["jurisdiction"], "us")
        self.assertEqual(d["schedule"], "schedule_i")


if __name__ == "__main__":
    unittest.main()
