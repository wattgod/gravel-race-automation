#!/usr/bin/env python3
"""
Generate race preview blog articles from race JSON data.

Template-based (no Claude API needed). Creates HTML preview articles
for races with upcoming dates, timed to registration windows. Pages render
on the editorial shell (editorial_shell.render_editorial_page): noindex,
no JSON-LD, no article_* events, no read time, no plans ladder.

Usage:
    python wordpress/generate_blog_preview.py --dry-run       # List candidates
    python wordpress/generate_blog_preview.py --slug mid-south # Single preview
    python wordpress/generate_blog_preview.py --all            # All upcoming races
"""

import argparse
import html
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brand_tokens import TIER_NAMES
from blog_tracking import get_plan_intent_tracking_script
from editorial_shell import ArticleMeta, Claim, OgImage, render_editorial_page

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
OUTPUT_DIR = PROJECT_ROOT / "wordpress" / "output" / "blog"
SITE_URL = "https://gravelgodcycling.com"
MONTH_NUMBERS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def esc(text):
    """HTML-escape text."""
    return html.escape(str(text)) if text else ""


# Generic suffering zone labels used as filler in low-data profiles
GENERIC_ZONE_LABELS = {
    "early rolling", "midpoint", "late rolling", "final stretch",
    "early climb", "mid climb", "final descent", "early hills",
    "mid hills", "late hills", "early flat", "mid flat",
    "final push", "opening miles", "middle miles", "closing miles",
}


def is_generic_suffering(suffering_zones):
    """Detect if suffering_zones are generic template filler.

    Returns True if the majority of zone labels match known generic patterns
    or descriptions are very short/templated.
    """
    if not isinstance(suffering_zones, list) or not suffering_zones:
        return False
    generic_count = 0
    for z in suffering_zones:
        if not isinstance(z, dict):
            continue
        label = (z.get("label") or "").lower().strip()
        desc = (z.get("desc") or "").lower().strip()
        # Check for known generic labels
        if label in GENERIC_ZONE_LABELS:
            generic_count += 1
        # Check for very short generic descriptions
        elif len(desc) < 30 and any(g in desc for g in [
            "first rolling", "halfway through", "final rolling",
            "first sections", "last sections", "before finish",
            "opening stretch", "closing stretch",
        ]):
            generic_count += 1
    return generic_count >= len(suffering_zones) * 0.5


# Editorial-interest priority for picking opinion explanations
OPINION_PRIORITY_KEYS = [
    "prestige", "experience", "community", "field_depth",
    "race_quality", "value", "adventure",
]


def pick_best_opinions(biased_opinion_ratings, max_count=3):
    """Select top opinion explanations by editorial interest.

    Picks from high-editorial-value categories, preferring those with
    the longest (most detailed) explanations.
    """
    if not isinstance(biased_opinion_ratings, dict):
        return []
    candidates = []
    for key in OPINION_PRIORITY_KEYS:
        rating = biased_opinion_ratings.get(key)
        if isinstance(rating, dict):
            explanation = (rating.get("explanation") or "").strip()
            if len(explanation) > 40:
                candidates.append((key, explanation))
    # Sort by explanation length (most detailed first)
    candidates.sort(key=lambda c: -len(c[1]))
    return candidates[:max_count]


# Stat values longer than this read as prose (e.g. "750+ riders (2020); waves
# of up to 100"), so they take a full row in the serif face instead of a tile.
STAT_TILE_MAX_CHARS = 16


def _stat(value, label):
    """One Key Stats cell; long values span the row."""
    value = str(value)
    cls = "gg-blog-stat wide" if len(value) > STAT_TILE_MAX_CHARS else "gg-blog-stat"
    return (f'<div class="{cls}"><span class="gg-blog-stat-val">{esc(value)}</span>'
            f'<span class="gg-blog-stat-label">{esc(label)}</span></div>')


def parse_race_date(date_str):
    """Parse date_specific string like '2026: June 6' into a date object."""
    if not date_str:
        return None
    match = re.match(r"(\d{4}).*?(\w+)\s+(\d+)", str(date_str))
    if not match:
        return None
    year, month_name, day = match.groups()
    month_num = MONTH_NUMBERS.get(month_name.lower())
    if not month_num:
        return None
    try:
        return date(int(year), month_num, int(day))
    except ValueError:
        return None


# The hero shows the race date as a clean date plus a short status, never the
# raw date_specific string (which carries notes, later editions and URLs).
_WEEKDAY = r"(?:(?:mon|tues|wednes|thurs|fri|satur|sun)day,?\s+)?"
_MONTH_FIRST_RE = re.compile(
    r"^\s*(\d{4})\s*:\s*" + _WEEKDAY + r"([A-Za-z]+)\.?\s+(\d{1,2})"
    r"(?:\s*[-\u2013]\s*(\d{1,2})|((?:\s*,\s*\d{1,2}\b)+))?",
    re.I,
)
_DAY_FIRST_RE = re.compile(
    r"^\s*" + _WEEKDAY + r"([A-Za-z]+)\.?\s+(\d{1,2})(?:\s*[-\u2013]\s*(\d{1,2}))?,\s*(\d{4})\b",
    re.I,
)
_URL_RE = re.compile(r"(?:https?://|www\.)\S+|\b[\w-]+(?:\.[\w-]+)*\.(?:com|org|net|bike|cc|co|io|es|pt|uk|eu|de|fr|it|nz|au|ca)\b\S*", re.I)


def _strip_urls(text):
    """Drop URLs (and any parenthetical holding one) from a date note."""
    text = re.sub(r"\([^)]*\)", lambda m: "" if _URL_RE.search(m.group(0)) else m.group(0), text)
    text = _URL_RE.sub("", text)
    text = re.sub(r"\(\s*\)", "", text)
    return re.sub(r"\s{2,}", " ", text).strip(" ,;\u2014-")


_MONTH_ABBR = {name[:3]: num for name, num in MONTH_NUMBERS.items()}
_MONTH_ABBR["sept"] = 9


def _month_number(name):
    name = name.lower()
    return MONTH_NUMBERS.get(name) or _MONTH_ABBR.get(name)


def _first_edition(raw):
    """Text up to the first ';' outside parentheses, or the next 'YYYY:'."""
    depth = 0
    for i, ch in enumerate(raw):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(depth - 1, 0)
        elif ch == ";" and depth == 0:
            raw = raw[:i]
            break
    return re.split(r"\.\s+\d{4}\s*:", raw, maxsplit=1)[0].strip()


def _date_status(clause):
    low = clause.lower()
    if "registration open" in low:
        return "Registration open"
    if re.search(r"(?<!un)(?<!not )\bconfirmed\b", low):
        return "Confirmed"
    return ""


def race_date_line(date_str):
    """'October 25, 2026 · Registration open' from a date_specific string.

    Only the first edition named counts (text before the first top-level ';'). If the
    date doesn't parse, the raw first clause is shown with URLs removed.
    """
    display, status, _ = race_date_parts(date_str)
    return " \u00b7 ".join(p for p in (display, status) if p)


def race_date_parts(date_str):
    """(display, status, parsed) behind race_date_line().

    parsed is False when the date didn't parse and display is the raw first
    clause with URLs removed (status is then always "").
    """
    raw = str(date_str or "").strip()
    if not raw:
        return "", "", False
    clause = _first_edition(raw)
    status = _date_status(clause)
    display = ""
    m = _MONTH_FIRST_RE.match(clause)
    if m:
        year, month, day, end, more = m.groups()
    else:
        m = _DAY_FIRST_RE.match(clause)
        if m:
            month, day, end, year = m.groups()
            more = None
    month_num = _month_number(month) if m else None
    if month_num:
        try:
            date(int(year), month_num, int(day))
            if end:
                date(int(year), month_num, int(end))
        except ValueError:
            month_num = None
    if month_num:
        mname = date(2000, month_num, 1).strftime("%B")
        if end:
            display = f"{mname} {int(day)}\u2013{int(end)}, {year}"
        elif more:
            days = [str(int(day))] + re.findall(r"\d{1,2}", more)
            display = f"{mname} {', '.join(days[:-1])} and {days[-1]}, {year}"
        else:
            display = f"{mname} {int(day)}, {year}"
    else:
        display = _strip_urls(clause)
        status = ""  # the fallback text already says what it knows
    return display, status, bool(month_num)


# ── "In short" (spec: ~/specs/gg-editorial-shell-2026-10-08/IN_SHORT_SPEC.md) ──
# Every claim is race data verbatim or a fixed template over race fields. A
# claim is skipped when its data is missing, looks cut off, breaks the voice
# rules or runs past IN_SHORT_MAX_WORDS. Fewer than 2 claims: no "In short".

IN_SHORT_MAX_WORDS = 25
IN_SHORT_MIN_CLAIMS = 2
MIN_ZONE_WORDS = 6  # a suffering-zone sentence shorter than this is filler

# The h2 id of each preview section and the label its "In short" link uses.
SECTION_LABELS = {
    "why-race": "Why Race",
    "the-real-talk": "The Real Talk",
    "course-preview": "Course Preview",
    "key-stats": "Key Stats",
    "training-focus": "Training Focus",
    "history": "History",
    "registration-info": "Registration & Info",
}

# A period after one of these doesn't end a sentence.
_ABBREVIATIONS = {
    "st", "mt", "mr", "mrs", "ms", "dr", "jr", "sr", "vs", "approx", "est",
    "no", "ft", "mi", "km", "e.g", "i.e", "u.s", "u.k", "etc", "ave", "rd",
}
_SENTENCE_END_RE = re.compile(r"[.?!][\"'’”)]*(?=\s|$)")
_BANNED_CLAIM_RE = re.compile(
    r"!|—|\s[–-]\s|…|\.\.\."           # exclamation, dash asides, ellipses
    r"|\bI\b|\b[Ww]e\b|\b[Oo]ur\b|\bus\b|\b[Mm]y\b|\bme\b"  # first person
    r"|\bnot\b[^.;]*\bbut\b|\b(?:isn't|aren't|wasn't)\b[^.;]*\bit'?s\b|,\s+not\b",  # not X, but Y / X, not Y
)
_NUMBERISH_RE = re.compile(r"~?\d[\d,]*(?:\.\d+)?(?:\s*[-–]\s*\d[\d,]*(?:\.\d+)?)?\+?")


def first_sentence(text):
    """The first full sentence of text, or None if it has no terminal punctuation.

    A string with no sentence end looks cut off (truncation guard), so it
    yields None rather than a fragment.
    """
    text = " ".join(str(text or "").split())
    for m in _SENTENCE_END_RE.finditer(text):
        candidate = text[:m.end()]
        word = re.search(r"(\S+?)[.?!][\"'’”)]*$", candidate)
        token = (word.group(1) if word else "").lstrip("(\"'“").lower()
        if m.group(0)[0] == "." and (token in _ABBREVIATIONS or len(token) == 1):
            continue
        return candidate
    return None


def claim_ok(text):
    """True if a plain-text claim fits the voice and length rules."""
    return (bool(text) and len(text.split()) <= IN_SHORT_MAX_WORDS
            and not _BANNED_CLAIM_RE.search(text))


def _number(value):
    """Display a numeric stat ('5,741', '74.5', '4,500–9,116'), or '' if it isn't one."""
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, (int, float)):
        if value <= 0:
            return ""
        return f"{value:,.1f}".rstrip("0").rstrip(".") if value % 1 else f"{int(value):,}"
    text = str(value).strip()
    return text.replace("-", "–") if _NUMBERISH_RE.fullmatch(text) else ""


def surface_breakdown(rd):
    """[(surface, pct)] from course_description.surface_breakdown.overall, largest first."""
    overall = ((rd.get("course_description") or {}).get("surface_breakdown") or {})
    overall = overall.get("overall") if isinstance(overall, dict) else None
    if not isinstance(overall, dict):
        return []
    parts = [(str(k).replace("_", " "), v) for k, v in overall.items()
             if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0]
    return sorted(parts, key=lambda kv: (-kv[1], kv[0]))


def why_race_text(rd):
    """The first paragraph of Why Race: bottom_line, else should_you_race."""
    biased = rd.get("biased_opinion") or {}
    final_verdict = rd.get("final_verdict") or {}
    return biased.get("bottom_line", "") or final_verdict.get("should_you_race", "")


def shown_suffering_zones(rd):
    """The suffering zones Course Preview lists (generic filler is hidden there)."""
    zones = (rd.get("course_description") or {}).get("suffering_zones")
    if isinstance(zones, list) and zones and not is_generic_suffering(zones):
        return zones
    return []


def _verdict_claim(rd):
    rating = rd.get("gravel_god_rating") or {}
    score, tier = rating.get("overall_score"), rating.get("tier")
    if not isinstance(score, (int, float)) or isinstance(score, bool) or tier not in TIER_NAMES:
        return None
    verdict = first_sentence(why_race_text(rd))
    if not verdict:
        return None
    return f"Rated {_number(score) or score}/100, Tier {tier} {TIER_NAMES[tier]}. {verdict}"


def _course_claim(rd):
    vitals = rd.get("vitals") or {}
    distance = _number(vitals.get("distance_mi"))
    if not distance:
        return None
    elevation = _number(vitals.get("elevation_ft"))
    text = f"{distance} miles" + (f" with {elevation} ft of elevation gain" if elevation else "")
    surfaces = surface_breakdown(rd)
    if surfaces:
        surface, pct = surfaces[0]
        text += f", {_number(pct)}% {surface}"
    return text + "."


def _hard_part_claim(rd):
    """(text, section id): the first weakness, else the first shown suffering zone."""
    weaknesses = (rd.get("biased_opinion") or {}).get("weaknesses")
    if isinstance(weaknesses, list) and weaknesses:
        sentence = first_sentence(weaknesses[0]) if isinstance(weaknesses[0], str) else None
        if sentence and claim_ok(sentence):
            return sentence, "the-real-talk"
    for zone in shown_suffering_zones(rd)[:1]:
        if not isinstance(zone, dict):
            continue
        sentence = first_sentence(zone.get("desc"))
        # Short template descs ("First desert sections.") say nothing hard.
        if not sentence or len(sentence.split()) < MIN_ZONE_WORDS:
            continue
        label = " ".join(str(zone.get("label") or "").split())
        mile = _number(zone.get("mile")) if zone.get("mile") != 0 else "0"
        where = f"{label} (mile {mile})" if label and mile else label or (f"Mile {mile}" if mile else "")
        return (f"{where}: {sentence}" if where else sentence), "course-preview"
    return None, None


def _when_claim(rd):
    vitals = rd.get("vitals") or {}
    display, status, parsed = race_date_parts(vitals.get("date_specific", "") or vitals.get("date", ""))
    if not parsed:
        return None
    noun = "Race dates" if ("–" in display or " and " in display) else "Race date"
    text = f"{noun}: {display}"
    if status == "Registration open":
        return text + ". Registration is open."
    if status == "Confirmed":
        return text + " (confirmed)."
    return text + "."


def build_in_short(rd, section_ids):
    """The preview's "In short" claims (editorial_shell.Claim), or None.

    section_ids: the h2 ids of the sections the page renders, in order. A claim
    renders only when the section that backs it is on the page.
    """
    candidates = [(_verdict_claim(rd), "why-race")]
    candidates.append((_course_claim(rd), "key-stats"))
    candidates.append(_hard_part_claim(rd))
    candidates.append((_when_claim(rd), "registration-info"))
    claims = []
    for text, sid in candidates:
        if not text or sid not in section_ids or not claim_ok(text):
            continue
        idx = section_ids.index(sid)
        claims.append(Claim(esc(text), f"#{sid}", f"See {SECTION_LABELS[sid]} · §{idx + 1:02d}", idx))
    return claims if len(claims) >= IN_SHORT_MIN_CLAIMS else None


def load_race(slug):
    """Load a single race JSON."""
    path = RACE_DATA_DIR / f"{slug}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return data.get("race", data)


def load_all_races():
    """Load all race JSONs."""
    races = []
    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            rd = data.get("race", data)
            rd["_slug"] = f.stem
            races.append(rd)
        except (json.JSONDecodeError, KeyError):
            continue
    return races


def find_candidates(min_days=30, max_days=120):
    """Find races with dates in the registration window.

    Returns races whose date is 30-120 days from now,
    sorted by tier (T1 first) then by date proximity.
    """
    today = date.today()
    candidates = []

    for race in load_all_races():
        date_str = race.get("vitals", {}).get("date_specific", "")
        race_date = parse_race_date(date_str)
        if not race_date:
            continue

        days_until = (race_date - today).days
        if min_days <= days_until <= max_days:
            gravel_god = race.get("gravel_god_rating", {})
            candidates.append({
                "slug": race["_slug"],
                "name": race.get("name", race["_slug"]),
                "date": race_date,
                "days_until": days_until,
                "tier": gravel_god.get("tier", 4),
                "score": gravel_god.get("overall_score", 0),
            })

    # Sort: T1 first, then by date proximity
    candidates.sort(key=lambda c: (c["tier"], c["days_until"]))
    return candidates


def generate_preview_html(slug):
    """Generate a preview article HTML for a single race."""
    rd = load_race(slug)
    if not rd:
        print(f"  SKIP  {slug}: JSON not found")
        return None

    name = rd.get("name", slug)
    vitals = rd.get("vitals", {})
    gravel_god = rd.get("gravel_god_rating", {})
    biased = rd.get("biased_opinion", {})
    course_desc = rd.get("course_description", {})
    history = rd.get("history", {})
    logistics = rd.get("logistics", {})
    non_negotiables = rd.get("non_negotiables", [])

    tier = gravel_god.get("tier", 4)
    score = gravel_god.get("overall_score", 0)
    tier_name = TIER_NAMES.get(tier, "Grassroots")
    location = vitals.get("location", "") or vitals.get("location_badge", "")
    date_str = vitals.get("date_specific", "") or vitals.get("date", "")
    distance = vitals.get("distance_mi", "")
    elevation = vitals.get("elevation_ft", "")
    field_size = vitals.get("field_size", "")
    terrain_types = vitals.get("terrain_types", "")
    registration = vitals.get("registration", "")
    official_site = logistics.get("official_site", "")
    if official_site and not str(official_site).startswith("http"):
        official_site = ""

    profile_url = f"{SITE_URL}/race/{slug}/"
    prep_kit_url = f"{SITE_URL}/race/{slug}/prep-kit/"
    og_image_url = f"{SITE_URL}/og/{slug}.jpg"

    # Article date — use race date, not today's date
    race_date_obj = parse_race_date(date_str)
    if race_date_obj:
        # Publish preview ~60 days before the race
        preview_date = race_date_obj - timedelta(days=60)
        # But never future-date (cap at today)
        if preview_date > date.today():
            preview_date = date.today()
    else:
        preview_date = date.today()

    biased_ratings = rd.get("biased_opinion_ratings", {})

    # Build sections
    why_section = ""
    biased_summary = biased.get("summary", "")
    # Prefer bottom_line (more direct) over should_you_race (hedging)
    why_text = why_race_text(rd)
    if why_text or biased_summary:
        why_section = f"""
    <section class="gg-blog-section">
      <h2 id="why-race">Why Race {esc(name)}?</h2>
      {f'<p>{esc(why_text)}</p>' if why_text else ''}
      {f'<p>{esc(biased_summary)}</p>' if biased_summary else ''}
    </section>"""

    # "Real Talk" section — strengths, weaknesses, and top opinion explanations
    real_talk_section = ""
    strengths = biased.get("strengths", [])
    weaknesses = biased.get("weaknesses", [])
    best_opinions = pick_best_opinions(biased_ratings)
    if strengths or weaknesses or best_opinions:
        strengths_html = ""
        if isinstance(strengths, list) and strengths:
            items = "".join(f"<li>{esc(s)}</li>" for s in strengths[:5])
            strengths_html = f'<p><strong>Strengths:</strong></p><ul>{items}</ul>'
        weaknesses_html = ""
        if isinstance(weaknesses, list) and weaknesses:
            items = "".join(f"<li>{esc(w)}</li>" for w in weaknesses[:5])
            weaknesses_html = f'<p><strong>Weaknesses:</strong></p><ul>{items}</ul>'
        opinions_html = ""
        if best_opinions:
            items = "".join(
                f"<li><strong>{esc(key.replace('_', ' ').title())}:</strong> {esc(explanation)}</li>"
                for key, explanation in best_opinions
            )
            opinions_html = f'<p><strong>Our Take:</strong></p><ul>{items}</ul>'
        real_talk_section = f"""
    <section class="gg-blog-section">
      <h2 id="the-real-talk">The Real Talk</h2>
      {strengths_html}
      {weaknesses_html}
      {opinions_html}
    </section>"""

    course_section = ""
    character = course_desc.get("character", "")
    suffering = course_desc.get("suffering_zones", "")
    suffering_html = ""
    # Suppress generic suffering zones (template filler in low-data profiles)
    if shown_suffering_zones(rd):
        items = []
        for z in suffering:
            if isinstance(z, dict):
                label = esc(z.get("label", ""))
                mile = z.get("mile", "")
                desc = esc(z.get("desc", ""))
                prefix = f"Mile {esc(str(mile))}: " if mile is not None and mile != "" else ""
                items.append(f"<li><strong>{prefix}{label}</strong> — {desc}</li>")
            else:
                items.append(f"<li>{esc(str(z))}</li>")
        suffering_html = f'<p><strong>Key challenges:</strong></p><ul>{"".join(items)}</ul>'
    elif suffering and not isinstance(suffering, list):
        suffering_html = f"<p><strong>Key challenges:</strong> {esc(str(suffering))}</p>"
    if character or suffering_html:
        course_section = f"""
    <section class="gg-blog-section">
      <h2 id="course-preview">Course Preview</h2>
      {f'<p>{esc(character)}</p>' if character else ''}
      {suffering_html}
    </section>"""

    stats_items = []
    if distance:
        stats_items.append(_stat(str(distance), "Miles"))
    if elevation:
        if isinstance(elevation, (int, float)):
            elev_display = f"{int(elevation):,}"
        else:
            elev_display = str(elevation)
        stats_items.append(_stat(elev_display, "Ft Elevation"))
    if field_size:
        stats_items.append(_stat(str(field_size), "Field Size"))
    surfaces = surface_breakdown(rd)
    if surfaces:
        stats_items.append(_stat(" · ".join(f"{_number(pct)}% {name}" for name, pct in surfaces), "Surface"))
    if terrain_types:
        terrain_display = " · ".join(str(t) for t in terrain_types) if isinstance(terrain_types, list) else str(terrain_types)
        stats_items.append(_stat(terrain_display, "Terrain"))
    stats_section = ""
    if stats_items:
        stats_section = f"""
    <section class="gg-blog-section">
      <h2 id="key-stats">Key Stats</h2>
      <div class="gg-blog-stats">{''.join(stats_items)}</div>
    </section>"""

    training_section = ""
    if non_negotiables:
        top3 = non_negotiables[:3]
        items = []
        for n in top3:
            if isinstance(n, dict):
                req = esc(n.get("requirement", ""))
                why = esc(n.get("why", ""))
                items.append(f"<li><strong>{req}</strong> — {why}</li>" if why else f"<li><strong>{req}</strong></li>")
            else:
                items.append(f"<li>{esc(str(n))}</li>")
        training_section = f"""
    <section class="gg-blog-section">
      <h2 id="training-focus">Training Focus</h2>
      <p>To be competitive at {esc(name)}, prioritize these non-negotiables:</p>
      <ol>{"".join(items)}</ol>
    </section>"""

    history_section = ""
    origin = history.get("origin_story", "")
    notable = history.get("notable_moments", "")
    notable_html = ""
    if isinstance(notable, list) and notable:
        items = "".join(f"<li>{esc(str(m))}</li>" for m in notable)
        notable_html = f"<p><strong>Notable moments:</strong></p><ul>{items}</ul>"
    elif notable:
        notable_html = f"<p><strong>Notable moments:</strong> {esc(str(notable))}</p>"
    if origin or notable_html:
        history_section = f"""
    <section class="gg-blog-section">
      <h2 id="history">History</h2>
      {f'<p>{esc(origin)}</p>' if origin else ''}
      {notable_html}
    </section>"""

    reg_section = ""
    if registration or official_site:
        reg_section = f"""
    <section class="gg-blog-section">
      <h2 id="registration-info">Registration &amp; Info</h2>
      {f'<p><strong>Registration:</strong> {esc(str(registration))}</p>' if registration else ''}
      {f'<p><a href="{esc(official_site)}">Official Website &rarr;</a></p>' if official_site else ''}
    </section>"""

    # No JSON-LD for preview pages — they are noindexed, and Article schema
    # on noindexed pages sends contradictory signals to Google.

    named_sections = [
        ("why-race", why_section), ("the-real-talk", real_talk_section),
        ("course-preview", course_section), ("key-stats", stats_section),
        ("training-focus", training_section), ("history", history_section),
        ("registration-info", reg_section),
    ]
    sections = [s for _, s in named_sections if s]
    in_short = build_in_short(rd, [sid for sid, s in named_sections if s])

    # Race-specific CTAs: same URLs and copy as before (no data-cta; the
    # plan-intent script still tracks the prep-kit link by its href).
    cta_block = f"""
    <div class="gg-blog-cta">
      <a class="btn" href="{profile_url}">Full Race Profile <span class="chev" aria-hidden="true">&rsaquo;</span></a>
      <a class="btn alt" href="{prep_kit_url}">Free Prep Kit <span class="chev" aria-hidden="true">&rsaquo;</span></a>
    </div>"""

    kicker = " · ".join(
        str(part) for part in (f"Tier {tier} {tier_name}", location) if part
    )
    meta = ArticleMeta(
        slug=slug,
        canonical_url=f"{SITE_URL}/blog/{slug}/",
        title=f"{name} Race Preview — Gravel God",
        description=(
            f"Everything you need to know about {name}: course preview, key stats, "
            f"training tips, and registration info. Tier {tier} {tier_name} rated {score}/100."
        ),
        og_description=f"Tier {tier} {tier_name} gravel race. {location}. Rated {score}/100.",
        headline=f"{name} Race Preview",
        date_published=preview_date,
        kicker=kicker,
        dek=race_date_line(date_str),
        robots="noindex, follow",
        hero_class="gg-blog-hero",
        og_image=OgImage(url=og_image_url, width=1200, height=630),
        track_article_events=False,
        show_read_time=False,
        nav_active=None,
    )
    # The share card (title, tier, location, score) would repeat the hero, so
    # it sits after the first section as a plain inline figure. It keeps the
    # gg-blog-hero-img class the blog validator checks for.
    share_card = (
        f'\n    <div class="gg-article-img-inline">\n'
        f'      <img class="gg-blog-hero-img" src="{esc(og_image_url)}" '
        f'alt="{esc(name)} race preview" width="1200" height="630" loading="lazy">\n'
        f'    </div>'
    )
    if sections:
        sections[0] += share_card
    else:
        sections.append(share_card)

    page_html = render_editorial_page(
        meta,
        "\n".join(sections) + cta_block,
        in_short=in_short,
        ladder=False,
        contents=len(sections) >= 3,
        extra_css=PREVIEW_CSS,
        extra_body_end=get_plan_intent_tracking_script(),
    )
    return _add_score_tile(page_html, _score_tile(score, tier, tier_name))


def _score_tile(score, tier, tier_name):
    """The rating as a hero measurement tile: the number, then /100 and the tier."""
    return (
        f'<div class="gg-blog-score"><span class="gg-blog-score-val">{esc(str(score))}</span>'
        f'<span class="gg-blog-score-of">/100</span>'
        f'<span class="gg-blog-stat-label">Tier {esc(str(tier))} {esc(tier_name)}</span></div>'
    )


# The shell's hero takes no extra markup, so the score tile goes in right
# before its byline. Fail loudly if that markup ever changes.
_BYLINE_ANCHOR = '<p class="by">'


def _add_score_tile(page_html, tile_html):
    if page_html.count(_BYLINE_ANCHOR) != 1:
        raise RuntimeError(f"editorial shell hero markup changed: {_BYLINE_ANCHOR!r} not found once")
    return page_html.replace(_BYLINE_ANCHOR, tile_html + "\n      " + _BYLINE_ANCHOR, 1)


# Preview-only blocks on top of the shell: the stat row and the race CTAs.
PREVIEW_CSS = """
.article .gg-blog-section{overflow-wrap:break-word}
.article .gg-blog-section a{color:var(--teal-ink);text-decoration:underline;text-underline-offset:3px;text-decoration-thickness:2px}
.gg-blog-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:6px;margin:0 0 1.05em}
.gg-blog-stat{background:var(--sand);padding:16px 18px;min-width:0}
.gg-blog-stat-val{display:block;font:700 24px/1.2 var(--mono);color:var(--ink);overflow-wrap:anywhere}
.gg-blog-stat-label{display:block;font:700 12px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--ink3);margin-top:6px}
.gg-blog-stat.wide{grid-column:1/-1}
.gg-blog-score{display:inline-grid;grid-template-columns:auto 1fr;align-items:baseline;column-gap:8px;background:var(--sand);padding:14px 18px 16px;margin:4px 0 16px}
.gg-blog-score-val{font:700 48px/1 var(--mono);color:var(--ink)}
.gg-blog-score-of{font:700 13px var(--mono);letter-spacing:.1em;color:var(--ink3)}
.gg-blog-score .gg-blog-stat-label{grid-column:1/-1;margin-top:8px}
.gg-blog-stat.wide .gg-blog-stat-val{font:400 19px/1.45 var(--serif)}
.gg-blog-cta{display:flex;flex-wrap:wrap;gap:10px;margin:56px 0 0}
.gg-blog-cta .btn.alt{background:var(--ink)}
.gg-blog-cta .btn.alt:hover{background:#000}
@media (max-width:640px){
  .gg-blog-stat-val{font-size:21px}
  .gg-blog-stat.wide .gg-blog-stat-val{font-size:17px}
}
"""


def main():
    parser = argparse.ArgumentParser(description="Generate race preview blog articles")
    parser.add_argument("--slug", help="Generate preview for a single race slug")
    parser.add_argument("--all", action="store_true", help="Generate for all upcoming races")
    parser.add_argument("--dry-run", action="store_true", help="List candidates without generating")
    parser.add_argument("--min-days", type=int, default=30, help="Minimum days until race (default: 30)")
    parser.add_argument("--max-days", type=int, default=120, help="Maximum days until race (default: 120)")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)

    if args.dry_run:
        candidates = find_candidates(args.min_days, args.max_days)
        if not candidates:
            print("No races found in the registration window "
                  f"({args.min_days}-{args.max_days} days from now).")
            return
        print(f"{'SLUG':<40} {'TIER':>4} {'SCORE':>5} {'DATE':>12} {'DAYS':>5}")
        print("-" * 70)
        for c in candidates:
            print(f"{c['slug']:<40} T{c['tier']:>3} {c['score']:>5} "
                  f"{c['date'].isoformat():>12} {c['days_until']:>5}")
        print(f"\n{len(candidates)} candidates found.")
        return

    if args.slug:
        html_content = generate_preview_html(args.slug)
        if html_content:
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"{args.slug}.html"
            out_file.write_text(html_content)
            print(f"  OK    {out_file}")
        return

    if args.all:
        candidates = find_candidates(args.min_days, args.max_days)
        if not candidates:
            print("No races found in the registration window.")
            return

        out_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for c in candidates:
            html_content = generate_preview_html(c["slug"])
            if html_content:
                out_file = out_dir / f"{c['slug']}.html"
                out_file.write_text(html_content)
                print(f"  OK    T{c['tier']} {c['slug']}")
                count += 1

        print(f"\nGenerated {count} preview articles in {out_dir}/")
        return

    parser.error("Provide --slug NAME, --all, or --dry-run")


if __name__ == "__main__":
    main()
