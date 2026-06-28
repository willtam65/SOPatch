"""
setup_tags.py -- SOPatch First-Time Setup

Run this script once when onboarding SOPatch to a new company.
Fetches all SOP pages from Confluence, uses Claude to generate semantic tags,
and writes them directly as native Confluence labels on each page.

No external files needed -- the labels live in Confluence alongside the SOPs.
Re-run this script whenever SOPs are significantly restructured or renamed.

Usage:
    python setup_tags.py
"""

import os
import re
import json
import anthropic
from dotenv import load_dotenv
from core.confluence import get_sop_pages, set_page_labels, get_credentials
from core.config import MODEL

load_dotenv()


def generate_labels_for_sop(client, sop_title, sop_content):
    """
    Ask Claude to generate semantic labels for a single SOP.
    Returns a list of lowercase hyphen-separated label strings.
    """
    prompt = f"""You are generating Confluence labels for an internal SOP so it can be matched against product release notes.

Your goal is to produce labels that are UNIQUE to this SOP's specific domain -- labels that would NOT appear on most other SOPs.

Generate 4-8 labels that describe the SPECIFIC process this SOP covers.

Rules:
- Focus on what makes this SOP distinct from others (e.g. "agent-qa-scoring", "sla-breach-review", "ticket-triage")
- Do NOT include generic tools used by everyone (zendesk, slack, notion, google-sheets) unless the SOP is specifically about configuring or administering that tool
- Do NOT include generic team names (cx-operations, cx-support, engineering) -- these appear on every SOP
- Do NOT include generic concepts (escalation, reporting) unless this SOP is the primary owner of that process
- Tags must be lowercase, hyphen-separated
- Respond with ONLY a JSON array of strings, no explanation

SOP TITLE: {sop_title}

SOP CONTENT:
{sop_content}"""

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


def run_setup():
    creds = get_credentials()
    client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    print("SOPatch Label Setup")
    print(f"Fetching SOPs from Confluence (parent page: {creds['sop_parent_id']})...\n")

    pages = get_sop_pages(creds)
    if not pages:
        print("No SOP pages found. Check CONFLUENCE_SOP_PARENT_ID in .env")
        return

    print(f"Found {len(pages)} SOP(s). Generating and writing labels...\n")

    for page in pages:
        print(f"  {page['title']} (page {page['page_id']})")
        try:
            labels = generate_labels_for_sop(client, page['title'], page['content'])
            set_page_labels(page['page_id'], labels, creds)
            print(f"    Labels written: {', '.join(labels)}")
        except Exception as e:
            print(f"    Error: {e}")

    print("\nDone. Labels are now visible on each SOP page in Confluence.")
    print("SOPatch will use these labels for matching -- no local files needed.")
    print("Re-run this script only if SOPs are significantly restructured.")


if __name__ == '__main__':
    run_setup()
