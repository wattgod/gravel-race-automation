"""Generated native signing UI contracts and deployment wiring."""
import re
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'wordpress'))
from generate_coaching_setup import generate_setup_page
from generate_coaching_apply import generate_apply_page
from brand_tokens import get_tokens_css


def test_native_setup_hides_capabilities_before_analytics_and_has_noindex():
    html = generate_setup_page()
    assert 'noindex,nofollow' in html
    assert 'name="referrer" content="no-referrer"' in html
    assert html.index('history.replaceState') < html.index('googletagmanager')
    assert 'GGNativeOnboarding.mountSetup' in html
    assert 'get_consent_banner_html' not in html
    assert 'Privacy choices' in html
    assert 'window.addEventListener("hashchange"' in html


def test_application_mounts_native_acceptance_and_downloads_saved_copy():
    html = generate_apply_page()
    assert 'id="gg-native-consent"' in html
    assert 'GGNativeOnboarding.mountIntake' in html
    assert 'data.native_acceptance = nativeAcceptance' in html
    assert 'nativeOnboarding.showReceipt(result.native_receipt)' in html
    assert 'Download your signed copy' in html
    assert 'input.checked = true' not in (ROOT / 'web/coaching-native.js').read_text()


def test_native_css_uses_existing_tokens_and_html_has_separate_style_tags():
    css = (ROOT / 'web/coaching-native.css').read_text()
    definitions = set(re.findall(r'(--gg-[\w-]+)\s*:', get_tokens_css()))
    refs = set(re.findall(r'var\((--gg-[\w-]+)', css))
    assert refs <= definitions
    html = generate_setup_page()
    assert '<style><style>' not in html
    assert re.search(r'<style>[^<]*\.gg-native-consent', html)


def test_native_javascript_parses_and_uses_safe_dom_construction():
    source = ROOT / 'web/coaching-native.js'
    assert 'innerHTML' not in source.read_text()
    subprocess.run(['node', '--check', str(source)], check=True, capture_output=True)


def test_setup_page_has_reproducible_deploy_flag():
    result = subprocess.run([sys.executable, 'scripts/push_wordpress.py', '--help'],
                            cwd=ROOT, capture_output=True, text=True, check=True)
    assert '--sync-coaching-setup' in result.stdout
