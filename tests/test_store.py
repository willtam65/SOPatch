"""Tests for the review store: runs, decisions, and the audit trail."""

import pytest

from core.store import ReviewStore

RESULT = {
    "affected_count": 2,
    "results": [{"title": "QA Monitoring SOP"}, {"title": "SLA Tracking SOP"}],
}


@pytest.fixture
def store(tmp_path):
    return ReviewStore(db_path=str(tmp_path / "test.db"))


def test_create_run_returns_id_and_logs_created_event(store):
    run_id = store.create_run("Jira release v3.1", "Release v3.1\n\nBig change", RESULT)
    run = store.get_run(run_id)
    assert run["source"] == "Jira release v3.1"
    assert run["status"] == "pending"
    assert run["affected_count"] == 2
    assert run["result"]["results"][0]["title"] == "QA Monitoring SOP"
    events = [e["event"] for e in run["audit"]]
    assert events == ["created"]


def test_notified_event_is_appended(store):
    run_id = store.create_run("Jira OPS-42", "OPS-42: change", RESULT)
    store.record_event(run_id, "notified", detail="log")
    run = store.get_run(run_id)
    assert [e["event"] for e in run["audit"]] == ["created", "notified"]


def test_set_decision_approves_and_audits(store):
    run_id = store.create_run("Jira OPS-42", "note", RESULT)
    updated = store.set_decision(run_id, "approved", actor="Will Tam")
    assert updated["status"] == "approved"
    assert updated["approver"] == "Will Tam"
    assert updated["decided_at"]
    assert [e["event"] for e in updated["audit"]] == ["created", "approved"]


def test_set_decision_rejects(store):
    run_id = store.create_run("Jira OPS-42", "note", RESULT)
    assert store.set_decision(run_id, "rejected")["status"] == "rejected"


def test_set_decision_on_missing_run_returns_none(store):
    assert store.set_decision(999, "approved") is None


def test_invalid_decision_raises(store):
    run_id = store.create_run("Jira OPS-42", "note", RESULT)
    with pytest.raises(ValueError):
        store.set_decision(run_id, "maybe")


def test_get_missing_run_returns_none(store):
    assert store.get_run(12345) is None


def test_list_runs_newest_first(store):
    first = store.create_run("Jira OPS-1", "a", RESULT)
    second = store.create_run("Jira OPS-2", "b", RESULT)
    ids = [r["id"] for r in store.list_runs()]
    assert ids == [second, first]


def test_store_persists_across_instances(tmp_path):
    path = str(tmp_path / "persist.db")
    run_id = ReviewStore(db_path=path).create_run("Jira OPS-9", "note", RESULT)
    # A fresh instance (new connection) still sees the run.
    assert ReviewStore(db_path=path).get_run(run_id)["source"] == "Jira OPS-9"
