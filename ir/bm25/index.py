"""
BM25 retrieval index over EKOS chunks.

Decoupled from the database on purpose: build() takes plain (chunk_id, text)
pairs, so this module has no dependency on SQLAlchemy/backend internals and
can be unit tested or reused (e.g. from evaluation/) without spinning up a
DB session.
"""
import pickle
from pathlib import Path

from rank_bm25 import BM25Okapi

from .tokenizer import tokenize


class BM25Index:
    def __init__(self):
        self._bm25: BM25Okapi | None = None
        self._chunk_ids: list[int] = []

    def build(self, chunk_records: list[tuple[int, str]]) -> None:
        """chunk_records: list of (chunk_id, chunk_text)."""
        if not chunk_records:
            raise ValueError("Cannot build a BM25 index over zero chunks")

        self._chunk_ids = [cid for cid, _ in chunk_records]
        tokenized_corpus = [tokenize(text) for _, text in chunk_records]
        self._bm25 = BM25Okapi(tokenized_corpus)

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """Returns [(chunk_id, bm25_score), ...] sorted by score descending.
        Only chunks with a positive score are returned -- a score of 0 means
        no query term matched that chunk at all, which is not a meaningful
        BM25 result and should not count as "retrieved" for evaluation."""
        if self._bm25 is None:
            raise RuntimeError("BM25Index.build() must be called (or load()) before search()")

        tokenized_query = tokenize(query)
        scores = self._bm25.get_scores(tokenized_query)

        ranked = sorted(zip(self._chunk_ids, scores), key=lambda x: x[1], reverse=True)
        ranked = [(cid, float(score)) for cid, score in ranked if score > 0]
        return ranked[:top_k]

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"bm25": self._bm25, "chunk_ids": self._chunk_ids}, f)

    @classmethod
    def load(cls, path: str | Path) -> "BM25Index":
        with open(path, "rb") as f:
            data = pickle.load(f)
        instance = cls()
        instance._bm25 = data["bm25"]
        instance._chunk_ids = data["chunk_ids"]
        return instance
