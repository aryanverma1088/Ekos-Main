"""
Rule-based relationship extraction.

Two sources, both fully rule-based (no LLM):

1. Metadata-derived relations (confidence 1.0 -- directly encoded in the
   document's frontmatter, no inference involved):
   - owned_by:   Document -> Department (owner field)
   - belongs_to: Document -> Department (department field, when different
                 from owner -- e.g. project-atlas-charter is department
                 "Projects" but owner "Marketing")
   - created_by: Document -> Person (author field, skipped for team names)
   - supersedes: Document -> Document (supersedes_doc_key field)
   - applies_to: Document -> Group("Employees") for company-wide Policy/
                 Handbook docs, or Document -> Department for SOPs (which
                 are department-internal procedures)

2. Text-pattern relations (confidence 0.9-1.0 -- detected by scanning
   document text against a small set of precision-first patterns; see
   knowledge/entities/extract_entities.py for the extraction patterns
   themselves, which this module turns into graph edges):
   - references:  Document -> Document (title mentioned in another
                  document's body)
   - manages:     Team -> Document (explicit "X team owns/manages" statement)
   - related_to:  Document -> Project (title names a project) OR
                  Document -> Document (shared non-generic tag, weaker
                  signal, capped at confidence 0.6)
   - defines:     Document -> Concept (formal "X is defined as/means"
                  statement -- the graph-level view of the same signal
                  the definition-conflict detector uses)

Confidence deliberately distinguishes source strength: metadata relations
are ground truth (1.0), explicit text statements are high-confidence but
not infallible (0.9), and tag-overlap is a real but weaker topical signal
(0.6) -- not asserted with the same confidence as an explicit statement.

Note: conflicts_with and duplicate_of edges are NOT produced by this
module. They're derived from the integrity engine's actual detections
(Conflict/Duplicate DB rows), not from static text patterns, and are
written directly by scripts/build_integrity_engine.py after detection
runs -- see that script for why the ordering matters.
"""
from ..entities.extract_entities import extract_team_mentions, extract_project_names, extract_concept_terms

MIN_TITLE_LENGTH_FOR_MATCHING = 10  # avoid matching on short/generic titles


def extract_metadata_relationships(documents: list[dict]) -> list[dict]:
    """
    documents: list of dicts with doc_key, department, owner, author,
    doc_type, supersedes_doc_key, id (all from backend.models.Document).

    Returns: list of {source, source_type, target, target_type, relation_type, confidence}
    where source/target are entity names (resolved to entity_id by the caller,
    since this module has no DB dependency).
    """
    rels = []
    by_key = {d["doc_key"]: d for d in documents}

    def add(source, source_type, target, target_type, relation_type, confidence=1.0):
        rels.append({
            "source": source, "source_type": source_type,
            "target": target, "target_type": target_type,
            "relation_type": relation_type, "confidence": confidence,
        })

    for doc in documents:
        doc_key = doc["doc_key"]

        if doc.get("owner"):
            add(doc_key, "Document", doc["owner"], "Department", "owned_by")

        if doc["department"] and doc.get("owner") and doc["department"] != doc["owner"]:
            add(doc_key, "Document", doc["department"], "Department", "belongs_to")
        elif not doc.get("owner"):
            add(doc_key, "Document", doc["department"], "Department", "belongs_to")

        author = doc.get("author")
        if author and not author.strip().endswith("Team"):
            add(doc_key, "Document", author, "Person", "created_by")

        if doc.get("supersedes_doc_key"):
            target_key = doc["supersedes_doc_key"]
            if target_key in by_key:
                add(doc_key, "Document", target_key, "Document", "supersedes")

        if doc["doc_type"] in ("Policy", "Handbook"):
            add(doc_key, "Document", "Employees", "Group", "applies_to")
        elif doc["doc_type"] == "SOP":
            add(doc_key, "Document", doc["department"], "Department", "applies_to")

    return rels


def extract_text_reference_relationships(documents: list[dict]) -> list[dict]:
    """
    documents: list of dicts with doc_key, title, raw_text.

    Scans each document's body for other documents' titles (as a whole,
    case-insensitive substring, with whitespace normalized so a title that
    happens to wrap across a line break in the source markdown -- e.g.
    "...and Device\\nPolicy." -- still matches "Device Policy"). Deliberately
    excludes self-matches, matches against a document's own supersession
    chain (referring to your own older version isn't a cross-reference),
    and -- importantly -- matches against any *other* document that shares
    the source document's own title (two versions of the same policy share
    a title, so a document's own H1 heading would otherwise spuriously
    "match" its sibling version and create a nonsensical backward-in-time
    reference; this was caught by manually inspecting the extracted edges
    against the source text during development).
    """
    rels = []
    title_to_keys: dict[str, list[str]] = {}
    for doc in documents:
        title = doc["title"]
        if len(title) >= MIN_TITLE_LENGTH_FOR_MATCHING:
            title_to_keys.setdefault(title.lower(), []).append(doc["doc_key"])

    supersedes_pairs = {
        (d["doc_key"], d["supersedes_doc_key"])
        for d in documents if d.get("supersedes_doc_key")
    }

    def normalize(text: str) -> str:
        return " ".join(text.split())

    for doc in documents:
        body_normalized = normalize(doc["raw_text"]).lower()
        own_title_lower = doc["title"].lower()

        for title_lower, target_keys in title_to_keys.items():
            if title_lower == own_title_lower:
                continue  # a document's own heading trivially "matches" any sibling sharing its title
            if title_lower in own_title_lower:
                continue  # target's title is a substring of the source's OWN title (e.g. "Leave Policy"
                          # is a substring of "Parental Leave Policy") -- matching this just re-parses
                          # the source's own name, not a genuine mention of the other document

            for target_key in target_keys:
                if target_key == doc["doc_key"]:
                    continue
                if (doc["doc_key"], target_key) in supersedes_pairs:
                    continue  # already captured as 'supersedes', don't double-count as 'references'
                if title_lower in body_normalized:
                    rels.append({
                        "source": doc["doc_key"], "source_type": "Document",
                        "target": target_key, "target_type": "Document",
                        "relation_type": "references", "confidence": 0.9,
                    })

    return rels


def extract_team_relationships(documents: list[dict]) -> list[dict]:
    """Team --manages--> Document, from an explicit ownership/management
    statement in the document body (see extract_team_mentions in
    knowledge/entities/extract_entities.py for the pattern and why it's
    narrower than matching every "X team" mention)."""
    rels = []
    for doc in documents:
        for team_name in extract_team_mentions(doc.get("raw_text", "")):
            rels.append({
                "source": team_name, "source_type": "Team",
                "target": doc["doc_key"], "target_type": "Document",
                "relation_type": "manages", "confidence": 0.9,
            })
    return rels


def extract_project_relationships(documents: list[dict]) -> list[dict]:
    """Document --related_to--> Project, for documents whose title names a
    project ("Project Atlas Charter" -> Project Atlas)."""
    rels = []
    for doc in documents:
        for project_name in extract_project_names(doc["title"]):
            rels.append({
                "source": doc["doc_key"], "source_type": "Document",
                "target": project_name, "target_type": "Project",
                "relation_type": "related_to", "confidence": 1.0,
            })
    return rels


def extract_concept_relationships(documents: list[dict]) -> list[dict]:
    """Document --defines--> Concept, for documents containing a formal
    "X is defined as / X means" statement. This is the graph-level view of
    the same signal integrity/definitions/definition_conflict_detector.py
    uses to find cross-department definition conflicts -- a Concept node
    with 2+ incoming 'defines' edges from different departments is exactly
    a definition conflict, visible directly in the graph."""
    rels = []
    for doc in documents:
        for term in extract_concept_terms(doc.get("raw_text", "")):
            rels.append({
                "source": doc["doc_key"], "source_type": "Document",
                "target": term, "target_type": "Concept",
                "relation_type": "defines", "confidence": 0.9,
            })
    return rels


# Tags equal to a department or owner name just restate the belongs_to/
# owned_by relation already captured elsewhere -- excluded so related_to
# reflects genuine topical overlap, not a department name appearing twice.
def _generic_tag_stoplist(documents: list[dict]) -> set[str]:
    stoplist = set()
    for d in documents:
        if d.get("department"):
            stoplist.add(d["department"].lower())
        if d.get("owner"):
            stoplist.add(d["owner"].lower())
    return stoplist


def extract_tag_overlap_relationships(documents: list[dict]) -> list[dict]:
    """Document --related_to--> Document, for pairs sharing at least one
    non-generic tag. Weaker signal than references (0.9) or supersedes
    (1.0), so confidence is capped at 0.6. Excludes supersedes pairs (a
    version pair sharing tags with itself isn't a new finding) and
    generic department/owner-name tags (see _generic_tag_stoplist)."""
    stoplist = _generic_tag_stoplist(documents)
    supersedes_pairs = {
        (d["doc_key"], d["supersedes_doc_key"])
        for d in documents if d.get("supersedes_doc_key")
    }

    tag_sets = {}
    for d in documents:
        raw = d.get("tags") or ""
        tags = {t.strip().lower() for t in raw.split(",") if t.strip()}
        tag_sets[d["doc_key"]] = tags - stoplist

    rels = []
    seen_pairs = set()
    doc_keys = sorted(tag_sets.keys())

    for i in range(len(doc_keys)):
        for j in range(i + 1, len(doc_keys)):
            a, b = doc_keys[i], doc_keys[j]
            if (a, b) in supersedes_pairs or (b, a) in supersedes_pairs:
                continue
            shared = tag_sets[a] & tag_sets[b]
            if not shared:
                continue
            pair_key = tuple(sorted([a, b]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            rels.append({
                "source": a, "source_type": "Document",
                "target": b, "target_type": "Document",
                "relation_type": "related_to", "confidence": 0.6,
            })

    return rels


def extract_all_relationships(documents: list[dict]) -> list[dict]:
    return (
        extract_metadata_relationships(documents)
        + extract_text_reference_relationships(documents)
        + extract_team_relationships(documents)
        + extract_project_relationships(documents)
        + extract_concept_relationships(documents)
        + extract_tag_overlap_relationships(documents)
    )
