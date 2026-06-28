<img width="1470" height="833" alt="Screenshot 2026-06-14 at 2 48 50 PM" src="https://github.com/user-attachments/assets/9e6ddb37-87d8-4446-8b6e-2d9ef4bcbd03" />
# SOPatch

AI-powered SOP update detection. Paste a release note, get flagged sections and suggested rewrites, push directly to Confluence.

[![CI](https://github.com/willtam65/SOPatch/actions/workflows/ci.yml/badge.svg)](https://github.com/willtam65/SOPatch/actions/workflows/ci.yml) ![version](https://img.shields.io/badge/version-0.2-blue) ![Python](https://img.shields.io/badge/python-3.12-green) ![evals](https://img.shields.io/badge/tagger%20eval-20%20cases-informational)

## What it does

When a product release or policy change drops, SOPatch:

1. Reads all your SOPs live from Confluence
2. Uses Claude AI to identify which SOPs are affected
3. Flags the specific outdated sections with explanations
4. Suggests rewrites for each flagged section, and drops any edit whose quoted
   "current wording" can't be found in the source SOP (a grounding guard against
   hallucinated edits)
5. Pushes approved updates back to Confluence with version tracking

## Stack

- Python / Flask
- Claude API (claude-opus-4-8)
- Confluence REST API
- Vanilla JS frontend

## Evaluation

The hard part of a tool like this isn't generating text. It's knowing whether
the *tagger* picked the right SOPs. That's a set-prediction problem, so it's
measured with precision/recall against a hand-labeled gold set (`evals/`).

```bash
python -m evals.run_eval --dry-run   # validate the dataset, no API key needed
python -m evals.run_eval --live      # real metrics (needs ANTHROPIC_API_KEY)
python -m evals.run_eval --replay    # re-score saved model outputs, no API calls
```

The eval earned its keep immediately. The original matcher used exact-string
label intersection, and the eval showed it was missing real cases: the model
extracted `weekly-cx-reporting` but the label was `weekly-reporting`, so they
never matched. **The misses were retrieval, not the model.** Replacing exact
matching with a token-aware matcher (`core/matching.py`) recovered them. Scored
by replaying the *same* model outputs on the original 14 cases, so the only
variable is the matcher:

| Matcher | Precision | Recall | F1 | Exact-match |
| --- | --- | --- | --- | --- |
| Exact string | 1.00 | 0.81 | 0.90 | 12/14 |
| Token-aware | 1.00 | 1.00 | 1.00 | 14/14 |

End to end on the full set (now 20 labelled cases, run live) it scores around
**precision 0.95, recall 0.95**, give or take a little run to run since tag
extraction is non-deterministic. The misses are SOPs the release note really
affected, but whose labels the model's extracted tags didn't happen to overlap.

The fix for that is matching on document content, not label strings. At a few
dozen SOPs a vector index is overkill, so instead there's an optional **content
gate** (`SOPATCH_CONTENT_GATE=1`, or `run_eval --gate`): a second pass that asks
the model which of the label-missed SOPs are actually affected, reading their
content. Measured, it's a deliberate tradeoff, not a free win:

| Matching | Precision | Recall | F1 |
| --- | --- | --- | --- |
| Label match (default) | ~0.95 | ~0.95 | ~0.95 |
| Label match + content gate | ~0.88 | ~1.00 | ~0.93 |

The gate catches every stale SOP (recall ~1.00) but over-flags a few tangential
ones, lowering precision and adding a call per analysis. That F1 cost isn't
worth it for most runs, so it's left off by default and turned on when recall
matters more than a reviewer dismissing the occasional false alarm. Scoring is
pure and unit-tested (`pytest`), so CI runs it without secrets.

## Setup

```bash
git clone https://github.com/willtam65/SOPatch.git
cd SOPatch
pip install -r requirements.txt
cp .env.example .env
# Fill in your credentials in .env
python3 app.py
```

Open `http://localhost:5001`

## Demo Mode

Want to try the full workflow without any credentials or setup? Run SOPatch in
Demo Mode. It uses bundled sample data, makes **zero external API calls**, and
needs no Anthropic or Confluence keys.

```bash
SOPATCH_DEMO=1 python3 app.py
```

Then open `http://localhost:5001`. (You can also leave the env var unset and just
visit `http://localhost:5001/?demo=1`.)

In Demo Mode you get the complete experience. You can analyze a fixed sample
release note, see the flagged SOP sections, view the before/after diff, and
reach the push step, all from local files in `data/`. The release note is pre-filled and
read-only, the Refine button is disabled (it needs live AI), and the live
Confluence push is replaced with a demo notice (nothing is sent to Confluence).

With valid credentials and Demo Mode off, the app runs the real live flow exactly
as normal.

## Deploy

The public demo runs in Demo Mode (no keys, no external calls), so it's safe to
expose. Served by gunicorn. Locally:

```bash
docker build -t sopatch .
docker run -p 5001:5001 -e SOPATCH_DEMO=1 sopatch   # http://localhost:5001
```

On Render: open **New**, choose **Blueprint**, and point it at this repo.
`render.yaml` deploys the demo on the free plan with a `/healthz` liveness check.

## Environment variables

```
ANTHROPIC_API_KEY=
CONFLUENCE_BASE_URL=https://yourcompany.atlassian.net
CONFLUENCE_EMAIL=
CONFLUENCE_API_TOKEN=
CONFLUENCE_SPACE_KEY=
CONFLUENCE_SOP_PARENT_ID=
```

## Built by

Will Tam, [LinkedIn](https://linkedin.com/in/willtam65)
