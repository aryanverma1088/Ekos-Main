"""
Standard retrieval evaluation metrics. Implemented directly (no external
eval library) since each is ~10 lines and this project wants the metrics
themselves to be a legible, defensible part of the IR contribution.

All functions take:
    retrieved: list[int]   -- ranked chunk_ids returned by the system, best first
    relevant:  set[int]    -- ground-truth relevant chunk_ids for the query
"""
import math


def precision_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for cid in top_k if cid in relevant)
    return hits / len(top_k)


def recall_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    if not relevant:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for cid in top_k if cid in relevant)
    return hits / len(relevant)


def reciprocal_rank(retrieved: list[int], relevant: set[int]) -> float:
    """Reciprocal rank of the first relevant item in the ranked list (0 if none found)."""
    for rank, cid in enumerate(retrieved, start=1):
        if cid in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    """Binary-relevance nDCG@K (relevant items have gain 1, others gain 0)."""
    top_k = retrieved[:k]

    dcg = 0.0
    for i, cid in enumerate(top_k):
        if cid in relevant:
            dcg += 1.0 / math.log2(i + 2)  # +2 because rank is 1-indexed and log2(1)=0

    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))

    if idcg == 0:
        return 0.0
    return dcg / idcg


def evaluate_run(
    per_query_retrieved: dict[str, list[int]],
    per_query_relevant: dict[str, set[int]],
    k_values: tuple[int, ...] = (5, 10),
) -> dict:
    """
    Aggregates metrics across a full query set.

    Returns a dict of {metric_name: mean_value} plus a "per_query" breakdown,
    so results can be inspected at both the summary and per-query level.
    """
    per_query = {}
    for qid, retrieved in per_query_retrieved.items():
        relevant = per_query_relevant.get(qid, set())
        row = {"mrr": reciprocal_rank(retrieved, relevant)}
        for k in k_values:
            row[f"precision@{k}"] = precision_at_k(retrieved, relevant, k)
            row[f"recall@{k}"] = recall_at_k(retrieved, relevant, k)
            row[f"ndcg@{k}"] = ndcg_at_k(retrieved, relevant, k)
        per_query[qid] = row

    n = len(per_query) or 1
    summary = {"mrr": sum(r["mrr"] for r in per_query.values()) / n}
    for k in k_values:
        summary[f"precision@{k}"] = sum(r[f"precision@{k}"] for r in per_query.values()) / n
        summary[f"recall@{k}"] = sum(r[f"recall@{k}"] for r in per_query.values()) / n
        summary[f"ndcg@{k}"] = sum(r[f"ndcg@{k}"] for r in per_query.values()) / n

    return {"summary": summary, "per_query": per_query}
