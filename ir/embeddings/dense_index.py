"""
Dense retrieval index: encoder + FAISS flat inner-product index.

Mirrors ir/bm25/index.py's shape (build/search/save/load over
(chunk_id, text) pairs) so evaluation scripts can treat BM25Index and
DenseIndex interchangeably.

Uses IndexFlatIP (exact, not approximate) since the corpus is small
(tens of chunks for this course project) -- no need for IVF/HNSW indexing
at this scale, and flat search is exact (no recall loss from approximation),
which matters for a clean evaluation comparison.
"""
import json
import pickle
from pathlib import Path

import faiss
import numpy as np

from .base import Encoder


class DenseIndex:
    def __init__(self, encoder: Encoder):
        self.encoder = encoder
        self._faiss_index: faiss.Index | None = None
        self._chunk_ids: list[int] = []

    def build(self, chunk_records: list[tuple[int, str]]) -> None:
        """chunk_records: list of (chunk_id, chunk_text)."""
        if not chunk_records:
            raise ValueError("Cannot build a dense index over zero chunks")

        self._chunk_ids = [cid for cid, _ in chunk_records]
        texts = [text for _, text in chunk_records]

        self.encoder.fit(texts)
        vectors = self.encoder.encode(texts)

        dim = vectors.shape[1]
        self._faiss_index = faiss.IndexFlatIP(dim)
        self._faiss_index.add(vectors)

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """Returns [(chunk_id, cosine_similarity), ...] sorted by score descending."""
        if self._faiss_index is None:
            raise RuntimeError("DenseIndex.build() (or load()) must be called before search()")

        query_vec = self.encoder.encode([query])
        scores, indices = self._faiss_index.search(query_vec, min(top_k, len(self._chunk_ids)))

        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx == -1:
                continue
            results.append((self._chunk_ids[idx], float(score)))
        return results

    def save(self, dir_path: str | Path) -> None:
        dir_path = Path(dir_path)
        dir_path.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self._faiss_index, str(dir_path / "index.faiss"))
        with open(dir_path / "chunk_ids.pkl", "wb") as f:
            pickle.dump(self._chunk_ids, f)
        self.encoder.save(str(dir_path / "encoder.pkl"))
        with open(dir_path / "meta.json", "w") as f:
            json.dump({"encoder_name": self.encoder.name}, f)

    @classmethod
    def load(cls, dir_path: str | Path, encoder: Encoder) -> "DenseIndex":
        dir_path = Path(dir_path)

        meta = json.loads((dir_path / "meta.json").read_text())
        if meta["encoder_name"] != encoder.name:
            raise ValueError(
                f"Index was built with encoder '{meta['encoder_name']}' but you passed "
                f"encoder '{encoder.name}'. Rebuild the index with the current encoder "
                f"(scripts/build_dense_index.py --reset) or pass the matching encoder."
            )

        encoder.load(str(dir_path / "encoder.pkl"))

        instance = cls(encoder)
        instance._faiss_index = faiss.read_index(str(dir_path / "index.faiss"))
        with open(dir_path / "chunk_ids.pkl", "rb") as f:
            instance._chunk_ids = pickle.load(f)
        return instance
