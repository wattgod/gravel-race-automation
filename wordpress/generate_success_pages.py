#!/usr/bin/env python3
"""
Generate post-checkout success pages for all 3 product types.

Pages:
  /training-plans/success/  — after training plan purchase
  /coaching/welcome/        — after coaching subscription
  /consulting/confirmed/    — after consulting payment

Each page:
  - Fires GA4 `purchase` event with session_id from URL
  - Shows next-steps specific to the product
  - Cross-sells other products
  - Uses shared header/footer + brand tokens

Usage:
    python generate_success_pages.py
    python generate_success_pages.py --output-dir ./output
"""
from __future__ import annotations

import argparse
import html
from pathlib import Path

from generate_neo_brutalist import (
    GA_MEASUREMENT_ID,
    SITE_BASE_URL,
    get_page_css,
    build_inline_js,
    write_shared_assets,
)
from brand_tokens import get_ab_head_snippet, get_preload_hints
from shared_footer import get_mega_footer_html
from shared_header import get_site_header_html

OUTPUT_DIR = Path(__file__).parent / "output"


def esc(text) -> str:
    return html.escape(str(text)) if text else ""


# ── Shared Components ────────────────────────────────────────


def build_success_css() -> str:
    """CSS for all success pages. Uses brand tokens only."""
    return """<style>
.gg-success-hero {
  padding: 80px 24px 60px;
  text-align: center;
  background: var(--gg-color-warm-paper);
  border-bottom: 3px solid var(--gg-color-primary-brown);
}
.gg-success-hero h1 {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-2xl);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-primary-brown);
  margin: 0 0 16px;
}
.gg-success-hero p {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-md);
  color: var(--gg-color-secondary-brown);
  max-width: 600px;
  margin: 0 auto;
  line-height: 1.6;
}
.gg-success-check {
  display: inline-block;
  width: 64px;
  height: 64px;
  border: 3px solid var(--gg-color-teal);
  color: var(--gg-color-teal);
  font-size: var(--gg-font-size-2xl);
  line-height: 58px;
  text-align: center;
  margin-bottom: 24px;
}
.gg-success-steps {
  padding: 60px 24px;
  max-width: 700px;
  margin: 0 auto;
}
.gg-success-steps h2 {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--gg-color-teal);
  margin: 0 0 32px;
}
.gg-success-step {
  display: flex;
  gap: 20px;
  margin-bottom: 32px;
  align-items: flex-start;
}
.gg-success-step-num {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border: 2px solid var(--gg-color-primary-brown);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-primary-brown);
  text-align: center;
  line-height: 32px;
}
.gg-success-step-text h3 {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-lg);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-primary-brown);
  margin: 0 0 6px;
}
.gg-success-step-text p {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-secondary-brown);
  margin: 0;
  line-height: 1.6;
}
.gg-success-crosssell {
  padding: 60px 24px;
  background: var(--gg-color-warm-paper);
  text-align: center;
  border-top: 3px solid var(--gg-color-primary-brown);
}
.gg-success-crosssell h2 {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-xl);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-primary-brown);
  margin: 0 0 16px;
}
.gg-success-crosssell p {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-secondary-brown);
  max-width: 500px;
  margin: 0 auto 24px;
  line-height: 1.6;
}
.gg-success-cta {
  display: inline-block;
  padding: 14px 32px;
  background: var(--gg-color-primary-brown);
  color: var(--gg-color-warm-paper);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  text-decoration: none;
  border: 3px solid var(--gg-color-primary-brown);
  transition: background-color 0.2s, color 0.2s;
}
.gg-success-cta:hover {
  background: var(--gg-color-warm-paper);
  color: var(--gg-color-primary-brown);
}
.gg-success-support {
  padding: 40px 24px;
  text-align: center;
}
.gg-success-support p {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-tan);
  margin: 0;
}
.gg-success-support a {
  color: var(--gg-color-teal);
  text-decoration: none;
}
.gg-success-support a:hover {
  border-bottom: 2px solid var(--gg-color-teal);
}
@media (max-width: 600px) {
  .gg-success-hero { padding: 60px 16px 40px; }
  .gg-success-hero h1 { font-size: var(--gg-font-size-xl); }
  .gg-success-steps { padding: 40px 16px; }
  .gg-success-crosssell { padding: 40px 16px; }
}
</style>"""


def build_success_js() -> str:
    """JS for GA4 purchase event + session_id extraction."""
    return """<script>
(function() {
  var params = new URLSearchParams(window.location.search);
  var sessionId = params.get('session_id') || '';
  var productType = document.querySelector('[data-product-type]');
  var ptype = productType ? productType.getAttribute('data-product-type') : 'unknown';

  if (typeof gtag === 'function') {
    gtag('event', 'purchase', {
      transaction_id: sessionId,
      product_type: ptype,
    });
    gtag('event', 'success_page_view', {
      product_type: ptype,
      session_id: sessionId,
    });
  }

  // Dedup: mark this session as converted so the funnel doesn't double-count
  if (sessionId && typeof sessionStorage !== 'undefined') {
    sessionStorage.setItem('gg_converted_' + sessionId, '1');
  }

  // Cross-sell CTA tracking
  var ctas = document.querySelectorAll('.gg-success-cta');
  ctas.forEach(function(cta) {
    cta.addEventListener('click', function() {
      if (typeof gtag === 'function') {
        gtag('event', 'success_crosssell_click', {
          product_type: ptype,
          destination: cta.getAttribute('href'),
        });
      }
    });
  });
})();
</script>"""


# ── Training Plan Success ─────────────────────────────────────


def build_training_plan_success() -> str:
    """Content sections for training plan success page."""
    hero = f"""
  <div class="gg-success-hero" data-product-type="training_plan">
    <div class="gg-success-check">&check;</div>
    <h1>Your Training Plan Is on the Way</h1>
    <p>Payment confirmed. Your custom plan is being generated and will be
    delivered to your email shortly.</p>
  </div>"""

    steps = """
  <div class="gg-success-steps">
    <h2>WHAT HAPPENS NEXT</h2>
    <div class="gg-success-step">
      <div class="gg-success-step-num">1</div>
      <div class="gg-success-step-text">
        <h3>Check Your Email</h3>
        <p>Your plan is being built right now. You'll receive an email
        once it's ready. Check spam if you don't see it within an hour,
        and reply to that email if you have questions.</p>
      </div>
    </div>
    <div class="gg-success-step">
      <div class="gg-success-step-num">2</div>
      <div class="gg-success-step-text">
        <h3>Import Your Workouts</h3>
        <p>The package includes .zwo files for TrainingPeaks, Zwift,
        and Wahoo. Import them into your platform of choice.</p>
      </div>
    </div>
    <div class="gg-success-step">
      <div class="gg-success-step-num">3</div>
      <div class="gg-success-step-text">
        <h3>Read the Training Guide</h3>
        <p>Start with the phase overview. Week 1 is calibration &mdash;
        workouts may feel easy. That's intentional.</p>
      </div>
    </div>
  </div>"""

    crosssell = f"""
  <div class="gg-success-crosssell">
    <h2>Want a Human in Your Corner?</h2>
    <p>Your plan gets you to the start line. Coaching gets you to the
    finish line faster. Weekly adjustments, race-day strategy, and real
    accountability.</p>
    <a href="{SITE_BASE_URL}/coaching/" class="gg-success-cta">EXPLORE COACHING</a>
  </div>"""

    support = f"""
  <div class="gg-success-support">
    <p>Questions? Reply to your delivery email or reach out at
    <a href="mailto:gravelgodcoaching@gmail.com">gravelgodcoaching@gmail.com</a></p>
  </div>"""

    return hero + steps + crosssell + support


# ── Coaching Success ──────────────────────────────────────────


def build_coaching_success() -> str:
    """Content sections for coaching welcome page."""
    hero = f"""
  <div class="gg-success-hero" data-product-type="coaching">
    <div class="gg-success-check">&check;</div>
    <h1>Welcome to Coaching</h1>
    <p>Your subscription is active. Let's get to work.</p>
  </div>"""

    steps = f"""
  <div class="gg-success-steps">
    <h2>WHAT HAPPENS NEXT</h2>
    <div class="gg-success-step">
      <div class="gg-success-step-num">1</div>
      <div class="gg-success-step-text">
        <h3>Fill Out the Intake Form</h3>
        <p>If you haven't already, complete the athlete intake so I have
        everything I need to build your plan.
        <a href="{SITE_BASE_URL}/coaching/apply/">Complete intake &rarr;</a></p>
      </div>
    </div>
    <div class="gg-success-step">
      <div class="gg-success-step-num">2</div>
      <div class="gg-success-step-text">
        <h3>Expect an Email Within 24 Hours</h3>
        <p>I'll review your intake and reach out with initial questions,
        your training philosophy alignment, and a timeline for your
        first structured week.</p>
      </div>
    </div>
    <div class="gg-success-step">
      <div class="gg-success-step-num">3</div>
      <div class="gg-success-step-text">
        <h3>We Train Together</h3>
        <p>Your plan lands in your calendar. I review every session,
        adjust the plan when life happens, and keep you accountable
        through race day.</p>
      </div>
    </div>
  </div>"""

    crosssell = f"""
  <div class="gg-success-crosssell">
    <h2>While You Wait</h2>
    <p>Browse 328 gravel race profiles with course intel, tier ratings,
    and free prep kits for every race in the database.</p>
    <a href="{SITE_BASE_URL}/gravel-races/" class="gg-success-cta">EXPLORE RACES</a>
  </div>"""

    support = f"""
  <div class="gg-success-support">
    <p>Questions about your coaching subscription? Email
    <a href="mailto:gravelgodcoaching@gmail.com">gravelgodcoaching@gmail.com</a></p>
  </div>"""

    return hero + steps + crosssell + support


# ── Consulting Success ────────────────────────────────────────


def build_consulting_success() -> str:
    """Content sections for consulting confirmation page."""
    hero = f"""
  <div class="gg-success-hero" data-product-type="consulting">
    <div class="gg-success-check">&check;</div>
    <h1>Consulting Session Confirmed</h1>
    <p>Payment received. I'll reach out within 24 hours to schedule
    your session.</p>
  </div>"""

    steps = """
  <div class="gg-success-steps">
    <h2>WHAT HAPPENS NEXT</h2>
    <div class="gg-success-step">
      <div class="gg-success-step-num">1</div>
      <div class="gg-success-step-text">
        <h3>Check Your Email</h3>
        <p>I'll send a scheduling link within 24 hours. We'll find a
        time that works for both of us.</p>
      </div>
    </div>
    <div class="gg-success-step">
      <div class="gg-success-step-num">2</div>
      <div class="gg-success-step-text">
        <h3>Prepare Your Questions</h3>
        <p>Think about what you want to cover. Race strategy, training
        philosophy, equipment choices, nutrition &mdash; everything is
        on the table.</p>
      </div>
    </div>
    <div class="gg-success-step">
      <div class="gg-success-step-num">3</div>
      <div class="gg-success-step-text">
        <h3>We Talk</h3>
        <p>Live session, no scripts, no fluff. You'll walk away with
        concrete action items tailored to your situation.</p>
      </div>
    </div>
  </div>"""

    crosssell = f"""
  <div class="gg-success-crosssell">
    <h2>Want Ongoing Support?</h2>
    <p>If you like what you hear in the consult, coaching picks up where
    the conversation leaves off. Weekly plan adjustments, daily feedback,
    and race-day strategy.</p>
    <a href="{SITE_BASE_URL}/coaching/" class="gg-success-cta">EXPLORE COACHING</a>
  </div>"""

    support = f"""
  <div class="gg-success-support">
    <p>Questions? Email
    <a href="mailto:gravelgodcoaching@gmail.com">gravelgodcoaching@gmail.com</a></p>
  </div>"""

    return hero + steps + crosssell + support


# ── Page Assembly ─────────────────────────────────────────────


PAGES = {
    'training-plans-success': {
        'title': 'Plan Confirmed | Gravel God Cycling',
        'description': 'Your custom training plan is being generated.',
        'canonical': '/training-plans/success/',
        'active_nav': 'products',
        'robots': 'noindex, follow',
        'builder': build_training_plan_success,
        'output_path': 'training-plans-success.html',
    },
    'coaching-welcome': {
        'title': 'Welcome to Coaching | Gravel God Cycling',
        'description': 'Your coaching subscription is active.',
        'canonical': '/coaching/welcome/',
        'active_nav': 'services',
        'robots': 'noindex, follow',
        'builder': build_coaching_success,
        'output_path': 'coaching-welcome.html',
    },
    'consulting-confirmed': {
        'title': 'Session Confirmed | Gravel God Cycling',
        'description': 'Your consulting session is confirmed.',
        'canonical': '/consulting/confirmed/',
        'active_nav': 'services',
        'robots': 'noindex, follow',
        'builder': build_consulting_success,
        'output_path': 'consulting-confirmed.html',
    },
}


def generate_success_page(page_key: str,
                          external_assets: dict = None) -> str:
    """Generate a single success page."""
    page = PAGES[page_key]
    canonical_url = SITE_BASE_URL + page['canonical']
    preload = get_preload_hints()

    nav = get_site_header_html(active=page['active_nav'])
    breadcrumb = f'''
  <div class="gg-breadcrumb">
    <a href="{SITE_BASE_URL}/">Home</a>
    <span class="gg-breadcrumb-sep">&rsaquo;</span>
    <span class="gg-breadcrumb-current">{esc(page['title'].split(' | ')[0])}</span>
  </div>'''

    content = page['builder']()
    footer = get_mega_footer_html()
    success_css = build_success_css()
    success_js = build_success_js()

    if external_assets:
        page_css = external_assets['css_tag']
        inline_js = external_assets['js_tag']
    else:
        page_css = get_page_css()
        inline_js = build_inline_js()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(page['title'])}</title>
  <meta name="description" content="{esc(page['description'])}">
  <meta name="robots" content="{page['robots']}">
  <link rel="canonical" href="{esc(canonical_url)}">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  {preload}
  {page_css}
  {success_css}
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA_MEASUREMENT_ID}');</script>
  {get_ab_head_snippet()}
</head>
<body>
<div class="gg-neo-brutalist-page">
  {nav}
  {breadcrumb}
  {content}
  {footer}
</div>
{inline_js}
{success_js}
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(
        description="Generate post-checkout success pages"
    )
    parser.add_argument(
        "--output-dir", default=str(OUTPUT_DIR),
        help="Output directory (default: wordpress/output)"
    )
    parser.add_argument(
        "--page", choices=list(PAGES.keys()),
        help="Generate a single page (default: all)"
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    assets = write_shared_assets(output_dir)

    pages_to_generate = [args.page] if args.page else list(PAGES.keys())

    for page_key in pages_to_generate:
        page_html = generate_success_page(page_key, external_assets=assets)
        page_config = PAGES[page_key]
        output_file = output_dir / page_config['output_path']
        output_file.write_text(page_html, encoding="utf-8")
        print(f"  Generated {output_file.name} ({len(page_html):,} bytes)")

    print(f"Done: {len(pages_to_generate)} success page(s) generated")


if __name__ == "__main__":
    main()
