"""Endpoint tests for validation, demo mode, and health -- no API key needed.

All paths exercised here short-circuit before any network call (demo payload,
validation 400, or /healthz), so the suite stays hermetic and CI-safe.
"""

import pytest

from app import app


@pytest.fixture
def client(monkeypatch):
    # Ensure the process-wide demo flag isn't forcing demo, so validation runs.
    monkeypatch.delenv("SOPATCH_DEMO", raising=False)
    app.config.update(TESTING=True)
    return app.test_client()


def test_healthz_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_analyze_demo_returns_payload(client):
    r = client.post("/analyze", json={"release_note": "anything", "demo": True})
    assert r.status_code == 200
    assert "results" in r.get_json()


def test_analyze_rejects_missing_release_note(client):
    r = client.post("/analyze", json={"demo": False})
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_analyze_rejects_non_json_body(client):
    r = client.post("/analyze", data="not json", content_type="text/plain")
    assert r.status_code == 400


def test_analyze_rejects_oversized_release_note(client):
    r = client.post("/analyze", json={"release_note": "x" * 50001})
    assert r.status_code == 400


def test_refine_disabled_in_demo(client):
    r = client.post("/refine", json={"demo": True, "user_instruction": "shorter"})
    assert r.status_code == 400


def test_push_rejects_missing_fields(client):
    r = client.post("/push", json={"demo": False})
    assert r.status_code == 400


def test_error_response_does_not_leak_internals(client):
    # A validation failure should return a clean message, never a stack trace.
    r = client.post("/analyze", json={})
    body = r.get_json()
    assert r.status_code == 400
    assert "Traceback" not in body["error"]
