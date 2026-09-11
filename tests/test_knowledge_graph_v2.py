"""
Tests for the enriched knowledge graph (Team/Project/Concept entities,
manages/related_to/defines relations, and the integrity-engine-to-graph
edge writeback for conflicts_with/duplicate_of).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from knowledge.entities.extract_entities import (                                    # noqa: E402
    extract_entities, extract_team_mentions, extract_project_names, extract_concept_terms
)
from knowledge.extraction.extract_relationships import (                              # noqa: E402
    extract_team_relationships, extract_project_relationships,
    extract_concept_relationships, extract_tag_overlap_relationships,
)


SAMPLE_DOCS = [
    {
        "doc_key": "eng-deployment-policy", "title": "Deployment Policy",
        "department": "Engineering", "doc_type": "SOP", "owner": "Engineering", "author": "Marcus Webb",
        "supersedes_doc_key": None, "tags": "deployment, ci-cd, engineering",
        "raw_text": "The Platform team owns the production deployment process end to end.",
        "first_chunk_id": 1,
    },
    {
        "doc_key": "eng-incident-response-sop", "title": "Incident Response SOP",
        "department": "Engineering", "doc_type": "SOP", "owner": "Engineering", "author": "Marcus Webb",
        "supersedes_doc_key": None, "tags": "incident-response, on-call, engineering",
        "raw_text": "The support team helps route customer-facing incidents to engineering.",
        "first_chunk_id": 2,
    },
    {
        "doc_key": "project-atlas-charter", "title": "Project Atlas Charter",
        "department": "Projects", "doc_type": "ProjectDocumentation", "owner": "Marketing", "author": "Sofia Nakamura",
        "supersedes_doc_key": None, "tags": "project-atlas, marketing, growth",
        "raw_text": "A Customer is defined as any qualified lead in the funnel.",
        "first_chunk_id": 3,
    },
    {
        "doc_key": "finance-glossary", "title": "Finance Glossary of Terms",
        "department": "Finance", "doc_type": "Documentation", "owner": "Finance", "author": "Rina Alvarez",
        "supersedes_doc_key": None, "tags": "glossary, definitions, finance",
        "raw_text": "A Customer is defined as a paying account with an active contract.",
        "first_chunk_id": 4,
    },
    {
        "doc_key": "it-security-policy-v2", "title": "IT Security Policy",
        "department": "IT-Security", "doc_type": "Policy", "owner": "IT-Security", "author": "Daniel Ochieng",
        "supersedes_doc_key": None, "tags": "security, passwords, encryption",
        "raw_text": "Passwords must be changed regularly.",
        "first_chunk_id": 5,
    },
    {
        "doc_key": "it-handbook", "title": "IT Handbook",
        "department": "IT-Security", "doc_type": "Handbook", "owner": "IT-Security", "author": "IT Team",
        "supersedes_doc_key": None, "tags": "it-support, onboarding, passwords",
        "raw_text": "General onboarding info for new hires.",
        "first_chunk_id": 6,
    },
]


class TestTeamExtraction:

    def test_extracts_team_with_ownership_verb(self):
        assert extract_team_mentions("The Platform team owns the deployment process.") == ["Platform"]

    def test_does_not_extract_incidental_team_mentions(self):
        """'the support team helps route' has no ownership/management verb
        directly after 'team' -- should NOT be extracted, matching the
        precision-first design (verified against the real corpus during
        development: only 'Platform team owns...' matched, nothing else)."""
        assert extract_team_mentions("The support team helps route incidents.") == []

    def test_matches_manages_leads_and_responsible_for(self):
        assert extract_team_mentions("The Growth team manages the funnel.") == ["Growth"]
        assert extract_team_mentions("The Design team leads this initiative.") == ["Design"]
        assert extract_team_mentions("The Ops team is responsible for uptime.") == ["Ops"]

    def test_no_false_positive_on_generic_team_calendar_mention(self):
        assert extract_team_mentions("leave is reflected in the shared team calendar.") == []


class TestProjectExtraction:

    def test_extracts_project_name_from_title(self):
        assert extract_project_names("Project Atlas Charter") == ["Project Atlas"]

    def test_extracts_from_title_with_em_dash_suffix(self):
        assert extract_project_names("Project Nova — Weekly Sync Notes") == ["Project Nova"]

    def test_no_match_when_title_has_no_project_name(self):
        assert extract_project_names("Deployment Policy") == []


class TestConceptExtraction:

    def test_extracts_is_defined_as_term(self):
        assert "Customer" in extract_concept_terms("A Customer is defined as a paying account.")

    def test_extracts_means_term(self):
        assert "Churn" in extract_concept_terms("Churn means cancellation before renewal.")

    def test_no_terms_in_plain_text(self):
        assert extract_concept_terms("This policy has no formal definitions.") == []


class TestEntityExtractionIncludesNewTypes:

    def test_platform_team_entity_created(self):
        entities = extract_entities(SAMPLE_DOCS)
        teams = [e for e in entities if e["entity_type"] == "Team"]
        assert any(e["name"] == "Platform" for e in teams)
        assert len(teams) == 1  # only Platform -- no false positives from the other docs

    def test_project_entities_created(self):
        entities = extract_entities(SAMPLE_DOCS)
        projects = {e["name"] for e in entities if e["entity_type"] == "Project"}
        assert projects == {"Project Atlas"}

    def test_concept_entity_deduplicated_across_documents(self):
        entities = extract_entities(SAMPLE_DOCS)
        concepts = [e for e in entities if e["entity_type"] == "Concept"]
        assert len(concepts) == 1  # "Customer" appears in 2 docs but is a single entity
        assert concepts[0]["name"] == "Customer"


class TestTeamRelationships:

    def test_manages_relation_created(self):
        rels = extract_team_relationships(SAMPLE_DOCS)
        assert len(rels) == 1
        assert rels[0] == {
            "source": "Platform", "source_type": "Team",
            "target": "eng-deployment-policy", "target_type": "Document",
            "relation_type": "manages", "confidence": 0.9,
        }


class TestProjectRelationships:

    def test_related_to_project_created(self):
        rels = extract_project_relationships(SAMPLE_DOCS)
        assert len(rels) == 1
        assert rels[0]["source"] == "project-atlas-charter"
        assert rels[0]["target"] == "Project Atlas"
        assert rels[0]["relation_type"] == "related_to"


class TestConceptRelationships:

    def test_defines_relation_from_both_documents(self):
        rels = extract_concept_relationships(SAMPLE_DOCS)
        sources = {r["source"] for r in rels}
        assert sources == {"project-atlas-charter", "finance-glossary"}
        assert all(r["target"] == "Customer" and r["relation_type"] == "defines" for r in rels)


class TestTagOverlapRelationships:

    def test_shared_specific_tag_creates_related_to(self):
        """it-security-policy-v2 and it-handbook share the 'passwords' tag --
        a real, specific topical signal (and not coincidentally, these are
        the same two documents in the password-contradiction ground truth)."""
        rels = extract_tag_overlap_relationships(SAMPLE_DOCS)
        pairs = {tuple(sorted([r["source"], r["target"]])) for r in rels}
        assert ("it-handbook", "it-security-policy-v2") in pairs

    def test_generic_department_name_tags_excluded(self):
        """Both eng-deployment-policy and eng-incident-response-sop are tagged
        'engineering' -- but that's just the department name restated, not a
        genuine topical signal, and should NOT create a related_to edge on
        that basis alone (they share no other tag)."""
        rels = extract_tag_overlap_relationships(SAMPLE_DOCS)
        pairs = {tuple(sorted([r["source"], r["target"]])) for r in rels}
        assert ("eng-deployment-policy", "eng-incident-response-sop") not in pairs

    def test_confidence_capped_below_explicit_signals(self):
        rels = extract_tag_overlap_relationships(SAMPLE_DOCS)
        assert all(r["confidence"] <= 0.6 for r in rels)

    def test_no_duplicate_pairs(self):
        rels = extract_tag_overlap_relationships(SAMPLE_DOCS)
        pairs = [tuple(sorted([r["source"], r["target"]])) for r in rels]
        assert len(pairs) == len(set(pairs))


class TestIntegrityGraphWriteback:
    """Tests the write_integrity_graph_edges logic from
    scripts/build_integrity_engine.py by exercising it against a real
    (temporary) SQLite DB -- this is the piece that connects detected
    conflicts/duplicates back into the graph as conflicts_with/duplicate_of
    edges, which did not exist before this change."""

    def test_conflicts_with_edge_resolves_chunk_to_document_entity(self, tmp_path):
        import importlib.util

        sys.path.insert(0, str(ROOT / "backend"))
        from models import Base, Document, Chunk, Entity
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(f"sqlite:///{tmp_path}/test.db")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        doc_a = Document(doc_key="doc-a", title="A", department="X", doc_type="Policy",
                          version="1.0", authority_level=1, status="current", raw_text="a")
        doc_b = Document(doc_key="doc-b", title="B", department="X", doc_type="Policy",
                          version="1.0", authority_level=1, status="current", raw_text="b")
        session.add_all([doc_a, doc_b])
        session.flush()

        chunk_a = Chunk(document_id=doc_a.id, chunk_index=0, chunk_text="a")
        chunk_b = Chunk(document_id=doc_b.id, chunk_index=0, chunk_text="b")
        session.add_all([chunk_a, chunk_b])
        session.flush()

        entity_a = Entity(name="doc-a", entity_type="Policy", canonical=True)
        entity_b = Entity(name="doc-b", entity_type="Policy", canonical=True)
        session.add_all([entity_a, entity_b])
        session.commit()

        spec = importlib.util.spec_from_file_location(
            "build_integrity_engine", ROOT / "scripts" / "build_integrity_engine.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        chunks = [
            {"chunk_id": chunk_a.id, "document_id": doc_a.id, "doc_key": "doc-a"},
            {"chunk_id": chunk_b.id, "document_id": doc_b.id, "doc_key": "doc-b"},
        ]
        contradictions = [{"chunk_a_id": chunk_a.id, "chunk_b_id": chunk_b.id}]

        created = mod.write_integrity_graph_edges(session, chunks, contradictions, [], [])
        assert created == 1

        from models import Relationship
        rel = session.query(Relationship).filter_by(relation_type="conflicts_with").first()
        assert rel is not None
        assert {rel.source_entity_id, rel.target_entity_id} == {entity_a.id, entity_b.id}

        # idempotency: running again must not create a duplicate edge
        created_again = mod.write_integrity_graph_edges(session, chunks, contradictions, [], [])
        assert created_again == 0
        assert session.query(Relationship).filter_by(relation_type="conflicts_with").count() == 1

        session.close()
