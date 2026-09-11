"""
Tests for the /search endpoint (BM25-backed, Phase 3).

Requires the BM25 index to already be built (scripts/build_bm25_index.py) --
these tests assert on that precondition rather than silently skipping, since
a missing index should be a loud failure in CI, not a silent pass.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from main import app                        # noqa: E402

client = TestClient(app)


def test_search_returns_results():
    r = client.get("/search", params={"q": "What is the current remote work policy?", "top_k": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["method"] == "hybrid_rerank"  # default method
    assert len(body["results"]) >= 1


def test_search_all_four_methods_work():
    for method in ["bm25", "dense", "hybrid", "hybrid_rerank"]:
        r = client.get("/search", params={"q": "remote work policy", "top_k": 5, "method": method})
        assert r.status_code == 200, f"method={method} failed: {r.text}"
        assert r.json()["method"] == method


def test_search_invalid_method_rejected():
    r = client.get("/search", params={"q": "test", "method": "not_a_real_method"})
    assert r.status_code == 422


def test_search_top_result_is_the_current_remote_work_policy():
    r = client.get("/search", params={"q": "What is the current remote work policy?", "top_k": 5, "method": "bm25"})
    top = r.json()["results"][0]
    assert top["doc_key"] == "hr-remote-work-policy-v4"


def test_search_surfaces_both_conflicting_password_sources():
    """This is the core Demo 2 behavior: a query touching a contradiction
    should retrieve BOTH conflicting sources, not silently pick one."""
    r = client.get("/search", params={"q": "How often must employees change their passwords?", "top_k": 5, "method": "bm25"})
    doc_keys = {item["doc_key"] for item in r.json()["results"]}
    assert "it-security-policy-v2" in doc_keys
    assert "it-handbook" in doc_keys


def test_search_respects_top_k():
    r = client.get("/search", params={"q": "policy", "top_k": 3})
    assert len(r.json()["results"]) <= 3


def test_search_requires_query_param():
    r = client.get("/search")
    assert r.status_code == 422  # FastAPI validation error, missing required 'q'


def test_search_results_are_score_ordered_descending():
    r = client.get("/search", params={"q": "production database access approval", "top_k": 10})
    scores = [item["score"] for item in r.json()["results"]]
    assert scores == sorted(scores, reverse=True)
