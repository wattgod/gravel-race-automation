#!/usr/bin/env python3
"""
Generate the Gravel God Consulting landing page in neo-brutalist style.

A brief, conversion-focused page for one-time 60-minute consulting calls.
Covers race selection, training periodization, nutrition, gear, and season
planning. No comparison to other products — this is a standalone service.

Uses brand tokens exclusively — zero hardcoded hex, no border-radius, no
box-shadow, no bounce easing, no entrance animations.

Usage:
    python generate_consulting.py
    python generate_consulting.py --output-dir ./output
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
from shared_header import get_site_header_html, get_site_header_css

OUTPUT_DIR = Path(__file__).parent / "output"

# ── Constants ─────────────────────────────────────────────────

BOOKING_URL = "https://calendly.com/gravelgodcycling/consult"
CONSULTING_PRICE = "$150"
CONSULTING_DURATION = "60 minutes"


def esc(text) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


# ── Page sections ─────────────────────────────────────────────


def build_nav() -> str:
    breadcrumb = f'''<div class="gg-breadcrumb">
  <a href="{SITE_BASE_URL}/">Home</a>
  <span class="gg-breadcrumb-sep">&rsaquo;</span>
  <span class="gg-breadcrumb-current">Consulting</span>
</div>'''
    return get_site_header_html(active="services") + breadcrumb


def build_hero() -> str:
    return f'''<section class="gg-consult-hero" id="hero">
  <div class="gg-consult-hero-inner">
    <h1 class="gg-consult-hero-title">One Call. Clear Answers.</h1>
    <p class="gg-consult-hero-subtitle">A focused {CONSULTING_DURATION} session to cut through the noise on race selection, training structure, nutrition, or season planning. You bring the questions &mdash; I bring the data.</p>
    <div class="gg-consult-hero-price">
      <span class="gg-consult-price-tag">{CONSULTING_PRICE}</span>
      <span class="gg-consult-price-detail">{CONSULTING_DURATION} &middot; 1-on-1 video call</span>
    </div>
    <a href="{BOOKING_URL}" class="gg-consult-btn-gold" data-cta="hero_book">Book a Consult</a>
  </div>
</section>'''


def build_what_you_get() -> str:
    items = [
        (
            "Pre-Call Prep",
            "Fill out a short intake so I review your background, goals, and questions before we talk. No time wasted on basics.",
        ),
        (
            "60-Minute Deep Dive",
            "Live video call covering whatever you need: race selection, periodization, fueling strategy, gear decisions, race-day execution.",
        ),
        (
            "Written Action Plan",
            "Within 48 hours you get a summary email with specific recommendations, resources, and next steps you can act on immediately.",
        ),
    ]
    cards = ""
    for title, desc in items:
        cards += f'''<div class="gg-consult-card">
      <h3 class="gg-consult-card-title">{esc(title)}</h3>
      <p class="gg-consult-card-desc">{esc(desc)}</p>
    </div>
'''
    return f'''<section class="gg-consult-section" id="what-you-get">
  <h2 class="gg-consult-section-title">What You Get</h2>
  <div class="gg-consult-cards">
    {cards}
  </div>
</section>'''


def build_how_it_works() -> str:
    steps = [
        ("1", "Book &amp; Fill Out Intake", "Choose a time that works. A short form captures your background so we hit the ground running."),
        ("2", "We Talk", "60 minutes, video call, no fluff. Bring your training files, race shortlist, or whatever needs sorting out."),
        ("3", "Get Your Plan", "Within 48 hours, a written action plan lands in your inbox. Specific, actionable, referenced to data."),
    ]
    html_steps = ""
    for num, title, desc in steps:
        html_steps += f'''<div class="gg-consult-step">
      <span class="gg-consult-step-num">{num}</span>
      <div class="gg-consult-step-body">
        <h3 class="gg-consult-step-title">{title}</h3>
        <p class="gg-consult-step-desc">{desc}</p>
      </div>
    </div>
'''
    return f'''<section class="gg-consult-section gg-consult-section--alt" id="how-it-works">
  <h2 class="gg-consult-section-title">How It Works</h2>
  <div class="gg-consult-steps">
    {html_steps}
  </div>
</section>'''


def build_topics() -> str:
    topics = [
        "Race selection &mdash; which events match your fitness, goals, and schedule",
        "Season planning &mdash; building a race calendar that makes sense",
        "Training structure &mdash; periodization, volume, intensity distribution",
        "Nutrition &amp; fueling &mdash; race-day strategy and daily habits",
        "Gear &amp; setup &mdash; tire selection, bike fit considerations, kit choices",
        "Race-day execution &mdash; pacing, logistics, contingency planning",
    ]
    items = "\n".join(f'      <li>{t}</li>' for t in topics)
    return f'''<section class="gg-consult-section" id="topics">
  <h2 class="gg-consult-section-title">What We Can Cover</h2>
  <ul class="gg-consult-topics">
{items}
  </ul>
  <p class="gg-consult-topics-note">Not sure if your question fits? It probably does. Book it and ask.</p>
</section>'''


def build_faq() -> str:
    faqs = [
        (
            "Who is this for?",
            "Anyone racing or considering gravel events who wants focused, data-informed guidance without committing to ongoing coaching. Works for first-timers and experienced riders alike.",
        ),
        (
            "What happens after I book?",
            "You get a confirmation email with a short intake form. Fill it out before the call so I can review your situation in advance. The call link arrives 24 hours before your session.",
        ),
        (
            "Can I record the call?",
            "Yes. You are welcome to record for personal reference.",
        ),
        (
            "What if I need more than one session?",
            "Book another one. Each session is standalone &mdash; no packages, no subscriptions, no pressure.",
        ),
    ]
    faq_html = ""
    for q, a in faqs:
        faq_html += f'''<div class="gg-consult-faq-item">
      <button class="gg-consult-faq-q" aria-expanded="false">{esc(q)}</button>
      <div class="gg-consult-faq-a">{esc(a)}</div>
    </div>
'''
    return f'''<section class="gg-consult-section gg-consult-section--alt" id="faq">
  <h2 class="gg-consult-section-title">FAQ</h2>
  <div class="gg-consult-faqs">
    {faq_html}
  </div>
</section>'''


def build_final_cta() -> str:
    return f'''<section class="gg-consult-cta" id="final-cta">
  <div class="gg-consult-cta-inner">
    <h2 class="gg-consult-cta-title">Stop Guessing. Start Racing Smarter.</h2>
    <p class="gg-consult-cta-desc">{CONSULTING_PRICE} &middot; {CONSULTING_DURATION} &middot; Action plan included</p>
    <a href="{BOOKING_URL}" class="gg-consult-btn-gold" data-cta="final_book">Book Your Consult</a>
  </div>
</section>'''


def build_footer() -> str:
    return get_mega_footer_html()


def build_consulting_css() -> str:
    return f'''<style>
/* ── Consulting Page ────────────────────────────────────── */
{get_site_header_css()}

.gg-consult-hero {{
  padding: var(--gg-spacing-2xl) var(--gg-spacing-xl) var(--gg-spacing-xl);
  background: var(--gg-color-warm-paper);
  border-bottom: 3px solid var(--gg-color-dark-brown);
}}
.gg-consult-hero-inner {{
  max-width: 640px;
  margin: 0 auto;
  text-align: center;
}}
.gg-consult-hero-title {{
  font-family: var(--gg-font-editorial);
  font-size: clamp(28px, 5vw, 42px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-md) 0;
  line-height: 1.15;
}}
.gg-consult-hero-subtitle {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-md);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
  margin: 0 0 var(--gg-spacing-lg) 0;
}}
.gg-consult-hero-price {{
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--gg-spacing-xs);
  margin-bottom: var(--gg-spacing-lg);
}}
.gg-consult-price-tag {{
  font-family: var(--gg-font-data);
  font-size: 36px;
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  letter-spacing: var(--gg-letter-spacing-wide);
}}
.gg-consult-price-detail {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
}}

/* ── Buttons ── */
.gg-consult-btn-gold {{
  display: inline-block;
  padding: var(--gg-spacing-sm) var(--gg-spacing-2xl);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-ultra-wide);
  text-transform: uppercase;
  text-decoration: none;
  color: var(--gg-color-dark-brown);
  background: var(--gg-color-light-gold);
  border: 3px solid var(--gg-color-dark-brown);
  transition: background-color var(--gg-transition-hover), border-color var(--gg-transition-hover);
}}
.gg-consult-btn-gold:hover {{
  background-color: var(--gg-color-gold);
  border-color: var(--gg-color-gold);
}}

/* ── Sections ── */
.gg-consult-section {{
  padding: var(--gg-spacing-xl) var(--gg-spacing-xl);
  max-width: 720px;
  margin: 0 auto;
}}
.gg-consult-section--alt {{
  background: var(--gg-color-sand);
}}
.gg-consult-section--alt {{
  max-width: none;
}}
.gg-consult-section--alt > * {{
  max-width: 720px;
  margin-left: auto;
  margin-right: auto;
}}
.gg-consult-section-title {{
  font-family: var(--gg-font-editorial);
  font-size: clamp(22px, 4vw, 30px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-lg) 0;
  text-align: center;
}}

/* ── Cards (What You Get) ── */
.gg-consult-cards {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--gg-spacing-md);
}}
.gg-consult-card {{
  padding: var(--gg-spacing-lg);
  background: var(--gg-color-warm-paper);
  border: 2px solid var(--gg-color-dark-brown);
}}
.gg-consult-card-title {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  color: var(--gg-color-dark-brown);
  text-transform: uppercase;
  margin: 0 0 var(--gg-spacing-sm) 0;
}}
.gg-consult-card-desc {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
  margin: 0;
}}

/* ── Steps (How It Works) ── */
.gg-consult-steps {{
  display: flex;
  flex-direction: column;
  gap: var(--gg-spacing-lg);
}}
.gg-consult-step {{
  display: flex;
  gap: var(--gg-spacing-md);
  align-items: flex-start;
}}
.gg-consult-step-num {{
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--gg-font-data);
  font-size: 20px;
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  background: var(--gg-color-light-gold);
  border: 2px solid var(--gg-color-dark-brown);
}}
.gg-consult-step-title {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  color: var(--gg-color-dark-brown);
  text-transform: uppercase;
  margin: 0 0 var(--gg-spacing-xs) 0;
}}
.gg-consult-step-desc {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
  margin: 0;
}}

/* ── Topics ── */
.gg-consult-topics {{
  list-style: none;
  padding: 0;
  margin: 0 0 var(--gg-spacing-md) 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--gg-spacing-sm);
}}
.gg-consult-topics li {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-dark-brown);
  padding-left: var(--gg-spacing-md);
  border-left: 3px solid var(--gg-color-gold);
}}
.gg-consult-topics-note {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
  text-align: center;
  letter-spacing: var(--gg-letter-spacing-wide);
  margin: 0;
}}

/* ── FAQ ── */
.gg-consult-faqs {{
  display: flex;
  flex-direction: column;
  gap: var(--gg-spacing-sm);
}}
.gg-consult-faq-item {{
  border: 2px solid var(--gg-color-dark-brown);
  background: var(--gg-color-warm-paper);
}}
.gg-consult-faq-q {{
  display: block;
  width: 100%;
  padding: var(--gg-spacing-md) var(--gg-spacing-lg);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  text-align: left;
  background: none;
  border: none;
  cursor: pointer;
  letter-spacing: var(--gg-letter-spacing-wide);
}}
.gg-consult-faq-a {{
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.3s ease;
  padding: 0 var(--gg-spacing-lg);
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
}}
.gg-consult-faq-item.open .gg-consult-faq-a {{
  max-height: 300px;
  padding-bottom: var(--gg-spacing-md);
}}

/* ── Final CTA ── */
.gg-consult-cta {{
  padding: var(--gg-spacing-2xl) var(--gg-spacing-xl);
  text-align: center;
  background: var(--gg-color-dark-brown);
}}
.gg-consult-cta-inner {{
  max-width: 640px;
  margin: 0 auto;
}}
.gg-consult-cta-title {{
  font-family: var(--gg-font-editorial);
  font-size: clamp(22px, 4vw, 30px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-white);
  margin: 0 0 var(--gg-spacing-sm) 0;
}}
.gg-consult-cta-desc {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-tan);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  margin: 0 0 var(--gg-spacing-lg) 0;
}}

/* ── Breadcrumb (shared pattern) ── */
.gg-breadcrumb {{
  padding: var(--gg-spacing-sm) var(--gg-spacing-xl);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  max-width: 960px;
  margin: 0 auto;
  letter-spacing: var(--gg-letter-spacing-wide);
}}
.gg-breadcrumb a {{
  color: var(--gg-color-secondary-brown);
  text-decoration: none;
  transition: color var(--gg-transition-hover);
}}
.gg-breadcrumb a:hover {{ color: var(--gg-color-gold); }}
.gg-breadcrumb-sep {{ margin: 0 var(--gg-spacing-xs); }}

/* ── Responsive ── */
@media (max-width: 768px) {{
  .gg-consult-cards {{ grid-template-columns: 1fr; }}
  .gg-consult-topics {{ grid-template-columns: 1fr; }}
  .gg-consult-hero {{ padding: var(--gg-spacing-xl) var(--gg-spacing-md); }}
  .gg-consult-section {{ padding: var(--gg-spacing-lg) var(--gg-spacing-md); }}
  .gg-consult-cta {{ padding: var(--gg-spacing-xl) var(--gg-spacing-md); }}
}}
</style>'''


def build_consulting_js() -> str:
    return f'''<script>
(function(){{
  /* FAQ accordion */
  document.querySelectorAll('.gg-consult-faq-q').forEach(function(btn){{
    btn.addEventListener('click',function(){{
      var item=btn.parentElement;
      var isOpen=item.classList.contains('open');
      document.querySelectorAll('.gg-consult-faq-item').forEach(function(el){{el.classList.remove('open');el.querySelector('.gg-consult-faq-q').setAttribute('aria-expanded','false')}});
      if(!isOpen){{item.classList.add('open');btn.setAttribute('aria-expanded','true')}}
      if(typeof gtag==='function'){{gtag('event','consulting_faq_open',{{'question':btn.textContent.slice(0,60)}})}}
    }});
  }});
  /* CTA click tracking */
  document.querySelectorAll('[data-cta]').forEach(function(el){{
    el.addEventListener('click',function(){{
      if(typeof gtag==='function'){{gtag('event','consulting_cta_click',{{'cta_name':el.getAttribute('data-cta')}})}}
    }});
  }});
  /* Scroll depth */
  if('IntersectionObserver' in window){{
    var fired={{}};
    var map={{'hero':'0_hero','what-you-get':'25_what_you_get','how-it-works':'50_how_it_works','faq':'75_faq','final-cta':'100_final_cta'}};
    var obs=new IntersectionObserver(function(entries){{
      entries.forEach(function(e){{
        if(e.isIntersecting&&!fired[e.target.id]){{
          fired[e.target.id]=true;
          if(typeof gtag==='function'){{gtag('event','consulting_scroll_depth',{{'section':map[e.target.id]||e.target.id}})}}
        }}
      }});
    }},{{'threshold':0.3}});
    Object.keys(map).forEach(function(id){{var el=document.getElementById(id);if(el)obs.observe(el)}});
  }}
  /* Page view */
  if(typeof gtag==='function'){{gtag('event','consulting_page_view')}}
}})();
</script>'''


def build_jsonld() -> str:
    return f'''<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Service",
  "name": "Gravel Race Consulting",
  "provider": {{
    "@type": "Organization",
    "name": "Gravel God Cycling",
    "url": "{SITE_BASE_URL}"
  }},
  "description": "One-on-one consulting for gravel race selection, training structure, nutrition, and season planning.",
  "offers": {{
    "@type": "Offer",
    "price": "150",
    "priceCurrency": "USD",
    "description": "60-minute 1-on-1 video consultation with written action plan"
  }},
  "url": "{SITE_BASE_URL}/consulting/"
}}
</script>'''


def generate_consulting_page(external_assets: dict = None) -> str:
    canonical_url = f"{SITE_BASE_URL}/consulting/"

    nav = build_nav()
    hero = build_hero()
    what = build_what_you_get()
    topics = build_topics()
    how = build_how_it_works()
    faq = build_faq()
    final_cta = build_final_cta()
    footer = build_footer()
    consulting_css = build_consulting_css()
    consulting_js = build_consulting_js()
    jsonld = build_jsonld()

    if external_assets:
        page_css = external_assets['css_tag']
        inline_js = external_assets['js_tag']
    else:
        page_css = get_page_css()
        inline_js = build_inline_js()

    meta_desc = "60-minute gravel race consulting call. Race selection, training structure, nutrition, and season planning. $150 with written action plan included."

    og_tags = f'''<meta property="og:title" content="Consulting | Gravel God">
  <meta property="og:description" content="60-minute gravel race consulting. Race selection, training, nutrition, and season planning.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="Consulting | Gravel God">
  <meta name="twitter:description" content="60-minute gravel race consulting. Race selection, training, nutrition, and season planning.">'''

    preload = get_preload_hints()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Consulting | Gravel God</title>
  <meta name="description" content="{esc(meta_desc)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical_url)}">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  {preload}
  {og_tags}
  {jsonld}
  {page_css}
  {consulting_css}
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA_MEASUREMENT_ID}');</script>
  {get_ab_head_snippet()}
</head>
<body>

<div class="gg-neo-brutalist-page">
  {nav}

  {hero}

  {what}

  {topics}

  {how}

  {faq}

  {final_cta}

  {footer}
</div>

{inline_js}
{consulting_js}

</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate Gravel God consulting page")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    assets = write_shared_assets(output_dir)

    html_content = generate_consulting_page(external_assets=assets)
    output_file = output_dir / "consulting.html"
    output_file.write_text(html_content, encoding="utf-8")
    print(f"Generated {output_file} ({len(html_content):,} bytes)")


if __name__ == "__main__":
    main()
