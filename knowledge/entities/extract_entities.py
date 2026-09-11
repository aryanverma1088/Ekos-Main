"""
Rule-based entity extraction.

Per docs/architecture.md: entities are extracted from structured metadata
we already have, plus a small set of precision-first text patterns -- not
a trained NER model. This gives high precision by construction, at the
cost of coverage versus an LLM extractor (documented tradeoff, not hidden).

Entity types produced here:
  - Policy / Process / Documentation  (one per ingested document, typed by
    doc_type; name = doc_key for uniqueness since two versions of the same
    policy share a title)
  - Department (from Document.department and Document.owner)
  - Team       (sub-department teams with an explicit ownership/management
                statement in the source text, e.g. "The Platform team owns
                the production deployment process" -- extracted via a
                verb-anchored pattern, not every incidental "X team"
                mention, to avoid noise; see extract_team_mentions())
  - Person     (from Document.author, when it looks like an individual --
                generic team names like "HR Team" are treated as an alias
                for the owning Department, not a separate Person entity)
  - Project    (named projects, e.g. "Project Atlas", extracted from
                document titles matching "Project <Name>")
  - Concept    (terms with a formal "X is defined as / X means" statement
                in the text -- see knowledge/extraction/extract_relationships.py
                for how these connect to documents via 'defines')
  - Group      (a single synthetic "Employees" entity, target of
                applies_to for company-wide policies)

Entity types intentionally NOT populated, and why: Regulation and Product
are part of the supported type vocabulary (see ENTITY_TYPES below) but this
corpus contains no document that names a specific external regulation or
company product, so no instances are fabricated. Role was considered
(e.g. "Senior Engineer" in eng-production-access-policy) but the source
text has no single low-false-positive-risk grammatical pattern for job
titles across the corpus ("Senior Engineers", "on-call engineer",
"department head" all phrase differently) -- extracting it reliably would
need either a curated title list (arbitrary) or an NER model (unavailable,
see docs/architecture.md network constraint). Left out rather than forced.

Returns entities as plain dicts (not ORM objects) so this module has no
DB dependency and can be unit tested in isolation.
"""
import re

# Full supported vocabulary, even though not every type has instances in
# this corpus -- documented above. Kept here so the type system itself is
# visible in one place rather than implied by whatever happens to be extracted.
ENTITY_TYPES = {
    "Policy", "Process", "Documentation", "Department", "Team", "Person",
    "Project", "Concept", "Group", "Regulation", "Product", "Role",
}

TEAM_NAME_SUFFIXES = ("Team",)  # "HR Team", "IT Team" -> department aliases, not Person entities

DOCUMENT_TYPE_MAP = {
    "Policy": "Policy",
    "SOP": "Process",
    "Handbook": "Documentation",
    "Documentation": "Documentation",
    "ProjectDocumentation": "Documentation",
    "MeetingNotes": "Documentation",
}

# Anchored on an ownership/management verb immediately after "<Name> team" --
# deliberately narrower than matching every "X team" mention (which would
# also pull in "Marketing team", "SDR team", "support team" on incidental
# mentions with no real relationship to extract). Verified against the
# actual corpus during development: matches "Platform team owns..." and
# nothing else, which is the correct precision/recall tradeoff here.
TEAM_OWNERSHIP_PATTERN = re.compile(
    r"\b([A-Z][a-zA-Z]+) team (?:owns|manages|is responsible for|leads)\b"
)

# "Project Atlas", "Project Nova" -- matched against document titles, the
# most reliable signal (body text is more prone to false positives, e.g.
# "project documentation" as a generic phrase rather than a proper name).
PROJECT_NAME_PATTERN = re.compile(r"\bProject ([A-Z][a-zA-Z]+)\b")

DEFINITION_PATTERNS = [
    re.compile(r"\b([A-Z][a-zA-Z]{2,40})\s+is defined as\s+"),
    re.compile(r"\b([A-Z][a-zA-Z]{2,40})\s+means\s+"),
]


def is_team_name(author: str) -> bool:
    return any(author.strip().endswith(suffix) for suffix in TEAM_NAME_SUFFIXES)


def extract_team_mentions(text: str) -> list[str]:
    """Returns team names with an explicit ownership/management statement
    in this text (see TEAM_OWNERSHIP_PATTERN docstring above)."""
    return sorted(set(TEAM_OWNERSHIP_PATTERN.findall(text)))


def extract_project_names(title: str) -> list[str]:
    """Returns full project names ('Project Atlas') found in a document title."""
    return [f"Project {m}" for m in PROJECT_NAME_PATTERN.findall(title)]


def extract_concept_terms(text: str) -> list[str]:
    """Returns terms with a formal definition statement in this text."""
    terms = []
    for pattern in DEFINITION_PATTERNS:
        terms.extend(pattern.findall(text))
    return sorted(set(terms))


def extract_entities(documents: list[dict]) -> list[dict]:
    """
    documents: list of dicts with doc_key, title, department, doc_type,
    owner, author, raw_text, first_chunk_id.

    Returns: list of {name, entity_type, first_seen_chunk_id, canonical}
    """
    entities = {}  # (entity_type, name) -> entity dict, dedupes automatically

    def add(entity_type: str, name: str, first_seen_chunk_id: int | None = None):
        key = (entity_type, name)
        if key not in entities:
            entities[key] = {
                "entity_type": entity_type,
                "name": name,
                "first_seen_chunk_id": first_seen_chunk_id,
                "canonical": True,
            }

    # Synthetic "Employees" group, target of applies_to for company-wide policies
    add("Group", "Employees")

    for doc in documents:
        chunk_id = doc.get("first_chunk_id")

        entity_type = DOCUMENT_TYPE_MAP.get(doc["doc_type"], "Documentation")
        add(entity_type, doc["doc_key"], chunk_id)

        # Department entities: both the owning/authoring department and the
        # declared department field (these differ for e.g. project-atlas-charter:
        # department=Projects, owner=Marketing)
        add("Department", doc["department"])
        if doc.get("owner"):
            add("Department", doc["owner"])

        # Person entities, skipping generic team names
        author = doc.get("author")
        if author and not is_team_name(author):
            add("Person", author)

        text = doc.get("raw_text", "")

        for team_name in extract_team_mentions(text):
            add("Team", team_name, chunk_id)

        for project_name in extract_project_names(doc["title"]):
            add("Project", project_name, chunk_id)

        for term in extract_concept_terms(text):
            add("Concept", term, chunk_id)

    return list(entities.values())
