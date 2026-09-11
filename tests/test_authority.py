"""
Tests for authority.py (the shared authority-level hierarchy) and its
integration into API responses (authority_label, resolution_reason fields).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from authority import authority_label, authority_description, higher_authority, AUTHORITY_LEVELS  # noqa: E402


class TestAuthorityModule:

    def test_all_six_levels_defined(self):
        assert set(AUTHORITY_LEVELS.keys()) == {1, 2, 3, 4, 5, 6}

    def test_labels_match_spec(self):
        assert authority_label(1) == "Official Policy"
        assert authority_label(2) == "Approved SOP"
        assert authority_label(3) == "Official Documentation"
        assert authority_label(4) == "Project Documentation"
        assert authority_label(5) == "Meeting Notes"
        assert authority_label(6) == "Informal Notes"

    def test_unknown_level_degrades_gracefully(self):
        assert authority_label(99) == "Level 99"
        assert "Unrecognized" in authority_description(99)

    def test_every_level_has_a_description(self):
        for level in AUTHORITY_LEVELS:
            assert len(authority_description(level)) > 10

    def test_higher_authority_lower_number_wins(self):
        assert higher_authority(1, 3) == 1
        assert higher_authority(6, 2) == 2
        assert higher_authority(4, 4) == 4


class TestAuthorityInApiResponses:

    def test_document_list_includes_authority_label(self):
        from fastapi.testclient import TestClient
        from main import app

        with TestClient(app) as client:
            r = client.get("/documents")
            docs = r.json()
            assert len(docs) > 0
            for d in docs:
                assert "authority_label" in d
                assert d["authority_label"] == authority_label(d["authority_level"])

    def test_search_results_include_authority_label(self):
        from fastapi.testclient import TestClient
        from main import app

        with TestClient(app) as client:
            r = client.get("/search", params={"q": "remote work policy", "top_k": 3, "method": "bm25"})
            for item in r.json()["results"]:
                assert item["authority_label"] == authority_label(item["authority_level"])

    def test_contradiction_has_plain_language_resolution_reason(self):
        from fastapi.testclient import TestClient
        from main import app

        with TestClient(app) as client:
            r = client.get("/integrity/conflicts", params={"conflict_type": "contradiction"})
            results = r.json()
            assert len(results) >= 1
            reason = results[0]["resolution_reason"]
            assert results[0]["resolved_doc_key"] in reason
            assert "outranks" in reason
            assert "level" in reason.lower()

    def test_definition_conflict_explains_why_not_resolved(self):
        from fastapi.testclient import TestClient
        from main import app

        with TestClient(app) as client:
            r = client.get("/integrity/definitions")
            results = r.json()
            assert len(results) >= 1
            assert results[0]["resolved_doc_key"] is None
            assert "not resolved" in results[0]["resolution_reason"].lower()

    def test_outdated_includes_version_and_reason(self):
        from fastapi.testclient import TestClient
        from main import app

        with TestClient(app) as client:
            r = client.get("/integrity/outdated")
            results = r.json()
            assert len(results) >= 2
            for item in results:
                assert item["outdated_version"]
                assert item["current_version"]
                assert item["current_doc_key"] in item["reason"]
                assert item["outdated_doc_key"] in item["reason"]
