"""core/matching.py -- tag/label matching for the tagger.

The tagger flags an SOP when an extracted release-note tag matches one of the
SOP's labels. The original rule was exact string equality, which is brittle:
the model extracts 'weekly-cx-reporting' but the label is 'weekly-reporting',
so they never match and the SOP is missed. The eval surfaced exactly this --
the misses were retrieval, not the model.

This module replaces exact equality with token-aware matching: two hyphenated
tags match if they're equal, if one's tokens are a subset of the other's, or if
their token sets overlap strongly. It stays cheap and dependency-free (no
embeddings) while recovering the near-misses. Pure functions, unit-tested.
"""

from __future__ import annotations

# A subset match needs at least this many shared tokens, so a single generic
# token (e.g. 'sla' or 'ticket') can't match everything and tank precision.
_MIN_SUBSET_TOKENS = 2

# Jaccard floor for the overlap fallback (when neither tag is a subset).
_JACCARD_THRESHOLD = 0.6


def _tokens(tag):
    return {t for t in tag.lower().split("-") if t}


def tags_match(tag, label):
    """True if a release-note tag and an SOP label refer to the same concept."""
    if tag == label:
        return True
    a, b = _tokens(tag), _tokens(label)
    if not a or not b:
        return False
    smaller, larger = (a, b) if len(a) <= len(b) else (b, a)
    if len(smaller) >= _MIN_SUBSET_TOKENS and smaller <= larger:
        return True
    return len(a & b) / len(a | b) >= _JACCARD_THRESHOLD


def matched_labels(note_tags, sop_labels):
    """The SOP labels that match at least one extracted note tag."""
    note_tags = list(note_tags)
    return {
        label
        for label in sop_labels
        if any(tags_match(tag, label) for tag in note_tags)
    }
