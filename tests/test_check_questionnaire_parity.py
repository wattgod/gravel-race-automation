"""Public artifact parity only: no checkout, token, paid action or private data."""
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
    return {key: checker.intake.generate_page(key) for key in ('start', 'details')}


def network(monkeypatch, pages, *, hops=None, final=None):
    calls = []
    def fetch(url=checker.LIVE_URL):
        calls.append(url)
        if url == checker.LIVE_URL:
            return checker.LivePage(pages['start'], final or checker.intake.START_URL, 200,
                                    ((302, checker.LIVE_URL, checker.intake.START_URL),) if hops is None else hops)
        assert url == checker.intake.DETAILS_URL
        return checker.LivePage(pages['details'], url)
    monkeypatch.setattr(checker, 'fetch_live', fetch)
    return calls


def test_complete_current_flow_checks_both_public_pages_without_token(monkeypatch, pages):
    calls = network(monkeypatch, pages)
    assert checker.check_parity() == []
    assert calls == [checker.LIVE_URL, checker.intake.DETAILS_URL]


def test_legacy_direct_200_retains_every_existing_field_and_marker_check(monkeypatch):
    legacy = checker.REPO_FILE.read_text()
    monkeypatch.setattr(checker, 'fetch_live', lambda: checker.LivePage(legacy, checker.LIVE_URL))
    assert checker.check_parity() == []
    assert len(checker.extract_fields(legacy)) > 60
    broken = legacy.replace('travelDatesGroup', 'missingTravelGroup')
    findings = checker.check_parity(broken, legacy)
    assert "content marker 'travelDatesGroup' in repo but missing live" in findings
    assert checker.check_parity('', legacy)


def test_start_without_intended_redirect_does_not_replace_legacy_contract(monkeypatch, pages):
    network(monkeypatch, pages, hops=(), final=checker.LIVE_URL)
    assert len(checker.check_parity()) > 60


@pytest.mark.parametrize('change', [
    lambda s: s.replace('name="race_date"', 'name="missing_date"'),
    lambda s: s.replace('name="_honeypot"', 'name="missing_honeypot"'),
    lambda s: s.replace('name="email" required', 'name="email"'),
    lambda s: s.replace("intake_flow: 'two_step'", "intake_flow: 'wrong'"),
    lambda s: s.replace("API_BASE + '/create-checkout'", "API_BASE + '/wrong'"),
    lambda s: s.replace('<script>\n/* Two-step questionnaire, step 1:', '<script src="">\n/* Two-step questionnaire, step 1:'),
    lambda s: s.replace('<script>\n/* Two-step questionnaire, step 1:', '<script nomodule>\n/* Two-step questionnaire, step 1:'),
    lambda s: s.replace('<script>\n/* Two-step questionnaire, step 1:', '<script type="application/json">\n/* Two-step questionnaire, step 1:'),
])
def test_damaged_start_controls_or_inline_checkout_behavior_fail(monkeypatch, pages, change):
    pages['start'] = change(pages['start'])
    network(monkeypatch, pages)
    assert any(item.startswith('start:') for item in checker.check_parity())


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


def test_comment_containing_entire_expected_markup_is_not_a_rendered_contract(monkeypatch, pages):
    markup = checker.intake.build_start_content()
    pages['start'] = pages['start'].replace(markup, '<!--' + markup + '-->')
    network(monkeypatch, pages)
    assert 'start: complete form DOM differs from repository builder' in checker.check_parity()


@pytest.mark.parametrize('url,code', [
    ('https://elsewhere.test/training-plans/start/', 302),
    ('http://gravelgodcycling.com/training-plans/start/', 302),
    (checker.intake.START_URL + '?t=synthetic', 302),
    (checker.intake.START_URL, 301),
    (checker.intake.START_URL, 307),
])
def test_only_the_exact_same_origin_intended_302_may_be_followed(url, code):
    handler = checker._Redirects()
    with pytest.raises(checker.UnexpectedPage):
        handler.redirect_request(urllib.request.Request(checker.LIVE_URL), None, code, '', {}, url)
    assert handler.hops == []


def test_a_second_redirect_and_any_details_redirect_are_refused():
    handler = checker._Redirects()
    request = handler.redirect_request(urllib.request.Request(checker.LIVE_URL), None, 302, '', {}, checker.intake.START_URL)
    assert request.full_url == checker.intake.START_URL
    with pytest.raises(checker.UnexpectedPage):
        handler.redirect_request(request, None, 302, '', {}, checker.intake.START_URL)
    with pytest.raises(checker.UnexpectedPage):
        checker._Redirects().redirect_request(urllib.request.Request(checker.intake.DETAILS_URL), None, 302, '', {}, checker.intake.START_URL)


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


@pytest.mark.parametrize('wrapper', ['template', 'noscript', 'div hidden', 'div inert'])
def test_matching_main_inside_an_inert_wrapper_is_not_a_visible_form(monkeypatch, pages, wrapper):
    markup = checker.intake.build_start_content()
    pages['start'] = pages['start'].replace(markup, '<' + wrapper + '>' + markup + '</' + wrapper.split()[0] + '>')
    network(monkeypatch, pages)
    assert checker.check_parity() == ['Questionnaire response violates the deployed flow contract']


def test_matching_behavior_inside_a_template_is_not_executable(monkeypatch, pages):
    js = checker.intake.START_JS_PATH.read_text()
    pages['start'] = pages['start'].replace('<script>\n' + js + '\n</script>', '<template><script>\n' + js + '\n</script></template>')
    network(monkeypatch, pages)
    assert 'start: complete ordered script contract differs from repository builder' in checker.check_parity()


@pytest.mark.parametrize('change', [
    lambda s: s.replace('name="robots" content="noindex, follow"', 'name="robots" content'),
    lambda s: s.replace('<script>\n/* Two-step questionnaire, step 1:', '<script type>\n/* Two-step questionnaire, step 1:'),
    lambda s: s.replace('<script>\n/* Two-step questionnaire, step 1:', '<script src>\n/* Two-step questionnaire, step 1:'),
    lambda s: s.replace('</body>', '<script>window.extraFormCode=true;</script></body>'),
    lambda s: s.replace("gg-consent-banner", "changed-consent-banner"),
])
def test_bare_attributes_and_any_added_or_changed_script_fail_closed(monkeypatch, pages, change):
    pages['start'] = change(pages['start'])
    network(monkeypatch, pages)
    assert checker.check_parity()


@pytest.mark.parametrize('wrapper', ['textarea', 'title', 'xmp'])
def test_form_text_inside_rcdata_cannot_satisfy_root_contract(monkeypatch, pages, wrapper):
    markup = checker.intake.build_start_content()
    pages['start'] = pages['start'].replace(markup, '<' + wrapper + '>' + markup + '</' + wrapper + '>')
    network(monkeypatch, pages)
    assert checker.check_parity()


def test_current_external_bundle_build_matches_without_writing_assets(monkeypatch, pages):
    import hashlib
    digest = hashlib.md5(checker._extract_js_content().encode()).hexdigest()[:8]
    for key in pages:
        pages[key] = checker.intake.generate_page(key, external_assets={
            'css_tag': '', 'js_tag': f'<script src="/race/assets/gg-scripts.{digest}.js"></script>',
        })
    network(monkeypatch, pages)
    assert checker.check_parity() == []
    pages['start'] = pages['start'].replace(f'gg-scripts.{digest}.js', 'gg-scripts.00000000.js')
    assert 'start: complete ordered script contract differs from repository builder' in checker.check_parity()


def test_socket_failure_is_classified_at_fetch_boundary_only(monkeypatch):
    class Opener:
        def open(self, request, timeout): raise ConnectionResetError('network reset')
    monkeypatch.setattr(checker.urllib.request, 'build_opener', lambda handler: Opener())
    with pytest.raises(urllib.error.URLError, match='Public questionnaire transport unavailable'):
        checker.fetch_live()


def test_duplicate_script_attributes_cannot_mask_browser_destination(monkeypatch, pages):
    pages['start'] = pages['start'].replace('<script>\n/* Two-step questionnaire, step 1:', '<script type="application/json" type="text/javascript">\n/* Two-step questionnaire, step 1:')
    network(monkeypatch, pages)
    assert checker.check_parity() == ['Questionnaire response violates the deployed flow contract']


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
    pages['start'] = pages['start'].replace('</head>', base + '</head>')
    network(monkeypatch, pages)
    assert checker.check_parity() == ['start: base elements are not allowed in the questionnaire contract']
