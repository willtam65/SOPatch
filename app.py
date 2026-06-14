"""
app.py -- SOPatch Web Application

Main entry point. Serves the web UI and handles:
- POST /analyze: loads SOPs from Confluence, runs AI matching + analysis
- POST /push: pushes approved SOP update back to the correct Confluence page
"""

import os
from flask import Flask, render_template, request, jsonify
from core.tagger import run_tagger
from core.analyzer import analyze_all_sops, refine_section
from core.confluence import push_to_confluence, get_credentials
from demo_data import (
    DEMO_ANALYSIS,
    DEMO_BANNER_TEXT,
    DEMO_PUSH_MESSAGE,
    DEMO_REFINE_MESSAGE,
)

app = Flask(__name__)

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


@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Accept a release note from the UI.
    Load SOPs from Confluence, run AI matching, run Claude analysis.
    Return results as JSON.
    """
    data = request.get_json()

    # Demo Mode: return the hardcoded result, no tagger / Claude / Confluence.
    if request_demo_enabled(data):
        return jsonify(DEMO_ANALYSIS)

    release_note_text = data.get('release_note', '').strip()

    if not release_note_text:
        return jsonify({'error': 'Release note is empty.'}), 400

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

        return jsonify({
            'affected_count': len(formatted),
            'unaffected_count': len(tagger_result['unaffected_sops']),
            'unaffected_sops': tagger_result['unaffected_sops'],
            'results': formatted
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/push', methods=['POST'])
def push():
    """
    Accept an approved SOP update from the UI.
    Push the change log to the correct Confluence page.
    """
    data = request.get_json()

    # Demo Mode: never touch Confluence; return a success-style demo notice.
    if request_demo_enabled(data):
        return jsonify({
            'success': True,
            'demo': True,
            'title': data.get('title', 'SOP'),
            'message': DEMO_PUSH_MESSAGE,
        })

    page_id = data.get('page_id', '').strip()
    analysis_text = data.get('analysis', '').strip()
    sop_title = data.get('title', 'SOP')

    if not page_id or not analysis_text:
        return jsonify({'error': 'Missing page ID or analysis.'}), 400

    try:
        creds = get_credentials()
        result = push_to_confluence(page_id, analysis_text, creds)
        return jsonify({
            'success': True,
            'title': result['title'],
            'new_version': result['new_version'],
            'url': result['url']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/refine', methods=['POST'])
def refine():
    """
    Accept a single section + user instruction.
    Return an improved suggested rewrite from Claude.
    """
    data = request.get_json()

    # Demo Mode: Refine needs a live Claude call, so it is disabled here.
    # The frontend hides the button in demo; this is a backend safety guard.
    if request_demo_enabled(data):
        return jsonify({'error': DEMO_REFINE_MESSAGE}), 400

    release_note_text = data.get('release_note', '').strip()
    sop_title = data.get('sop_title', '').strip()
    section_name = data.get('section_name', '').strip()
    current_wording = data.get('current_wording', '').strip()
    why_outdated = data.get('why_outdated', '').strip()
    suggested_rewrite = data.get('suggested_rewrite', '').strip()
    user_instruction = data.get('user_instruction', '').strip()

    if not user_instruction:
        return jsonify({'error': 'Please enter a refinement instruction.'}), 400

    try:
        new_rewrite = refine_section(
            release_note_text, sop_title, section_name,
            current_wording, why_outdated, suggested_rewrite, user_instruction
        )
        return jsonify({'rewrite': new_rewrite})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("SOPatch is running at http://localhost:5001")
    app.run(debug=True, port=5001)
