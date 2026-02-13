#!/usr/bin/env python3
"""Generate platform-ready video scripts from gravel race profile data.

Transforms 328 race profiles into spoken-cadence scripts for TikTok,
Instagram Reels, YouTube Shorts, and YouTube long-form. Scripts are
creative starting points for a presenter, not final copy.

Usage:
    python scripts/generate_video_scripts.py unbound-200
    python scripts/generate_video_scripts.py unbound-200 --format tier-reveal
    python scripts/generate_video_scripts.py --all --format tier-reveal
    python scripts/generate_video_scripts.py --all
    python scripts/generate_video_scripts.py --top 10
    python scripts/generate_video_scripts.py --head-to-head unbound-200 mid-south
    python scripts/generate_video_scripts.py --data-drops
    python scripts/generate_video_scripts.py --dry-run --all --format roast
"""

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
OUTPUT_DIR = PROJECT_ROOT / "video-scripts"

sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))
from generate_neo_brutalist import (
    normalize_race_data,
    ALL_DIMS,
    DIM_LABELS,
    COURSE_DIMS,
    OPINION_DIMS,
)

TIER_NAMES = {1: "Elite", 2: "Contender", 3: "Solid", 4: "Roster"}

FORMATS = ["tier-reveal", "should-you-race", "roast", "suffering-map"]

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_race(slug, data_dir=None):
    """Load and normalize a single race JSON by slug."""
    dirs = [Path(data_dir)] if data_dir else [RACE_DATA_DIR]
    for d in dirs:
        path = d / f"{slug}.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            return normalize_race_data(data)
    return None


def load_all_races(data_dir=None):
    """Load all race JSONs, return list of normalized dicts sorted by tier/score."""
    d = Path(data_dir) if data_dir else RACE_DATA_DIR
    races = []
    for path in sorted(d.glob("*.json")):
        with open(path) as f:
            data = json.load(f)
        rd = normalize_race_data(data)
        if rd.get("slug"):
            races.append(rd)
    races.sort(key=lambda r: (r["tier"], -r["overall_score"]))
    return races


# ---------------------------------------------------------------------------
# to_spoken — prose-to-voice transformer
# ---------------------------------------------------------------------------


def to_spoken(text):
    """Convert written prose to spoken-cadence text.

    - Converts em-dashes to periods
    - Breaks sentences >25 words at natural pauses
    - Converts large numbers to spoken approximations
    - Strips parenthetical asides
    """
    if not text:
        return ""

    text = str(text)

    # Strip parenthetical asides — (stuff in parens)
    text = re.sub(r"\s*\([^)]{0,120}\)", "", text)

    # Em-dashes → periods (both — and --)
    text = re.sub(r"\s*[—–]\s*", ". ", text)

    # Convert numbers to spoken form
    text = _convert_numbers(text)

    # Break long sentences
    sentences = re.split(r"(?<=[.!?])\s+", text)
    result = []
    for sent in sentences:
        words = sent.split()
        if len(words) > 25:
            result.append(_break_long_sentence(sent))
        else:
            result.append(sent)

    output = " ".join(result)
    # Clean up double periods / spaces
    output = re.sub(r"\.{2,}", ".", output)
    output = re.sub(r"\s{2,}", " ", output)
    return output.strip()


def _convert_numbers(text):
    """Convert numeric values to spoken approximations.

    Skips years (1900-2099), preserves number ranges (1,200-1,400),
    and converts large quantities to spoken form.
    """
    # First, protect number ranges like "1,200-1,400" by converting to spoken range
    def _range_to_spoken(match):
        low_str = match.group(1).replace(",", "")
        high_str = match.group(2).replace(",", "")
        try:
            low, high = int(low_str), int(high_str)
        except ValueError:
            return match.group(0)
        # Skip year ranges (e.g., "2006-2024")
        if 1900 <= low <= 2099 and 1900 <= high <= 2099:
            return match.group(0)
        low_spoken = _single_num_to_spoken(low)
        high_spoken = _single_num_to_spoken(high)
        if low_spoken and high_spoken:
            return f"{low_spoken} to {high_spoken}"
        return match.group(0)

    text = re.sub(r"([\d,]{4,})[-–]([\d,]{4,})", _range_to_spoken, text)

    def _num_to_spoken(match):
        prefix = match.group(1) or ""
        raw = match.group(2).replace(",", "")
        try:
            n = int(raw)
        except ValueError:
            return match.group(0)

        # Skip years (1900-2099) — they should be read as years, not quantities
        if 1900 <= n <= 2099 and prefix != "$":
            return match.group(0)

        is_dollar = prefix == "$"
        spoken = _single_num_to_spoken(n)
        if spoken is None:
            return match.group(0)

        if is_dollar:
            return f"{spoken} dollars"
        return spoken

    # Match optional $ + numbers with commas (at least 4 digits)
    return re.sub(r"(\$)?([\d,]{4,})", _num_to_spoken, text)


def _single_num_to_spoken(n):
    """Convert a single number to spoken form. Returns None if no conversion needed.

    Note: Year detection (1900-2099) is handled by the caller, not here.
    This function only converts magnitude.
    """
    if n >= 1_000_000:
        val = n / 1_000_000
        return f"{val:.1f}".rstrip("0").rstrip(".") + " million"
    elif n >= 10_000:
        val = n / 1000
        return f"{val:.0f} thousand"
    elif n >= 1000:
        val = n / 1000
        return f"{val:.1f}".rstrip("0").rstrip(".") + " thousand"
    return None


def _break_long_sentence(sent):
    """Break a long sentence at natural pause points."""
    # Try breaking at semicolons, then commas before conjunctions
    for pattern in [
        r";\s+",
        r",\s+(?=but\b)",
        r",\s+(?=and\b)",
        r",\s+(?=which\b)",
        r",\s+(?=where\b)",
        r",\s+(?=while\b)",
    ]:
        parts = re.split(pattern, sent, maxsplit=1)
        if len(parts) == 2 and len(parts[0].split()) >= 5:
            first = parts[0].rstrip(",;")
            if not first.endswith((".", "!", "?")):
                first += "."
            second = parts[1].strip()
            if second:
                second = second[0].upper() + second[1:]
            return f"{first} {second}"

    return sent


# ---------------------------------------------------------------------------
# analyze_hooks — hook generation from score patterns
# ---------------------------------------------------------------------------


def analyze_hooks(rd):
    """Return ranked list of hook angles derived from race data.

    Each hook: {angle: str, tension_text: str, engagement_question: str}
    """
    hooks = []
    scores = {dim: rd["explanations"][dim]["score"] for dim in ALL_DIMS}
    tier = rd["tier"]
    score = rd["overall_score"]
    name = rd["name"]
    tier_name = TIER_NAMES.get(tier, "Roster")

    # Overrated: high prestige but poor value/expenses
    if scores.get("prestige", 0) >= 4 and (
        scores.get("expenses", 5) <= 2 or scores.get("value", 5) <= 2
    ):
        hooks.append({
            "angle": "overrated",
            "tension_text": (
                f"{name} has a prestige score of {scores['prestige']} out of 5. "
                f"But expenses? {scores.get('expenses', '?')}. "
                f"Value? {scores.get('value', '?')}. Let me explain."
            ),
            "engagement_question": (
                f"Is {name} overrated? Or is the prestige worth the price?"
            ),
        })

    # Hidden gem: high adventure, low prestige
    if scores.get("adventure", 0) >= 4 and scores.get("prestige", 5) <= 2:
        hooks.append({
            "angle": "hidden_gem",
            "tension_text": (
                f"{name} scored {scores['adventure']} out of 5 for adventure. "
                f"Prestige? Just {scores['prestige']}. "
                f"Nobody's talking about this race. They should be."
            ),
            "engagement_question": (
                f"What's the most underrated gravel race you've done?"
            ),
        })

    # Prestige override: tier doesn't match raw score
    override_reason = rd["rating"].get("tier_override_reason", "")
    if "prestige" in override_reason.lower():
        hooks.append({
            "angle": "prestige_override",
            "tension_text": (
                f"{name} scored {score} out of 100. That's normally "
                f"{_score_to_tier_name(score)}. But it got bumped to "
                f"{tier_name} because of prestige. Here's why."
            ),
            "engagement_question": (
                f"Should prestige override the numbers? "
                f"Or should the score speak for itself?"
            ),
        })

    # Extreme stat: any dimension at 5 with a real explanation
    for dim in ALL_DIMS:
        if scores.get(dim, 0) == 5:
            expl = rd["explanations"][dim]["explanation"]
            if len(expl) > 50:
                hooks.append({
                    "angle": f"extreme_{dim}",
                    "tension_text": (
                        f"{name} scored a perfect 5 out of 5 for "
                        f"{DIM_LABELS.get(dim, dim)}. "
                        f"That's the highest possible rating. Here's what earned it."
                    ),
                    "engagement_question": (
                        f"What gravel race deserves a perfect "
                        f"{DIM_LABELS.get(dim, dim)} score?"
                    ),
                })
                break  # Only use first extreme stat

    # Fallback: generic tier reveal
    hooks.append({
        "angle": "tier_reveal",
        "tension_text": (
            f"We rated 328 gravel races. {name} is {tier_name}. "
            f"Score: {score} out of 100."
        ),
        "engagement_question": (
            f"Where would you rank {name}? Drop your tier in the comments."
        ),
    })

    return hooks


def _score_to_tier_name(score):
    """Map a raw score to its natural tier name (without overrides)."""
    if score >= 80:
        return "Elite"
    elif score >= 60:
        return "Contender"
    elif score >= 45:
        return "Solid"
    return "Roster"


# ---------------------------------------------------------------------------
# Format: tier-reveal (30-90s, TikTok/Reels/Shorts)
# ---------------------------------------------------------------------------


def fmt_tier_reveal(rd):
    """Generate a tier reveal short-form script."""
    hooks = analyze_hooks(rd)
    hook = hooks[0]
    name = rd["name"]
    slug = rd["slug"]
    tier = rd["tier"]
    score = rd["overall_score"]
    tier_name = TIER_NAMES.get(tier, "Roster")

    # Top dimensions by score (descending), take top 4
    dims_sorted = sorted(
        ALL_DIMS, key=lambda d: rd["explanations"][d]["score"], reverse=True
    )
    top_dims = dims_sorted[:4]

    # Build evidence lines
    evidence_lines = []
    for dim in top_dims:
        s = rd["explanations"][dim]["score"]
        expl = rd["explanations"][dim]["explanation"]
        spoken = to_spoken(expl)
        spoken = _truncate_to_sentence(spoken, 200)
        label = DIM_LABELS.get(dim, dim)
        evidence_lines.append(f"**{label}: {s}/5** — {spoken}")

    evidence_block = "\n".join(evidence_lines)

    location = rd["vitals"]["location"]
    distance = rd["vitals"]["distance"]

    return f"""# FORMAT: Tier Reveal | RACE: {name}
**Platform:** TikTok / Instagram Reels / YouTube Shorts | **Duration:** ~45-60s | **Hook Angle:** {hook['angle']}

---

## HOOK (0-3s)
[TEXT ON SCREEN: "{hook['tension_text'].split('.')[0]}."]
"{hook['tension_text']}"

## SETUP (3-8s)
[VISUAL: Race card — {name}, {location}, {distance}]
"{name}. {location}. {distance}."
[RIFF HERE — quick personal take or hot take on the race]

## EVIDENCE (8-35s)
[VISUAL: Score card cycling through dimensions]
{evidence_block}

## REVEAL (35-45s)
[TEXT ON SCREEN: "{tier_name.upper()} — {score}/100"]
"{name}. {tier_name}. {score} out of 100."
[RIFF HERE — agree or disagree with the rating? Would you bump it up or down?]

## CTA (45-55s)
[TEXT: gravelgodcycling.com/race/{slug}]
"Full breakdown on the site. Free race prep kit. Link in bio."

## ENGAGEMENT
"{hook['engagement_question']}"

---
**VISUAL NOTES:** Score card overlay, tier badge animation, race location map.{_rwgps_note(rd)}
"""


# ---------------------------------------------------------------------------
# Format: head-to-head (2-3 min, all platforms)
# ---------------------------------------------------------------------------


def fmt_head_to_head(rd1, rd2):
    """Generate a head-to-head comparison script for two races."""
    name1, name2 = rd1["name"], rd2["name"]
    slug1, slug2 = rd1["slug"], rd2["slug"]
    score1, score2 = rd1["overall_score"], rd2["overall_score"]
    tier1, tier2 = rd1["tier"], rd2["tier"]
    tn1 = TIER_NAMES.get(tier1, "Roster")
    tn2 = TIER_NAMES.get(tier2, "Roster")

    # Rank all dimensions by difference (descending), always show top 5-6
    all_diffs = []
    for dim in ALL_DIMS:
        s1 = rd1["explanations"][dim]["score"]
        s2 = rd2["explanations"][dim]["score"]
        all_diffs.append((dim, s1, s2, abs(s1 - s2)))
    all_diffs.sort(key=lambda x: x[3], reverse=True)

    # Take top 5-6 dimensions by difference (even if delta is only 1)
    diffs = [d for d in all_diffs if d[3] >= 1][:6]
    # If fewer than 3 dimensions differ at all, show top 5 by combined score
    if len(diffs) < 3:
        diffs = all_diffs[:5]

    big_diffs = sum(1 for d in diffs if d[3] >= 2)

    # Determine winner
    if tier1 < tier2:
        winner, loser = name1, name2
    elif tier2 < tier1:
        winner, loser = name2, name1
    elif score1 > score2:
        winner, loser = name1, name2
    elif score2 > score1:
        winner, loser = name2, name1
    else:
        winner, loser = None, None

    close_match = big_diffs < 3

    # Build comparison sections (up to 6 dims)
    comparison_blocks = []
    for dim, s1, s2, delta in diffs[:6]:
        label = DIM_LABELS.get(dim, dim)
        e1 = to_spoken(rd1["explanations"][dim]["explanation"])
        e2 = to_spoken(rd2["explanations"][dim]["explanation"])
        e1 = _truncate_to_sentence(e1, 150)
        e2 = _truncate_to_sentence(e2, 150)
        adv = name1 if s1 > s2 else name2
        comparison_blocks.append(
            f"### {label}\n"
            f"**{name1}: {s1}/5** — {e1}\n"
            f"**{name2}: {s2}/5** — {e2}\n"
            f"Edge: {adv} (+{delta})"
        )

    comparisons_text = "\n\n".join(comparison_blocks) if comparison_blocks else (
        "These two races scored almost identically across the board. "
        "The differences are in the details."
    )

    # Vitals comparison
    v1, v2 = rd1["vitals"], rd2["vitals"]

    close_note = ""
    if close_match:
        close_note = (
            "\n[RIFF HERE — these races are closer than the numbers suggest. "
            "Talk about what makes each one unique beyond scores.]"
        )

    winner_section = ""
    if winner:
        winner_section = (
            f'"{winner} takes it. But honestly? Do both."'
        )
    else:
        winner_section = (
            '"Dead heat. Same tier. Same score. Completely different races. Do both."'
        )

    return f"""# FORMAT: Head-to-Head | {name1} vs {name2}
**Platform:** All | **Duration:** ~2-3 min | **Hook Angle:** comparison

---

## HOOK (0-5s)
[TEXT ON SCREEN: "{name1} vs {name2}"]
"{name1} or {name2}. Which one deserves your entry fee? Let's break it down."

## TALE OF THE TAPE (5-20s)
[VISUAL: Split screen — race cards side by side]
"{name1}. {v1['location']}. {v1['distance']}. {tn1}, {score1} out of 100."
"{name2}. {v2['location']}. {v2['distance']}. {tn2}, {score2} out of 100."

## DIMENSION BREAKDOWN (20s-2min)
[VISUAL: Score comparison cards]
{comparisons_text}{close_note}

## VERDICT (2-2.5min)
[TEXT ON SCREEN: "WINNER: {winner or 'TIE'}"]
{winner_section}
[RIFF HERE — which would YOU choose if you could only do one?]

## CTA (2.5-3min)
[TEXT: gravelgodcycling.com]
"Full breakdowns for both on the site. Links in bio."

## ENGAGEMENT
"Which one are you picking? Drop it in the comments."

---
**VISUAL NOTES:** Split-screen score cards, radar chart overlay.{_rwgps_note(rd1)}{_rwgps_note(rd2)}
"""


# ---------------------------------------------------------------------------
# Format: should-you-race (5-10 min, YouTube)
# ---------------------------------------------------------------------------


def fmt_should_you_race(rd):
    """Generate a YouTube deep-dive script."""
    name = rd["name"]
    slug = rd["slug"]
    score = rd["overall_score"]
    tier = rd["tier"]
    tier_name = TIER_NAMES.get(tier, "Roster")

    # Course character
    character = to_spoken(rd["course"]["character"])

    # All 14 dimensions, top 8 highlighted
    dims_by_score = sorted(
        ALL_DIMS, key=lambda d: rd["explanations"][d]["score"], reverse=True
    )
    highlight_dims = dims_by_score[:8]
    remaining_dims = dims_by_score[8:]

    highlight_blocks = []
    for dim in highlight_dims:
        s = rd["explanations"][dim]["score"]
        expl = to_spoken(rd["explanations"][dim]["explanation"])
        label = DIM_LABELS.get(dim, dim)
        highlight_blocks.append(f"**{label}: {s}/5**\n\"{expl}\"")

    remaining_lines = []
    for dim in remaining_dims:
        s = rd["explanations"][dim]["score"]
        label = DIM_LABELS.get(dim, dim)
        remaining_lines.append(f"- {label}: {s}/5")

    highlights_text = "\n\n".join(highlight_blocks)
    remaining_text = "\n".join(remaining_lines)

    # Strengths / weaknesses
    strengths = rd["biased_opinion"]["strengths"]
    weaknesses = rd["biased_opinion"]["weaknesses"]
    strengths_text = "\n".join(f"- {to_spoken(s)}" for s in strengths) if strengths else "- No specific strengths listed"
    weaknesses_text = "\n".join(f"- {to_spoken(w)}" for w in weaknesses) if weaknesses else "- No specific weaknesses listed"

    # Verdict
    verdict_label = rd["biased_opinion"]["verdict"]
    should_you = to_spoken(rd["final_verdict"]["should_you_race"])
    alternatives = to_spoken(rd["final_verdict"]["alternatives"])

    # Logistics
    logi = rd["logistics"]
    logistics_items = []
    if logi.get("airport"):
        logistics_items.append(f"Fly into: {to_spoken(logi['airport'])}")
    if logi.get("lodging_strategy"):
        logistics_items.append(f"Lodging: {to_spoken(logi['lodging_strategy'])}")
    if rd["vitals"].get("entry_cost"):
        logistics_items.append(f"Entry: {rd['vitals']['entry_cost']}")
    logistics_text = "\n".join(f"- {item}" for item in logistics_items) if logistics_items else "- Logistics details on the site"

    location = rd["vitals"]["location"]
    distance = rd["vitals"]["distance"]

    return f"""# FORMAT: Should You Race | RACE: {name}
**Platform:** YouTube | **Duration:** ~5-10 min | **Hook Angle:** search intent

---

## HOOK (0-10s)
[TEXT ON SCREEN: "Should You Race {name}?"]
"Should you race {name}? I rated 328 gravel races. {name} scored {score} out of 100. {tier_name} tier. Here's what that actually means."

## THE COURSE (10s-1min)
[VISUAL: Route map{_rwgps_inline(rd)}]
"{name}. {location}. {distance}."
"{character}"
[RIFF HERE — describe what it feels like to ride this course]

## THE SCORES (1-5min)
[VISUAL: Score card with all 14 dimensions]

### Top 8 Dimensions
{highlights_text}

### Also Scored
{remaining_text}

[RIFF HERE — which scores surprised you? Which would you argue with?]

## STRENGTHS (5-6min)
[VISUAL: Strengths list overlay]
"What {name} does well:"
{strengths_text}

## WEAKNESSES (6-7min)
[VISUAL: Weaknesses list overlay]
"What they don't put on the website:"
{weaknesses_text}

## LOGISTICS (7-8min)
[VISUAL: Map + logistics card]
{logistics_text}

## VERDICT (8-9min)
[TEXT ON SCREEN: "{verdict_label} — {score}/100"]
"Verdict: {verdict_label}."
"{should_you}"
[RIFF HERE — would YOU do this race? Be honest.]

## ALTERNATIVES
"If {name} isn't quite right for you:"
"{alternatives}"

## CTA (9-10min)
[TEXT: gravelgodcycling.com/race/{slug}]
"Full breakdown on the site. Fourteen scored dimensions. Free race prep kit. Link in the description."

## ENGAGEMENT
"Have you raced {name}? Did we get the score right? Let me know in the comments."

---
**VISUAL NOTES:** Route map, score cards, strengths/weaknesses overlays, logistics map.{_rwgps_note(rd)}
"""


# ---------------------------------------------------------------------------
# Format: roast (2-4 min, all platforms)
# ---------------------------------------------------------------------------


def fmt_roast(rd):
    """Generate a race roast script."""
    name = rd["name"]
    slug = rd["slug"]
    score = rd["overall_score"]
    tier = rd["tier"]
    tier_name = TIER_NAMES.get(tier, "Roster")
    verdict = rd["biased_opinion"]["verdict"]

    strengths = rd["biased_opinion"]["strengths"]
    weaknesses = rd["biased_opinion"]["weaknesses"]
    bottom_line = to_spoken(rd["biased_opinion"]["bottom_line"])

    strengths_text = "\n".join(
        f'- "{to_spoken(s)}"' for s in strengths
    ) if strengths else '- "Honestly? We struggled to find highlights."'

    weaknesses_text = "\n".join(
        f'- "{to_spoken(w)}"' for w in weaknesses
    ) if weaknesses else '- "Look, every race has its issues."'

    # Find lowest-scoring dimensions for roast material
    dims_by_score = sorted(
        ALL_DIMS, key=lambda d: rd["explanations"][d]["score"]
    )
    worst_dims = dims_by_score[:3]
    roast_lines = []
    for dim in worst_dims:
        s = rd["explanations"][dim]["score"]
        label = DIM_LABELS.get(dim, dim)
        expl = to_spoken(rd["explanations"][dim]["explanation"])
        expl = _truncate_to_sentence(expl, 150)
        roast_lines.append(f"**{label}: {s}/5** — {expl}")
    roast_text = "\n".join(roast_lines)

    return f"""# FORMAT: Race Roast | RACE: {name}
**Platform:** All | **Duration:** ~2-3 min | **Hook Angle:** roast

---

## HOOK (0-5s)
[TEXT ON SCREEN: "{name}: {verdict}"]
"We gave {name} the verdict: {verdict}. {tier_name} tier. {score} out of 100. Let me tell you what that really means."

## WHAT THEY TELL YOU (5-30s)
[VISUAL: Marketing highlights overlay]
"Here's the pitch. What the website wants you to believe:"
{strengths_text}
[RIFF HERE — read these in your best promotional voice]

## WHAT THEY DON'T TELL YOU (30s-1.5min)
[VISUAL: Red flag overlay]
"Now the stuff that doesn't make the brochure:"
{weaknesses_text}
[RIFF HERE — which of these would actually make you think twice?]

## THE NUMBERS DON'T LIE (1.5-2min)
[VISUAL: Score card — lowest dimensions]
"And the scores that tell the real story:"
{roast_text}

## THE BOTTOM LINE (2-2.5min)
[TEXT ON SCREEN: "{verdict} — {score}/100"]
"{bottom_line}"
[RIFF HERE — roast it or defend it. Pick a side.]

## CTA (2.5-3min)
[TEXT: gravelgodcycling.com/race/{slug}]
"Full breakdown. All 14 dimensions. Free prep kit. Link in bio."

## ENGAGEMENT
"Roast or defend {name}. Go."

---
**VISUAL NOTES:** Score cards, marketing vs reality split screen.{_rwgps_note(rd)}
"""


# ---------------------------------------------------------------------------
# Format: suffering-map (15-60s, TikTok/Reels/Shorts)
# ---------------------------------------------------------------------------


def fmt_suffering_map(rd):
    """Generate a suffering map script. Returns None if no suffering zones."""
    zones = rd["course"].get("suffering_zones", [])
    if not zones:
        return None

    name = rd["name"]
    slug = rd["slug"]
    distance = rd["vitals"]["distance"]

    zone_blocks = []
    for zone in zones:
        mile = zone.get("mile", "?")
        label = zone.get("label", zone.get("named_section", "Unknown"))
        desc = to_spoken(zone.get("desc", ""))
        zone_blocks.append(
            f'[TEXT ON SCREEN: "MILE {mile}: {label}"]\n'
            f'"Mile {mile}. {label}. {desc}"'
        )

    zones_text = "\n\n".join(zone_blocks)
    duration = max(15, min(60, len(zones) * 12))

    return f"""# FORMAT: Suffering Map | RACE: {name}
**Platform:** TikTok / Instagram Reels / YouTube Shorts | **Duration:** ~{duration}s | **Hook Angle:** suffering

---

## HOOK (0-3s)
[TEXT ON SCREEN: "{name} — Where It Hurts"]
"Here's where {name} breaks you. {distance}. Zone by zone."

## THE SUFFERING ZONES (3-{duration - 8}s)
[VISUAL: Route map with zone markers]
{zones_text}

## CTA ({duration - 8}-{duration}s)
[TEXT: gravelgodcycling.com/race/{slug}]
"Full suffering breakdown on the site. Free race prep kit. Link in bio."

## ENGAGEMENT
"Which zone would end your race? Comment the mile marker."

---
**VISUAL NOTES:** Animated route map, zone markers appearing sequentially.{_rwgps_note(rd)}
"""


# ---------------------------------------------------------------------------
# Format: data-drops (database-wide, 15-30s each)
# ---------------------------------------------------------------------------


def fmt_data_drops(all_races):
    """Generate database-wide stat drops. Returns a single script with multiple drops."""
    total = len(all_races)
    tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    total_score = 0
    prestige_5 = []
    most_expensive = None
    cheapest_t1 = None
    highest_score = None
    lowest_score = None
    longest = None
    shortest = None

    for rd in all_races:
        tier = rd["tier"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        total_score += rd["overall_score"]

        if rd["explanations"]["prestige"]["score"] == 5:
            prestige_5.append(rd["name"])

        # Track extremes
        if highest_score is None or rd["overall_score"] > highest_score["overall_score"]:
            highest_score = rd
        if lowest_score is None or rd["overall_score"] < lowest_score["overall_score"]:
            lowest_score = rd

        dist = rd["vitals"].get("distance_mi", 0) or 0
        if dist > 0:
            if longest is None or dist > (longest["vitals"].get("distance_mi", 0) or 0):
                longest = rd
            if shortest is None or dist < (shortest["vitals"].get("distance_mi", 0) or 0):
                shortest = rd

        # Track cost extremes (parse dollar amounts from entry_cost)
        cost = _parse_cost(rd["vitals"].get("entry_cost"))
        if cost is not None:
            if most_expensive is None or cost > _parse_cost(most_expensive["vitals"].get("entry_cost")):
                most_expensive = rd
            if rd["tier"] == 1 and (cheapest_t1 is None or cost < _parse_cost(cheapest_t1["vitals"].get("entry_cost"))):
                cheapest_t1 = rd

    avg_score = round(total_score / total) if total else 0

    drops = []

    # Drop 1: Total database
    drops.append(
        _drop_script(
            "Database Size",
            f'"We rated {total} gravel races. Every single one scored on 14 dimensions. '
            f'Here\'s the breakdown."',
            f"[TEXT ON SCREEN: \"{total} RACES RATED\"]",
        )
    )

    # Drop 2: Tier distribution
    t1p = round(tier_counts[1] / total * 100) if total else 0
    drops.append(
        _drop_script(
            "Tier Distribution",
            f'"Out of {total} races, only {tier_counts[1]} made Elite. '
            f"That's {t1p} percent. "
            f'{tier_counts[2]} Contender. {tier_counts[3]} Solid. '
            f'{tier_counts[4]} Roster."',
            f"[TEXT ON SCREEN: \"ELITE: {tier_counts[1]} | CONTENDER: {tier_counts[2]} | "
            f"SOLID: {tier_counts[3]} | ROSTER: {tier_counts[4]}\"]",
        )
    )

    # Drop 3: Average score
    drops.append(
        _drop_script(
            "Average Score",
            f'"The average gravel race scores {avg_score} out of 100. '
            f'That puts most races in the {_score_to_tier_name(avg_score)} tier. '
            f'The bar is higher than you think."',
            f"[TEXT ON SCREEN: \"AVG SCORE: {avg_score}/100\"]",
        )
    )

    # Drop 4: Prestige 5 count
    if prestige_5:
        drops.append(
            _drop_script(
                "Perfect Prestige",
                f'"Only {len(prestige_5)} races earned a perfect 5 for Prestige. '
                f'The most exclusive club in gravel."',
                f"[TEXT ON SCREEN: \"PRESTIGE 5/5: {len(prestige_5)} RACES\"]",
            )
        )

    # Drop 5: Highest score
    if highest_score:
        drops.append(
            _drop_script(
                "Highest Rated",
                f'"{highest_score["name"]}. {highest_score["overall_score"]} out of 100. '
                f'The highest-rated gravel race in the database."',
                f"[TEXT ON SCREEN: \"#1: {highest_score['name']} — {highest_score['overall_score']}/100\"]",
            )
        )

    # Drop 6: Lowest score
    if lowest_score:
        drops.append(
            _drop_script(
                "Lowest Rated",
                f'"And the lowest? {lowest_score["name"]}. '
                f'{lowest_score["overall_score"]} out of 100. '
                f'Someone had to be last."',
                f"[TEXT ON SCREEN: \"LAST: {lowest_score['name']} — {lowest_score['overall_score']}/100\"]",
            )
        )

    # Drop 7: Longest race
    if longest:
        drops.append(
            _drop_script(
                "Longest Race",
                f'"{longest["name"]}. {longest["vitals"]["distance"]}. '
                f'The longest race in the database."',
                f"[TEXT ON SCREEN: \"LONGEST: {longest['name']} — {longest['vitals']['distance']}\"]",
            )
        )

    # Drop 8: Most expensive
    if most_expensive:
        cost_str = most_expensive["vitals"].get("entry_cost", "???")
        drops.append(
            _drop_script(
                "Most Expensive",
                f'"The most expensive entry fee in gravel? {most_expensive["name"]}. '
                f'{cost_str}. Pain isn\'t cheap."',
                f"[TEXT ON SCREEN: \"MOST EXPENSIVE: {most_expensive['name']} — {cost_str}\"]",
            )
        )

    # Drop 9: Cheapest T1
    if cheapest_t1:
        cost_str = cheapest_t1["vitals"].get("entry_cost", "???")
        drops.append(
            _drop_script(
                "Cheapest Elite Race",
                f'"The cheapest Elite-tier race? {cheapest_t1["name"]}. {cost_str}. '
                f'World-class racing without the world-class price tag."',
                f"[TEXT ON SCREEN: \"CHEAPEST ELITE: {cheapest_t1['name']} — {cost_str}\"]",
            )
        )

    drops_text = "\n\n---\n\n".join(drops)

    return f"""# FORMAT: Data Drops | DATABASE: {total} Gravel Races
**Platform:** TikTok / Instagram Reels / YouTube Shorts | **Duration:** ~15-30s each | **Hook Angle:** stats

Use each drop as a standalone short-form clip. Mix and match.

---

{drops_text}

---
**VISUAL NOTES:** Bold typography overlays, counter animations, tier badge graphics.
**CTA FOR ALL:** "{total} races. 14 dimensions. gravelgodcycling.com. Link in bio."
"""


def _drop_script(title, narration, visual):
    """Build a single data drop section."""
    return f"""## DROP: {title}
{visual}
{narration}"""


MAX_REASONABLE_ENTRY_FEE = 10_000  # No gravel race costs more than $10k to enter


def _parse_cost(cost_str):
    """Parse a dollar amount from a cost string. Returns int or None.

    Caps at MAX_REASONABLE_ENTRY_FEE to filter out prize purses,
    travel costs, and other non-entry-fee numbers that leak through
    the fallback regex in normalize_race_data.
    """
    if not cost_str:
        return None
    match = re.search(r"\$?([\d,]+)", str(cost_str))
    if match:
        try:
            val = int(match.group(1).replace(",", ""))
            if val > MAX_REASONABLE_ENTRY_FEE:
                return None  # Almost certainly not an entry fee
            return val
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncate_to_sentence(text, max_chars):
    """Truncate text at the last complete sentence within max_chars.

    Falls back to word boundary if no sentence boundary fits.
    """
    if len(text) <= max_chars:
        return text

    # Find the last sentence-ending punctuation within the limit
    truncated = text[:max_chars]
    for end in [". ", "! ", "? "]:
        idx = truncated.rfind(end)
        if idx > max_chars // 3:  # Don't truncate to less than 1/3 of allowed length
            return truncated[:idx + 1]

    # Check for sentence end at exactly the limit boundary
    if truncated.endswith((".", "!", "?")):
        return truncated

    # Fall back to word boundary
    word_break = truncated.rsplit(" ", 1)[0]
    if len(word_break) > max_chars // 3:
        return word_break + "..."

    return truncated + "..."


# Words per second for spoken narration (average presenter pace)
WORDS_PER_SECOND = 2.5

# Duration ranges in seconds for each format
FORMAT_DURATION_RANGES = {
    "tier-reveal": (30, 90),
    "head-to-head": (120, 210),
    "should-you-race": (300, 660),
    "roast": (120, 270),
    "suffering-map": (15, 75),
}


def estimate_spoken_seconds(script_text):
    """Estimate spoken duration from script text.

    Counts only words inside quoted narration lines (lines starting with ")
    and [RIFF HERE] markers (estimated at 10 seconds each).
    """
    word_count = 0
    riff_count = 0
    for line in script_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith('"') and stripped.endswith('"'):
            # Count words in narration lines
            word_count += len(stripped.split())
        if "[RIFF HERE" in stripped:
            riff_count += 1

    return round(word_count / WORDS_PER_SECOND) + (riff_count * 10)


def has_sufficient_data(rd, format_name):
    """Check if a race has enough data for a given format.

    Returns (bool, str) — (is_sufficient, reason if not).
    """
    bo = rd["biased_opinion"]

    if format_name == "roast":
        if not bo["strengths"] and not bo["weaknesses"]:
            return False, "missing strengths and weaknesses"
        if not bo["verdict"]:
            return False, "missing verdict label"

    if format_name == "should-you-race":
        if not bo["strengths"] and not bo["weaknesses"]:
            return False, "missing strengths and weaknesses"
        if not rd["final_verdict"]["should_you_race"]:
            return False, "missing should_you_race verdict"

    if format_name == "suffering-map":
        if not rd["course"].get("suffering_zones"):
            return False, "no suffering zones"

    return True, ""


def _rwgps_note(rd):
    """Return RWGPS visual note if route ID exists."""
    rwgps_id = rd["course"].get("ridewithgps_id")
    if rwgps_id:
        return f"\n**RWGPS Route:** https://ridewithgps.com/routes/{rwgps_id}"
    return ""


def _rwgps_inline(rd):
    """Return inline RWGPS reference for visual notes."""
    rwgps_id = rd["course"].get("ridewithgps_id")
    if rwgps_id:
        return f", RWGPS route {rwgps_id}"
    return ""


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_script(content, format_name, slug, output_dir):
    """Write a script to the output directory."""
    out_path = Path(output_dir) / format_name / f"{slug}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Generate video scripts from gravel race profiles."
    )
    parser.add_argument("slug", nargs="?", help="Race slug (e.g., unbound-200)")
    parser.add_argument(
        "--format",
        choices=["tier-reveal", "head-to-head", "should-you-race", "roast",
                 "suffering-map", "data-drops"],
        help="Script format to generate",
    )
    parser.add_argument("--all", action="store_true", help="Generate for all races")
    parser.add_argument("--top", type=int, help="Generate for top N races by tier/score")
    parser.add_argument(
        "--head-to-head", nargs=2, metavar="SLUG",
        help="Compare two races head-to-head",
    )
    parser.add_argument("--data-drops", action="store_true", help="Generate database stats")
    parser.add_argument("--data-dir", default=str(RACE_DATA_DIR), help="Race data directory")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")

    args = parser.parse_args()

    # Validate args — exactly one mode required
    modes = sum([
        bool(args.slug),
        args.all,
        bool(args.top),
        bool(args.head_to_head),
        args.data_drops,
    ])
    if modes == 0:
        parser.error("Provide a slug, --all, --top N, --head-to-head, or --data-drops")
    if modes > 1:
        parser.error("Use only one of: slug, --all, --top, --head-to-head, --data-drops")

    # Head-to-head mode
    if args.head_to_head:
        slug1, slug2 = args.head_to_head
        rd1 = load_race(slug1, args.data_dir)
        rd2 = load_race(slug2, args.data_dir)
        if not rd1:
            print(f"ERROR: Race not found: {slug1}", file=sys.stderr)
            sys.exit(1)
        if not rd2:
            print(f"ERROR: Race not found: {slug2}", file=sys.stderr)
            sys.exit(1)

        script = fmt_head_to_head(rd1, rd2)
        if args.dry_run:
            print(f"[DRY RUN] head-to-head: {slug1} vs {slug2}")
        else:
            path = write_script(script, "head-to-head", f"{slug1}-vs-{slug2}", args.output_dir)
            print(f"  wrote {path}")
        return

    # Data drops mode
    if args.data_drops:
        races = load_all_races(args.data_dir)
        script = fmt_data_drops(races)
        if args.dry_run:
            print(f"[DRY RUN] data-drops: {len(races)} races")
        else:
            path = write_script(script, "data-drops", "all-stats", args.output_dir)
            print(f"  wrote {path}")
        return

    # Determine race list
    if args.all or args.top:
        races = load_all_races(args.data_dir)
        if args.top:
            races = races[:args.top]
        slugs = [r["slug"] for r in races]
    else:
        slugs = [args.slug]

    # Determine formats
    per_race_formats = FORMATS  # tier-reveal, should-you-race, roast, suffering-map
    if args.format:
        per_race_formats = [args.format]

    # Generate
    total = 0
    skipped = 0
    for slug in slugs:
        rd = load_race(slug, args.data_dir)
        if not rd:
            print(f"WARNING: Race not found: {slug}", file=sys.stderr)
            continue

        for fmt in per_race_formats:
            if fmt == "head-to-head" or fmt == "data-drops":
                continue  # These are handled separately

            # Check data completeness before generating
            sufficient, reason = has_sufficient_data(rd, fmt)
            if not sufficient:
                skipped += 1
                if not (args.all or args.top):
                    print(f"  skipped {slug}/{fmt} ({reason})")
                continue

            if fmt == "tier-reveal":
                script = fmt_tier_reveal(rd)
            elif fmt == "should-you-race":
                script = fmt_should_you_race(rd)
            elif fmt == "roast":
                script = fmt_roast(rd)
            elif fmt == "suffering-map":
                script = fmt_suffering_map(rd)
                if script is None:
                    skipped += 1
                    continue
            else:
                continue

            if args.dry_run:
                print(f"[DRY RUN] {fmt}: {slug}")
            else:
                path = write_script(script, fmt, slug, args.output_dir)
                print(f"  wrote {path}")
            total += 1

    skip_msg = f", {skipped} skipped (insufficient data)" if skipped else ""
    if args.dry_run:
        print(f"\n{total} scripts would be generated{skip_msg}.")
    else:
        print(f"\n{total} scripts generated{skip_msg}.")


if __name__ == "__main__":
    main()
