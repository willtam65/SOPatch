"""
demo_data.py -- Self-contained sample data for SOPatch Demo Mode.

This module powers Demo Mode ONLY. It makes no network calls: the analysis
result below is hardcoded, and the original SOP bodies are read from the
local files in data/sops/ so the "before" side of every diff stays accurate.

The live flow (core/confluence.py + core/analyzer.py) never touches this file.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOPS_DIR = os.path.join(BASE_DIR, 'data', 'sops')

# Visual + copy constants used by the demo branches.
DEMO_BANNER_TEXT = 'DEMO MODE — sample data, no live Confluence connection'
DEMO_PUSH_MESSAGE = (
    'Demo Mode — in the live app, this pushes the approved rewrite to '
    'Confluence with automatic version and date tracking. Live push is '
    'disabled in this demo.'
)
DEMO_REFINE_MESSAGE = 'Refine uses live AI — disabled in demo.'


def _read_sop(filename):
    """Read a local SOP markdown file. Returns '' if missing rather than raising."""
    try:
        with open(os.path.join(SOPS_DIR, filename), 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ''


# Hardcoded structured analysis text per affected SOP, in the exact
# SECTION / CURRENT WORDING / WHY OUTDATED / SUGGESTED REWRITE format the
# frontend already parses.
_QA_ANALYSIS = """---
SECTION: Step 1 -- QA Sample Selection
CURRENT WORDING: Every week, randomly select 10% of resolved tickets from the previous week for QA review. Use Zendesk's random ticket selector or manually select from the resolved queue.
WHY OUTDATED: With the AI chatbot now escalating unresolved queries to Zendesk as tickets tagged [chat-escalation], the QA sample must explicitly include chat-escalated tickets. These require a new review step (chatbot response accuracy), so random sampling alone may miss them.
SUGGESTED REWRITE: Every week, randomly select 10% of resolved tickets from the previous week for QA review. Use Zendesk's random ticket selector or manually select from the resolved queue. Ensure that tickets tagged [chat-escalation] are proportionally represented in the sample. If the random selection does not include any chat-escalated tickets, manually add a representative sample from that pool.
---
SECTION: Step 2 -- QA Scorecard
CURRENT WORDING: Review each selected ticket against the QA scorecard (Notion: CX Ops > QA Scorecard). Score the following items: Tone and professionalism (1-5), Accuracy of information provided (1-5), Resolution speed relative to SLA (1-5), Proper escalation if needed (1-5).
WHY OUTDATED: The release note adds a mandatory QA checklist item for chat-escalated tickets: "Was the chatbot response accurate before escalation?" This item is not currently in the scorecard.
SUGGESTED REWRITE: Review each selected ticket against the QA scorecard (Notion: CX Ops > QA Scorecard). Score the following items: Tone and professionalism (1-5), Accuracy of information provided (1-5), Resolution speed relative to SLA (1-5), Proper escalation if needed (1-5). For tickets tagged [chat-escalation], additionally score: Was the chatbot response accurate before escalation? (Yes/No, with comments if No). Review the full chatbot conversation history attached to the ticket when scoring this item.
---
"""

_REPORTING_ANALYSIS = """---
SECTION: Step 2 -- Report Assembly
CURRENT WORDING: Populate the weekly CX report template (Google Sheets: CX Ops > Weekly Reports). Compare current week metrics to the previous week and the 4-week rolling average.
WHY OUTDATED: The release note states ticket volume, first response time, and resolution rate are all affected by an expected 35% volume drop from the chatbot launch (May 12, 2026). Direct comparison against pre-launch weeks would be misleading without noting the baseline shift.
SUGGESTED REWRITE: Populate the weekly CX report template (Google Sheets: CX Ops > Weekly Reports). Compare current week metrics to the previous week and the 4-week rolling average. Note: Effective May 12, 2026 (AI Chat Assistant launch), ticket volume, first response time, and resolution rate metrics have been rebaselined. All historical comparisons must reference this date as a baseline shift and must not compare post-launch metrics directly against pre-launch benchmarks without noting the change.
---
SECTION: Step 3 -- Trend Analysis
CURRENT WORDING: Flag any metric that has moved more than 10% week-over-week. Add a one-line explanation for each flagged metric.
WHY OUTDATED: A 35% volume drop is expected from the chatbot launch, which will trigger the 10% threshold for several metrics for reasons unrelated to performance. The trend analysis should account for this expected shift.
SUGGESTED REWRITE: Flag any metric that has moved more than 10% week-over-week. Add a one-line explanation for each flagged metric. For the weeks following the May 12, 2026 chatbot launch, annotate any volume-driven metric movements as expected effects of the chatbot rollout rather than performance changes, until the new baseline stabilizes.
---
"""

_SLA_ANALYSIS = """---
SECTION: Step 1 -- SLA Clock Start
CURRENT WORDING: The SLA clock starts at the moment a ticket is created in Zendesk. This applies to all inbound tickets regardless of source.
WHY OUTDATED: The release note changes the SLA clock rule for chat-escalated tickets: the clock starts when the chatbot fails to resolve the query, not when the agent picks it up. The current blanket rule does not capture this.
SUGGESTED REWRITE: The SLA clock starts at the moment a ticket is created in Zendesk. This applies to all inbound tickets regardless of source. Exception: for tickets tagged [chat-escalation], the SLA clock starts at the moment the chatbot fails to resolve the query (the chatbot escalation timestamp), not when the agent picks up the ticket. Use the chatbot escalation timestamp as the SLA start time for these tickets.
---
"""


def build_demo_analysis():
    """
    Build the demo /analyze payload in the exact JSON shape the live
    /analyze endpoint returns, reading the original SOP bodies from disk.
    """
    return {
        'affected_count': 3,
        'unaffected_count': 1,
        'unaffected_sops': ['Inbound Ticket Triage SOP'],
        'results': [
            {
                'page_id': 'demo-qa-001',
                'filename': 'qa_sop.md',
                'title': 'QA Monitoring SOP',
                'matching_tags': ['agent-qa-scoring', 'chat-escalation'],
                'analysis': _QA_ANALYSIS,
                'sop_content': _read_sop('qa_sop.md'),
            },
            {
                'page_id': 'demo-rep-002',
                'filename': 'reporting_sop.md',
                'title': 'Weekly CX Reporting SOP',
                'matching_tags': ['weekly-reporting', 'metrics-rebaseline'],
                'analysis': _REPORTING_ANALYSIS,
                'sop_content': _read_sop('reporting_sop.md'),
            },
            {
                'page_id': 'demo-sla-003',
                'filename': 'sla_sop.md',
                'title': 'SLA Tracking SOP',
                'matching_tags': ['sla-clock', 'chat-escalation'],
                'analysis': _SLA_ANALYSIS,
                'sop_content': _read_sop('sla_sop.md'),
            },
        ],
    }


# Built at import time so the demo branches can return it directly.
DEMO_ANALYSIS = build_demo_analysis()
