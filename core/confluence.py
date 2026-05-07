"""
confluence.py -- SOPatch Confluence Integration

Handles reading from and writing to Confluence pages via the REST API.
Confluence is the source of truth for all SOPs -- no local SOP files needed.
"""

import os
import re
import requests
from html.parser import HTMLParser
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()


def get_credentials():
    return {
        'base_url': os.getenv('CONFLUENCE_BASE_URL'),
        'email': os.getenv('CONFLUENCE_EMAIL'),
        'api_token': os.getenv('CONFLUENCE_API_TOKEN'),
        'page_id': os.getenv('CONFLUENCE_PAGE_ID'),
        'space_key': os.getenv('CONFLUENCE_SPACE_KEY'),
        'sop_parent_id': os.getenv('CONFLUENCE_SOP_PARENT_ID')
    }


def get_auth(creds):
    return HTTPBasicAuth(creds['email'], creds['api_token'])


# ── Reading from Confluence ──────────────────────────────────────────────────

def get_sop_pages(creds):
    """
    Fetch all child pages under the designated SOPs parent page.
    Includes labels, content, and version for each page.
    """
    parent_id = creds['sop_parent_id']
    url = (
        f"{creds['base_url']}/wiki/rest/api/content/{parent_id}/child/page"
        f"?limit=100&expand=body.storage,version,metadata.labels"
    )
    response = requests.get(url, auth=get_auth(creds))

    if response.status_code != 200:
        raise Exception(f"Failed to fetch SOP pages: {response.status_code} -- {response.text}")

    pages = []
    for page in response.json().get('results', []):
        raw_html = page['body']['storage']['value']
        plain_text = confluence_storage_to_text(raw_html)
        labels = [
            lbl['name']
            for lbl in page.get('metadata', {}).get('labels', {}).get('results', [])
        ]
        pages.append({
            'page_id': page['id'],
            'title': page['title'],
            'version': page['version']['number'],
            'content': plain_text,
            'raw_html': raw_html,
            'labels': labels
        })

    return pages


def set_page_labels(page_id, labels, creds):
    """
    Replace all labels on a Confluence page with the given list.
    Clears existing labels first, then writes the new ones.
    """
    auth = get_auth(creds)
    base_url = creds['base_url']

    # Fetch and remove existing labels
    existing = requests.get(
        f"{base_url}/wiki/rest/api/content/{page_id}/label",
        auth=auth
    ).json().get('results', [])

    for lbl in existing:
        requests.delete(
            f"{base_url}/wiki/rest/api/content/{page_id}/label?name={lbl['name']}",
            auth=auth
        )

    # Write new labels
    if labels:
        payload = [{'prefix': 'global', 'name': lbl} for lbl in labels]
        r = requests.post(
            f"{base_url}/wiki/rest/api/content/{page_id}/label",
            json=payload,
            auth=auth
        )
        if r.status_code not in (200, 201):
            raise Exception(f"Failed to set labels on page {page_id}: {r.status_code} -- {r.text}")


def get_page(page_id, creds):
    """
    Fetch a single Confluence page by ID.
    Returns title, version, plain-text content, and raw HTML body.
    """
    url = f"{creds['base_url']}/wiki/rest/api/content/{page_id}?expand=body.storage,version"
    response = requests.get(url, auth=get_auth(creds))

    if response.status_code != 200:
        raise Exception(f"Failed to fetch page {page_id}: {response.status_code} -- {response.text}")

    data = response.json()
    raw_html = data['body']['storage']['value']
    return {
        'id': page_id,
        'title': data['title'],
        'version': data['version']['number'],
        'content': confluence_storage_to_text(raw_html),
        'raw_html': raw_html
    }


class _TextExtractor(HTMLParser):
    """Strip Confluence XHTML to clean readable text for Claude."""

    BLOCK_TAGS = {'h1', 'h2', 'h3', 'h4', 'p', 'li', 'br', 'hr', 'ul', 'ol', 'tr', 'td', 'th'}
    HEADING_TAGS = {'h1', 'h2', 'h3', 'h4'}

    def __init__(self):
        super().__init__()
        self.parts = []
        self._tag_stack = []

    def handle_starttag(self, tag, attrs):
        self._tag_stack.append(tag)
        if tag in self.HEADING_TAGS:
            level = int(tag[1])
            self.parts.append('\n' + '#' * level + ' ')
        elif tag == 'li':
            self.parts.append('\n- ')
        elif tag == 'br':
            self.parts.append('\n')
        elif tag == 'hr':
            self.parts.append('\n---\n')
        elif tag in ('p', 'tr', 'td', 'th'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
        if tag in ('h1', 'h2', 'h3', 'h4', 'p', 'ul', 'ol'):
            self.parts.append('\n')

    def handle_data(self, data):
        self.parts.append(data)

    def get_text(self):
        text = ''.join(self.parts)
        # Collapse excessive blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


def confluence_storage_to_text(html):
    """Convert Confluence XHTML storage format to plain readable text."""
    parser = _TextExtractor()
    parser.feed(html)
    return parser.get_text()


# ── Writing to Confluence ────────────────────────────────────────────────────

def markdown_to_confluence(text):
    """Convert basic markdown to Confluence storage format (XHTML)."""
    lines = text.split('\n')
    html_lines = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append('<p></p>')
            continue

        if stripped.startswith('### '):
            if in_list: html_lines.append('</ul>'); in_list = False
            html_lines.append(f'<h3>{stripped[4:]}</h3>')
        elif stripped.startswith('## '):
            if in_list: html_lines.append('</ul>'); in_list = False
            html_lines.append(f'<h2>{stripped[3:]}</h2>')
        elif stripped.startswith('# '):
            if in_list: html_lines.append('</ul>'); in_list = False
            html_lines.append(f'<h1>{stripped[2:]}</h1>')
        elif stripped.startswith('- '):
            if not in_list: html_lines.append('<ul>'); in_list = True
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped[2:])
            html_lines.append(f'<li>{content}</li>')
        else:
            if in_list: html_lines.append('</ul>'); in_list = False
            line_html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped)
            html_lines.append(f'<p>{line_html}</p>')

    if in_list:
        html_lines.append('</ul>')

    return '\n'.join(html_lines)


def sanitize_for_html(text):
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = text.replace('\n', '<br/>')
    return text


def parse_analysis_blocks(analysis_text):
    """Parse Claude's structured analysis output into a list of dicts."""
    import re
    blocks = []
    for raw in analysis_text.split('---'):
        raw = raw.strip()
        if 'SECTION:' not in raw:
            continue
        block = {}
        lines = raw.split('\n')
        current_key = None
        buffer = []
        for line in lines:
            if line.startswith('SECTION:'):
                current_key = 'section'
                buffer = [line.replace('SECTION:', '').strip()]
            elif line.startswith('CURRENT WORDING:'):
                if current_key: block[current_key] = '\n'.join(buffer).strip()
                current_key = 'current'
                buffer = [line.replace('CURRENT WORDING:', '').strip()]
            elif line.startswith('WHY OUTDATED:'):
                if current_key: block[current_key] = '\n'.join(buffer).strip()
                current_key = 'why'
                buffer = [line.replace('WHY OUTDATED:', '').strip()]
            elif line.startswith('SUGGESTED REWRITE:'):
                if current_key: block[current_key] = '\n'.join(buffer).strip()
                current_key = 'rewrite'
                buffer = [line.replace('SUGGESTED REWRITE:', '').strip()]
            else:
                buffer.append(line)
        if current_key:
            block[current_key] = '\n'.join(buffer).strip()
        if block:
            blocks.append(block)
    return blocks


def strip_existing_change_log(html):
    """Remove any previously appended SOPatch change log so we never stack duplicates."""
    # Strips from the first <hr /> that precedes a SOPatch Change Log heading to end of content
    return re.sub(r'<hr\s*/>\s*<h2>SOPatch Change Log</h2>.*', '', html, flags=re.DOTALL)


def update_sop_metadata(html, new_sop_version, date_str):
    """
    Update the Version and Last Updated cells in the SOP metadata table at the top of the page.
    Handles both plain text and bold (<strong>) cell values.
    """
    html = re.sub(
        r'(<td><strong>Version</strong></td><td>)[^<]*(</td>)',
        lambda m: m.group(1) + new_sop_version + m.group(2),
        html
    )
    html = re.sub(
        r'(<td><strong>Last Updated</strong></td><td>)[^<]*(</td>)',
        lambda m: m.group(1) + date_str + m.group(2),
        html
    )
    return html


def next_sop_version(html):
    """
    Read the current Version value from the SOP metadata table and return the incremented version.
    e.g. '1.5' -> '1.6', '2.0' -> '2.1'. Falls back to '1.1' if not found.
    """
    match = re.search(r'<td><strong>Version</strong></td><td>(\d+)\.(\d+)</td>', html)
    if match:
        major, minor = int(match.group(1)), int(match.group(2))
        return f'{major}.{minor + 1}'
    return '1.1'


def build_updated_body(original_html, analysis_text, new_version=None):
    """
    Build the updated Confluence page body.
    Updates the Version and Last Updated fields in the SOP metadata table,
    then appends a SOPatch change log.
    """
    from datetime import datetime
    import zoneinfo

    now = datetime.now(zoneinfo.ZoneInfo('America/Toronto'))
    timestamp = now.strftime('%b %d, %Y at %I:%M %p %Z')
    date_str = now.strftime('%Y-%m-%d')
    version_label = f'Version {new_version}' if new_version else 'this version'

    # Strip any previously appended change log to avoid stacking duplicates
    original_html = strip_existing_change_log(original_html)

    # Use Confluence's integer version number (e.g. 6) to update the metadata table
    new_sop_version = str(new_version) if new_version else next_sop_version(original_html)
    updated_html = update_sop_metadata(original_html, new_sop_version, date_str)

    blocks = parse_analysis_blocks(analysis_text)

    change_log = '<hr /><h2>SOPatch Change Log</h2>'
    change_log += f'<p><em>Last updated: {timestamp} ({version_label}) &mdash; Sections automatically flagged by SOPatch. Review and apply suggested rewrites.</em></p>'

    for block in blocks:
        change_log += f'<h3>{block.get("section", "")}</h3>'
        change_log += '<table data-layout="default">'
        change_log += '<colgroup><col style="width: 180px;"/><col style="width: 580px;"/></colgroup>'
        change_log += '<tbody>'
        change_log += f'<tr><td><strong>Last updated</strong></td><td>{timestamp} ({version_label})</td></tr>'
        change_log += f'<tr><td><strong>Current wording</strong></td><td><em>{sanitize_for_html(block.get("current", ""))}</em></td></tr>'
        change_log += f'<tr><td><strong>Why outdated</strong></td><td>{sanitize_for_html(block.get("why", ""))}</td></tr>'
        change_log += f'<tr><td><strong>Suggested rewrite</strong></td><td><strong>{sanitize_for_html(block.get("rewrite", ""))}</strong></td></tr>'
        change_log += '</tbody></table>'

    return updated_html + '\n' + change_log


def update_page(page_id, updated_body, creds, page=None):
    """Write updated content back to a Confluence page."""
    if page is None:
        page = get_page(page_id, creds)
    new_version = page['version'] + 1

    url = f"{creds['base_url']}/wiki/rest/api/content/{page_id}"
    payload = {
        'id': page_id,
        'type': 'page',
        'title': page['title'],
        'version': {'number': new_version},
        'body': {
            'storage': {
                'value': updated_body,
                'representation': 'storage'
            }
        }
    }

    response = requests.put(url, json=payload, auth=get_auth(creds),
                            headers={'Content-Type': 'application/json'})

    if response.status_code not in (200, 201):
        raise Exception(f"Failed to update page: {response.status_code} -- {response.text}")

    return {
        'success': True,
        'page_id': page_id,
        'title': page['title'],
        'new_version': new_version,
        'url': f"{creds['base_url']}/wiki/spaces/SC/pages/{page_id}"
    }


def push_to_confluence(page_id, analysis_text, creds=None):
    """
    Push an approved SOP update to Confluence.
    Fetches the current page, appends the SOPatch change log, and writes it back.
    """
    if creds is None:
        creds = get_credentials()

    if not all([creds['base_url'], creds['email'], creds['api_token'], page_id]):
        raise Exception("Missing Confluence credentials in .env file")

    page = get_page(page_id, creds)
    new_version = page['version'] + 1
    updated_body = build_updated_body(page['raw_html'], analysis_text, new_version=new_version)
    return update_page(page_id, updated_body, creds, page=page)
