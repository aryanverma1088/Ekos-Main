"""
Abstract embedding encoder interface.

Why this exists: this sandboxed dev environment cannot reach huggingface.co
(see docs/architecture.md "Network constraint" note), so `sentence-transformers`
model weights cannot be downloaded here. Rather than block Phase 4 on that,
every dense-retrieval component is written against this interface. Two
implementations exist:

  - LSAEncoder (ir/embeddings/lsa_encoder.py): TF-IDF + TruncatedSVD (Latent
    Semantic Analysis). Pure scikit-learn, no network access needed, works
    everywhere. This is the DEFAULT and what all evaluation results in this
    repo were produced with.

  - SentenceTransformerEncoder (ir/embeddings/st_encoder.py): wraps a real
    sentence-transformers model (all-MiniLM-L6-v2). Produces genuinely
    semantic embeddings and should outperform LSA, especially on queries
    that are lexically dissimilar from the source text. Requires internet
    access (or a pre-populated local HF cache) the first time a model is
    loaded. Swap it in by changing ENCODER_TYPE in ir/embeddings/config.py --
    no other code changes needed, since everything downstream (DenseIndex,
    hybrid fusion, evaluation scripts) only depends on this interface.

Both implementations expose the same contract: fit once on the corpus,
then encode() any text (corpus or query) into a fixed-size vector.
"""
from abc import ABC, abstractmethod

import numpy as np


class Encoder(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier used in saved index metadata, e.g. 'lsa' or 'minilm-l6-v2'."""

    @abstractmethod
    def fit(self, corpus_texts: list[str]) -> None:
        """Fits the encoder on the full chunk corpus. For LSA this trains the
        TF-IDF vocabulary + SVD projection. For a pretrained transformer this
        is a no-op (the model is already trained) but is still called so the
        interface is uniform."""

    @abstractmethod
    def encode(self, texts: list[str]) -> np.ndarray:
        """Returns an (N, D) float32 array of embeddings, L2-normalized so
        that inner product == cosine similarity (required for the FAISS
        IndexFlatIP index used by DenseIndex)."""

    @abstractmethod
    def save(self, path: str) -> None:
        ...

    @abstractmethod
    def load(self, path: str) -> None:
        ...
