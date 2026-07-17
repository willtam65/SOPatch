"""End-to-end tests for the review queue routes, in demo mode (no secrets)."""

import os

import pytest

import app as app_module
from core.store import ReviewStore

VERSION_EVENT = {
    "webhookEvent": "jira:version_released",
    "version": {"name": "v3.1", "description": "AI Chat Assistant launch"},
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SOPATCH_DEMO", "1")
    # Isolate the store so tests never touch the real data/sopatch.db.
    monkeypatch.setattr(app_module, "store", ReviewStore(db_path=str(tmp_path / "reviews.db")))
    app_module.app.config.update(TESTING=True, SERVER_NAME="localhost")
    with app_module.app.test_client() as c:
        with app_module.app.app_context():
            yield c


def _fire_webhook(client):
    return client.post("/webhook/jira", json=VERSION_EVENT)


def test_webhook_creates_run_with_review_url(client):
    res = _fire_webhook(client)
    assert res.status_code == 200
    body = res.get_json()
    assert body["triggered"] is True
    assert body["run_id"] >= 1
    assert f"/review/{body['run_id']}" in body["review_url"]
    # The reviewer notification carries the clickable link.
    assert body["review_url"] in body["notification"]["message"]


def test_review_page_shows_source_and_flagged_sop(client):
    run_id = _fire_webhook(client).get_json()["run_id"]
    page = client.get(f"/review/{run_id}")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Jira release v3.1" in html
    assert "QA Monitoring SOP" in html
    assert "Approve edits" in html


def test_decision_approves_and_shows_in_queue(client):
    run_id = _fire_webhook(client).get_json()["run_id"]
    dec = client.post(f"/review/{run_id}/decision", json={"decision": "approved", "approver": "Will Tam"})
    assert dec.status_code == 200
    assert dec.get_json()["status"] == "approved"

    queue = client.get("/reviews").get_data(as_text=True)
    assert "Jira release v3.1" in queue
    assert "approved" in queue


def test_decision_rejects(client):
    run_id = _fire_webhook(client).get_json()["run_id"]
    dec = client.post(f"/review/{run_id}/decision", json={"decision": "rejected"})
    assert dec.get_json()["status"] == "rejected"


def test_bad_decision_is_400(client):
    run_id = _fire_webhook(client).get_json()["run_id"]
    res = client.post(f"/review/{run_id}/decision", json={"decision": "whenever"})
    assert res.status_code == 400


def test_missing_review_is_404(client):
    res = client.get("/review/999999")
    assert res.status_code == 404
    assert "not found" in res.get_data(as_text=True).lower()


def test_empty_queue_renders(client):
    res = client.get("/reviews")
    assert res.status_code == 200
    assert "No reviews yet" in res.get_data(as_text=True)
