#!/usr/bin/env python3
"""
Generate legal pages (Privacy Policy, Terms of Service, Cookies Policy).

Uses brand tokens exclusively — zero hardcoded hex, no border-radius.
Pages are static HTML deployed alongside other generated pages.

Usage:
    python generate_legal_pages.py
    python generate_legal_pages.py --output-dir ./output
"""
from __future__ import annotations

import argparse
import html
from datetime import date
from pathlib import Path

from generate_neo_brutalist import (
    SITE_BASE_URL,
    get_page_css,
    write_shared_assets,
)
from brand_tokens import get_ga4_head_snippet, get_preload_hints
from shared_footer import get_mega_footer_html, get_mega_footer_css
from shared_header import get_site_header_html, get_site_header_css
from cookie_consent import get_consent_banner_html

OUTPUT_DIR = Path(__file__).parent / "output"

SITE_NAME = "Gravel God Cycling"
CONTACT_EMAIL = "gravelgodcoaching@gmail.com"
SITE_URL = SITE_BASE_URL
CURRENT_YEAR = date.today().year


def esc(text: str) -> str:
    return html.escape(str(text)) if text else ""


# ── Page Content ──────────────────────────────────────────────


def get_privacy_content() -> str:
    return f"""
<h2>What We Collect</h2>
<p>We collect only what is necessary to operate the site and provide our services:</p>
<ul>
<li><strong>Analytics data</strong> &mdash; via Google Analytics 4 (GA4), we collect anonymized usage data including pages visited, session duration, and general location (country/region). This data is collected only after you consent via the cookie banner. We do not intentionally send personally identifiable information to GA4. GA4 uses IP anonymization by default.</li>
<li><strong>Form submissions</strong> &mdash; when you fill out the training plan questionnaire or coaching application, we collect the information you provide (name, email, training data). This data is used solely to deliver the service you requested.</li>
<li><strong>Payment information</strong> &mdash; processed securely by <a href="https://stripe.com/privacy" target="_blank" rel="noopener">Stripe</a>. We never see or store your full card number.</li>
<li><strong>Email address</strong> &mdash; if you subscribe to our newsletter via Substack, your email is managed by <a href="https://substack.com/privacy" target="_blank" rel="noopener">Substack</a>.</li>
</ul>

<h2>How We Use Your Data</h2>
<ul>
<li>To deliver training plans, coaching, and consulting services you purchase</li>
<li>To improve the website based on aggregate usage patterns</li>
<li>To send transactional emails related to your purchases (receipts, delivery confirmations)</li>
</ul>
<p>We do not sell, rent, or share your personal data with third parties for marketing purposes. Ever.</p>

<h2>Cookies</h2>
<p>We use a minimal set of cookies. See our <a href="{SITE_URL}/cookies/">Cookie Policy</a> for specifics.</p>

<h2>Third-Party Services</h2>
<p>We use the following third-party services that may process data on your behalf:</p>
<ul>
<li><strong>Google Analytics 4</strong> &mdash; anonymized site analytics (consent-gated)</li>
<li><strong>Stripe</strong> &mdash; payment processing</li>
<li><strong>Substack</strong> &mdash; newsletter delivery</li>
<li><strong>Formsubmit.co</strong> &mdash; form handling for coaching applications</li>
<li><strong>Google Calendar</strong> &mdash; consulting session booking</li>
<li><strong>Jetpack</strong> &mdash; site security and performance monitoring</li>
<li><strong>SiteGround</strong> &mdash; web hosting</li>
</ul>

<h2>Data Retention</h2>
<p>Form submission data is retained for as long as needed to deliver the requested service, plus a reasonable period for follow-up support. You can request deletion of your data at any time by emailing <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>

<h2>Your Rights</h2>
<p>You have the right to:</p>
<ul>
<li>Access the personal data we hold about you</li>
<li>Request correction or deletion of your data</li>
<li>Withdraw consent for analytics cookies at any time (clear your cookies or use browser settings)</li>
<li>Opt out of any marketing communications</li>
</ul>
<p>To exercise any of these rights, email <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>

<h2>Changes</h2>
<p>We may update this policy as our services evolve. Material changes will be noted on this page with an updated revision date.</p>
"""


def get_terms_content() -> str:
    return f"""
<h2>Services</h2>
<p>{SITE_NAME} provides gravel cycling race information, custom training plans, coaching services, and consulting. All services are provided by Matti Rowe as a sole proprietor.</p>

<h2>Race Information</h2>
<p>Race profiles, ratings, and course descriptions on this site are editorial content based on publicly available information and community research. They are not affiliated with, endorsed by, or officially connected to any race organizer or governing body. Race details change &mdash; always verify with official race sources before making travel or registration decisions.</p>

<h2>Training Plans &amp; Coaching</h2>
<ul>
<li><strong>Training plans</strong> are one-time purchases delivered to your TrainingPeaks calendar. Pricing is calculated at checkout based on weeks until your target race, capped at $249.</li>
<li><strong>Coaching</strong> is billed every 4 weeks (13 billing cycles per year), not monthly. A one-time $99 setup fee applies. You may cancel at the end of any 4-week cycle with no penalty.</li>
<li><strong>Consulting</strong> is a one-time $150 payment for a 60-minute video call plus a written action plan.</li>
</ul>
<p>All training and coaching content is general fitness guidance. It is not medical advice. Consult a physician before starting any exercise program, especially if you have health conditions.</p>

<h2>Payments &amp; Refunds</h2>
<p>All payments are processed by Stripe. If you are unsatisfied with a training plan or consulting session, contact <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a> within 7 days. We handle refund requests on a case-by-case basis and aim to be fair.</p>
<p>Coaching subscriptions can be cancelled at any time. No refunds are issued for partially completed billing cycles.</p>

<h2>Intellectual Property</h2>
<p>All content on this site &mdash; text, ratings, code, design, and media &mdash; is the property of {SITE_NAME} unless otherwise noted. You may not reproduce, redistribute, or resell any content without written permission.</p>

<h2>Limitation of Liability</h2>
<p>{SITE_NAME} provides information and training guidance on an &ldquo;as is&rdquo; basis. We are not liable for injuries, race outcomes, equipment decisions, or any other consequences arising from the use of our content or services.</p>

<h2>Changes</h2>
<p>We reserve the right to update these terms. Continued use of the site after changes constitutes acceptance.</p>
"""


def get_cookies_content() -> str:
    return f"""
<h2>What Are Cookies</h2>
<p>Cookies are small text files stored by your browser. They help websites remember your preferences and understand how you use the site.</p>

<h2>Cookies We Use</h2>

<h3>Essential Cookies</h3>
<p>These are required for the site to function. They cannot be disabled.</p>
<table class="gg-legal-table">
<thead><tr><th>Cookie</th><th>Purpose</th><th>Duration</th></tr></thead>
<tbody>
<tr><td><code>gg_consent</code></td><td>Stores your cookie consent preference (accepted or declined)</td><td>365 days</td></tr>
<tr><td><code>wordpress_*</code></td><td>WordPress session management (admin only)</td><td>Session</td></tr>
<tr><td><code>tk_tc</code></td><td>Jetpack &mdash; site security monitoring</td><td>Session</td></tr>
</tbody>
</table>

<h3>Analytics Cookies</h3>
<p>Set only after you accept the cookie consent banner. Used to understand how visitors use the site so we can improve it.</p>
<table class="gg-legal-table">
<thead><tr><th>Cookie</th><th>Purpose</th><th>Duration</th></tr></thead>
<tbody>
<tr><td><code>_ga</code></td><td>Google Analytics &mdash; distinguishes unique users</td><td>2 years</td></tr>
<tr><td><code>_ga_*</code></td><td>Google Analytics &mdash; maintains session state</td><td>2 years</td></tr>
</tbody>
</table>

<h2>Client-Side Storage (localStorage)</h2>
<p>In addition to cookies, we use your browser&rsquo;s localStorage to save preferences and improve your experience. This data never leaves your browser and is not sent to any server.</p>
<table class="gg-legal-table">
<thead><tr><th>Key</th><th>Purpose</th><th>Duration</th></tr></thead>
<tbody>
<tr><td><code>gg-favorites</code></td><td>Your saved race favorites</td><td>Persistent</td></tr>
<tr><td><code>gg-saved-filters</code></td><td>Named filter configurations you create</td><td>Persistent</td></tr>
<tr><td><code>athlete_questionnaire_progress</code></td><td>Coaching application form progress (save/resume)</td><td>Persistent</td></tr>
<tr><td><code>gg_ab_assign</code></td><td>A/B test variant assignments for site optimization</td><td>Persistent</td></tr>
<tr><td><code>gg_ab_vid</code></td><td>Anonymous visitor ID for A/B testing (not linked to personal data)</td><td>Persistent</td></tr>
<tr><td><code>gg_ab_cache</code></td><td>Cached experiment configuration</td><td>Persistent</td></tr>
</tbody>
</table>

<h2>Third-Party Cookies</h2>
<p>We do not use any advertising or social media tracking cookies. The only third-party cookies come from Google Analytics (consent-gated) and Jetpack (site security).</p>

<h2>Managing Cookies</h2>
<p>You can control cookies through your browser settings. Most browsers let you block or delete cookies. Note that blocking essential cookies may prevent parts of the site from working correctly.</p>
<p>To withdraw analytics consent, clear your cookies or use your browser&rsquo;s cookie management tools. On your next visit, the consent banner will reappear.</p>
"""


LEGAL_PAGES = {
    "privacy": {
        "title": "Privacy Policy",
        "slug": "privacy",
        "content_fn": get_privacy_content,
        "description": f"Privacy policy for {SITE_NAME}. How we collect, use, and protect your data.",
    },
    "terms": {
        "title": "Terms of Service",
        "slug": "terms",
        "content_fn": get_terms_content,
        "description": f"Terms of service for {SITE_NAME}. Rules governing use of this website and its services.",
    },
    "cookies": {
        "title": "Cookie Policy",
        "slug": "cookies",
        "content_fn": get_cookies_content,
        "description": f"Cookie policy for {SITE_NAME}. What cookies we use and how to manage them.",
    },
}


def build_page_css() -> str:
    return f"""<style>
{get_site_header_css()}

.gg-legal-hero {{
  padding: var(--gg-spacing-2xl) var(--gg-spacing-xl) var(--gg-spacing-xl);
  background: var(--gg-color-warm-paper);
  border-bottom: 3px solid var(--gg-color-dark-brown);
}}
.gg-legal-hero-inner {{
  max-width: 640px;
  margin: 0 auto;
  text-align: center;
}}
.gg-legal-hero-title {{
  font-family: var(--gg-font-editorial);
  font-size: clamp(28px, 5vw, 42px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-sm) 0;
  line-height: 1.15;
}}
.gg-legal-hero-date {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
  letter-spacing: var(--gg-letter-spacing-wide);
}}
.gg-legal-body {{
  max-width: 640px;
  margin: 0 auto;
  padding: var(--gg-spacing-xl);
}}
.gg-legal-body h2 {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-md);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: var(--gg-spacing-xl) 0 var(--gg-spacing-sm) 0;
  letter-spacing: var(--gg-letter-spacing-standard);
  text-transform: uppercase;
}}
.gg-legal-body h3 {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-primary-brown);
  margin: var(--gg-spacing-lg) 0 var(--gg-spacing-xs) 0;
}}
.gg-legal-body p, .gg-legal-body li {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
}}
.gg-legal-body ul {{
  padding-left: var(--gg-spacing-lg);
  margin: var(--gg-spacing-sm) 0;
}}
.gg-legal-body li {{
  margin-bottom: var(--gg-spacing-xs);
}}
.gg-legal-body a {{
  color: var(--gg-color-teal);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: border-color var(--gg-transition-hover);
}}
.gg-legal-body a:hover {{
  border-color: var(--gg-color-teal);
}}
.gg-legal-body code {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  background: var(--gg-color-warm-paper);
  padding: 2px 6px;
  border: 1px solid var(--gg-color-cream);
}}
.gg-legal-table {{
  width: 100%;
  border-collapse: collapse;
  margin: var(--gg-spacing-md) 0;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
}}
.gg-legal-table th, .gg-legal-table td {{
  text-align: left;
  padding: var(--gg-spacing-xs) var(--gg-spacing-sm);
  border-bottom: 1px solid var(--gg-color-cream);
  color: var(--gg-color-primary-brown);
}}
.gg-legal-table th {{
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  color: var(--gg-color-dark-brown);
}}

{get_mega_footer_css()}

@media (max-width: 600px) {{
  .gg-legal-body {{ padding: var(--gg-spacing-md); }}
  .gg-legal-table {{ font-size: 11px; }}
}}
</style>"""


def generate_page(page_key: str, output_dir: Path) -> None:
    page = LEGAL_PAGES[page_key]
    title = page["title"]
    slug = page["slug"]
    content = page["content_fn"]()
    description = page["description"]

    nav = get_site_header_html(active="about")
    breadcrumb = f'''<div class="gg-breadcrumb" style="max-width:640px;margin:0 auto;padding:var(--gg-spacing-sm) var(--gg-spacing-xl) 0;">
  <a href="{SITE_URL}/" style="color:var(--gg-color-teal);text-decoration:none;font-family:var(--gg-font-data);font-size:12px;">Home</a>
  <span style="color:var(--gg-color-secondary-brown);margin:0 4px;">&rsaquo;</span>
  <span style="color:var(--gg-color-secondary-brown);font-family:var(--gg-font-data);font-size:12px;">{esc(title)}</span>
</div>'''
    preload = get_preload_hints()
    css = build_page_css()
    page_css = get_page_css()
    footer = get_mega_footer_html()

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)} | Gravel God</title>
  <meta name="description" content="{esc(description)}">
  <meta name="robots" content="noindex, follow">
  <link rel="canonical" href="{SITE_URL}/{slug}/">
  <meta property="og:title" content="{esc(title)} | Gravel God">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{SITE_URL}/{slug}/">
  <meta property="og:image" content="{SITE_URL}/og/homepage.jpg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:image" content="{SITE_URL}/og/homepage.jpg">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' fill='%233a2e25'/><text x='16' y='24' text-anchor='middle' font-family='serif' font-size='24' font-weight='700' fill='%239a7e0a'>G</text></svg>">
  {preload}
  {page_css}
  {css}
  {get_ga4_head_snippet()}
</head>
<body>
<div class="gg-neo-brutalist-page">
  {nav}
  {breadcrumb}

  <section class="gg-legal-hero">
    <div class="gg-legal-hero-inner">
      <h1 class="gg-legal-hero-title">{esc(title)}</h1>
      <p class="gg-legal-hero-date">Last updated: {date.today().strftime('%B')} {CURRENT_YEAR}</p>
    </div>
  </section>

  <main class="gg-legal-body">
    {content}
  </main>

  {footer}
</div>
{get_consent_banner_html()}
</body>
</html>"""

    out_path = output_dir / f"{slug}.html"
    out_path.write_text(html_content)
    print(f"Generated {out_path} ({len(html_content):,} bytes)")


def main():
    parser = argparse.ArgumentParser(description="Generate legal pages")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_shared_assets(args.output_dir)

    for key in LEGAL_PAGES:
        generate_page(key, args.output_dir)


if __name__ == "__main__":
    main()
