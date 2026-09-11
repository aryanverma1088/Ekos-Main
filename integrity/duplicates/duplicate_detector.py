"""
Duplicate/near-duplicate detection: pairwise TF-IDF cosine similarity
across chunk text, grouped into clusters via union-find.

Uses a dedicated TF-IDF vectorizer (not the LSA dense index from
ir/embeddings/) -- duplicate detection needs fine-grained lexical overlap,
which SVD dimensionality reduction tends to blur; a direct comparison during
development found LSA and plain TF-IDF score the labeled ground-truth
duplicate pairs almost identically anyway (both ~0.14-0.18), so there's no
accuracy cost to using the simpler, dependency-free approach here.

Excludes pairs from the same document, and pairs whose documents are
connected by a supersedes relationship (a near-identical document that
supersedes another isn't a "duplicate" finding -- it's the SAME document,
i.e. an "outdated" finding; see integrity/versions/).

IMPORTANT -- see integrity/FINDINGS.md: validating this detector against
the two labeled ground-truth duplicate cases found they score 0.143 and
0.181, LOWER than several unrelated same-topic chunk pairs in this corpus
(0.27-0.31). No threshold value separates the true duplicates from noise
here. THRESHOLD is set high enough (0.60) to catch only near-verbatim
duplication with high precision; it will not catch the labeled paraphrased
duplicate cases with this fallback lexical method. This is an honest,
validated limitation, not an unvalidated guess -- see FINDINGS.md for the
full investigation and what closing this gap would require.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

SIMILARITY_THRESHOLD = 0.60


class UnionFind:
    def __init__(self, items: list[int]):
        self.parent = {i: i for i in items}

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def detect_duplicates(
    chunk_records: list[tuple[int, int, str]],
    supersedes_doc_pairs: set[tuple[int, int]],
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[dict]:
    """
    chunk_records: [(chunk_id, document_id, text), ...]
    supersedes_doc_pairs: set of (document_id, document_id) pairs (either
        order) connected by a supersedes relationship, excluded from results.

    Returns: [{chunk_a_id, chunk_b_id, similarity_score, cluster_id}, ...]
    """
    if len(chunk_records) < 2:
        return []

    chunk_ids = [c[0] for c in chunk_records]
    doc_ids = [c[1] for c in chunk_records]
    texts = [c[2] for c in chunk_records]

    vectorizer = TfidfVectorizer(lowercase=True, stop_words="english", ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(texts)
    sims = cosine_similarity(matrix)

    n = len(chunk_records)
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            if doc_ids[i] == doc_ids[j]:
                continue
            doc_pair = (doc_ids[i], doc_ids[j])
            if doc_pair in supersedes_doc_pairs or doc_pair[::-1] in supersedes_doc_pairs:
                continue
            score = float(sims[i, j])
            if score >= threshold:
                pairs.append((chunk_ids[i], chunk_ids[j], score))

    uf = UnionFind(chunk_ids)
    for a, b, _ in pairs:
        uf.union(a, b)

    roots_in_clusters = sorted({uf.find(a) for a, b, _ in pairs} | {uf.find(b) for a, b, _ in pairs})
    cluster_id_map = {root: idx + 1 for idx, root in enumerate(roots_in_clusters)}

    results = []
    for a, b, score in pairs:
        results.append({
            "chunk_a_id": a,
            "chunk_b_id": b,
            "similarity_score": score,
            "cluster_id": cluster_id_map[uf.find(a)],
        })

    return results
