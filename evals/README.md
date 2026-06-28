# SOPatch eval harness

A small evaluation harness for the part of SOPatch that's easy to get wrong and
impossible to eyeball: **the tagger**. Given a release note, which SOPs does it
flag as affected?

That's a set-prediction problem, so it's scored with **precision, recall, and
F1** against a hand-labelled gold set (20 cases over 4 SOPs).

## What it measures

For each release note, the harness runs the real model-driven step from
`core/tagger.py` (`extract_tags_from_release_note`), matches the extracted tags
against each SOP's labels (token-aware, see `core/matching.py`), and compares the
predicted affected set to the gold set.

- **Precision**: of the SOPs we flagged, how many should have been flagged? (low
  precision means noisy false alarms a human has to dismiss)
- **Recall**: of the SOPs that should have been flagged, how many did we catch?
  (low recall means a stale doc slips through, the worse failure here)

## Run it

```bash
# validate the dataset, no API calls, no key needed:
python -m evals.run_eval --dry-run

# real metrics (needs ANTHROPIC_API_KEY):
python -m evals.run_eval --live
python -m evals.run_eval --live --limit 3    # quick smoke run

# re-score the saved model outputs with the current matcher (no API calls):
python -m evals.run_eval --replay

# add the optional content gate on top of label matching (the hybrid):
python -m evals.run_eval --live --gate
```

A live run prints a results table and writes full per-case traces (extracted
tags, predicted set, gold set, TP/FP/FN) to `evals/results/latest.json`. The
`--gate` run writes to `evals/results/latest-gated.json` instead.

## What the harness found

The original matcher used exact-string label intersection and quietly missed
cases (the model extracted `weekly-cx-reporting`, the label was
`weekly-reporting`). `--replay` re-scores the same saved model outputs so a
matcher change can be measured in isolation: the token-aware matcher took recall
from 0.81 to 1.00 on those outputs.

End to end on the full set it runs around precision 0.95, recall 0.95. The
optional content gate (`--gate`) lifts recall to ~1.00 by checking label-missed
SOPs against their content, but over-flags a few tangential ones, so it trades
precision (~0.88) and a call per analysis. That tradeoff is why it's off by
default. See the main README for the full table.

## Tests

The scoring math (`scoring.py`) and the matching rule (`predict_affected`) are
pure and unit-tested, so they run in CI with no API key:

```bash
pip install -r requirements-dev.txt
pytest
```

## Files

| File | Purpose |
| --- | --- |
| `dataset.py` | SOP label and content fixtures plus the hand-labelled gold cases |
| `scoring.py` | Pure precision/recall/F1 set metrics (unit-tested) |
| `run_eval.py` | Runner: extract tags, match, optional content gate, score, traces |
| `results/latest.json` | Per-case traces from the most recent default live run |
| `results/latest-gated.json` | Traces from the most recent `--gate` run |
