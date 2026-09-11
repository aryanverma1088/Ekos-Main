"""
Evaluates System A (BM25) over the ground-truth query set and saves results.

Run:
    python evaluation/evaluate_bm25.py

Prerequisites:
    python scripts/ingest.py --reset
    python scripts/resolve_ground_truth.py
    python scripts/build_bm25_index.py

Later phases (Dense, Hybrid, Hybrid+Rerank) will follow this exact same
shape -- load resolved ground truth, run system.search() per query, call
evaluate_run() -- so results are directly comparable across systems in the
final System A/B/C/D comparison table.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from ir.bm25.index import BM25Index      # noqa: E402
from evaluation.metrics import evaluate_run  # noqa: E402

INDEX_PATH = ROOT / "data" / "processed" / "bm25_index.pkl"
RESOLVED_GT_PATH = ROOT / "data" / "processed" / "resolved_ground_truth.json"
RESULTS_PATH = ROOT / "evaluation" / "results_bm25.json"

TOP_K_RETRIEVE = 10  # retrieve enough to score both P@5 and P@10


def run():
    if not INDEX_PATH.exists():
        raise FileNotFoundError(f"{INDEX_PATH} not found. Run scripts/build_bm25_index.py first.")
    if not RESOLVED_GT_PATH.exists():
        raise FileNotFoundError(f"{RESOLVED_GT_PATH} not found. Run scripts/resolve_ground_truth.py first.")

    index = BM25Index.load(INDEX_PATH)
    resolved_gt = json.loads(RESOLVED_GT_PATH.read_text())

    per_query_retrieved = {}
    per_query_relevant = {}

    for q in resolved_gt["queries"]:
        qid = q["query_id"]
        results = index.search(q["query_text"], top_k=TOP_K_RETRIEVE)
        per_query_retrieved[qid] = [chunk_id for chunk_id, _score in results]
        per_query_relevant[qid] = set(q["relevant_chunk_ids"])

    eval_result = evaluate_run(per_query_retrieved, per_query_relevant, k_values=(5, 10))

    output = {
        "system": "BM25",
        "num_queries": len(resolved_gt["queries"]),
        **eval_result,
    }
    RESULTS_PATH.write_text(json.dumps(output, indent=2))

    print(f"System: BM25  ({len(resolved_gt['queries'])} queries)")
    print("-" * 40)
    for metric, value in eval_result["summary"].items():
        print(f"  {metric:14s}: {value:.3f}")
    print(f"\nFull results (including per-query breakdown) written to {RESULTS_PATH}")


if __name__ == "__main__":
    run()
