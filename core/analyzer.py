"""
analyzer.py -- SOPatch Claude Analysis Engine

Takes the release note and a list of affected SOPs.
Sends each SOP to Claude with the release note for comparison.
Returns flagged sections and suggested rewrites for each SOP.
"""

from dotenv import load_dotenv
from core.config import MODEL
from core.grounding import ground_sections
from core.llm import get_client, complete
from core.logging import get_logger
from core.schema import AnalysisResult, ANALYSIS_TOOL, sections_to_text

load_dotenv()

log = get_logger("sopatch.analyzer")


def build_prompt(release_note_text, sop_content, sop_title):
    """Build the Claude prompt for a single SOP analysis.

    Structure is enforced by the report_flagged_sections tool, so the prompt
    only has to describe the task and the quoting rule that grounding relies on.
    """
    return f"""You are a CX Operations specialist reviewing an internal SOP for accuracy after a product release.

You are given a release note describing what changed, and an existing SOP. Identify every section or step in the SOP that is now outdated, incomplete, or incorrect because of the release note, and report them by calling the report_flagged_sections tool.

Rules:
- Only flag sections genuinely affected by the release note. Do not flag sections that are still accurate.
- Quote the current wording VERBATIM from the SOP (copy the exact text) so it can be located in the document.
- Keep each suggested rewrite in the same style and format as the original SOP.
- If nothing is affected, call the tool with an empty sections list.

RELEASE NOTE:
{release_note_text}

SOP TITLE: {sop_title}

SOP CONTENT:
{sop_content}"""


def _extract_tool_input(message, tool_name):
    """Pull the forced tool call's validated input out of the response."""
    for block in message.content:
        if getattr(block, 'type', None) == 'tool_use' and block.name == tool_name:
            return block.input
    return {'sections': []}


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
        tools=[ANALYSIS_TOOL],
        tool_choice={'type': 'tool', 'name': ANALYSIS_TOOL['name']},
        messages=[
            {'role': 'user', 'content': prompt}
        ]
    )

    # Structured output: the model is forced to call the tool, so we read and
    # validate its input instead of regex-parsing free text.
    result = AnalysisResult(**_extract_tool_input(message, ANALYSIS_TOOL['name']))

    # Grounding guard: drop any flagged section whose quoted current wording
    # can't be found in the source SOP (a hallucinated edit). Then serialize the
    # survivors into the block format the frontend and push step expect.
    kept, dropped = ground_sections(result.sections, sop['content'])
    if dropped:
        log.info("analyzer.dropped_ungrounded", sop=sop['title'], count=len(dropped))

    return {
        'filename': sop['filename'],
        'title': sop['title'],
        'matching_tags': sop['matching_tags'],
        'analysis': sections_to_text(kept)
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
