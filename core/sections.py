"""core/sections.py -- parse the analyzer's wire format into review sections.

The analyzer serialises each flagged SOP as `---`-delimited blocks with SECTION /
CURRENT WORDING / WHY OUTDATED / SUGGESTED REWRITE labels (the same shape the
browser UI parses in JS). The server-rendered review page needs it as structured
data, so this turns that text into a list of dicts. Pure and unit-tested.
"""

from __future__ import annotations

# Label prefix -> dict key. Order matters only for readability.
_LABELS = {
    "SECTION": "section",
    "CURRENT WORDING": "current_wording",
    "WHY OUTDATED": "why_outdated",
    "SUGGESTED REWRITE": "suggested_rewrite",
}

_KEYS = ("section", "current_wording", "why_outdated", "suggested_rewrite")


def _finalize(block):
    """Ensure every key exists so the template never trips on a missing field."""
    return {key: block.get(key, "").strip() for key in _KEYS}


def parse_sections(analysis_text):
    """Turn an analyzer result string into a list of section dicts.

    Each dict has section / current_wording / why_outdated / suggested_rewrite.
    Unknown lines that follow a label are treated as continuations of that field,
    so a multi-line rewrite survives intact. Blocks with no content are dropped.
    """
    sections = []
    current = {}
    field = None
    for raw in (analysis_text or "").splitlines():
        stripped = raw.strip()
        if stripped == "---":
            if current:
                sections.append(_finalize(current))
                current, field = {}, None
            continue
        matched = False
        for label, key in _LABELS.items():
            if stripped.startswith(label + ":"):
                current[key] = stripped[len(label) + 1:].strip()
                field = key
                matched = True
                break
        if not matched and field is not None and stripped:
            current[field] = (current.get(field, "") + "\n" + raw).strip()
    if current:
        sections.append(_finalize(current))
    return [s for s in sections if s["section"] or s["suggested_rewrite"]]
