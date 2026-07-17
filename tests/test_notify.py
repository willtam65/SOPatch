"""Tests for the reviewer-notification formatting -- no network needed."""

from core.notify import format_review_notification


def test_notification_lists_flagged_sops():
    result = {"affected_count": 2, "results": [{"title": "QA Monitoring SOP"}, {"title": "SLA Tracking SOP"}]}
    msg = format_review_notification("Jira release v3.1", result)
    assert "2 SOP" in msg
    assert "QA Monitoring SOP" in msg
    assert "SLA Tracking SOP" in msg
    assert "release v3.1" in msg
    assert "approve" in msg.lower()


def test_notification_when_nothing_affected():
    msg = format_review_notification("Jira OPS-99", {"affected_count": 0, "results": []})
    assert "no sops affected" in msg.lower()


def test_notification_includes_review_url_when_given():
    msg = format_review_notification(
        "Jira release v3.1",
        {"affected_count": 1, "results": [{"title": "A"}]},
        review_url="https://sopatch.example/review/1",
    )
    assert "https://sopatch.example/review/1" in msg
