"""Generate the native /coaching/setup/ completion page; private data comes from the edge."""
import argparse
from pathlib import Path

from brand_tokens import (get_favicon_head_snippet,
                         get_ga4_head_snippet)
from generate_coaching_apply import build_nav, build_apply_css
from generate_neo_brutalist import get_page_css
from shared_header import get_site_header_js
from cookie_consent import get_consent_banner_html

ROOT = Path(__file__).resolve().parents[1]


def generate_setup_page():
    # Remove the capability before analytics or external resources load. It is
    # consumed synchronously by the inline native script at the bottom of page.
    return '''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta name="referrer" content="no-referrer">
<title>Finish Your Coaching Setup | Gravel God</title>
<script>window.__GGSetupToken = new URLSearchParams(location.hash.slice(1)).get("token") || "";
history.replaceState(null, "", location.pathname);</script>
''' + get_favicon_head_snippet() + get_ga4_head_snippet() + get_page_css() + build_apply_css() + '<style>' + (ROOT / 'web/coaching-native.css').read_text() + '''</style>
</head><body class="gg-neo-brutalist-page" style="background:var(--gg-color-warm-paper);color:var(--gg-color-near-black);font-family:var(--gg-font-data);font-size:var(--gg-font-size-sm);line-height:1.7;min-height:100vh">''' + build_nav().replace('gg-breadcrumb-current">Apply', 'gg-breadcrumb-current">Setup') + '''
<main class="gg-apply-container">
  <div class="gg-apply-header"><h1>Finish your coaching setup</h1>
  <p>Your application is already saved. Review and sign the documents below.</p></div>
  <p id="setup-status" role="status" aria-live="polite"></p>
  <section id="coaching-setup" class="gg-native-consent gg-apply-form-card" hidden></section>
  <noscript>Please enable JavaScript, or email gravelgodcoaching@gmail.com for another signing method.</noscript>
</main>
<script>''' + (ROOT / 'web/coaching-native.js').read_text() + '''
GGNativeOnboarding.mountSetup(document.getElementById("coaching-setup"), document.getElementById("setup-status"));
''' + get_site_header_js() + '''
window.addEventListener("hashchange", function () {
  if (location.hash.indexOf("token=") >= 0) {
    GGNativeOnboarding.mountSetup(document.getElementById("coaching-setup"), document.getElementById("setup-status"));
  }
});
</script>''' + get_consent_banner_html() + '''</body></html>'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', default=str(ROOT / 'wordpress/output'))
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'coaching-setup.html').write_text(generate_setup_page())
    print('Generated coaching-setup.html')


if __name__ == '__main__':
    main()
