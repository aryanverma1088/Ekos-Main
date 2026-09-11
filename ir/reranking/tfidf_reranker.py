"""
Fallback reranker: fits a fresh TF-IDF vector space over just the query +
candidate texts (not the corpus-level index) and rescores by cosine
similarity to the query. See ir/reranking/base.py for why this exists
instead of a cross-encoder in this environment.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .base import Reranker


class TfidfRerankerFallback(Reranker):
    @property
    def name(self) -> str:
        return "tfidf_fallback"

    def rerank(self, query: str, candidates: list[tuple[int, str]]) -> list[tuple[int, float]]:
        if not candidates:
            return []

        chunk_ids = [cid for cid, _ in candidates]
        texts = [text for _, text in candidates]

        vectorizer = TfidfVectorizer(lowercase=True, stop_words="english", ngram_range=(1, 2))
        # Fit on candidates + query together so the query's terms are in-vocabulary.
        matrix = vectorizer.fit_transform(texts + [query])

        candidate_vectors = matrix[:-1]
        query_vector = matrix[-1]

        sims = cosine_similarity(query_vector, candidate_vectors)[0]

        scored = list(zip(chunk_ids, sims.tolist()))
        return sorted(scored, key=lambda x: x[1], reverse=True)
