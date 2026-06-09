"""Tests for cannavec_science.europepmc_discover (spec 005 US6 / FR-007)."""

from __future__ import annotations

import json
import unittest
import urllib.parse

from cannavec_science.discover_guard import Provenance
from cannavec_science.intent import distill_query
from cannavec_science.europepmc_discover import (
    EuropePMCSearcher,
    LiveEuropePMCHit,
    SearchRefused,
    render_json,
    render_markdown,
    suggested_grade_for_pubtypes,
)


def _make_record(
    europe_pmc_id: str = "12345678",
    source: str = "MED",
    pmid: str = "12345678",
    doi: str = "10.1000/test",
    title: str = "Cannabis research test paper",
    author_string: str = "Smith J, Jones K, Brown L",
    pub_year: str = "2024",
    journal: str = "J Cannabis Res",
    pubtypes: list[str] | None = None,
    is_open_access: str = "Y",
) -> dict:
    return {
        "id": europe_pmc_id,
        "source": source,
        "pmid": pmid,
        "doi": doi,
        "title": title,
        "authorString": author_string,
        "pubYear": pub_year,
        "journalTitle": journal,
        "pubTypeList": {
            "pubType": pubtypes or ["Journal Article"],
        },
        "isOpenAccess": is_open_access,
    }


def _make_payload(records: list[dict], hit_count: int | None = None) -> str:
    return json.dumps({
        "hitCount": hit_count if hit_count is not None else len(records),
        "resultList": {
            "result": records,
        },
    })


def _stub_fetcher(payload: str):
    calls: list[str] = []

    def f(url: str) -> str:
        calls.append(url)
        return payload

    f.calls = calls
    return f


# ── Happy path ────────────────────────────────────────────────────────


class HappyPathTests(unittest.TestCase):
    def test_three_hits_returned(self):
        payload = _make_payload([
            _make_record("11111111", title="Paper 1"),
            _make_record("22222222", title="Paper 2"),
            _make_record("33333333", title="Paper 3"),
        ])
        s = EuropePMCSearcher(fetcher=_stub_fetcher(payload))
        hits = s.search("nabiximols European approval", max_results=5)
        self.assertEqual(len(hits), 3)
        self.assertEqual(hits[0].europe_pmc_id, "11111111")
        self.assertEqual(hits[1].title, "Paper 2")

    def test_provenance_tag(self):
        payload = _make_payload([_make_record()])
        s = EuropePMCSearcher(fetcher=_stub_fetcher(payload))
        hits = s.search("cannabis", max_results=1)
        self.assertEqual(hits[0].provenance, Provenance.LIVE_EUROPEPMC.value)
        self.assertEqual(hits[0].provenance, "live_europepmc")

    def test_first_author_extracted(self):
        payload = _make_payload([_make_record(author_string="Russo EB")])
        s = EuropePMCSearcher(fetcher=_stub_fetcher(payload))
        hits = s.search("cannabis", max_results=1)
        self.assertEqual(hits[0].first_author_surname, "Russo")

    def test_open_access_flag_parsed(self):
        payload = _make_payload([_make_record(is_open_access="Y")])
        s = EuropePMCSearcher(fetcher=_stub_fetcher(payload))
        hits = s.search("cannabis", max_results=1)
        self.assertTrue(hits[0].is_open_access)

    def test_closed_access_flag_parsed(self):
        payload = _make_payload([_make_record(is_open_access="N")])
        s = EuropePMCSearcher(fetcher=_stub_fetcher(payload))
        hits = s.search("cannabis", max_results=1)
        self.assertFalse(hits[0].is_open_access)

    def test_max_results_caps_returned_rows(self):
        records = [_make_record(str(i) * 8) for i in range(1, 6)]
        payload = _make_payload(records)
        s = EuropePMCSearcher(fetcher=_stub_fetcher(payload))
        hits = s.search("cannabis", max_results=2)
        self.assertEqual(len(hits), 2)


# ── URL building ──────────────────────────────────────────────────────


class UrlBuildingTests(unittest.TestCase):
    def test_url_carries_query_token(self):
        payload = _make_payload([])
        fetcher = _stub_fetcher(payload)
        s = EuropePMCSearcher(fetcher=fetcher)
        s.search("CBD epilepsy", max_results=3)
        self.assertEqual(len(fetcher.calls), 1)
        url = fetcher.calls[0]
        self.assertIn("query=", url)
        # URL-encoded "CBD"; %20 separator.
        self.assertTrue("CBD" in url or "cbd" in url.lower())

    def test_url_carries_page_size(self):
        payload = _make_payload([])
        fetcher = _stub_fetcher(payload)
        s = EuropePMCSearcher(fetcher=fetcher)
        s.search("CBD", max_results=7)
        # Over-fetch (3×, capped at the ceiling) so dropping conference
        # abstracts still fills the requested rows: 7 → 21.
        self.assertIn("pageSize=21", fetcher.calls[0])

    def test_distills_interrogative_query(self):
        # A natural-language question must reach Europe PMC as distilled content
        # terms, not the raw interrogative — filler words ("how/does/when")
        # dilute relevance and pull in broad reviews + conference dumps.
        fetcher = _stub_fetcher(_make_payload([]))
        s = EuropePMCSearcher(fetcher=fetcher)
        q = "How does THC impair motor coordination and balance?"
        distilled = distill_query(q)
        self.assertNotEqual(distilled, q, "precondition: distillation changes it")
        s.search(q, max_results=5)
        url = fetcher.calls[0]
        self.assertIn(urllib.parse.quote(distilled), url)

    def test_conference_abstracts_filtered(self):
        # Europe PMC pubType "Abstract" = poster/meeting dump, not citable
        # primary research. Drop it; over-fetch backfills the slot.
        payload = _make_payload([
            _make_record("11111111", title="Real PK study",
                         pubtypes=["research-article", "Journal Article"]),
            _make_record("22222222", title="ACNP Annual Meeting: Poster Abstracts",
                         pubtypes=["Abstract"]),
            _make_record("33333333", title="Meeting dump",
                         pubtypes=["abstract", "Journal Article"]),
            _make_record("44444444", title="Real review",
                         pubtypes=["review-article", "Review", "Journal Article"]),
        ])
        s = EuropePMCSearcher(fetcher=_stub_fetcher(payload))
        hits = s.search("thc motor coordination", max_results=8)
        ids = [h.europe_pmc_id for h in hits]
        self.assertEqual(ids, ["11111111", "44444444"],
                         "only real research/review records survive")

    def test_since_date_appended(self):
        payload = _make_payload([])
        fetcher = _stub_fetcher(payload)
        s = EuropePMCSearcher(fetcher=fetcher)
        s.search("CBD", since="2024-01-01")
        url = fetcher.calls[0]
        self.assertIn("FIRST_PDATE", url)

    def test_open_access_filter(self):
        payload = _make_payload([])
        fetcher = _stub_fetcher(payload)
        s = EuropePMCSearcher(fetcher=fetcher)
        s.search("CBD", open_access_only=True)
        url = fetcher.calls[0]
        self.assertIn("OPEN_ACCESS", url)

    def test_url_omits_sort_param(self):
        # Regression: a `sort=` token (e.g. the legacy `FIRST_PDATE desc`) is
        # silently REJECTED by the current Europe PMC REST API — it returns a
        # degenerate `{"version": ...}` body with no resultList, so every query
        # returned zero hits and the lane was dead. We rely on the default
        # RELEVANCE ranking and pass no sort param; assert it stays out of the
        # URL so the lane cannot regress to the silent-failure mode.
        fetcher = _stub_fetcher(_make_payload([]))
        EuropePMCSearcher(fetcher=fetcher).search("CBD", max_results=3)
        self.assertNotIn("sort=", fetcher.calls[0])


# ── Edge cases / error paths ──────────────────────────────────────────


class ErrorPathTests(unittest.TestCase):
    def test_empty_query_raises(self):
        s = EuropePMCSearcher(fetcher=_stub_fetcher("{}"))
        with self.assertRaises(ValueError):
            s.search("", max_results=3)

    def test_invalid_since_raises(self):
        s = EuropePMCSearcher(fetcher=_stub_fetcher("{}"))
        with self.assertRaises(ValueError):
            s.search("CBD", since="not-a-date")

    def test_degenerate_version_only_payload_returns_empty(self):
        # The EXACT real-world failure mode that killed the lane: Europe PMC
        # returns `{"version": "6.9"}` (well-formed JSON, but no resultList and
        # no hitCount) for a malformed request. The lane must degrade to zero
        # hits gracefully, never raise.
        s = EuropePMCSearcher(fetcher=_stub_fetcher('{"version": "6.9"}'))
        self.assertEqual(s.search("CBD", max_results=3), ())

    def test_unparseable_json_returns_empty(self):
        s = EuropePMCSearcher(fetcher=_stub_fetcher("not json {{{"))
        hits = s.search("CBD")
        self.assertEqual(hits, ())

    def test_empty_payload_returns_empty(self):
        s = EuropePMCSearcher(fetcher=_stub_fetcher(_make_payload([])))
        hits = s.search("CBD")
        self.assertEqual(hits, ())

    def test_safety_preflight_blocks_dosing_question(self):
        # A safety-refused prompt must NOT touch the network.
        fetcher = _stub_fetcher("{}")
        s = EuropePMCSearcher(fetcher=fetcher)
        # An individualised-dosing prompt should be refused upstream.
        with self.assertRaises(SearchRefused):
            s.search("how much CBD should I take for my anxiety")
        self.assertEqual(len(fetcher.calls), 0)


# ── Suggested grade ───────────────────────────────────────────────────


class SuggestedGradeTests(unittest.TestCase):
    def test_meta_analysis_to_level_a(self):
        self.assertEqual(
            suggested_grade_for_pubtypes(("Meta-Analysis",)),
            "Level A (provisional)",
        )

    def test_systematic_review_to_level_a(self):
        self.assertEqual(
            suggested_grade_for_pubtypes(("Systematic Review",)),
            "Level A (provisional)",
        )

    def test_rct_to_level_b(self):
        self.assertEqual(
            suggested_grade_for_pubtypes(("Randomized Controlled Trial",)),
            "Level B (provisional)",
        )

    def test_clinical_trial_to_level_c(self):
        self.assertEqual(
            suggested_grade_for_pubtypes(("Clinical Trial",)),
            "Level C (provisional)",
        )

    def test_case_report_to_level_d(self):
        self.assertEqual(
            suggested_grade_for_pubtypes(("Case Reports",)),
            "Level D (provisional)",
        )

    def test_preprint_to_level_d(self):
        self.assertEqual(
            suggested_grade_for_pubtypes(("Preprint",)),
            "Level D (provisional)",
        )

    def test_journal_article_floors_to_level_d(self):
        # A real primary article of unverified design is admissible-but-unranked
        # evidence (Level D provisional), NOT "Unsupported" / no-evidence. This
        # also matches the OpenAlex lane, which already floors journal-article.
        self.assertEqual(
            suggested_grade_for_pubtypes(("Journal Article",)),
            "Level D (provisional)",
        )

    def test_research_article_token_floors_to_level_d(self):
        # The lowercase EuropePMC token seen on recent live records.
        self.assertEqual(
            suggested_grade_for_pubtypes(("research-article", "Journal Article")),
            "Level D (provisional)",
        )

    def test_empty_pubtypes_stays_unsupported(self):
        # Genuinely empty / design-signal-free metadata is the ONLY remaining
        # Unsupported case.
        self.assertEqual(
            suggested_grade_for_pubtypes(()),
            "Unsupported (provisional)",
        )

    def test_non_evidence_types_with_journal_article_stay_unsupported(self):
        # Corrections / letters / news frequently co-carry "Journal Article" but
        # are NOT admissible primary evidence — the floor must not over-grade
        # them to Level D.
        for pt in ("Published Erratum", "Retraction of Publication",
                   "Comment", "Editorial"):
            self.assertEqual(
                suggested_grade_for_pubtypes((pt, "Journal Article")),
                "Unsupported (provisional)",
                f"{pt!r} co-carrying Journal Article must stay Unsupported",
            )

    def test_newspaper_article_not_floored(self):
        self.assertEqual(
            suggested_grade_for_pubtypes(("Newspaper Article",)),
            "Unsupported (provisional)",
        )


# ── Renderers ─────────────────────────────────────────────────────────


class RenderMarkdownTests(unittest.TestCase):
    def test_renders_section_header(self):
        hits = (
            LiveEuropePMCHit(
                europe_pmc_id="12345678",
                source="MED",
                pmid="12345678",
                doi="10.1000/x",
                title="Test",
                first_author_surname="Smith",
                year=2024,
                journal="J Test",
                pubtypes=("Randomized Controlled Trial",),
                is_open_access=True,
                suggested_grade="Level B (provisional)",
            ),
        )
        md = render_markdown("cannabis", hits)
        self.assertIn("Live Europe PMC search — cannabis", md)
        self.assertIn("12345678", md)

    def test_no_hits_message(self):
        md = render_markdown("cannabis", ())
        self.assertIn("No hits returned by Europe PMC", md)


class RenderJsonTests(unittest.TestCase):
    def test_json_round_trip(self):
        hits = (
            LiveEuropePMCHit(
                europe_pmc_id="42424242",
                source="PMC",
                pmid="42424242",
                doi="10.1/y",
                title="Test",
                first_author_surname="Russo",
                year=2024,
                journal="J Test",
                pubtypes=("Journal Article",),
                is_open_access=False,
                suggested_grade="Level D (provisional)",
            ),
        )
        out = render_json("cannabis", hits)
        payload = json.loads(out)
        self.assertEqual(payload["query"], "cannabis")
        self.assertEqual(payload["provenance"], "live_europepmc")
        self.assertEqual(len(payload["hits"]), 1)
        self.assertEqual(payload["hits"][0]["pmid"], "42424242")


if __name__ == "__main__":
    unittest.main()
