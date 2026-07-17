"""core/jira.py -- turn a Jira webhook event into a change note.

The automated trigger. Instead of a human remembering to paste a release note,
Jira posts a webhook when a version ships or an issue is labelled as a policy or
process change. This module decides whether an event should fire SOPatch and
extracts the human-readable change text, handling Jira Cloud's ADF description
format. Pure functions, unit-tested.
"""

from __future__ import annotations

# Events and labels that mean "something shipped that might make an SOP stale".
TRIGGER_EVENTS = {"jira:version_released"}
DEFAULT_TRIGGER_LABELS = {"policy-change", "process-change", "sop-update", "release-note"}


def should_trigger(event, trigger_labels=DEFAULT_TRIGGER_LABELS):
    """True if this Jira event should run SOPatch."""
    if not isinstance(event, dict):
        return False
    if event.get("webhookEvent") in TRIGGER_EVENTS:
        return True
    fields = (event.get("issue") or {}).get("fields") or {}
    labels = set(fields.get("labels") or [])
    return bool(labels & set(trigger_labels))


def _adf_to_text(node):
    """Flatten Jira Cloud's Atlassian Document Format (ADF) into plain text.

    Jira Cloud issue descriptions are a JSON document, not a string. Walk it and
    collect the text nodes so the model sees the actual change description.
    """
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "\n".join(t for t in (_adf_to_text(n) for n in node) if t)
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        return _adf_to_text(node.get("content", []))
    return ""


def extract_change_note(event):
    """Pull the human-readable change text out of a Jira event.

    Handles a released version (name + description) and an issue (key + summary +
    description, where the description may be an ADF object on Jira Cloud).
    """
    version = event.get("version")
    if version:
        parts = [
            f"Release {(version.get('name') or '').strip()}".strip(),
            (version.get("description") or "").strip(),
        ]
        return "\n\n".join(p for p in parts if p)

    issue = event.get("issue") or {}
    fields = issue.get("fields") or {}
    key = (issue.get("key") or "").strip()
    summary = (fields.get("summary") or "").strip()
    desc = fields.get("description")
    desc_text = _adf_to_text(desc).strip() if desc else ""
    header = f"{key}: {summary}".strip(": ").strip()
    return "\n\n".join(p for p in [header, desc_text] if p)


def source_label(event):
    """A short label for the change source, for logs and the reviewer message."""
    version = event.get("version")
    if version:
        return f"Jira release {(version.get('name') or '').strip()}".strip()
    issue = event.get("issue") or {}
    key = (issue.get("key") or "").strip()
    return f"Jira {key}" if key else "a Jira event"
