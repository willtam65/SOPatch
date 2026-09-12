"""
app.py -- SOPatch Web Application

Main entry point. Serves the web UI and handles:
- POST /analyze: loads SOPs from Confluence, runs AI matching + analysis
- POST /push: pushes approved SOP update back to the correct Confluence page
- POST /webhook/jira: automated trigger; runs the pipeline on a Jira change and
  notifies a reviewer, instead of waiting for a human to paste a release note
"""

import os
import anthropic
import requests
from flask import Flask, render_template, request, jsonify, url_for
from pydantic import BaseModel, Field, ValidationError
from core.tagger import run_tagger
from core.analyzer import analyze_all_sops, refine_section
from core.confluence import push_to_confluence, get_credentials
from core.jira import should_trigger, extract_change_note, source_label
from core.notify import format_review_notification, send_notification
from core.sections import parse_sections
from core.store import ReviewStore
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

# Persisted review queue + audit trail. Path is SOPATCH_DB (see core/store.py);
# tests point it at a temp file, and the demo writes to data/sopatch.db.
store = ReviewStore()


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


class DecisionRequest(BaseModel):
    decision: str = Field(pattern='^(approved|rejected)$')
    approver: str = Field(default='reviewer', max_length=200)


def _error(message, status):
    return jsonify({'error': message}), status


def _validation_error(exc):
    """Turn a Pydantic ValidationError into a safe 400 (no internals leaked)."""
    first = exc.errors()[0]
    field = '.'.join(str(p) for p in first.get('loc', ()))
    return _error(f"Invalid request: {field} ({first.get('msg', 'invalid')}).", 400)


def _analyze_release_note(release_note_text):
    """Run the tagger + analyzer for a release note and return the result payload.
    Shared by POST /analyze and the Jira webhook. Raises on model/Confluence errors."""
    tagger_result = run_tagger(release_note_text)
    if not tagger_result['affected_sops']:
        return {
            'affected_count': 0,
            'unaffected_count': len(tagger_result['unaffected_sops']),
            'unaffected_sops': tagger_result['unaffected_sops'],
            'results': [],
            'message': 'No SOPs were affected by this release note.'
        }
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
    return {
        'affected_count': len(formatted),
        'unaffected_count': len(tagger_result['unaffected_sops']),
        'unaffected_sops': tagger_result['unaffected_sops'],
        'results': formatted
    }


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
        result = _analyze_release_note(release_note_text)
        log.info("analyze.done", affected=result['affected_count'],
                 unaffected=result['unaffected_count'])
        return jsonify(result)

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


@app.route('/webhook/jira', methods=['POST'])
def jira_webhook():
    """
    Automated trigger. Jira posts here when a version ships or an issue is
    labelled a policy or process change. SOPatch runs itself and notifies a
    reviewer, instead of waiting for a human to paste a release note.
    """
    secret = os.environ.get('JIRA_WEBHOOK_SECRET')
    if secret and request.headers.get('X-Webhook-Secret') != secret:
        return _error('Unauthorized.', 401)

    event = request.get_json(silent=True) or {}
    if not should_trigger(event):
        return jsonify({'triggered': False, 'reason': 'event did not match a trigger'})

    change_note = extract_change_note(event).strip()
    if not change_note:
        return jsonify({'triggered': False, 'reason': 'no change text in the event'})

    source = source_label(event)
    try:
        result = DEMO_ANALYSIS if env_demo_enabled() else _analyze_release_note(change_note)
    except anthropic.APIError as e:
        log.error("jira_webhook.llm_error", error=str(e))
        return _error('The AI service is temporarily unavailable.', 503)
    except requests.RequestException as e:
        log.error("jira_webhook.confluence_error", error=str(e))
        return _error('Could not reach Confluence.', 502)
    except Exception as e:
        log.error("jira_webhook.unexpected", error=str(e))
        return _error('Something went wrong handling the event.', 500)

    # Record the run so a reviewer can open it, decide, and leave an audit trail.
    run_id = store.create_run(source, change_note, result)
    review_url = url_for('review_page', run_id=run_id, _external=True)

    message = format_review_notification(source, result, review_url=review_url)
    delivery = send_notification(message)
    store.record_event(run_id, 'notified', actor='system', detail=delivery['channel'])
    log.info("jira_webhook.triggered", run_id=run_id, source=source,
             affected=result.get('affected_count'), channel=delivery['channel'])
    return jsonify({
        'triggered': True,
        'run_id': run_id,
        'review_url': review_url,
        'source': source,
        'change_note_preview': change_note[:280],
        'affected_count': result.get('affected_count', 0),
        # Full analysis payload so a programmatic caller (or the demo UI) can
        # render the flagged SOPs from the same call, without a second request.
        # Jira itself ignores the response body.
        'result': result,
        'notification': {
            'delivered': delivery['sent'],
            'channel': delivery['channel'],
            'message': message,
        },
    })


@app.route('/reviews')
def reviews_list():
    """The review queue: every automated run, newest first, with its status."""
    return render_template('reviews.html', runs=store.list_runs(),
                           demo_mode=env_demo_enabled())


@app.route('/review/<int:run_id>')
def review_page(run_id):
    """One run's flagged SOPs, before/after edits, decision controls, audit trail."""
    run = store.get_run(run_id)
    if run is None:
        return render_template('reviews.html', runs=store.list_runs(),
                               demo_mode=env_demo_enabled(), not_found_id=run_id), 404
    # Attach parsed sections per flagged SOP for server-side rendering.
    flagged = []
    for r in run['result'].get('results', []):
        flagged.append({**r, 'sections': parse_sections(r.get('analysis', ''))})
    return render_template('review.html', run=run, flagged=flagged,
                           demo_mode=env_demo_enabled())


def _push_approved_run(run_id, run):
    """Push an approved run's edits to Confluence, one page per flagged SOP.

    Approval is the moment the human takes responsibility for the edit, so it is
    also the moment the edit ships. Every page is audited individually: a partial
    failure leaves a record of exactly which SOPs landed and which did not,
    rather than failing the whole approval. Demo Mode never touches Confluence.
    """
    results = run.get('result', {}).get('results', [])
    if env_demo_enabled():
        store.record_event(run_id, 'push_skipped', actor='system',
                           detail='demo mode, nothing sent to Confluence')
        return {'demo': True, 'attempted': 0, 'pushed': 0, 'failed': 0}

    creds = get_credentials()
    pushed, failed = 0, 0
    for r in results:
        page_id = (r.get('page_id') or '').strip()
        analysis = (r.get('analysis') or '').strip()
        title = r.get('title', 'SOP')
        if not page_id or not analysis:
            continue
        try:
            out = push_to_confluence(page_id, analysis, creds)
            pushed += 1
            store.record_event(
                run_id, 'pushed', actor='system',
                detail=f"{title} -> v{out.get('new_version')} {out.get('url', '')}".strip())
        except Exception as e:
            failed += 1
            log.error("review.push_error", run_id=run_id, page_id=page_id, error=str(e))
            store.record_event(run_id, 'push_failed', actor='system', detail=f"{title}: {e}")
    return {'demo': False, 'attempted': pushed + failed, 'pushed': pushed, 'failed': failed}


@app.route('/review/<int:run_id>/decision', methods=['POST'])
def review_decision(run_id):
    """Record an approve/reject decision, and on approval push the edits."""
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    try:
        req = DecisionRequest(**data)
    except ValidationError as e:
        return _validation_error(e)

    updated = store.set_decision(run_id, req.decision, actor=req.approver.strip() or 'reviewer')
    if updated is None:
        return _error('Review not found.', 404)

    push = _push_approved_run(run_id, updated) if req.decision == 'approved' else None
    log.info("review.decision", run_id=run_id, decision=req.decision,
             approver=req.approver, pushed=(push or {}).get('pushed'))
    return jsonify({
        'run_id': run_id,
        'status': updated['status'],
        'decided_at': updated['decided_at'],
        'approver': updated['approver'],
        'push': push,
        'audit': store.get_run(run_id)['audit'],
    })


if __name__ == '__main__':
    # Local dev server. In production the app is served by gunicorn (see
    # Dockerfile), which imports `app` directly and ignores this block.
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    print(f"SOPatch is running at http://localhost:{port}")
    app.run(debug=debug, host='0.0.0.0', port=port)
