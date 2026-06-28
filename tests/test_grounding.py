"""Unit tests for the grounding guard -- no API key required.

Verifies that a flagged section whose quoted 'current wording' isn't in the
source SOP is dropped, while genuinely-quoted sections are kept.
"""

from core.grounding import ground_analysis, is_grounded

SOP = """# SLA Tracking SOP
Step 1: The SLA clock starts at the moment a ticket is created in Zendesk.
Step 2: Escalations are reviewed weekly by a senior specialist.
"""

# First block quotes real text; second invents a policy that isn't in the SOP.
ANALYSIS = """---
SECTION: Step 1
CURRENT WORDING: The SLA clock starts at the moment a ticket is created in Zendesk.
WHY OUTDATED: Chat-escalated tickets start the clock differently now.
SUGGESTED REWRITE: The SLA clock starts when the chatbot fails to resolve the query.
---
SECTION: Step 9
CURRENT WORDING: All tickets must be closed within 24 hours of the customer's third reply.
WHY OUTDATED: This policy is changing.
SUGGESTED REWRITE: Close within 12 hours.
---"""


def test_drops_hallucinated_section_keeps_real_one():
    grounded, dropped = ground_analysis(ANALYSIS, SOP)
    assert len(dropped) == 1
    assert dropped[0]["section"] == "Step 9"
    assert "Step 1" in grounded
    assert "Step 9" not in grounded
    assert "created in Zendesk" in grounded


def test_is_grounded_true_for_verbatim_quote():
    assert is_grounded("The SLA clock starts at the moment a ticket is created in Zendesk.", SOP)


def test_is_grounded_ignores_case_and_whitespace():
    assert is_grounded("the sla   clock starts at the moment a ticket is\ncreated in zendesk.", SOP)


def test_is_grounded_strips_surrounding_quotes():
    assert is_grounded('“Escalations are reviewed weekly by a senior specialist.”', SOP)


def test_is_grounded_false_for_invented_text():
    assert not is_grounded("All tickets must be closed within 24 hours.", SOP)


def test_is_grounded_false_for_empty():
    assert not is_grounded("", SOP)
    assert not is_grounded("   ", SOP)


def test_first_sentence_fallback_matches_extended_quote():
    # model quotes a real sentence plus an invented trailing one -> still grounded
    quote = "Escalations are reviewed weekly by a senior specialist. They must also file a report."
    assert is_grounded(quote, SOP)


def test_unparseable_analysis_returned_unchanged():
    text = "No structured blocks here, just prose."
    grounded, dropped = ground_analysis(text, SOP)
    assert grounded == text
    assert dropped == []
