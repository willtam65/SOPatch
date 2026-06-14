<img width="1470" height="833" alt="Screenshot 2026-06-14 at 2 48 50 PM" src="https://github.com/user-attachments/assets/9e6ddb37-87d8-4446-8b6e-2d9ef4bcbd03" />
# SOPatch

AI-powered SOP update detection. Paste a release note, get flagged sections and suggested rewrites, push directly to Confluence.

![SOPatch](https://img.shields.io/badge/version-0.1-blue) ![Python](https://img.shields.io/badge/python-3.9+-green) ![Flask](https://img.shields.io/badge/flask-2.x-lightgrey)

## What it does

When a product release or policy change drops, SOPatch:

1. Reads all your SOPs live from Confluence
2. Uses Claude AI to identify which SOPs are affected
3. Flags the specific outdated sections with explanations
4. Suggests rewrites for each flagged section
5. Pushes approved updates back to Confluence with version tracking

## Stack

- Python / Flask
- Claude API (claude-opus-4-6)
- Confluence REST API
- Vanilla JS frontend

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
