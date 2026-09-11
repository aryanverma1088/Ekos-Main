"""
Search result enrichment: turns a raw (chunk_id, score) retrieval hit into
something a reviewer can actually evaluate -- which terms matched, why this
method ranked it here, and a confidence figure that's honestly scoped.

On "confidence": BM25 scores are unbounded, cosine similarity is 0-1, RRF
scores are small fractions, and the TF-IDF reranker's scores are yet another
scale -- there is no single meaningful absolute "confidence" across all four
methods without a calibrated model backing it (which none of these fallback
implementations have). Rather than fabricate a fake universal percentage,
confidence here is explicitly RELATIVE: each result's score normalized
against the top score in its own result set, labeled as such in the API and
UI. That's an honest, real number -- "how strong is this match relative to
the best match for this query" -- not a claim of calibrated probability.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ir.bm25.tokenizer import tokenize  # noqa: E402

METHOD_EXPLANATIONS = {
    "bm25": "Ranked by lexical term overlap (BM25).",
    "dense": "Ranked by semantic similarity (dense retrieval).",
    "hybrid": "Ranked by combining lexical (BM25) and semantic signals via reciprocal rank fusion.",
    "hybrid_rerank": "Ranked by combined lexical + semantic retrieval, then rescored for relevance to your exact query.",
}


def matched_terms(query: str, chunk_text: str, limit: int = 6) -> list[str]:
    """Query terms that literally appear in this chunk, in query order,
    deduplicated. Empty for dense-only matches where there may be no
    literal term overlap at all -- that's an honest signal, not a bug."""
    q_tokens = tokenize(query)
    chunk_tokens = set(tokenize(chunk_text))
    seen = set()
    matched = []
    for t in q_tokens:
        if t in chunk_tokens and t not in seen:
            seen.add(t)
            matched.append(t)
    return matched[:limit]


def ranking_explanation(method: str, query: str, chunk_text: str) -> str:
    base = METHOD_EXPLANATIONS.get(method, "Ranked by relevance.")
    if method == "dense":
        return base  # LSA has no literal term-overlap explanation to add honestly
    terms = matched_terms(query, chunk_text)
    if terms:
        return f"{base} Matched terms: {', '.join(terms)}."
    return f"{base} No literal term overlap -- matched via the semantic component."


def relative_confidence(score: float, max_score_in_results: float) -> float:
    """Returns a 0-100 figure: this result's score as a percentage of the
    top score in its own result set. Explicitly relative -- see module
    docstring for why an absolute cross-method confidence isn't offered."""
    if max_score_in_results <= 0:
        return 0.0
    return round(min(100.0, max(0.0, (score / max_score_in_results) * 100)), 1)
