#!/usr/bin/env python3
"""
Generate the Gravel God homepage in Desert Editorial style.

Leads with the race database as the primary value prop, includes stats bar,
featured T1 races, race calendar, training guide preview, how-it-works funnel,
featured-in logos, training CTA, newsletter with article carousel, and footer.

Usage:
    python generate_homepage.py
    python generate_homepage.py --output-dir ./output
"""

import argparse
import html
import json
import random
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

# Import shared constants from the race page generator
from generate_neo_brutalist import (
    SITE_BASE_URL,
    SUBSTACK_URL,
    SUBSTACK_EMBED,
    COACHING_URL,
    TRAINING_PLANS_URL,
)

OUTPUT_DIR = Path(__file__).parent / "output"
RACE_INDEX_PATH = Path(__file__).parent.parent / "web" / "race-index.json"
RACE_DATA_DIR = Path(__file__).parent.parent / "race-data"
GUIDE_CONTENT_PATH = Path(__file__).parent.parent / "guide" / "gravel-guide-content.json"
SUBSTACK_RSS_URL = "https://gravelgodcycling.substack.com/feed"

GA4_MEASUREMENT_ID = "G-EJJZ9T6M52"

# ── Featured race slugs (curated for homepage diversity) ─────

FEATURED_SLUGS = [
    "unbound-gravel",
    "mid-south",
    "badlands",
    "steamboat-gravel",
    "the-traka",
    "belgian-waffle-ride",
]

# ── Featured on-site articles (curated for homepage voice) ──────
# These are the "saucy takes" that show personality and editorial voice.
# Each entry: (title, url_path, category_tag, teaser)
# Update FEATURED_ONSITE_UPDATED when you change these articles.

FEATURED_ONSITE_UPDATED = "2026-02-10"  # YYYY-MM-DD — last time articles were curated

FEATURED_ONSITE_ARTICLES = [
    (
        "I Opened a FasCat AI Coaching Email So You Don't Have To",
        "/i-opened-a-fascat-ai-coaching-email-so-you-dont-have-to/",
        "CONTROVERSIAL OPINION",
        "What happens when AI tries to coach cyclists? We opened the email so you can skip the sales pitch.",
    ),
    (
        "Maybe a Hater Poster is What You've Been Missing",
        "/maybe-a-hate-poster-is-what-youve-been-missing/",
        "MINDSET",
        "Sometimes the best motivation isn't a quote from Marcus Aurelius. Sometimes it's spite.",
    ),
    (
        "I Messed Up Big Horn Gravel So You Don't Have To",
        "/i-messed-up-big-horn-gravel-so-you-dont-have-to/",
        "RACE REPORT",
        "Every mistake you can make in a gravel race, catalogued for your benefit. You're welcome.",
    ),
]


def esc(text) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


# ── Data loading ─────────────────────────────────────────────


def load_race_index(index_path: Path = None) -> list:
    """Load race-index.json and return list of race dicts."""
    path = index_path or RACE_INDEX_PATH
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compute_stats(race_index: list) -> dict:
    """Compute homepage statistics from the race index."""
    race_count = len(race_index)
    t1_count = sum(1 for r in race_index if r.get("tier") == 1)
    return {
        "race_count": race_count,
        "dimensions": 14,
        "t1_count": t1_count,
    }


def get_featured_races(race_index: list) -> list:
    """Return featured race dicts from the index, falling back to top T1 by score."""
    by_slug = {r["slug"]: r for r in race_index}
    featured = []
    for slug in FEATURED_SLUGS:
        if slug in by_slug:
            featured.append(by_slug[slug])
    # Fallback: fill remaining slots with top T1 races by score
    if len(featured) < 6:
        t1_races = sorted(
            [r for r in race_index if r.get("tier") == 1 and r not in featured],
            key=lambda r: r.get("overall_score", 0),
            reverse=True,
        )
        for r in t1_races:
            if len(featured) >= 6:
                break
            featured.append(r)
    return featured


def load_editorial_one_liners(race_data_dir: Path = None) -> list:
    """Load punchy one-liners from T1/T2 race profiles for the ticker."""
    data_dir = race_data_dir or RACE_DATA_DIR
    one_liners = []
    for f in sorted(data_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            race = data.get("race", data)
            tier = race.get("gravel_god_rating", {}).get("tier", 4)
            if tier > 2:
                continue
            name = race.get("display_name") or race.get("name", "")
            slug = race.get("slug", f.stem)
            score = race.get("gravel_god_rating", {}).get("overall_score", 0)
            fv = race.get("final_verdict", {})
            one_liner = fv.get("one_liner", "").strip()
            if one_liner:
                one_liners.append({
                    "name": name, "slug": slug, "score": score,
                    "tier": tier, "text": one_liner,
                })
        except (json.JSONDecodeError, KeyError):
            continue
    return one_liners


def load_upcoming_races(race_data_dir: Path = None, today: date = None) -> list:
    """Parse date_specific from profiles to find upcoming and recent races."""
    data_dir = race_data_dir or RACE_DATA_DIR
    today = today or date.today()
    races = []
    for f in sorted(data_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            race = data.get("race", data)
            ds = race.get("vitals", {}).get("date_specific", "")
            m = re.match(r"(\d{4}):\s*(\w+)\s+(\d+)", ds)
            if not m:
                continue
            year, month_name, day = m.groups()
            race_date = datetime.strptime(f"{year} {month_name} {day}", "%Y %B %d").date()
            diff = (race_date - today).days
            if diff < -14 or diff > 60:
                continue
            name = race.get("display_name") or race.get("name", "")
            slug = race.get("slug", f.stem)
            tier = race.get("gravel_god_rating", {}).get("tier", 4)
            score = race.get("gravel_god_rating", {}).get("overall_score", 0)
            location = race.get("vitals", {}).get("location", "")
            races.append({
                "name": name, "slug": slug, "tier": tier, "score": score,
                "date": race_date, "days": diff, "location": location,
            })
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    races.sort(key=lambda r: r["date"])
    return races


def fetch_substack_posts(limit: int = 6) -> list:
    """Fetch latest posts from Substack RSS with titles, URLs, and snippets."""
    try:
        req = urllib.request.Request(SUBSTACK_RSS_URL, headers={"User-Agent": "GravelGod/1.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        root = ET.fromstring(resp.read())
        posts = []
        for item in root.findall(".//item")[:limit]:
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            if title_el is not None and title_el.text:
                snippet = ""
                if desc_el is not None and desc_el.text:
                    snippet = re.sub(r"<[^>]+>", "", desc_el.text)[:120].strip()
                posts.append({
                    "title": title_el.text.strip(),
                    "url": link_el.text.strip() if link_el is not None and link_el.text else "",
                    "snippet": snippet,
                })
        return posts
    except Exception:
        return []


def load_guide_chapters(guide_path: Path = None) -> list:
    """Load chapter titles from the guide content JSON."""
    path = guide_path or GUIDE_CONTENT_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [
            {
                "number": ch["number"],
                "title": ch["title"],
                "subtitle": ch.get("subtitle", ""),
                "gated": ch.get("gated", False),
            }
            for ch in data.get("chapters", [])
        ]
    except (json.JSONDecodeError, FileNotFoundError):
        return []


# ── Section builders ─────────────────────────────────────────


def build_nav() -> str:
    return f'''<header class="gg-hp-header">
    <div class="gg-hp-header-inner">
      <a href="{SITE_BASE_URL}/" class="gg-hp-header-logo">
        <img src="https://gravelgodcycling.com/wp-content/uploads/2021/09/cropped-Gravel-God-logo.png" alt="Gravel God" width="50" height="50">
      </a>
      <nav class="gg-hp-header-nav">
        <a href="{SITE_BASE_URL}/gravel-races/">RACES</a>
        <a href="{SITE_BASE_URL}/coaching/">COACHING</a>
        <a href="{SITE_BASE_URL}/articles/">ARTICLES</a>
        <a href="{SITE_BASE_URL}/about/">ABOUT</a>
      </nav>
    </div>
  </header>'''


def build_ticker(one_liners: list, substack_posts: list, upcoming: list) -> str:
    """Build the scrolling ticker with editorial one-liners, Substack posts, and race alerts."""
    items = []

    # Races happening this week (next 7 days) or just happened (last 3 days)
    for race in upcoming:
        d = race["days"]
        if d == 0:
            items.append(f'<span class="gg-ticker-tag gg-ticker-tag--red">RACE DAY</span> '
                         f'<a href="{SITE_BASE_URL}/race/{esc(race["slug"])}/">{esc(race["name"])}</a>')
        elif 1 <= d <= 7:
            items.append(f'<span class="gg-ticker-tag gg-ticker-tag--teal">THIS WEEK</span> '
                         f'<a href="{SITE_BASE_URL}/race/{esc(race["slug"])}/">{esc(race["name"])}</a> &mdash; {d} day{"s" if d != 1 else ""}')
        elif -3 <= d < 0:
            items.append(f'<span class="gg-ticker-tag gg-ticker-tag--gold">JUST RACED</span> '
                         f'<a href="{SITE_BASE_URL}/race/{esc(race["slug"])}/">{esc(race["name"])}</a>')

    # Substack posts
    for post in substack_posts:
        items.append(f'<span class="gg-ticker-tag gg-ticker-tag--brown">NEWSLETTER</span> '
                     f'<a href="{esc(post["url"])}">{esc(post["title"])}</a>')

    # Editorial one-liners (random sample, rotates daily)
    sample_size = min(8, len(one_liners))
    if one_liners:
        random.seed(date.today().toordinal())  # Rotates daily, deterministic within a day
        sampled = random.sample(one_liners, sample_size)
        for ol in sampled:
            text = ol["text"][:100] + ("..." if len(ol["text"]) > 100 else "")
            items.append(
                f'<span class="gg-ticker-tag gg-ticker-tag--teal">T{ol["tier"]}</span> '
                f'<a href="{SITE_BASE_URL}/race/{esc(ol["slug"])}/">{esc(ol["name"])}</a>: '
                f'&ldquo;{esc(text)}&rdquo;'
            )

    if not items:
        return ""

    # Duplicate items for seamless loop
    separator = '<span class="gg-hp-ticker-sep">&bull;</span>'
    content = separator.join(f'<span class="gg-hp-ticker-item">{item}</span>' for item in items)

    # Mobile: show the first (most important) item as a static line
    mobile_item = items[0] if items else ""

    return f'''<div class="gg-hp-ticker" aria-label="Race news ticker">
    <div class="gg-hp-ticker-track">
      <div class="gg-hp-ticker-content">{content}{separator}{content}</div>
    </div>
  </div>
  <div class="gg-hp-ticker-mobile" aria-label="Latest update">
    <span class="gg-hp-ticker-item">{mobile_item}</span>
  </div>'''


def build_coming_up(upcoming: list) -> str:
    """Build the 'Coming Up' section showing races in the next 30-60 days."""
    future = [r for r in upcoming if r["days"] >= 0]
    recent = [r for r in upcoming if r["days"] < 0]

    if not future and not recent:
        return f'''<section class="gg-hp-coming-up" id="coming-up">
    <div class="gg-hp-section-header">
      <h2>COMING UP</h2>
    </div>
    <div class="gg-hp-cal-offseason">
      Off-season. The next wave of races is loading. <a href="{SITE_BASE_URL}/gravel-races/">Browse all races &rarr;</a>
    </div>
  </section>'''

    items = ""

    # Show recently finished (last 14 days)
    if recent:
        for race in recent[-2:]:  # Last 2
            days_ago = abs(race["days"])
            badge_cls = _tier_badge_class(race["tier"])
            items += f'''
        <a href="{SITE_BASE_URL}/race/{esc(race['slug'])}/" class="gg-hp-cal-item gg-hp-cal-item--past">
          <span class="gg-hp-cal-date">{race["date"].strftime("%b %d")}</span>
          <span class="gg-hp-cal-badge {badge_cls}">T{race["tier"]}</span>
          <span class="gg-hp-cal-info">
            <span class="gg-hp-cal-name">{esc(race["name"])}</span>
            <span class="gg-hp-cal-meta">{esc(race["location"])} &middot; {days_ago}d ago</span>
          </span>
          <span class="gg-hp-cal-score">{race["score"]}</span>
        </a>'''

    # Show upcoming (next 60 days)
    for race in future[:5]:
        d = race["days"]
        if d == 0:
            urgency = "gg-hp-cal-item--today"
            label = "TODAY"
        elif d <= 7:
            urgency = "gg-hp-cal-item--soon"
            label = f"{d}d"
        else:
            urgency = ""
            label = f"{d}d"
        badge_cls = _tier_badge_class(race["tier"])
        items += f'''
        <a href="{SITE_BASE_URL}/race/{esc(race['slug'])}/" class="gg-hp-cal-item {urgency}">
          <span class="gg-hp-cal-date">{race["date"].strftime("%b %d")}</span>
          <span class="gg-hp-cal-badge {badge_cls}">T{race["tier"]}</span>
          <span class="gg-hp-cal-info">
            <span class="gg-hp-cal-name">{esc(race["name"])}</span>
            <span class="gg-hp-cal-meta">{esc(race["location"])} &middot; {label}</span>
          </span>
          <span class="gg-hp-cal-score">{race["score"]}</span>
        </a>'''

    return f'''<section class="gg-hp-coming-up" id="coming-up">
    <div class="gg-hp-section-header">
      <h2>COMING UP</h2>
    </div>
    <div class="gg-hp-cal-list">{items}
    </div>
    <div class="gg-hp-cal-cta">
      <a href="{SITE_BASE_URL}/gravel-races/" class="gg-hp-btn gg-hp-btn--primary" data-ga="view_all_races" data-ga-label="calendar">FULL RACE CALENDAR &rarr;</a>
    </div>
  </section>'''


def build_guide_preview(chapters: list) -> str:
    """Build the guide preview section with chapter list and email gate pitch."""
    if not chapters:
        return ""

    items = ""
    for ch in chapters:
        if ch["gated"]:
            lock = ' <span class="gg-hp-guide-lock">&#128274;</span>'
            tag = '<span class="gg-hp-guide-email-tag">EMAIL TO UNLOCK</span>'
        else:
            lock = ""
            tag = '<span class="gg-hp-guide-free">FREE</span>'
        items += f'''
      <a href="{SITE_BASE_URL}/guide/#ch{ch["number"]}" class="gg-hp-guide-ch">
        <span class="gg-hp-guide-num">CH {ch["number"]}</span>
        <span class="gg-hp-guide-title">{esc(ch["title"])}{lock}</span>
        <span class="gg-hp-guide-sub">{esc(ch["subtitle"])} {tag}</span>
      </a>'''

    return f'''<section class="gg-hp-guide" id="guide">
    <div class="gg-hp-section-header gg-hp-section-header--teal">
      <h2>THE GRAVEL TRAINING GUIDE</h2>
    </div>
    <div class="gg-hp-guide-intro">
      <p>Everything you need to know about gravel racing &mdash; from what to buy to how to train to race-day execution. 8 chapters, written by coaches who actually race gravel.</p>
      <p class="gg-hp-guide-deal"><strong>The deal:</strong> Chapters 1&ndash;3 are free. Drop your email to unlock the full guide &mdash; nutrition, race tactics, race week protocol, and more.</p>
    </div>
    <div class="gg-hp-guide-grid">{items}
    </div>
    <div class="gg-hp-guide-cta">
      <a href="{SITE_BASE_URL}/guide/" class="gg-hp-btn gg-hp-btn--primary" data-ga="guide_click">READ FREE CHAPTERS &rarr;</a>
    </div>
  </section>'''


def build_hero(stats: dict) -> str:
    race_count = stats["race_count"]
    return f'''<section class="gg-hp-hero" id="main">
    <div class="gg-hp-hero-badge">{race_count} RACES RATED</div>
    <h1>EVERY GRAVEL RACE. RATED. RANKED.</h1>
    <p class="gg-hp-hero-tagline">The definitive gravel race database. 14 dimensions. No sponsors. No pay-to-play. Just honest ratings &mdash; plus coaching and training for people with real lives who still want to go fast.</p>
    <form class="gg-hp-hero-search" action="{SITE_BASE_URL}/gravel-races/" method="get" data-ga="hero_search">
      <input type="text" name="q" placeholder="Search 328 races &mdash; try &ldquo;Colorado&rdquo; or &ldquo;200 miles&rdquo;" class="gg-hp-hero-input" aria-label="Search races">
      <button type="submit" class="gg-hp-hero-search-btn">SEARCH</button>
    </form>
    <div class="gg-hp-hero-ctas">
      <a href="{SITE_BASE_URL}/gravel-races/" class="gg-hp-btn gg-hp-btn--primary" data-ga="hero_cta_click">BROWSE ALL RACES</a>
      <a href="{SITE_BASE_URL}/race/methodology/" class="gg-hp-btn gg-hp-btn--secondary" data-ga="hero_secondary_click">HOW WE RATE</a>
    </div>
  </section>'''


def build_stats_bar(stats: dict) -> str:
    items = [
        (stats["race_count"], "Races Rated"),
        (stats["dimensions"], "Scoring Dimensions"),
        (stats["t1_count"], "Tier 1 Elite Races"),
        (0, "Sponsors"),
    ]
    cells = ""
    for value, label in items:
        cells += f'''
      <div class="gg-hp-stat">
        <span class="gg-hp-stat-number">{value}</span>
        <span class="gg-hp-stat-label">{esc(label)}</span>
      </div>'''
    return f'''<section class="gg-hp-stats-bar">{cells}
  </section>'''


def _tier_badge_class(tier: int) -> str:
    """Return CSS class for a tier badge."""
    return f"gg-hp-badge-t{tier}" if 1 <= tier <= 4 else "gg-hp-badge-t4"


def _format_month(month: str) -> str:
    """Return abbreviated 3-letter month."""
    if not month:
        return ""
    return month[:3].upper()


def build_featured_races(race_index: list) -> str:
    featured = get_featured_races(race_index)
    stats = compute_stats(race_index)
    cards = ""
    for race in featured:
        tier = race.get("tier", 4)
        score = race.get("overall_score", 0)
        name = race.get("name", "")
        slug = race.get("slug", "")
        location = race.get("location", "")
        distance = race.get("distance_mi")
        month = race.get("month", "")
        tagline = race.get("tagline", "")
        profile_url = race.get("profile_url", f"/race/{slug}/")

        meta_parts = []
        if location:
            meta_parts.append(esc(location))
        if distance:
            meta_parts.append(f"{distance} mi")
        if month:
            meta_parts.append(_format_month(month))
        meta_str = " &middot; ".join(meta_parts)

        badge_cls = _tier_badge_class(tier)

        cards += f'''
      <a href="{SITE_BASE_URL}{esc(profile_url)}" class="gg-hp-race-card" data-ga="featured_race_click" data-ga-label="{esc(name)}">
        <div class="gg-hp-race-card-top">
          <span class="gg-hp-tier-badge {badge_cls}">TIER {tier}</span>
          <span class="gg-hp-score">{score}</span>
        </div>
        <h3 class="gg-hp-race-name">{esc(name)}</h3>
        <div class="gg-hp-race-meta">{meta_str}</div>
        <p class="gg-hp-race-tagline">{esc(tagline[:120]) + ("..." if len(tagline) > 120 else "")}</p>
      </a>'''

    return f'''<section class="gg-hp-featured" id="featured">
    <div class="gg-hp-section-header">
      <h2>FEATURED RACES</h2>
    </div>
    <div class="gg-hp-race-grid">{cards}
    </div>
    <div class="gg-hp-featured-cta">
      <a href="{SITE_BASE_URL}/gravel-races/" class="gg-hp-btn gg-hp-btn--primary" data-ga="view_all_races">VIEW ALL {stats["race_count"]} RACES &rarr;</a>
      <div class="gg-hp-quick-filters">
        <span class="gg-hp-quick-label">QUICK FILTER:</span>
        <a href="{SITE_BASE_URL}/gravel-races/?tier=1" class="gg-hp-quick-chip" data-ga="quick_tier1">TIER 1</a>
        <a href="{SITE_BASE_URL}/gravel-races/?tier=2" class="gg-hp-quick-chip" data-ga="quick_tier2">TIER 2</a>
        <a href="{SITE_BASE_URL}/gravel-races/?region=West" class="gg-hp-quick-chip" data-ga="quick_west">WEST</a>
        <a href="{SITE_BASE_URL}/gravel-races/?region=Midwest" class="gg-hp-quick-chip" data-ga="quick_midwest">MIDWEST</a>
        <a href="{SITE_BASE_URL}/gravel-races/?region=South" class="gg-hp-quick-chip" data-ga="quick_south">SOUTH</a>
        <a href="{SITE_BASE_URL}/gravel-races/?region=Northeast" class="gg-hp-quick-chip" data-ga="quick_ne">NORTHEAST</a>
        <a href="{SITE_BASE_URL}/gravel-races/?region=International" class="gg-hp-quick-chip" data-ga="quick_intl">INTERNATIONAL</a>
        <a href="{SITE_BASE_URL}/gravel-races/?nearme=1" class="gg-hp-quick-chip gg-hp-quick-chip--accent" data-ga="quick_nearme">NEAR ME</a>
        <a href="{SITE_BASE_URL}/gravel-races/?view=calendar" class="gg-hp-quick-chip gg-hp-quick-chip--accent" data-ga="quick_calendar">CALENDAR</a>
      </div>
    </div>
  </section>'''


def build_latest_takes() -> str:
    """Build the 'Latest Takes' section with curated on-site article cards."""
    if not FEATURED_ONSITE_ARTICLES:
        return ""

    # Warn if articles haven't been updated in >90 days
    try:
        updated = datetime.strptime(FEATURED_ONSITE_UPDATED, "%Y-%m-%d").date()
        stale_days = (date.today() - updated).days
        if stale_days > 90:
            import sys
            print(f"  WARNING: FEATURED_ONSITE_ARTICLES last updated {stale_days} days ago. "
                  f"Consider refreshing the homepage article picks.", file=sys.stderr)
    except (ValueError, TypeError):
        pass

    cards = ""
    for title, url_path, tag, teaser in FEATURED_ONSITE_ARTICLES:
        cards += f'''
      <a href="{SITE_BASE_URL}{esc(url_path)}" class="gg-hp-take-card" data-ga="article_click" data-ga-label="{esc(title)}">
        <span class="gg-hp-take-tag">{esc(tag)}</span>
        <h3 class="gg-hp-take-title">{esc(title)}</h3>
        <p class="gg-hp-take-teaser">{esc(teaser)}</p>
        <span class="gg-hp-take-read">READ &rarr;</span>
      </a>'''

    return f'''<section class="gg-hp-latest-takes" id="takes">
    <div class="gg-hp-section-header gg-hp-section-header--gold">
      <h2>LATEST TAKES</h2>
    </div>
    <div class="gg-hp-take-grid">{cards}
    </div>
    <div class="gg-hp-take-cta">
      <a href="{SITE_BASE_URL}/articles/" class="gg-hp-btn gg-hp-btn--primary" data-ga="view_all_articles">ALL ARTICLES &rarr;</a>
    </div>
  </section>'''


def build_how_it_works(stats: dict = None) -> str:
    race_count = stats["race_count"] if stats else 328
    steps = [
        ("01", "PICK YOUR RACE", f"{race_count} races. Scored honestly. Filter by what actually matters to you &mdash; not what a sponsor paid us to promote."),
        ("02", "READ THE REAL TAKE", "Every rating comes with an editorial opinion. We tell you if it&rsquo;s worth the flight, the entry fee, and the suffering."),
        ("03", "SHOW UP READY", "Race-specific training plans and a 30-page guide so you don&rsquo;t blow up at mile 60 like we did."),
    ]
    cells = ""
    for num, title, desc in steps:
        cells += f'''
      <div class="gg-hp-step">
        <span class="gg-hp-step-num">{num}</span>
        <h3 class="gg-hp-step-title">{title}</h3>
        <p class="gg-hp-step-desc">{desc}</p>
      </div>'''
    return f'''<section class="gg-hp-how-it-works">{cells}
  </section>'''


FEATURED_IN = [
    {
        "name": "TrainingPeaks",
        "url": "https://www.trainingpeaks.com",
        "logo": "https://gravelgodcycling.com/wp-content/uploads/2025/12/TP_Preferred_Vertical-Logo-Blue-Navy.HighRes-scaled.png",
    },
    {
        "name": "The Better Podcast",
        "url": "https://open.spotify.com/show/4NyQFbuHNyS8OHOla8NoZP",
        "logo": "https://gravelgodcycling.com/wp-content/uploads/2025/12/Untitled-design-1.png",
    },
    {
        "name": "Training Babble Podcast",
        "url": "https://open.spotify.com/episode/03NpuD7U0CNX1dSJGa8tlm",
        "logo": "https://gravelgodcycling.com/wp-content/uploads/2025/12/Untitled-design-2.png",
    },
]


def build_featured_in() -> str:
    logos = ""
    for item in FEATURED_IN:
        logos += f'''
      <a class="gg-hp-feat-logo" href="{esc(item["url"])}" target="_blank" rel="noopener">
        <img src="{esc(item["logo"])}" alt="{esc(item["name"])}" loading="lazy">
      </a>'''
    return f'''<section class="gg-hp-featured-in">
    <div class="gg-hp-feat-inner">
      <div class="gg-hp-feat-text">
        <span class="gg-hp-feat-label">AS FEATURED IN</span>
        <p class="gg-hp-feat-copy">Trusted by coaches, podcasters, and the gravel community.</p>
      </div>
      <div class="gg-hp-feat-logos">{logos}
      </div>
    </div>
  </section>'''


def build_training_cta() -> str:
    return f'''<section class="gg-hp-training" id="training">
    <div class="gg-hp-section-header gg-hp-section-header--teal">
      <h2>RACE-SPECIFIC TRAINING</h2>
    </div>
    <div class="gg-hp-training-grid">
      <div class="gg-hp-training-card gg-hp-training-card--primary">
        <h3>Training Plans</h3>
        <p class="gg-hp-training-subtitle">Race-specific. Built for your target event. $15/week, capped at $199.</p>
        <ul class="gg-hp-training-bullets">
          <li>Structured workouts pushed to your device</li>
          <li>30+ page custom training guide</li>
          <li>Heat &amp; altitude protocols</li>
          <li>Nutrition &amp; strength training</li>
        </ul>
        <a href="{esc(TRAINING_PLANS_URL)}" class="gg-hp-btn gg-hp-btn--primary" data-ga="training_plan_click">BUILD MY PLAN</a>
      </div>
      <div class="gg-hp-training-card gg-hp-training-card--secondary">
        <h3>1:1 Coaching</h3>
        <p class="gg-hp-training-subtitle">A human in your corner. Adapts week to week.</p>
        <p>Your coach reviews every session, adjusts when life happens, and builds race-day strategy with you. Not a plan &mdash; a partnership.</p>
        <a href="{esc(COACHING_URL)}" class="gg-hp-btn gg-hp-btn--secondary" target="_blank" rel="noopener" data-ga="coaching_click">APPLY</a>
      </div>
    </div>
  </section>'''


def build_email_capture(posts: list = None) -> str:
    articles = posts or []

    cards = ""
    for post in articles[:6]:
        title = esc(post.get("title", ""))
        url = esc(post.get("url", ""))
        snippet = esc(post.get("snippet", ""))
        cards += f'''
        <a href="{url}" class="gg-hp-article-card" target="_blank" rel="noopener" data-ga="article_click" data-ga-label="{title}">
          <h3 class="gg-hp-article-title">{title}</h3>
          <p class="gg-hp-article-snippet">{snippet}</p>
        </a>'''

    carousel = ""
    if cards:
        carousel = f'''
    <div class="gg-hp-article-carousel">{cards}
    </div>'''

    return f'''<section class="gg-hp-email" id="newsletter">
    <div class="gg-hp-email-inner">
      <span class="gg-hp-email-label">NEWSLETTER</span>
      <h2 class="gg-hp-email-title">Slow, Mid, 38s</h2>
      <p class="gg-hp-email-text">Essays on training, meaning, and not majoring in the minors.</p>
    </div>{carousel}
    <div class="gg-hp-email-form">
      <iframe src="{esc(SUBSTACK_EMBED)}" width="100%" height="150" style="border:none; background:transparent;" frameborder="0" scrolling="no" loading="lazy"></iframe>
    </div>
  </section>'''


def build_footer() -> str:
    return f'''<footer class="gg-hp-footer">
    <div class="gg-hp-footer-grid">
      <div class="gg-hp-footer-brand">
        <h3 class="gg-hp-footer-title">GRAVEL GOD CYCLING</h3>
        <p class="gg-hp-footer-tagline">Practical coaching and training for people with real lives who still want to go fast.</p>
      </div>
      <div class="gg-hp-footer-nav">
        <h4 class="gg-hp-footer-heading">EXPLORE</h4>
        <a href="{SITE_BASE_URL}/coaching/">&rarr; Coaching</a>
        <a href="{SITE_BASE_URL}/products/training-plans/">&rarr; Training Plans</a>
        <a href="{SITE_BASE_URL}/gravel-races/">&rarr; All Races</a>
        <a href="{SITE_BASE_URL}/articles/">&rarr; Articles</a>
        <a href="{SITE_BASE_URL}/about/">&rarr; About</a>
      </div>
      <div class="gg-hp-footer-newsletter">
        <h4 class="gg-hp-footer-heading">NEWSLETTER</h4>
        <p>Slow, Mid, 38s &mdash; essays on training, meaning, and not majoring in the minors.</p>
        <a href="{esc(SUBSTACK_URL)}" class="gg-hp-footer-subscribe" target="_blank" rel="noopener" data-ga="subscribe_click" data-ga-label="footer">SUBSCRIBE</a>
      </div>
    </div>
    <div class="gg-hp-footer-legal">
      <span>&copy; 2026 Gravel God Cycling. All rights reserved.</span>
    </div>
  </footer>'''


# ── CSS ──────────────────────────────────────────────────────


def build_homepage_css() -> str:
    return '''<style>
/* ── Ticker (functional animation) ───────────────────────── */
@keyframes gg-ticker-scroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }

/* ── Custom properties ───────────────────────────────────── */
:root { --gg-ease: var(--gg-ease); }

/* ── Reset & base ────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Source Serif 4', Georgia, serif; color: #3a2e25; line-height: 1.75; background: #ede4d8; margin: 0; }
a { text-decoration: none; color: #178079; }

/* ── Page container ──────────────────────────────────────── */
.gg-hp-page { margin: 0; padding: 0; }

/* ── Header ──────────────────────────────────────────────── */
.gg-hp-header { padding: 16px 24px; border-bottom: 4px solid #3a2e25; }
.gg-hp-header-inner { display: flex; align-items: center; justify-content: space-between; max-width: 1200px; margin: 0 auto; }
.gg-hp-header-logo img { display: block; height: 50px; width: auto; }
.gg-hp-header-nav { display: flex; gap: 28px; }
.gg-hp-header-nav a { color: #3a2e25; text-decoration: none; font-family: 'Sometype Mono', monospace; font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; transition: color var(--gg-ease); }
.gg-hp-header-nav a:hover { color: #9a7e0a; }

/* ── Ticker ──────────────────────────────────────────────── */
.gg-hp-ticker { background: #1a1613; border-bottom: 3px solid #9a7e0a; overflow: hidden; white-space: nowrap; }
.gg-hp-ticker-track { overflow: hidden; }
.gg-hp-ticker-content { display: inline-block; animation: gg-ticker-scroll 60s linear infinite; padding: 10px 0; }
.gg-hp-ticker-content:hover { animation-play-state: paused; }
.gg-hp-ticker-item { font-family: 'Sometype Mono', monospace; font-size: 11px; color: #7d695d; letter-spacing: 0.5px; }
.gg-hp-ticker-item a { color: #d4c5b9; text-decoration: none; transition: color var(--gg-ease); }
.gg-hp-ticker-item a:hover { color: #f5efe6; }
.gg-hp-ticker-sep { color: #3a2e25; margin: 0 20px; }
.gg-ticker-tag { display: inline-block; padding: 1px 6px; font-family: 'Sometype Mono', monospace; font-size: 9px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; margin-right: 6px; }
.gg-ticker-tag--teal { background: #178079; color: #fff; }
.gg-ticker-tag--gold { background: #9a7e0a; color: #fff; }
.gg-ticker-tag--brown { background: #59473c; color: #fff; }
.gg-ticker-tag--red { background: #c0392b; color: #fff; }
.gg-hp-ticker-mobile { display: none; }

/* ── Hero ─────────────────────────────────────────────────── */
.gg-hp-hero { background: #59473c; color: #fff; padding: 64px 48px; border-bottom: 3px solid #9a7e0a; }
.gg-hp-hero-badge { display: inline-block; font-family: 'Sometype Mono', monospace; font-size: 12px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; color: #9a7e0a; border: 2px solid #9a7e0a; padding: 6px 16px; margin-bottom: 24px; }
.gg-hp-hero h1 { font-family: 'Source Serif 4', Georgia, serif; font-size: 48px; font-weight: 700; line-height: 1.1; letter-spacing: -0.5px; margin-bottom: 20px; }
.gg-hp-hero-tagline { font-family: 'Source Serif 4', Georgia, serif; font-size: 18px; line-height: 1.75; color: #d4c5b9; max-width: 640px; margin-bottom: 36px; }
.gg-hp-hero-search { display: flex; max-width: 560px; margin-bottom: 20px; }
.gg-hp-hero-input { flex: 1; padding: 14px 16px; font-family: 'Sometype Mono', monospace; font-size: 12px; letter-spacing: 0.5px; background: rgba(255,255,255,0.08); color: #f5efe6; border: 2px solid #7d695d; border-right: none; outline: none; }
.gg-hp-hero-input::placeholder { color: #7d695d; }
.gg-hp-hero-input:focus { border-color: #9a7e0a; background: rgba(255,255,255,0.12); }
.gg-hp-hero-search-btn { padding: 14px 24px; font-family: 'Sometype Mono', monospace; font-size: 12px; font-weight: 700; letter-spacing: 2px; background: #9a7e0a; color: #fff; border: 2px solid #9a7e0a; cursor: pointer; }
.gg-hp-hero-search-btn:hover { background: #d4af0f; border-color: #d4af0f; }
.gg-hp-hero-ctas { display: flex; gap: 16px; flex-wrap: wrap; }

/* ── Buttons ─────────────────────────────────────────────── */
.gg-hp-btn { display: inline-block; padding: 14px 32px; font-family: 'Sometype Mono', monospace; font-size: 12px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; text-align: center; cursor: pointer; border: 3px solid transparent; transition: background-color var(--gg-ease), border-color var(--gg-ease), color var(--gg-ease); }
.gg-hp-btn--primary { background: #f5efe6; color: #3a2e25; border-color: #3a2e25; }
.gg-hp-btn--primary:hover { border-color: #9a7e0a; color: #9a7e0a; }
.gg-hp-btn--secondary { background: transparent; color: #d4c5b9; border-color: #d4c5b9; }
.gg-hp-btn--secondary:hover { color: #fff; border-color: #9a7e0a; }
/* On light backgrounds, dark button variant */
.gg-hp-featured-cta .gg-hp-btn--primary,
.gg-hp-cal-cta .gg-hp-btn--primary,
.gg-hp-guide-cta .gg-hp-btn--primary { background: #59473c; color: #fff; border-color: #3a2e25; }
.gg-hp-featured-cta .gg-hp-btn--primary:hover,
.gg-hp-cal-cta .gg-hp-btn--primary:hover,
.gg-hp-guide-cta .gg-hp-btn--primary:hover { border-color: #9a7e0a; color: #fff; }
.gg-hp-training .gg-hp-btn--primary { background: #59473c; color: #fff; border-color: #3a2e25; }
.gg-hp-training .gg-hp-btn--primary:hover { border-color: #9a7e0a; }
.gg-hp-training .gg-hp-btn--secondary { background: #f5efe6; color: #59473c; border-color: #59473c; }
.gg-hp-training .gg-hp-btn--secondary:hover { background: #59473c; color: #fff; }

/* ── Stats bar ───────────────────────────────────────────── */
.gg-hp-stats-bar { background: #1a1613; display: grid; grid-template-columns: repeat(4, 1fr); border-bottom: 4px double #3a2e25; }
.gg-hp-stat { text-align: center; padding: 32px 16px; border-right: 2px solid #3a2e25; }
.gg-hp-stat:last-child { border-right: none; }
.gg-hp-stat-number { display: block; font-family: 'Sometype Mono', monospace; font-size: 44px; font-weight: 700; color: #fff; line-height: 1.1; margin-bottom: 8px; }
.gg-hp-stat-label { display: block; font-family: 'Sometype Mono', monospace; font-size: 10px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; color: #7d695d; }

/* ── Section headers ─────────────────────────────────────── */
.gg-hp-section-header { background: #59473c; padding: 16px 20px; border-bottom: 4px double #3a2e25; }
.gg-hp-section-header h2 { font-family: 'Sometype Mono', monospace; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 3px; color: #f5efe6; margin: 0; }
.gg-hp-section-header--teal { background: #178079; }

/* ── Featured races ──────────────────────────────────────── */
.gg-hp-featured { max-width: 1200px; margin: 32px auto 0; border: 3px solid #3a2e25; }
.gg-hp-race-grid { display: grid; grid-template-columns: repeat(3, 1fr); }
.gg-hp-race-card { display: block; padding: 24px; border: 1px solid #d4c5b9; text-decoration: none; color: #3a2e25; background: #f5efe6; transition: border-color var(--gg-ease); }
.gg-hp-race-card:hover { border-color: #9a7e0a; }
.gg-hp-race-card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.gg-hp-tier-badge { display: inline-block; font-family: 'Sometype Mono', monospace; padding: 3px 10px; font-size: 9px; font-weight: 700; letter-spacing: 2px; }
.gg-hp-badge-t1 { background: #59473c; color: #fff; }
.gg-hp-badge-t2 { background: #7d695d; color: #fff; }
.gg-hp-badge-t3 { background: transparent; color: #766a5e; border: 2px solid #766a5e; }
.gg-hp-badge-t4 { background: transparent; color: #5e6868; border: 2px solid #5e6868; }
.gg-hp-score { font-family: 'Sometype Mono', monospace; font-size: 28px; font-weight: 700; color: #178079; }
.gg-hp-race-name { font-family: 'Source Serif 4', Georgia, serif; font-size: 16px; font-weight: 700; line-height: 1.1; margin-bottom: 6px; }
.gg-hp-race-meta { font-family: 'Sometype Mono', monospace; font-size: 10px; color: #7d695d; letter-spacing: 0.5px; margin-bottom: 10px; }
.gg-hp-race-tagline { font-family: 'Source Serif 4', Georgia, serif; font-size: 12px; color: #7d695d; line-height: 1.7; margin: 0; }
.gg-hp-featured-cta { padding: 24px; text-align: center; background: #ede4d8; border-top: 2px solid #d4c5b9; }
.gg-hp-quick-filters { margin-top: 16px; display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 8px; }
.gg-hp-quick-label { font-family: 'Sometype Mono', monospace; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; color: #7d695d; }
.gg-hp-quick-chip { font-family: 'Sometype Mono', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1px; padding: 4px 12px; border: 2px solid #59473c; color: #59473c; text-decoration: none; transition: all var(--gg-ease); }
.gg-hp-quick-chip:hover { background: #59473c; color: #f5efe6; }
.gg-hp-quick-chip--accent { border-color: #178079; color: #178079; }
.gg-hp-quick-chip--accent:hover { background: #178079; color: #f5efe6; border-color: #178079; }

/* ── Latest Takes ───────────────────────────────────────── */
.gg-hp-latest-takes { max-width: 1200px; margin: 32px auto 0; border: 3px solid #3a2e25; }
.gg-hp-section-header--gold { background: #9a7e0a; }
.gg-hp-take-grid { display: grid; grid-template-columns: repeat(3, 1fr); }
.gg-hp-take-card { display: flex; flex-direction: column; padding: 24px; border: 1px solid #d4c5b9; text-decoration: none; color: #3a2e25; background: #f5efe6; transition: border-color var(--gg-ease); }
.gg-hp-take-card:hover { border-color: #9a7e0a; }
.gg-hp-take-tag { display: inline-block; font-family: 'Sometype Mono', monospace; font-size: 9px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: #9a7e0a; margin-bottom: 10px; }
.gg-hp-take-title { font-family: 'Source Serif 4', Georgia, serif; font-size: 16px; font-weight: 700; line-height: 1.3; margin-bottom: 10px; }
.gg-hp-take-teaser { font-family: 'Source Serif 4', Georgia, serif; font-size: 13px; color: #7d695d; line-height: 1.7; margin: 0 0 16px; flex: 1; }
.gg-hp-take-read { font-family: 'Sometype Mono', monospace; font-size: 11px; font-weight: 700; letter-spacing: 2px; color: #178079; }
.gg-hp-take-cta { padding: 24px; text-align: center; background: #ede4d8; border-top: 2px solid #d4c5b9; }
.gg-hp-take-cta .gg-hp-btn--primary { background: #59473c; color: #fff; border-color: #3a2e25; }
.gg-hp-take-cta .gg-hp-btn--primary:hover { border-color: #9a7e0a; color: #fff; }

/* ── How it works ────────────────────────────────────────── */
.gg-hp-how-it-works { background: #1a1613; display: grid; grid-template-columns: repeat(3, 1fr); margin-top: 32px; border: 3px solid #3a2e25; }
.gg-hp-step { padding: 36px 24px; border-right: 2px solid #3a2e25; }
.gg-hp-step:last-child { border-right: none; }
.gg-hp-step-num { display: block; font-family: 'Sometype Mono', monospace; font-size: 36px; font-weight: 700; color: #9a7e0a; margin-bottom: 12px; }
.gg-hp-step-title { font-family: 'Sometype Mono', monospace; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; color: #f5efe6; margin-bottom: 10px; }
.gg-hp-step-desc { font-family: 'Source Serif 4', Georgia, serif; font-size: 14px; color: #7d695d; line-height: 1.7; }

/* ── Coming Up ───────────────────────────────────────────── */
.gg-hp-coming-up { max-width: 1200px; margin: 32px auto 0; border: 3px solid #3a2e25; }
.gg-hp-cal-list { padding: 0; }
.gg-hp-cal-item { display: flex; align-items: center; gap: 16px; padding: 14px 20px; border-bottom: 2px solid #d4c5b9; text-decoration: none; color: #3a2e25; transition: border-color var(--gg-ease), background-color var(--gg-ease); }
.gg-hp-cal-item:last-child { border-bottom: none; }
.gg-hp-cal-item:hover { border-color: #9a7e0a; background: #f5efe6; }
.gg-hp-cal-item--past { opacity: 0.5; }
.gg-hp-cal-item--past:hover { opacity: 0.7; }
.gg-hp-cal-item--today { border-left: 3px solid #c0392b; }
.gg-hp-cal-item--soon { border-left: 3px solid #9a7e0a; }
.gg-hp-cal-date { font-family: 'Sometype Mono', monospace; font-size: 11px; font-weight: 700; color: #7d695d; letter-spacing: 1px; text-transform: uppercase; min-width: 50px; }
.gg-hp-cal-badge { display: inline-block; font-family: 'Sometype Mono', monospace; padding: 2px 8px; font-size: 9px; font-weight: 700; letter-spacing: 1.5px; min-width: 36px; text-align: center; }
.gg-hp-cal-info { flex: 1; min-width: 0; }
.gg-hp-cal-name { display: block; font-family: 'Source Serif 4', Georgia, serif; font-size: 14px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.gg-hp-cal-meta { display: block; font-family: 'Sometype Mono', monospace; font-size: 10px; color: #7d695d; margin-top: 2px; }
.gg-hp-cal-score { font-family: 'Sometype Mono', monospace; font-size: 20px; font-weight: 700; color: #178079; min-width: 36px; text-align: right; }
.gg-hp-cal-cta { padding: 20px; text-align: center; background: #ede4d8; border-top: 2px solid #d4c5b9; }
.gg-hp-cal-offseason { padding: 24px 20px; font-family: 'Sometype Mono', monospace; font-size: 12px; color: #7d695d; letter-spacing: 0.5px; }
.gg-hp-cal-offseason a { color: #178079; font-weight: 700; }

/* ── Guide Preview ───────────────────────────────────────── */
.gg-hp-guide { max-width: 1200px; margin: 32px auto 0; border: 3px solid #3a2e25; }
.gg-hp-guide-intro { padding: 20px; font-family: 'Source Serif 4', Georgia, serif; font-size: 14px; color: #3a2e25; line-height: 1.75; border-bottom: 2px solid #d4c5b9; }
.gg-hp-guide-intro p { margin: 0; }
.gg-hp-guide-grid { display: grid; grid-template-columns: repeat(2, 1fr); }
.gg-hp-guide-ch { display: flex; flex-direction: column; padding: 16px 20px; border: 1px solid #d4c5b9; text-decoration: none; color: #3a2e25; background: #f5efe6; transition: border-color var(--gg-ease); }
.gg-hp-guide-ch:hover { border-color: #9a7e0a; }
.gg-hp-guide-num { font-family: 'Sometype Mono', monospace; font-size: 10px; font-weight: 700; letter-spacing: 3px; color: #9a7e0a; margin-bottom: 4px; }
.gg-hp-guide-title { font-family: 'Source Serif 4', Georgia, serif; font-size: 14px; font-weight: 700; margin-bottom: 2px; }
.gg-hp-guide-lock { font-size: 10px; }
.gg-hp-guide-sub { font-family: 'Sometype Mono', monospace; font-size: 10px; color: #7d695d; }
.gg-hp-guide-free { display: inline-block; font-family: 'Sometype Mono', monospace; background: #178079; color: #fff; padding: 0 5px; font-size: 8px; font-weight: 700; letter-spacing: 1px; margin-left: 4px; vertical-align: middle; }
.gg-hp-guide-email-tag { display: inline-block; font-family: 'Sometype Mono', monospace; background: #9a7e0a; color: #fff; padding: 0 5px; font-size: 8px; font-weight: 700; letter-spacing: 1px; margin-left: 4px; vertical-align: middle; }
.gg-hp-guide-deal { margin-top: 12px; padding: 12px 16px; border-left: 3px solid #9a7e0a; font-size: 13px; color: #3a2e25; line-height: 1.7; }
.gg-hp-guide-deal strong { color: #9a7e0a; }
.gg-hp-guide-cta { padding: 20px; text-align: center; background: #ede4d8; border-top: 2px solid #d4c5b9; }

/* ── As Featured In ─────────────────────────────────────── */
.gg-hp-featured-in { max-width: 1200px; margin: 32px auto 0; border: 3px solid #3a2e25; background: #f5efe6; }
.gg-hp-feat-inner { display: flex; align-items: center; gap: 32px; padding: 32px 24px; }
.gg-hp-feat-text { flex: 0 0 auto; max-width: 260px; }
.gg-hp-feat-label { display: inline-block; font-family: 'Sometype Mono', monospace; font-size: 10px; font-weight: 700; letter-spacing: 4px; text-transform: uppercase; color: #9a7e0a; margin-bottom: 8px; }
.gg-hp-feat-copy { font-family: 'Source Serif 4', Georgia, serif; font-size: 13px; line-height: 1.7; color: #7d695d; font-style: italic; margin: 0; }
.gg-hp-feat-logos { display: flex; align-items: center; gap: 32px; flex: 1; justify-content: center; flex-wrap: wrap; }
.gg-hp-feat-logo { display: block; transition: border-color var(--gg-ease); border: 2px solid transparent; padding: 8px; }
.gg-hp-feat-logo:hover { border-color: #9a7e0a; }
.gg-hp-feat-logo img { display: block; height: 56px; width: auto; }

/* ── Training CTA ────────────────────────────────────────── */
.gg-hp-training { max-width: 1200px; margin: 32px auto 0; border: 3px solid #3a2e25; }
.gg-hp-training-grid { display: grid; grid-template-columns: 1.2fr 0.8fr; }
.gg-hp-training-card { padding: 36px 24px; }
.gg-hp-training-card--primary { border-right: 3px solid #3a2e25; border-top: 3px solid #9a7e0a; }
.gg-hp-training-card h3 { font-family: 'Source Serif 4', Georgia, serif; font-size: 18px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }
.gg-hp-training-subtitle { font-family: 'Sometype Mono', monospace; font-size: 12px; color: #7d695d; margin-bottom: 16px; }
.gg-hp-training-bullets { padding-left: 20px; margin-bottom: 24px; }
.gg-hp-training-bullets li { font-family: 'Source Serif 4', Georgia, serif; font-size: 13px; line-height: 2; color: #3a2e25; }
.gg-hp-training-bullets li::marker { color: #9a7e0a; }
.gg-hp-training-card--secondary { background: #ede4d8; }
.gg-hp-training-card--secondary p { font-family: 'Source Serif 4', Georgia, serif; font-size: 13px; line-height: 1.75; color: #59473c; margin-bottom: 16px; }

/* ── Email capture ───────────────────────────────────────── */
.gg-hp-email { background: #59473c; margin-top: 32px; padding: 48px; border: 3px solid #3a2e25; }
.gg-hp-email-inner { max-width: 560px; margin: 0 auto; text-align: center; }
.gg-hp-email-label { display: inline-block; font-family: 'Sometype Mono', monospace; font-size: 10px; font-weight: 700; letter-spacing: 4px; text-transform: uppercase; color: #9a7e0a; margin-bottom: 12px; }
.gg-hp-email-title { font-family: 'Source Serif 4', Georgia, serif; font-size: 28px; font-weight: 700; color: #fff; margin-bottom: 12px; }
.gg-hp-email-text { font-family: 'Source Serif 4', Georgia, serif; font-size: 14px; color: #d4c5b9; margin-bottom: 0; line-height: 1.75; }

/* ── Article carousel ───────────────────────────────────── */
.gg-hp-article-carousel { display: flex; gap: 16px; overflow-x: auto; scroll-snap-type: x mandatory; padding: 24px 48px; -webkit-overflow-scrolling: touch; }
.gg-hp-article-carousel::-webkit-scrollbar { height: 4px; }
.gg-hp-article-carousel::-webkit-scrollbar-track { background: #3a2e25; }
.gg-hp-article-carousel::-webkit-scrollbar-thumb { background: #9a7e0a; }
.gg-hp-article-card { flex: 0 0 280px; scroll-snap-align: start; padding: 20px; background: #f5efe6; border: 2px solid transparent; text-decoration: none; color: #3a2e25; transition: border-color var(--gg-ease); }
.gg-hp-article-card:hover { border-color: #9a7e0a; }
.gg-hp-article-title { font-family: 'Source Serif 4', Georgia, serif; font-size: 15px; font-weight: 700; line-height: 1.3; margin-bottom: 8px; }
.gg-hp-article-snippet { font-family: 'Source Serif 4', Georgia, serif; font-size: 12px; color: #7d695d; line-height: 1.6; margin: 0; }

/* ── Email form ─────────────────────────────────────────── */
.gg-hp-email-form { background: #f5efe6; padding: 20px 32px; max-width: 480px; margin: 24px auto 0; min-height: 150px; }

/* ── Footer ──────────────────────────────────────────────── */
.gg-hp-footer { background: #59473c; margin-top: 32px; border-top: 4px double #3a2e25; }
.gg-hp-footer-grid { display: grid; grid-template-columns: 1.2fr 0.8fr 1fr; gap: 32px; padding: 48px 32px; max-width: 1200px; margin: 0 auto; }
.gg-hp-footer-title { font-family: 'Sometype Mono', monospace; font-size: 14px; font-weight: 700; letter-spacing: 3px; color: #fff; margin-bottom: 12px; }
.gg-hp-footer-tagline { font-family: 'Source Serif 4', Georgia, serif; font-size: 13px; line-height: 1.75; color: #d4c5b9; margin: 0; }
.gg-hp-footer-heading { font-family: 'Sometype Mono', monospace; font-size: 10px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; color: #9a7e0a; margin-bottom: 16px; }
.gg-hp-footer-nav { display: flex; flex-direction: column; gap: 10px; }
.gg-hp-footer-nav a { color: #d4c5b9; font-family: 'Sometype Mono', monospace; font-size: 12px; text-decoration: none; transition: color var(--gg-ease); }
.gg-hp-footer-nav a:hover { color: #fff; }
.gg-hp-footer-newsletter p { font-family: 'Source Serif 4', Georgia, serif; font-size: 13px; color: #d4c5b9; line-height: 1.75; margin: 0 0 16px; }
.gg-hp-footer-subscribe { display: inline-block; padding: 10px 24px; font-family: 'Sometype Mono', monospace; font-size: 11px; font-weight: 700; letter-spacing: 2px; background: #178079; color: #fff; text-decoration: none; border: 3px solid #178079; transition: background-color var(--gg-ease), border-color var(--gg-ease); }
.gg-hp-footer-subscribe:hover { background: transparent; border-color: #178079; }
.gg-hp-footer-legal { padding: 16px 32px; border-top: 2px solid #3a2e25; text-align: center; font-family: 'Sometype Mono', monospace; font-size: 10px; color: #7d695d; letter-spacing: 1px; max-width: 1200px; margin: 0 auto; }

/* ── Skip link ───────────────────────────────────────────── */
.gg-hp-skip { position: absolute; left: -9999px; top: auto; width: 1px; height: 1px; overflow: hidden; font-family: 'Sometype Mono', monospace; font-size: 12px; font-weight: 700; letter-spacing: 2px; padding: 12px 24px; background: #9a7e0a; color: #3a2e25; z-index: 100; }
.gg-hp-skip:focus { position: fixed; top: 0; left: 0; width: auto; height: auto; }

/* ── Responsive: tablet ─────────────────────────────────── */
@media (max-width: 1024px) {
  .gg-hp-race-grid { grid-template-columns: repeat(2, 1fr); }
  .gg-hp-take-grid { grid-template-columns: 1fr; }
  .gg-hp-guide-grid { grid-template-columns: 1fr; }
  .gg-hp-footer-grid { grid-template-columns: 1fr 1fr; }
  .gg-hp-feat-inner { flex-direction: column; text-align: center; }
  .gg-hp-feat-text { max-width: 100%; }
}

/* ── Responsive: mobile ─────────────────────────────────── */
@media (max-width: 768px) {
  html, body { overflow-x: hidden; }
  .gg-hp-page { overflow-x: hidden; }

  /* Full-bleed sections on mobile — remove side borders */
  .gg-hp-featured, .gg-hp-latest-takes, .gg-hp-how-it-works, .gg-hp-coming-up,
  .gg-hp-guide, .gg-hp-featured-in, .gg-hp-training, .gg-hp-email { margin: 16px 0 0; border-left: none; border-right: none; }

  /* Header */
  .gg-hp-header { padding: 12px 16px; }
  .gg-hp-header-inner { flex-wrap: wrap; justify-content: center; gap: 10px; }
  .gg-hp-header-logo img { height: 40px; }
  .gg-hp-header-nav { gap: 12px; flex-wrap: wrap; justify-content: center; }
  .gg-hp-header-nav a { font-size: 10px; letter-spacing: 1.5px; }

  /* Ticker — scrolling version hidden, static mobile version shown */
  .gg-hp-ticker { display: none; }
  .gg-hp-ticker-mobile { display: block; background: #1a1613; border-bottom: 3px solid #9a7e0a; padding: 10px 16px; text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  /* Hero */
  .gg-hp-hero { padding: 36px 16px; }
  .gg-hp-hero-badge { font-size: 10px; letter-spacing: 2px; padding: 5px 12px; }
  .gg-hp-hero h1 { font-size: 26px; }
  .gg-hp-hero-tagline { font-size: 15px; }
  .gg-hp-hero-search { flex-direction: column; }
  .gg-hp-hero-input { border-right: 2px solid #7d695d; font-size: 11px; }
  .gg-hp-hero-search-btn { width: 100%; }
  .gg-hp-hero-ctas { flex-direction: column; }
  .gg-hp-hero-ctas .gg-hp-btn { width: 100%; text-align: center; }

  /* Buttons */
  .gg-hp-btn { padding: 12px 20px; font-size: 11px; letter-spacing: 1.5px; }

  /* Stats bar */
  .gg-hp-stats-bar { grid-template-columns: repeat(2, 1fr); }
  .gg-hp-stat { padding: 20px 10px; }
  .gg-hp-stat:nth-child(2) { border-right: none; }
  .gg-hp-stat:nth-child(1), .gg-hp-stat:nth-child(2) { border-bottom: 2px solid #3a2e25; }
  .gg-hp-stat-number { font-size: 28px; }
  .gg-hp-stat-label { font-size: 9px; letter-spacing: 2px; }

  /* Featured races */
  .gg-hp-race-grid { grid-template-columns: 1fr; }
  .gg-hp-race-card { padding: 16px; }
  .gg-hp-featured-cta { padding: 16px; }

  /* Latest takes */
  .gg-hp-take-grid { grid-template-columns: 1fr; }
  .gg-hp-take-card { padding: 16px; }
  .gg-hp-take-cta { padding: 16px; }

  /* How it works */
  .gg-hp-how-it-works { grid-template-columns: 1fr; }
  .gg-hp-step { padding: 24px 16px; border-right: none; border-bottom: 2px solid #3a2e25; }
  .gg-hp-step:last-child { border-bottom: none; }
  .gg-hp-step-num { font-size: 28px; }

  /* Coming up */
  .gg-hp-cal-item { gap: 8px; padding: 12px 12px; flex-wrap: wrap; }
  .gg-hp-cal-date { font-size: 10px; min-width: 44px; }
  .gg-hp-cal-name { font-size: 13px; }
  .gg-hp-cal-score { font-size: 16px; }

  /* Guide */
  .gg-hp-guide-grid { grid-template-columns: 1fr; }
  .gg-hp-guide-ch { padding: 12px 16px; }
  .gg-hp-guide-intro { padding: 16px; }
  .gg-hp-guide-deal { padding: 10px 12px; }

  /* Featured in */
  .gg-hp-feat-inner { flex-direction: column; text-align: center; padding: 24px 16px; gap: 20px; }
  .gg-hp-feat-text { max-width: 100%; }
  .gg-hp-feat-logos { gap: 20px; }
  .gg-hp-feat-logo img { height: 44px; }

  /* Training */
  .gg-hp-training-grid { grid-template-columns: 1fr; }
  .gg-hp-training-card { padding: 24px 16px; }
  .gg-hp-training-card--primary { border-right: none; border-bottom: 3px solid #3a2e25; }

  /* Email / articles — stack vertically on mobile, show max 3 */
  .gg-hp-email { padding: 32px 0; }
  .gg-hp-email-inner { padding: 0 16px; }
  .gg-hp-email-title { font-size: 22px; }
  .gg-hp-article-carousel { flex-direction: column; overflow-x: visible; scroll-snap-type: none; padding: 16px; gap: 12px; }
  .gg-hp-article-card { flex: none; width: 100%; padding: 16px; }
  .gg-hp-article-card:nth-child(n+4) { display: none; }
  .gg-hp-email-form { margin: 20px 16px 0; padding: 16px; }

  /* Footer */
  .gg-hp-footer { margin-top: 16px; }
  .gg-hp-footer-grid { grid-template-columns: 1fr; gap: 24px; padding: 32px 16px; }
  .gg-hp-footer-legal { padding: 12px 16px; }

  /* Section headers */
  .gg-hp-section-header { padding: 12px 16px; }
  .gg-hp-section-header h2 { font-size: 11px; letter-spacing: 2px; }
}
</style>'''


# ── JavaScript ───────────────────────────────────────────────


def build_homepage_js() -> str:
    return '''<script>
// GA4 event tracking on CTA clicks
document.querySelectorAll('[data-ga]').forEach(function(el) {
  el.addEventListener('click', function() {
    var event_name = el.getAttribute('data-ga');
    var label = el.getAttribute('data-ga-label') || '';
    if (typeof gtag === 'function') {
      gtag('event', event_name, { event_label: label });
    }
  });
});
</script>'''


# ── JSON-LD ──────────────────────────────────────────────────


def build_jsonld(stats: dict) -> str:
    org = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Gravel God Cycling",
        "url": SITE_BASE_URL,
        "description": "The definitive gravel race database. Honest ratings across 14 dimensions.",
    }
    website = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "Gravel God Cycling",
        "url": SITE_BASE_URL,
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{SITE_BASE_URL}/gravel-races/?q={{search_term_string}}",
            "query-input": "required name=search_term_string",
        },
    }
    parts = [
        f'<script type="application/ld+json">\n{json.dumps(org, indent=2)}\n</script>',
        f'<script type="application/ld+json">\n{json.dumps(website, indent=2)}\n</script>',
    ]
    return "\n  ".join(parts)


# ── Page assembler ───────────────────────────────────────────


def generate_homepage(race_index: list, race_data_dir: Path = None,
                      guide_path: Path = None) -> str:
    stats = compute_stats(race_index)
    canonical_url = f"{SITE_BASE_URL}/"
    title = f"Gravel God \u2014 {stats['race_count']} Gravel Races Rated & Ranked | The Definitive Database"
    meta_desc = f"The definitive gravel race database. {stats['race_count']} races scored across 14 dimensions, from Unbound to the Tour Divide. Find your next race, compare ratings, and build a training plan."

    # Load dynamic data
    one_liners = load_editorial_one_liners(race_data_dir)
    upcoming = load_upcoming_races(race_data_dir)
    substack_posts = fetch_substack_posts()
    chapters = load_guide_chapters(guide_path)

    nav = build_nav()
    ticker = build_ticker(one_liners, substack_posts, upcoming)
    hero = build_hero(stats)
    stats_bar = build_stats_bar(stats)
    featured = build_featured_races(race_index)
    latest_takes = build_latest_takes()
    coming_up = build_coming_up(upcoming)
    how_it_works = build_how_it_works(stats)
    guide_preview = build_guide_preview(chapters)
    featured_in = build_featured_in()
    training = build_training_cta()
    email = build_email_capture(substack_posts)
    footer = build_footer()
    css = build_homepage_css()
    js = build_homepage_js()
    jsonld = build_jsonld(stats)

    og_image = f"{SITE_BASE_URL}/og/homepage.jpg"
    og_tags = f'''<meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(meta_desc)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:image" content="{esc(og_image)}">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(title)}">
  <meta name="twitter:description" content="{esc(meta_desc)}">
  <meta name="twitter:image" content="{esc(og_image)}">'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' fill='%233a2e25'/><text x='16' y='24' text-anchor='middle' font-family='serif' font-size='24' font-weight='700' fill='%23B7950B'>G</text></svg>">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(meta_desc)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical_url)}">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Sometype+Mono:ital,wght@0,400;0,700;1,400;1,700&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,700;1,8..60,400;1,8..60,700&display=swap">
  {og_tags}
  {jsonld}
  {css}
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA4_MEASUREMENT_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA4_MEASUREMENT_ID}');</script>
</head>
<body>

<a href="#main" class="gg-hp-skip">Skip to content</a>
<div class="gg-hp-page">
  {nav}

  {ticker}

  {hero}

  {stats_bar}

  {featured}

  {latest_takes}

  {coming_up}

  {how_it_works}

  {training}

  {guide_preview}

  {featured_in}

  {email}

  {footer}
</div>

{js}

</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate Gravel God homepage")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    parser.add_argument("--index-file", default=str(RACE_INDEX_PATH),
                        help="Path to race-index.json")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    race_index = load_race_index(Path(args.index_file))
    html_content = generate_homepage(race_index)

    output_file = output_dir / "homepage.html"
    output_file.write_text(html_content, encoding="utf-8")

    # Summary stats (reuse cheap computations, avoid re-fetching Substack RSS)
    stats = compute_stats(race_index)
    upcoming = load_upcoming_races()
    one_liners = load_editorial_one_liners()
    chapters = load_guide_chapters()
    print(f"Generated {output_file} ({len(html_content):,} bytes)")
    print(f"  {stats['race_count']} races, {stats['t1_count']} T1, {stats['dimensions']} dimensions")
    print(f"  Ticker: {len(one_liners)} one-liners")
    print(f"  Coming up: {len([r for r in upcoming if r['days'] >= 0])} upcoming, {len([r for r in upcoming if r['days'] < 0])} recent")
    print(f"  Guide: {len(chapters)} chapters")


if __name__ == "__main__":
    main()
