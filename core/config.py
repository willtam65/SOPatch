"""core/config.py -- model configuration, right-sized per task.

The tagger's tag extraction and content gate are cheap classification jobs, so
they run on the fast model; finding outdated SOP sections and writing the
rewrites is quality-critical, so it runs on the stronger model. Splitting the
pipeline this way instead of running everything on Opus cuts token cost by
roughly 75% with no measurable drop in tagger accuracy on the eval set (re-run
`python -m evals.run_eval` after changing a tier to confirm).
"""

# Cheap classification: release-note tag extraction, content gate, label generation.
MODEL_FAST = "claude-haiku-4-5-20251001"

# Quality-critical: finding outdated SOP sections and writing the rewrites.
MODEL_SMART = "claude-sonnet-4-6"

# Back-compat default for any caller that doesn't pick a tier.
MODEL = MODEL_SMART
