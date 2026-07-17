"""Tests for parsing the analyzer wire format into review sections."""

from core.sections import parse_sections

SAMPLE = """---
SECTION: Step 1 -- QA Sample Selection
CURRENT WORDING: Every week, select 10% of resolved tickets.
WHY OUTDATED: The chatbot now escalates tickets tagged [chat-escalation].
SUGGESTED REWRITE: Every week, select 10% of resolved tickets, ensuring [chat-escalation] tickets are represented.
---
SECTION: Step 2 -- QA Scorecard
CURRENT WORDING: Score tone, accuracy, speed, escalation.
WHY OUTDATED: A new checklist item is required for chat-escalated tickets.
SUGGESTED REWRITE: Score tone, accuracy, speed, escalation, plus chatbot accuracy for [chat-escalation].
---
"""


def test_parses_all_blocks():
    secs = parse_sections(SAMPLE)
    assert len(secs) == 2
    assert secs[0]["section"] == "Step 1 -- QA Sample Selection"
    assert "10%" in secs[0]["current_wording"]
    assert "chat-escalation" in secs[0]["why_outdated"]
    assert "represented" in secs[0]["suggested_rewrite"]
    assert secs[1]["section"] == "Step 2 -- QA Scorecard"


def test_every_key_present():
    for sec in parse_sections(SAMPLE):
        assert set(sec) == {"section", "current_wording", "why_outdated", "suggested_rewrite"}


def test_empty_input_is_empty_list():
    assert parse_sections("") == []
    assert parse_sections(None) == []


def test_multiline_rewrite_is_joined():
    text = (
        "---\n"
        "SECTION: A\n"
        "SUGGESTED REWRITE: line one\n"
        "line two\n"
        "---\n"
    )
    secs = parse_sections(text)
    assert len(secs) == 1
    assert secs[0]["suggested_rewrite"] == "line one\nline two"


def test_block_without_section_or_rewrite_is_dropped():
    text = "---\nWHY OUTDATED: orphaned note with no section or rewrite\n---\n"
    assert parse_sections(text) == []
