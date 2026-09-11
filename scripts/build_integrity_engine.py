"""
Runs the full integrity engine:
  1. Outdated detection (metadata-driven, ~100% precision by construction)
  2. Duplicate detection (TF-IDF cosine + union-find clustering)
  3. Contradiction detection (numeric-fact grouping)
  4. Definition conflict detection (regex extraction + cross-department diff)

Persists duplicates/conflicts to SQLite (idempotent -- re-running without
--reset checks for existing chunk-pair matches before inserting, so it's
safe to run multiple times without creating duplicate database rows), then
validates each detector against the hand-labeled ground truth in
data/ground_truth/, printing precision/recall/exact findings rather than
just "it ran".

Run after scripts/ingest.py and scripts/resolve_ground_truth.py.
--reset clears existing duplicates/conflicts tables first.
"""
import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from db import get_session                                      # noqa: E402
from models import Document, Chunk, Duplicate, Conflict, Entity, Relationship  # noqa: E402
from integrity.versions.outdated_detector import (                 # noqa: E402
    detect_outdated, find_supersedes_document_id_pairs
)
from integrity.duplicates.duplicate_detector import detect_duplicates       # noqa: E402
from integrity.contradictions.contradiction_detector import detect_contradictions  # noqa: E402
from integrity.definitions.definition_conflict_detector import detect_definition_conflicts  # noqa: E402
from knowledge.graph.graph_builder import build_graph, to_node_link_json          # noqa: E402

RESOLVED_GT_PATH = ROOT / "data" / "processed" / "resolved_ground_truth.json"
RESULTS_PATH = ROOT / "data" / "processed" / "integrity_results.json"
GRAPH_EXPORT_PATH = ROOT / "data" / "processed" / "knowledge_graph.json"


def write_integrity_graph_edges(session, chunks, contradictions, definitions, duplicates):
    """
    Writes conflicts_with and duplicate_of edges into the knowledge graph
    from what the integrity engine actually detected -- these did NOT
    exist before: the graph (Phase 5) and the integrity engine (Phase 6)
    were built as separate systems that never wrote back to each other.
    A document's conflicts are real, detected facts; the graph should
    show them like any other relationship, not just list them on a
    separate page.

    Requires entities to already exist (scripts/build_knowledge_graph.py
    must run first). If you re-run that script with --reset AFTER this
    one, it wipes these edges along with everything else -- re-run this
    script again afterward to restore them. Idempotent: safe to run
    multiple times, never creates duplicate edges for the same pair+type.
    """
    chunk_to_doc_id = {c["chunk_id"]: c["document_id"] for c in chunks}
    doc_id_to_key = {}  # filled from the documents already loaded by the caller via chunks' doc_key
    for c in chunks:
        doc_id_to_key[c["document_id"]] = c["doc_key"]

    entities = session.query(Entity).filter(Entity.name.in_(doc_id_to_key.values())).all()
    doc_key_to_entity_id = {e.name: e.id for e in entities}

    if not doc_key_to_entity_id:
        print("  (skipping graph edge writeback -- no matching entities found; "
              "run scripts/build_knowledge_graph.py first)")
        return 0

    def resolve_entity_id(chunk_id):
        doc_id = chunk_to_doc_id.get(chunk_id)
        doc_key = doc_id_to_key.get(doc_id)
        return doc_key_to_entity_id.get(doc_key)

    def upsert_edge(source_id, target_id, relation_type, confidence):
        if source_id is None or target_id is None or source_id == target_id:
            return False
        exists = (
            session.query(Relationship)
            .filter_by(source_entity_id=source_id, target_entity_id=target_id, relation_type=relation_type)
            .first()
        )
        reverse_exists = (
            session.query(Relationship)
            .filter_by(source_entity_id=target_id, target_entity_id=source_id, relation_type=relation_type)
            .first()
        )
        if exists or reverse_exists:
            return False
        session.add(Relationship(
            source_entity_id=source_id, target_entity_id=target_id,
            relation_type=relation_type, confidence=confidence,
        ))
        return True

    created = 0
    for c in contradictions + definitions:
        a_id = resolve_entity_id(c["chunk_a_id"])
        b_id = resolve_entity_id(c["chunk_b_id"])
        if upsert_edge(a_id, b_id, "conflicts_with", 1.0):
            created += 1

    for d in duplicates:
        a_id = resolve_entity_id(d["chunk_a_id"])
        b_id = resolve_entity_id(d["chunk_b_id"])
        if upsert_edge(a_id, b_id, "duplicate_of", d["similarity_score"]):
            created += 1

    session.commit()
    return created


def load_documents(session):
    docs = session.query(Document).all()
    return [{
        "id": d.id, "doc_key": d.doc_key, "title": d.title, "department": d.department,
        "status": d.status, "supersedes_doc_key": d.supersedes_doc_key,
        "authority_level": d.authority_level,
    } for d in docs]


def load_chunks(session):
    chunks = session.query(Chunk).all()
    doc_by_id = {d.id: d for d in session.query(Document).all()}
    return [{
        "chunk_id": c.id, "document_id": c.document_id, "text": c.chunk_text,
        "doc_key": doc_by_id[c.document_id].doc_key,
        "department": doc_by_id[c.document_id].department,
        "authority_level": doc_by_id[c.document_id].authority_level,
    } for c in chunks]


def validate_against_ground_truth(outdated, duplicates, contradictions, definitions):
    if not RESOLVED_GT_PATH.exists():
        print("(no resolved ground truth found -- run scripts/resolve_ground_truth.py to enable validation)")
        return

    gt = json.loads(RESOLVED_GT_PATH.read_text())

    print("\n--- Validation against ground truth ---")

    # duplicates
    gt_dup_pairs = {tuple(sorted([c["chunk_a_id"], c["chunk_b_id"]])) for c in gt["duplicates"]}
    found_dup_pairs = {tuple(sorted([d["chunk_a_id"], d["chunk_b_id"]])) for d in duplicates}
    dup_hits = gt_dup_pairs & found_dup_pairs
    print(f"Duplicates:     {len(dup_hits)}/{len(gt_dup_pairs)} ground-truth cases found "
          f"({len(found_dup_pairs)} total detected)")

    # contradictions
    gt_conf_pairs = {tuple(sorted([c["chunk_a_id"], c["chunk_b_id"]])) for c in gt["contradictions"]}
    found_conf_pairs = {tuple(sorted([c["chunk_a_id"], c["chunk_b_id"]])) for c in contradictions}
    conf_hits = gt_conf_pairs & found_conf_pairs
    print(f"Contradictions: {len(conf_hits)}/{len(gt_conf_pairs)} ground-truth cases found "
          f"({len(found_conf_pairs)} total detected)")

    # outdated
    gt_outdated_ids = {(c["outdated_doc_id"], c["current_doc_id"]) for c in gt["outdated"]}
    found_outdated_ids = {(o["outdated_doc_id"], o["current_doc_id"]) for o in outdated}
    outdated_hits = gt_outdated_ids & found_outdated_ids
    print(f"Outdated:       {len(outdated_hits)}/{len(gt_outdated_ids)} ground-truth cases found "
          f"({len(found_outdated_ids)} total detected)")

    # definitions
    gt_def_pairs = {tuple(sorted([c["chunk_a_id"], c["chunk_b_id"]])) for c in gt["definitions"]}
    found_def_pairs = {tuple(sorted([d["chunk_a_id"], d["chunk_b_id"]])) for d in definitions}
    def_hits = gt_def_pairs & found_def_pairs
    print(f"Definitions:    {len(def_hits)}/{len(gt_def_pairs)} ground-truth cases found "
          f"({len(found_def_pairs)} total detected)")

    print("\nSee integrity/FINDINGS.md for the full honest analysis of these results,")
    print("including why duplicate detection scores 0/2 with the fallback lexical method.")


def run(reset: bool = False):
    session = get_session()

    if reset:
        print("Clearing existing duplicates and conflicts...")
        session.query(Duplicate).delete()
        session.query(Conflict).delete()
        session.commit()

    documents = load_documents(session)
    chunks = load_chunks(session)

    if not documents:
        print("No documents found. Run scripts/ingest.py first.")
        session.close()
        return

    doc_by_key = {d["doc_key"]: d for d in documents}
    chunk_by_doc = {}
    for c in chunks:
        chunk_by_doc.setdefault(c["document_id"], c)  # first chunk per doc, used for outdated finding evidence

    # --- 1. outdated (metadata) ---
    outdated_raw = detect_outdated(documents)
    outdated = []
    for o in outdated_raw:
        outdated_doc = doc_by_key[o["outdated_doc_key"]]
        current_doc = doc_by_key[o["current_doc_key"]]
        outdated.append({
            "outdated_doc_id": outdated_doc["id"],
            "current_doc_id": current_doc["id"],
            "concept": o["concept"],
        })
    print(f"Outdated: {len(outdated)} supersession chains found")

    supersedes_doc_pairs = find_supersedes_document_id_pairs(documents)

    # --- 2. duplicates ---
    chunk_tuples = [(c["chunk_id"], c["document_id"], c["text"]) for c in chunks]
    duplicates = detect_duplicates(chunk_tuples, supersedes_doc_pairs)
    print(f"Duplicates: {len(duplicates)} pairs found ({len({d['cluster_id'] for d in duplicates})} clusters)")

    for d in duplicates:
        exists = (
            session.query(Duplicate)
            .filter_by(chunk_a_id=d["chunk_a_id"], chunk_b_id=d["chunk_b_id"])
            .first()
        )
        if exists:
            continue
        session.add(Duplicate(
            chunk_a_id=d["chunk_a_id"], chunk_b_id=d["chunk_b_id"],
            similarity_score=d["similarity_score"], cluster_id=d["cluster_id"],
        ))

    # --- 3. contradictions ---
    contradictions = detect_contradictions(chunks, supersedes_doc_pairs)
    print(f"Contradictions: {len(contradictions)} found")

    for c in contradictions:
        exists = (
            session.query(Conflict)
            .filter_by(conflict_type="contradiction", chunk_a_id=c["chunk_a_id"], chunk_b_id=c["chunk_b_id"])
            .first()
        )
        if exists:
            continue
        session.add(Conflict(
            concept=c["concept"], conflict_type="contradiction",
            chunk_a_id=c["chunk_a_id"], chunk_b_id=c["chunk_b_id"],
            value_a=c["value_a"], value_b=c["value_b"],
            severity=c["severity"], resolved_doc_key=c["resolved_doc_key"],
            detection_method=c["detection_method"],
        ))

    # --- 4. definition conflicts ---
    definitions = detect_definition_conflicts(chunks)
    print(f"Definition conflicts: {len(definitions)} found")

    for d in definitions:
        exists = (
            session.query(Conflict)
            .filter_by(conflict_type="definition", chunk_a_id=d["chunk_a_id"], chunk_b_id=d["chunk_b_id"])
            .first()
        )
        if exists:
            continue
        session.add(Conflict(
            concept=d["term"], conflict_type="definition",
            chunk_a_id=d["chunk_a_id"], chunk_b_id=d["chunk_b_id"],
            value_a=d["definition_a"][:250], value_b=d["definition_b"][:250],
            severity="medium", resolved_doc_key=None,
            detection_method="rule",
        ))

    session.commit()

    graph_edges_created = write_integrity_graph_edges(session, chunks, contradictions, definitions, duplicates)
    print(f"Graph edges: {graph_edges_created} conflicts_with/duplicate_of edges written to knowledge graph")

    # Re-export the static graph snapshot so it includes the edges just written --
    # without this, data/processed/knowledge_graph.json goes stale immediately
    # after this script runs (the API itself is unaffected, since /knowledge/graph
    # always rebuilds live from the DB; this is purely for external tooling that
    # reads the static file, e.g. diagram generation).
    all_entities = session.query(Entity).all()
    all_relationships = session.query(Relationship).all()
    entity_dicts = [{"id": e.id, "name": e.name, "entity_type": e.entity_type} for e in all_entities]
    rel_dicts = [
        {"source_entity_id": r.source_entity_id, "target_entity_id": r.target_entity_id,
         "relation_type": r.relation_type, "confidence": r.confidence}
        for r in all_relationships
    ]
    g = build_graph(entity_dicts, rel_dicts)
    graph_json = to_node_link_json(g)
    GRAPH_EXPORT_PATH.write_text(json.dumps(graph_json, indent=2))
    print(f"Re-exported {GRAPH_EXPORT_PATH} ({len(graph_json['nodes'])} nodes, {len(graph_json['edges'])} edges)")

    session.close()

    RESULTS_PATH.write_text(json.dumps({
        "outdated": outdated, "duplicates": duplicates,
        "contradictions": contradictions, "definitions": definitions,
    }, indent=2))
    print(f"\nFull results written to {RESULTS_PATH}")

    validate_against_ground_truth(outdated, duplicates, contradictions, definitions)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    run(reset=args.reset)
