"""
Tests for the /knowledge/entities and /knowledge/graph endpoints.

Requires the knowledge graph to already be built
(scripts/build_knowledge_graph.py) against the current DB -- these tests
assert on that precondition rather than silently skipping, same policy as
tests/test_search_api.py for the BM25 index.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from main import app                        # noqa: E402

client = TestClient(app)


def test_list_entities_returns_populated_data():
    r = client.get("/knowledge/entities")
    assert r.status_code == 200
    entities = r.json()
    assert len(entities) > 0
    for e in entities:
        assert e["name"]
        assert e["entity_type"]


def test_filter_entities_by_type():
    r = client.get("/knowledge/entities", params={"entity_type": "Department"})
    entities = r.json()
    assert len(entities) >= 5  # HR, IT-Security, Finance, Engineering, Projects at minimum
    assert all(e["entity_type"] == "Department" for e in entities)
    names = {e["name"] for e in entities}
    assert "HR" in names
    assert "IT-Security" in names


def test_get_entity_not_found():
    r = client.get("/knowledge/entities/999999")
    assert r.status_code == 404


def test_full_graph_export():
    r = client.get("/knowledge/graph")
    assert r.status_code == 200
    body = r.json()
    assert len(body["nodes"]) > 0
    assert len(body["edges"]) > 0


def test_graph_neighborhood_for_remote_work_policy():
    """This is the Demo 4 scenario from the project spec: searching a policy
    should surface its owning department, applies_to scope, related security
    policy, and superseded version."""
    r = client.get("/knowledge/graph", params={"entity_name": "hr-remote-work-policy-v4", "depth": 1})
    assert r.status_code == 200
    body = r.json()
    node_names = {n["name"] for n in body["nodes"]}

    assert "HR" in node_names
    assert "Employees" in node_names
    assert "hr-remote-work-policy-v3" in node_names  # superseded version
    assert "it-security-policy-v2" in node_names  # cross-referenced in the doc text

    relation_types = {e["relation_type"] for e in body["edges"]}
    assert "supersedes" in relation_types
    assert "owned_by" in relation_types


def test_graph_neighborhood_unknown_entity_404s():
    r = client.get("/knowledge/graph", params={"entity_name": "definitely-not-a-real-entity"})
    assert r.status_code == 404


def test_graph_neighborhood_is_case_insensitive():
    r1 = client.get("/knowledge/graph", params={"entity_name": "HR"})
    r2 = client.get("/knowledge/graph", params={"entity_name": "hr"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert len(r1.json()["nodes"]) == len(r2.json()["nodes"])
