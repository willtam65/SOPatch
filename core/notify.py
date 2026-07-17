"""core/notify.py -- tell a reviewer when the auto-trigger flags SOPs.

When the Jira webhook runs SOPatch on its own, a human still approves the edits.
This sends that reviewer a short message: what changed, which SOPs were flagged,
and where to review. It posts to Slack when SLACK_WEBHOOK_URL is set; otherwise
it logs the message, so the trigger is fully demonstrable with no external
service wired up.
"""

from __future__ import annotations

import os

import requests

from core.logging import get_logger

log = get_logger("sopatch.notify")


def format_review_notification(source, result, review_url=None):
    """Compose the reviewer message from a change source and an analysis result."""
    affected = result.get("affected_count", 0)
    if not affected:
        return f"SOPatch checked {source} and found no SOPs affected."
    titles = [r.get("title", "") for r in result.get("results", []) if r.get("title")]
    lines = [f"SOPatch flagged {affected} SOP(s) after {source}:"]
    lines += [f"  - {t}" for t in titles]
    lines.append("Review and approve before anything is pushed to Confluence.")
    if review_url:
        lines.append(review_url)
    return "\n".join(lines)


def send_notification(text):
    """Post to Slack if configured, otherwise log. Returns {sent, channel}."""
    url = os.getenv("SLACK_WEBHOOK_URL")
    if not url:
        log.info("notify.logged", message=text)
        return {"sent": False, "channel": "log"}
    try:
        requests.post(url, json={"text": text}, timeout=10)
        return {"sent": True, "channel": "slack"}
    except requests.RequestException as e:
        log.error("notify.slack_error", error=str(e))
        return {"sent": False, "channel": "slack-error"}
