"""
Abstract reranker interface. Same network-constraint story as
ir/embeddings/base.py: a real cross-encoder reranker needs a
sentence-transformers model download, which this sandboxed environment
can't do. Two implementations:

  - TfidfRerankerFallback (ir/reranking/tfidf_reranker.py): recomputes a
    fresh TF-IDF vector space over just the query + candidate set at
    query time (not the corpus-level TF-IDF used elsewhere) and rescores
    by cosine similarity. This is a genuinely different signal from BM25
    (no term-frequency saturation, no corpus-wide IDF) and from LSA (no
    dimensionality reduction) -- a legitimate, if modest, reranking step.
    No network access required. DEFAULT.

  - CrossEncoderReranker (ir/reranking/cross_encoder_reranker.py): wraps
    `cross-encoder/ms-marco-MiniLM-L-6-v2` via sentence-transformers.
    Jointly encodes (query, passage) pairs for a much stronger relevance
    signal than any bag-of-words method. Requires internet on first use.
    Swap in via ir/reranking/config.py.
"""
from abc import ABC, abstractmethod


class Reranker(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def rerank(self, query: str, candidates: list[tuple[int, str]]) -> list[tuple[int, float]]:
        """candidates: [(chunk_id, chunk_text), ...] in their pre-rerank order.
        Returns [(chunk_id, rerank_score), ...] sorted by score descending."""
