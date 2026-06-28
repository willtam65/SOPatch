"""core/schema.py -- typed structured output for the analyzer.

Instead of asking the model for a free-text block format and parsing it back
with a regex, the analyzer makes the model fill a typed tool call. The result is
validated by Pydantic before anything downstream touches it, which removes a
whole class of "the model formatted it slightly differently" parsing bugs.

The serialized block format is kept (sections_to_text) so the frontend and the
Confluence push step, which already speak it, don't need to change.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FlaggedSection(BaseModel):
    section: str = Field(description="Section name or step number in the SOP.")
    current_wording: str = Field(description="The exact current text being changed, quoted verbatim from the SOP.")
    why_outdated: str = Field(description="One or two sentences on why this section is now outdated.")
    suggested_rewrite: str = Field(description="The new wording to replace the current text.")


class AnalysisResult(BaseModel):
    sections: list[FlaggedSection] = Field(default_factory=list)


# The tool the model is forced to call, so its output is structured, not free
# text. Mirrors FlaggedSection; kept explicit so the schema sent to the API is
# obvious at the call site.
ANALYSIS_TOOL = {
    "name": "report_flagged_sections",
    "description": "Report every SOP section made outdated by the release note.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sections": {
                "type": "array",
                "description": "One entry per outdated section. Empty if nothing is affected.",
                "items": {
                    "type": "object",
                    "properties": {
                        "section": {"type": "string", "description": "Section name or step number."},
                        "current_wording": {"type": "string", "description": "Exact current text, quoted verbatim from the SOP."},
                        "why_outdated": {"type": "string", "description": "Why this section is now outdated."},
                        "suggested_rewrite": {"type": "string", "description": "The new wording to replace it."},
                    },
                    "required": ["section", "current_wording", "why_outdated", "suggested_rewrite"],
                },
            }
        },
        "required": ["sections"],
    },
}


def sections_to_text(sections):
    """Serialize flagged sections into the SECTION/.../--- block format that the
    frontend and the Confluence push step already understand."""
    if not sections:
        return ""
    inner = "\n---\n".join(
        f"SECTION: {s.section}\n"
        f"CURRENT WORDING: {s.current_wording}\n"
        f"WHY OUTDATED: {s.why_outdated}\n"
        f"SUGGESTED REWRITE: {s.suggested_rewrite}"
        for s in sections
    )
    return f"---\n{inner}\n---"
