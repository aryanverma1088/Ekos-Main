"""
Evaluates System B (Dense retrieval) over the ground-truth query set.

Prerequisites:
    python scripts/ingest.py --reset
    python scripts/resolve_ground_truth.py
    python scripts/build_dense_index.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from ir.embeddings.config import get_encoder      # noqa: E402
from ir.embeddings.dense_index import DenseIndex  # noqa: E402
from evaluation.metrics import evaluate_run        # noqa: E402

INDEX_DIR = ROOT / "data" / "processed" / "dense_index"
RESOLVED_GT_PATH = ROOT / "data" / "processed" / "resolved_ground_truth.json"
RESULTS_PATH = ROOT / "evaluation" / "results_dense.json"

TOP_K_RETRIEVE = 10


def run():
    if not INDEX_DIR.exists():
        raise FileNotFoundError(f"{INDEX_DIR} not found. Run scripts/build_dense_index.py first.")
    if not RESOLVED_GT_PATH.exists():
        raise FileNotFoundError(f"{RESOLVED_GT_PATH} not found. Run scripts/resolve_ground_truth.py first.")

    encoder = get_encoder()
    index = DenseIndex.load(INDEX_DIR, encoder)
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
        "system": f"Dense ({encoder.name})",
        "num_queries": len(resolved_gt["queries"]),
        **eval_result,
    }
    RESULTS_PATH.write_text(json.dumps(output, indent=2))

    print(f"System: Dense ({encoder.name})  ({len(resolved_gt['queries'])} queries)")
    print("-" * 40)
    for metric, value in eval_result["summary"].items():
        print(f"  {metric:14s}: {value:.3f}")
    print(f"\nFull results written to {RESULTS_PATH}")


if __name__ == "__main__":
    run()
