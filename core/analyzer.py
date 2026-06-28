"""
analyzer.py -- SOPatch Claude Analysis Engine

Takes the release note and a list of affected SOPs.
Sends each SOP to Claude with the release note for comparison.
Returns flagged sections and suggested rewrites for each SOP.
"""

import os
from dotenv import load_dotenv
from core.config import MODEL
from core.grounding import ground_analysis
from core.llm import get_client, complete
from core.logging import get_logger

load_dotenv()

log = get_logger("sopatch.analyzer")


def build_prompt(release_note_text, sop_content, sop_title):
    """
    Build the Claude prompt for a single SOP analysis.
    Intentionally structured -- core logic abstracted for GitHub publication.
    """
    return f"""You are a CX Operations specialist reviewing internal SOPs for accuracy after a product release.

You will be given:
1. A release note describing what changed in the product
2. An existing SOP document

Your job is to:
- Identify every section or step in the SOP that is now outdated, incomplete, or incorrect based on the release note
- For each affected section, explain exactly why it needs updating
- Provide a specific suggested rewrite for each affected section

Important rules:
- Only flag sections that are genuinely affected by the release note
- Do not suggest changes to sections that are still accurate
- Be specific -- quote the exact outdated wording
- Keep suggested rewrites in the same style and format as the original SOP
- Do NOT include any introduction, summary, or closing sentence -- output only the structured blocks below

Format your response exactly like this for each affected section, with no text before the first --- or after the last ---:

---
SECTION: [section name or step number]
CURRENT WORDING: [quote the exact current text]
WHY OUTDATED: [one or two sentences explaining the issue]
SUGGESTED REWRITE: [the new wording to replace it]
---

RELEASE NOTE:
{release_note_text}

SOP TITLE: {sop_title}

SOP CONTENT:
{sop_content}"""


def analyze_sop(client, release_note_text, sop):
    """
    Send one SOP to Claude for analysis.
    Returns the analysis result for that SOP.
    """
    prompt = build_prompt(release_note_text, sop['content'], sop['title'])

    message = complete(
        client,
        model=MODEL,
        max_tokens=4096,
        messages=[
            {'role': 'user', 'content': prompt}
        ]
    )

    # Grounding guard: drop any flagged section whose quoted current wording
    # can't be found in the source SOP (a hallucinated edit).
    analysis, dropped = ground_analysis(message.content[0].text, sop['content'])
    if dropped:
        log.info("analyzer.dropped_ungrounded", sop=sop['title'], count=len(dropped))

    return {
        'filename': sop['filename'],
        'title': sop['title'],
        'matching_tags': sop['matching_tags'],
        'analysis': analysis
    }


def analyze_all_sops(release_note_text, affected_sops):
    """
    Analyze all affected SOPs one by one.
    Creates the Claude client once and reuses it across all calls.
    Returns a list of analysis results.
    """
    client = get_client()
    results = []
    for sop in affected_sops:
        log.info("analyzer.analyzing", sop=sop['title'])
        result = analyze_sop(client, release_note_text, sop)
        results.append(result)
    return results


def refine_section(release_note_text, sop_title, section_name, current_wording, why_outdated, suggested_rewrite, user_instruction):
    """
    Re-run Claude on a single section with additional user instruction.
    Returns just the new suggested rewrite text.
    """
    client = get_client()

    prompt = f"""You are a CX Operations specialist refining a suggested SOP rewrite.

CONTEXT:
- SOP Title: {sop_title}
- Section: {section_name}
- Release note that triggered the change:
{release_note_text}

CURRENT WORDING IN THE SOP:
{current_wording}

WHY THIS SECTION IS OUTDATED:
{why_outdated}

PREVIOUS SUGGESTED REWRITE:
{suggested_rewrite}

USER'S INSTRUCTION FOR REFINEMENT:
{user_instruction}

Your task: Produce an improved suggested rewrite that follows the user's instruction above.
Keep the same style and format as the original SOP section.
Output ONLY the new rewrite text -- no labels, no explanation, no preamble."""

    message = complete(
        client,
        model=MODEL,
        max_tokens=1024,
        messages=[{'role': 'user', 'content': prompt}]
    )
    return message.content[0].text.strip()


# Quick test -- run this file directly to verify analyzer works
if __name__ == '__main__':
    from tagger import run_tagger

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    release_note_path = os.path.join(base_dir, 'data', 'release_note.txt')
    sop_directory = os.path.join(base_dir, 'data', 'sops')

    print("Running tagger...")
    tagger_result = run_tagger(release_note_path, sop_directory)

    print(f"Analyzing {len(tagger_result['affected_sops'])} affected SOPs...\n")
    results = analyze_all_sops(
        tagger_result['release_note_text'],
        tagger_result['affected_sops']
    )

    for result in results:
        print(f"\n{'='*60}")
        print(f"SOP: {result['title']}")
        print(f"Matched on: {result['matching_tags']}")
        print(f"{'='*60}")
        print(result['analysis'])
