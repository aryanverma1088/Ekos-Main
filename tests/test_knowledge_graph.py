"""
Tests for knowledge/entities, knowledge/extraction, knowledge/graph.

Several of these tests exist specifically because manual inspection of the
extracted graph during development caught real bugs:
  - DiGraph silently collapsing two different relation_types between the
    same (source, target) pair into one edge -> must use MultiDiGraph
  - Two document versions sharing an identical title caused the source's
    own H1 heading to "match" its sibling version's title, producing a
    nonsensical backward-in-time reference
  - A title matching as a SUBSTRING of the source's own title (e.g.
    "Leave Policy" inside "Parental Leave Policy") produced the same kind
    of spurious self-referential match
  - Hard-wrapped line breaks in the source markdown (e.g. "...Device\\nPolicy")
    defeated naive substring matching until whitespace was normalized
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from knowledge.entities.extract_entities import extract_entities, is_team_name  # noqa: E402
from knowledge.extraction.extract_relationships import (                          # noqa: E402
    extract_metadata_relationships, extract_text_reference_relationships, extract_all_relationships
)
from knowledge.graph.graph_builder import build_graph, to_node_link_json, get_neighborhood, find_entity_id_by_name  # noqa: E402


SAMPLE_DOCS = [
    {
        "doc_key": "hr-remote-work-policy-v3", "title": "Remote Work Policy",
        "department": "HR", "doc_type": "Policy", "owner": "HR", "author": "Priya Nathan",
        "supersedes_doc_key": None, "raw_text": "# Remote Work Policy\n\nOld version text here.",
        "first_chunk_id": 1,
    },
    {
        "doc_key": "hr-remote-work-policy-v4", "title": "Remote Work Policy",
        "department": "HR", "doc_type": "Policy", "owner": "HR", "author": "Priya Nathan",
        "supersedes_doc_key": "hr-remote-work-policy-v3",
        "raw_text": "# Remote Work Policy\n\nEmployees must follow the IT Security Policy too.",
        "first_chunk_id": 2,
    },
    {
        "doc_key": "it-security-policy-v2", "title": "IT Security Policy",
        "department": "IT-Security", "doc_type": "Policy", "owner": "IT-Security", "author": "Daniel Ochieng",
        "supersedes_doc_key": None, "raw_text": "# IT Security Policy\n\nPasswords must be changed regularly.",
        "first_chunk_id": 3,
    },
    {
        "doc_key": "it-handbook", "title": "IT Handbook",
        "department": "IT-Security", "doc_type": "Handbook", "owner": "IT-Security", "author": "IT Team",
        "supersedes_doc_key": None, "raw_text": "# IT Handbook\n\nGeneral onboarding info.",
        "first_chunk_id": 4,
    },
    {
        "doc_key": "hr-parental-leave-policy", "title": "Parental Leave Policy",
        "department": "HR", "doc_type": "Policy", "owner": "HR", "author": "Priya Nathan",
        "supersedes_doc_key": None, "raw_text": "# Parental Leave Policy\n\nEighteen weeks of leave.",
        "first_chunk_id": 5,
    },
    {
        "doc_key": "hr-leave-policy", "title": "Leave Policy",
        "department": "HR", "doc_type": "Policy", "owner": "HR", "author": "Priya Nathan",
        "supersedes_doc_key": None, "raw_text": "# Leave Policy\n\nStandard annual leave rules.",
        "first_chunk_id": 6,
    },
    {
        "doc_key": "eng-wrapped-line-doc", "title": "Device Policy",
        "department": "Engineering", "doc_type": "Policy", "owner": "Engineering", "author": "Marcus Webb",
        "supersedes_doc_key": None,
        "raw_text": "# Device Policy\n\nAll laptops require full-disk encryption.",
        "first_chunk_id": 7,
    },
    {
        "doc_key": "eng-references-wrapped-title", "title": "Wrapped Reference Doc",
        "department": "Engineering", "doc_type": "Policy", "owner": "Engineering", "author": "Marcus Webb",
        "supersedes_doc_key": None,
        # deliberately mirrors the real bug: target title split across a hard line wrap in the source markdown
        "raw_text": "# Wrapped Reference Doc\n\nComply with the current Device\nPolicy at all times.",
        "first_chunk_id": 8,
    },
]


class TestEntityExtraction:

    def test_is_team_name(self):
        assert is_team_name("HR Team")
        assert is_team_name("IT Team")
        assert not is_team_name("Priya Nathan")

    def test_every_document_becomes_an_entity(self):
        entities = extract_entities(SAMPLE_DOCS)
        doc_entity_names = {e["name"] for e in entities if e["entity_type"] in ("Policy", "Documentation", "Process")}
        for doc in SAMPLE_DOCS:
            assert doc["doc_key"] in doc_entity_names

    def test_team_authors_do_not_become_person_entities(self):
        entities = extract_entities(SAMPLE_DOCS)
        person_names = {e["name"] for e in entities if e["entity_type"] == "Person"}
        assert "IT Team" not in person_names
        assert "Priya Nathan" in person_names

    def test_departments_deduplicated(self):
        entities = extract_entities(SAMPLE_DOCS)
        dept_entities = [e for e in entities if e["entity_type"] == "Department" and e["name"] == "HR"]
        assert len(dept_entities) == 1  # HR appears as owner/department on multiple docs, should dedupe

    def test_employees_group_entity_created(self):
        entities = extract_entities(SAMPLE_DOCS)
        assert any(e["entity_type"] == "Group" and e["name"] == "Employees" for e in entities)


class TestMetadataRelationships:

    def test_supersedes_relation_created(self):
        rels = extract_metadata_relationships(SAMPLE_DOCS)
        supersedes = [r for r in rels if r["relation_type"] == "supersedes"]
        assert any(r["source"] == "hr-remote-work-policy-v4" and r["target"] == "hr-remote-work-policy-v3" for r in supersedes)

    def test_created_by_skips_team_authors(self):
        rels = extract_metadata_relationships(SAMPLE_DOCS)
        created_by = [r for r in rels if r["relation_type"] == "created_by"]
        sources = {r["source"] for r in created_by}
        assert "it-handbook" not in sources  # authored by "IT Team", should be skipped

    def test_policy_applies_to_employees(self):
        rels = extract_metadata_relationships(SAMPLE_DOCS)
        applies = [r for r in rels if r["relation_type"] == "applies_to"]
        assert any(r["source"] == "hr-remote-work-policy-v3" and r["target"] == "Employees" for r in applies)

    def test_owned_by_relation(self):
        rels = extract_metadata_relationships(SAMPLE_DOCS)
        owned = [r for r in rels if r["relation_type"] == "owned_by"]
        assert any(r["source"] == "it-security-policy-v2" and r["target"] == "IT-Security" for r in owned)


class TestTextReferenceRelationships:
    """Regression tests for the specific false-positive bugs caught during development."""

    def test_finds_genuine_cross_reference(self):
        rels = extract_text_reference_relationships(SAMPLE_DOCS)
        refs = [(r["source"], r["target"]) for r in rels]
        assert ("hr-remote-work-policy-v4", "it-security-policy-v2") in refs

    def test_does_not_create_backward_reference_between_shared_title_versions(self):
        """v3 and v4 share the exact title 'Remote Work Policy' -- v3's own H1
        heading should not spuriously 'match' v4's title and create a
        nonsensical v3 -> v4 reference."""
        rels = extract_text_reference_relationships(SAMPLE_DOCS)
        refs = [(r["source"], r["target"]) for r in rels]
        assert ("hr-remote-work-policy-v3", "hr-remote-work-policy-v4") not in refs
        assert ("hr-remote-work-policy-v4", "hr-remote-work-policy-v3") not in refs  # also covered by supersedes exclusion

    def test_does_not_match_substring_of_own_title(self):
        """'Leave Policy' is a substring of 'Parental Leave Policy' -- the
        parental leave doc's own heading should not spuriously match the
        unrelated hr-leave-policy document."""
        rels = extract_text_reference_relationships(SAMPLE_DOCS)
        refs = [(r["source"], r["target"]) for r in rels]
        assert ("hr-parental-leave-policy", "hr-leave-policy") not in refs

    def test_matches_across_hard_line_wraps(self):
        """'Device\\nPolicy' in the source markdown (hard-wrapped mid-title)
        must still match the title 'Device Policy' after whitespace
        normalization -- this is the exact bug caught during development
        when 'and Device\\nPolicy.' in a real seed document failed to match
        the title 'Device Policy' with naive (non-normalized) substring
        matching."""
        rels = extract_text_reference_relationships(SAMPLE_DOCS)
        refs = [(r["source"], r["target"]) for r in rels]
        assert ("eng-references-wrapped-title", "eng-wrapped-line-doc") in refs

    def test_supersedes_pair_not_double_counted_as_reference(self):
        rels = extract_text_reference_relationships(SAMPLE_DOCS)
        refs = [(r["source"], r["target"]) for r in rels]
        assert ("hr-remote-work-policy-v4", "hr-remote-work-policy-v3") not in refs


class TestGraphBuilder:

    def test_multidigraph_preserves_parallel_edges_with_different_relation_types(self):
        """Regression test for the DiGraph-collapses-parallel-edges bug: a
        department-owned SOP is both owned_by and applies_to the same
        department -- both edges must survive."""
        entities = [
            {"id": 1, "name": "some-sop", "entity_type": "Process"},
            {"id": 2, "name": "Engineering", "entity_type": "Department"},
        ]
        relationships = [
            {"source_entity_id": 1, "target_entity_id": 2, "relation_type": "owned_by", "confidence": 1.0},
            {"source_entity_id": 1, "target_entity_id": 2, "relation_type": "applies_to", "confidence": 1.0},
        ]
        g = build_graph(entities, relationships)
        exported = to_node_link_json(g)
        assert len(exported["edges"]) == 2

    def test_neighborhood_returns_connected_nodes(self):
        entities = [
            {"id": 1, "name": "doc-a", "entity_type": "Policy"},
            {"id": 2, "name": "HR", "entity_type": "Department"},
            {"id": 3, "name": "unrelated-doc", "entity_type": "Policy"},
        ]
        relationships = [
            {"source_entity_id": 1, "target_entity_id": 2, "relation_type": "owned_by", "confidence": 1.0},
        ]
        g = build_graph(entities, relationships)
        neighborhood = get_neighborhood(g, entity_id=1, depth=1)
        node_ids = {n["id"] for n in neighborhood["nodes"]}
        assert node_ids == {1, 2}
        assert 3 not in node_ids

    def test_find_entity_id_by_name_case_insensitive(self):
        entities = [{"id": 5, "name": "Remote Work Policy", "entity_type": "Policy"}]
        g = build_graph(entities, [])
        assert find_entity_id_by_name(g, "remote work policy") == 5
        assert find_entity_id_by_name(g, "nonexistent") is None


class TestFullExtractionPipeline:

    def test_extract_all_relationships_runs_without_error(self):
        rels = extract_all_relationships(SAMPLE_DOCS)
        assert len(rels) > 0
        for r in rels:
            assert "source" in r and "target" in r and "relation_type" in r
