"""Unit tests for the eval scoring -- pure functions, no API key required.

This is what CI runs on every push, so the eval's math is guaranteed correct
independent of any model behavior.
"""

from evals.scoring import aggregate, score_case


def test_perfect_prediction():
    r = score_case({"qa", "sla"}, {"qa", "sla"})
    assert r["tp"] == 2 and r["fp"] == 0 and r["fn"] == 0
    assert r["exact_match"] is True


def test_false_positive_and_negative():
    # predicted flags reporting (wrong) and misses sla (missed)
    r = score_case({"qa", "reporting"}, {"qa", "sla"})
    assert r["tp"] == 1
    assert r["fp"] == 1 and r["false_positives"] == ["reporting"]
    assert r["fn"] == 1 and r["false_negatives"] == ["sla"]
    assert r["exact_match"] is False


def test_empty_gold_with_false_positive():
    r = score_case({"qa"}, set())
    assert r["tp"] == 0 and r["fp"] == 1 and r["fn"] == 0
    assert r["exact_match"] is False


def test_empty_prediction_and_gold_is_exact_match():
    r = score_case(set(), set())
    assert r["tp"] == 0 and r["fp"] == 0 and r["fn"] == 0
    assert r["exact_match"] is True


def test_aggregate_micro_average():
    results = [
        score_case({"qa", "sla"}, {"qa", "sla"}),       # tp2
        score_case({"qa", "reporting"}, {"qa", "sla"}),  # tp1 fp1 fn1
    ]
    summary = aggregate(results)
    assert summary["tp"] == 3 and summary["fp"] == 1 and summary["fn"] == 1
    assert summary["precision"] == 3 / 4
    assert summary["recall"] == 3 / 4
    assert summary["f1"] == 3 / 4
    assert summary["cases"] == 2
    assert summary["exact_match"] == 1
    assert summary["exact_match_rate"] == 1 / 2


def test_aggregate_handles_empty_without_dividing_by_zero():
    summary = aggregate([])
    assert summary["precision"] == 0.0
    assert summary["recall"] == 0.0
    assert summary["f1"] == 0.0
    assert summary["exact_match_rate"] == 0.0
