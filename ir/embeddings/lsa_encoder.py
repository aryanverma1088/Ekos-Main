"""
LSA (Latent Semantic Analysis) encoder: TF-IDF followed by TruncatedSVD.

This is a real, citable dense-retrieval technique (Deerwester et al., 1990)
predating neural embeddings -- it projects the sparse TF-IDF space down to a
small number of latent dimensions via SVD, capturing co-occurrence-based
"topics" rather than exact term overlap. It is not as strong as a modern
sentence embedding model at capturing paraphrase/synonymy, but it is a
legitimate and commonly-taught dense baseline, and critically: it needs
nothing but scikit-learn, so it works in any environment.

Used as the default dense encoder in this project because the sandboxed dev
environment cannot reach huggingface.co to download sentence-transformers
weights. See ir/embeddings/base.py for how to swap in a real transformer
encoder once running with internet access.
"""
import pickle

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

from .base import Encoder

DEFAULT_N_COMPONENTS = 100  # latent dimensions; capped at min(n_components, n_chunks-1, n_features-1) internally


class LSAEncoder(Encoder):
    def __init__(self, n_components: int = DEFAULT_N_COMPONENTS, random_state: int = 42):
        self.n_components = n_components
        self.random_state = random_state
        self._vectorizer: TfidfVectorizer | None = None
        self._svd: TruncatedSVD | None = None

    @property
    def name(self) -> str:
        return "lsa"

    def fit(self, corpus_texts: list[str]) -> None:
        self._vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),   # unigrams + bigrams give LSA a bit more to work with on a small corpus
            min_df=1,
        )
        tfidf_matrix = self._vectorizer.fit_transform(corpus_texts)

        # n_components must be < min(n_samples, n_features) for TruncatedSVD
        max_components = min(self.n_components, tfidf_matrix.shape[0] - 1, tfidf_matrix.shape[1] - 1)
        max_components = max(max_components, 2)  # need at least 2 for anything meaningful

        self._svd = TruncatedSVD(n_components=max_components, random_state=self.random_state)
        self._svd.fit(tfidf_matrix)

    def encode(self, texts: list[str]) -> np.ndarray:
        if self._vectorizer is None or self._svd is None:
            raise RuntimeError("LSAEncoder.fit() (or load()) must be called before encode()")

        tfidf_matrix = self._vectorizer.transform(texts)
        vectors = self._svd.transform(tfidf_matrix)
        vectors = normalize(vectors, norm="l2", axis=1)  # so inner product == cosine similarity
        return vectors.astype(np.float32)

    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            pickle.dump({
                "vectorizer": self._vectorizer,
                "svd": self._svd,
                "n_components": self.n_components,
            }, f)

    def load(self, path: str) -> None:
        with open(path, "rb") as f:
            data = pickle.load(f)
        self._vectorizer = data["vectorizer"]
        self._svd = data["svd"]
        self.n_components = data["n_components"]
