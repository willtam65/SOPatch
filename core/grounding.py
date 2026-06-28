"""core/grounding.py -- drop hallucinated edits.

The analyzer is told to quote the SOP's existing wording it wants to change. If
that quoted "current wording" doesn't actually appear in the source SOP, the
model invented it -- a hallucinated edit. In a tool that pushes changes back to
a real wiki, showing a confident edit to a sentence that doesn't exist is a
liability, so we drop any flagged section whose quoted current wording can't be
found in the source.

This is a check we write, not a model setting. Pure functions, unit-tested.
"""

from __future__ import annotations

import re

from core.confluence import parse_analysis_blocks

_QUOTE_CHARS = "\"'“”‘’"


def _normalize(text):
    """Lowercase, strip surrounding quotes, collapse whitespace -- for matching."""
    text = text.strip().strip(_QUOTE_CHARS)
    return re.sub(r"\s+", " ", text).strip().lower()


def is_grounded(current_wording, sop_content):
    """True if the quoted current wording can be found in the source SOP.

    Falls back to matching just the first sentence (the model sometimes quotes a
    slightly longer span than the verbatim source), mirroring how the UI's diff
    preview locates the text it's about to strike through.
    """
    cur = _normalize(current_wording)
    if not cur:
        return False
    src = _normalize(sop_content)
    if cur in src:
        return True
    first_sentence = re.split(r"[.!?]", cur)[0].strip()
    return len(first_sentence) > 10 and first_sentence in src


def _blocks_to_text(blocks):
    """Re-serialize parsed blocks back into the SECTION/.../--- analysis format."""
    if not blocks:
        return ""
    inner = "\n---\n".join(
        f"SECTION: {b.get('section', '')}\n"
        f"CURRENT WORDING: {b.get('current', '')}\n"
        f"WHY OUTDATED: {b.get('why', '')}\n"
        f"SUGGESTED REWRITE: {b.get('rewrite', '')}"
        for b in blocks
    )
    return f"---\n{inner}\n---"


def ground_analysis(analysis_text, sop_content):
    """Filter out flagged sections whose current wording isn't in the source SOP.

    Returns (grounded_text, dropped_blocks). If the analysis can't be parsed into
    structured blocks, it's returned unchanged (nothing to verify against).
    """
    blocks = parse_analysis_blocks(analysis_text)
    if not blocks:
        return analysis_text, []
    kept, dropped = [], []
    for block in blocks:
        if is_grounded(block.get("current", ""), sop_content):
            kept.append(block)
        else:
            dropped.append(block)
    return _blocks_to_text(kept), dropped
