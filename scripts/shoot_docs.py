"""scripts/shoot_docs.py -- regenerate the screenshots in docs/.

The README's screenshots went stale the moment the UI changed, which is the
normal fate of hand-captured images. This script regenerates them from the real
app so they can never drift far: it boots SOPatch in Demo Mode against a throwaway
database, seeds a representative review queue, drives the actual UI, and writes
the PNGs the README points at.

    pip install -r requirements-dev.txt
    playwright install chromium
    python scripts/shoot_docs.py

Demo Mode makes no external calls, so this needs no API keys and touches nothing
real. It writes only to docs/ and a temp directory.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
VIEWPORT = {"width": 1280, "height": 800}
# Retina-scale so the text stays crisp after GitHub and LinkedIn recompress it.
SCALE = 2


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(base, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base}/healthz", timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def _seed(db_path):
    """A queue that looks like a real one: one approved, one still waiting."""
    sys.path.insert(0, str(REPO))
    os.environ["SOPATCH_DB"] = db_path
    from core.store import ReviewStore
    from demo_data import DEMO_ANALYSIS

    store = ReviewStore(db_path=db_path)
    approved = store.create_run(
        "Jira release v3.1",
        "Release v3.1\n\nAI Chat Assistant launch. Unresolved chat queries are escalated "
        "to Zendesk tagged [chat-escalation]. The SLA clock for chat-escalated tickets "
        "starts when the chatbot fails to resolve, not when the agent picks up.",
        DEMO_ANALYSIS,
    )
    store.record_event(approved, "notified", detail="log")
    store.set_decision(approved, "approved", actor="Will Tam")

    pending = store.create_run(
        "Jira OPS-42",
        "OPS-42: Refund window changed to 14 days for chat-escalated tickets\n\n"
        "Effective immediately, the refund window for tickets tagged [chat-escalation] "
        "extends from 7 to 14 days. Update any SOP that quotes the 7-day window.",
        DEMO_ANALYSIS,
    )
    store.record_event(pending, "notified", detail="log")
    return pending


def main():
    from playwright.sync_api import sync_playwright

    tmp = tempfile.mkdtemp(prefix="sopatch-shots-")
    db_path = os.path.join(tmp, "shots.db")
    pending_id = _seed(db_path)

    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    env = {**os.environ, "SOPATCH_DEMO": "1", "SOPATCH_DB": db_path,
           "PORT": str(port), "FLASK_DEBUG": "0"}
    server = subprocess.Popen([sys.executable, "app.py"], cwd=REPO, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not _wait_for_server(base):
            raise SystemExit("the demo server did not come up")
        DOCS.mkdir(exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport=VIEWPORT, device_scale_factor=SCALE)
            # Pin the light theme: it reads better in a README than dark.
            page.add_init_script(
                "try { localStorage.setItem('sopatch-theme','light'); } catch (e) {}")

            # 1. The dashboard mid-story: a Jira release has just been picked up,
            #    the SOPs are flagged, and the reviewer has a real link to open.
            page.goto(base, wait_until="networkidle")
            page.click("#btn-simulate")
            page.wait_for_selector(".slack-review-btn", timeout=30_000)
            page.wait_for_timeout(400)
            page.screenshot(path=str(DOCS / "demo.png"))

            # 2. The queue, with a decided run and a waiting one.
            page.goto(f"{base}/reviews", wait_until="networkidle")
            page.wait_for_timeout(300)
            page.screenshot(path=str(DOCS / "review-queue.png"))

            # 3. One review still awaiting a human, showing the before/after.
            page.goto(f"{base}/review/{pending_id}", wait_until="networkidle")
            page.wait_for_timeout(300)
            page.screenshot(path=str(DOCS / "review-page.png"))

            browser.close()

        for name in ("demo.png", "review-queue.png", "review-page.png"):
            size = (DOCS / name).stat().st_size
            print(f"  wrote docs/{name}  ({size // 1024} KB)")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
