"""Tests for cannavec.pubmed_search — live PubMed discovery.

cannabis-insight-engine spec 001 User Story 1.

All tests use injected fetcher fixtures so the suite runs offline.
The network-enabled production path is exercised in
``evals/canonical_questions_holdout.yaml`` (continue-on-error).
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.pubmed_search import (  # noqa: E402
    LivePubMedHit,
    PubMedSearcher,
    SearchRefused,
    _parse_efetch_xml,
    render_markdown,
    render_json,
    suggested_grade_for_pubtypes,
)


_EFETCH_XML = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle><MedlineCitation><PMID>111</PMID>
    <Article><Abstract><AbstractText>Cannabidiol reduced gut permeability in human patients.</AbstractText></Abstract>
    <PublicationTypeList><PublicationType>Randomized Controlled Trial</PublicationType></PublicationTypeList></Article>
    <MeshHeadingList><MeshHeading><DescriptorName>Humans</DescriptorName></MeshHeading></MeshHeadingList>
  </MedlineCitation></PubmedArticle>
  <PubmedArticle><MedlineCitation><PMID>222</PMID>
    <Article><Abstract><AbstractText Label="METHODS">CBD in a mouse model of colitis.</AbstractText></Abstract>
    <PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList></Article>
    <MeshHeadingList><MeshHeading><DescriptorName>Animals</DescriptorName></MeshHeading>
    <MeshHeading><DescriptorName>Mice</DescriptorName></MeshHeading></MeshHeadingList>
  </MedlineCitation></PubmedArticle>
</PubmedArticleSet>"""


class EnrichmentTests(unittest.TestCase):
    def test_parse_efetch_xml_extracts_abstract_pubtypes_species(self):
        out = _parse_efetch_xml(_EFETCH_XML)
        self.assertIn("permeability", out["111"]["abstract"])
        self.assertEqual(out["111"]["species"], "human")
        self.assertIn("Randomized Controlled Trial", out["111"]["pubtypes"])
        self.assertEqual(out["222"]["species"], "animal")     # MeSH Animals + Mice
        self.assertIn("mouse", out["222"]["abstract"])

    def test_parse_efetch_xml_malformed_returns_empty(self):
        self.assertEqual(_parse_efetch_xml("not xml at all"), {})

    def _enriched_searcher(self, efetch_body=_EFETCH_XML, efetch=None):
        recs = [
            {"uid": "111", "title": "Cannabidiol trial", "source": "NEJM",
             "pubdate": "2019", "authors": [{"name": "Smith J"}],
             "pubtype": ["Journal Article"]},
            {"uid": "222", "title": "Cannabidiol gut study", "source": "J Vet",
             "pubdate": "2024", "authors": [{"name": "Lee K"}],
             "pubtype": ["Journal Article"]},
        ]
        return PubMedSearcher(
            esearch_fetcher=_stub_fetcher(_make_esearch_fixture(["111", "222"])),
            esummary_fetcher=_stub_fetcher(_make_esummary_fixture(recs)),
            efetch_fetcher=efetch or _stub_fetcher(efetch_body),
        )

    def test_enrich_adds_abstract_species_and_animal_tag(self):
        hits = {h.pmid: h for h in
                self._enriched_searcher().search("cbd gut", enrich=True)}
        self.assertIn("permeability", hits["111"].abstract)
        self.assertEqual(hits["111"].species, "human")
        # MeSH-confirmed animal study gets an "animal model" design tag.
        self.assertEqual(hits["222"].species, "animal")
        self.assertIn("animal model", hits["222"].pubtypes)

    def test_no_enrich_by_default(self):
        hits = {h.pmid: h for h in
                self._enriched_searcher().search("cbd gut")}  # enrich defaults False
        self.assertEqual(hits["111"].abstract, "")
        self.assertEqual(hits["111"].species, "")

    def test_enrich_degrades_gracefully_on_efetch_failure(self):
        def boom(url):
            raise IOError("efetch down")
        hits = {h.pmid: h for h in
                self._enriched_searcher(efetch=boom).search("cbd gut", enrich=True)}
        # Title-only hits still returned — enrichment is best-effort.
        self.assertEqual(len(hits), 2)
        self.assertEqual(hits["111"].abstract, "")


# ── Fixture builders ──────────────────────────────────────────────────


def _make_esearch_fixture(ids: list[str], count: int | None = None) -> str:
    """Build a JSON string mimicking NCBI's esearch.fcgi response."""
    payload = {
        "esearchresult": {
            "count": str(count if count is not None else len(ids)),
            "retmax": str(len(ids)),
            "retstart": "0",
            "idlist": ids,
        }
    }
    return json.dumps(payload)


def _make_esummary_record(
    pmid: str,
    title: str = "Test Paper",
    pubdate: str = "2024 Jan 15",
    journal: str = "J Test Med",
    first_author: str = "Smith J",
    pubtypes: list[str] | None = None,
) -> dict:
    return {
        "uid": pmid,
        "title": title,
        "pubdate": pubdate,
        "source": journal,
        "authors": [{"name": first_author}],
        "pubtype": pubtypes or ["Journal Article"],
    }


def _make_esummary_fixture(records: list[dict]) -> str:
    """Build a JSON string mimicking NCBI's esummary.fcgi response."""
    result = {"uids": [r["uid"] for r in records]}
    for r in records:
        result[r["uid"]] = r
    return json.dumps({"result": result})


def _stub_fetcher(response_body: str):
    calls: list[str] = []

    def f(url: str) -> str:
        calls.append(url)
        return response_body

    f.calls = calls  # type: ignore[attr-defined]
    return f


# ── Happy path ────────────────────────────────────────────────────────


class TestHappyPath(unittest.TestCase):
    def test_five_results_returned(self) -> None:
        ids = ["10000001", "10000002", "10000003", "10000004", "10000005"]
        esearch = _stub_fetcher(_make_esearch_fixture(ids))
        records = [
            _make_esummary_record(p, title=f"Paper {p}") for p in ids
        ]
        esummary = _stub_fetcher(_make_esummary_fixture(records))

        s = PubMedSearcher(
            esearch_fetcher=esearch, esummary_fetcher=esummary
        )
        hits = s.search("CBD PTSD", max_results=5)

        self.assertEqual(len(hits), 5)
        self.assertEqual(hits[0].pmid, "10000001")
        self.assertEqual(hits[0].provenance, "live_pubmed")
        # The fetchers were called exactly once each.
        self.assertEqual(len(esearch.calls), 1)
        self.assertEqual(len(esummary.calls), 1)

    def test_first_author_surname_only(self) -> None:
        ids = ["10000010"]
        esearch = _stub_fetcher(_make_esearch_fixture(ids))
        esummary = _stub_fetcher(_make_esummary_fixture([
            _make_esummary_record("10000010", first_author="Devinsky O")
        ]))
        s = PubMedSearcher(
            esearch_fetcher=esearch, esummary_fetcher=esummary
        )
        hits = s.search("CBD epilepsy", max_results=1)
        self.assertEqual(hits[0].first_author_surname, "Devinsky")

    def test_year_extracted(self) -> None:
        ids = ["10000020"]
        esearch = _stub_fetcher(_make_esearch_fixture(ids))
        esummary = _stub_fetcher(_make_esummary_fixture([
            _make_esummary_record("10000020", pubdate="2024 May 25")
        ]))
        s = PubMedSearcher(
            esearch_fetcher=esearch, esummary_fetcher=esummary
        )
        hits = s.search("test", max_results=1)
        self.assertEqual(hits[0].year, 2024)


# ── Empty / pathological ──────────────────────────────────────────────


class TestEmptyResults(unittest.TestCase):
    def test_empty_idlist_returns_empty_tuple(self) -> None:
        esearch = _stub_fetcher(_make_esearch_fixture([], count=0))
        esummary = _stub_fetcher(_make_esummary_fixture([]))
        s = PubMedSearcher(
            esearch_fetcher=esearch, esummary_fetcher=esummary
        )
        hits = s.search("nothing matches this query", max_results=10)
        self.assertEqual(hits, ())
        # esummary MUST NOT be called when there are no IDs.
        self.assertEqual(len(esummary.calls), 0)


# ── Safety / banned-pattern gates ────────────────────────────────────


class TestSafetyShortCircuit(unittest.TestCase):
    def test_refuse_individualized_skips_network(self) -> None:
        esearch = _stub_fetcher(_make_esearch_fixture(["1"]))
        esummary = _stub_fetcher(_make_esummary_fixture([
            _make_esummary_record("1")
        ]))
        s = PubMedSearcher(
            esearch_fetcher=esearch, esummary_fetcher=esummary
        )
        # An individualized-dose query should hit the refuse gate.
        with self.assertRaises(SearchRefused) as ctx:
            s.search("What dose of CBD should I take for my anxiety?")
        self.assertIn("individualized", ctx.exception.reason.lower())
        # Neither fetcher should have been called.
        self.assertEqual(len(esearch.calls), 0)
        self.assertEqual(len(esummary.calls), 0)

    def test_synthesis_query_refused_without_network(self) -> None:
        esearch = _stub_fetcher(_make_esearch_fixture(["1"]))
        esummary = _stub_fetcher(_make_esummary_fixture([
            _make_esummary_record("1")
        ]))
        s = PubMedSearcher(
            esearch_fetcher=esearch, esummary_fetcher=esummary
        )
        with self.assertRaises(SearchRefused):
            s.search("How do I synthesize K2 at home?")
        self.assertEqual(len(esearch.calls), 0)


class TestBannedPatternShortCircuit(unittest.TestCase):
    def test_cultivar_as_effect_refused_without_network(self) -> None:
        esearch = _stub_fetcher(_make_esearch_fixture(["1"]))
        esummary = _stub_fetcher(_make_esummary_fixture([
            _make_esummary_record("1")
        ]))
        s = PubMedSearcher(
            esearch_fetcher=esearch, esummary_fetcher=esummary
        )
        with self.assertRaises(SearchRefused) as ctx:
            s.search("OG Kush is good for pain relief")
        self.assertIn("cultivar_as_effect", ctx.exception.reason)
        self.assertEqual(len(esearch.calls), 0)


# ── Retraction handling ───────────────────────────────────────────────


class TestRetractionFlag(unittest.TestCase):
    def test_retraction_status_propagates(self) -> None:
        ids = ["20000001"]
        esearch = _stub_fetcher(_make_esearch_fixture(ids))
        esummary = _stub_fetcher(_make_esummary_fixture([
            _make_esummary_record(
                "20000001",
                pubtypes=["Journal Article", "Retracted Publication"],
            )
        ]))
        s = PubMedSearcher(
            esearch_fetcher=esearch, esummary_fetcher=esummary
        )
        hits = s.search("clean query", max_results=1)
        self.assertEqual(hits[0].retraction_status, "retracted")

    def test_clean_paper_marked_clean(self) -> None:
        ids = ["20000002"]
        esearch = _stub_fetcher(_make_esearch_fixture(ids))
        esummary = _stub_fetcher(_make_esummary_fixture([
            _make_esummary_record("20000002", pubtypes=["Journal Article"])
        ]))
        s = PubMedSearcher(
            esearch_fetcher=esearch, esummary_fetcher=esummary
        )
        hits = s.search("clean query", max_results=1)
        self.assertEqual(hits[0].retraction_status, "clean")


# ── Suggested grade mapping ──────────────────────────────────────────


class TestSuggestedGrade(unittest.TestCase):
    def test_meta_analysis_grades_a(self) -> None:
        self.assertEqual(
            suggested_grade_for_pubtypes(("Meta-Analysis",)),
            "Level A (provisional)",
        )

    def test_systematic_review_grades_a(self) -> None:
        self.assertEqual(
            suggested_grade_for_pubtypes(("Systematic Review",)),
            "Level A (provisional)",
        )

    def test_rct_grades_b(self) -> None:
        self.assertEqual(
            suggested_grade_for_pubtypes(
                ("Randomized Controlled Trial",)
            ),
            "Level B (provisional)",
        )

    def test_observational_grades_c(self) -> None:
        self.assertEqual(
            suggested_grade_for_pubtypes(("Observational Study",)),
            "Level C (provisional)",
        )

    def test_case_report_grades_d(self) -> None:
        self.assertEqual(
            suggested_grade_for_pubtypes(("Case Reports",)),
            "Level D (provisional)",
        )

    def test_plain_review_grades_d(self) -> None:
        self.assertEqual(
            suggested_grade_for_pubtypes(("Review",)),
            "Level D (provisional)",
        )

    def test_journal_article_unsupported(self) -> None:
        self.assertEqual(
            suggested_grade_for_pubtypes(("Journal Article",)),
            "Unsupported (provisional)",
        )


# ── since / max_results ──────────────────────────────────────────────


class TestSinceAndMax(unittest.TestCase):
    def test_since_adds_mindate(self) -> None:
        esearch = _stub_fetcher(_make_esearch_fixture(["1"]))
        esummary = _stub_fetcher(_make_esummary_fixture([
            _make_esummary_record("1")
        ]))
        s = PubMedSearcher(
            esearch_fetcher=esearch, esummary_fetcher=esummary
        )
        s.search("query", since="2024-01-01", max_results=1)
        self.assertEqual(len(esearch.calls), 1)
        url = esearch.calls[0]
        self.assertIn("mindate=2024%2F01%2F01", url)
        self.assertIn("datetype=pdat", url)

    def test_max_results_capped_at_50(self) -> None:
        esearch = _stub_fetcher(_make_esearch_fixture([]))
        esummary = _stub_fetcher(_make_esummary_fixture([]))
        s = PubMedSearcher(
            esearch_fetcher=esearch, esummary_fetcher=esummary
        )
        s.search("query", max_results=999)
        url = esearch.calls[0]
        self.assertIn("retmax=50", url)

    def test_esearch_sorts_by_relevance_not_date(self) -> None:
        # Recall fix: a landmark older trial must not be pushed off the result
        # set by a flurry of recent papers (date sort did exactly that).
        esearch = _stub_fetcher(_make_esearch_fixture([]))
        esummary = _stub_fetcher(_make_esummary_fixture([]))
        s = PubMedSearcher(esearch_fetcher=esearch, esummary_fetcher=esummary)
        s.search("cannabidiol gut permeability", max_results=8)
        url = esearch.calls[0]
        self.assertIn("sort=relevance", url)
        self.assertNotIn("sort=date", url)

    def test_invalid_since_raises(self) -> None:
        esearch = _stub_fetcher(_make_esearch_fixture([]))
        esummary = _stub_fetcher(_make_esummary_fixture([]))
        s = PubMedSearcher(
            esearch_fetcher=esearch, esummary_fetcher=esummary
        )
        with self.assertRaises(ValueError):
            s.search("query", since="not-a-date")


# ── Render contracts ─────────────────────────────────────────────────


class TestRenderMarkdown(unittest.TestCase):
    def test_markdown_has_unverified_disclaimer(self) -> None:
        hits = (
            LivePubMedHit(
                pmid="12345",
                title="Cannabidiol for PTSD",
                first_author_surname="Smith",
                year=2024,
                journal="J Test",
                pubtypes=("Journal Article",),
                retraction_status="clean",
                suggested_grade="Unsupported (provisional)",
                provenance="live_pubmed",
            ),
        )
        out = render_markdown("CBD PTSD", hits)
        self.assertIn("live PubMed", out)
        self.assertIn("unverified", out.lower())
        self.assertIn("12345", out)
        self.assertIn("Smith", out)

    def test_markdown_empty_hits(self) -> None:
        out = render_markdown("nothing", ())
        self.assertIn("no hits", out.lower())


class TestRenderJson(unittest.TestCase):
    def test_json_shape(self) -> None:
        hits = (
            LivePubMedHit(
                pmid="12345",
                title="X",
                first_author_surname="A",
                year=2024,
                journal="J",
                pubtypes=("Review",),
                retraction_status="clean",
                suggested_grade="Level D (provisional)",
                provenance="live_pubmed",
            ),
        )
        out = render_json("Q", hits)
        payload = json.loads(out)
        self.assertEqual(payload["query"], "Q")
        self.assertEqual(len(payload["hits"]), 1)
        self.assertEqual(payload["hits"][0]["provenance"], "live_pubmed")
        self.assertEqual(payload["hits"][0]["pmid"], "12345")


# ── Retraction sorted to bottom ──────────────────────────────────────


class TestSortRetractedLast(unittest.TestCase):
    def test_retracted_papers_sort_after_clean(self) -> None:
        ids = ["1", "2", "3"]
        esearch = _stub_fetcher(_make_esearch_fixture(ids))
        esummary = _stub_fetcher(_make_esummary_fixture([
            _make_esummary_record(
                "1",
                pubtypes=["Journal Article", "Retracted Publication"],
            ),
            _make_esummary_record("2", pubtypes=["Journal Article"]),
            _make_esummary_record("3", pubtypes=["Journal Article"]),
        ]))
        s = PubMedSearcher(
            esearch_fetcher=esearch, esummary_fetcher=esummary
        )
        hits = s.search("test", max_results=3)
        # Retracted "1" should be last.
        self.assertEqual(hits[-1].pmid, "1")
        self.assertEqual(hits[-1].retraction_status, "retracted")


if __name__ == "__main__":
    unittest.main()
