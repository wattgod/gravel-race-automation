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
from brand_tokens import (
    GA_MEASUREMENT_ID,
    RACER_RATING_THRESHOLD,
    get_ab_head_snippet,
    get_font_face_css,
    get_preload_hints,
    get_tokens_css,
)
from shared_footer import get_mega_footer_css, get_mega_footer_html
from shared_header import get_site_header_css, get_site_header_html

OUTPUT_DIR = Path(__file__).parent / "output"
RACE_INDEX_PATH = Path(__file__).parent.parent / "web" / "race-index.json"
RACE_DATA_DIR = Path(__file__).parent.parent / "race-data"
GUIDE_CONTENT_PATH = Path(__file__).parent.parent / "guide" / "gravel-guide-content.json"
SUBSTACK_RSS_URL = "https://gravelgodcycling.substack.com/feed"

GA4_MEASUREMENT_ID = GA_MEASUREMENT_ID
CURRENT_YEAR = date.today().year

# ── Featured race slugs (curated for homepage diversity) ─────

FEATURED_SLUGS = [
    "unbound-200",
    "sbt-grvl",
    "bwr-california",
]

# ── Featured on-site articles (curated for homepage voice) ──────
# These are the "saucy takes" that show personality and editorial voice.
# Each entry: (title, url_path, category_tag, teaser)
# Update FEATURED_ONSITE_UPDATED when you change these articles.

FEATURED_ONSITE_UPDATED = "2026-02-15"  # YYYY-MM-DD — last time articles were curated

FEATURED_ONSITE_ARTICLES = [
    (
        "If You're Not Talented, You Should Probably Quit",
        "/if-youre-not-talented-you-should-probably-quit/",
        "HOT TAKE",
        "The worst advice in cycling is \u201canyone can do it.\u201d Here\u2019s what nobody says out loud.",
    ),
    (
        "I Opened a FasCat AI Coaching Email So You Don't Have To",
        "/i-opened-a-fascat-ai-coaching-email-so-you-dont-have-to/",
        "CONTROVERSIAL OPINION",
        "What happens when AI tries to coach cyclists? I opened the email so you can skip the sales pitch.",
    ),
    (
        "5 Ways to Become a Power Meter Clown",
        "/5-ways-to-become-a-power-meter-clown/",
        "TRAINING",
        "The power meter doesn\u2019t make you fast. Staring at it while you ride makes you slow.",
    ),
    (
        "Your Eating Habits Are Killing Your Performance",
        "/your-eating-habits-are-killing-your-performance/",
        "NUTRITION",
        "You\u2019re not under-training. You\u2019re under-eating. And the solution isn\u2019t another gel.",
    ),
    (
        "Maybe Stop Sandbagging Your Goals",
        "/maybe-stop-sandbagging-your-goals/",
        "MINDSET",
        "Setting \u201crealistic\u201d goals is just fear wearing a sensible hat.",
    ),
    (
        "How to Beat People 20 Years Younger Than You",
        "/how-to-beat-people-20-years-younger-than-you/",
        "RACING",
        "Age is an excuse until it isn\u2019t. Here\u2019s what actually changes \u2014 and what doesn\u2019t.",
    ),
    (
        "Does Beer Make You Slow?",
        "/does-beer-make-you-slow/",
        "SINCE YOU ASKED",
        "The question every cyclist asks and nobody answers honestly.",
    ),
    (
        "How to Develop Your Athletic Sh**t Detector",
        "/how-to-develop-your-athletic-sht-detector/",
        "TRAINING",
        "Most cycling advice is marketing. Here\u2019s how to tell the difference.",
    ),
    (
        "I Messed Up Big Horn Gravel So You Don't Have To",
        "/i-messed-up-big-horn-gravel-so-you-dont-have-to/",
        "RACE REPORT",
        "Every mistake you can make in a gravel race, catalogued for your benefit.",
    ),
    (
        "You Don't Need To Bike To Bike Fast",
        "/you-dont-need-to-bike-to-bike-fast/",
        "CONTROVERSIAL OPINION",
        "The fastest gains most cyclists will ever make happen off the bike.",
    ),
    (
        "Your FTP Does Matter",
        "/since-no-one-asked-why-did-dumoulin-retire-he-just-wants-to-eat-some-cheese/",
        "CONTROVERSIAL OPINION",
        "Everyone\u2019s telling you FTP doesn\u2019t matter. They\u2019re wrong, and here\u2019s why.",
    ),
    (
        "Maybe a Hater Poster is What You've Been Missing",
        "/maybe-a-hate-poster-is-what-youve-been-missing/",
        "MINDSET",
        "Sometimes the best motivation isn\u2019t a quote from Marcus Aurelius. Sometimes it\u2019s spite.",
    ),
]

# ── Athlete testimonials (from live site coaching section) ──────
TESTIMONIALS = [
    {
        "quote": "I finished Unbound in 13:47 this year. Last year I DNF\u2019d at mile 140 because I had no idea how to pace myself and ran out of food twice. Matti\u2019s plan was boring as hell but it worked.",
        "name": "Sarah K.",
        "title": "Unbound 200 finisher",
        "tags": "Gravel \u00b7 9 hrs/week \u00b7 Elementary school teacher",
    },
    {
        "quote": "First time I cracked top 20 at a regional race. Not because I got fitter\u2014I\u2019ve been \u2018fit enough\u2019 for years. I just finally learned to not go hard when it felt easy and actually recover on easy days.",
        "name": "Marcus T.",
        "title": "consistent podium threat",
        "tags": "Gravel \u00b7 12 hrs/week \u00b7 Night shift RN",
    },
    {
        "quote": "Matti told me to stop doing VO2 intervals in February and I thought he was an idiot. Then I PR\u2019d every race distance from June through September. Turns out base actually matters.",
        "name": "Jordan P.",
        "title": "multiple Cat 1/2 wins",
        "tags": "Road & gravel \u00b7 14 hrs/week \u00b7 Software engineer",
    },
    {
        "quote": "I went from blowing up on every climb longer than 10 minutes to finishing SBT GRVL Black in the top third. The difference was pacing and fueling strategy, not some magic workout.",
        "name": "Chris M.",
        "title": "SBT GRVL Black finisher",
        "tags": "Gravel \u00b7 10 hrs/week \u00b7 Two kids under 5",
    },
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
    t2_count = sum(1 for r in race_index if r.get("tier") == 2)
    regions = set()
    for r in race_index:
        loc = r.get("location", "")
        if loc:
            parts = [p.strip() for p in loc.split(",")]
            if parts:
                regions.add(parts[-1])
    return {
        "race_count": race_count,
        "dimensions": 14,
        "t1_count": t1_count,
        "t2_count": t2_count,
        "region_count": len(regions),
    }


def get_featured_races(race_index: list) -> list:
    """Return featured race dicts from the index, falling back to top T1 by score."""
    by_slug = {r["slug"]: r for r in race_index}
    featured = []
    for slug in FEATURED_SLUGS:
        if slug in by_slug:
            featured.append(by_slug[slug])
    # Fallback: fill remaining slots with top T1 races by score
    if len(featured) < 3:
        t1_races = sorted(
            [r for r in race_index if r.get("tier") == 1 and r not in featured],
            key=lambda r: r.get("overall_score", 0),
            reverse=True,
        )
        for r in t1_races:
            if len(featured) >= 3:
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
    return get_site_header_html()


def build_top_bar() -> str:
    return '<div class="gg-hp-top-bar" aria-hidden="true"></div>'


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


def build_hero(stats: dict, race_index: list = None) -> str:
    race_count = stats["race_count"]

    # Featured race card
    feature_html = ""
    if race_index:
        featured = get_featured_races(race_index)
        if featured:
            race = featured[0]
            tier = race.get("tier", 1)
            score = race.get("overall_score", 0)
            name = esc(race.get("name", ""))
            slug = esc(race.get("slug", ""))
            location = esc(race.get("location", ""))
            month = race.get("month", "")
            tagline = esc(race.get("tagline", "")[:120])
            tier_labels = {1: "Tier 1 Elite", 2: "Tier 2 Contender", 3: "Tier 3", 4: "Tier 4"}
            tier_label = tier_labels.get(tier, f"Tier {tier}")
            feature_html = f'''<a href="{SITE_BASE_URL}/race/{slug}/" class="gg-hp-hero-feature" data-ga="hero_featured_click" data-ga-label="{name}">
          <div class="gg-hp-hf-img" role="img" aria-label="{name} course landscape"></div>
          <div class="gg-hp-hf-body">
            <div class="gg-hp-hf-header">
              <div>
                <p class="gg-hp-hf-tier">Featured &middot; {esc(tier_label)}</p>
                <h3 class="gg-hp-hf-name">{name}</h3>
              </div>
              <span class="gg-hp-hf-score" data-counter="{score}" aria-label="Score: {score}">{score}</span>
            </div>
            <p class="gg-hp-hf-meta">{location}{(" &middot; " + _format_month(month)) if month else ""}</p>
            <p class="gg-hp-hf-excerpt">{tagline}</p>
          </div>
        </a>'''

    return f'''<section class="gg-hp-hero" id="main">
    <div class="gg-hp-hero-inner">
      <div class="gg-hp-hero-content">
        <div class="gg-hp-announce-pill" aria-hidden="true"><span class="gg-hp-announce-dot"></span> {race_count} Races Scored for {CURRENT_YEAR}</div>
        <p class="gg-hp-hero-kicker">THE {CURRENT_YEAR} RACE DATABASE</p>
        <h1 id="hero-title">Every gravel race, honestly rated</h1>
        <div class="gg-hp-accent-line" aria-hidden="true"></div>
        <p class="gg-hp-hero-deck" data-ab="hero_tagline">{race_count} races scored on 14 criteria. No sponsors, no affiliates, no pulled punches. Just the data and the dirt.</p>
        <div class="gg-hp-hero-actions">
          <a href="{SITE_BASE_URL}/gravel-races/" class="gg-hp-btn-primary" data-ga="hero_cta_click">Browse All Races</a>
          <a href="{SITE_BASE_URL}/race/methodology/" class="gg-hp-btn-secondary" data-ga="hero_secondary_click">How We Rate</a>
        </div>
      </div>
      {feature_html}
    </div>
  </section>'''


def build_stats_bar(stats: dict) -> str:
    items = [
        (stats["race_count"], "Races", ""),
        (stats["t1_count"], "Tier 1", ""),
        (stats["t2_count"], "Tier 2", ""),
        (stats["region_count"], "Regions", "+"),
        (stats["dimensions"], "Criteria", ""),
    ]
    cells = ""
    for value, label, suffix in items:
        display = f'{value}{suffix}'
        cells += f'''
      <div class="gg-hp-ss-item">
        <div class="gg-hp-ss-val" data-counter="{value}"{' data-suffix="' + suffix + '"' if suffix else ''} aria-label="{display} {esc(label)}">{display}</div>
        <div class="gg-hp-ss-lbl">{esc(label)}</div>
      </div>'''
    return f'''<section class="gg-hp-stats-stripe" aria-label="Database statistics">
    <div class="gg-hp-stats-inner">{cells}
    </div>
  </section>'''


def _tier_badge_class(tier: int) -> str:
    """Return CSS class for a tier badge."""
    return f"gg-hp-badge-t{tier}" if 1 <= tier <= 4 else "gg-hp-badge-t4"


def _format_month(month: str) -> str:
    """Return abbreviated 3-letter month."""
    if not month:
        return ""
    return month[:3].upper()


def build_bento_features(race_index: list) -> str:
    """Build a bento grid with 1 lead card + 2 secondary cards for featured races."""
    featured = get_featured_races(race_index)
    if not featured:
        return '<div class="gg-hp-bento"><p class="gg-hp-bento-empty">Featured races loading&hellip;</p></div>'
    tier_labels = {1: "Elite", 2: "Contender", 3: "Rising", 4: "Local"}
    cards = ""
    for i, race in enumerate(featured[:3]):
        tier = race.get("tier", 4)
        score = race.get("overall_score", 0)
        name = esc(race.get("name", ""))
        slug = esc(race.get("slug", ""))
        location = esc(race.get("location", ""))
        month = race.get("month", "")
        tagline = race.get("tagline", "")[:120]
        tier_label = tier_labels.get(tier, f"Tier {tier}")
        is_lead = i == 0
        lead_class = " gg-hp-bento-lead" if is_lead else ""
        lg = " lg" if is_lead else ""
        short = " short" if not is_lead else ""
        month_str = (" &middot; " + _format_month(month)) if month else ""
        cards += f'''
      <a href="{SITE_BASE_URL}/race/{slug}/" class="gg-hp-bento-card{lead_class}" data-ga="featured_race_click" data-ga-label="{name}">
        <div class="gg-hp-bento-img{short}" role="img" aria-label="{name} course landscape"></div>
        <div class="gg-hp-bento-body">
          <p class="gg-hp-bento-meta">Tier {tier} {esc(tier_label)} &middot; Score {score}</p>
          <h3 class="gg-hp-bento-name{lg}">{name}</h3>
          <p class="gg-hp-bento-excerpt">{esc(tagline)}</p>
          <p class="gg-hp-bento-byline">{location}{month_str}</p>
        </div>
      </a>'''

    return f'''<div class="gg-hp-bento">{cards}
    </div>'''


# Alias for backward compatibility with tests
build_featured_races = build_bento_features


def build_latest_takes() -> str:
    """Build the 'Latest Takes' carousel with curated on-site article cards."""
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

    total = len(FEATURED_ONSITE_ARTICLES)

    return f'''<section class="gg-hp-latest-takes" id="takes">
    <div class="gg-hp-section-header gg-hp-section-header--gold">
      <h2>LATEST TAKES</h2>
    </div>
    <div class="gg-hp-take-carousel" id="gg-takes-carousel">{cards}
    </div>
    <div class="gg-hp-take-nav">
      <button class="gg-hp-take-btn" id="gg-takes-prev" aria-label="Previous articles">&larr;</button>
      <span class="gg-hp-take-counter" id="gg-takes-count">1 / {(total + 1) // 2}</span>
      <button class="gg-hp-take-btn" id="gg-takes-next" aria-label="Next articles">&rarr;</button>
    </div>
    <div class="gg-hp-take-cta">
      <a href="{SITE_BASE_URL}/articles/" class="gg-hp-btn gg-hp-btn--primary" data-ga="view_all_articles">ALL ARTICLES &rarr;</a>
    </div>
  </section>'''


def build_tabbed_rankings(race_index: list) -> str:
    """Build ARIA-compliant tabbed rankings: All Tiers, Tier 1, Tier 2."""
    tier_labels = {1: "Elite", 2: "Contender", 3: "Rising", 4: "Local"}

    def _build_items(races):
        if not races:
            return '\n        <p class="gg-hp-article-empty">No races in this tier yet.</p>'
        items = ""
        for idx, race in enumerate(races[:5], 1):
            tier = race.get("tier", 4)
            score = race.get("overall_score", 0)
            name = esc(race.get("name", ""))
            slug = esc(race.get("slug", ""))
            tagline = esc(race.get("tagline", "")[:80])
            tl = tier_labels.get(tier, f"Tier {tier}")
            items += f'''
        <a href="{SITE_BASE_URL}/race/{slug}/" class="gg-hp-article-item" data-ga="ranking_click" data-ga-label="{name}">
          <span class="gg-hp-article-num" aria-hidden="true">{idx:02d}</span>
          <div>
            <p class="gg-hp-article-meta">Tier {tier} {esc(tl)}</p>
            <h3 class="gg-hp-article-name">{name}</h3>
            <p class="gg-hp-article-excerpt">{tagline}</p>
          </div>
          <span class="gg-hp-article-score" aria-label="Score {score}">{score}</span>
        </a>'''
        return items

    all_sorted = sorted(race_index, key=lambda r: r.get("overall_score", 0), reverse=True)
    t1_sorted = sorted(
        [r for r in race_index if r.get("tier") == 1],
        key=lambda r: r.get("overall_score", 0), reverse=True,
    )
    t2_sorted = sorted(
        [r for r in race_index if r.get("tier") == 2],
        key=lambda r: r.get("overall_score", 0), reverse=True,
    )

    return f'''<h2 class="gg-hp-col-header" id="rankings-heading">RACE RANKINGS</h2>
    <div class="gg-hp-tab-bar" role="tablist" aria-label="Filter by tier">
      <button type="button" role="tab" id="gg-tab-all" aria-selected="true" aria-controls="gg-panel-all" tabindex="0">All Tiers</button>
      <button type="button" role="tab" id="gg-tab-t1" aria-selected="false" aria-controls="gg-panel-t1" tabindex="-1">Tier 1</button>
      <button type="button" role="tab" id="gg-tab-t2" aria-selected="false" aria-controls="gg-panel-t2" tabindex="-1">Tier 2</button>
    </div>
    <div role="tabpanel" id="gg-panel-all" aria-labelledby="gg-tab-all">{_build_items(all_sorted)}
    </div>
    <div role="tabpanel" id="gg-panel-t1" aria-labelledby="gg-tab-t1" class="gg-hp-tab-inactive">{_build_items(t1_sorted)}
    </div>
    <div role="tabpanel" id="gg-panel-t2" aria-labelledby="gg-tab-t2" class="gg-hp-tab-inactive">{_build_items(t2_sorted)}
    </div>'''


def build_sidebar(stats: dict, race_index: list, upcoming: list) -> str:
    """Build sidebar with stats bento, pullquote, power rankings, coming up, and CTA."""

    # 1. Stats bento (2x2 grid)
    stat_items = [
        (stats["race_count"], "Races"),
        (stats["t1_count"], "Tier 1"),
        (stats["t2_count"], "Tier 2"),
        (stats["dimensions"], "Criteria"),
    ]
    stat_cells = ""
    for val, label in stat_items:
        stat_cells += f'''
        <div class="gg-hp-sb-stat">
          <div class="gg-hp-sb-stat-val" data-counter="{val}" aria-label="{val} {esc(label)}">{val}</div>
          <div class="gg-hp-sb-stat-lbl">{esc(label)}</div>
        </div>'''

    stats_html = f'''<h2 class="gg-hp-col-header">BY THE NUMBERS</h2>
    <div class="gg-hp-sidebar-card">
      <div class="gg-hp-sidebar-stat-grid">{stat_cells}
      </div>
    </div>'''

    # 2. Pullquote — pull from top-ranked race's final_verdict one_liner
    _pullquote_text = ""
    _pullquote_cite = ""
    for _slug in FEATURED_SLUGS:
        _match = next((r for r in race_index if r.get("slug") == _slug), None)
        if _match and _match.get("tagline"):
            _pullquote_text = esc(_match["tagline"])
            _pullquote_cite = f'On {esc(_match.get("name", _slug))}'
            break
    if not _pullquote_text:
        # Hardcoded fallback only if no featured race has a tagline
        _pullquote_text = "Not one killer climb, but 200 miles of constant attrition. The Flint Hills don&rsquo;t negotiate."
        _pullquote_cite = "On Unbound 200"
    pullquote_html = f'''<blockquote class="gg-hp-pullquote">
      <p>&ldquo;{_pullquote_text}&rdquo;</p>
      <cite>{_pullquote_cite}</cite>
    </blockquote>'''

    # 3. Power rankings (top 5 by score)
    top5 = sorted(race_index, key=lambda r: r.get("overall_score", 0), reverse=True)[:5]
    rank_items = ""
    for i, race in enumerate(top5, 1):
        name = esc(race.get("name", ""))
        score = race.get("overall_score", 0)
        rank_items += f'''
        <li class="gg-hp-rank-item">
          <span class="gg-hp-rank-pos" aria-hidden="true">{i}.</span>
          <span class="gg-hp-rank-name">{name}</span>
          <span class="gg-hp-rank-score" aria-label="Score {score}">{score}</span>
        </li>'''

    rankings_html = f'''<h2 class="gg-hp-col-header">POWER RANKINGS</h2>
    <div class="gg-hp-sidebar-card">
      <ol class="gg-hp-rank-list">{rank_items}
      </ol>
    </div>'''

    # 4. Coming up compact (next 4 upcoming races)
    future = [r for r in upcoming if r["days"] >= 0][:4]
    if future:
        coming_items = ""
        for race in future:
            badge_cls = _tier_badge_class(race["tier"])
            coming_items += f'''
        <a href="{SITE_BASE_URL}/race/{esc(race['slug'])}/" class="gg-hp-coming-compact-item">
          <span class="gg-hp-coming-compact-date">{race["date"].strftime("%b %d")}</span>
          <span class="gg-hp-coming-compact-name">{esc(race["name"])}</span>
          <span class="gg-hp-coming-compact-tier {badge_cls}">T{race["tier"]}</span>
        </a>'''
        coming_html = f'''<h2 class="gg-hp-col-header">COMING UP</h2>
    <div class="gg-hp-sidebar-card gg-hp-coming-up-compact">{coming_items}
    </div>'''
    else:
        coming_html = f'''<h2 class="gg-hp-col-header">COMING UP</h2>
    <div class="gg-hp-sidebar-card gg-hp-coming-up-compact">
      <p class="gg-hp-coming-compact-empty">Off-season. <a href="{SITE_BASE_URL}/gravel-races/">Browse all races &rarr;</a></p>
    </div>'''

    # 5. Sidebar CTA
    cta_html = f'''<div class="gg-hp-sidebar-cta">
      <h3>Don&rsquo;t wing race day</h3>
      <p>Your target race has specific terrain, elevation, and weather. Your plan should too.</p>
      <a href="{esc(TRAINING_PLANS_URL)}" class="gg-hp-sidebar-cta-btn" data-ga="sidebar_cta_click">Get Your Plan &rarr;</a>
    </div>'''

    return f'''{stats_html}
    {pullquote_html}
    {rankings_html}
    {coming_html}
    {cta_html}'''


def build_content_grid(race_index: list, stats: dict, upcoming: list) -> str:
    """Wrap main column content and sidebar into a 2-column grid."""
    main = build_bento_features(race_index)
    main += build_tabbed_rankings(race_index)
    main += build_latest_takes()
    sidebar = build_sidebar(stats, race_index, upcoming)
    return f'''<div class="gg-hp-content-grid">
    <section class="gg-hp-main-col" aria-label="Featured content">{main}</section>
    <aside class="gg-hp-sidebar" aria-label="Statistics and rankings">
      <div class="gg-hp-sidebar-sticky">{sidebar}</div>
    </aside>
  </div>'''


def build_how_it_works(stats: dict = None) -> str:
    race_count = stats["race_count"] if stats else 328
    steps = [
        ("01", "PICK YOUR RACE", f"{race_count} races. Scored honestly. Filter by what actually matters to you &mdash; not what a sponsor paid us to promote."),
        ("02", "READ THE REAL TAKE", "Every rating comes with an editorial opinion. We tell you if it&rsquo;s worth the flight, the entry fee, and the suffering."),
        ("03", "SHOW UP READY", "You&rsquo;ve already paid for the entry fee. Don&rsquo;t waste it. Race-specific plans so you don&rsquo;t blow up at mile 60 like we did."),
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
    return f'''<section class="gg-hp-training-cta-full" id="training" aria-label="Training call to action">
    <div class="gg-hp-cta-card">
      <div class="gg-hp-cta-left">
        <h2>Train for the course, not just the distance</h2>
        <p>Every generic plan treats gravel like a road race with dirt. This isn&rsquo;t that. Training plans matched to your target race&rsquo;s exact terrain, elevation profile, and typical conditions. Built around your schedule, your fitness, and your goal.</p>
        <p class="gg-hp-cta-price" data-ab="training_price">Race-specific. Built for your target event. Less than your race hotel &mdash; $2/day.</p>
        <a href="{esc(TRAINING_PLANS_URL)}" class="gg-hp-cta-btn" data-ga="training_plan_click" data-ab="training_cta_btn">Get Your Plan &rarr;</a>
      </div>
      <div class="gg-hp-cta-right" role="img" aria-label="Training plan preview"></div>
    </div>
  </section>'''


def build_testimonials() -> str:
    """Build the athlete testimonials section with quotes from coached athletes."""
    if not TESTIMONIALS:
        return ""

    cards = ""
    for t in TESTIMONIALS:
        cards += f'''
      <div class="gg-hp-test-card">
        <blockquote class="gg-hp-test-quote">&ldquo;{esc(t["quote"])}&rdquo;</blockquote>
        <div class="gg-hp-test-attr">
          <span class="gg-hp-test-name">{esc(t["name"])}</span>
          <span class="gg-hp-test-title">{esc(t["title"])}</span>
        </div>
        <div class="gg-hp-test-tags">{esc(t["tags"])}</div>
      </div>'''

    return f'''<section class="gg-hp-testimonials" id="testimonials">
    <div class="gg-hp-section-header">
      <h2>ATHLETE RESULTS</h2>
    </div>
    <div class="gg-hp-test-grid">{cards}
    </div>
    <div class="gg-hp-test-cta">
      <p data-ab="coaching_scarcity">A human in your corner. Adapts week to week. Limited spots.</p>
      <a href="{esc(COACHING_URL)}" class="gg-hp-btn gg-hp-btn--primary" data-ga="coaching_cta_testimonials">SEE COACHING OPTIONS &rarr;</a>
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
    return get_mega_footer_html()


# ── CSS ──────────────────────────────────────────────────────


def build_homepage_css() -> str:
    font_face = get_font_face_css()
    tokens = get_tokens_css()
    mega_footer_css = get_mega_footer_css()
    return '<style>\n/* ── Self-hosted fonts ──────────────────────────────────── */\n' + font_face + '\n\n' + tokens + '\n\n' + '''/* ── Ticker (functional animation) ───────────────────────── */
@keyframes gg-ticker-scroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }

/* ── Custom properties ───────────────────────────────────── */
:root { --gg-ease: var(--gg-ease); }

/* ── Reset & base ────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Source Serif 4', Georgia, serif; color: #3a2e25; line-height: 1.75; background: #ede4d8; margin: 0; }
a { text-decoration: none; color: #178079; }

/* ── Page container ──────────────────────────────────────── */
.gg-hp-page { margin: 0; padding: 0; }

/* ── Scroll progress ── */
.gg-hp-scroll-progress { position: fixed; top: 0; left: 0; height: 3px; width: 0%; background: #B7950B; z-index: 200; will-change: width; }

/* ── Gold top bar ── */
.gg-hp-top-bar { height: 4px; background: #B7950B; }

''' + get_site_header_css() + '''

/* ── Ticker ──────────────────────────────────────────────── */
.gg-hp-ticker { background: #ede4d8; border-bottom: 1px solid #d4c5b9; overflow: hidden; white-space: nowrap; }
.gg-hp-ticker-track { overflow: hidden; }
.gg-hp-ticker-content { display: inline-block; animation: gg-ticker-scroll 60s linear infinite; padding: 10px 0; }
.gg-hp-ticker-content:hover { animation-play-state: paused; }
.gg-hp-ticker-item { font-family: 'Sometype Mono', monospace; font-size: 11px; color: #7d695d; letter-spacing: 0.5px; }
.gg-hp-ticker-item a { color: #59473c; text-decoration: none; transition: color var(--gg-ease); }
.gg-hp-ticker-item a:hover { color: #9a7e0a; }
.gg-hp-ticker-sep { color: #d4c5b9; margin: 0 20px; }
.gg-ticker-tag { display: inline-block; padding: 1px 6px; font-family: 'Sometype Mono', monospace; font-size: 9px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; margin-right: 6px; }
.gg-ticker-tag--teal { background: #178079; color: #fff; }
.gg-ticker-tag--gold { background: #9a7e0a; color: #fff; }
.gg-ticker-tag--brown { background: #59473c; color: #fff; }
.gg-ticker-tag--red { background: #c0392b; color: #fff; }
.gg-hp-ticker-mobile { display: none; }

/* ── Announcement pill ── */
.gg-hp-announce-pill { display: inline-flex; align-items: center; gap: 8px; padding: 6px 16px; border: 2px solid #B7950B; margin-bottom: 20px; font-family: 'Sometype Mono', monospace; font-size: 11px; font-weight: 600; color: #B7950B; text-transform: uppercase; letter-spacing: 1px; }
.gg-hp-announce-dot { width: 6px; height: 6px; background: #178079; animation: gg-announce-pulse 2s ease-in-out infinite; }
@keyframes gg-announce-pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

/* ── Accent line ── */
.gg-hp-accent-line { width: 48px; height: 3px; background: #178079; margin-bottom: 16px; }

/* ── Hero ─────────────────────────────────────────────────── */
.gg-hp-hero { background: #f5efe6; padding: 64px 48px; border-bottom: 3px solid #3a2e25; }
.gg-hp-hero-inner { max-width: 960px; margin: 0 auto; display: grid; grid-template-columns: 1fr 1fr; gap: 64px; align-items: center; }
.gg-hp-hero-kicker { font-family: 'Sometype Mono', monospace; font-size: 10px; font-weight: 700; color: #B7950B; text-transform: uppercase; letter-spacing: 3px; margin-bottom: 16px; }
.gg-hp-hero h1 { font-family: 'Source Serif 4', Georgia, serif; font-size: 48px; font-weight: 900; line-height: 1.05; margin-bottom: 12px; color: #3a2e25; }
.gg-hp-hero-deck { font-size: 17px; font-weight: 300; color: #59473c; line-height: 1.7; margin-bottom: 28px; }
.gg-hp-hero-actions { display: flex; gap: 12px; flex-wrap: wrap; }
.gg-hp-btn-primary { display: inline-block; padding: 12px 28px; background: #3a2e25; color: #f5efe6; font-family: 'Sometype Mono', monospace; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; border: 2px solid #3a2e25; text-decoration: none; transition: background-color .3s, color .3s; }
.gg-hp-btn-primary:hover { background: #B7950B; color: #1a1613; border-color: #B7950B; }
.gg-hp-btn-secondary { display: inline-block; padding: 12px 28px; background: transparent; color: #3a2e25; font-family: 'Sometype Mono', monospace; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; border: 2px solid #3a2e25; text-decoration: none; transition: border-color .3s, color .3s; }
.gg-hp-btn-secondary:hover { border-color: #178079; color: #178079; }

/* ── Hero featured card ── */
.gg-hp-hero-feature { display: block; background: #ede4d8; border: 3px solid #3a2e25; text-decoration: none; color: inherit; transition: border-color .3s; }
.gg-hp-hero-feature:hover { border-color: #178079; }
.gg-hp-hero-feature:hover .gg-hp-hf-name { color: #178079; }
.gg-hp-hf-img { height: 180px; background: #d4c5b9; border-bottom: 2px solid #3a2e25; }
.gg-hp-hf-body { padding: 24px; }
.gg-hp-hf-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 8px; }
.gg-hp-hf-tier { font-family: 'Sometype Mono', monospace; font-size: 10px; font-weight: 700; color: #178079; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 4px; }
.gg-hp-hf-name { font-size: 22px; font-weight: 900; color: #3a2e25; }
.gg-hp-hf-score { font-family: 'Sometype Mono', monospace; font-size: 36px; font-weight: 700; color: #178079; line-height: 1; flex-shrink: 0; }
.gg-hp-hf-meta { font-family: 'Sometype Mono', monospace; font-size: 11px; color: #8c7568; margin-bottom: 8px; }
.gg-hp-hf-excerpt { font-size: 14px; color: #59473c; line-height: 1.6; }

/* ── Buttons ─────────────────────────────────────────────── */
.gg-hp-btn { display: inline-block; padding: 14px 32px; font-family: 'Sometype Mono', monospace; font-size: 12px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; text-align: center; cursor: pointer; border: 3px solid transparent; transition: background-color var(--gg-ease), border-color var(--gg-ease), color var(--gg-ease); }
.gg-hp-btn--primary { background: #f5efe6; color: #3a2e25; border-color: #3a2e25; }
.gg-hp-btn--primary:hover { border-color: #9a7e0a; color: #9a7e0a; }
.gg-hp-btn--secondary { background: transparent; color: #d4c5b9; border-color: #d4c5b9; }
.gg-hp-btn--secondary:hover { color: #fff; border-color: #9a7e0a; }
/* On light backgrounds, dark button variant */
.gg-hp-cal-cta .gg-hp-btn--primary,
.gg-hp-guide-cta .gg-hp-btn--primary { background: #9a7e0a; color: #f5efe6; border-color: #9a7e0a; }
.gg-hp-cal-cta .gg-hp-btn--primary:hover,
.gg-hp-guide-cta .gg-hp-btn--primary:hover { border-color: #9a7e0a; color: #fff; }

/* ── Stats stripe ───────────────────────────────────────── */
.gg-hp-stats-stripe { background: #3a2e25; padding: 0 48px; }
.gg-hp-stats-inner { max-width: 960px; margin: 0 auto; display: grid; grid-template-columns: repeat(5, 1fr); }
.gg-hp-ss-item { text-align: center; padding: 20px 0; border-right: 2px solid #59473c; }
.gg-hp-ss-item:last-child { border-right: none; }
.gg-hp-ss-val { font-family: 'Sometype Mono', monospace; font-size: 24px; font-weight: 700; color: #B7950B; }
.gg-hp-ss-lbl { font-family: 'Sometype Mono', monospace; font-size: 9px; color: #A68E80; text-transform: uppercase; letter-spacing: 1px; }

/* ── Section headers ─────────────────────────────────────── */
.gg-hp-section-header { background: #f5efe6; padding: 16px 20px; border-bottom: 1px solid #9a7e0a; }
.gg-hp-section-header h2 { font-family: 'Sometype Mono', monospace; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 3px; color: #3a2e25; margin: 0; }
.gg-hp-section-header--teal { border-bottom-color: #178079; }

/* ── Content grid ───────────────────────────────────────── */
.gg-hp-content-grid { max-width: 960px; margin: 0 auto; padding: 48px; display: grid; grid-template-columns: 7fr 5fr; gap: 48px; }
.gg-hp-sidebar-sticky { position: sticky; top: 24px; max-height: calc(100vh - 48px); overflow-y: auto; }
.gg-hp-col-header { font-family: 'Sometype Mono', monospace; font-size: 10px; font-weight: 700; color: #B7950B; text-transform: uppercase; letter-spacing: 3px; padding-bottom: 12px; border-bottom: 3px solid #3a2e25; margin-bottom: 24px; }

/* ── Bento features ─────────────────────────────────────── */
.gg-hp-bento { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 36px; }
.gg-hp-bento-lead { grid-column: 1 / -1; }
.gg-hp-bento-card { cursor: pointer; background: #f5efe6; border: 2px solid #d4c5b9; transition: border-color .3s; text-decoration: none; color: inherit; display: block; }
.gg-hp-bento-card:hover, .gg-hp-bento-card:focus-visible { border-color: #178079; }
.gg-hp-bento-card:hover .gg-hp-bento-name, .gg-hp-bento-card:focus-visible .gg-hp-bento-name { color: #178079; }
.gg-hp-bento-img { width: 100%; height: 220px; background: #d4c5b9; border-bottom: 2px solid #d4c5b9; }
.gg-hp-bento-img.short { height: 140px; }
.gg-hp-bento-body { padding: 20px; }
.gg-hp-bento-meta { font-family: 'Sometype Mono', monospace; font-size: 11px; font-weight: 700; color: #B7950B; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 8px; }
.gg-hp-bento-name { font-size: 24px; font-weight: 700; line-height: 1.15; margin-bottom: 8px; transition: color .3s; }
.gg-hp-bento-name.lg { font-size: 28px; }
.gg-hp-bento-excerpt { font-size: 14px; color: #59473c; line-height: 1.7; }
.gg-hp-bento-byline { font-family: 'Sometype Mono', monospace; font-size: 11px; color: #8c7568; letter-spacing: .5px; margin-top: 8px; }

/* ── Tabs ───────────────────────────────────────────────── */
.gg-hp-tab-bar { display: flex; gap: 0; margin-bottom: 0; }
.gg-hp-tab-bar [role="tab"] { padding: 10px 20px; font-family: 'Sometype Mono', monospace; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #8c7568; background: #ede4d8; border: 2px solid #d4c5b9; border-bottom: none; cursor: pointer; transition: color .3s, background-color .3s; }
.gg-hp-tab-bar [role="tab"][aria-selected="true"] { color: #1a1613; background: #f5efe6; border-color: #3a2e25; }
.gg-hp-tab-bar [role="tab"]:hover { color: #1a1613; }
[role="tabpanel"] { border: 2px solid #3a2e25; border-top: 3px solid #3a2e25; padding: 24px; background: #f5efe6; }
.gg-hp-tab-inactive { display: none; }

/* ── Article items (ranking rows) ───────────────────────── */
.gg-hp-article-item { display: grid; grid-template-columns: auto 1fr auto; gap: 16px; padding: 16px 0; border-top: 2px solid #d4c5b9; cursor: pointer; align-items: start; text-decoration: none; color: inherit; }
.gg-hp-article-item:first-child { border-top: none; }
.gg-hp-article-item:hover .gg-hp-article-name, .gg-hp-article-item:focus-visible .gg-hp-article-name { color: #178079; }
.gg-hp-article-num { font-size: 24px; font-weight: 700; color: #d4c5b9; line-height: 1; min-width: 32px; }
.gg-hp-article-meta { font-family: 'Sometype Mono', monospace; font-size: 10px; font-weight: 700; color: #B7950B; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
.gg-hp-article-name { font-size: 18px; font-weight: 700; line-height: 1.25; margin-bottom: 4px; transition: color .3s; }
.gg-hp-article-excerpt { font-size: 14px; color: #59473c; line-height: 1.6; }
.gg-hp-article-score { font-family: 'Sometype Mono', monospace; font-size: 18px; font-weight: 700; color: #178079; }

/* ── Sidebar ────────────────────────────────────────────── */
.gg-hp-sidebar-card { background: #f5efe6; border: 2px solid #3a2e25; padding: 28px; margin-bottom: 24px; }
.gg-hp-sidebar-stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.gg-hp-sb-stat { text-align: center; padding: 16px 12px; background: #ede4d8; border: 2px solid #d4c5b9; }
.gg-hp-sb-stat-val { font-family: 'Sometype Mono', monospace; font-size: 28px; font-weight: 700; color: #1a1613; }
.gg-hp-sb-stat-lbl { font-family: 'Sometype Mono', monospace; font-size: 10px; color: #8c7568; text-transform: uppercase; letter-spacing: 1px; }
.gg-hp-pullquote { font-size: 17px; font-style: italic; line-height: 1.6; color: #59473c; padding: 20px 0; border-top: 3px solid #B7950B; border-bottom: 2px solid #d4c5b9; margin-bottom: 24px; }
.gg-hp-pullquote cite { display: block; font-family: 'Sometype Mono', monospace; font-size: 10px; font-style: normal; color: #B7950B; margin-top: 8px; letter-spacing: 1px; text-transform: uppercase; }
.gg-hp-rank-list { list-style: none; padding: 0; }
.gg-hp-rank-item { display: flex; justify-content: space-between; align-items: baseline; padding: 10px 0; border-bottom: 2px solid #d4c5b9; }
.gg-hp-rank-item:last-child { border-bottom: none; }
.gg-hp-rank-pos { font-family: 'Sometype Mono', monospace; font-size: 12px; font-weight: 700; color: #8c7568; min-width: 24px; }
.gg-hp-rank-name { font-size: 14px; font-weight: 600; flex: 1; }
.gg-hp-rank-score { font-family: 'Sometype Mono', monospace; font-size: 14px; font-weight: 700; color: #178079; }
.gg-hp-sidebar-cta { background: #1a1613; border: 3px solid #3a2e25; padding: 32px 28px; text-align: center; }
.gg-hp-sidebar-cta h3 { font-size: 22px; font-weight: 700; color: #f5efe6; margin-bottom: 8px; }
.gg-hp-sidebar-cta p { font-size: 14px; color: #A68E80; margin-bottom: 20px; line-height: 1.6; }
.gg-hp-sidebar-cta-btn { display: inline-block; background: #B7950B; color: #1a1613; padding: 12px 24px; border: none; font-family: 'Sometype Mono', monospace; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; text-decoration: none; transition: background-color .3s; }
.gg-hp-sidebar-cta-btn:hover { background-color: #c9a92c; }

/* ── Coming up compact (sidebar) ────────────────────────── */
.gg-hp-coming-up-compact { padding: 0; }
.gg-hp-coming-compact-empty { padding: 16px; font-family: 'Sometype Mono', monospace; font-size: 12px; color: #8c7568; }
.gg-hp-coming-compact-empty a { color: #178079; font-weight: 700; }
.gg-hp-coming-compact-item { display: flex; align-items: center; gap: 12px; padding: 10px 16px; border-bottom: 2px solid #d4c5b9; text-decoration: none; color: inherit; transition: background-color .3s; }
.gg-hp-coming-compact-item:last-child { border-bottom: none; }
.gg-hp-coming-compact-item:hover { background: #ede4d8; }
.gg-hp-coming-compact-date { font-family: 'Sometype Mono', monospace; font-size: 10px; font-weight: 700; color: #8c7568; letter-spacing: 1px; text-transform: uppercase; min-width: 50px; }
.gg-hp-coming-compact-name { font-size: 13px; font-weight: 600; flex: 1; }
.gg-hp-coming-compact-tier { font-family: 'Sometype Mono', monospace; font-size: 9px; font-weight: 700; letter-spacing: 1px; padding: 2px 6px; }

/* ── Tier badges ── */
.gg-hp-tier-badge { display: inline-block; font-family: 'Sometype Mono', monospace; padding: 2px 8px; font-size: 9px; font-weight: 700; letter-spacing: 2px; }
.gg-hp-badge-t1 { background: transparent; color: #59473c; border: 1px solid #59473c; }
.gg-hp-badge-t2 { background: transparent; color: #7d695d; border: 1px solid #7d695d; }
.gg-hp-badge-t3 { background: transparent; color: #766a5e; border: 1px solid #766a5e; }
.gg-hp-badge-t4 { background: transparent; color: #5e6868; border: 1px solid #5e6868; }

/* ── Latest Takes ───────────────────────────────────────── */
.gg-hp-latest-takes { margin: 32px 0 0; border: 1px solid #d4c5b9; }
.gg-hp-section-header--gold { border-bottom-color: #9a7e0a; }
.gg-hp-take-carousel { display: flex; gap: 0; overflow-x: auto; scroll-snap-type: x mandatory; -webkit-overflow-scrolling: touch; scrollbar-width: none; }
.gg-hp-take-carousel::-webkit-scrollbar { display: none; }
.gg-hp-take-card { flex: 0 0 calc(50% - 0px); scroll-snap-align: start; display: flex; flex-direction: column; padding: 24px; border: 1px solid #d4c5b9; text-decoration: none; color: #3a2e25; background: #f5efe6; transition: border-color var(--gg-ease); box-sizing: border-box; min-width: 0; }
.gg-hp-take-card:hover { border-color: #9a7e0a; }
.gg-hp-take-tag { display: inline-block; font-family: 'Sometype Mono', monospace; font-size: 9px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: #9a7e0a; margin-bottom: 10px; }
.gg-hp-take-title { font-family: 'Source Serif 4', Georgia, serif; font-size: 16px; font-weight: 700; line-height: 1.3; margin-bottom: 10px; }
.gg-hp-take-teaser { font-family: 'Source Serif 4', Georgia, serif; font-size: 13px; color: #7d695d; line-height: 1.7; margin: 0 0 16px; flex: 1; }
.gg-hp-take-read { font-family: 'Sometype Mono', monospace; font-size: 11px; font-weight: 700; letter-spacing: 2px; color: #178079; }
.gg-hp-take-nav { display: flex; align-items: center; justify-content: center; gap: 16px; padding: 16px; background: #ede4d8; border-top: 1px solid #d4c5b9; }
.gg-hp-take-btn { width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 700; background: #f5efe6; border: 2px solid #3a2e25; color: #3a2e25; cursor: pointer; font-family: 'Sometype Mono', monospace; transition: background-color var(--gg-ease), border-color var(--gg-ease); }
.gg-hp-take-btn:hover { background: #9a7e0a; color: #f5efe6; border-color: #9a7e0a; }
.gg-hp-take-counter { font-family: 'Sometype Mono', monospace; font-size: 12px; font-weight: 700; letter-spacing: 2px; color: #7d695d; min-width: 48px; text-align: center; }
.gg-hp-take-cta { padding: 24px; text-align: center; background: #ede4d8; border-top: 2px solid #d4c5b9; }
.gg-hp-take-cta .gg-hp-btn--primary { background: #9a7e0a; color: #f5efe6; border-color: #9a7e0a; }
.gg-hp-take-cta .gg-hp-btn--primary:hover { background: #c9a92c; border-color: #c9a92c; }

/* ── How it works ────────────────────────────────────────── */
.gg-hp-how-it-works { background: #f5efe6; display: grid; grid-template-columns: repeat(3, 1fr); margin-top: 32px; border: 1px solid #d4c5b9; border-top: 2px solid #9a7e0a; max-width: 960px; margin: 32px auto 0; }
.gg-hp-step { padding: 36px 24px; border-right: 1px solid #d4c5b9; }
.gg-hp-step:last-child { border-right: none; }
.gg-hp-step-num { display: block; font-family: 'Sometype Mono', monospace; font-size: 36px; font-weight: 700; color: #9a7e0a; margin-bottom: 12px; }
.gg-hp-step-title { font-family: 'Sometype Mono', monospace; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; color: #3a2e25; margin-bottom: 10px; }
.gg-hp-step-desc { font-family: 'Source Serif 4', Georgia, serif; font-size: 14px; color: #7d695d; line-height: 1.7; }

/* ── Coming Up (kept for compatibility) ─────────────────── */
.gg-hp-coming-up { max-width: 960px; margin: 32px auto 0; border: 1px solid #d4c5b9; }
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

/* ── Training CTA (split card) ──────────────────────────── */
.gg-hp-training-cta-full { max-width: 960px; margin: 32px auto 0; padding: 0 48px; }
.gg-hp-cta-card { display: grid; grid-template-columns: 1fr 1fr; border: 3px solid #3a2e25; }
.gg-hp-cta-left { background: #1a1613; padding: 40px; display: flex; flex-direction: column; justify-content: center; }
.gg-hp-cta-left h2 { font-size: 28px; font-weight: 900; color: #f5efe6; margin-bottom: 8px; }
.gg-hp-cta-left p { font-size: 14px; color: #A68E80; line-height: 1.7; margin-bottom: 20px; }
.gg-hp-cta-btn { display: inline-block; padding: 12px 28px; background: #B7950B; color: #1a1613; font-family: 'Sometype Mono', monospace; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; border: none; text-decoration: none; align-self: flex-start; transition: background-color .3s; }
.gg-hp-cta-btn:hover { background-color: #c9a92c; }
.gg-hp-cta-right { background: #d4c5b9; min-height: 200px; }

/* ── Guide Preview ───────────────────────────────────────── */
.gg-hp-guide { max-width: 960px; margin: 32px auto 0; border: 1px solid #d4c5b9; }
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
.gg-hp-featured-in { max-width: 960px; margin: 32px auto 0; border: 1px solid #d4c5b9; background: #f5efe6; }
.gg-hp-feat-inner { display: flex; align-items: center; gap: 32px; padding: 32px 24px; }
.gg-hp-feat-text { flex: 0 0 auto; max-width: 260px; }
.gg-hp-feat-label { display: inline-block; font-family: 'Sometype Mono', monospace; font-size: 10px; font-weight: 700; letter-spacing: 4px; text-transform: uppercase; color: #9a7e0a; margin-bottom: 8px; }
.gg-hp-feat-copy { font-family: 'Source Serif 4', Georgia, serif; font-size: 13px; line-height: 1.7; color: #7d695d; font-style: italic; margin: 0; }
.gg-hp-feat-logos { display: flex; align-items: center; gap: 32px; flex: 1; justify-content: center; flex-wrap: wrap; }
.gg-hp-feat-logo { display: block; transition: border-color var(--gg-ease); border: 2px solid transparent; padding: 8px; }
.gg-hp-feat-logo:hover { border-color: #9a7e0a; }
.gg-hp-feat-logo img { display: block; height: 56px; width: auto; }

/* ── Testimonials ────────────────────────────────────────── */
.gg-hp-testimonials { max-width: 960px; margin: 32px auto 0; border: 1px solid #d4c5b9; }
.gg-hp-test-grid { display: grid; grid-template-columns: repeat(2, 1fr); }
.gg-hp-test-card { padding: 24px; border: 1px solid #d4c5b9; background: #f5efe6; }
.gg-hp-test-quote { font-family: 'Source Serif 4', Georgia, serif; font-size: 14px; line-height: 1.75; color: #3a2e25; font-style: italic; margin: 0 0 16px; border-left: 3px solid #9a7e0a; padding-left: 16px; }
.gg-hp-test-attr { margin-bottom: 8px; }
.gg-hp-test-name { font-family: 'Sometype Mono', monospace; font-size: 12px; font-weight: 700; color: #3a2e25; letter-spacing: 1px; }
.gg-hp-test-title { font-family: 'Sometype Mono', monospace; font-size: 11px; color: #9a7e0a; letter-spacing: 0.5px; margin-left: 8px; }
.gg-hp-test-tags { font-family: 'Sometype Mono', monospace; font-size: 9px; color: #7d695d; letter-spacing: 1.5px; text-transform: uppercase; }
.gg-hp-test-cta { padding: 20px; text-align: center; background: #ede4d8; border-top: 2px solid #d4c5b9; }
.gg-hp-test-cta .gg-hp-btn--primary { background: #9a7e0a; color: #f5efe6; border-color: #9a7e0a; }
.gg-hp-test-cta .gg-hp-btn--primary:hover { border-color: #9a7e0a; color: #fff; }

/* ── Email capture ───────────────────────────────────────── */
.gg-hp-email { background: #f5efe6; padding: 48px; border: 1px solid #d4c5b9; border-top: 2px solid #178079; max-width: 960px; margin: 32px auto 0; }
.gg-hp-email-inner { max-width: 560px; margin: 0 auto; text-align: center; }
.gg-hp-email-label { display: inline-block; font-family: 'Sometype Mono', monospace; font-size: 10px; font-weight: 700; letter-spacing: 4px; text-transform: uppercase; color: #9a7e0a; margin-bottom: 12px; }
.gg-hp-email-title { font-family: 'Source Serif 4', Georgia, serif; font-size: 28px; font-weight: 700; color: #3a2e25; margin-bottom: 12px; }
.gg-hp-email-text { font-family: 'Source Serif 4', Georgia, serif; font-size: 14px; color: #7d695d; margin-bottom: 0; line-height: 1.75; }

/* ── Article carousel (email section) ───────────────────── */
.gg-hp-article-carousel { display: flex; gap: 16px; overflow-x: auto; scroll-snap-type: x mandatory; padding: 24px 48px; -webkit-overflow-scrolling: touch; }
.gg-hp-article-carousel::-webkit-scrollbar { height: 4px; }
.gg-hp-article-carousel::-webkit-scrollbar-track { background: #d4c5b9; }
.gg-hp-article-carousel::-webkit-scrollbar-thumb { background: #9a7e0a; }
.gg-hp-article-card { flex: 0 0 280px; scroll-snap-align: start; padding: 20px; background: #f5efe6; border: 2px solid transparent; text-decoration: none; color: #3a2e25; transition: border-color var(--gg-ease); }
.gg-hp-article-card:hover { border-color: #9a7e0a; }
.gg-hp-article-title { font-family: 'Source Serif 4', Georgia, serif; font-size: 15px; font-weight: 700; line-height: 1.3; margin-bottom: 8px; }
.gg-hp-article-snippet { font-family: 'Source Serif 4', Georgia, serif; font-size: 12px; color: #7d695d; line-height: 1.6; margin: 0; }

/* ── Email form ─────────────────────────────────────────── */
.gg-hp-email-form { background: #f5efe6; padding: 20px 32px; max-width: 480px; margin: 24px auto 0; min-height: 150px; }

/* ── Skip link ───────────────────────────────────────────── */
.gg-hp-skip { position: absolute; left: -9999px; top: auto; width: 1px; height: 1px; overflow: hidden; font-family: 'Sometype Mono', monospace; font-size: 12px; font-weight: 700; letter-spacing: 2px; padding: 12px 24px; background: #9a7e0a; color: #3a2e25; z-index: 100; }
.gg-hp-skip:focus { position: fixed; top: 0; left: 0; width: auto; height: auto; }

/* ── Responsive: 900px ─────────────────────────────────── */
@media (max-width: 900px) {
  .gg-hp-hero-inner { grid-template-columns: 1fr; gap: 32px; }
  .gg-hp-cta-card { grid-template-columns: 1fr; }
  .gg-hp-content-grid { grid-template-columns: 1fr; }
  .gg-hp-sidebar-sticky { position: static; max-height: none; }
  .gg-hp-bento { grid-template-columns: 1fr; }
}

/* ── Responsive: 600px ─────────────────────────────────── */
@media (max-width: 600px) {
  html, body { overflow-x: hidden; }
  .gg-hp-page { overflow-x: hidden; }

  /* Ticker — scrolling version hidden, static mobile version shown */
  .gg-hp-ticker { display: none; }
  .gg-hp-ticker-mobile { display: block; background: #ede4d8; border-bottom: 1px solid #d4c5b9; padding: 10px 16px; text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  /* Hero */
  .gg-hp-hero { padding: 36px 16px; }
  .gg-hp-hero h1 { font-size: 28px; }
  .gg-hp-hero-actions { flex-direction: column; }
  .gg-hp-hero-actions a { width: 100%; text-align: center; }

  /* Stats stripe */
  .gg-hp-stats-inner { grid-template-columns: repeat(2, 1fr); }
  .gg-hp-ss-item:nth-child(2) { border-right: none; }
  .gg-hp-ss-item:nth-child(5) { grid-column: 1 / -1; border-right: none; }

  /* Article score hidden */
  .gg-hp-article-score { display: none; }

  /* Latest takes */
  .gg-hp-take-card { flex: 0 0 100%; padding: 16px; }
  .gg-hp-take-cta { padding: 16px; }

  /* How it works */
  .gg-hp-how-it-works { grid-template-columns: 1fr; }
  .gg-hp-step { padding: 24px 16px; border-right: none; border-bottom: 1px solid #d4c5b9; }
  .gg-hp-step:last-child { border-bottom: none; }
  .gg-hp-step-num { font-size: 28px; }

  /* Content grid */
  .gg-hp-content-grid { padding: 24px 16px; gap: 24px; }

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

  /* Training CTA */
  .gg-hp-training-cta-full { padding: 0 16px; }

  /* Testimonials */
  .gg-hp-test-grid { grid-template-columns: 1fr; }
  .gg-hp-test-card { padding: 16px; }
  .gg-hp-test-quote { font-size: 13px; }

  /* Full-bleed sections on mobile */
  .gg-hp-latest-takes, .gg-hp-how-it-works, .gg-hp-coming-up,
  .gg-hp-guide, .gg-hp-featured-in, .gg-hp-email, .gg-hp-testimonials { margin: 16px 0 0; border-left: none; border-right: none; }

  /* Buttons */
  .gg-hp-btn { padding: 12px 20px; font-size: 11px; letter-spacing: 1.5px; }

  /* Email / articles — stack vertically on mobile, show max 3 */
  .gg-hp-email { padding: 32px 0; }
  .gg-hp-email-inner { padding: 0 16px; }
  .gg-hp-email-title { font-size: 22px; }
  .gg-hp-article-carousel { flex-direction: column; overflow-x: visible; scroll-snap-type: none; padding: 16px; gap: 12px; }
  .gg-hp-article-card { flex: none; width: 100%; padding: 16px; }
  .gg-hp-article-card:nth-child(n+4) { display: none; }
  .gg-hp-email-form { margin: 20px 16px 0; padding: 16px; }

  /* Section headers */
  .gg-hp-section-header { padding: 12px 16px; }
  .gg-hp-section-header h2 { font-size: 11px; letter-spacing: 2px; }
}

/* ── Responsive: 480px ─────────────────────────────────── */
@media (max-width: 480px) {
  .gg-hp-hero { padding: 24px 12px; }
  .gg-hp-content-grid { padding: 16px 12px; }
  .gg-hp-training-cta-full { padding: 0 12px; }
  .gg-hp-cta-left { padding: 24px 16px; }
  .gg-hp-btn-primary, .gg-hp-btn-secondary { width: 100%; text-align: center; }
}

/* ── Print ──────────────────────────────────────────────── */
@media print { .gg-hp-scroll-progress, .gg-hp-top-bar, .gg-hp-ticker, .gg-hp-ticker-mobile { display: none; } .gg-hp-sidebar-sticky { position: static; } .gg-hp-stats-stripe { background: none; border: 2px solid #3a2e25; } .gg-hp-ss-val { color: #1a1613; } }

/* ── Reduced motion ────────────────────────────────────── */
@media (prefers-reduced-motion: reduce) { .gg-hp-scroll-progress { display: none; } .gg-hp-announce-dot { animation: none; } }
''' + mega_footer_css + '''
</style>'''


# ── JavaScript ───────────────────────────────────────────────


def build_homepage_js() -> str:
    return '''<script>
(function() {
'use strict';

// GA4 event tracking
document.querySelectorAll('[data-ga]').forEach(function(el) {
  el.addEventListener('click', function() {
    var event_name = el.getAttribute('data-ga');
    var label = el.getAttribute('data-ga-label') || '';
    if (typeof gtag === 'function') {
      gtag('event', event_name, { event_label: label });
    }
  });
});

// Scroll progress — rAF-throttled
var progressBar = document.getElementById('scrollProgress');
var scrollTicking = false;
function updateScrollProgress() {
  var doc = document.documentElement;
  var scrollable = doc.scrollHeight - doc.clientHeight;
  if (scrollable <= 0) { progressBar.style.width = '0%'; scrollTicking = false; return; }
  var pct = Math.min((doc.scrollTop / scrollable) * 100, 100);
  progressBar.style.width = pct + '%';
  scrollTicking = false;
}
window.addEventListener('scroll', function() {
  if (!scrollTicking) { requestAnimationFrame(updateScrollProgress); scrollTicking = true; }
}, { passive: true });

// Animated counters
var prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
var counterEls = document.querySelectorAll('[data-counter]');
if (!prefersReducedMotion && counterEls.length > 0) {
  var counterObserver = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (!entry.isIntersecting) return;
      var el = entry.target;
      if (el.dataset.counterDone) return;
      el.dataset.counterDone = 'true';
      var target = parseInt(el.dataset.counter, 10);
      var suffix = el.dataset.suffix || '';
      var duration = 1200;
      var start = performance.now();
      function tick(now) {
        var progress = Math.min((now - start) / duration, 1);
        var eased = 1 - Math.pow(1 - progress, 3);
        var current = Math.round(eased * target);
        el.textContent = current.toLocaleString() + suffix;
        if (progress < 1) { requestAnimationFrame(tick); }
        else { el.textContent = target.toLocaleString() + suffix; }
      }
      el.textContent = '0' + suffix;
      requestAnimationFrame(tick);
    });
  }, { threshold: 0.2 });
  counterEls.forEach(function(el) { counterObserver.observe(el); });
}

// ARIA tabs
var tablist = document.querySelector('[role="tablist"]');
if (tablist) {
  var tabs = Array.from(tablist.querySelectorAll('[role="tab"]'));
  var panels = tabs.map(function(tab) { return document.getElementById(tab.getAttribute('aria-controls')); });
  function activateTab(tab) {
    tabs.forEach(function(t, i) {
      t.setAttribute('aria-selected', 'false');
      t.setAttribute('tabindex', '-1');
      if (panels[i]) { panels[i].classList.add('gg-hp-tab-inactive'); panels[i].setAttribute('aria-hidden', 'true'); }
    });
    tab.setAttribute('aria-selected', 'true');
    tab.setAttribute('tabindex', '0');
    tab.focus();
    var panel = document.getElementById(tab.getAttribute('aria-controls'));
    if (panel) { panel.classList.remove('gg-hp-tab-inactive'); panel.removeAttribute('aria-hidden'); }
  }
  tabs.forEach(function(tab) { tab.addEventListener('click', function() { activateTab(tab); }); });
  tablist.addEventListener('keydown', function(e) {
    var ci = tabs.indexOf(document.activeElement);
    if (ci === -1) return;
    var ni;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); ni = (ci + 1) % tabs.length; }
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); ni = (ci - 1 + tabs.length) % tabs.length; }
    else if (e.key === 'Home') { e.preventDefault(); ni = 0; }
    else if (e.key === 'End') { e.preventDefault(); ni = tabs.length - 1; }
    if (ni !== undefined) activateTab(tabs[ni]);
  });
}

// Latest Takes carousel
(function() {
  var carousel = document.getElementById('gg-takes-carousel');
  var prev = document.getElementById('gg-takes-prev');
  var next = document.getElementById('gg-takes-next');
  var counter = document.getElementById('gg-takes-count');
  if (!carousel || !prev || !next) return;
  var cards = carousel.querySelectorAll('.gg-hp-take-card');
  var total = cards.length;

  function perPage() {
    if (window.innerWidth <= 600) return 1;
    return 2;
  }
  function totalPages() {
    return Math.ceil(total / perPage());
  }
  function getPage() {
    if (!cards.length) return 0;
    var cardWidth = cards[0].offsetWidth;
    return Math.round(carousel.scrollLeft / (cardWidth * perPage()));
  }
  function updateCounter() {
    if (counter) counter.textContent = (getPage() + 1) + ' / ' + totalPages();
  }
  function scrollToPage(page) {
    var cardWidth = cards[0].offsetWidth;
    carousel.scrollTo({ left: page * perPage() * cardWidth, behavior: 'smooth' });
  }

  prev.addEventListener('click', function() {
    var page = getPage();
    scrollToPage(page > 0 ? page - 1 : totalPages() - 1);
    stopAuto(); startAuto();
    if (typeof gtag === 'function') gtag('event', 'takes_carousel', { action: 'prev' });
  });
  next.addEventListener('click', function() {
    var page = getPage();
    scrollToPage(page < totalPages() - 1 ? page + 1 : 0);
    stopAuto(); startAuto();
    if (typeof gtag === 'function') gtag('event', 'takes_carousel', { action: 'next' });
  });
  carousel.addEventListener('scroll', function() { updateCounter(); });
  window.addEventListener('resize', function() { updateCounter(); });
  updateCounter();

  // Auto-rotate every 6 seconds, pause on hover
  var autoTimer = null;
  var paused = false;
  function autoAdvance() {
    if (paused) return;
    var page = getPage();
    scrollToPage(page < totalPages() - 1 ? page + 1 : 0);
  }
  function startAuto() { autoTimer = setInterval(autoAdvance, 6000); }
  function stopAuto() { clearInterval(autoTimer); }
  carousel.addEventListener('mouseenter', function() { paused = true; });
  carousel.addEventListener('mouseleave', function() { paused = false; });
  startAuto();
})();

})();
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
        f'<script type="application/ld+json">{json.dumps(org, separators=(",",":"))}</script>',
        f'<script type="application/ld+json">{json.dumps(website, separators=(",",":"))}</script>',
    ]
    return "\n  ".join(parts)


# ── Page assembler ───────────────────────────────────────────


def generate_homepage(race_index: list, race_data_dir: Path = None,
                      guide_path: Path = None) -> str:
    stats = compute_stats(race_index)
    canonical_url = f"{SITE_BASE_URL}/"
    title = f"Gravel God \u2014 {stats['race_count']} Gravel Races Rated & Ranked | The Definitive Database"
    meta_desc = f"The definitive gravel race database. {stats['race_count']} races scored across 14 dimensions, from Unbound to the Tour Divide. Find your next race, compare ratings, and build a training plan."

    one_liners = load_editorial_one_liners(race_data_dir)
    upcoming = load_upcoming_races(race_data_dir)
    substack_posts = fetch_substack_posts()
    chapters = load_guide_chapters(guide_path)

    top_bar = build_top_bar()
    nav = build_nav()
    hero = build_hero(stats, race_index)
    stats_stripe = build_stats_bar(stats)
    ticker = build_ticker(one_liners, substack_posts, upcoming)
    content_grid = build_content_grid(race_index, stats, upcoming)
    how_it_works = build_how_it_works(stats)
    training_cta = build_training_cta()
    guide_preview = build_guide_preview(chapters)
    featured_in = build_featured_in()
    testimonials = build_testimonials()
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
  <link rel="icon" href="data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%27%20viewBox%3D%270%200%2032%2032%27%3E%3Crect%20width%3D%2732%27%20height%3D%2732%27%20fill%3D%27%233a2e25%27%2F%3E%3Ctext%20x%3D%2716%27%20y%3D%2724%27%20text-anchor%3D%27middle%27%20font-family%3D%27serif%27%20font-size%3D%2724%27%20font-weight%3D%27700%27%20fill%3D%27%239a7e0a%27%3EG%3C%2Ftext%3E%3C%2Fsvg%3E">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(meta_desc)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical_url)}">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  {get_preload_hints()}
  {og_tags}
  {jsonld}
  {css}
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA4_MEASUREMENT_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA4_MEASUREMENT_ID}');</script>
  {get_ab_head_snippet()}
</head>
<body>

<div class="gg-hp-scroll-progress" id="scrollProgress" aria-hidden="true"></div>
<a href="#main" class="gg-hp-skip">Skip to content</a>
<div class="gg-hp-page">
  {top_bar}

  {nav}

  {hero}

  {stats_stripe}

  {ticker}

  {content_grid}

  {how_it_works}

  {training_cta}

  {guide_preview}

  {featured_in}

  {testimonials}

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
    print(f"  {stats['race_count']} races, {stats['t1_count']} T1, {stats['t2_count']} T2, {stats['region_count']} regions, {stats['dimensions']} dimensions")
    print(f"  Ticker: {len(one_liners)} one-liners")
    print(f"  Coming up: {len([r for r in upcoming if r['days'] >= 0])} upcoming, {len([r for r in upcoming if r['days'] < 0])} recent")
    print(f"  Guide: {len(chapters)} chapters")


if __name__ == "__main__":
    main()
