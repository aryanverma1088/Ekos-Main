"""
Unit tests for evaluation/metrics.py, checked against hand-computed values
so we can trust the evaluation harness before running it over real results.
"""
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evaluation.metrics import (  # noqa: E402
    precision_at_k, recall_at_k, reciprocal_rank, ndcg_at_k, evaluate_run
)


def test_precision_at_k_basic():
    retrieved = [1, 2, 3, 4, 5]
    relevant = {3}
    assert precision_at_k(retrieved, relevant, 5) == 1 / 5
    assert precision_at_k(retrieved, relevant, 1) == 0.0
    assert precision_at_k(retrieved, relevant, 3) == 1 / 3


def test_recall_at_k_basic():
    retrieved = [1, 2, 3, 4, 5]
    relevant = {3, 10}  # 10 is not retrieved at all
    assert recall_at_k(retrieved, relevant, 5) == 1 / 2
    assert recall_at_k(retrieved, relevant, 2) == 0.0


def test_recall_with_no_relevant_docs_is_zero():
    assert recall_at_k([1, 2, 3], set(), 5) == 0.0


def test_precision_with_empty_retrieved_is_zero():
    assert precision_at_k([], {1, 2}, 5) == 0.0


def test_reciprocal_rank():
    assert reciprocal_rank([5, 6, 3, 8], {3}) == 1 / 3
    assert reciprocal_rank([3, 6, 5], {3}) == 1.0
    assert reciprocal_rank([1, 2, 3], {99}) == 0.0
    assert reciprocal_rank([], {1}) == 0.0


def test_ndcg_perfect_ranking_is_one():
    retrieved = [1, 2, 3]
    relevant = {1, 2, 3}
    assert ndcg_at_k(retrieved, relevant, 3) == pytest.approx(1.0)


def test_ndcg_hand_computed():
    # relevant doc is at rank 3 (0-indexed position 2)
    retrieved = [1, 2, 3, 4, 5]
    relevant = {3}
    dcg = 1.0 / math.log2(2 + 2)   # position index 2 -> log2(4)
    idcg = 1.0 / math.log2(1 + 1)  # single ideal hit at rank 1 -> log2(2)
    expected = dcg / idcg
    assert ndcg_at_k(retrieved, relevant, 5) == pytest.approx(expected)


def test_ndcg_with_no_relevant_is_zero():
    assert ndcg_at_k([1, 2, 3], set(), 5) == 0.0


def test_evaluate_run_aggregates_correctly():
    per_query_retrieved = {
        "q1": [1, 2, 3],
        "q2": [4, 5, 6],
    }
    per_query_relevant = {
        "q1": {1},   # perfect: relevant at rank 1
        "q2": {99},  # miss: relevant not retrieved at all
    }
    result = evaluate_run(per_query_retrieved, per_query_relevant, k_values=(3,))
    summary = result["summary"]

    # q1: precision@3=1/3, recall@3=1, mrr=1, ndcg@3=1
    # q2: precision@3=0, recall@3=0, mrr=0, ndcg@3=0
    assert summary["mrr"] == pytest.approx(0.5)
    assert summary["precision@3"] == pytest.approx((1 / 3 + 0) / 2)
    assert summary["recall@3"] == pytest.approx((1.0 + 0) / 2)
    assert summary["ndcg@3"] == pytest.approx(0.5)
    assert set(result["per_query"].keys()) == {"q1", "q2"}
