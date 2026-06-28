"""Tests for the content-gate config and helpers -- no API key needed.

The gate's actual LLM call isn't unit-tested (it needs the API), but the
on/off switch and the affected-entry shape are pure and covered here.
"""

from core.tagger import _affected_entry, content_gate_enabled


def test_gate_off_by_default(monkeypatch):
    monkeypatch.delenv("SOPATCH_CONTENT_GATE", raising=False)
    assert content_gate_enabled() is False


def test_gate_opt_in_with_1(monkeypatch):
    monkeypatch.setenv("SOPATCH_CONTENT_GATE", "1")
    assert content_gate_enabled() is True


def test_gate_stays_off_for_other_values(monkeypatch):
    monkeypatch.setenv("SOPATCH_CONTENT_GATE", "0")
    assert content_gate_enabled() is False
    monkeypatch.setenv("SOPATCH_CONTENT_GATE", "true")
    assert content_gate_enabled() is False


def test_affected_entry_shape():
    sop = {"page_id": "p1", "filename": "f.md", "title": "T",
           "content": "body", "labels": ["x"]}
    entry = _affected_entry(sop, ["content-match"])
    assert entry == {
        "page_id": "p1",
        "filename": "f.md",
        "title": "T",
        "content": "body",
        "matching_tags": ["content-match"],
    }
