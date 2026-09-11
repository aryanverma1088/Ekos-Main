"""
Outdated/superseded document detection.

Pure metadata -- walks the supersedes_doc_key chain already captured in
Document.status / Document.supersedes_doc_key at ingestion time (and
mirrored as 'supersedes' edges in the knowledge graph, Phase 5). No
similarity computation, no ambiguity: this is the one integrity detector
that achieves ~100% precision/recall by construction, since supersession
is an explicit fact from the source document's own frontmatter, not
something inferred from content.
"""


def detect_outdated(documents: list[dict]) -> list[dict]:
    """
    documents: [{doc_key, status, supersedes_doc_key, title}, ...]

    Returns: [{outdated_doc_key, current_doc_key, concept}, ...]
    for every document that has something superseding it (walking one hop --
    supersedes_doc_key on the current doc points directly at the outdated one).
    """
    by_key = {d["doc_key"]: d for d in documents}
    results = []

    for doc in documents:
        target_key = doc.get("supersedes_doc_key")
        if not target_key or target_key not in by_key:
            continue

        outdated_doc = by_key[target_key]
        results.append({
            "outdated_doc_key": target_key,
            "current_doc_key": doc["doc_key"],
            "concept": doc["title"],  # same title on both ends of a supersedes edge, by convention
        })

    return results


def find_supersedes_document_id_pairs(documents: list[dict]) -> set[tuple[int, int]]:
    """
    documents: [{id, supersedes_doc_key}, ...] where supersedes_doc_key
    resolves to another document's doc_key.

    Returns a set of (document_id, document_id) pairs connected by a
    supersedes relationship, for use by the contradiction/duplicate
    detectors to exclude version-pairs from their own findings (a value
    that changed between versions is an "outdated" story, not a
    "contradiction" or "duplicate" story).
    """
    by_key_to_id = {d["doc_key"]: d["id"] for d in documents}
    pairs = set()
    for doc in documents:
        target_key = doc.get("supersedes_doc_key")
        if target_key and target_key in by_key_to_id:
            pairs.add((doc["id"], by_key_to_id[target_key]))
    return pairs
