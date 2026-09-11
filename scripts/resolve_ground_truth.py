"""
Resolves the hand-authored ground truth files (which reference doc_key and
text snippets, since chunk_ids don't exist until after ingestion) into
concrete chunk_ids against the current database.

Run this after every `python scripts/ingest.py` (schema/dataset changes can
shift chunk_ids).

Output: data/processed/resolved_ground_truth.json
    {
      "queries":       [{query_id, query_text, category, relevant_chunk_ids}],
      "duplicates":     [{case_id, chunk_a_id, chunk_b_id, expected_similarity_min}],
      "contradictions": [{case_id, concept, chunk_a_id, chunk_b_id, severity, resolved_doc_key}],
      "outdated":       [{case_id, outdated_doc_id, current_doc_id}],
      "definitions":    [{case_id, term, chunk_a_id, chunk_b_id}]
    }

This resolved file -- not the hand-authored source files -- is what
evaluation/ and integrity/ scripts should read.
"""
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from db import get_session          # noqa: E402
from models import Document, Chunk  # noqa: E402

GT_DIR = SCRIPT_DIR.parent / "data" / "ground_truth"
OUT_PATH = SCRIPT_DIR.parent / "data" / "processed" / "resolved_ground_truth.json"


def load_json(name):
    with open(GT_DIR / name) as f:
        return json.load(f)


def chunk_ids_for_doc(session, doc_key: str) -> list[int]:
    doc = session.query(Document).filter_by(doc_key=doc_key).first()
    if doc is None:
        raise ValueError(f"Ground truth references unknown doc_key: {doc_key}")
    return [c.id for c in session.query(Chunk).filter_by(document_id=doc.id).order_by(Chunk.chunk_index).all()]


def chunk_id_for_snippet(session, doc_key: str, snippet: str) -> int:
    """Finds the chunk within doc_key whose text contains the given snippet.
    Falls back to the first chunk with a warning if no exact match is found
    (can happen if chunking merges/splits differently than expected)."""
    doc = session.query(Document).filter_by(doc_key=doc_key).first()
    if doc is None:
        raise ValueError(f"Ground truth references unknown doc_key: {doc_key}")
    chunks = session.query(Chunk).filter_by(document_id=doc.id).order_by(Chunk.chunk_index).all()

    normalized_snippet = " ".join(snippet.split())
    for c in chunks:
        normalized_text = " ".join(c.chunk_text.split())
        if normalized_snippet in normalized_text:
            return c.id

    print(f"  WARNING: snippet not found verbatim in {doc_key}, defaulting to first chunk. "
          f"Snippet: {snippet[:60]}...")
    return chunks[0].id


def resolve():
    session = get_session()
    resolved = {"queries": [], "duplicates": [], "contradictions": [], "outdated": [], "definitions": []}

    # --- queries ---
    for q in load_json("queries.json")["queries"]:
        relevant_ids = []
        for doc_key in q["relevant_docs"]:
            relevant_ids.extend(chunk_ids_for_doc(session, doc_key))
        resolved["queries"].append({
            "query_id": q["query_id"],
            "query_text": q["query_text"],
            "category": q["category"],
            "relevant_chunk_ids": relevant_ids,
        })

    # --- duplicates ---
    for case in load_json("duplicates.json")["cases"]:
        resolved["duplicates"].append({
            "case_id": case["case_id"],
            "chunk_a_id": chunk_id_for_snippet(session, case["doc_a"], case["snippet_a"]),
            "chunk_b_id": chunk_id_for_snippet(session, case["doc_b"], case["snippet_b"]),
            "expected_similarity_min": case["expected_similarity_min"],
        })

    # --- contradictions ---
    for case in load_json("contradictions.json")["cases"]:
        resolved["contradictions"].append({
            "case_id": case["case_id"],
            "concept": case["concept"],
            "chunk_a_id": chunk_id_for_snippet(session, case["doc_a"], case["snippet_a"]),
            "chunk_b_id": chunk_id_for_snippet(session, case["doc_b"], case["snippet_b"]),
            "severity": case["severity"],
            "resolved_doc_key": case["resolved_doc_key"],
        })

    # --- outdated ---
    for case in load_json("outdated.json")["cases"]:
        outdated_doc = session.query(Document).filter_by(doc_key=case["outdated_doc"]).first()
        current_doc = session.query(Document).filter_by(doc_key=case["current_doc"]).first()
        resolved["outdated"].append({
            "case_id": case["case_id"],
            "concept": case["concept"],
            "outdated_doc_id": outdated_doc.id,
            "current_doc_id": current_doc.id,
        })

    # --- definitions ---
    for case in load_json("definitions.json")["cases"]:
        resolved["definitions"].append({
            "case_id": case["case_id"],
            "term": case["term"],
            "chunk_a_id": chunk_id_for_snippet(session, case["doc_a"], case["definition_a"]),
            "chunk_b_id": chunk_id_for_snippet(session, case["doc_b"], case["definition_b"]),
        })

    session.close()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(resolved, f, indent=2)

    print(f"Resolved ground truth written to {OUT_PATH}")
    print(f"  queries: {len(resolved['queries'])}")
    print(f"  duplicates: {len(resolved['duplicates'])}")
    print(f"  contradictions: {len(resolved['contradictions'])}")
    print(f"  outdated: {len(resolved['outdated'])}")
    print(f"  definitions: {len(resolved['definitions'])}")


if __name__ == "__main__":
    resolve()
