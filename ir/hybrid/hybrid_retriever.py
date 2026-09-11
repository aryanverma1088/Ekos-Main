"""
Hybrid retrieval: runs BM25 and dense search independently, then fuses
their ranked lists with Reciprocal Rank Fusion. Exposes the same
search(query, top_k) -> [(chunk_id, score)] shape as BM25Index/DenseIndex.

Each underlying retriever is asked for a wider candidate pool
(CANDIDATE_POOL_SIZE) than the caller's requested top_k, so fusion has
enough material to work with even when the caller only wants a handful of
final results.
"""
from ir.bm25.index import BM25Index
from ir.embeddings.dense_index import DenseIndex
from ir.hybrid.rrf import reciprocal_rank_fusion

CANDIDATE_POOL_SIZE = 20


class HybridRetriever:
    def __init__(self, bm25_index: BM25Index, dense_index: DenseIndex):
        self.bm25_index = bm25_index
        self.dense_index = dense_index

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        bm25_results = self.bm25_index.search(query, top_k=CANDIDATE_POOL_SIZE)
        dense_results = self.dense_index.search(query, top_k=CANDIDATE_POOL_SIZE)

        bm25_ranked_ids = [cid for cid, _ in bm25_results]
        dense_ranked_ids = [cid for cid, _ in dense_results]

        fused = reciprocal_rank_fusion([bm25_ranked_ids, dense_ranked_ids])
        return fused[:top_k]
