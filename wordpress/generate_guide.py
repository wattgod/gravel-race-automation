#!/usr/bin/env python3
"""
Generate the Gravel God Interactive Training Guide page.

Reads structured content from guide/gravel-guide-content.json and produces
a standalone HTML page with interactive blocks (accordions, tabs, timelines,
process lists, data tables, callouts, knowledge checks), a content gate
after Chapter 3, and CTAs for Substack, training plans, and coaching.

Follows the same pattern as generate_methodology.py — imports shared constants,
defines page-specific builders, outputs standalone HTML.

Usage:
    python generate_guide.py
    python generate_guide.py --inline
    python generate_guide.py --output-dir ./output
"""

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Import shared constants from the race page generator
sys.path.insert(0, str(Path(__file__).parent))
from generate_neo_brutalist import (
    SITE_BASE_URL,
    SUBSTACK_EMBED,
    SUBSTACK_URL,
    COACHING_URL,
    TRAINING_PLANS_URL,
)

GA4_MEASUREMENT_ID = "G-EJJZ9T6M52"

GUIDE_DIR = Path(__file__).parent.parent / "guide"
CONTENT_JSON = GUIDE_DIR / "gravel-guide-content.json"
OUTPUT_DIR = Path(__file__).parent / "output"


def esc(text) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


# ── Content Loading ──────────────────────────────────────────


def load_content() -> dict:
    """Load and return guide content JSON."""
    return json.loads(CONTENT_JSON.read_text(encoding="utf-8"))


# ── Markdown helpers ─────────────────────────────────────────


def _md_inline(text: str) -> str:
    """Apply markdown-lite inline formatting (bold, italic, links)."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
    return text


def _md_block(content: str) -> str:
    """Convert escaped content into HTML paragraphs and lists."""
    content = _md_inline(content)
    lines = content.split('\n')
    result = []
    in_list = False
    list_type = None  # 'ul' or 'ol'
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('- '):
            if not in_list:
                result.append('<ul class="gg-guide-list">')
                in_list = True
                list_type = 'ul'
            result.append(f'<li>{stripped[2:]}</li>')
        elif re.match(r'^\d+\.\s', stripped):
            if not in_list:
                result.append('<ol class="gg-guide-list">')
                in_list = True
                list_type = 'ol'
            # Strip the number prefix (e.g. "1. ", "12. ")
            li_text = re.sub(r'^\d+\.\s', '', stripped)
            result.append(f'<li>{li_text}</li>')
        else:
            if in_list:
                result.append(f'</{list_type}>')
                in_list = False
                list_type = None
            if stripped:
                result.append(f'<p>{stripped}</p>')
    if in_list:
        result.append(f'</{list_type}>')
    return '\n'.join(result)


# ── Block Renderers ──────────────────────────────────────────


def render_prose(block: dict) -> str:
    """Render a prose block — paragraphs with markdown-lite formatting."""
    return _md_block(esc(block["content"]))


def render_data_table(block: dict) -> str:
    """Render a data table block."""
    caption = esc(block.get("caption", ""))
    headers = block["headers"]
    rows = block["rows"]

    header_cells = ''.join(f'<th>{esc(h)}</th>' for h in headers)
    body_rows = []
    for row in rows:
        cells = ''.join(f'<td>{esc(c)}</td>' for c in row)
        body_rows.append(f'<tr>{cells}</tr>')

    caption_html = f'<caption>{caption}</caption>' if caption else ''
    return f'''<div class="gg-guide-table-wrap">
      <table class="gg-guide-table">
        {caption_html}
        <thead><tr>{header_cells}</tr></thead>
        <tbody>{''.join(body_rows)}</tbody>
      </table>
    </div>'''


def render_accordion(block: dict) -> str:
    """Render an accordion block with collapsible items."""
    items_html = []
    for idx, item in enumerate(block["items"]):
        title = esc(item["title"])
        content_html = _md_block(esc(item["content"]))
        panel_id = f"accordion-panel-{hashlib.md5(title.encode()).hexdigest()[:8]}-{idx}"

        items_html.append(f'''<div class="gg-guide-accordion-item">
        <button class="gg-guide-accordion-trigger" aria-expanded="false" aria-controls="{panel_id}">
          <span>{title}</span>
          <span class="gg-guide-accordion-icon" aria-hidden="true">+</span>
        </button>
        <div class="gg-guide-accordion-body" id="{panel_id}">{content_html}</div>
      </div>''')
    return '\n'.join(items_html)


def render_tabs(block: dict) -> str:
    """Render a tabbed content block."""
    tabs = block["tabs"]
    tab_id = f"tabs-{hashlib.md5(tabs[0]['label'].encode()).hexdigest()[:8]}"

    tab_buttons = []
    tab_panels = []
    for i, tab in enumerate(tabs):
        active = ' gg-guide-tab--active' if i == 0 else ''
        hidden = '' if i == 0 else ' style="display:none"'
        selected = 'true' if i == 0 else 'false'
        label = esc(tab["label"])
        title = esc(tab.get("title", tab["label"]))
        content_html = _md_block(esc(tab["content"]))
        panel_id = f"{tab_id}-{i}"
        btn_id = f"{tab_id}-btn-{i}"

        tab_buttons.append(
            f'<button class="gg-guide-tab{active}" role="tab" '
            f'aria-selected="{selected}" aria-controls="{panel_id}" '
            f'id="{btn_id}" data-tab="{panel_id}">{label}</button>'
        )
        tab_panels.append(
            f'<div class="gg-guide-tab-panel" role="tabpanel" '
            f'aria-labelledby="{btn_id}" id="{panel_id}"{hidden}>'
            f'<h4 class="gg-guide-tab-title">{title}</h4>'
            f'{content_html}</div>'
        )

    return f'''<div class="gg-guide-tabs" data-tabgroup="{tab_id}">
      <div class="gg-guide-tab-bar" role="tablist">{''.join(tab_buttons)}</div>
      <div class="gg-guide-tab-content">{''.join(tab_panels)}</div>
    </div>'''


def render_timeline(block: dict) -> str:
    """Render a timeline block."""
    title = esc(block.get("title", ""))
    steps = block["steps"]
    steps_html = []
    for i, step in enumerate(steps):
        label = esc(step["label"])
        content = _md_inline(esc(step["content"]))
        paras = [f'<p>{p.strip()}</p>' for p in content.split('\n') if p.strip()]
        steps_html.append(f'''<div class="gg-guide-timeline-step">
        <div class="gg-guide-timeline-marker">{i + 1}</div>
        <div class="gg-guide-timeline-content">
          <h4 class="gg-guide-timeline-label">{label}</h4>
          {''.join(paras)}
        </div>
      </div>''')

    title_html = f'<h3 class="gg-guide-timeline-title">{title}</h3>' if title else ''
    return f'''<div class="gg-guide-timeline">
      {title_html}
      {''.join(steps_html)}
    </div>'''


def render_process_list(block: dict) -> str:
    """Render a numbered process list with labels and details."""
    items = block["items"]
    items_html = []
    for i, item in enumerate(items):
        label = esc(item["label"])
        detail = _md_inline(esc(item["detail"]))
        pct = item.get("percentage")
        pct_html = f'<span class="gg-guide-process-pct">{pct}%</span>' if pct is not None else ''
        items_html.append(f'''<div class="gg-guide-process-item">
        <div class="gg-guide-process-num">{i + 1}</div>
        <div class="gg-guide-process-body">
          <span class="gg-guide-process-label">{label}</span>{pct_html}
          <p class="gg-guide-process-detail">{detail}</p>
        </div>
      </div>''')
    return f'<div class="gg-guide-process-list">{chr(10).join(items_html)}</div>'


def render_callout(block: dict) -> str:
    """Render a callout/quote block."""
    style = block.get("style", "highlight")
    content = _md_inline(esc(block["content"]))
    paras = [f'<p>{p.strip()}</p>' for p in content.split('\n') if p.strip()]
    return f'<div class="gg-guide-callout gg-guide-callout--{esc(style)}">{"".join(paras)}</div>'


def render_knowledge_check(block: dict) -> str:
    """Render a knowledge check mini-quiz."""
    question = esc(block["question"])
    explanation = esc(block["explanation"])
    options_html = []
    for i, opt in enumerate(block["options"]):
        text = esc(opt["text"])
        correct = "true" if opt["correct"] else "false"
        options_html.append(
            f'<button class="gg-guide-kc-option" data-correct="{correct}">{text}</button>'
        )
    return f'''<div class="gg-guide-knowledge-check">
      <div class="gg-guide-kc-label">KNOWLEDGE CHECK</div>
      <p class="gg-guide-kc-question">{question}</p>
      <div class="gg-guide-kc-options">{"".join(options_html)}</div>
      <div class="gg-guide-kc-explanation" style="display:none">
        <p>{explanation}</p>
      </div>
    </div>'''


# Block type -> renderer dispatch
BLOCK_RENDERERS = {
    "prose": render_prose,
    "data_table": render_data_table,
    "accordion": render_accordion,
    "tabs": render_tabs,
    "timeline": render_timeline,
    "process_list": render_process_list,
    "callout": render_callout,
    "knowledge_check": render_knowledge_check,
}


def render_block(block: dict) -> str:
    """Route a block to its renderer."""
    renderer = BLOCK_RENDERERS.get(block["type"])
    if not renderer:
        return f'<!-- unknown block type: {esc(block["type"])} -->'
    return renderer(block)


# ── Page Sections ────────────────────────────────────────────


def build_nav() -> str:
    return f'''<nav class="gg-site-nav">
    <div class="gg-site-nav-inner">
      <a href="{SITE_BASE_URL}/" class="gg-site-nav-brand">GRAVEL GOD</a>
      <a href="{SITE_BASE_URL}/gravel-races/" class="gg-site-nav-link">ALL RACES</a>
      <a href="{SITE_BASE_URL}/race/methodology/" class="gg-site-nav-link">HOW WE RATE</a>
      <a href="{SITE_BASE_URL}/guide/" class="gg-site-nav-link" style="color:#1A8A82">GUIDE</a>
    </div>
    <div class="gg-breadcrumb">
      <a href="{SITE_BASE_URL}/">Home</a>
      <span class="gg-breadcrumb-sep">&rsaquo;</span>
      <span class="gg-breadcrumb-current">Training Guide</span>
    </div>
  </nav>'''


def build_hero(content: dict) -> str:
    title = esc(content["title"])
    subtitle = esc(content["subtitle"])
    return f'''<div class="gg-hero">
    <div class="gg-hero-tier" style="background:#1A8A82">FREE GUIDE</div>
    <h1 data-text="{title}">{title}</h1>
    <p class="gg-hero-tagline">{subtitle}</p>
  </div>'''


def build_progress_bar() -> str:
    return '<div class="gg-guide-progress" id="gg-guide-progress"><div class="gg-guide-progress-bar" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100" aria-label="Reading progress"></div></div>'


def build_chapter_nav(chapters: list) -> str:
    items = []
    for ch in chapters:
        num = f'{ch["number"]:02d}'
        lock = ' gg-guide-chapnav-item--locked' if ch["gated"] else ''
        icon = '<span class="gg-guide-chapnav-lock" aria-hidden="true">&#128274;</span>' if ch["gated"] else ''
        items.append(
            f'<a href="#{esc(ch["id"])}" class="gg-guide-chapnav-item{lock}" '
            f'data-chapter="{esc(ch["id"])}" role="button" tabindex="0" '
            f'aria-label="Chapter {ch["number"]}: {esc(ch["title"])}">'
            f'{num}{icon}</a>'
        )
    return f'''<div class="gg-guide-chapnav" id="gg-guide-chapnav" aria-label="Chapter navigation">
    {"".join(items)}
  </div>'''


def build_chapter(chapter: dict) -> str:
    """Build a full chapter section."""
    num = chapter["number"]
    ch_id = chapter["id"]
    title = esc(chapter["title"])
    subtitle = esc(chapter.get("subtitle", ""))
    gated_class = ' gg-guide-gated' if chapter["gated"] else ''

    subtitle_html = f'<p class="gg-guide-chapter-subtitle">{subtitle}</p>' if subtitle else ''

    colors = ['#59473c', '#000', '#1A8A82', '#59473c', '#000', '#1A8A82', '#59473c', '#000']
    bg = colors[(num - 1) % len(colors)]

    sections_html = []
    for section in chapter["sections"]:
        sec_title = section.get("title", "")
        sec_title_html = f'<h3 class="gg-guide-section-title">{esc(sec_title)}</h3>' if sec_title else ''
        blocks_html = '\n'.join(render_block(b) for b in section["blocks"])
        sections_html.append(f'''<div class="gg-guide-section" id="{esc(section["id"])}">
        {sec_title_html}
        {blocks_html}
      </div>''')

    return f'''<div class="gg-guide-chapter{gated_class}" id="{esc(ch_id)}" data-chapter="{num}">
    <div class="gg-guide-chapter-hero" style="background:{bg}">
      <span class="gg-guide-chapter-num">CHAPTER {num:02d}</span>
      <h2 class="gg-guide-chapter-title">{title}</h2>
      {subtitle_html}
    </div>
    <div class="gg-guide-chapter-body">
      {"".join(sections_html)}
    </div>
  </div>'''


def build_cta_newsletter() -> str:
    return f'''<div class="gg-guide-cta gg-guide-cta--newsletter">
    <div class="gg-guide-cta-inner">
      <span class="gg-guide-cta-kicker">STAY IN THE LOOP</span>
      <h3>Get Race Intel, Training Tips & New Guides</h3>
      <p>Join the Gravel God newsletter. No spam. Just useful gravel content.</p>
      <iframe src="{SUBSTACK_EMBED}" width="100%" height="150" style="border:none;background:transparent" frameborder="0" scrolling="no" loading="lazy"></iframe>
    </div>
  </div>'''


def build_cta_training() -> str:
    return f'''<div class="gg-guide-cta gg-guide-cta--training">
    <div class="gg-guide-cta-inner">
      <span class="gg-guide-cta-kicker">READY TO TRAIN?</span>
      <h3>Custom Gravel Training Plan</h3>
      <p>Race-specific. Built for you by a coach. $15/week, capped at $199.</p>
      <ul>
        <li>Structured workouts pushed to your device</li>
        <li>30+ page custom training guide</li>
        <li>Heat &amp; altitude protocols</li>
        <li>Nutrition plan</li>
        <li>Strength training</li>
      </ul>
      <a href="{TRAINING_PLANS_URL}" class="gg-guide-btn gg-guide-btn--primary">BUILD MY PLAN</a>
    </div>
  </div>'''


def build_cta_coaching() -> str:
    return f'''<div class="gg-guide-cta gg-guide-cta--coaching">
    <div class="gg-guide-cta-inner">
      <span class="gg-guide-cta-kicker">NEXT LEVEL</span>
      <h3>1:1 Gravel Coaching</h3>
      <p>For athletes who want individualized programming, weekly check-ins, and race-specific preparation. Limited spots available.</p>
      <a href="{COACHING_URL}" class="gg-guide-btn gg-guide-btn--secondary">APPLY FOR COACHING</a>
    </div>
  </div>'''


def build_cta_finale() -> str:
    """Build the 3-CTA finale grid after the final chapter."""
    return f'''<div class="gg-guide-finale" id="gg-guide-finale">
    <h2 class="gg-guide-finale-title">What's Your Next Move?</h2>
    <div class="gg-guide-finale-grid">
      <div class="gg-guide-finale-card gg-guide-finale-card--newsletter">
        <span class="gg-guide-finale-kicker">STAY CONNECTED</span>
        <h3>Newsletter</h3>
        <p>Race intel, training tips, and new guides.</p>
        <a href="{SUBSTACK_URL}" class="gg-guide-btn gg-guide-btn--primary" target="_blank">SUBSCRIBE FREE</a>
      </div>
      <div class="gg-guide-finale-card gg-guide-finale-card--training">
        <span class="gg-guide-finale-kicker">READY TO TRAIN</span>
        <h3>Training Plan</h3>
        <p>Custom plans built for your race and ability.</p>
        <a href="{TRAINING_PLANS_URL}" class="gg-guide-btn gg-guide-btn--primary">BUILD MY PLAN</a>
      </div>
      <div class="gg-guide-finale-card gg-guide-finale-card--coaching">
        <span class="gg-guide-finale-kicker">GO FURTHER</span>
        <h3>1:1 Coaching</h3>
        <p>Individualized programming and race prep.</p>
        <a href="{COACHING_URL}" class="gg-guide-btn gg-guide-btn--secondary">APPLY</a>
      </div>
    </div>
  </div>'''


def build_gate() -> str:
    """Build the content gate overlay between Ch 3 and Ch 4."""
    return f'''<div class="gg-guide-gate" id="gg-guide-gate">
    <div class="gg-guide-gate-inner">
      <span class="gg-guide-gate-kicker">CHAPTERS 4-8 ARE LOCKED</span>
      <h2>Unlock the Full Guide</h2>
      <p>You've read the free chapters. The remaining 5 chapters cover workout execution, nutrition, mental training &amp; race tactics, race week protocol, and post-race recovery.</p>
      <p>Subscribe to the Gravel God newsletter to unlock everything instantly.</p>
      <iframe src="{SUBSTACK_EMBED}" width="100%" height="150" style="border:none;background:transparent" frameborder="0" scrolling="no" loading="lazy"></iframe>
      <button class="gg-guide-gate-bypass" id="gg-guide-gate-bypass">I already subscribed &mdash; unlock</button>
    </div>
  </div>'''


def build_footer() -> str:
    year = datetime.now().year
    return f'''<div class="gg-footer">
    <p class="gg-footer-disclaimer">This guide represents our editorial views on gravel racing training. Consult a physician before starting any exercise program. We are not affiliated with any race organizer, governing body, or equipment manufacturer. Training plans and coaching are separate paid services.</p>
    <p style="margin-top:12px;font-size:11px;color:#666">&copy; {year} Gravel God Cycling. All rights reserved.</p>
  </div>'''


CTA_BUILDERS = {
    "newsletter": build_cta_newsletter,
    "training_plans": build_cta_training,
    "coaching": build_cta_coaching,
    "finale": build_cta_finale,
}


def build_jsonld(content: dict) -> str:
    """Build Article + BreadcrumbList JSON-LD."""
    canonical = f"{SITE_BASE_URL}/guide/"
    # Use file mtime for dateModified, current date for datePublished
    try:
        mtime = CONTENT_JSON.stat().st_mtime
        date_modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except OSError:
        date_modified = datetime.now().strftime("%Y-%m-%d")
    date_published = "2025-06-01"
    og_image = f"{SITE_BASE_URL}/wp-content/uploads/gravel-god-og.png"

    article = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": content["title"],
        "description": content["meta_description"],
        "url": canonical,
        "datePublished": date_published,
        "dateModified": date_modified,
        "image": og_image,
        "author": {
            "@type": "Organization",
            "name": "Gravel God Cycling",
            "url": SITE_BASE_URL,
        },
        "publisher": {
            "@type": "Organization",
            "name": "Gravel God Cycling",
            "url": SITE_BASE_URL,
        },
        "isPartOf": {
            "@type": "WebSite",
            "name": "Gravel God Cycling",
            "url": SITE_BASE_URL,
        },
    }
    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": SITE_BASE_URL,
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": "Training Guide",
                "item": canonical,
            },
        ],
    }
    parts = [
        f'<script type="application/ld+json">\n{json.dumps(article, indent=2)}\n</script>',
        f'<script type="application/ld+json">\n{json.dumps(breadcrumb, indent=2)}\n</script>',
    ]
    return '\n'.join(parts)


# ── CSS ──────────────────────────────────────────────────────


def build_guide_css() -> str:
    """Return all guide-specific CSS."""
    return '''/* ── Guide Progress Bar ── */
.gg-guide-progress{position:fixed;top:0;left:0;width:100%;height:3px;z-index:1001;background:transparent}
.gg-guide-progress-bar{height:100%;width:0%;background:#1A8A82;transition:width 0.15s linear}

/* ── Chapter Nav ── */
.gg-guide-chapnav{position:sticky;top:3px;z-index:1000;background:#000;display:flex;justify-content:center;gap:0;border:3px solid #000;margin-bottom:32px}
.gg-guide-chapnav-item{color:#d4c5b9;text-decoration:none;font-size:12px;font-weight:700;letter-spacing:1px;padding:10px 16px;transition:all 0.2s;display:flex;align-items:center;gap:4px;border-right:1px solid #333}
.gg-guide-chapnav-item:last-child{border-right:none}
.gg-guide-chapnav-item:hover{color:#fff;background:#333}
.gg-guide-chapnav-item--active{color:#fff;background:#1A8A82}
.gg-guide-chapnav-item--locked .gg-guide-chapnav-lock{font-size:9px;opacity:0.5}
.gg-guide-chapnav-item--unlocked .gg-guide-chapnav-lock{display:none}

/* ── Chapter ── */
.gg-guide-chapter{margin-bottom:40px;border:3px solid #000;background:#fff}
.gg-guide-chapter-hero{padding:48px 32px;color:#fff;position:relative}
.gg-guide-chapter-num{display:block;font-size:11px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:rgba(255,255,255,0.85);margin-bottom:8px}
.gg-guide-chapter-title{font-size:32px;font-weight:700;text-transform:uppercase;letter-spacing:2px;line-height:1.2;margin:0;color:#fff}
.gg-guide-chapter-subtitle{font-size:14px;color:rgba(255,255,255,0.7);margin-top:8px}
.gg-guide-chapter-body{padding:32px 24px}

/* ── Gating ── */
.gg-guide-gated{display:none}
.gg-guide-unlocked .gg-guide-gated{display:block}
.gg-guide-unlocked .gg-guide-gate{display:none}
.gg-guide-unlocked .gg-guide-chapnav-item--locked .gg-guide-chapnav-lock{display:none}

/* ── Gate Overlay ── */
.gg-guide-gate{background:#59473c;color:#fff;padding:48px 32px;border:3px solid #000;margin-bottom:40px;text-align:center}
.gg-guide-gate-inner{max-width:600px;margin:0 auto}
.gg-guide-gate-kicker{display:inline-block;background:#000;color:#fff;padding:4px 12px;font-size:10px;font-weight:700;letter-spacing:3px;margin-bottom:16px}
.gg-guide-gate h2{font-size:28px;text-transform:uppercase;letter-spacing:2px;margin:12px 0}
.gg-guide-gate p{font-size:13px;color:#d4c5b9;line-height:1.6;margin-bottom:16px}
.gg-guide-gate-bypass{background:none;border:none;color:#8c7568;font-size:12px;cursor:pointer;text-decoration:underline;margin-top:16px;font-family:'Sometype Mono',monospace}
.gg-guide-gate-bypass:hover{color:#d4c5b9}

/* ── Section ── */
.gg-guide-section{margin-bottom:32px}
.gg-guide-section-title{font-size:18px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;margin:0 0 16px;padding-bottom:8px;border-bottom:2px solid #000;color:#59473c}

/* ── Prose ── */
.gg-guide-chapter-body p{font-size:14px;line-height:1.7;margin:0 0 14px;color:#222}
.gg-guide-chapter-body strong{font-weight:700}
.gg-guide-list{padding-left:20px;margin:0 0 16px;font-size:14px;line-height:1.7}
.gg-guide-list li{margin-bottom:6px}

/* ── Data Table ── */
.gg-guide-table-wrap{overflow-x:auto;margin:0 0 20px}
.gg-guide-table{width:100%;border-collapse:collapse;font-size:12px;border:2px solid #000}
.gg-guide-table caption{text-align:left;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;padding:8px 12px;background:#f5f0eb;border:2px solid #000;border-bottom:none;color:#59473c}
.gg-guide-table th{background:#59473c;color:#fff;padding:8px 12px;text-align:left;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;border:1px solid #000}
.gg-guide-table td{padding:8px 12px;border:1px solid #ddd;vertical-align:top}
.gg-guide-table tbody tr:nth-child(even){background:#faf5f0}

/* ── Accordion ── */
.gg-guide-accordion-item{border:2px solid #000;margin-bottom:8px}
.gg-guide-accordion-trigger{display:flex;justify-content:space-between;align-items:center;width:100%;padding:12px 16px;background:#f5f0eb;border:none;cursor:pointer;font-family:'Sometype Mono',monospace;font-size:13px;font-weight:700;text-align:left;color:#000}
.gg-guide-accordion-trigger:hover{background:#e8dfd7}
.gg-guide-accordion-icon{font-size:18px;font-weight:700;transition:transform 0.2s}
.gg-guide-accordion-trigger[aria-expanded="true"] .gg-guide-accordion-icon{transform:rotate(45deg)}
.gg-guide-accordion-body{display:none;padding:16px;border-top:2px solid #000}
.gg-guide-accordion-trigger[aria-expanded="true"]+.gg-guide-accordion-body{display:block}

/* ── Tabs ── */
.gg-guide-tabs{border:2px solid #000;margin:0 0 20px}
.gg-guide-tab-bar{display:flex;flex-wrap:wrap;background:#000;gap:0}
.gg-guide-tab{padding:10px 16px;background:#333;color:#d4c5b9;border:none;cursor:pointer;font-family:'Sometype Mono',monospace;font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;border-right:1px solid #555;transition:all 0.2s}
.gg-guide-tab:last-child{border-right:none}
.gg-guide-tab:hover{background:#555;color:#fff}
.gg-guide-tab--active{background:#1A8A82;color:#fff}
.gg-guide-tab-panel{padding:20px}
.gg-guide-tab-title{font-size:15px;font-weight:700;margin:0 0 12px;color:#59473c;text-transform:uppercase;letter-spacing:1px}

/* ── Timeline ── */
.gg-guide-timeline{margin:0 0 24px;padding-left:20px}
.gg-guide-timeline-title{font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:2px;margin:0 0 16px;color:#59473c}
.gg-guide-timeline-step{display:flex;gap:16px;margin-bottom:20px;position:relative}
.gg-guide-timeline-step:not(:last-child)::before{content:'';position:absolute;left:15px;top:32px;bottom:-20px;width:2px;background:#ddd}
.gg-guide-timeline-marker{width:32px;height:32px;min-width:32px;background:#1A8A82;color:#fff;font-size:13px;font-weight:700;display:flex;align-items:center;justify-content:center;position:relative;z-index:1}
.gg-guide-timeline-content{flex:1}
.gg-guide-timeline-label{font-size:14px;font-weight:700;margin:0 0 6px;text-transform:uppercase;letter-spacing:1px;color:#000}
.gg-guide-timeline-content p{font-size:13px;line-height:1.6;margin:0;color:#444}

/* ── Process List ── */
.gg-guide-process-list{margin:0 0 20px}
.gg-guide-process-item{display:flex;gap:14px;margin-bottom:16px;padding:12px;border:2px solid #000;background:#fff}
.gg-guide-process-num{width:32px;height:32px;min-width:32px;background:#000;color:#fff;font-size:14px;font-weight:700;display:flex;align-items:center;justify-content:center}
.gg-guide-process-body{flex:1}
.gg-guide-process-label{font-weight:700;font-size:14px;color:#000}
.gg-guide-process-pct{display:inline-block;background:#B7950B;color:#fff;font-size:10px;font-weight:700;padding:2px 6px;margin-left:8px;letter-spacing:1px}
.gg-guide-process-detail{font-size:13px;color:#444;margin:4px 0 0;line-height:1.5}

/* ── Callout ── */
.gg-guide-callout{padding:20px 24px;margin:0 0 20px;border-left:4px solid #1A8A82;background:#f5f0eb}
.gg-guide-callout--quote{border-left-color:#B7950B;background:#faf5f0;font-style:italic}
.gg-guide-callout--highlight{border-left-color:#1A8A82;background:#f0faf9}
.gg-guide-callout--traffic_light{border-left-color:#B7950B;background:#faf5f0}
.gg-guide-callout p{font-size:13px;line-height:1.7;margin:0 0 8px;color:#333}
.gg-guide-callout p:last-child{margin-bottom:0}

/* ── Knowledge Check ── */
.gg-guide-knowledge-check{border:3px solid #000;margin:0 0 24px;background:#fff}
.gg-guide-kc-label{background:#B7950B;color:#fff;padding:8px 16px;font-size:10px;font-weight:700;letter-spacing:3px;text-transform:uppercase}
.gg-guide-kc-question{padding:16px 20px 8px;font-size:14px;font-weight:700;color:#000;margin:0}
.gg-guide-kc-options{padding:8px 20px 16px;display:flex;flex-direction:column;gap:8px}
.gg-guide-kc-option{padding:10px 16px;background:#f5f0eb;border:2px solid #000;cursor:pointer;font-family:'Sometype Mono',monospace;font-size:12px;text-align:left;transition:all 0.2s}
.gg-guide-kc-option:hover{background:#e8dfd7}
.gg-guide-kc-option--correct{background:#1A8A82 !important;color:#fff !important;border-color:#1A8A82 !important}
.gg-guide-kc-option--incorrect{background:#c44 !important;color:#fff !important;border-color:#c44 !important}
.gg-guide-kc-option--disabled{pointer-events:none;opacity:0.6}
.gg-guide-kc-explanation{padding:12px 20px 16px;background:#f0faf9;border-top:2px solid #1A8A82}
.gg-guide-kc-explanation p{font-size:13px;line-height:1.6;margin:0;color:#333}

/* ── CTA Blocks ── */
.gg-guide-cta{margin:0 0 40px;border:3px solid #000;padding:40px 32px;text-align:center}
.gg-guide-cta-inner{max-width:600px;margin:0 auto}
.gg-guide-cta-kicker{display:inline-block;font-size:10px;font-weight:700;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px}
.gg-guide-cta h3{font-size:22px;font-weight:700;text-transform:uppercase;letter-spacing:2px;margin:0 0 12px}
.gg-guide-cta p{font-size:13px;line-height:1.6;margin:0 0 16px}
.gg-guide-cta ul{text-align:left;font-size:13px;line-height:1.8;padding-left:20px;margin:0 0 20px}
.gg-guide-cta--newsletter{background:#59473c;color:#fff}
.gg-guide-cta--newsletter .gg-guide-cta-kicker{color:#d4c5b9}
.gg-guide-cta--newsletter p{color:#d4c5b9}
.gg-guide-cta--training{background:#000;color:#fff}
.gg-guide-cta--training .gg-guide-cta-kicker{color:#8c7568}
.gg-guide-cta--training p,.gg-guide-cta--training ul{color:#d4c5b9}
.gg-guide-cta--coaching{background:#1A8A82;color:#fff}
.gg-guide-cta--coaching .gg-guide-cta-kicker{color:rgba(255,255,255,0.7)}

/* ── Buttons ── */
.gg-guide-btn{display:inline-block;padding:12px 28px;font-family:'Sometype Mono',monospace;font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;text-decoration:none;cursor:pointer;border:3px solid #000;transition:all 0.15s}
.gg-guide-btn--primary{background:#59473c;color:#fff;border-color:#59473c}
.gg-guide-btn--primary:hover{background:#8c7568;border-color:#8c7568}
.gg-guide-btn--secondary{background:#fff;color:#000;border-color:#000}
.gg-guide-btn--secondary:hover{background:#000;color:#fff}

/* ── Finale Grid ── */
.gg-guide-finale{margin:0 0 40px;text-align:center}
.gg-guide-finale-title{font-size:24px;font-weight:700;text-transform:uppercase;letter-spacing:2px;margin:0 0 24px;color:#59473c}
.gg-guide-finale-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:0}
.gg-guide-finale-card{padding:32px 20px;border:3px solid #000;text-align:center}
.gg-guide-finale-card+.gg-guide-finale-card{border-left:none}
.gg-guide-finale-kicker{display:block;font-size:10px;font-weight:700;letter-spacing:3px;margin-bottom:8px}
.gg-guide-finale-card h3{font-size:18px;font-weight:700;text-transform:uppercase;margin:0 0 8px}
.gg-guide-finale-card p{font-size:12px;line-height:1.5;margin:0 0 16px}
.gg-guide-finale-card--newsletter{background:#59473c;color:#fff}
.gg-guide-finale-card--newsletter .gg-guide-finale-kicker{color:#d4c5b9}
.gg-guide-finale-card--newsletter p{color:#d4c5b9}
.gg-guide-finale-card--training{background:#000;color:#fff}
.gg-guide-finale-card--training .gg-guide-finale-kicker{color:#8c7568}
.gg-guide-finale-card--training p{color:#d4c5b9}
.gg-guide-finale-card--coaching{background:#1A8A82;color:#fff}
.gg-guide-finale-card--coaching .gg-guide-finale-kicker{color:rgba(255,255,255,0.7)}

/* ── Scroll Fade-In ── */
.gg-guide-fade-in{opacity:0;transform:translateY(20px)}
.gg-guide-fade-in--visible{opacity:1;transform:translateY(0)}

/* ── Footer ── */
.gg-guide-chapter-body .gg-footer{border:none;margin:0;padding:24px 0 0}

/* ── Reduced Motion ── */
@media(prefers-reduced-motion: no-preference){
  .gg-guide-progress-bar{transition:width 0.15s linear}
  .gg-guide-chapnav-item{transition:all 0.2s}
  .gg-guide-accordion-icon{transition:transform 0.2s}
  .gg-guide-tab{transition:all 0.2s}
  .gg-guide-kc-option{transition:all 0.2s}
  .gg-guide-btn{transition:all 0.15s}
  .gg-guide-fade-in{transition:opacity 0.5s ease,transform 0.5s ease}
}

/* ── Responsive ── */
@media(max-width:768px){
  .gg-guide-chapnav{flex-wrap:wrap}
  .gg-guide-chapnav-item{padding:8px 10px;font-size:11px}
  .gg-guide-chapter-hero{padding:32px 20px}
  .gg-guide-chapter-title{font-size:24px}
  .gg-guide-chapter-body{padding:24px 16px}
  .gg-guide-finale-grid{grid-template-columns:1fr}
  .gg-guide-finale-card+.gg-guide-finale-card{border-left:3px solid #000;border-top:none}
  .gg-guide-cta{padding:32px 20px}
  .gg-guide-tab-bar{flex-direction:column}
  .gg-guide-tab{border-right:none;border-bottom:1px solid #555}
  .gg-guide-process-item{flex-direction:column;gap:8px}
  .gg-guide-timeline-step{gap:12px}
  .gg-guide-table{font-size:11px}
  .gg-guide-table th,.gg-guide-table td{padding:6px 8px}
}
'''


# ── JS ───────────────────────────────────────────────────────


def build_guide_js() -> str:
    """Return all guide-specific JavaScript as a single IIFE."""
    return '''(function(){
"use strict";

/* ── Analytics Helper (beacon transport) ── */
function track(eventName, params) {
  if (typeof gtag === "function") {
    gtag("event", eventName, Object.assign({ transport_type: "beacon" }, params || {}));
  }
}

/* ── Gate Logic ── */
var STORAGE_KEY = "gg_guide_unlocked";
var page = document.querySelector(".gg-neo-brutalist-page");

function isUnlocked() {
  try { return localStorage.getItem(STORAGE_KEY) === "1"; } catch(e) { return false; }
}

function unlock(method) {
  try { localStorage.setItem(STORAGE_KEY, "1"); } catch(e) {}
  if (page) page.classList.add("gg-guide-unlocked");
  document.querySelectorAll(".gg-guide-chapnav-item--locked").forEach(function(el) {
    el.classList.add("gg-guide-chapnav-item--unlocked");
  });
  track("guide_unlock", { method: method || "unknown" });
}

if (isUnlocked()) {
  if (page) page.classList.add("gg-guide-unlocked");
  document.querySelectorAll(".gg-guide-chapnav-item--locked").forEach(function(el) {
    el.classList.add("gg-guide-chapnav-item--unlocked");
  });
  track("guide_return_visit", { unlocked: true });
}

// Listen for Substack postMessage
window.addEventListener("message", function(e) {
  if (e.origin && e.origin.indexOf("substack.com") !== -1) {
    if (e.data && (e.data.type === "subscription-created" || e.data === "subscription-created")) {
      unlock("substack_subscribe");
    }
  }
});

// Manual bypass
var bypassBtn = document.getElementById("gg-guide-gate-bypass");
if (bypassBtn) {
  bypassBtn.addEventListener("click", function() { unlock("manual_bypass"); });
}

/* ── Scroll Depth Tracking ── */
var scrollMilestones = { 25: false, 50: false, 75: false, 100: false };
var progressBar = document.querySelector(".gg-guide-progress-bar");
var ticking = false;
window.addEventListener("scroll", function() {
  if (!ticking) {
    requestAnimationFrame(function() {
      var h = document.documentElement.scrollHeight - window.innerHeight;
      var pct = h > 0 ? (window.scrollY / h) * 100 : 0;
      if (progressBar) {
        progressBar.style.width = Math.min(100, pct) + "%";
        progressBar.setAttribute("aria-valuenow", Math.round(Math.min(100, pct)));
      }
      // Fire milestone events
      [25, 50, 75, 100].forEach(function(m) {
        if (!scrollMilestones[m] && pct >= m) {
          scrollMilestones[m] = true;
          track("guide_scroll_depth", { percent: m, unlocked: isUnlocked() });
        }
      });
      ticking = false;
    });
    ticking = true;
  }
}, { passive: true });

/* ── Chapter Read Tracking ── */
var chapters = document.querySelectorAll(".gg-guide-chapter");
var navItems = document.querySelectorAll(".gg-guide-chapnav-item");
var chaptersRead = {};

if (chapters.length && "IntersectionObserver" in window) {
  var activeId = null;

  // Chapter nav active state
  var chapterObserver = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        activeId = entry.target.id;
        var chNum = entry.target.getAttribute("data-chapter");
        navItems.forEach(function(nav) {
          nav.classList.toggle("gg-guide-chapnav-item--active",
            nav.getAttribute("data-chapter") === activeId);
        });
        // Track chapter view (once per session)
        if (chNum && !chaptersRead[chNum]) {
          chaptersRead[chNum] = true;
          track("guide_chapter_view", {
            chapter_number: parseInt(chNum, 10),
            chapter_id: activeId
          });
        }
      }
    });
  }, { rootMargin: "-20% 0px -70% 0px", threshold: 0 });
  chapters.forEach(function(ch) { chapterObserver.observe(ch); });
}

// Chapter nav click — scroll to gate if chapter is gated and locked
navItems.forEach(function(item) {
  item.addEventListener("click", function(e) {
    e.preventDefault();
    var chapterId = item.getAttribute("data-chapter");
    var target = document.getElementById(chapterId);
    if (target && target.classList.contains("gg-guide-gated") && !isUnlocked()) {
      var gateEl = document.getElementById("gg-guide-gate");
      if (gateEl) gateEl.scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    track("guide_chapnav_click", { chapter: chapterId });
  });
});

/* ── Gate Impression Tracking ── */
var gateEl = document.getElementById("gg-guide-gate");
if (gateEl && "IntersectionObserver" in window) {
  var gateTracked = false;
  var gateObserver = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting && !gateTracked) {
        gateTracked = true;
        track("guide_gate_impression", {});
        gateObserver.unobserve(gateEl);
      }
    });
  }, { threshold: 0.3 });
  gateObserver.observe(gateEl);
}

/* ── Accordion Toggle ── */
document.querySelectorAll(".gg-guide-accordion-trigger").forEach(function(trigger) {
  trigger.addEventListener("click", function() {
    var expanded = trigger.getAttribute("aria-expanded") === "true";
    trigger.setAttribute("aria-expanded", expanded ? "false" : "true");
  });
});

/* ── Tab Switching ── */
document.querySelectorAll(".gg-guide-tabs").forEach(function(tabGroup) {
  var tabs = tabGroup.querySelectorAll(".gg-guide-tab");
  var panels = tabGroup.querySelectorAll(".gg-guide-tab-panel");
  tabs.forEach(function(tab) {
    tab.addEventListener("click", function() {
      var targetId = tab.getAttribute("data-tab");
      tabs.forEach(function(t) {
        t.classList.remove("gg-guide-tab--active");
        t.setAttribute("aria-selected", "false");
      });
      panels.forEach(function(p) { p.style.display = "none"; });
      tab.classList.add("gg-guide-tab--active");
      tab.setAttribute("aria-selected", "true");
      var panel = document.getElementById(targetId);
      if (panel) panel.style.display = "block";
    });
  });
});

/* ── Knowledge Check ── */
document.querySelectorAll(".gg-guide-knowledge-check").forEach(function(kc) {
  var options = kc.querySelectorAll(".gg-guide-kc-option");
  var explanation = kc.querySelector(".gg-guide-kc-explanation");
  var answered = false;
  options.forEach(function(opt) {
    opt.addEventListener("click", function() {
      if (answered) return;
      answered = true;
      var isCorrect = opt.getAttribute("data-correct") === "true";
      opt.classList.add(isCorrect ? "gg-guide-kc-option--correct" : "gg-guide-kc-option--incorrect");
      if (!isCorrect) {
        options.forEach(function(o) {
          if (o.getAttribute("data-correct") === "true") o.classList.add("gg-guide-kc-option--correct");
        });
      }
      options.forEach(function(o) {
        if (o !== opt && o.getAttribute("data-correct") !== "true") o.classList.add("gg-guide-kc-option--disabled");
        o.setAttribute("aria-disabled", "true");
      });
      if (explanation) explanation.style.display = "block";
      track("guide_knowledge_check", { correct: isCorrect });
    });
  });
});

/* ── CTA Click Tracking ── */
document.querySelectorAll(".gg-guide-cta a, .gg-guide-finale-card a").forEach(function(link) {
  link.addEventListener("click", function() {
    var ctaBlock = link.closest(".gg-guide-cta, .gg-guide-finale-card");
    var ctaType = "unknown";
    if (ctaBlock) {
      if (ctaBlock.classList.contains("gg-guide-cta--newsletter") || ctaBlock.classList.contains("gg-guide-finale-card--newsletter")) ctaType = "newsletter";
      else if (ctaBlock.classList.contains("gg-guide-cta--training") || ctaBlock.classList.contains("gg-guide-finale-card--training")) ctaType = "training_plan";
      else if (ctaBlock.classList.contains("gg-guide-cta--coaching") || ctaBlock.classList.contains("gg-guide-finale-card--coaching")) ctaType = "coaching";
    }
    track("guide_cta_click", {
      cta_type: ctaType,
      link_url: link.href
    });
  });
});

/* ── Scroll Fade-In ── */
if ("IntersectionObserver" in window) {
  var fadeEls = document.querySelectorAll(".gg-guide-fade-in");
  if (fadeEls.length) {
    var fadeObserver = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("gg-guide-fade-in--visible");
          fadeObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1 });
    fadeEls.forEach(function(el) { fadeObserver.observe(el); });
  }
}

/* ── Time on Page (beacon) ── */
var pageStartTime = Date.now();
window.addEventListener("beforeunload", function() {
  var seconds = Math.round((Date.now() - pageStartTime) / 1000);
  if (navigator.sendBeacon && typeof gtag === "function") {
    var params = "?seconds=" + seconds + "&chapters=" + Object.keys(chaptersRead).length;
    navigator.sendBeacon("/guide/ping" + params);
  }
  track("guide_time_on_page", { seconds: seconds, chapters_read: Object.keys(chaptersRead).length });
});

})();
'''


# ── Page Assembly ────────────────────────────────────────────


def generate_guide_page(content: dict, inline: bool = False, assets_dir: Path = None) -> str:
    """Generate the complete guide HTML page."""
    canonical_url = f"{SITE_BASE_URL}/guide/"
    og_image = f"{SITE_BASE_URL}/wp-content/uploads/gravel-god-og.png"

    nav = build_nav()
    hero = build_hero(content)
    progress = build_progress_bar()
    chapnav = build_chapter_nav(content["chapters"])
    jsonld = build_jsonld(content)
    footer = build_footer()

    # Build chapters with CTAs
    chapters_html = []
    for ch in content["chapters"]:
        chapters_html.append(build_chapter(ch))
        cta_type = ch.get("cta_after")
        if cta_type == "gate":
            chapters_html.append(build_gate())
        elif cta_type == "finale":
            chapters_html.append(build_cta_finale())
        elif cta_type and cta_type in CTA_BUILDERS:
            chapters_html.append(CTA_BUILDERS[cta_type]())

    # CSS/JS
    guide_css_content = build_guide_css()
    guide_js_content = build_guide_js()

    if inline:
        css_html = f'<style>{guide_css_content}</style>'
        js_html = f'<script>{guide_js_content}</script>'
    else:
        # Write to assets_dir with content hash
        if assets_dir is None:
            assets_dir = OUTPUT_DIR / "guide-assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        css_hash = hashlib.md5(guide_css_content.encode()).hexdigest()[:8]
        js_hash = hashlib.md5(guide_js_content.encode()).hexdigest()[:8]

        css_file = f"gg-guide-styles.{css_hash}.css"
        js_file = f"gg-guide-scripts.{js_hash}.js"

        (assets_dir / css_file).write_text(guide_css_content, encoding="utf-8")
        (assets_dir / js_file).write_text(guide_js_content, encoding="utf-8")

        print(f"  Wrote {assets_dir / css_file} ({len(guide_css_content):,} bytes)")
        print(f"  Wrote {assets_dir / js_file} ({len(guide_js_content):,} bytes)")

        css_html = f'<link rel="stylesheet" href="/guide/guide-assets/{css_file}">'
        js_html = f'<script src="/guide/guide-assets/{js_file}"></script>'

    og_tags = f'''<meta property="og:title" content="{esc(content["title"])}">
  <meta property="og:description" content="{esc(content["meta_description"])}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:image" content="{esc(og_image)}">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(content["title"])}">
  <meta name="twitter:description" content="{esc(content["meta_description"])}">
  <meta name="twitter:image" content="{esc(og_image)}">'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(content["title"])} — Gravel God Cycling</title>
  <meta name="description" content="{esc(content["meta_description"])}">
  <link rel="canonical" href="{esc(canonical_url)}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Sometype+Mono:wght@400;700&display=swap">
  <!-- GA4 -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA4_MEASUREMENT_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA4_MEASUREMENT_ID}');</script>
  {og_tags}
  {jsonld}
  <style>
/* Base reset (from neo-brutalist) */
.gg-neo-brutalist-page {{
  max-width: 960px;
  margin: 0 auto;
  padding: 0 20px;
  font-family: 'Sometype Mono', monospace;
  color: #000;
  line-height: 1.6;
}}
.gg-neo-brutalist-page *, .gg-neo-brutalist-page *::before, .gg-neo-brutalist-page *::after {{
  border-radius: 0 !important;
  box-shadow: none !important;
  font-family: 'Sometype Mono', monospace;
  box-sizing: border-box;
}}
/* Nav */
.gg-neo-brutalist-page .gg-site-nav {{ background: #000; border: 3px solid #000; margin-bottom: 0; }}
.gg-neo-brutalist-page .gg-site-nav-inner {{ display: flex; align-items: center; padding: 12px 20px; gap: 20px; }}
.gg-neo-brutalist-page .gg-site-nav-brand {{ color: #fff; text-decoration: none; font-size: 16px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; }}
.gg-neo-brutalist-page .gg-site-nav-link {{ color: #d4c5b9; text-decoration: none; font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; transition: color 0.2s; }}
.gg-neo-brutalist-page .gg-site-nav-link:hover {{ color: #fff; }}
.gg-neo-brutalist-page .gg-breadcrumb {{ padding: 8px 20px; font-size: 11px; background: #111; }}
.gg-neo-brutalist-page .gg-breadcrumb a {{ color: #c4b5ab; text-decoration: none; }}
.gg-neo-brutalist-page .gg-breadcrumb a:hover {{ color: #d4c5b9; }}
.gg-neo-brutalist-page .gg-breadcrumb-sep {{ color: #555; margin: 0 6px; }}
.gg-neo-brutalist-page .gg-breadcrumb-current {{ color: #d4c5b9; }}
/* Hero */
.gg-neo-brutalist-page .gg-hero {{ background: #59473c; color: #fff; padding: 60px 40px; border: 3px solid #000; border-top: none; margin-bottom: 0; position: relative; overflow: hidden; }}
.gg-neo-brutalist-page .gg-hero-tier {{ display: inline-block; background: #000; color: #fff; padding: 4px 12px; font-size: 12px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 16px; }}
.gg-neo-brutalist-page .gg-hero h1 {{ font-size: 36px; font-weight: 700; line-height: 1.1; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 16px; color: #fff; position: relative; }}
.gg-neo-brutalist-page .gg-hero h1::after {{ content: attr(data-text); position: absolute; left: 3px; top: 3px; color: #1A8A82; opacity: 0.3; z-index: 0; pointer-events: none; }}
.gg-neo-brutalist-page .gg-hero-tagline {{ font-size: 14px; line-height: 1.6; color: #d4c5b9; max-width: 700px; }}
/* Footer */
.gg-neo-brutalist-page .gg-footer {{ padding: 24px 20px; border: 3px solid #000; background: #f5f0eb; margin-top: 0; }}
.gg-neo-brutalist-page .gg-footer-disclaimer {{ font-size: 11px; color: #666; line-height: 1.6; }}
@media(max-width:768px){{
  .gg-neo-brutalist-page .gg-hero {{ padding: 40px 20px; }}
  .gg-neo-brutalist-page .gg-hero h1 {{ font-size: 26px; }}
  .gg-neo-brutalist-page .gg-site-nav-inner {{ flex-wrap: wrap; gap: 12px; }}
}}
  </style>
  {css_html}
</head>
<body>

{progress}

<div class="gg-neo-brutalist-page" id="gg-guide-page">
  {nav}

  {hero}

  {chapnav}

  {"".join(chapters_html)}

  {footer}
</div>

{js_html}

</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate Gravel God Training Guide page")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    parser.add_argument("--inline", action="store_true", help="Inline CSS/JS for local preview")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    content = load_content()
    print(f"Loaded {len(content['chapters'])} chapters from {CONTENT_JSON}")

    if args.inline:
        html_content = generate_guide_page(content, inline=True)
        output_file = output_dir / "guide.html"
    else:
        assets_dir = output_dir / "guide-assets"
        html_content = generate_guide_page(content, inline=False, assets_dir=assets_dir)
        output_file = output_dir / "guide.html"

    output_file.write_text(html_content, encoding="utf-8")
    print(f"Generated {output_file} ({len(html_content):,} bytes)")


if __name__ == "__main__":
    main()
