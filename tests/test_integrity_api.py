"""
Tests for the /integrity/* endpoints. Requires
scripts/build_integrity_engine.py to have been run against the current DB.

These assert specific, known results against the real corpus (not just
"status 200") because integrity/FINDINGS.md documents exact validated
numbers -- if these tests ever show different counts, that's a signal
something in the corpus or detector logic changed and FINDINGS.md needs
re-validating, not that the test is wrong.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from main import app                        # noqa: E402

client = TestClient(app)


def test_outdated_finds_both_known_supersession_chains():
    r = client.get("/integrity/outdated")
    assert r.status_code == 200
    results = r.json()
    keys = {(item["outdated_doc_key"], item["current_doc_key"]) for item in results}
    assert ("hr-remote-work-policy-v3", "hr-remote-work-policy-v4") in keys
    assert ("finance-expense-policy-v1", "finance-expense-policy-v2") in keys


def test_conflicts_includes_password_contradiction():
    r = client.get("/integrity/conflicts", params={"conflict_type": "contradiction"})
    assert r.status_code == 200
    results = r.json()
    assert len(results) >= 1
    password_conflict = next((c for c in results if "90" in (c["value_a"] or "") + (c["value_b"] or "")), None)
    assert password_conflict is not None
    assert password_conflict["severity"] == "high"
    assert password_conflict["resolved_doc_key"] == "it-security-policy-v2"


def test_conflicts_includes_customer_definition():
    r = client.get("/integrity/conflicts", params={"conflict_type": "definition"})
    assert r.status_code == 200
    results = r.json()
    assert len(results) >= 1
    assert results[0]["concept"] == "Customer"


def test_definitions_alias_matches_conflicts_filtered():
    r1 = client.get("/integrity/definitions")
    r2 = client.get("/integrity/conflicts", params={"conflict_type": "definition"})
    assert len(r1.json()) == len(r2.json())


def test_conflicts_filter_by_severity():
    r = client.get("/integrity/conflicts", params={"severity": "high"})
    results = r.json()
    assert all(c["severity"] == "high" for c in results)


def test_duplicates_endpoint_returns_valid_shape_even_if_empty():
    """Per integrity/FINDINGS.md, this is documented to be empty with the
    current fallback lexical method -- the important thing is the endpoint
    still returns a well-formed (if empty) response, not that it's non-empty."""
    r = client.get("/integrity/duplicates")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_conflict_includes_chunk_evidence():
    r = client.get("/integrity/conflicts")
    results = r.json()
    assert len(results) >= 1
    for c in results:
        assert c["chunk_a"]["chunk_text"]
        assert c["chunk_b"]["chunk_text"]
        assert c["chunk_a"]["doc_key"]
        assert c["chunk_b"]["doc_key"]
