#!/usr/bin/env python3
"""Validate the deployed questionnaire against its authoritative repository flow.

/questionnaire/ is the Elementor page again (2026-11-13): the plan billed
every 4 weeks is sold from the one-page questionnaire only, and the two-step
step 1 at /training-plans/start/ is retired. A direct 200 gets the Elementor
field/marker checks plus an offer check: the live page must state the plan
billed every 4 weeks and must not show any retired one-off offer phrase
(the purchase terms live in the widget, which deploys by hand). A redirect
back to the retired step 1, or any other redirect, is drift. The two-step
step 2 (/training-plans/details/) must still match its generated DOM.
No checkout, private token, saved answer or payment request is made.
Exit: 0 parity, 1 drift, 2 fetch/parse failure.
"""

from dataclasses import dataclass
from html.parser import HTMLParser
import hashlib
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_FILE = ROOT / 'web' / 'training-plans-questionnaire.html'
LIVE_URL = 'https://gravelgodcycling.com/questionnaire/'
USER_AGENT = 'Mozilla/5.0 (parity-check; gravel-god-automation)'
MAX_PAGE_BYTES = 2 * 1024 * 1024
sys.path.insert(0, str(ROOT / 'wordpress'))
import generate_plan_intake_pages as intake  # noqa: E402
from plan_offer import PLAN_PRICE_LINE, stale_offer_phrases  # noqa: E402
from generate_neo_brutalist import _extract_js_content  # noqa: E402

CONTENT_MARKERS = ['gg-trust-strip', 'travelDatesGroup', '#178079', 'gg-purchase-terms']
VOID_TAGS = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}


class UnexpectedPage(ValueError):
    """A fetched resource cannot represent this deployed flow."""


@dataclass(frozen=True)
class LivePage:
    html: str
    url: str
    status: int = 200
    redirects: tuple = ()


class _Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        self.hops = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Refuse before following: the questionnaire and step 2 both answer
        # 200 directly. A redirect (back to the retired /training-plans/start/
        # or anywhere else) is drift, and its destination is never fetched.
        if fp is not None:
            try:
                fp.close()
            except OSError:
                pass
        self.hops.append((code, req.full_url, newurl))
        raise UnexpectedPage('Unexpected questionnaire redirect')


def fetch_live(url=LIVE_URL) -> LivePage:
    redirects = _Redirects()
    opener = urllib.request.build_opener(redirects)
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with opener.open(req, timeout=30) as resp:
            if resp.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'text/html':
                raise UnexpectedPage('Questionnaire response is not HTML')
            raw = resp.read(MAX_PAGE_BYTES + 1)
            if len(raw) > MAX_PAGE_BYTES:
                raise UnexpectedPage('Questionnaire response exceeds size bound')
            return LivePage(raw.decode('utf-8'), resp.url, resp.status, tuple(redirects.hops))
    except urllib.error.HTTPError:
        raise  # An HTTP failure is a contract failure, not an unreachable warning.
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        # Only this network boundary may classify transport unavailability.
        raise urllib.error.URLError('Public questionnaire transport unavailable') from exc



class _Contract(HTMLParser):
    """Normalized actual DOM, not marker substrings that could live in comments."""
    def __init__(self, source, root_id):
        super().__init__(convert_charrefs=True)
        self.root_id = root_id
        self.roots = 0
        self.depth = 0
        self.dom = []
        self.scripts = []
        self.script = None
        self.canonicals = []
        self.has_base = False
        self.robots = []
        self.ancestors = []
        self.root_paths = []
        self.script_paths = []
        self.script_path = ()
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if len(attr) != len(attrs):
            raise UnexpectedPage('Duplicate questionnaire attributes')
        inert_parent = any(parent in ('template', 'noscript') or 'hidden' in properties or 'inert' in properties
                           for parent, properties in self.ancestors)
        if tag == 'main' and attr.get('id') == self.root_id:
            self.roots += 1
            self.root_paths.append(tuple(parent for parent, _ in self.ancestors))
            if inert_parent or any(parent == 'head' for parent, _ in self.ancestors):
                raise UnexpectedPage('Questionnaire root is inert')
            if self.depth:
                raise UnexpectedPage('Nested questionnaire root')
            self.depth = 1
        elif self.depth and tag not in VOID_TAGS:
            self.depth += 1
        if self.depth:
            self.dom.append(('start', tag, tuple(sorted(attrs, key=lambda item: item[0]))))
        if tag == 'script':
            self.script = [attr, '']
            self.script_path = tuple(parent for parent, _ in self.ancestors)
        if tag == 'base':
            self.has_base = True
        if tag == 'link' and attr.get('rel') == 'canonical':
            self.canonicals.append(attr.get('href'))
        if tag == 'meta' and attr.get('name') == 'robots':
            self.robots.append(attr.get('content') or '')
        if tag not in VOID_TAGS:
            self.ancestors.append((tag, attr))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.ancestors) - 1, -1, -1):
            if self.ancestors[index][0] == tag:
                del self.ancestors[index:]
                break
        if self.depth:
            self.dom.append(('end', tag))
            if tag not in VOID_TAGS:
                self.depth -= 1
        if tag == 'script' and self.script is not None:
            self.scripts.append(self.script)
            self.script_paths.append(self.script_path)
            self.script = None

    def handle_data(self, data):
        if self.script is not None:
            self.script[1] += data
        if self.depth and data.strip():
            self.dom.append(('text', re.sub(r'\s+', ' ', data).strip()))


def extract_fields(html: str) -> set:
    """Legacy field coverage, intentionally preserved for a legacy 200."""
    fields = set(re.findall(r'<(?:input|select|textarea)[^>]*\bname="([^"]+)"', html))
    fields |= set(re.findall(r'<(?:div|input|select|textarea)[^>]*\bid="([^"]+)"', html))
    return fields


def _offer_findings(live_html):
    """The widget's purchase terms must describe the plan billed every 4
    weeks: the form JS charges it, so a page still quoting the one-off plan
    tells the buyer a price they won't be charged."""
    findings = [f"live page still shows retired offer copy: '{phrase}'"
                for phrase in stale_offer_phrases(live_html)]
    if PLAN_PRICE_LINE not in live_html:
        findings.append(f"live page does not state '{PLAN_PRICE_LINE}'")
    return findings


def _legacy_parity(live_html, repo_html):
    findings = []
    for field in sorted(extract_fields(repo_html)):
        if field not in live_html:
            findings.append(f"form field '{field}' in repo but missing live")
    for marker in CONTENT_MARKERS:
        if marker in repo_html and marker not in live_html:
            findings.append(f"content marker '{marker}' in repo but missing live")
    return findings


def _script_contract(document):
    # All script tags, including external fingerprints, attributes and order.
    # This also rejects unknown extra scripts and scripts moved into RCDATA or templates.
    return [(tuple(sorted(attrs.items(), key=lambda item: item[0])), body.strip(), path)
            for (attrs, body), path in zip(document.scripts, document.script_paths)]


def _two_step_parity(page, key):
    config = intake.PAGES[key]
    expected_url = intake.SITE_BASE_URL + config['canonical']
    if page.status != 200 or page.url != expected_url:
        return [f'{key}: unexpected response status or destination']
    root_id = 'gg-plan-' + key
    actual = _Contract(page.html, root_id)
    inline = _Contract(intake.generate_page(key), root_id)
    # Mirror the generator's content-addressed shared JS name without writing assets.
    digest = hashlib.md5(_extract_js_content().encode('utf-8')).hexdigest()[:8]
    external = _Contract(intake.generate_page(key, external_assets={
        'css_tag': '', 'js_tag': f'<script src="/race/assets/gg-scripts.{digest}.js"></script>',
    }), root_id)
    findings = []
    if actual.has_base:
        findings.append(f'{key}: base elements are not allowed in the questionnaire contract')
    if actual.roots != 1 or actual.depth != 0 or actual.dom != inline.dom or actual.root_paths != inline.root_paths:
        findings.append(f'{key}: complete form DOM differs from repository builder')
    if actual.canonicals != [expected_url] or not any('noindex' in [part.strip() for part in value.split(',')] for value in actual.robots):
        findings.append(f'{key}: canonical or noindex contract differs')
    if _script_contract(actual) not in (_script_contract(inline), _script_contract(external)):
        findings.append(f'{key}: complete ordered script contract differs from repository builder')
    return findings


def check_parity(live_html: str = None, repo_html: str = None) -> list:
    """Pure legacy injection remains supported; network mode validates exact routing."""
    if repo_html is None:
        repo_html = REPO_FILE.read_text()
    if live_html is not None:
        return _legacy_parity(live_html, repo_html)
    try:
        page = fetch_live()
        if page.status == 200 and page.url == LIVE_URL and not page.redirects:
            findings = _legacy_parity(page.html, repo_html) + _offer_findings(page.html)
        else:
            return ['Unexpected questionnaire redirect or response']
        details = fetch_live(intake.DETAILS_URL)
        if details.redirects:
            return findings + ['details: unexpected redirect']
        return findings + _two_step_parity(details, 'details')
    except (UnexpectedPage, UnicodeDecodeError):
        return ['Questionnaire response violates the deployed flow contract']
    except urllib.error.HTTPError as exc:
        return [f'Questionnaire resource returned HTTP {exc.code}']


def main():
    try:
        findings = check_parity()
    except Exception as exc:
        print(f'Questionnaire parity check could not run: {type(exc).__name__}')
        return 2
    if findings:
        print(f'Questionnaire DRIFT detected ({len(findings)} findings):')
        for finding in findings:
            print(f'  - {finding}')
        print('Repair the matching deployed flow: legacy Elementor or generated two-step intake. See docs/questionnaire-parity-check.md.')
        return 1
    print('Questionnaire parity: deployed flow matches repository contract')
    return 0


if __name__ == '__main__':
    sys.exit(main())
