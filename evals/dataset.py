"""Gold dataset + SOP label fixtures for the SOPatch tagger eval.

The eval measures the core tagger decision: given a release note, which SOPs
SHOULD be flagged as affected? Each case lists that gold set.

The SOP label fixtures below mirror what setup_tags.py writes to Confluence in
the live system. Keeping them in-repo lets the eval run with no Confluence
connection, and pins the labels so the only moving part is the model's tag
extraction -- which is exactly what we want to measure.

Some cases are marked hard=True: they describe a process using wording that
diverges from the SOP's labels (a renamed process, a synonym). Exact-label
intersection is brittle there, so recall on those cases is honestly below 100%.
That gap is the point -- surfacing it is what an eval is for, and "fix the
retrieval, not the model" is the lesson it teaches.
"""

from __future__ import annotations

# Four SOPs and their labels (as setup_tags.py would generate them in Confluence).
SOP_FIXTURES = {
    "qa": {
        "title": "QA Monitoring SOP",
        "labels": [
            "agent-qa-scoring",
            "qa-scorecard",
            "chat-escalation",
            "response-quality-review",
        ],
    },
    "reporting": {
        "title": "Weekly CX Reporting SOP",
        "labels": [
            "weekly-reporting",
            "metrics-rebaseline",
            "cx-metrics-report",
            "trend-analysis",
        ],
    },
    "sla": {
        "title": "SLA Tracking SOP",
        "labels": [
            "sla-clock",
            "sla-breach-review",
            "response-time-sla",
            "chat-escalation",
        ],
    },
    "triage": {
        "title": "Inbound Ticket Triage SOP",
        "labels": [
            "ticket-triage",
            "inbound-routing",
            "priority-assignment",
            "queue-management",
        ],
    },
}


# Each case: a release note and the set of SOP ids that should be flagged.
# `hard` marks cases where the wording diverges from the labels on purpose.
CASES = [
    {
        "id": "chatbot_launch",
        "summary": "AI chatbot launch (the canonical SOPatch demo note)",
        "note": (
            "AI Chat Assistant Launch. Effective immediately an AI chatbot is "
            "live and handles tier-1 support queries autonomously. Unresolved "
            "chat queries are escalated to Zendesk as tickets tagged "
            "[chat-escalation] with full conversation history attached. Inbound "
            "ticket volume is expected to drop 35%. The SLA clock for "
            "chat-escalated tickets starts when the chatbot fails to resolve the "
            "query, not when the agent picks it up. Agents must review chatbot "
            "responses as part of QA: a new QA checklist item is added, 'Was the "
            "chatbot response accurate before escalation?'. Weekly reporting "
            "metrics must be rebaselined to note the launch date as a baseline shift."
        ),
        "gold": {"qa", "reporting", "sla"},
        "hard": False,
    },
    {
        "id": "sla_clock_change",
        "summary": "SLA clock start rule changes",
        "note": (
            "Policy change: the SLA clock now starts at the first agent response "
            "rather than at ticket creation. SLA breach reviews must use the new "
            "start time when calculating response-time compliance."
        ),
        "gold": {"sla"},
        "hard": False,
    },
    {
        "id": "triage_routing",
        "summary": "Inbound routing / priority matrix update",
        "note": (
            "We are rolling out a new inbound ticket routing matrix. Priority "
            "assignment on intake changes: P1 tickets are now auto-routed to "
            "senior agents and the queue management rules are rebuilt."
        ),
        "gold": {"triage"},
        "hard": False,
    },
    {
        "id": "qa_scorecard_update",
        "summary": "New QA scorecard item",
        "note": (
            "The agent QA scorecard gains a new scored item this quarter: "
            "'empathy and acknowledgement'. All QA reviewers must score it on "
            "the 1-5 scale during response quality review."
        ),
        "gold": {"qa"},
        "hard": False,
    },
    {
        "id": "reporting_cadence",
        "summary": "Weekly report adds a metric / trend rule",
        "note": (
            "The weekly CX report adds an NPS column and the trend-analysis "
            "threshold for flagging a moved metric drops from 10% to 7% "
            "week-over-week. Report assembly steps are updated accordingly."
        ),
        "gold": {"reporting"},
        "hard": False,
    },
    {
        "id": "unrelated_office_move",
        "summary": "Office relocation (should flag nothing)",
        "note": (
            "Facilities notice: the company is relocating to a new office on "
            "the 14th floor next month. Badge access will be reissued and "
            "desk assignments will be sent out by People Ops."
        ),
        "gold": set(),
        "hard": False,
    },
    {
        "id": "unrelated_hr_policy",
        "summary": "HR parental-leave policy (should flag nothing)",
        "note": (
            "HR update: the parental leave policy is extended to 20 weeks fully "
            "paid, effective next quarter. Eligibility and request steps are "
            "described in the People Ops handbook."
        ),
        "gold": set(),
        "hard": False,
    },
    {
        "id": "billing_migration",
        "summary": "Billing provider migration (should flag nothing)",
        "note": (
            "Finance is migrating to a new billing provider. Invoice numbering "
            "changes and the finance team will reconcile balances during the "
            "cutover weekend. No customer-facing support process changes."
        ),
        "gold": set(),
        "hard": False,
    },
    {
        "id": "p0_severity_tier",
        "summary": "New P0 tier affecting both SLA and triage",
        "note": (
            "We are introducing a new P0 severity tier with a 1-hour SLA. "
            "Triage must tag P0 on intake and the SLA breach review process "
            "must track the new 1-hour response-time target separately."
        ),
        "gold": {"sla", "triage"},
        "hard": False,
    },
    {
        "id": "qa_into_reporting",
        "summary": "QA scores feed the weekly report",
        "note": (
            "Starting this month, weekly agent QA scoring results are rolled "
            "into the weekly CX report as a new quality column, so both the QA "
            "scorecard process and the weekly report assembly steps change."
        ),
        "gold": {"qa", "reporting"},
        "hard": False,
    },
    {
        "id": "sla_into_reporting",
        "summary": "SLA breach stats added to weekly report",
        "note": (
            "SLA breach counts must now appear in the weekly CX report. The SLA "
            "breach review feeds a new section in the weekly reporting template."
        ),
        "gold": {"sla", "reporting"},
        "hard": False,
    },
    {
        "id": "triage_tool_migration",
        "summary": "Inbound queue moves to a new tool",
        "note": (
            "The inbound support queue is migrating to a new helpdesk tool. "
            "Inbound routing rules and queue management workflows are rebuilt "
            "from scratch on the new platform."
        ),
        "gold": {"triage"},
        "hard": False,
    },
    # --- Deliberately hard: wording diverges from the labels ---
    {
        "id": "renamed_qa_audit",
        "summary": "QA described as 'conversation audit' (synonym -> likely missed)",
        "note": (
            "New initiative: every resolved customer conversation now receives a "
            "post-resolution accuracy audit by a senior reviewer, who records "
            "whether the agent's answers were correct and complete."
        ),
        "gold": {"qa"},
        "hard": True,
    },
    {
        "id": "rebaseline_euphemism",
        "summary": "Reporting rebaseline described obliquely (likely missed)",
        "note": (
            "Heads up for anyone comparing numbers week to week: because of a "
            "major channel shift this month, prior-period benchmarks are no "
            "longer apples-to-apples and dashboards should annotate the shift."
        ),
        "gold": {"reporting"},
        "hard": True,
    },
]


def all_sop_ids():
    """The universe of SOP ids the tagger chooses from."""
    return set(SOP_FIXTURES)


def predict_affected(note_tags):
    """Mirror the live tagger: intersect extracted note tags with SOP labels.

    A SOP is flagged iff at least one extracted tag exactly matches one of its
    labels -- the same set intersection core.tagger.match_with_labels performs.
    """
    note_tags = set(note_tags)
    return {
        sop_id
        for sop_id, fixture in SOP_FIXTURES.items()
        if note_tags & set(fixture["labels"])
    }


def validate():
    """Sanity-check the dataset; raises AssertionError on a malformed case."""
    universe = all_sop_ids()
    seen_ids = set()
    for case in CASES:
        assert case["id"] not in seen_ids, f"duplicate case id: {case['id']}"
        seen_ids.add(case["id"])
        assert case["note"].strip(), f"empty note in case: {case['id']}"
        assert set(case["gold"]) <= universe, (
            f"case {case['id']} references unknown SOP ids: "
            f"{set(case['gold']) - universe}"
        )
    return True
