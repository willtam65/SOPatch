"""Pure, deterministic scoring for the SOPatch tagger eval.

Deliberately free of any LLM/API/network code so it can be unit-tested without
credentials -- this is the part CI runs on every push. The tagger decision is a
set-prediction problem (which SOPs are affected?), so we score it with the
standard set metrics: precision, recall, F1, plus exact-set-match rate.
"""

from __future__ import annotations


def score_case(predicted, gold):
    """Score one case: the predicted affected-SOP set vs the gold set.

    Returns per-case true/false positive/negative counts, whether the sets
    matched exactly, and the specific SOPs that were over- or under-flagged
    (useful for the saved traces).
    """
    predicted, gold = set(predicted), set(gold)
    true_pos = predicted & gold
    false_pos = predicted - gold
    false_neg = gold - predicted
    return {
        "tp": len(true_pos),
        "fp": len(false_pos),
        "fn": len(false_neg),
        "exact_match": predicted == gold,
        "false_positives": sorted(false_pos),
        "false_negatives": sorted(false_neg),
    }


def _ratio(numerator, denominator):
    """Safe division that returns 0.0 instead of raising on an empty set."""
    return numerator / denominator if denominator else 0.0


def aggregate(case_results):
    """Micro-average a list of per-case results from `score_case`.

    Micro-averaging (pool all TP/FP/FN, then compute) weights every SOP-level
    decision equally regardless of how many SOPs a given release note touches.
    """
    tp = sum(c["tp"] for c in case_results)
    fp = sum(c["fp"] for c in case_results)
    fn = sum(c["fn"] for c in case_results)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = _ratio(2 * precision * recall, precision + recall)
    exact = sum(1 for c in case_results if c["exact_match"])
    return {
        "cases": len(case_results),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "exact_match": exact,
        "exact_match_rate": _ratio(exact, len(case_results)),
    }
