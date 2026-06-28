"""Unit tests for the token-aware tag/label matcher -- no API key required.

These pin the exact near-miss cases the eval surfaced (the model's tag vs the
SOP's label) so a future matcher change can't silently regress them.
"""

from core.matching import matched_labels, tags_match


def test_exact_match():
    assert tags_match("sla-clock", "sla-clock")


def test_label_is_subset_of_extracted_tag():
    # the real misses: model over-specifies, label is the shorter form
    assert tags_match("weekly-cx-reporting", "weekly-reporting")
    assert tags_match("weekly-reporting-rebaseline", "weekly-reporting")
    assert tags_match("sla-clock-start-rules", "sla-clock")
    assert tags_match("qa-scorecard-process", "qa-scorecard")


def test_single_shared_token_does_not_match():
    # 'sla' alone must not match everything (precision guard)
    assert not tags_match("sla-policy-update", "response-time-sla")
    assert not tags_match("ticket-volume-baseline", "ticket-triage")


def test_unrelated_tags_do_not_match():
    assert not tags_match("office-relocation", "weekly-reporting")
    assert not tags_match("parental-leave", "agent-qa-scoring")


def test_matched_labels_returns_matching_labels():
    labels = ["weekly-reporting", "metrics-rebaseline", "trend-analysis"]
    assert matched_labels(["weekly-cx-reporting"], labels) == {"weekly-reporting"}


def test_matched_labels_empty_when_nothing_matches():
    assert matched_labels(["office-move"], ["sla-clock", "ticket-triage"]) == set()
