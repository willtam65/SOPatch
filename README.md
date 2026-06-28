<img width="1470" height="833" alt="Screenshot 2026-06-14 at 2 48 50 PM" src="https://github.com/user-attachments/assets/9e6ddb37-87d8-4446-8b6e-2d9ef4bcbd03" />
# SOPatch

AI-powered SOP update detection. Paste a release note, get flagged sections and suggested rewrites, push directly to Confluence.

[![CI](https://github.com/willtam65/SOPatch/actions/workflows/ci.yml/badge.svg)](https://github.com/willtam65/SOPatch/actions/workflows/ci.yml) ![version](https://img.shields.io/badge/version-0.2-blue) ![Python](https://img.shields.io/badge/python-3.12-green) ![evals](https://img.shields.io/badge/tagger%20eval-P%201.00%20%C2%B7%20R%201.00-success)

## What it does

When a product release or policy change drops, SOPatch:

1. Reads all your SOPs live from Confluence
2. Uses Claude AI to identify which SOPs are affected
3. Flags the specific outdated sections with explanations
4. Suggests rewrites for each flagged section
5. Pushes approved updates back to Confluence with version tracking

## Stack

- Python / Flask
- Claude API (claude-opus-4-8)
- Confluence REST API
- Vanilla JS frontend

## Evaluation

The hard part of a tool like this isn't generating text — it's knowing whether
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
matching with a token-aware matcher (`core/matching.py`) closed the gap — scored
by replaying the *same* model outputs, so the only variable is the matcher:

| Matcher | Precision | Recall | F1 | Exact-match |
| --- | --- | --- | --- | --- |
| Exact string | 1.00 | 0.81 | 0.90 | 12/14 |
| Token-aware | 1.00 | 1.00 | 1.00 | 14/14 |

100% on 14 cases means the set no longer discriminates, not that retrieval is
"solved." The next step is a larger set with true-synonym cases that token
matching can't bridge — that's where embeddings + reranking would earn their
cost. Scoring is pure and unit-tested (`pytest`), so CI runs it without secrets.

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

In Demo Mode you get the complete experience — analyze a fixed sample release
note, see the flagged SOP sections, view the before/after diff, and reach the
push step — all from local files in `data/`. The release note is pre-filled and
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

On Render: **New → Blueprint**, point it at this repo. `render.yaml` deploys the
demo on the free plan with a `/healthz` liveness check.

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

Will Tam — [LinkedIn](https://linkedin.com/in/willtam65)
