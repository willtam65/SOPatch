# SOPatch eval harness

A small evaluation harness for the part of SOPatch that's easy to get wrong and
impossible to eyeball: **the tagger** — given a release note, which SOPs does it
flag as affected?

That's a set-prediction problem, so it's scored with **precision, recall, and
F1** against a hand-labeled gold set.

## What it measures

For each release note in the dataset, the harness runs the real, model-driven
step from `core/tagger.py` (`extract_tags_from_release_note`), intersects the
extracted tags with each SOP's labels, and compares the predicted affected set
to the gold set.

- **Precision** — of the SOPs we flagged, how many should have been flagged?
  (low precision = noisy false alarms a human has to dismiss)
- **Recall** — of the SOPs that should have been flagged, how many did we catch?
  (low recall = a stale doc slips through — the worse failure here)

The matching is exact-label intersection, which is fast and cheap but brittle:
if a release note describes a process with different words than the SOP's
labels, the match misses. The dataset includes a few `hard` cases that do
exactly this, so **recall is honestly below 100%** — surfacing that gap is the
whole point, and it's the motivation for moving to embedding-based retrieval.

## Run it

```bash
# validate the dataset, no API calls, no key needed:
python -m evals.run_eval --dry-run

# real metrics (needs ANTHROPIC_API_KEY):
python -m evals.run_eval --live
python -m evals.run_eval --live --limit 3   # quick smoke run
```

A live run prints a results table and writes full per-case traces (extracted
tags, predicted set, gold set, TP/FP/FN) to `evals/results/latest.json`.

## Tests

The scoring math (`evals/scoring.py`) and the matching rule (`predict_affected`)
are pure and unit-tested — no API key required, so they run in CI:

```bash
pip install -r requirements-dev.txt
pytest
```

## Files

| File | Purpose |
| --- | --- |
| `dataset.py` | SOP label fixtures + hand-labeled gold cases |
| `scoring.py` | Pure precision/recall/F1 set metrics (unit-tested) |
| `run_eval.py` | Live runner: extract tags → match → score → table + traces |
| `results/latest.json` | Per-case traces from the most recent live run |
