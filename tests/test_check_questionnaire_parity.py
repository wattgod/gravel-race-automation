"""Public artifact parity only: no checkout, token, paid action or private data.

/questionnaire/ is the one-page Elementor form again (2026-11-13): the plan
billed every 4 weeks sells only from it. The retired two-step step 1 is not
generated; step 2 (/training-plans/details/) still must match its builder.
"""
import sys
from pathlib import Path
import urllib.error
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import check_questionnaire_parity as checker


@pytest.fixture
def pages():
    return {'questionnaire': checker.REPO_FILE.read_text(),
            'details': checker.intake.generate_page('details')}


def network(monkeypatch, pages, *, hops=()):
    calls = []
    def fetch(url=checker.LIVE_URL):
        calls.append(url)
        if url == checker.LIVE_URL:
            return checker.LivePage(pages['questionnaire'], checker.LIVE_URL, 200, hops)
        assert url == checker.intake.DETAILS_URL
        return checker.LivePage(pages['details'], url)
    monkeypatch.setattr(checker, 'fetch_live', fetch)
    return calls


def test_complete_current_flow_checks_both_public_pages_without_token(monkeypatch, pages):
    calls = network(monkeypatch, pages)
    assert checker.check_parity() == []
    assert calls == [checker.LIVE_URL, checker.intake.DETAILS_URL]


def test_the_questionnaire_redirecting_anywhere_is_drift(monkeypatch, pages):
    network(monkeypatch, pages, hops=((302, checker.LIVE_URL, checker.intake.START_URL),))
    assert checker.check_parity() == ['Unexpected questionnaire redirect or response']


@pytest.mark.parametrize('old', [
    '$15 per week until your A-race, rounded up to whole weeks. Four-week minimum. Paid once.',
    'Full refund within 7 days, no questions asked.',
    'One-time payment, no subscription.',
])
def test_widget_still_selling_the_one_off_plan_is_drift(monkeypatch, pages, old):
    """The purchase terms ship by hand in the Elementor widget. The form JS
    charges the plan billed every 4 weeks, so stale terms are drift."""
    pages['questionnaire'] = pages['questionnaire'].replace(
        '<span id="gg-plan-total">', '<span>' + old + '</span> <span id="gg-plan-total">')
    network(monkeypatch, pages)
    assert any(item.startswith('live page still shows retired offer copy') for item in checker.check_parity())


def test_widget_that_never_states_the_new_price_is_drift(monkeypatch, pages):
    pages['questionnaire'] = pages['questionnaire'].replace(checker.PLAN_PRICE_LINE, 'a price')
    network(monkeypatch, pages)
    assert f"live page does not state '{checker.PLAN_PRICE_LINE}'" in checker.check_parity()


def test_direct_200_retains_every_existing_field_and_marker_check(monkeypatch, pages):
    legacy = pages['questionnaire']
    network(monkeypatch, pages)
    assert checker.check_parity() == []
    assert len(checker.extract_fields(legacy)) > 60
    broken = legacy.replace('travelDatesGroup', 'missingTravelGroup')
    findings = checker.check_parity(broken, legacy)
    assert "content marker 'travelDatesGroup' in repo but missing live" in findings
    assert checker.check_parity('', legacy)


@pytest.mark.parametrize('change', [
    lambda s: s.replace('name="sex"', 'name="missing_sex"'),
    lambda s: s.replace('value="female"', 'value="wrong_option"'),
    lambda s: s.replace("submit: true", "submit: false"),
    lambda s: s.replace(checker.intake.TOKEN_SCRUB_HEAD_JS, ''),
    lambda s: s.replace(checker.intake.TOKEN_SCRUB_HEAD_JS, '<script src="https://www.googletagmanager.com/gtag/js"></script>' + checker.intake.TOKEN_SCRUB_HEAD_JS),
])
def test_details_questions_dynamic_behavior_and_token_privacy_remain_required(monkeypatch, pages, change):
    pages['details'] = change(pages['details'])
    network(monkeypatch, pages)
    assert any(item.startswith('details:') for item in checker.check_parity())


@pytest.mark.parametrize('url,code', [
    ('https://elsewhere.test/training-plans/start/', 302),
    ('http://gravelgodcycling.com/training-plans/start/', 302),
    (checker.intake.START_URL, 302),
    (checker.intake.START_URL, 301),
    (checker.intake.START_URL, 307),
])
def test_no_redirect_is_ever_followed(url, code):
    handler = checker._Redirects()
    with pytest.raises(checker.UnexpectedPage):
        handler.redirect_request(urllib.request.Request(checker.LIVE_URL), None, code, '', {}, url)
    with pytest.raises(checker.UnexpectedPage):
        checker._Redirects().redirect_request(urllib.request.Request(checker.intake.DETAILS_URL), None, code, '', {}, url)


def test_http_failure_is_a_drift_failure_not_an_unreachable_warning(monkeypatch):
    def fail(url=checker.LIVE_URL):
        raise urllib.error.HTTPError(url, 404, 'missing', {}, None)
    monkeypatch.setattr(checker, 'fetch_live', fail)
    assert checker.check_parity() == ['Questionnaire resource returned HTTP 404']


def test_unexpected_redirect_failure_is_reported_without_fetching_the_destination(monkeypatch):
    def fail(url=checker.LIVE_URL):
        raise checker.UnexpectedPage('unexpected')
    monkeypatch.setattr(checker, 'fetch_live', fail)
    assert checker.check_parity() == ['Questionnaire response violates the deployed flow contract']


def test_commented_privacy_script_cannot_disguise_execution_after_analytics(monkeypatch, pages):
    scrub = checker.intake.TOKEN_SCRUB_HEAD_JS
    pages['details'] = pages['details'].replace(scrub, '<!--' + scrub + '-->').replace('</body>', scrub + '</body>')
    network(monkeypatch, pages)
    assert 'details: complete ordered script contract differs from repository builder' in checker.check_parity()


@pytest.mark.parametrize('body,content_type', [(b'x' * 33, 'text/html'), (b'<html></html>', 'application/json')])
def test_fetch_bounds_and_html_type_are_required(monkeypatch, body, content_type):
    class Response:
        url = checker.LIVE_URL
        status = 200
        headers = {'Content-Type': content_type}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return body[:size]
    class Opener:
        def open(self, request, timeout): return Response()
    monkeypatch.setattr(checker, 'MAX_PAGE_BYTES', 32)
    monkeypatch.setattr(checker.urllib.request, 'build_opener', lambda handler: Opener())
    with pytest.raises(checker.UnexpectedPage):
        checker.fetch_live()


@pytest.mark.parametrize('change', [
    lambda s: s.replace('name="robots" content="noindex, follow"', 'name="robots" content'),
    lambda s: s.replace('</body>', '<script>window.extraFormCode=true;</script></body>'),
    lambda s: s.replace("gg-consent-banner", "changed-consent-banner"),
])
def test_bare_attributes_and_any_added_or_changed_details_script_fail_closed(monkeypatch, pages, change):
    pages['details'] = change(pages['details'])
    network(monkeypatch, pages)
    assert checker.check_parity()


def test_current_external_bundle_build_matches_without_writing_assets(monkeypatch, pages):
    import hashlib
    digest = hashlib.md5(checker._extract_js_content().encode()).hexdigest()[:8]
    pages['details'] = checker.intake.generate_page('details', external_assets={
        'css_tag': '', 'js_tag': f'<script src="/race/assets/gg-scripts.{digest}.js"></script>',
    })
    network(monkeypatch, pages)
    assert checker.check_parity() == []
    pages['details'] = pages['details'].replace(f'gg-scripts.{digest}.js', 'gg-scripts.00000000.js')
    assert 'details: complete ordered script contract differs from repository builder' in checker.check_parity()


def test_socket_failure_is_classified_at_fetch_boundary_only(monkeypatch):
    class Opener:
        def open(self, request, timeout): raise ConnectionResetError('network reset')
    monkeypatch.setattr(checker.urllib.request, 'build_opener', lambda handler: Opener())
    with pytest.raises(urllib.error.URLError, match='Public questionnaire transport unavailable'):
        checker.fetch_live()


def test_real_urllib_refuses_an_unexpected_redirect_before_fetching_it(monkeypatch):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Thread
    seen = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            self.send_response(302)
            self.send_header('Location', '/unexpected/')
            self.end_headers()
        def log_message(self, *args): pass
    server = HTTPServer(('127.0.0.1', 0), Handler)
    base = f'http://127.0.0.1:{server.server_port}'
    monkeypatch.setattr(checker, 'LIVE_URL', base + '/questionnaire/')
    monkeypatch.setattr(checker.intake, 'START_URL', base + '/training-plans/start/')
    thread = Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
    thread.start()
    try:
        with pytest.raises(checker.UnexpectedPage):
            checker.fetch_live(checker.LIVE_URL)
        assert seen == ['/questionnaire/']
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


@pytest.mark.parametrize('base', ['<base href="https://elsewhere.test/">', '<base target="_blank">'])
def test_base_outside_main_cannot_redirect_checked_relative_shared_script(monkeypatch, pages, base):
    pages['details'] = pages['details'].replace('</head>', base + '</head>')
    network(monkeypatch, pages)
    assert 'details: base elements are not allowed in the questionnaire contract' in checker.check_parity()
