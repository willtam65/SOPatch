"""Tests for the eval dataset and the (deterministic) matching logic.

These run without an API key: predict_affected is pure set intersection, so we
can assert the tagger's matching rule is correct independent of the model.
"""

import pytest

from evals.dataset import (
    CASES,
    SOP_FIXTURES,
    all_sop_ids,
    predict_affected,
    validate,
)


def test_dataset_is_valid():
    assert validate() is True


def test_has_enough_cases():
    assert len(CASES) >= 12, "eval set too small to be credible"


def test_case_ids_unique():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids))


def test_gold_sets_within_universe():
    universe = all_sop_ids()
    for case in CASES:
        assert set(case["gold"]) <= universe


def test_includes_negative_cases():
    # at least one release note should affect no SOP (precision / false-alarm test)
    assert any(not case["gold"] for case in CASES)


def test_includes_hard_cases():
    assert any(case["hard"] for case in CASES)


def test_predict_affected_matches_on_shared_label():
    # 'sla-clock' is a label on the SLA SOP only
    assert predict_affected({"sla-clock"}) == {"sla"}


def test_predict_affected_shared_label_hits_multiple():
    # 'chat-escalation' is a label on both qa and sla
    assert predict_affected({"chat-escalation"}) == {"qa", "sla"}


def test_predict_affected_no_overlap_returns_empty():
    assert predict_affected({"totally-unrelated-tag"}) == set()


@pytest.mark.parametrize("sop_id,fixture", SOP_FIXTURES.items())
def test_every_sop_has_labels(sop_id, fixture):
    assert fixture["labels"], f"{sop_id} has no labels"
    assert fixture["title"]
