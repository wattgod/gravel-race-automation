#!/usr/bin/env python3
"""
Generate Race Prep Kit pages — personalized 12-week timeline + race-day checklists.

Reads structured content from guide/gravel-guide-content.json and race profiles
from race-data/*.json to produce standalone, print-friendly HTML pages.

Two personalization tiers:
  - Full (235 races): training_config + non_negotiables → milestones injected
  - Generic (93 races): guide content + race context callout

Usage:
    python wordpress/generate_prep_kit.py unbound-200
    python wordpress/generate_prep_kit.py --all
    python wordpress/generate_prep_kit.py --all --output-dir /tmp/pk
"""

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Import shared constants from the race page generator
sys.path.insert(0, str(Path(__file__).parent))
from generate_neo_brutalist import (
    SITE_BASE_URL,
    SUBSTACK_URL,
    COACHING_URL,
    TRAINING_PLANS_URL,
    normalize_race_data,
    find_data_file,
    load_race_data,
)
from generate_neo_brutalist import esc  # HTML escape helper

from brand_tokens import (
    GA_MEASUREMENT_ID,
    get_font_face_css,
    get_preload_hints,
    get_tokens_css,
)

# Disable glossary tooltips in guide renderers (we don't need them here)
import generate_guide
generate_guide._GLOSSARY = None
from generate_guide import (
    render_timeline,
    render_accordion,
    render_process_list,
    render_callout,
    _md_inline,
)

# ── Constants ──────────────────────────────────────────────────

GUIDE_DIR = Path(__file__).parent.parent / "guide"
CONTENT_JSON = GUIDE_DIR / "gravel-guide-content.json"
OUTPUT_DIR = Path(__file__).parent / "output" / "prep-kit"
CURRENT_YEAR = str(datetime.now().year)

# Guide section IDs we extract content from
GUIDE_SECTION_IDS = [
    "ch3-phases",       # 12-week training timeline
    "ch5-race-day",     # Race-day nutrition
    "ch5-gut-training", # Gut training timeline
    "ch6-decision-tree",# In-race decision tree
    "ch7-taper",        # Race week countdown
    "ch7-equipment",    # Equipment checklist
    "ch7-morning",      # Race morning protocol
    "ch8-immediate",    # Post-race recovery
]

# Phase boundaries for milestone bucketing
PHASE_RANGES = {
    "base":  (1, 4),
    "build": (5, 10),
    "taper": (11, 12),
}


# ── Data Loading ──────────────────────────────────────────────


def load_guide_sections() -> dict:
    """Extract the 8 target sections from guide JSON by ID.

    Returns dict mapping section ID → section dict (with 'blocks' list).
    """
    content = json.loads(CONTENT_JSON.read_text(encoding="utf-8"))
    sections = {}
    for chapter in content.get("chapters", []):
        for section in chapter.get("sections", []):
            if section.get("id") in GUIDE_SECTION_IDS:
                sections[section["id"]] = section
    return sections


def load_raw_training_data(filepath: Path) -> dict:
    """Load raw race JSON and extract training-specific fields.

    Returns dict with keys: training_config, non_negotiables, guide_variables,
    race_specific, plus the full raw data under 'raw'.
    """
    data = json.loads(filepath.read_text(encoding="utf-8"))
    race = data.get("race", data)
    return {
        "training_config": race.get("training_config"),
        "non_negotiables": race.get("non_negotiables"),
        "guide_variables": race.get("guide_variables"),
        "race_specific": race.get("race_specific"),
        "climate": race.get("climate", {}),
        "course_description": race.get("course_description", {}),
        "vitals": race.get("vitals", {}),
    }


def has_full_training_data(raw: dict) -> bool:
    """True if race has training_config AND non_negotiables for full personalization."""
    tc = raw.get("training_config")
    nn = raw.get("non_negotiables")
    return bool(tc) and bool(nn) and len(nn) > 0


# ── Personalization ───────────────────────────────────────────


def parse_by_when(text: str) -> Optional[int]:
    """Extract first week number from by_when text like 'Week 6' or 'Week 8-10'.

    Returns integer week number or None if unparseable.
    """
    if not text:
        return None
    m = re.search(r'[Ww]eek\s*(\d+)', text)
    return int(m.group(1)) if m else None


def week_to_phase(week: int) -> str:
    """Map a week number to its training phase name."""
    for phase, (lo, hi) in PHASE_RANGES.items():
        if lo <= week <= hi:
            return phase
    return "build"  # Default to build if out of range


def build_phase_extras(workout_mods: dict) -> dict:
    """Build workout mod chip HTML snippets bucketed by phase.

    Milestones are NOT included here — they appear in the dedicated
    Non-Negotiables section (Section 02) to avoid repetition.

    Returns dict mapping phase name → HTML string to inject after timeline content.
    """
    phase_mods = {"base": [], "build": [], "taper": []}
    for mod_name, mod_cfg in (workout_mods or {}).items():
        if not isinstance(mod_cfg, dict) or not mod_cfg.get("enabled"):
            continue
        week_str = mod_cfg.get("week", "")
        week = parse_by_when(f"Week {week_str}") if isinstance(week_str, (int, float)) else parse_by_when(str(week_str))
        if week:
            phase = week_to_phase(week)
        else:
            phase = "build"
        label = mod_name.replace("_", " ").title()
        phase_mods[phase].append(label)

    result = {}
    for phase in ("base", "build", "taper"):
        parts = []
        for mod_label in phase_mods.get(phase, []):
            parts.append(
                f'<span class="gg-pk-workout-mod">{esc(mod_label)}</span>'
            )
        result[phase] = "\n".join(parts)
    return result


def render_personalized_timeline(block: dict, phase_extras: dict) -> str:
    """Render timeline with injected milestone/mod HTML after each phase step.

    Like render_timeline() but appends extra HTML per phase (base/build/taper)
    after the content div, avoiding the esc() that render_timeline applies.
    """
    title = esc(block.get("title", ""))
    steps = block["steps"]
    phase_names = ["base", "build", "taper"]
    steps_html = []

    for i, step in enumerate(steps):
        label = esc(step["label"])
        content = _md_inline(esc(step["content"]))
        paras = [f'<p>{p.strip()}</p>' for p in content.split('\n') if p.strip()]

        phase = phase_names[i] if i < len(phase_names) else "taper"
        extra = phase_extras.get(phase, "")

        steps_html.append(f'''<div class="gg-guide-timeline-step">
        <div class="gg-guide-timeline-marker">{i + 1}</div>
        <div class="gg-guide-timeline-content">
          <h4 class="gg-guide-timeline-label">{label}</h4>
          {''.join(paras)}
          {extra}
        </div>
      </div>''')

    title_html = f'<h3 class="gg-guide-timeline-title">{title}</h3>' if title else ''
    return f'''<div class="gg-guide-timeline">
      {title_html}
      {''.join(steps_html)}
    </div>'''


def build_race_context_callout(raw: dict, rd: dict) -> str:
    """Build context callout box for generic-tier races (no training_config).

    Pulls distance, terrain, climate, signature challenge from available data.
    """
    parts = []

    distance = rd["vitals"].get("distance", "")
    if distance and distance != "--":
        parts.append(f"<strong>Distance:</strong> {esc(distance)}")

    elevation = rd["vitals"].get("elevation", "")
    if elevation and elevation != "--":
        parts.append(f"<strong>Elevation:</strong> {esc(elevation)}")

    location = rd["vitals"].get("location", "")
    if location and location != "--":
        parts.append(f"<strong>Location:</strong> {esc(location)}")

    climate = raw.get("climate", {})
    if isinstance(climate, dict):
        conditions = climate.get("race_day_conditions", "")
        if conditions:
            parts.append(f"<strong>Conditions:</strong> {esc(conditions)}")

    course = raw.get("course_description", {})
    if isinstance(course, dict):
        sig = course.get("signature_challenge", "")
        if sig:
            parts.append(f"<strong>Signature Challenge:</strong> {esc(sig)}")

    if not parts:
        return ""

    items = "".join(f"<p>{p}</p>" for p in parts)
    return f'''<div class="gg-pk-context-box">
      <div class="gg-pk-context-label">RACE CONTEXT: {esc(rd["name"].upper())}</div>
      {items}
    </div>'''


# ── Improvement Helpers ───────────────────────────────────────


def compute_wake_time(start_time_str: str) -> Optional[str]:
    """Parse start time and subtract 3 hours for wake-up alarm.

    Handles formats like 'Saturday 6:00 AM', 'Friday 1:00 PM',
    and multi-line strings (takes first time found).
    Returns formatted time string or None.
    """
    if not start_time_str:
        return None
    m = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)', start_time_str, re.IGNORECASE)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2))
    ampm = m.group(3).upper()
    # Convert to 24h
    if ampm == "PM" and hour != 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    # Subtract 3 hours
    hour = (hour - 3) % 24
    # Convert back to 12h
    if hour == 0:
        return f"12:{minute:02d} AM"
    elif hour < 12:
        return f"{hour}:{minute:02d} AM"
    elif hour == 12:
        return f"12:{minute:02d} PM"
    else:
        return f"{hour - 12}:{minute:02d} PM"


def compute_fueling_estimate(distance_mi) -> Optional[dict]:
    """Estimate fueling needs based on race distance.

    Returns dict with hours, carbs range, gel equivalents, or None.
    """
    if not distance_mi:
        return None
    try:
        distance_mi = int(distance_mi)
    except (ValueError, TypeError):
        return None
    if distance_mi < 20:
        return None
    # Conservative average speeds for gravel (including stops)
    if distance_mi <= 50:
        avg_mph = 14
    elif distance_mi <= 100:
        avg_mph = 12
    elif distance_mi <= 150:
        avg_mph = 11
    else:
        avg_mph = 10
    hours = distance_mi / avg_mph
    carbs_low = int(hours * 60)
    carbs_high = int(hours * 90)
    gels_low = carbs_low // 25
    gels_high = carbs_high // 25
    return {
        "hours": round(hours, 1),
        "avg_mph": avg_mph,
        "carbs_low": carbs_low,
        "carbs_high": carbs_high,
        "gels_low": gels_low,
        "gels_high": gels_high,
    }


def build_climate_gear_callout(climate_data: dict) -> str:
    """Build climate-adapted gear recommendations based on race conditions."""
    if not climate_data or not isinstance(climate_data, dict):
        return ""
    desc = (climate_data.get("description", "") or "").lower()
    challenges = climate_data.get("challenges", [])
    challenge_text = " ".join(c.lower() for c in challenges if isinstance(c, str))
    combined = desc + " " + challenge_text

    recs = []
    if any(kw in combined for kw in ["heat", "hot", "90", "95", "100", "sun"]):
        recs.extend([
            "Sun sleeves or arm coolers",
            "Extra water bottles or hydration vest",
            "Electrolyte supplements (extra sodium)",
            "Light-colored kit",
        ])
    if any(kw in combined for kw in ["cold", "freez", "40°", "30°", "snow", "ice"]):
        recs.extend([
            "Knee warmers or leg warmers",
            "Wind vest or thermal layer",
            "Full-finger gloves",
            "Toe covers",
        ])
    if any(kw in combined for kw in ["rain", "wet", "mud"]):
        recs.extend([
            "Lightweight rain jacket (packable)",
            "Mudguards or frame protection",
            "Extra chain lube",
            "Clear or yellow lens glasses",
        ])
    if any(kw in combined for kw in ["wind", "exposed"]):
        recs.extend(["Wind vest", "Aero positioning practice"])
    if not recs:
        return ""

    # Deduplicate — also skip if a more detailed version already exists
    # (e.g. "Wind vest" skipped when "Wind vest or thermal layer" is present)
    seen = []
    unique_recs = []
    for r in recs:
        if r not in seen and not any(r in existing for existing in seen):
            seen.append(r)
            unique_recs.append(r)

    items = "".join(f"<li>{esc(r)}</li>" for r in unique_recs)
    primary = esc(climate_data.get("primary", "Race-day conditions"))
    return f'''<div class="gg-guide-callout gg-guide-callout--highlight">
        <p><strong>Climate Gear ({primary}):</strong></p>
        <ul>{items}</ul>
      </div>'''


def build_terrain_emphasis_callout(rd: dict) -> str:
    """Build terrain-adapted training emphasis based on technicality and terrain."""
    rating = rd.get("rating", {})
    tech = rating.get("technicality", 0) or 0
    terrain_types = rd["vitals"].get("terrain_types", [])
    elevation = rd["vitals"].get("elevation", "")
    distance_mi = rd["vitals"].get("distance_mi", 0) or 0

    tips = []
    if tech >= 4:
        tips.append(
            "Add 1 MTB skills session per week during Build phase (weeks 5-10)"
            " \u2014 focus on line choice, loose surface cornering, and"
            " dismount/remount"
        )
    elif tech >= 3:
        tips.append(
            "Include off-road skills work every 2 weeks \u2014 practice loose"
            " gravel descending and rough surface handling"
        )

    # Check for elevation-heavy courses
    elev_ft = 0
    if elevation:
        m = re.search(r'([\d,]+)\s*ft', elevation)
        if m:
            elev_ft = int(m.group(1).replace(',', ''))
    if distance_mi > 0 and elev_ft > 0:
        ft_per_mile = elev_ft / distance_mi
        if ft_per_mile > 80:
            tips.append(
                f"Include 2 extended climbing intervals per week (20-30 min at"
                f" threshold) \u2014 this course averages {ft_per_mile:.0f}"
                f" ft/mile of climbing"
            )

    terrain_str = ", ".join(terrain_types[:3]) if terrain_types else ""
    if terrain_str and any(
        kw in terrain_str.lower() for kw in ["sand", "mud", "clay"]
    ):
        tips.append(
            f"Train on similar surfaces ({terrain_str}) at least once per week"
            f" to build specific handling confidence"
        )

    if not tips:
        return ""

    items = "".join(f"<li>{esc(t)}</li>" for t in tips)
    return f'''<div class="gg-guide-callout gg-guide-callout--highlight">
        <p><strong>Race-Specific Training Focus:</strong></p>
        <ul>{items}</ul>
      </div>'''


# ── Section Builders ──────────────────────────────────────────


def build_pk_header(rd: dict, raw: dict) -> str:
    """Build header with race name and vitals ribbon."""
    name = esc(rd["name"])
    vitals = rd["vitals"]

    stats = []
    if vitals.get("distance") and vitals["distance"] != "--":
        stats.append(f'<span class="gg-pk-stat"><strong>{esc(vitals["distance"])}</strong></span>')
    if vitals.get("elevation") and vitals["elevation"] != "--":
        stats.append(f'<span class="gg-pk-stat"><strong>{esc(vitals["elevation"])}</strong></span>')
    if vitals.get("date") and vitals["date"] != "--":
        stats.append(f'<span class="gg-pk-stat">{esc(vitals["date"])}</span>')
    if vitals.get("location") and vitals["location"] != "--":
        stats.append(f'<span class="gg-pk-stat">{esc(vitals["location"])}</span>')

    ribbon = f'<div class="gg-pk-vitals-ribbon">{" ".join(stats)}</div>' if stats else ""

    is_full = has_full_training_data(raw)
    tier_label = "PERSONALIZED" if is_full else "GUIDE"

    return f'''<header class="gg-pk-header">
    <div class="gg-pk-header-badge">{tier_label} PREP KIT</div>
    <h1 class="gg-pk-header-title">{name}</h1>
    <p class="gg-pk-header-subtitle">12-Week Training Timeline &bull; Race-Day Checklists &bull; Packing List</p>
    {ribbon}
  </header>'''


def build_pk_training_timeline(guide_sections: dict, raw: dict, rd: dict) -> str:
    """Build Section 1: 12-Week Training Timeline."""
    section = guide_sections.get("ch3-phases")
    if not section:
        return ""

    # Find the timeline block
    timeline_block = None
    for block in section.get("blocks", []):
        if block.get("type") == "timeline":
            timeline_block = block
            break

    if not timeline_block:
        return ""

    if has_full_training_data(raw):
        # Full personalization: inject workout mod chips after each phase
        # (milestones are shown in the dedicated Non-Negotiables section)
        mods = (raw.get("training_config") or {}).get("workout_modifications", {})
        extras = build_phase_extras(mods)
        timeline_html = render_personalized_timeline(timeline_block, extras)
    else:
        # Generic: render standard timeline + race context callout
        timeline_html = render_timeline(timeline_block)
        context = build_race_context_callout(raw, rd)
        if context:
            timeline_html = context + timeline_html

    # Terrain-adapted training emphasis (both tiers)
    terrain_callout = build_terrain_emphasis_callout(rd)

    return f'''<section class="gg-pk-section">
    <div class="gg-pk-section-header">
      <span class="gg-pk-section-num">01</span>
      <h2>12-Week Training Timeline</h2>
    </div>
    {terrain_callout}
    {timeline_html}
  </section>'''


def build_pk_non_negotiables(raw: dict) -> str:
    """Build Section 2: Race-Specific Non-Negotiables. Empty for generic races."""
    if not has_full_training_data(raw):
        return ""

    nn_list = raw.get("non_negotiables", [])
    if not nn_list:
        return ""

    cards = []
    for nn in nn_list:
        req = esc(nn.get("requirement", ""))
        by_when = esc(nn.get("by_when", ""))
        why = esc(nn.get("why", ""))
        cards.append(f'''<div class="gg-pk-nn-card">
        <div class="gg-pk-nn-req">{req}</div>
        <span class="gg-pk-nn-badge">{by_when}</span>
        <p class="gg-pk-nn-why">{why}</p>
      </div>''')

    return f'''<section class="gg-pk-section">
    <div class="gg-pk-section-header">
      <span class="gg-pk-section-num">02</span>
      <h2>Race-Specific Non-Negotiables</h2>
    </div>
    <div class="gg-pk-nn-grid">
      {"".join(cards)}
    </div>
  </section>'''


def build_pk_race_week(guide_sections: dict, raw: dict) -> str:
    """Build Section 3: Race Week Countdown (7-day taper)."""
    section = guide_sections.get("ch7-taper")
    if not section:
        return ""

    timeline_block = None
    for block in section.get("blocks", []):
        if block.get("type") == "timeline":
            timeline_block = block
            break

    if not timeline_block:
        return ""

    # Add weather callout if available
    weather_html = ""
    gv = raw.get("guide_variables", {})
    if isinstance(gv, dict):
        weather = gv.get("race_weather", "")
        if weather:
            weather_html = f'''<div class="gg-guide-callout gg-guide-callout--highlight">
        <p><strong>Expected Conditions:</strong> {esc(weather)}</p>
      </div>'''

    return f'''<section class="gg-pk-section">
    <div class="gg-pk-section-header">
      <span class="gg-pk-section-num">03</span>
      <h2>Race Week Countdown</h2>
    </div>
    {weather_html}
    {render_timeline(timeline_block)}
  </section>'''


def build_pk_equipment(guide_sections: dict, raw: dict, rd: dict) -> str:
    """Build Section 4: Equipment & Packing Checklist."""
    section = guide_sections.get("ch7-equipment")
    if not section:
        return ""

    accordion_block = None
    for block in section.get("blocks", []):
        if block.get("type") == "accordion":
            accordion_block = block
            break

    if not accordion_block:
        return ""

    # Check for race-specific tire recommendations (Unbound has mechanicals)
    tire_html = ""
    rs = raw.get("race_specific")
    if isinstance(rs, dict):
        mechs = rs.get("mechanicals", {})
        if isinstance(mechs, dict):
            tires = mechs.get("recommended_tires", [])
            if tires:
                tire_items = "".join(f"<li>{esc(t)}</li>" for t in tires)
                tire_html = f'''<div class="gg-guide-callout gg-guide-callout--highlight">
        <p><strong>Recommended Tires:</strong></p>
        <ul>{tire_items}</ul>
      </div>'''

    # Climate-adapted gear recommendations
    climate_html = build_climate_gear_callout(rd.get("climate_data", {}))

    return f'''<section class="gg-pk-section">
    <div class="gg-pk-section-header">
      <span class="gg-pk-section-num">04</span>
      <h2>Equipment &amp; Packing Checklist</h2>
    </div>
    {tire_html}
    {climate_html}
    {render_accordion(accordion_block)}
  </section>'''


def build_pk_race_morning(guide_sections: dict, rd: dict) -> str:
    """Build Section 5: Race Morning Protocol."""
    section = guide_sections.get("ch7-morning")
    if not section:
        return ""

    timeline_block = None
    for block in section.get("blocks", []):
        if block.get("type") == "timeline":
            timeline_block = block
            break

    if not timeline_block:
        return ""

    # Add start time + computed wake-up time callout
    start_html = ""
    start_time = rd["vitals"].get("start_time", "")
    if start_time:
        wake = compute_wake_time(start_time)
        wake_line = f' Set your alarm for <strong>{esc(wake)}</strong>.' if wake else ""
        start_html = f'''<div class="gg-guide-callout gg-guide-callout--highlight">
        <p><strong>{esc(rd["name"])} Start Time:</strong> {esc(start_time)}.{wake_line}</p>
      </div>'''

    return f'''<section class="gg-pk-section">
    <div class="gg-pk-section-header">
      <span class="gg-pk-section-num">05</span>
      <h2>Race Morning Protocol</h2>
    </div>
    {start_html}
    {render_timeline(timeline_block)}
  </section>'''


def build_pk_fueling(guide_sections: dict, raw: dict, rd: dict) -> str:
    """Build Section 6: Race-Day Fueling (race-day nutrition + gut training)."""
    parts = []

    # Distance-adjusted fueling estimate
    distance_mi = rd["vitals"].get("distance_mi", 0)
    estimate = compute_fueling_estimate(distance_mi)
    if estimate:
        parts.append(
            f'<div class="gg-guide-callout gg-guide-callout--highlight">'
            f'<p><strong>Your Fueling Math ({distance_mi} miles):</strong> '
            f'At ~{estimate["avg_mph"]}mph, expect ~{estimate["hours"]} hours'
            f' on course. At 60-90g carbs/hour, you need '
            f'<strong>{estimate["carbs_low"]}-{estimate["carbs_high"]}g total'
            f' carbs</strong> ({estimate["gels_low"]}-{estimate["gels_high"]}'
            f' gels equivalent).</p>'
            f'</div>'
        )

    # Aid station info
    aid_info = rd["vitals"].get("aid_stations", "")
    if aid_info and aid_info != "--":
        parts.append(
            f'<div class="gg-guide-callout gg-guide-callout--highlight">'
            f'<p><strong>Aid Stations:</strong> {esc(aid_info)}</p>'
            f'</div>'
        )

    # Race-day nutrition timeline
    rd_section = guide_sections.get("ch5-race-day")
    if rd_section:
        for block in rd_section.get("blocks", []):
            if block.get("type") == "timeline":
                parts.append(render_timeline(block))
                break

    # Aggressive fueling callout if enabled
    tc = raw.get("training_config")
    if isinstance(tc, dict):
        mods = tc.get("workout_modifications", {})
        af = mods.get("aggressive_fueling", {})
        if isinstance(af, dict) and af.get("enabled"):
            settings = af.get("settings", {})
            target = settings.get("target_carbs_per_hour", "")
            if target:
                parts.append(
                    f'<div class="gg-guide-callout gg-guide-callout--highlight">'
                    f'<p><strong>Target:</strong> {esc(target)}g carbs/hour during race</p>'
                    f'</div>'
                )

    # Gut training timeline
    gt_section = guide_sections.get("ch5-gut-training")
    if gt_section:
        for block in gt_section.get("blocks", []):
            if block.get("type") == "timeline":
                parts.append(f'<h3 class="gg-pk-subsection-title">Gut Training Protocol</h3>')
                parts.append(render_timeline(block))
                break

    if not parts:
        return ""

    return f'''<section class="gg-pk-section">
    <div class="gg-pk-section-header">
      <span class="gg-pk-section-num">06</span>
      <h2>Race-Day Fueling</h2>
    </div>
    {"".join(parts)}
  </section>'''


def build_pk_decision_tree(guide_sections: dict, rd: dict) -> str:
    """Build Section 7: In-Race Decision Tree."""
    section = guide_sections.get("ch6-decision-tree")
    if not section:
        return ""

    accordion_block = None
    for block in section.get("blocks", []):
        if block.get("type") == "accordion":
            accordion_block = block
            break

    if not accordion_block:
        return ""

    # Add suffering zones callout if available
    zones_html = ""
    suffering = rd["course"].get("suffering_zones", [])
    if suffering:
        zone_parts = []
        for z in suffering[:5]:
            if isinstance(z, dict):
                label = z.get("label", "")
                desc = z.get("desc", "")
                mile = z.get("mile")
                prefix = f"Mile {mile}: " if mile else ""
                suffix = f" — {esc(desc)}" if desc else ""
                zone_parts.append(f"<li><strong>{esc(prefix)}{esc(label)}</strong>{suffix}</li>")
            else:
                zone_parts.append(f"<li>{esc(z)}</li>")
        zone_items = "".join(zone_parts)
        zones_html = f'''<div class="gg-guide-callout gg-guide-callout--highlight">
        <p><strong>Known Suffering Zones:</strong></p>
        <ul>{zone_items}</ul>
      </div>'''

    return f'''<section class="gg-pk-section">
    <div class="gg-pk-section-header">
      <span class="gg-pk-section-num">07</span>
      <h2>In-Race Decision Tree</h2>
    </div>
    {zones_html}
    {render_accordion(accordion_block)}
  </section>'''


def build_pk_recovery(guide_sections: dict) -> str:
    """Build Section 8: Post-Race Recovery."""
    section = guide_sections.get("ch8-immediate")
    if not section:
        return ""

    process_block = None
    for block in section.get("blocks", []):
        if block.get("type") == "process_list":
            process_block = block
            break

    if not process_block:
        return ""

    return f'''<section class="gg-pk-section">
    <div class="gg-pk-section-header">
      <span class="gg-pk-section-num">08</span>
      <h2>Post-Race Recovery</h2>
    </div>
    {render_process_list(process_block)}
  </section>'''


def build_pk_footer_cta(rd: dict) -> str:
    """Build footer CTA linking to training plans and newsletter."""
    name = esc(rd["name"])
    slug = esc(rd["slug"])
    return f'''<footer class="gg-pk-footer">
    <div class="gg-pk-footer-inner">
      <h3>Ready to Race {name}?</h3>
      <p>This free prep kit covers the essentials. For a fully personalized plan built
         specifically for {name} — structured workouts, nutrition protocols, and race-day
         strategy — get a custom training plan.</p>
      <div class="gg-pk-footer-buttons">
        <a href="{esc(TRAINING_PLANS_URL)}" class="gg-pk-btn gg-pk-btn--primary">BUILD MY PLAN &mdash; $15/WK</a>
        <a href="{esc(COACHING_URL)}" class="gg-pk-btn gg-pk-btn--secondary" target="_blank" rel="noopener">1:1 COACHING</a>
      </div>
      <p class="gg-pk-footer-back">
        <a href="/race/{slug}/">Back to {name} Race Profile</a>
      </p>
    </div>
  </footer>'''


# ── CSS ───────────────────────────────────────────────────────


def build_prep_kit_css() -> str:
    """Build complete CSS for prep kit pages."""
    return """/* ── Prep Kit Layout ── */
.gg-pk-page{max-width:800px;margin:0 auto;padding:24px 20px;background:var(--gg-color-warm-paper);color:var(--gg-color-near-black);font-family:var(--gg-font-editorial)}

/* ── Header ── */
.gg-pk-header{text-align:center;padding:32px 0 24px;border-bottom:3px solid var(--gg-color-near-black);margin-bottom:32px}
.gg-pk-header-badge{display:inline-block;font-family:var(--gg-font-data);font-size:11px;font-weight:700;letter-spacing:3px;text-transform:uppercase;background:var(--gg-color-near-black);color:var(--gg-color-warm-paper);padding:4px 12px;margin-bottom:12px}
.gg-pk-header-title{font-family:var(--gg-font-data);font-size:32px;font-weight:700;text-transform:uppercase;letter-spacing:2px;margin:0 0 8px;color:var(--gg-color-near-black)}
.gg-pk-header-subtitle{font-family:var(--gg-font-data);font-size:13px;color:var(--gg-color-secondary-brown);margin:0 0 16px;letter-spacing:1px}
.gg-pk-vitals-ribbon{display:flex;flex-wrap:wrap;justify-content:center;gap:16px;padding-top:16px;border-top:2px solid var(--gg-color-tan)}
.gg-pk-stat{font-family:var(--gg-font-data);font-size:13px;color:var(--gg-color-primary-brown)}

/* ── Sections ── */
.gg-pk-section{margin-bottom:40px;page-break-inside:avoid}
.gg-pk-section-header{display:flex;align-items:baseline;gap:12px;border-bottom:3px solid var(--gg-color-near-black);padding-bottom:8px;margin-bottom:20px}
.gg-pk-section-num{font-family:var(--gg-font-data);font-size:14px;font-weight:700;color:var(--gg-color-teal);letter-spacing:1px}
.gg-pk-section-header h2{font-family:var(--gg-font-data);font-size:18px;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:0;color:var(--gg-color-near-black)}
.gg-pk-subsection-title{font-family:var(--gg-font-data);font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:2px;margin:24px 0 12px;color:var(--gg-color-primary-brown)}

/* ── Non-Negotiable Cards ── */
.gg-pk-nn-grid{display:grid;gap:16px}
.gg-pk-nn-card{border:2px solid var(--gg-color-near-black);padding:16px;background:var(--gg-color-white)}
.gg-pk-nn-req{font-family:var(--gg-font-data);font-size:14px;font-weight:700;color:var(--gg-color-near-black);margin-bottom:8px}
.gg-pk-nn-badge{display:inline-block;font-family:var(--gg-font-data);font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;background:var(--gg-color-teal);color:var(--gg-color-white);padding:2px 8px;margin-bottom:8px}
.gg-pk-nn-why{font-size:13px;line-height:1.6;color:var(--gg-color-primary-brown);margin:0}

/* ── Milestone + Workout Mod Chips ── */
.gg-pk-milestone{border-left:4px solid var(--gg-color-teal);padding:8px 12px;margin-top:12px;background:rgba(23,128,121,0.06);font-family:var(--gg-font-data);font-size:12px;color:var(--gg-color-near-black)}
.gg-pk-milestone-badge{display:inline-block;background:var(--gg-color-teal);color:var(--gg-color-white);font-size:10px;font-weight:700;padding:2px 6px;margin-right:8px;letter-spacing:1px;text-transform:uppercase}
.gg-pk-workout-mod{display:inline-block;font-family:var(--gg-font-data);font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;background:var(--gg-color-gold);color:var(--gg-color-white);padding:3px 8px;margin:8px 6px 0 0}

/* ── Context Box (generic races) ── */
.gg-pk-context-box{border:2px solid var(--gg-color-near-black);padding:16px 20px;margin-bottom:20px;background:var(--gg-color-white)}
.gg-pk-context-label{font-family:var(--gg-font-data);font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--gg-color-teal);margin-bottom:8px}
.gg-pk-context-box p{font-size:13px;line-height:1.6;margin:4px 0;color:var(--gg-color-primary-brown)}

/* ── Footer CTA ── */
.gg-pk-footer{border-top:3px solid var(--gg-color-near-black);padding:32px 0 16px;text-align:center;margin-top:40px}
.gg-pk-footer-inner h3{font-family:var(--gg-font-data);font-size:20px;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:0 0 12px}
.gg-pk-footer-inner p{font-size:14px;line-height:1.6;color:var(--gg-color-primary-brown);max-width:560px;margin:0 auto 20px}
.gg-pk-footer-buttons{display:flex;flex-wrap:wrap;justify-content:center;gap:12px;margin-bottom:24px}
.gg-pk-btn{display:inline-block;font-family:var(--gg-font-data);font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:2px;padding:12px 24px;text-decoration:none;text-align:center;transition:background 0.2s,color 0.2s}
.gg-pk-btn--primary{background:var(--gg-color-near-black);color:var(--gg-color-warm-paper);border:3px solid var(--gg-color-near-black)}
.gg-pk-btn--primary:hover{background:var(--gg-color-primary-brown);border-color:var(--gg-color-primary-brown)}
.gg-pk-btn--secondary{background:transparent;color:var(--gg-color-near-black);border:3px solid var(--gg-color-near-black)}
.gg-pk-btn--secondary:hover{background:var(--gg-color-near-black);color:var(--gg-color-warm-paper)}
.gg-pk-footer-back{font-family:var(--gg-font-data);font-size:12px;margin-top:16px}
.gg-pk-footer-back a{color:var(--gg-color-teal);text-decoration:underline}

/* ── Guide block overrides (copied from guide for standalone page) ── */

/* Timeline */
.gg-guide-timeline{margin:0 0 24px;padding-left:20px}
.gg-guide-timeline-title{font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:2px;margin:0 0 16px;color:var(--gg-color-primary-brown)}
.gg-guide-timeline-step{display:flex;gap:16px;margin-bottom:20px;position:relative}
.gg-guide-timeline-step:not(:last-child)::before{content:'';position:absolute;left:15px;top:32px;bottom:-20px;width:2px;background:var(--gg-color-tan)}
.gg-guide-timeline-marker{width:32px;height:32px;min-width:32px;background:var(--gg-color-teal);color:#fff;font-size:13px;font-weight:700;display:flex;align-items:center;justify-content:center;position:relative;z-index:1}
.gg-guide-timeline-content{flex:1}
.gg-guide-timeline-label{font-size:14px;font-weight:700;margin:0 0 6px;text-transform:uppercase;letter-spacing:1px;color:var(--gg-color-near-black)}
.gg-guide-timeline-content p{font-family:var(--gg-font-editorial);font-size:13px;line-height:1.6;margin:0;color:var(--gg-color-primary-brown)}

/* Accordion */
.gg-guide-accordion-item{border:2px solid var(--gg-color-near-black);margin-bottom:8px}
.gg-guide-accordion-trigger{display:flex;justify-content:space-between;align-items:center;width:100%;padding:12px 16px;background:var(--gg-color-warm-paper);border:none;cursor:pointer;font-family:var(--gg-font-data);font-size:13px;font-weight:700;text-align:left;color:var(--gg-color-near-black)}
.gg-guide-accordion-trigger:hover{background:var(--gg-color-sand)}
.gg-guide-accordion-icon{font-size:18px;font-weight:700}
.gg-guide-accordion-trigger[aria-expanded="true"] .gg-guide-accordion-icon{transform:rotate(45deg)}
.gg-guide-accordion-body{display:none;padding:16px;border-top:2px solid var(--gg-color-near-black)}
.gg-guide-accordion-trigger[aria-expanded="true"]+.gg-guide-accordion-body{display:block}

/* Process List */
.gg-guide-process-list{margin:0 0 20px}
.gg-guide-process-item{display:flex;gap:14px;margin-bottom:16px;padding:12px;border:2px solid var(--gg-color-near-black);background:var(--gg-color-warm-paper)}
.gg-guide-process-num{width:32px;height:32px;min-width:32px;background:var(--gg-color-near-black);color:#fff;font-size:14px;font-weight:700;display:flex;align-items:center;justify-content:center}
.gg-guide-process-body{flex:1}
.gg-guide-process-label{font-weight:700;font-size:14px;color:var(--gg-color-near-black)}
.gg-guide-process-pct{display:inline-block;background:var(--gg-color-gold);color:#fff;font-size:10px;font-weight:700;padding:2px 6px;margin-left:8px;letter-spacing:1px}
.gg-guide-process-detail{font-size:13px;color:var(--gg-color-primary-brown);margin:4px 0 0;line-height:1.5}

/* Callout */
.gg-guide-callout{padding:20px 24px;margin:0 0 20px;border-left:6px solid var(--gg-color-teal);background:var(--gg-color-warm-paper)}
.gg-guide-callout--quote{border-left-color:var(--gg-color-gold);font-style:italic}
.gg-guide-callout--highlight{border-left-color:var(--gg-color-gold)}
.gg-guide-callout p{font-family:var(--gg-font-editorial);font-size:13px;line-height:1.7;margin:0 0 8px;color:var(--gg-color-near-black)}
.gg-guide-callout p:last-child{margin-bottom:0}
.gg-guide-callout ul{margin:8px 0;padding-left:20px}
.gg-guide-callout li{font-family:var(--gg-font-editorial);font-size:13px;line-height:1.6;color:var(--gg-color-near-black)}

/* ── Print Styles ── */
@media print{
  body{background:#fff !important}
  .gg-pk-page{max-width:100%;padding:0;margin:0}
  .gg-pk-header{padding:16px 0;border-bottom:2px solid #000}
  .gg-pk-header-badge{background:#000;color:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .gg-pk-section{page-break-inside:avoid}
  .gg-pk-footer{display:none}
  .gg-guide-accordion-body{display:block !important}
  .gg-guide-accordion-trigger{pointer-events:none}
  .gg-guide-accordion-icon{display:none}
  .gg-guide-timeline-marker,.gg-guide-process-num,.gg-pk-nn-badge,.gg-pk-milestone-badge,.gg-pk-workout-mod{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  a[href]:after{content:none !important}
}

/* ── Responsive ── */
@media (max-width:600px){
  .gg-pk-header-title{font-size:24px}
  .gg-pk-vitals-ribbon{flex-direction:column;align-items:center;gap:6px}
  .gg-pk-footer-buttons{flex-direction:column;align-items:center}
  .gg-pk-btn{width:100%;max-width:300px}
}"""


# ── Page Assembly ─────────────────────────────────────────────


def build_prep_kit_js() -> str:
    """Minimal JS for accordion toggle on prep kit pages."""
    return """document.querySelectorAll('.gg-guide-accordion-trigger').forEach(function(btn){
  btn.addEventListener('click',function(){
    var expanded=this.getAttribute('aria-expanded')==='true';
    this.setAttribute('aria-expanded',String(!expanded));
  });
});"""


def generate_prep_kit_page(rd: dict, raw: dict, guide_sections: dict) -> str:
    """Assemble the complete prep kit HTML page."""
    slug = rd["slug"]
    name = rd["name"]
    canonical = f"{SITE_BASE_URL}/race/{slug}/prep-kit/"

    sections = [
        build_pk_header(rd, raw),
        build_pk_training_timeline(guide_sections, raw, rd),
        build_pk_non_negotiables(raw),
        build_pk_race_week(guide_sections, raw),
        build_pk_equipment(guide_sections, raw, rd),
        build_pk_race_morning(guide_sections, rd),
        build_pk_fueling(guide_sections, raw, rd),
        build_pk_decision_tree(guide_sections, rd),
        build_pk_recovery(guide_sections),
        build_pk_footer_cta(rd),
    ]

    body = "\n".join(s for s in sections if s)

    # Renumber sections sequentially (handles generic races skipping Section 02)
    counter = [0]
    def _renumber(m):
        counter[0] += 1
        return f'<span class="gg-pk-section-num">{counter[0]:02d}</span>'
    body = re.sub(
        r'<span class="gg-pk-section-num">\d{2}</span>', _renumber, body
    )

    tokens_css = get_tokens_css()
    font_css = get_font_face_css("/race/assets/fonts")
    preload = get_preload_hints("/race/assets/fonts")
    pk_css = build_prep_kit_css()
    js = build_prep_kit_js()

    meta_desc = f"Free race prep kit for {name}: 12-week training timeline, race-day checklists, packing list, and fueling strategy."

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Race Prep Kit: {esc(name)} | Gravel God</title>
  <meta name="description" content="{esc(meta_desc)}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:title" content="Race Prep Kit: {esc(name)}">
  <meta property="og:description" content="{esc(meta_desc)}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="Gravel God">
  {preload}
  <style>
{font_css}
{tokens_css}
{pk_css}
  </style>
  <!-- GA4 -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA_MEASUREMENT_ID}');</script>
</head>
<body>
<div class="gg-pk-page">
{body}
</div>
<script>
{js}
</script>
</body>
</html>'''


# ── CLI ───────────────────────────────────────────────────────


def generate_single(slug: str, data_dirs: list, output_dir: Path,
                    guide_sections: dict) -> bool:
    """Generate prep kit for a single race. Returns True on success."""
    filepath = find_data_file(slug, data_dirs)
    if not filepath:
        print(f"  SKIP  {slug} — data file not found")
        return False

    rd = load_race_data(filepath)
    raw = load_raw_training_data(filepath)
    page_html = generate_prep_kit_page(rd, raw, guide_sections)

    out_file = output_dir / f"{slug}.html"
    out_file.write_text(page_html, encoding="utf-8")
    tier = "full" if has_full_training_data(raw) else "generic"
    print(f"  OK    {slug} ({tier})")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Generate Race Prep Kit pages for gravel race profiles."
    )
    parser.add_argument("slug", nargs="?", help="Race slug (e.g., unbound-200)")
    parser.add_argument("--all", action="store_true", help="Generate for all races")
    parser.add_argument("--data-dir", help="Primary data directory")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    args = parser.parse_args()

    if not args.slug and not args.all:
        parser.error("Provide a race slug or use --all")

    project_root = Path(__file__).parent.parent
    data_dirs = []
    if args.data_dir:
        data_dirs.append(Path(args.data_dir))
    data_dirs.append(project_root / "race-data")

    output_dir = Path(args.output_dir) if args.output_dir else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load guide content once
    guide_sections = load_guide_sections()
    print(f"Loaded {len(guide_sections)} guide sections")

    if args.all:
        primary = None
        for d in data_dirs:
            d = Path(d)
            if d.exists() and list(d.glob("*.json")):
                primary = d
                break
        if not primary:
            print("ERROR: No race data directory found")
            return 1

        json_files = sorted(primary.glob("*.json"))
        ok_count = 0
        fail_count = 0
        full_count = 0
        generic_count = 0

        for jf in json_files:
            slug = jf.stem
            filepath = find_data_file(slug, data_dirs)
            if not filepath:
                fail_count += 1
                continue
            try:
                rd = load_race_data(filepath)
                raw = load_raw_training_data(filepath)
                page_html = generate_prep_kit_page(rd, raw, guide_sections)
                out_file = output_dir / f"{slug}.html"
                out_file.write_text(page_html, encoding="utf-8")
                ok_count += 1
                if has_full_training_data(raw):
                    full_count += 1
                else:
                    generic_count += 1
            except Exception as e:
                print(f"  FAIL  {slug}: {e}")
                fail_count += 1

        print(f"\nGenerated {ok_count} prep kits ({full_count} full, {generic_count} generic)")
        if fail_count:
            print(f"Failed: {fail_count}")
        return 1 if fail_count else 0

    else:
        success = generate_single(args.slug, data_dirs, output_dir, guide_sections)
        return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
