"""core/config.py -- single source of truth for SOPatch model configuration.

Keeping the model id in one place means a model upgrade is a one-line change
here, not a find-and-replace across every call site. (This file exists because
the id was previously hardcoded in five places and drifted out of date.)
"""

# The Claude model used for tag extraction, SOP analysis, and refinement.
MODEL = "claude-opus-4-8"
