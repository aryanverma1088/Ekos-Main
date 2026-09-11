"""
Contradiction detection: groups numeric facts (see numeric_fact_extractor.py)
by (unit, context) across chunks from DIFFERENT, NON-SUPERSEDING documents.
A group with 2+ distinct values is a candidate contradiction.

Excludes chunk pairs whose documents are connected by a supersedes
relationship -- a value that changed between versions of the same policy is
an "outdated" finding (see integrity/versions/), not a "contradiction"
between two currently-valid sources.

Known limitation (see integrity/FINDINGS.md): this only catches
contradictions expressible as "same concept, different number" (e.g.
password expiration: 90 vs 180 days). Qualitative contradictions that don't
hinge on a number (e.g. differing access-approval rules) are NOT caught by
this rule-based fallback -- that class of case needs semantic/NLI reasoning,
which the original architecture plan assigns to an LLM. This sandboxed
environment has no network access to run one; see docs/architecture.md.
"""
from .numeric_fact_extractor import extract_numeric_facts

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from authority import higher_authority  # noqa: E402

SEVERITY_KEYWORDS_HIGH = {"security", "password", "access", "encryption", "incident"}
SEVERITY_KEYWORDS_MEDIUM = {"finance", "expense", "reimbursement", "budget"}


def _infer_severity(concept_context: str, department_a: str, department_b: str) -> str:
    text = (concept_context + " " + department_a + " " + department_b).lower()
    if any(kw in text for kw in SEVERITY_KEYWORDS_HIGH):
        return "high"
    if any(kw in text for kw in SEVERITY_KEYWORDS_MEDIUM):
        return "medium"
    return "low"


def detect_contradictions(
    chunk_records: list[dict],
    supersedes_doc_pairs: set[tuple[int, int]],
) -> list[dict]:
    """
    chunk_records: [{chunk_id, document_id, doc_key, department, authority_level, text}, ...]
    supersedes_doc_pairs: set of (document_id, document_id) pairs (either order)
        connected by a supersedes relationship, to exclude from contradiction
        detection (see module docstring).

    Returns: [{concept, chunk_a_id, chunk_b_id, value_a, value_b, severity,
               resolved_doc_key, detection_method}, ...]
    """
    facts_by_context: dict[str, list[dict]] = {}

    for chunk in chunk_records:
        facts = extract_numeric_facts(chunk["text"])
        for f in facts:
            facts_by_context.setdefault(f["context_key"], []).append({
                **f,
                "chunk_id": chunk["chunk_id"],
                "document_id": chunk["document_id"],
                "doc_key": chunk["doc_key"],
                "department": chunk["department"],
                "authority_level": chunk["authority_level"],
            })

    results = []
    seen_pairs = set()

    for context_key, facts in facts_by_context.items():
        distinct_values = {f["value"] for f in facts}
        if len(distinct_values) < 2:
            continue

        # all pairwise combinations within this concept group with differing values
        for i in range(len(facts)):
            for j in range(i + 1, len(facts)):
                a, b = facts[i], facts[j]
                if a["value"] == b["value"]:
                    continue
                if a["document_id"] == b["document_id"]:
                    continue

                doc_pair = (a["document_id"], b["document_id"])
                if doc_pair in supersedes_doc_pairs or doc_pair[::-1] in supersedes_doc_pairs:
                    continue  # version change, not a contradiction -- see integrity/versions/

                pair_key = tuple(sorted([a["chunk_id"], b["chunk_id"]]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # resolve by authority level -- centralized in authority.py so
                # this logic (lower integer = higher authority) is never re-derived
                winning_level = higher_authority(a["authority_level"], b["authority_level"])
                resolved_doc_key = a["doc_key"] if a["authority_level"] == winning_level else b["doc_key"]

                concept = context_key.split("::", 1)[1] or context_key
                severity = _infer_severity(context_key, a["department"], b["department"])

                results.append({
                    "concept": concept,
                    "chunk_a_id": a["chunk_id"],
                    "chunk_b_id": b["chunk_id"],
                    "value_a": a["raw_match"],
                    "value_b": b["raw_match"],
                    "severity": severity,
                    "resolved_doc_key": resolved_doc_key,
                    "detection_method": "rule",
                })

    return results
