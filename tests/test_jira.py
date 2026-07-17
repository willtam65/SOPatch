"""Tests for the Jira webhook parsing and trigger logic -- no API key needed."""

from core.jira import extract_change_note, should_trigger, source_label

VERSION_EVENT = {
    "webhookEvent": "jira:version_released",
    "version": {
        "name": "v3.1",
        "description": "AI Chat Assistant launch. The SLA clock for chat-escalated tickets now starts when the chatbot fails to resolve.",
    },
}

LABELED_ISSUE = {
    "webhookEvent": "jira:issue_updated",
    "issue": {
        "key": "OPS-42",
        "fields": {
            "summary": "New refund policy",
            "labels": ["policy-change"],
            "description": {
                "type": "doc",
                "content": [
                    {"type": "paragraph", "content": [
                        {"type": "text", "text": "Refunds now require lead approval."}
                    ]},
                ],
            },
        },
    },
}

UNRELATED_ISSUE = {
    "webhookEvent": "jira:issue_updated",
    "issue": {"key": "OPS-99", "fields": {"summary": "Fix a typo", "labels": ["chore"], "description": None}},
}


def test_version_released_triggers():
    assert should_trigger(VERSION_EVENT) is True


def test_labeled_issue_triggers():
    assert should_trigger(LABELED_ISSUE) is True


def test_unrelated_issue_does_not_trigger():
    assert should_trigger(UNRELATED_ISSUE) is False


def test_empty_or_bad_event_does_not_trigger():
    assert should_trigger({}) is False
    assert should_trigger(None) is False


def test_extract_from_version():
    note = extract_change_note(VERSION_EVENT)
    assert "v3.1" in note
    assert "SLA clock" in note


def test_extract_from_issue_flattens_adf():
    note = extract_change_note(LABELED_ISSUE)
    assert "OPS-42" in note
    assert "New refund policy" in note
    assert "Refunds now require lead approval." in note


def test_extract_handles_missing_description():
    note = extract_change_note(UNRELATED_ISSUE)
    assert "OPS-99" in note and "Fix a typo" in note


def test_source_label():
    assert "v3.1" in source_label(VERSION_EVENT)
    assert "OPS-42" in source_label(LABELED_ISSUE)
