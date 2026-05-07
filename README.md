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
