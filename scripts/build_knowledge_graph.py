"""
Builds the knowledge graph:
  1. Extracts entities + relationships from the current DB (rule-based,
     see knowledge/entities/extract_entities.py and
     knowledge/extraction/extract_relationships.py)
  2. Persists them to the entities/relationships SQLite tables (so
     GET /dashboard/metrics and GET /knowledge/entities reflect real counts)
  3. Builds a NetworkX graph and exports it to
     data/processed/knowledge_graph.json for the /knowledge/graph API and
     eventual frontend graph view.

Run this after every `python scripts/ingest.py`.

--reset clears existing entities/relationships tables first (safe to run
repeatedly; does NOT touch documents/chunks).
"""
import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from db import get_session                                          # noqa: E402
from models import Document, Chunk, Entity, Relationship             # noqa: E402
from knowledge.entities.extract_entities import extract_entities      # noqa: E402
from knowledge.extraction.extract_relationships import extract_all_relationships  # noqa: E402
from knowledge.graph.graph_builder import build_graph, to_node_link_json  # noqa: E402

GRAPH_EXPORT_PATH = ROOT / "data" / "processed" / "knowledge_graph.json"


def documents_as_dicts(session) -> list[dict]:
    docs = session.query(Document).all()
    result = []
    for d in docs:
        first_chunk = (
            session.query(Chunk)
            .filter_by(document_id=d.id)
            .order_by(Chunk.chunk_index)
            .first()
        )
        result.append({
            "doc_key": d.doc_key,
            "title": d.title,
            "department": d.department,
            "doc_type": d.doc_type,
            "owner": d.owner,
            "author": d.author,
            "supersedes_doc_key": d.supersedes_doc_key,
            "raw_text": d.raw_text,
            "first_chunk_id": first_chunk.id if first_chunk else None,
        })
    return result


def build(reset: bool = False):
    session = get_session()

    if reset:
        print("Clearing existing entities and relationships...")
        session.query(Relationship).delete()
        session.query(Entity).delete()
        session.commit()

    documents = documents_as_dicts(session)
    if not documents:
        print("No documents found. Run scripts/ingest.py first.")
        session.close()
        return

    # --- entities ---
    extracted_entities = extract_entities(documents)
    entity_id_by_key: dict[tuple[str, str], int] = {}

    for e in extracted_entities:
        key = (e["entity_type"], e["name"])
        existing = session.query(Entity).filter_by(entity_type=e["entity_type"], name=e["name"]).first()
        if existing:
            entity_id_by_key[key] = existing.id
            continue
        entity = Entity(
            name=e["name"],
            entity_type=e["entity_type"],
            first_seen_chunk_id=e["first_seen_chunk_id"],
            canonical=e["canonical"],
        )
        session.add(entity)
        session.flush()
        entity_id_by_key[key] = entity.id

    session.commit()
    print(f"Entities: {len(entity_id_by_key)}")

    # --- relationships ---
    # Document-type entities are stored under whatever entity_type
    # extract_entities mapped their doc_type to (Policy/Process/Documentation),
    # not a single "Document" type -- build a lookup from doc_key to whatever
    # entity_type/id it actually got.
    doc_key_to_entity_id = {}
    for doc in documents:
        for (etype, ename), eid in entity_id_by_key.items():
            if ename == doc["doc_key"]:
                doc_key_to_entity_id[doc["doc_key"]] = eid
                break

    def resolve_entity_id(name: str, hinted_type: str) -> int | None:
        if name in doc_key_to_entity_id:
            return doc_key_to_entity_id[name]
        for (etype, ename), eid in entity_id_by_key.items():
            if ename == name:
                return eid
        return None

    extracted_rels = extract_all_relationships(documents)

    created = 0
    skipped_unresolved = 0
    for r in extracted_rels:
        source_id = resolve_entity_id(r["source"], r["source_type"])
        target_id = resolve_entity_id(r["target"], r["target_type"])
        if source_id is None or target_id is None:
            skipped_unresolved += 1
            continue

        exists = (
            session.query(Relationship)
            .filter_by(source_entity_id=source_id, target_entity_id=target_id, relation_type=r["relation_type"])
            .first()
        )
        if exists:
            continue

        rel = Relationship(
            source_entity_id=source_id,
            target_entity_id=target_id,
            relation_type=r["relation_type"],
            confidence=r["confidence"],
        )
        session.add(rel)
        created += 1

    session.commit()
    print(f"Relationships: {created} created" + (f" ({skipped_unresolved} skipped, unresolved entity)" if skipped_unresolved else ""))

    # --- graph export ---
    all_entities = session.query(Entity).all()
    all_relationships = session.query(Relationship).all()
    session.close()

    entity_dicts = [{"id": e.id, "name": e.name, "entity_type": e.entity_type} for e in all_entities]
    rel_dicts = [
        {"source_entity_id": r.source_entity_id, "target_entity_id": r.target_entity_id,
         "relation_type": r.relation_type, "confidence": r.confidence}
        for r in all_relationships
    ]

    g = build_graph(entity_dicts, rel_dicts)
    graph_json = to_node_link_json(g)

    GRAPH_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_EXPORT_PATH.write_text(json.dumps(graph_json, indent=2))
    print(f"Graph exported to {GRAPH_EXPORT_PATH} ({len(graph_json['nodes'])} nodes, {len(graph_json['edges'])} edges)")
    if reset:
        print("\nNote: --reset clears ALL relationships, including conflicts_with/duplicate_of edges")
        print("written by scripts/build_integrity_engine.py. Re-run that script now to restore them.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    build(reset=args.reset)
