"""
Tests for backend/search_enrichment.py and its integration into /search.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from search_enrichment import matched_terms, ranking_explanation, relative_confidence  # noqa: E402


class TestMatchedTerms:

    def test_finds_overlapping_terms_in_query_order(self):
        terms = matched_terms("password expiration policy", "Our password policy is strict.")
        assert terms == ["password", "policy"]

    def test_no_overlap_returns_empty(self):
        assert matched_terms("unrelated query text", "completely different content here") == []

    def test_deduplicates_repeated_query_terms(self):
        terms = matched_terms("policy policy policy", "This is our policy document.")
        assert terms == ["policy"]

    def test_respects_limit(self):
        terms = matched_terms("alpha beta gamma delta epsilon zeta eta", "alpha beta gamma delta epsilon zeta eta", limit=3)
        assert len(terms) == 3


class TestRankingExplanation:

    def test_bm25_includes_matched_terms(self):
        text = ranking_explanation("bm25", "password policy", "Our password policy document.")
        assert "BM25" in text
        assert "password" in text

    def test_dense_never_claims_term_overlap(self):
        """LSA has no honest 'matched terms' story -- the explanation
        should not imply lexical matching for the dense method."""
        text = ranking_explanation("dense", "password policy", "Our password policy document.")
        assert "Matched terms" not in text

    def test_no_overlap_says_so_explicitly(self):
        text = ranking_explanation("bm25", "zzz yyy xxx", "completely unrelated content")
        assert "No literal term overlap" in text

    def test_hybrid_rerank_explanation_mentions_rescoring(self):
        text = ranking_explanation("hybrid_rerank", "password", "password policy text")
        assert "rescored" in text.lower()


class TestRelativeConfidence:

    def test_top_result_is_100_percent(self):
        assert relative_confidence(10.0, 10.0) == 100.0

    def test_lower_score_is_proportional(self):
        assert relative_confidence(5.0, 10.0) == 50.0

    def test_zero_max_score_does_not_divide_by_zero(self):
        assert relative_confidence(0.0, 0.0) == 0.0

    def test_never_exceeds_100(self):
        assert relative_confidence(15.0, 10.0) == 100.0

    def test_never_negative(self):
        assert relative_confidence(-5.0, 10.0) == 0.0


class TestSearchApiEnrichment:

    def test_conflicting_documents_flagged_and_reference_each_other(self):
        from fastapi.testclient import TestClient
        from main import app

        with TestClient(app) as client:
            r = client.get("/search", params={"q": "password expiration", "top_k": 5, "method": "bm25"})
            results = r.json()["results"]
            conflicted = {item["doc_key"]: item for item in results if item["has_known_conflict"]}
            assert "it-handbook" in conflicted
            assert "it-security-policy-v2" in conflicted

            handbook_related = {e["name"] for e in conflicted["it-handbook"]["related_entities"]}
            assert "it-security-policy-v2" in handbook_related

    def test_non_conflicting_document_not_flagged(self):
        from fastapi.testclient import TestClient
        from main import app

        with TestClient(app) as client:
            r = client.get("/search", params={"q": "parental leave weeks", "top_k": 3, "method": "bm25"})
            results = r.json()["results"]
            assert len(results) >= 1
            assert not any(item["has_known_conflict"] for item in results if item["doc_key"] == "hr-parental-leave-policy")

    def test_confidence_is_100_for_top_result(self):
        from fastapi.testclient import TestClient
        from main import app

        with TestClient(app) as client:
            r = client.get("/search", params={"q": "remote work policy", "top_k": 5, "method": "bm25"})
            results = r.json()["results"]
            assert results[0]["confidence_percent"] == 100.0
            # confidence should be non-increasing down the ranked list
            confidences = [item["confidence_percent"] for item in results]
            assert confidences == sorted(confidences, reverse=True)

    def test_every_result_has_a_ranking_explanation(self):
        from fastapi.testclient import TestClient
        from main import app

        with TestClient(app) as client:
            r = client.get("/search", params={"q": "expense reimbursement limit", "top_k": 3, "method": "hybrid_rerank"})
            for item in r.json()["results"]:
                assert len(item["ranking_explanation"]) > 0
