"""
tagger.py -- SOPatch AI Matching Engine

Loads SOPs directly from Confluence (labels + content).
Uses Claude to extract semantic tags from the release note,
then matches those against each SOP's native Confluence labels.

No local files or external registries -- Confluence is the single source of truth.

Matching flow:
  1. Fetch all SOP pages from Confluence (with their labels)
  2. Claude reads the release note and extracts relevant tags
  3. Token-aware match of those tags against each SOP's labels (cheap, no extra call)
  4. Content gate (opt-in, SOPATCH_CONTENT_GATE=1): re-check the SOPs the labels
     missed against their actual content with one call, to lift recall at a
     measured precision cost
  5. Only matched SOPs go to the full analyzer

Fallback (no labels set):
  If SOPs have no labels yet, the content gate scans every SOP instead.
  Run setup_tags.py to generate and write labels to Confluence.
"""

import os
import re
import json
from dotenv import load_dotenv
from core.confluence import get_sop_pages, get_credentials
from core.config import MODEL
from core.matching import matched_labels
from core.llm import get_client, complete
from core.logging import get_logger

load_dotenv()

log = get_logger("sopatch.tagger")


def load_sops_from_confluence():
    """Pull all SOP pages from Confluence, including their labels."""
    creds = get_credentials()
    pages = get_sop_pages(creds)
    return [
        {
            'page_id': p['page_id'],
            'filename': f"{p['page_id']}.confluence",
            'title': p['title'],
            'content': p['content'],
            'labels': p['labels']
        }
        for p in pages
    ]


# ── Tag extraction from release note ────────────────────────────────────────

def extract_tags_from_release_note(client, release_note_text):
    """Ask Claude to extract semantic tags from the release note."""
    prompt = f"""You are analyzing a product release note to extract tags for matching against SOP labels.

Generate 4-10 tags that describe the SPECIFIC operational processes this release note affects.

Rules:
- Focus on the specific workflows that need to change (e.g. "ticket-triage", "sla-breach-review", "agent-qa-scoring", "weekly-reporting")
- Do NOT include generic tools (zendesk, slack, notion) unless the change is specifically about how that tool works
- Do NOT include generic team names (cx-operations, cx-support)
- Tags must be lowercase, hyphen-separated
- Match the specificity of SOP labels -- narrow enough to avoid false positives
- Respond with ONLY a JSON array of strings, no explanation

RELEASE NOTE:
{release_note_text}"""

    message = complete(
        client,
        model=MODEL,
        max_tokens=256,
        messages=[{'role': 'user', 'content': prompt}]
    )

    response_text = message.content[0].text.strip()
    if '```' in response_text:
        match = re.search(r'```(?:json)?\s*([\s\S]+?)```', response_text)
        if match:
            response_text = match.group(1).strip()

    return json.loads(response_text)


# ── Mode 1: Label-based matching ─────────────────────────────────────────────

def match_with_labels(release_note_text, sops):
    """
    Extract tags from the release note and match them against each SOP's labels,
    then use the content gate as a recall booster on whatever the labels missed.
    """
    client = get_client()

    note_tags = set(extract_tags_from_release_note(client, release_note_text))
    log.info("tagger.tags_extracted", tags=sorted(note_tags))

    affected, unmatched = [], []
    for sop in sops:
        overlap = matched_labels(note_tags, sop['labels'])
        if overlap:
            affected.append(_affected_entry(sop, sorted(overlap)))
        else:
            unmatched.append(sop)

    # Recall booster: label matching only fires when the model emits a tag that
    # overlaps a label string, which it doesn't always do. Re-check the SOPs the
    # labels missed against their actual content with one cheap call.
    if content_gate_enabled() and unmatched:
        recovered = content_gate(client, release_note_text, unmatched)
        if recovered:
            log.info("tagger.content_gate_recovered", count=len(recovered))
        still_unmatched = []
        for sop in unmatched:
            if sop['page_id'] in recovered:
                affected.append(_affected_entry(sop, ['content-match']))
            else:
                still_unmatched.append(sop)
        unmatched = still_unmatched

    unaffected = [sop['title'] for sop in unmatched]
    return affected, unaffected


# ── Content gate: does this release note affect these SOPs, by content? ───────

def content_gate_enabled():
    """The content-gate recall booster is opt-in (off by default).

    Measured tradeoff: it takes recall to ~1.00 but drops precision (it
    over-flags tangential SOPs) and adds a call per analysis, so it's left off
    by default and turned on with SOPATCH_CONTENT_GATE=1 for recall-critical use.
    """
    return os.environ.get('SOPATCH_CONTENT_GATE', '0') == '1'


def content_gate(client, release_note_text, sops):
    """Ask Claude which of these SOPs are affected, reading their actual content.

    This is the content-aware stage: it catches SOPs label matching misses
    because the model's extracted tags didn't happen to overlap a label string.
    Returns the set of affected page_ids. Used both as the recall booster in
    match_with_labels and as the full fallback scan when no labels exist.

    At a few dozen SOPs this is cheaper and more accurate than embeddings; a
    vector index would only earn its keep at thousands of documents.
    """
    sop_list = '\n\n'.join(
        f"Page ID: {sop['page_id']}\nTitle: {sop['title']}\n\n{sop['content']}"
        for sop in sops
    )

    prompt = f"""You are checking whether a product release note REQUIRES an edit to each internal SOP below.

Mark an SOP as affected ONLY if the release note clearly and specifically requires changing that SOP's own steps, policies, or wording. If the SOP is merely related, adjacent, or only tangentially connected to the change, mark it UNAFFECTED. When in doubt, mark it unaffected -- a false alarm wastes a reviewer's time.

Respond with ONLY a valid JSON object in this exact format, no explanation:
{{"affected": ["page_id_1"], "unaffected": ["page_id_2", "page_id_3"]}}

Use the Page ID values exactly as given.

RELEASE NOTE:
{release_note_text}

---

SOPs TO REVIEW:
{sop_list}"""

    message = complete(
        client,
        model=MODEL,
        max_tokens=512,
        messages=[{'role': 'user', 'content': prompt}]
    )

    response_text = message.content[0].text.strip()
    if '```' in response_text:
        match = re.search(r'```(?:json)?\s*([\s\S]+?)```', response_text)
        if match:
            response_text = match.group(1).strip()

    result = json.loads(response_text)
    return set(result.get('affected', []))


# ── Mode 2: Full content scan (fallback when no labels exist) ────────────────

def match_sops_with_ai(release_note_text, sops):
    """
    Fallback for when no SOP has labels yet (before setup_tags.py is run):
    run the content gate over every SOP.
    """
    client = get_client()
    affected_ids = content_gate(client, release_note_text, sops)

    affected, unaffected = [], []
    for sop in sops:
        if sop['page_id'] in affected_ids:
            affected.append(_affected_entry(sop, []))
        else:
            unaffected.append(sop['title'])

    return affected, unaffected


def _affected_entry(sop, matching_tags):
    """Build the affected-SOP dict the analyzer consumes."""
    return {
        'page_id': sop['page_id'],
        'filename': sop['filename'],
        'title': sop['title'],
        'content': sop['content'],
        'matching_tags': matching_tags,
    }


# ── Main entry point ─────────────────────────────────────────────────────────

def run_tagger(release_note_text):
    """
    Load SOPs from Confluence and match against the release note.

    Uses label-based matching if labels exist on the SOP pages.
    Falls back to full AI scan if no labels are found (run setup_tags.py to fix).
    """
    sops = load_sops_from_confluence()
    log.info("tagger.sops_loaded", count=len(sops))

    # Check if any SOPs have labels
    sops_with_labels = [s for s in sops if s['labels']]

    if sops_with_labels:
        log.info("tagger.match_mode", mode="labels")
        return _build_result(*match_with_labels(release_note_text, sops))
    else:
        log.info("tagger.match_mode", mode="full_ai_scan", hint="run setup_tags.py to enable label matching")
        return _build_result(*match_sops_with_ai(release_note_text, sops))


def _build_result(affected_sops, unaffected_sops):
    return {
        'affected_sops': affected_sops,
        'unaffected_sops': unaffected_sops
    }
