"""
Evaluates System D (Hybrid retrieval + reranking) over the ground-truth
query set. Uses the reranker configured in ir/reranking/config.py
(TF-IDF fallback by default; swap to a real cross-encoder once running
with internet access).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from db import get_session                                    # noqa: E402
from models import Chunk                                       # noqa: E402
from ir.bm25.index import BM25Index                             # noqa: E402
from ir.embeddings.config import get_encoder                    # noqa: E402
from ir.embeddings.dense_index import DenseIndex                # noqa: E402
from ir.hybrid.hybrid_retriever import HybridRetriever          # noqa: E402
from ir.reranking.config import get_reranker                     # noqa: E402
from ir.reranking.reranked_retriever import HybridRerankRetriever  # noqa: E402
from evaluation.metrics import evaluate_run                      # noqa: E402

BM25_INDEX_PATH = ROOT / "data" / "processed" / "bm25_index.pkl"
DENSE_INDEX_DIR = ROOT / "data" / "processed" / "dense_index"
RESOLVED_GT_PATH = ROOT / "data" / "processed" / "resolved_ground_truth.json"
RESULTS_PATH = ROOT / "evaluation" / "results_hybrid_rerank.json"

TOP_K_RETRIEVE = 10


def build_chunk_text_lookup():
    """Loads all chunk texts once into memory so the reranker's lookup
    function doesn't open a DB session per candidate."""
    session = get_session()
    rows = session.query(Chunk.id, Chunk.chunk_text).all()
    session.close()
    text_by_id = {cid: text for cid, text in rows}
    return lambda chunk_id: text_by_id[chunk_id]


def run():
    for path in (BM25_INDEX_PATH, DENSE_INDEX_DIR, RESOLVED_GT_PATH):
        if not path.exists():
            raise FileNotFoundError(f"{path} not found. Build both indexes and resolve ground truth first.")

    bm25_index = BM25Index.load(BM25_INDEX_PATH)
    encoder = get_encoder()
    dense_index = DenseIndex.load(DENSE_INDEX_DIR, encoder)
    hybrid = HybridRetriever(bm25_index, dense_index)

    reranker = get_reranker()
    chunk_text_lookup = build_chunk_text_lookup()
    pipeline = HybridRerankRetriever(hybrid, reranker, chunk_text_lookup)

    resolved_gt = json.loads(RESOLVED_GT_PATH.read_text())

    per_query_retrieved = {}
    per_query_relevant = {}

    for q in resolved_gt["queries"]:
        qid = q["query_id"]
        results = pipeline.search(q["query_text"], top_k=TOP_K_RETRIEVE)
        per_query_retrieved[qid] = [chunk_id for chunk_id, _score in results]
        per_query_relevant[qid] = set(q["relevant_chunk_ids"])

    eval_result = evaluate_run(per_query_retrieved, per_query_relevant, k_values=(5, 10))

    output = {
        "system": f"Hybrid + Rerank ({reranker.name})",
        "num_queries": len(resolved_gt["queries"]),
        **eval_result,
    }
    RESULTS_PATH.write_text(json.dumps(output, indent=2))

    print(f"System: Hybrid + Rerank ({reranker.name})  ({len(resolved_gt['queries'])} queries)")
    print("-" * 40)
    for metric, value in eval_result["summary"].items():
        print(f"  {metric:14s}: {value:.3f}")
    print(f"\nFull results written to {RESULTS_PATH}")


if __name__ == "__main__":
    run()
