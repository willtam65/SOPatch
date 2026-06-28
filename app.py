"""
app.py -- SOPatch Web Application

Main entry point. Serves the web UI and handles:
- POST /analyze: loads SOPs from Confluence, runs AI matching + analysis
- POST /push: pushes approved SOP update back to the correct Confluence page
"""

import os
import anthropic
import requests
from flask import Flask, render_template, request, jsonify
from pydantic import BaseModel, Field, ValidationError
from core.tagger import run_tagger
from core.analyzer import analyze_all_sops, refine_section
from core.confluence import push_to_confluence, get_credentials
from core.logging import get_logger
from demo_data import (
    DEMO_ANALYSIS,
    DEMO_BANNER_TEXT,
    DEMO_PUSH_MESSAGE,
    DEMO_REFINE_MESSAGE,
)

app = Flask(__name__)
log = get_logger("sopatch.app")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RELEASE_NOTE_PATH = os.path.join(BASE_DIR, 'data', 'release_note.txt')


def env_demo_enabled():
    """Demo Mode forced on for the whole process via SOPATCH_DEMO=1."""
    return os.environ.get('SOPATCH_DEMO') == '1'


def request_demo_enabled(data):
    """
    Demo Mode for a single API call. Enabled if the process-wide env flag is
    set, or the frontend (rendered in demo mode) sent {"demo": true}.
    Demo Mode is only ever entered explicitly -- a failed live Confluence call
    never falls back to demo.
    """
    return env_demo_enabled() or bool(data.get('demo'))


# ── Request validation ───────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    release_note: str = Field(min_length=1, max_length=50000)


class RefineRequest(BaseModel):
    user_instruction: str = Field(min_length=1, max_length=2000)
    release_note: str = Field(default='', max_length=50000)
    sop_title: str = Field(default='', max_length=500)
    section_name: str = Field(default='', max_length=500)
    current_wording: str = Field(default='', max_length=10000)
    why_outdated: str = Field(default='', max_length=10000)
    suggested_rewrite: str = Field(default='', max_length=10000)


class PushRequest(BaseModel):
    page_id: str = Field(min_length=1, max_length=100)
    analysis: str = Field(min_length=1, max_length=100000)
    title: str = Field(default='SOP', max_length=500)


def _error(message, status):
    return jsonify({'error': message}), status


def _validation_error(exc):
    """Turn a Pydantic ValidationError into a safe 400 (no internals leaked)."""
    first = exc.errors()[0]
    field = '.'.join(str(p) for p in first.get('loc', ()))
    return _error(f"Invalid request: {field} ({first.get('msg', 'invalid')}).", 400)


@app.route('/')
def index():
    """Serve the main SOPatch UI."""
    release_note_text = ''
    try:
        with open(RELEASE_NOTE_PATH, 'r', encoding='utf-8') as f:
            release_note_text = f.read()
    except FileNotFoundError:
        pass
    demo_mode = env_demo_enabled() or request.args.get('demo') == '1'
    return render_template(
        'index.html',
        release_note=release_note_text,
        demo_mode=demo_mode,
        demo_banner_text=DEMO_BANNER_TEXT,
        demo_refine_message=DEMO_REFINE_MESSAGE,
    )


@app.route('/healthz')
def healthz():
    """Liveness probe for the deployment platform (Render/Railway/Docker)."""
    return jsonify({'status': 'ok', 'demo': env_demo_enabled()})


@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Accept a release note from the UI.
    Load SOPs from Confluence, run AI matching, run Claude analysis.
    Return results as JSON.
    """
    data = request.get_json(silent=True) or {}

    # Demo Mode: return the hardcoded result, no tagger / Claude / Confluence.
    if request_demo_enabled(data):
        return jsonify(DEMO_ANALYSIS)

    try:
        req = AnalyzeRequest(**data)
    except ValidationError as e:
        return _validation_error(e)

    release_note_text = req.release_note.strip()
    if not release_note_text:
        return _error('Release note is empty.', 400)

    try:
        # Step 1: Load SOPs from Confluence + AI matching
        tagger_result = run_tagger(release_note_text)

        if not tagger_result['affected_sops']:
            return jsonify({
                'affected_count': 0,
                'unaffected_count': len(tagger_result['unaffected_sops']),
                'unaffected_sops': tagger_result['unaffected_sops'],
                'results': [],
                'message': 'No SOPs were affected by this release note.'
            })

        # Step 2: Claude analysis on each affected SOP
        results = analyze_all_sops(release_note_text, tagger_result['affected_sops'])

        formatted = []
        for r in results:
            source_sop = next(
                sop for sop in tagger_result['affected_sops']
                if sop['filename'] == r['filename']
            )
            formatted.append({
                'page_id': source_sop['page_id'],
                'filename': r['filename'],
                'title': r['title'],
                'matching_tags': list(r['matching_tags']),
                'analysis': r['analysis'],
                'sop_content': source_sop['content']
            })

        log.info("analyze.done", affected=len(formatted),
                 unaffected=len(tagger_result['unaffected_sops']))
        return jsonify({
            'affected_count': len(formatted),
            'unaffected_count': len(tagger_result['unaffected_sops']),
            'unaffected_sops': tagger_result['unaffected_sops'],
            'results': formatted
        })

    except anthropic.APIError as e:
        log.error("analyze.llm_error", error=str(e))
        return _error('The AI service is temporarily unavailable. Please try again.', 503)
    except requests.RequestException as e:
        log.error("analyze.confluence_error", error=str(e))
        return _error('Could not reach Confluence. Please try again shortly.', 502)
    except Exception as e:
        log.error("analyze.unexpected", error=str(e))
        return _error('Something went wrong while analyzing. Please try again.', 500)


@app.route('/push', methods=['POST'])
def push():
    """
    Accept an approved SOP update from the UI.
    Push the change log to the correct Confluence page.
    """
    data = request.get_json(silent=True) or {}

    # Demo Mode: never touch Confluence; return a success-style demo notice.
    if request_demo_enabled(data):
        return jsonify({
            'success': True,
            'demo': True,
            'title': data.get('title', 'SOP'),
            'message': DEMO_PUSH_MESSAGE,
        })

    try:
        req = PushRequest(**data)
    except ValidationError as e:
        return _validation_error(e)

    try:
        creds = get_credentials()
        result = push_to_confluence(req.page_id.strip(), req.analysis.strip(), creds)
        log.info("push.done", page_id=req.page_id.strip(), version=result.get('new_version'))
        return jsonify({
            'success': True,
            'title': result['title'],
            'new_version': result['new_version'],
            'url': result['url']
        })
    except requests.RequestException as e:
        log.error("push.confluence_error", error=str(e))
        return _error('Could not reach Confluence. Please try again shortly.', 502)
    except Exception as e:
        log.error("push.unexpected", error=str(e))
        return _error('Something went wrong while pushing to Confluence. Please try again.', 500)


@app.route('/refine', methods=['POST'])
def refine():
    """
    Accept a single section + user instruction.
    Return an improved suggested rewrite from Claude.
    """
    data = request.get_json(silent=True) or {}

    # Demo Mode: Refine needs a live Claude call, so it is disabled here.
    # The frontend hides the button in demo; this is a backend safety guard.
    if request_demo_enabled(data):
        return _error(DEMO_REFINE_MESSAGE, 400)

    try:
        req = RefineRequest(**data)
    except ValidationError as e:
        return _validation_error(e)

    try:
        new_rewrite = refine_section(
            req.release_note.strip(), req.sop_title.strip(), req.section_name.strip(),
            req.current_wording.strip(), req.why_outdated.strip(),
            req.suggested_rewrite.strip(), req.user_instruction.strip()
        )
        return jsonify({'rewrite': new_rewrite})
    except anthropic.APIError as e:
        log.error("refine.llm_error", error=str(e))
        return _error('The AI service is temporarily unavailable. Please try again.', 503)
    except Exception as e:
        log.error("refine.unexpected", error=str(e))
        return _error('Something went wrong while refining. Please try again.', 500)


if __name__ == '__main__':
    # Local dev server. In production the app is served by gunicorn (see
    # Dockerfile), which imports `app` directly and ignores this block.
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    print(f"SOPatch is running at http://localhost:{port}")
    app.run(debug=debug, host='0.0.0.0', port=port)
