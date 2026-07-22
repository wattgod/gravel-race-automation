#!/usr/bin/env python3
"""
Generate the articles index page at articles/index.html.

Lists all published articles (category "article") from blog-index.json.
Includes shared header, footer, GA4, and brand tokens.

Usage:
    python wordpress/generate_articles_index.py
"""

import json
import html as html_mod
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "wordpress" / "output"
INDEX_JSON = PROJECT_ROOT / "web" / "blog-index.json"
SITE_URL = "https://gravelgodcycling.com"

# Import shared components
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from brand_tokens import get_tokens_css, get_font_face_css, get_ga4_head_snippet
from shared_header import get_site_header_html, get_site_header_css, get_site_header_js
from shared_footer import get_mega_footer_html, get_mega_footer_css
from cookie_consent import get_consent_banner_html


def _esc(text):
    return html_mod.escape(str(text)) if text else ""


def generate_articles_index():
    """Generate the articles index HTML page."""
    today_str = date.today().strftime("%B %d, %Y")

    # Load articles from blog-index.json
    articles = []
    if INDEX_JSON.exists():
        try:
            entries = json.loads(INDEX_JSON.read_text())
            articles = [e for e in entries if e.get("category") == "article"]
        except (json.JSONDecodeError, KeyError):
            pass

    # Render article cards
    cards_html = ""
    for entry in articles:
        title = _esc(entry.get("title", ""))
        excerpt = _esc(entry.get("excerpt", ""))
        url = _esc(entry.get("url", ""))
        date_str = _esc(entry.get("date", ""))
        og_img = entry.get("og_image", "")
        img_html = ""
        if og_img:
            img_html = f'<img src="{_esc(og_img)}" alt="" class="gg-ai-card-img" loading="lazy">'
        cards_html += f"""
      <a href="{url}" class="gg-ai-card">
        {img_html}
        <div class="gg-ai-card-body">
          <h3 class="gg-ai-card-title">{title}</h3>
          <div class="gg-ai-card-date">{date_str}</div>
          <p class="gg-ai-card-excerpt">{excerpt}</p>
        </div>
      </a>"""

    if not cards_html:
        cards_html = '<p class="gg-ai-empty">More articles coming soon.</p>'

    tokens_css = get_tokens_css()
    fonts_css = get_font_face_css("/race/assets/fonts")
    header_css = get_site_header_css()
    footer_css = get_mega_footer_css()
    header_html = get_site_header_html(active="articles")
    footer_html = get_mega_footer_html()
    ga4 = get_ga4_head_snippet()
    consent = get_consent_banner_html()
    header_js = '<script>' + get_site_header_js() + '</script>'

    page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Articles — Gravel God Cycling</title>
  <meta name="description" content="In-depth articles on gravel cycling training, nutrition, and race strategy from Gravel God.">
  <meta property="og:title" content="Articles — Gravel God Cycling">
  <meta property="og:description" content="In-depth articles on gravel cycling training, nutrition, and race strategy.">
  <meta property="og:url" content="{SITE_URL}/articles/">
  <link rel="canonical" href="{SITE_URL}/articles/">
  <meta name="robots" content="index, follow">
  {ga4}
  <style>
{fonts_css}
{tokens_css}
{header_css}
{footer_css}

* {{ margin: 0; padding: 0; box-sizing: border-box; border-radius: 0 !important; box-shadow: none !important; }}
body {{ font-family: var(--gg-font-data); background: var(--gg-color-warm-paper); color: var(--gg-color-dark-brown); line-height: 1.6; }}

.gg-ai-page {{ max-width: 960px; margin: 0 auto; padding: 0 20px; }}

/* Hero */
.gg-ai-hero {{
  padding: 48px 32px;
  border-bottom: 2px solid var(--gg-color-gold);
  margin-bottom: 32px;
}}
.gg-ai-hero h1 {{
  font-family: var(--gg-font-editorial);
  font-size: 42px;
  font-weight: 700;
  line-height: 1.05;
  letter-spacing: -0.5px;
  margin: 0 0 8px;
}}
.gg-ai-hero-sub {{
  font-family: var(--gg-font-data);
  font-size: 13px;
  color: var(--gg-color-secondary-brown);
  letter-spacing: 1px;
  text-transform: uppercase;
}}

/* Article cards */
.gg-ai-grid {{
  display: grid;
  gap: 24px;
  margin-bottom: 48px;
}}
.gg-ai-card {{
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 20px;
  border: 1px solid var(--gg-color-tan);
  background: var(--gg-color-warm-paper);
  text-decoration: none;
  color: inherit;
  transition: border-color 0.2s;
}}
.gg-ai-card:hover {{
  border-color: var(--gg-color-gold);
}}
.gg-ai-card-img {{
  width: 200px;
  height: 140px;
  object-fit: cover;
  display: block;
}}
.gg-ai-card-body {{
  padding: 16px 16px 16px 0;
}}
.gg-ai-card-title {{
  font-family: var(--gg-font-editorial);
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
  margin-bottom: 4px;
}}
.gg-ai-card-date {{
  font-family: var(--gg-font-data);
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: 8px;
}}
.gg-ai-card-excerpt {{
  font-family: var(--gg-font-editorial);
  font-size: 14px;
  line-height: 1.5;
  color: var(--gg-color-secondary-brown);
}}
.gg-ai-empty {{
  font-family: var(--gg-font-data);
  font-size: 14px;
  color: var(--gg-color-secondary-brown);
  padding: 32px 0;
}}

@media (max-width: 600px) {{
  .gg-ai-hero h1 {{ font-size: 28px; }}
  .gg-ai-card {{ grid-template-columns: 1fr; }}
  .gg-ai-card-img {{ width: 100%; height: 180px; }}
  .gg-ai-card-body {{ padding: 12px 16px 16px; }}
}}
  </style>
</head>
<body>
{header_html}
<div class="gg-ai-page">
  <section class="gg-ai-hero">
    <h1>Hot Takes</h1>
    <p class="gg-ai-hero-sub">In-depth articles on training, racing, and not being slow</p>
  </section>
  <div class="gg-ai-grid">
    {cards_html}
  </div>
</div>
{footer_html}
{header_js}
{consent}
</body>
</html>"""

    out_path = OUTPUT_DIR / "articles" / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page_html, encoding="utf-8")
    print(f"Generated {out_path} ({len(articles)} articles)")


if __name__ == "__main__":
    generate_articles_index()
