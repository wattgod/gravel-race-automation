#!/usr/bin/env python3
"""
GRAVEL TV — weekly broadcast digest page.

Generates /gravel-tv/ entirely from data the repo already owns:
  ON AIR THIS WEEK   races in the next 14 days (race-data date_specific)
  THE DESK           the coach's weekly editorial note (markdown slot)
  FRESH TAPE         latest curated race videos (youtube_data thumbnails)
  REPLAY DESK        newest recaps/previews (web/blog-index.json)
  SUBSCRIBE          email capture via the lead-intake worker

Design language: early-90s music-television vocabulary — chunky stacked
letterforms, scanlines, chyron bars — as an ORIGINAL mark (no borrowed
logos; evoke the era, don't copy the asset).

Usage:
    python3 wordpress/generate_gravel_tv.py
Desk note:
    Edit web/gravel-tv-desk-note.md weekly, regenerate, deploy.
"""

import hashlib
import html as html_mod
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brand_tokens import get_ga4_head_snippet, get_font_face_css, get_tokens_css
from shared_header import get_site_header_html, get_site_header_css, get_site_header_js

PROJECT_ROOT = Path(__file__).parent.parent
RACE_DATA = PROJECT_ROOT / 'race-data'
BLOG_INDEX = PROJECT_ROOT / 'web' / 'blog-index.json'
DESK_NOTE = PROJECT_ROOT / 'web' / 'gravel-tv-desk-note.md'
OUTPUT = PROJECT_ROOT / 'wordpress' / 'output' / 'gravel-tv.html'

LEAD_WORKER_URL = "https://fueling-lead-intake.gravelgodcoaching.workers.dev"

MONTHS = {m: i + 1 for i, m in enumerate(
    ['January', 'February', 'March', 'April', 'May', 'June', 'July',
     'August', 'September', 'October', 'November', 'December'])}


def esc(text) -> str:
    if text is None or text == "":
        return ""
    return html_mod.escape(str(text), quote=True)


def parse_date_specific(ds) -> date | None:
    """'2026: May 30' / '2026: July 11-12' → date of the first day."""
    m = re.match(r'^(\d{4}):\s*([A-Z][a-z]+)\s+(\d{1,2})', str(ds).strip())
    if not m:
        return None
    month = MONTHS.get(m.group(2))
    if not month:
        return None
    try:
        return date(int(m.group(1)), month, int(m.group(3)))
    except ValueError:
        return None


def load_races() -> list[dict]:
    races = []
    for f in sorted(RACE_DATA.glob('*.json')):
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        race = d.get('race', d)
        rating = race.get('gravel_god_rating') or race.get('fondo_rating') or {}
        races.append({
            'slug': f.stem,
            'name': race.get('name', f.stem),
            'date': parse_date_specific(race.get('vitals', {}).get('date_specific', '')),
            'tier': rating.get('tier'),
            'location': race.get('vitals', {}).get('location', ''),
            'discipline': race.get('discipline', 'gravel'),
            'videos': (race.get('youtube_data') or {}).get('videos', []),
        })
    return races


def section_on_air(races: list[dict], today: date) -> str:
    horizon = today + timedelta(days=14)
    upcoming = sorted(
        (r for r in races if r['date'] and today <= r['date'] <= horizon),
        key=lambda r: (r['date'], r['tier'] or 9))
    if not upcoming:
        return ('<p class="gtv-empty">Quiet fortnight on the calendar. '
                'The dirt is resting.</p>')

    cards = ''
    for r in upcoming[:16]:
        tier = r['tier'] or '?'
        day = r['date'].strftime('%a %b %-d')
        loc = esc(r['location'][:40]) if r['location'] else ''
        cards += f'''
        <a class="gtv-card" href="/race/{esc(r['slug'])}/">
          <span class="gtv-card-date">{esc(day)}</span>
          <span class="gtv-card-tier gtv-tier-{esc(tier)}">T{esc(tier)}</span>
          <span class="gtv-card-name">{esc(r['name'])}</span>
          {f'<span class="gtv-card-loc">{loc}</span>' if loc else ''}
        </a>'''
    more = ''
    if len(upcoming) > 16:
        more = (f'<p class="gtv-more"><a href="/gravel-races/?view=calendar">'
                f'+{len(upcoming) - 16} more on the full calendar →</a></p>')
    return f'<div class="gtv-grid">{cards}\n      </div>{more}'


def section_fresh_tape(races: list[dict], today: date) -> str:
    """Latest curated race videos — prefer races racing soon, then tier."""
    candidates = []
    for r in races:
        for v in r['videos'][:1]:
            thumb = v.get('thumbnail_url')
            if not thumb:
                continue
            days_out = (r['date'] - today).days if r['date'] else 9999
            soon = 0 if 0 <= days_out <= 30 else 1
            candidates.append((soon, r['tier'] or 9, -(v.get('thumbnail_score') or 0), {
                'slug': r['slug'], 'race': r['name'],
                'title': v.get('title', ''), 'thumb': thumb,
                'video_id': v.get('video_id', ''),
            }))
    candidates.sort(key=lambda c: c[:3])
    tiles = ''
    for _, _, _, v in candidates[:6]:
        vid_url = f"https://www.youtube.com/watch?v={esc(v['video_id'])}" if v['video_id'] else f"/race/{esc(v['slug'])}/"
        tiles += f'''
        <div class="gtv-tape">
          <a href="{vid_url}" rel="noopener" target="_blank">
            <img src="{esc(v['thumb'])}" alt="{esc(v['title'])}" loading="lazy" width="320" height="180">
          </a>
          <a class="gtv-tape-race" href="/race/{esc(v['slug'])}/">{esc(v['race'])}</a>
          <span class="gtv-tape-title">{esc(v['title'][:70])}</span>
        </div>'''
    return f'<div class="gtv-tapes">{tiles}\n      </div>' if tiles else ''


def section_replay_desk() -> str:
    try:
        entries = json.loads(BLOG_INDEX.read_text())
    except (OSError, json.JSONDecodeError):
        return ''
    entries = sorted(entries, key=lambda e: e.get('date', ''), reverse=True)[:4]
    items = ''
    for e in entries:
        prefix = 'articles' if e.get('category') == 'article' else 'blog'
        items += f'''
        <li><span class="gtv-replay-date">{esc(e.get('date', ''))}</span>
            <a href="/{prefix}/{esc(e.get('slug', ''))}/">{esc(e.get('title', ''))}</a></li>'''
    return f'<ul class="gtv-replays">{items}\n      </ul>' if items else ''


def section_desk_note() -> str:
    """The coach's weekly note. Plain markdown → paragraphs. His voice, his slot."""
    if not DESK_NOTE.exists():
        return '<p class="gtv-empty">The desk is empty this week. Unprecedented.</p>'
    raw = DESK_NOTE.read_text().strip()
    # Fingerprint lets CI verify THIS note is live (gtv-logo alone can't
    # detect a stale page after a failed upload)
    fingerprint = hashlib.md5(raw.encode()).hexdigest()
    # strip a leading h1 if present (the section provides the heading)
    raw = re.sub(r'^#\s+.*\n', '', raw)
    paras = ''.join(f'<p>{esc(p.strip())}</p>'
                    for p in raw.split('\n\n') if p.strip())
    if not paras:
        return '<p class="gtv-empty">The desk is empty this week.</p>'
    return f'<!-- gtv-note-hash: {fingerprint} -->{paras}'


def build_page() -> str:
    today = date.today()
    races = load_races()
    issue_no = (today - date(2026, 6, 8)).days // 7 + 1  # weekly since launch Monday

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Gravel TV — This Week in Gravel Racing | Gravel God</title>
  <meta name="description" content="Gravel TV: the weekly gravel racing broadcast. Races on this week, fresh race footage, recaps, and the desk note — from the database that rates every race honestly.">
{get_ga4_head_snippet()}
  <style>
{get_tokens_css()}
{get_font_face_css()}
{get_site_header_css()}
  body {{ margin: 0; background: var(--gg-color-warm-paper); color: #000;
         font-family: 'Sometype Mono', monospace; }}
  .gtv-wrap {{ max-width: 960px; margin: 0 auto; padding: 0 20px 64px; }}

  /* ── Masthead: early-90s broadcast, original mark ───────── */
  .gtv-masthead {{ position: relative; border: 4px solid #000;
    background: var(--gg-color-teal); padding: 36px 24px 28px;
    margin: 24px 0 8px; overflow: hidden; }}
  .gtv-masthead::after {{ content: ''; position: absolute; inset: 0;
    background: repeating-linear-gradient(0deg, rgba(0,0,0,0.14) 0 1px,
      transparent 1px 4px); pointer-events: none; }}
  .gtv-logo {{ font-size: clamp(3rem, 10vw, 5.5rem); font-weight: 700;
    line-height: 0.9; letter-spacing: -0.02em; color: var(--gg-color-warm-paper);
    text-transform: uppercase; margin: 0;
    text-shadow: 3px 3px 0 #000, 6px 6px 0 var(--gg-color-gold),
      9px 9px 0 #000; }}
  .gtv-logo .gtv-tv {{ display: inline-block; background: #000;
    color: var(--gg-color-gold); padding: 0 0.15em; margin-left: 0.12em;
    transform: rotate(-2deg); }}
  .gtv-chyron {{ display: flex; justify-content: space-between; gap: 12px;
    border: 3px solid #000; border-top: none; background: #000;
    color: var(--gg-color-warm-paper); padding: 6px 14px; font-size: 12px;
    text-transform: uppercase; letter-spacing: 0.12em; flex-wrap: wrap; }}
  .gtv-chyron strong {{ color: var(--gg-color-gold); }}

  /* ── Sections ───────────────────────────────────────────── */
  .gtv-section {{ margin-top: 40px; }}
  .gtv-section-bar {{ display: flex; align-items: center; gap: 12px;
    background: #000; color: var(--gg-color-warm-paper); border: 3px solid #000;
    padding: 8px 14px; }}
  .gtv-section-bar h2 {{ font-size: 1rem; margin: 0; text-transform: uppercase;
    letter-spacing: 0.14em; }}
  .gtv-live-dot {{ width: 10px; height: 10px; background: var(--gg-color-gold);
    display: inline-block; animation: gtv-blink 1.4s steps(2) infinite; }}
  @media (prefers-reduced-motion: reduce) {{ .gtv-live-dot {{ animation: none; }} }}
  @keyframes gtv-blink {{ 50% {{ opacity: 0.15; }} }}
  .gtv-section-body {{ border: 3px solid #000; border-top: none;
    background: #fff; padding: 18px; }}

  .gtv-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
    gap: 12px; }}
  .gtv-card {{ display: flex; flex-direction: column; gap: 4px; border: 3px solid #000;
    padding: 10px 12px; text-decoration: none; color: #000; background: #fff;
    transition: transform var(--gg-transition-hover), box-shadow var(--gg-transition-hover); }}
  .gtv-card:hover {{ transform: translate(-2px, -2px); box-shadow: 4px 4px 0 #000; }}
  .gtv-card-date {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; }}
  .gtv-card-tier {{ font-size: 11px; font-weight: 700; width: fit-content;
    padding: 1px 6px; border: 2px solid #000; }}
  .gtv-tier-1 {{ background: var(--gg-color-gold); }}
  .gtv-tier-2 {{ background: var(--gg-color-tan); }}
  .gtv-card-name {{ font-weight: 700; font-size: 14px; line-height: 1.3; }}
  .gtv-card-loc {{ font-size: 11px; color: #555; }}
  .gtv-more {{ margin: 14px 0 0; font-size: 13px; }}
  .gtv-empty {{ font-style: italic; color: #555; }}

  .gtv-tapes {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px; }}
  .gtv-tape img {{ width: 100%; height: auto; display: block; border: 3px solid #000;
    filter: saturate(1.1) contrast(1.05); }}
  .gtv-tape-race {{ display: block; font-weight: 700; margin-top: 6px; color: #000;
    text-decoration: none; font-size: 14px; }}
  .gtv-tape-title {{ font-size: 12px; color: #555; }}

  .gtv-replays {{ list-style: none; margin: 0; padding: 0; }}
  .gtv-replays li {{ display: flex; gap: 14px; padding: 8px 0;
    border-bottom: 2px solid var(--gg-color-tan); font-size: 14px; }}
  .gtv-replays li:last-child {{ border-bottom: none; }}
  .gtv-replay-date {{ color: #555; white-space: nowrap; font-size: 12px;
    padding-top: 2px; }}
  .gtv-replays a {{ color: #000; font-weight: 600; }}

  .gtv-desk p {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 1.05rem;
    line-height: 1.7; margin: 0 0 1em; }}

  /* ── Subscribe ──────────────────────────────────────────── */
  .gtv-sub {{ margin-top: 48px; border: 4px solid #000; background: #000;
    color: var(--gg-color-warm-paper); padding: 26px 22px; }}
  .gtv-sub h2 {{ margin: 0 0 6px; text-transform: uppercase; letter-spacing: 0.1em;
    font-size: 1.2rem; color: var(--gg-color-gold); }}
  .gtv-sub p {{ margin: 0 0 14px; font-size: 14px; }}
  .gtv-sub-form {{ display: flex; gap: 10px; flex-wrap: wrap; }}
  .gtv-sub-form input[type="email"] {{ flex: 1; min-width: 220px; padding: 12px 14px;
    border: 3px solid var(--gg-color-warm-paper); background: #fff; color: #000;
    font-family: 'Sometype Mono', monospace; font-size: 14px; }}
  .gtv-sub-form button {{ padding: 12px 22px; border: 3px solid var(--gg-color-gold);
    background: var(--gg-color-gold); color: #000; font-weight: 700;
    font-family: 'Sometype Mono', monospace; text-transform: uppercase;
    letter-spacing: 0.08em; cursor: pointer; }}
  .gtv-hp {{ position: absolute; left: -9999px; opacity: 0; height: 0; width: 0; }}
  .gtv-sub-msg {{ margin-top: 10px; font-size: 13px; min-height: 18px; }}
  </style>
</head>
<body>
{get_site_header_html()}
<main class="gtv-wrap">

  <div class="gtv-masthead">
    <h1 class="gtv-logo">Gravel<span class="gtv-tv">TV</span></h1>
  </div>
  <div class="gtv-chyron">
    <span>ISSUE <strong>#{issue_no:03d}</strong></span>
    <span>{esc(today.strftime('%A %B %-d, %Y').upper())}</span>
    <span>BROADCASTING IN <strong>GRAVEL-VISION</strong></span>
  </div>

  <section class="gtv-section" id="desk">
    <div class="gtv-section-bar"><span class="gtv-live-dot"></span><h2>The Desk</h2></div>
    <div class="gtv-section-body gtv-desk">
      {section_desk_note()}
    </div>
  </section>

  <section class="gtv-section" id="on-air">
    <div class="gtv-section-bar"><span class="gtv-live-dot"></span><h2>On Air This Week</h2></div>
    <div class="gtv-section-body">
      {section_on_air(races, today)}
    </div>
  </section>

  <section class="gtv-section" id="fresh-tape">
    <div class="gtv-section-bar"><h2>Fresh Tape</h2></div>
    <div class="gtv-section-body">
      {section_fresh_tape(races, today)}
    </div>
  </section>

  <section class="gtv-section" id="replay-desk">
    <div class="gtv-section-bar"><h2>Replay Desk</h2></div>
    <div class="gtv-section-body">
      {section_replay_desk()}
    </div>
  </section>

  <section class="gtv-sub" id="subscribe">
    <h2>Get The Broadcast</h2>
    <p>One email a week. The desk note, the weekend's races, the freshest tape. No reruns.</p>
    <form class="gtv-sub-form" id="gtv-sub-form" autocomplete="off">
      <input type="text" class="gtv-hp" name="website" value="" tabindex="-1" aria-hidden="true">
      <input type="email" name="email" required placeholder="your@email.com" aria-label="Email address">
      <button type="submit">Tune In</button>
    </form>
    <div class="gtv-sub-msg" id="gtv-sub-msg" role="status"></div>
  </section>

</main>
{get_site_header_js()}
<script>
(function() {{
  var form = document.getElementById('gtv-sub-form');
  var msg = document.getElementById('gtv-sub-msg');
  if (!form) return;
  form.addEventListener('submit', function(e) {{
    e.preventDefault();
    var email = form.email.value.trim();
    if (!email) return;
    var payload = {{
      email: email,
      race_slug: '',
      race_name: 'Gravel TV',
      source: 'gravel_tv_subscribe',
      website: form.website.value
    }};
    fetch('{LEAD_WORKER_URL}', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify(payload)
    }}).then(function() {{
      msg.textContent = "You're on the air. First broadcast lands this week.";
      form.email.value = '';
      if (typeof gtag === 'function') {{
        gtag('event', 'gravel_tv_subscribe', {{ source: 'gravel_tv_page' }});
      }}
    }}).catch(function() {{
      msg.textContent = 'Transmission failed — try again.';
    }});
  }});
}})();
</script>
</body>
</html>'''


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    page = build_page()
    OUTPUT.write_text(page)
    print(f"Generated {OUTPUT} ({len(page):,} bytes)")


if __name__ == '__main__':
    main()
