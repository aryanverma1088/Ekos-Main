"""
Loads results_bm25.json, results_dense.json, results_hybrid.json, and
results_hybrid_rerank.json and prints/saves a single comparison table --
the centerpiece figure for the IR evaluation section of the report.

Run this AFTER all four evaluate_*.py scripts have been run.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "evaluation"

RESULT_FILES = [
    ("System A: BM25", "results_bm25.json"),
    ("System B: Dense", "results_dense.json"),
    ("System C: Hybrid (RRF)", "results_hybrid.json"),
    ("System D: Hybrid + Rerank", "results_hybrid_rerank.json"),
]

METRIC_ORDER = ["precision@5", "recall@5", "mrr", "ndcg@5", "precision@10", "recall@10", "ndcg@10"]


def load_results():
    rows = []
    missing = []
    for label, filename in RESULT_FILES:
        path = EVAL_DIR / filename
        if not path.exists():
            missing.append(filename)
            continue
        data = json.loads(path.read_text())
        rows.append((label, data["system"], data["summary"]))
    return rows, missing


def print_table(rows):
    header = ["System"] + METRIC_ORDER
    col_widths = [26] + [12] * len(METRIC_ORDER)

    def fmt_row(cells):
        return "".join(str(c).ljust(w) for c, w in zip(cells, col_widths))

    print(fmt_row(header))
    print("-" * sum(col_widths))
    for label, _system_name, summary in rows:
        cells = [label] + [f"{summary[m]:.3f}" for m in METRIC_ORDER]
        print(fmt_row(cells))


def save_table(rows):
    out = {
        "metric_order": METRIC_ORDER,
        "systems": [
            {"label": label, "system": system_name, "metrics": summary}
            for label, system_name, summary in rows
        ],
    }
    out_path = EVAL_DIR / "comparison_table.json"
    out_path.write_text(json.dumps(out, indent=2))
    return out_path


def run():
    rows, missing = load_results()

    if missing:
        print("Missing result files (run the corresponding evaluate_*.py script first):")
        for m in missing:
            print(f"  - {m}")
        print()

    if not rows:
        print("No results available yet.")
        return

    print_table(rows)
    out_path = save_table(rows)
    print(f"\nComparison table saved to {out_path}")


if __name__ == "__main__":
    run()
