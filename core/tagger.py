"""
tagger.py -- SOPatch AI Matching Engine

Loads SOPs directly from Confluence (labels + content).
Uses Claude to extract semantic tags from the release note,
then matches those against each SOP's native Confluence labels.

No local files or external registries -- Confluence is the single source of truth.

Matching flow:
  1. Fetch all SOP pages from Confluence (with their labels)
  2. Claude reads the release note and extracts relevant tags
  3. Tag intersection against each SOP's labels
  4. Only matched SOPs go to the full analyzer

Fallback (no labels set):
  If SOPs have no labels yet, falls back to full AI scan.
  Run setup_tags.py to generate and write labels to Confluence.
"""

import os
import re
import json
import anthropic
from dotenv import load_dotenv
from core.confluence import get_sop_pages, get_credentials
from core.config import MODEL
from core.matching import matched_labels

load_dotenv()


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

    message = client.messages.create(
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
    Extract tags from the release note, match against Confluence labels.
    Only SOPs with overlapping labels are flagged as affected.
    """
    client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    print("  [SOPatch] Extracting release note tags...")
    note_tags = set(extract_tags_from_release_note(client, release_note_text))
    print(f"  Tags: {', '.join(note_tags)}")

    affected = []
    unaffected = []

    for sop in sops:
        overlap = matched_labels(note_tags, sop['labels'])
        if overlap:
            affected.append({
                'page_id': sop['page_id'],
                'filename': sop['filename'],
                'title': sop['title'],
                'content': sop['content'],
                'matching_tags': sorted(overlap)
            })
        else:
            unaffected.append(sop['title'])

    return affected, unaffected


# ── Mode 2: Full AI scan (fallback when no labels exist) ─────────────────────

def match_sops_with_ai(release_note_text, sops):
    """
    Fallback: send release note + all SOP content to Claude.
    Used when SOPs have no labels set yet (before setup_tags.py is run).
    """
    client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    sop_list = '\n\n'.join([
        f"Page ID: {sop['page_id']}\nTitle: {sop['title']}\n\n{sop['content']}"
        for sop in sops
    ])

    prompt = f"""You are reviewing internal SOPs to determine which ones need updating based on a product release note.

An SOP is affected if any of its steps, processes, or policies would need to change based on what is described in the release note.

Respond with ONLY a valid JSON object in this exact format, no explanation:
{{"affected": ["page_id_1", "page_id_2"], "unaffected": ["page_id_3"]}}

Use the Page ID values exactly as given.

RELEASE NOTE:
{release_note_text}

---

SOPs TO REVIEW:
{sop_list}"""

    message = client.messages.create(
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
    affected_ids = set(result.get('affected', []))

    affected, unaffected = [], []
    for sop in sops:
        if sop['page_id'] in affected_ids:
            affected.append({**sop, 'matching_tags': []})
        else:
            unaffected.append(sop['title'])

    return affected, unaffected


# ── Main entry point ─────────────────────────────────────────────────────────

def run_tagger(release_note_text):
    """
    Load SOPs from Confluence and match against the release note.

    Uses label-based matching if labels exist on the SOP pages.
    Falls back to full AI scan if no labels are found (run setup_tags.py to fix).
    """
    print("  [SOPatch] Loading SOPs from Confluence...")
    sops = load_sops_from_confluence()
    print(f"  Loaded {len(sops)} SOP(s).")

    # Check if any SOPs have labels
    sops_with_labels = [s for s in sops if s['labels']]

    if sops_with_labels:
        print(f"  [SOPatch] Labels found -- using label-based matching.")
        return _build_result(*match_with_labels(release_note_text, sops))
    else:
        print("  [SOPatch] No labels found -- using full AI scan. Run setup_tags.py to enable label matching.")
        return _build_result(*match_sops_with_ai(release_note_text, sops))


def _build_result(affected_sops, unaffected_sops):
    return {
        'affected_sops': affected_sops,
        'unaffected_sops': unaffected_sops
    }
