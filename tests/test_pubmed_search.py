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
    distill_query,
    render_markdown,
    render_json,
    suggested_grade_for_pubtypes,
)


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

    def test_journal_article_floors_to_level_d(self) -> None:
        # Lockstep with EuropePMC + OpenAlex: a bare primary article of
        # unverified design floors to Level D provisional, not Unsupported.
        self.assertEqual(
            suggested_grade_for_pubtypes(("Journal Article",)),
            "Level D (provisional)",
        )

    def test_empty_pubtypes_stays_unsupported(self) -> None:
        self.assertEqual(
            suggested_grade_for_pubtypes(()),
            "Unsupported (provisional)",
        )

    def test_non_evidence_types_with_journal_article_stay_unsupported(self) -> None:
        for pt in ("Published Erratum", "Retraction of Publication",
                   "Comment", "Editorial"):
            self.assertEqual(
                suggested_grade_for_pubtypes((pt, "Journal Article")),
                "Unsupported (provisional)",
                f"{pt!r} co-carrying Journal Article must stay Unsupported",
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
                suggested_grade="Level D (provisional)",
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


# ── Query distillation ────────────────────────────────────────────────


class TestDistillQuery(unittest.TestCase):
    """Natural-language questions must be distilled to content terms before
    they reach PubMed esearch. Regression: a typed question reached esearch
    verbatim, which automatic term mapping parses as `the, is[Author] AND
    (...)` — reading "is" as an [Author] field — and returns ZERO hits even
    though thousands of relevant papers exist.
    """

    def test_question_scaffolding_stripped_content_kept(self) -> None:
        out = distill_query(
            "What is the molecular difference between THC and CBD?"
        )
        tokens = out.split()
        for stop in ("What", "what", "is", "the", "between", "and"):
            self.assertNotIn(stop, tokens)
        for kw in ("molecular", "difference", "THC", "CBD"):
            self.assertIn(kw, tokens)
        self.assertNotIn("?", out)

    def test_keyword_query_is_unchanged_idempotent(self) -> None:
        kw = "THC CBD molecular structure"
        self.assertEqual(distill_query(kw), kw)
        self.assertEqual(distill_query(distill_query(kw)), kw)

    def test_single_uppercase_letter_preserved(self) -> None:
        # "vitamin A" must survive even though lowercase "a" is a stopword.
        self.assertEqual(distill_query("vitamin A and cannabis"), "vitamin A cannabis")

    def test_domain_spelling_with_punctuation_preserved(self) -> None:
        out = distill_query("How does Δ9-THC bind the CB1 receptor?")
        tokens = out.split()
        self.assertIn("Δ9-THC", tokens)
        self.assertIn("CB1", tokens)
        self.assertIn("receptor", tokens)
        self.assertNotIn("How", tokens)
        self.assertNotIn("does", tokens)

    def test_all_stopwords_falls_back_to_original(self) -> None:
        # Never return an empty search; degrade to the original query.
        self.assertEqual(distill_query("what is the"), "what is the")

    def test_natural_language_question_is_distilled_before_esearch(self) -> None:
        from urllib.parse import unquote

        esearch = _stub_fetcher(_make_esearch_fixture([]))
        esummary = _stub_fetcher(_make_esummary_fixture([]))
        s = PubMedSearcher(esearch_fetcher=esearch, esummary_fetcher=esummary)
        s.search(
            "What is the molecular difference between THC and CBD?",
            max_results=5,
        )
        term = unquote(esearch.calls[0].split("&term=")[1].split("&")[0])
        self.assertNotIn("is", term.lower().split())
        self.assertNotIn("what", term.lower().split())
        for kw in ("molecular", "difference", "THC", "CBD"):
            self.assertIn(kw, term)


def _url_aware_esearch(empty_body: str, recovered_body: str):
    """esearch stub that returns nothing for the primary (sort=date) query but the
    recovered ids for the broadened best-match (sort=relevance) retry."""
    calls: list[str] = []

    def f(url: str) -> str:
        calls.append(url)
        return recovered_body if "sort=relevance" in url else empty_body

    f.calls = calls  # type: ignore[attr-defined]
    return f


class TestZeroResultBroadening(unittest.TestCase):
    """A conjunctive query that ANDs to 0 must still recall relevant papers: retry
    ONCE with the distinctive terms OR'd + cannabis-scoped, best-match ranked. So
    discover raises papers for any cannabis-science question, not 0."""

    def test_zero_result_query_broadens_and_recovers(self) -> None:
        esearch = _url_aware_esearch(
            _make_esearch_fixture([], count=0),
            _make_esearch_fixture(["20000001", "20000002"]))
        esummary = _stub_fetcher(_make_esummary_fixture([
            _make_esummary_record("20000001", title="Constituents of Cannabis sativa"),
            _make_esummary_record("20000002", title="Myrcene terpene pharmacology"),
        ]))
        s = PubMedSearcher(esearch_fetcher=esearch, esummary_fetcher=esummary)
        hits = s.search("terpene myrcene sedation entourage effect", max_results=5)
        self.assertEqual(len(hits), 2)                       # recovered, not 0
        self.assertEqual(len(esearch.calls), 2)              # primary + one broadened retry
        self.assertNotIn("sort=relevance", esearch.calls[0])  # primary unchanged (date)
        self.assertIn("sort=relevance", esearch.calls[1])     # retry is best-match

    def test_no_broaden_when_primary_returns_results(self) -> None:
        esearch = _stub_fetcher(_make_esearch_fixture(["10000001"]))
        esummary = _stub_fetcher(_make_esummary_fixture([
            _make_esummary_record("10000001")]))
        s = PubMedSearcher(esearch_fetcher=esearch, esummary_fetcher=esummary)
        s.search("terpene myrcene sedation entourage effect", max_results=5)
        self.assertEqual(len(esearch.calls), 1)              # purely additive — no retry

    def test_single_distinctive_term_is_not_broadened(self) -> None:
        esearch = _stub_fetcher(_make_esearch_fixture([], count=0))
        esummary = _stub_fetcher(_make_esummary_fixture([]))
        s = PubMedSearcher(esearch_fetcher=esearch, esummary_fetcher=esummary)
        hits = s.search("myrcene", max_results=5)
        self.assertEqual(hits, ())                           # nothing to broaden
        self.assertEqual(len(esearch.calls), 1)

    def test_broaden_term_builder(self) -> None:
        from cannavec_science.pubmed_search import _broaden_pubmed_term
        out = _broaden_pubmed_term("terpene myrcene sedation entourage effect")
        self.assertIn("myrcene OR", out)
        self.assertNotIn("effect", out)                      # generic filler dropped
        self.assertIn("AND (cannabis", out)                  # cannabis-scoped recall
        self.assertIsNone(_broaden_pubmed_term("myrcene"))   # one term → no broadening


if __name__ == "__main__":
    unittest.main()
