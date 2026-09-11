"""
Reciprocal Rank Fusion (RRF) -- Cormack, Clarke & Buettcher, 2009.

Combines multiple ranked lists into one by summing 1/(k + rank) across
lists for each item, then re-sorting by that combined score. Chosen over a
tuned linear weighting of BM25/dense scores because RRF operates purely on
RANKS, not raw scores -- so it needs no score normalization (BM25 and
cosine similarity are on completely different scales) and has no
hyperparameter to overfit to a 15-18 query evaluation set beyond the
constant k, which is conventionally left at 60 and not tuned.
"""

RRF_K = 60  # standard constant from the original paper; deliberately not tuned per-query


def reciprocal_rank_fusion(
    ranked_lists: list[list[int]],
    k: int = RRF_K,
) -> list[tuple[int, float]]:
    """
    ranked_lists: e.g. [bm25_chunk_ids_best_first, dense_chunk_ids_best_first]
    Returns [(chunk_id, rrf_score), ...] sorted by rrf_score descending.
    An item that appears in more lists, or ranks higher within a list,
    gets a higher combined score.
    """
    scores: dict[int, float] = {}
    for ranked_list in ranked_lists:
        for rank, chunk_id in enumerate(ranked_list, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
