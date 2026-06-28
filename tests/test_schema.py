"""Tests for the structured-output schema, serialization, and typed grounding.

No API key needed: these cover the validation and (de)serialization that
replaced the old regex parsing of free-text model output.
"""

from core.confluence import parse_analysis_blocks
from core.grounding import ground_sections
from core.schema import (
    ANALYSIS_TOOL,
    AnalysisResult,
    FlaggedSection,
    sections_to_text,
)


def test_analysis_result_validates():
    r = AnalysisResult(sections=[{
        "section": "Step 1",
        "current_wording": "x",
        "why_outdated": "y",
        "suggested_rewrite": "z",
    }])
    assert len(r.sections) == 1
    assert r.sections[0].section == "Step 1"


def test_analysis_result_defaults_to_empty():
    assert AnalysisResult().sections == []


def test_empty_sections_serialize_to_empty_string():
    assert sections_to_text([]) == ""


def test_sections_to_text_roundtrips_through_the_parser():
    # The serialized form must be readable by the same block parser the push
    # step and frontend use -- this is what keeps the wire format stable.
    secs = [
        FlaggedSection(
            section="Step 1",
            current_wording="The clock starts at creation.",
            why_outdated="changed",
            suggested_rewrite="The clock starts at escalation.",
        )
    ]
    blocks = parse_analysis_blocks(sections_to_text(secs))
    assert len(blocks) == 1
    assert blocks[0]["section"] == "Step 1"
    assert blocks[0]["current"] == "The clock starts at creation."
    assert blocks[0]["rewrite"] == "The clock starts at escalation."


def test_tool_schema_matches_the_model():
    assert ANALYSIS_TOOL["name"] == "report_flagged_sections"
    item_props = ANALYSIS_TOOL["input_schema"]["properties"]["sections"]["items"]["properties"]
    assert set(item_props) == {"section", "current_wording", "why_outdated", "suggested_rewrite"}


def test_ground_sections_drops_ungrounded():
    sop = "Step 1: The clock starts at creation."
    secs = [
        FlaggedSection(section="Step 1", current_wording="The clock starts at creation.",
                       why_outdated="x", suggested_rewrite="y"),
        FlaggedSection(section="Phantom", current_wording="Refunds need VP approval.",
                       why_outdated="x", suggested_rewrite="y"),
    ]
    kept, dropped = ground_sections(secs, sop)
    assert [s.section for s in kept] == ["Step 1"]
    assert [s.section for s in dropped] == ["Phantom"]
