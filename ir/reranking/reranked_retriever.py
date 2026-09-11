"""
System D: Hybrid retrieval (BM25 + dense via RRF) followed by reranking of
the top candidates. Needs chunk text for reranking, so it takes a
chunk_id -> text lookup function rather than hitting the DB directly,
keeping this module free of any DB dependency.
"""
from typing import Callable

from ir.hybrid.hybrid_retriever import HybridRetriever, CANDIDATE_POOL_SIZE
from ir.reranking.base import Reranker


class HybridRerankRetriever:
    def __init__(self, hybrid_retriever: HybridRetriever, reranker: Reranker, chunk_text_lookup: Callable[[int], str]):
        self.hybrid_retriever = hybrid_retriever
        self.reranker = reranker
        self.chunk_text_lookup = chunk_text_lookup

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        candidates = self.hybrid_retriever.search(query, top_k=CANDIDATE_POOL_SIZE)
        candidate_pairs = [(cid, self.chunk_text_lookup(cid)) for cid, _ in candidates]

        reranked = self.reranker.rerank(query, candidate_pairs)
        return reranked[:top_k]
