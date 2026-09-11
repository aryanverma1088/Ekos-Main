"""
Definition conflict detection: extracts "X is defined as Y." / "X means Y."
statements via regex, groups by term, and flags terms defined differently
by documents from different departments.

Unlike contradictions.py, a definition conflict is NOT necessarily an
error -- two departments can legitimately use a term differently for their
own reporting purposes (e.g. Finance's "Customer" for revenue recognition
vs Marketing's "Customer" for funnel tracking). This detector surfaces the
divergence; it deliberately does not attempt to resolve one definition as
"correct" via authority level, unlike the contradiction detector.
"""
import re

DEFINITION_PATTERNS = [
    re.compile(r"\b([A-Z][a-zA-Z]{2,40})\s+is defined as\s+([^.]+)\."),
    re.compile(r"\b([A-Z][a-zA-Z]{2,40})\s+means\s+([^.]+)\."),
]

# Below this Jaccard word-overlap ratio, two definitions of the same term
# are considered meaningfully different (not just a trivial restatement).
DIFFERENCE_THRESHOLD = 0.5


def extract_definitions(text: str) -> list[dict]:
    """Returns [{term, definition_text}, ...]."""
    results = []
    for pattern in DEFINITION_PATTERNS:
        for m in pattern.finditer(text):
            term = m.group(1).strip()
            definition = m.group(2).strip()
            results.append({"term": term, "definition_text": definition})
    return results


def _jaccard_word_overlap(a: str, b: str) -> float:
    words_a = set(re.findall(r"[a-z]+", a.lower()))
    words_b = set(re.findall(r"[a-z]+", b.lower()))
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def detect_definition_conflicts(chunk_records: list[dict]) -> list[dict]:
    """
    chunk_records: [{chunk_id, document_id, department, text}, ...]

    Returns: [{term, chunk_a_id, chunk_b_id, definition_a, definition_b}, ...]
    for terms defined meaningfully differently by documents in different
    departments.
    """
    definitions_by_term: dict[str, list[dict]] = {}

    for chunk in chunk_records:
        for d in extract_definitions(chunk["text"]):
            term_key = d["term"].lower()
            definitions_by_term.setdefault(term_key, []).append({
                **d,
                "chunk_id": chunk["chunk_id"],
                "document_id": chunk["document_id"],
                "department": chunk["department"],
            })

    results = []
    seen_pairs = set()

    for term_key, defs in definitions_by_term.items():
        for i in range(len(defs)):
            for j in range(i + 1, len(defs)):
                a, b = defs[i], defs[j]
                if a["department"] == b["department"]:
                    continue  # same-department restatement isn't a cross-org conflict
                if a["chunk_id"] == b["chunk_id"]:
                    continue

                overlap = _jaccard_word_overlap(a["definition_text"], b["definition_text"])
                if overlap >= DIFFERENCE_THRESHOLD:
                    continue  # similar enough to be the same definition, not a conflict

                pair_key = tuple(sorted([a["chunk_id"], b["chunk_id"]]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                results.append({
                    "term": a["term"],
                    "chunk_a_id": a["chunk_id"],
                    "chunk_b_id": b["chunk_id"],
                    "definition_a": a["definition_text"],
                    "definition_b": b["definition_text"],
                })

    return results
