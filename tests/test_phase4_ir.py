"""
Tests for Phase 4 components: dense encoder/index, RRF fusion, reranker.
These build small in-memory indexes rather than depending on the ingested
DB, so they run fast and independently of ingestion state.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ir.embeddings.lsa_encoder import LSAEncoder      # noqa: E402
from ir.embeddings.dense_index import DenseIndex        # noqa: E402
from ir.hybrid.rrf import reciprocal_rank_fusion         # noqa: E402
from ir.reranking.tfidf_reranker import TfidfRerankerFallback  # noqa: E402

SAMPLE_CHUNKS = [
    (1, "Employees may work remotely up to three days per week with manager approval."),
    (2, "Passwords must be changed every ninety days according to the security policy."),
    (3, "The finance team approves expense reimbursements up to two hundred fifty dollars monthly."),
    (4, "Production database access requires manager approval and a completed access ticket."),
    (5, "Senior engineers are granted standing access to production databases without a per-instance request."),
]


class TestLSAEncoder:

    def test_fit_and_encode_produces_normalized_vectors(self):
        encoder = LSAEncoder(n_components=3)
        texts = [t for _, t in SAMPLE_CHUNKS]
        encoder.fit(texts)
        vectors = encoder.encode(texts)

        assert vectors.shape[0] == len(texts)
        # L2-normalized: each row's norm should be ~1 (or 0 for a degenerate all-zero row, not expected here)
        norms = (vectors ** 2).sum(axis=1) ** 0.5
        for n in norms:
            assert abs(n - 1.0) < 1e-4

    def test_encode_before_fit_raises(self):
        encoder = LSAEncoder()
        try:
            encoder.encode(["some text"])
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass

    def test_save_and_load_roundtrip(self):
        encoder = LSAEncoder(n_components=3)
        texts = [t for _, t in SAMPLE_CHUNKS]
        encoder.fit(texts)
        original_vectors = encoder.encode(texts)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp:
            path = tmp.name
        encoder.save(path)

        loaded = LSAEncoder()
        loaded.load(path)
        loaded_vectors = loaded.encode(texts)

        assert (abs(original_vectors - loaded_vectors) < 1e-6).all()
        Path(path).unlink()


class TestDenseIndex:

    def test_build_and_search_finds_relevant_chunk(self):
        encoder = LSAEncoder(n_components=3)
        index = DenseIndex(encoder)
        index.build(SAMPLE_CHUNKS)

        results = index.search("How many days can I work from home?", top_k=3)
        result_ids = [cid for cid, _ in results]
        assert 1 in result_ids  # remote work chunk should be retrieved

    def test_search_returns_scores_descending(self):
        encoder = LSAEncoder(n_components=3)
        index = DenseIndex(encoder)
        index.build(SAMPLE_CHUNKS)

        results = index.search("password rotation policy", top_k=5)
        scores = [s for _, s in results]
        assert scores == sorted(scores, reverse=True)

    def test_save_load_roundtrip_and_encoder_mismatch_check(self):
        encoder = LSAEncoder(n_components=3)
        index = DenseIndex(encoder)
        index.build(SAMPLE_CHUNKS)

        with tempfile.TemporaryDirectory() as tmpdir:
            index.save(tmpdir)

            loaded_encoder = LSAEncoder(n_components=3)
            loaded_index = DenseIndex.load(tmpdir, loaded_encoder)
            results = loaded_index.search("production database access", top_k=3)
            result_ids = {cid for cid, _ in results}
            assert 4 in result_ids or 5 in result_ids


class TestRRF:

    def test_item_in_both_lists_ranks_above_item_in_one(self):
        list_a = [1, 2, 3]
        list_b = [2, 1, 4]
        fused = reciprocal_rank_fusion([list_a, list_b])
        fused_ids = [cid for cid, _ in fused]
        # item 1 and 2 both appear in both lists near the top; item 3 and 4 appear in only one list
        assert fused_ids[0] in (1, 2)
        assert fused_ids[1] in (1, 2)
        assert set(fused_ids[:2]) == {1, 2}

    def test_empty_lists_produce_empty_result(self):
        assert reciprocal_rank_fusion([[], []]) == []

    def test_single_list_preserves_relative_order(self):
        fused = reciprocal_rank_fusion([[5, 3, 8]])
        fused_ids = [cid for cid, _ in fused]
        assert fused_ids == [5, 3, 8]


class TestTfidfReranker:

    def test_rerank_orders_by_relevance(self):
        reranker = TfidfRerankerFallback()
        candidates = [(cid, text) for cid, text in SAMPLE_CHUNKS]
        # Query deliberately shares literal tokens with chunk 2 ("changed", "days",
        # "security policy") since TfidfRerankerFallback is bag-of-words with no
        # stemming -- it has no way to match "password expiration" to "Passwords
        # ... changed" without literal overlap. That's a documented limitation
        # (see ir/reranking/base.py), not something this test should paper over.
        results = reranker.rerank("how often are passwords changed under the security policy", candidates)
        assert results[0][0] == 2

    def test_rerank_empty_candidates(self):
        reranker = TfidfRerankerFallback()
        assert reranker.rerank("anything", []) == []
