#!/usr/bin/env python3
"""Generate production-ready video briefs from gravel race profile data.

Reads race JSON profiles and existing video scripts, then outputs
structured production briefs with:
  - Story arc beats with timing and retention targets
  - Trope detection from scoring patterns
  - Avatar reaction pose selections
  - B-roll sourcing queries (YouTube, RWGPS, race websites)
  - Music BPM targets and sound design cues
  - Meme/reaction insert points
  - Text-on-screen specs
  - Thumbnail generation prompts

Usage:
    python scripts/generate_video_briefs.py unbound-200
    python scripts/generate_video_briefs.py unbound-200 --format tier-reveal
    python scripts/generate_video_briefs.py --all --format tier-reveal
    python scripts/generate_video_briefs.py --top 25
    python scripts/generate_video_briefs.py --head-to-head unbound-200 mid-south
    python scripts/generate_video_briefs.py --data-drops
    python scripts/generate_video_briefs.py --dry-run --all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
SCRIPTS_DIR = PROJECT_ROOT / "video-scripts"
OUTPUT_DIR = PROJECT_ROOT / "video-briefs"

sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))
from generate_neo_brutalist import (
    normalize_race_data,
    ALL_DIMS,
    DIM_LABELS,
    COURSE_DIMS,
    OPINION_DIMS,
)

# Import script generators for narration text
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from generate_video_scripts import (
    analyze_hooks,
    to_spoken,
    load_race,
    load_all_races,
    estimate_spoken_seconds,
    TIER_NAMES,
)

# ── Constants ─────────────────────────────────────────────────

FORMATS = ["tier-reveal", "should-you-race", "roast", "suffering-map",
           "head-to-head"]
# "data-drops" excluded — script-only format, no production brief generator yet.
# Use generate_video_scripts.py --data-drops for script text.

# Duration targets in seconds per format (updated from retention research)
DURATION_TARGETS = {
    "tier-reveal": (25, 35),       # Short: 75-85% completion sweet spot
    "suffering-map": (15, 30),     # Short: max completion
    "data-drops": (15, 20),        # Short: single stat, loop potential
    "roast": (180, 300),           # Mid: 3-5 min, contrast pattern
    "head-to-head": (300, 480),    # Mid: 5-8 min, escalation room
    "should-you-race": (480, 720), # Long: 8-12 min, mid-roll eligible
}

# Music BPM targets by energy level
BPM = {
    "calm": (60, 80),       # Analysis, explanation, data sections
    "building": (80, 100),  # Setup, context, moderate energy
    "tension": (100, 120),  # Pre-reveal, escalation, controversy
    "reveal": (120, 140),   # Tier reveal, verdict, payoff moments
}

# Music volume in dB by section energy
VOLUME_DB = {
    "narration": (-22, -25),   # Background during talking
    "transition": (-15, -18),  # Between sections
    "burst": (-8, -12),        # Energy peaks, meme inserts
}

# Visual change frequency (seconds between cuts) by format type
CUT_FREQUENCY = {
    "short": (2, 3),     # Shorts: visual change every 2-3 seconds
    "mid": (15, 25),     # Mid-form: 15-25 seconds (younger audience)
    "long": (20, 40),    # Long-form: 20-40 seconds (data audience)
}

# Retention targets
RETENTION_TARGETS = {
    "short": {"3s_hold": ">65%", "completion": ">75%", "loop_replay": "target"},
    "mid": {"30s_hold": ">70%", "midpoint": ">55%", "completion": ">40%"},
    "long": {"1min_hold": ">70%", "midpoint": ">50%", "avg_retention": ">45%"},
}

# Narration speed limits (words per minute)
WPM_COMFORTABLE = 150    # Conversational, authentic delivery
WPM_FAST = 170           # Energetic but still clear
WPM_MAX = 200            # Absolute ceiling — auctioneer territory
WPM_TARGET = WPM_FAST    # Default target for narration feasibility

# Short-format hard ceiling (seconds)
SHORT_MAX_SEC = 55  # Leave 5s buffer under platform 60s limit

# Avatar reaction library (what to request from Midjourney/Runway)
AVATAR_REACTIONS = {
    "shocked": "Wide eyes, jaw drop — for surprising data",
    "chef_kiss": "Chef's kiss gesture — for perfect 5/5 scores",
    "facepalm": "Facepalm — for low scores or weaknesses",
    "mustache_twirl": "Villain mustache twirl — for roast reveals",
    "thinking": "Chin stroke, squinting — for analysis moments",
    "presenting": "Open palm gesture — for data presentation",
    "pointing": "Pointing at screen — for text callouts",
    "thumbs_up": "Thumbs up, confident — for positive verdicts",
    "thumbs_down": "Thumbs down, grimace — for negative verdicts",
    "suffering": "Agony face, sweat drops — for suffering zones",
    "excited": "Arms up, grinning — for tier-1 reveals",
    "skeptical": "One eyebrow raised — for overrated takes",
    "mind_blown": "Hands on head, explosion effect — for shocking stats",
    "shrug": "Both palms up — for 'it depends' moments",
    "counting": "Finger counting — for numbered lists",
    "versus": "Boxing stance — for head-to-head hooks",
}

# ── Humor System ─────────────────────────────────────────────


def _stable_hash(s: str) -> int:
    """Deterministic hash for quip selection (Python hash() is randomized)."""
    return int(hashlib.md5(s.encode()).hexdigest(), 16)


# Score quips: dimension → score (1-5) → list of deadpan one-liners (<15 words)
SCORE_QUIPS = {
    "logistics": {
        1: ["You are the aid station.", "Good luck finding anything out there.", "Organizers communicate via telepathy, apparently."],
        2: ["Basic setup. Don't expect hand-holding.", "Functional. Not impressive.", "You'll figure it out. Eventually."],
        3: ["Gets the job done. Nothing fancy.", "Competent operation. Shows up on time.", "Adequate. The word was invented for this."],
        4: ["Well-oiled machine. Aid stations where you need them.", "Smooth operation. Somebody knows what they're doing.", "One less thing to worry about."],
        5: ["Military precision. Every detail dialed.", "Best-in-class operations. Everything just works.", "You could set your watch to this organization."],
    },
    "length": {
        1: ["Short enough to call a training ride.", "Barely registers as a race distance.", "Your warmup might be longer."],
        2: ["Manageable distance. Back by lunch.", "Short but honest about it.", "Won't destroy your week."],
        3: ["Proper race distance. Enough to hurt.", "Long enough to matter. Short enough to recover.", "The Goldilocks zone of suffering."],
        4: ["This is a long day. Plan accordingly.", "Bring real food. Not just gels.", "Double-digit hours are on the table."],
        5: ["Ultra distance. Bring lights and a plan.", "Your legs will remember this one for weeks.", "This race measures commitment in hours, not miles."],
    },
    "technicality": {
        1: ["If you can ride a bike, you can ride this.", "Smooth roads. Save your suspension money.", "Flat bars optional."],
        2: ["Some chunky bits. Nothing catastrophic.", "Mild technical demands. Pick decent tires.", "Your road bike might survive. Might."],
        3: ["Requires line choice. Rewards the attentive rider.", "Technical enough to thin the pack.", "The course bites if you stop paying attention."],
        4: ["Bike handling matters here. Practice your descents.", "Rocky, rooty, or both. Probably both.", "Your equipment choices will be tested."],
        5: ["Borderline mountain bike territory.", "Technical enough to ruin your day on wrong tires.", "The course is the competitor."],
    },
    "elevation": {
        1: ["Flat. Your climbing legs get a rest day.", "Elevation gain measured in speed bumps.", "Your biggest climb is the parking garage."],
        2: ["Rolling terrain. Nothing that'll break you.", "Some ups and downs. Manageable.", "A few hills. Nothing to lose sleep over."],
        3: ["Proper climbing. You'll earn your descents.", "Enough vertical to remind you gravity exists.", "The hills sort the trained from the untrained."],
        4: ["Serious elevation. Train your climbing legs.", "Mountain passes on the menu.", "Your power-to-weight ratio matters here."],
        5: ["Relentless vertical. The climbing never stops.", "Mountainous. Your granny gear will earn its keep.", "Elevation gain that belongs on a trail run."],
    },
    "climate": {
        1: ["Weather's a non-factor. Predictably mild.", "Pack one layer. You'll be fine.", "Climate controlled by nature."],
        2: ["Mostly pleasant. Check the forecast anyway.", "Weather cooperates more often than not.", "Mild conditions. Nothing dramatic."],
        3: ["Variable. Bring layers and a flexible attitude.", "The weather could go either way.", "Pack for two seasons."],
        4: ["Weather is part of the race strategy.", "Conditions will test your kit choices.", "Expect to be uncomfortable at some point."],
        5: ["The weather IS the race.", "Extreme conditions guaranteed. Dress accordingly.", "Mother Nature gets a vote and a veto."],
    },
    "altitude": {
        1: ["Sea level. Your lungs get a day off.", "Low altitude. Breathe easy.", "Oxygen plentiful. Power output normal."],
        2: ["Mild elevation. Most riders won't notice.", "Not enough altitude to blame for your pace.", "Negligible altitude effect."],
        3: ["Moderate altitude. Worth acclimatizing for.", "You'll feel it on the climbs.", "Altitude starts to matter here."],
        4: ["Thin air territory. Acclimatize or suffer.", "High enough to affect your power. Plan for it.", "Your sea-level FTP is a fiction up here."],
        5: ["Extreme altitude. Your power meter will gaslight you.", "Oxygen is a luxury item at this elevation.", "Breathe twice as hard for half the watts."],
    },
    "adventure": {
        1: ["Straightforward course. No surprises.", "About as adventurous as a bike path.", "Adventure not included."],
        2: ["Mild adventure. Scenic ride with a number plate.", "Some interesting terrain. Mostly familiar.", "Light adventure. Nothing wild."],
        3: ["Genuine adventure elements. Expect the unexpected.", "This race takes you somewhere different.", "Adventure factor is real."],
        4: ["Serious exploration vibes. Far from pavement.", "Remote terrain. Self-sufficiency required.", "The kind of ride you'll tell stories about."],
        5: ["Full expedition mode. Genuine backcountry.", "Type-two fun guaranteed. Type-one fun optional.", "Adventure is the entire point."],
    },
    "prestige": {
        1: ["Nobody at the coffee shop will recognize this name.", "Under the radar. Completely unknown.", "Zero name recognition."],
        2: ["Regional reputation. The locals know.", "Known in certain circles. Niche following.", "Building a name. Not there yet."],
        3: ["Established race. Solid reputation.", "Name carries weight in the gravel community.", "Respected. Not yet legendary."],
        4: ["Prestigious. People plan seasons around it.", "Top-shelf reputation. Calendar priority.", "Finishing this one means something."],
        5: ["Bucket list tier. The name speaks for itself.", "Gravel royalty. The race everyone knows.", "The one people ask about first."],
    },
    "race_quality": {
        1: ["Bare minimum effort. Just a course and a clock.", "Quality is not the selling point here.", "Participation trophy vibes."],
        2: ["Basic but functional. Gets the job done.", "Nothing special about the race execution.", "Adequate. Room for improvement."],
        3: ["Well-run race. Professional touches throughout.", "Good race quality. No major complaints.", "Solid production value."],
        4: ["High-quality event. Attention to detail shows.", "Premium race experience.", "The kind of race that spoils you for others."],
        5: ["World-class execution. Sets the standard.", "Best-in-class race production.", "Everything about this race is dialed."],
    },
    "experience": {
        1: ["Forgettable. Just another gravel road.", "The experience is unremarkable.", "Nothing to write home about."],
        2: ["Pleasant enough. Won't change your life.", "A nice day on the bike. Nothing more.", "Fine. Just fine."],
        3: ["Memorable course. Has character.", "You'll remember this one. Mostly fondly.", "The experience justifies the entry fee."],
        4: ["Special. This race sticks with you.", "Genuinely unique. Hard to replicate.", "The kind of race that reshapes your season."],
        5: ["Transformative. People come back different.", "Once-in-a-lifetime course experience.", "This race ruins other races for you."],
    },
    "community": {
        1: ["Show up. Race. Leave.", "Community vibe is nonexistent.", "Every rider for themselves."],
        2: ["Polite. Not exactly warm.", "Some community spirit. Nothing organized.", "Riders acknowledge each other. Barely."],
        3: ["Genuine community feel. People stick around.", "Good vibes. Riders actually talk to each other.", "Community is a real selling point."],
        4: ["Strong community. This race builds friendships.", "The post-race scene is half the event.", "Riders come for the race. Stay for the people."],
        5: ["Family reunion energy. Everyone belongs.", "The community IS the race.", "Strangers become friends by mile ten."],
    },
    "field_depth": {
        1: ["Small field. You might podium by showing up.", "Sparse start line. Plenty of elbow room.", "Not exactly stacked."],
        2: ["Modest field. Some fast riders in the mix.", "Enough competition to keep you honest.", "Small but scrappy field."],
        3: ["Solid field depth. Competitive across the board.", "Good racing at every level.", "Deep enough to push you."],
        4: ["Stacked field. Fast riders everywhere.", "Competition is fierce. Train accordingly.", "Pro-level talent in the mix."],
        5: ["Start line looks like a WorldTour bus exploded.", "Deepest field in gravel. Murderer's row.", "World-class athletes. And they race hard."],
    },
    "value": {
        1: ["Terrible value. The math does not work.", "You're overpaying for the privilege of suffering.", "Your entry fee deserves better."],
        2: ["Below-average value. You can do better.", "Not the worst deal. Close though.", "Value is not the strong suit."],
        3: ["Fair value. You get what you pay for.", "Reasonable price for what's offered.", "The math works out. Barely."],
        4: ["Good value. More bang for your buck than most.", "Strong value proposition.", "One of the better deals in gravel."],
        5: ["Dollar for dollar, one of the best in gravel.", "Exceptional value. Almost feels like a steal.", "Punches way above its price point."],
    },
    "expenses": {
        # expenses: 1 = MOST EXPENSIVE (worst), 5 = MOST AFFORDABLE (best)
        1: ["Bring a second mortgage and strong opinions about hotels.", "Premium pricing. Everything costs more here.", "Your accountant would not approve."],
        2: ["Expensive. Travel and lodging add up fast.", "Not cheap. The costs pile on.", "Budget carefully. The extras get you."],
        3: ["Mid-range expenses. Budget a proper race weekend.", "Plan for a few hundred all-in.", "Standard gravel race budget."],
        4: ["Affordable. Won't break the bank.", "Reasonable costs. Plan a modest budget.", "Your wallet will survive this one."],
        5: ["Budget-friendly. Your bank account barely notices.", "Cheap to do. No excuses.", "Minimal financial barrier."],
    },
    "_default": {
        1: ["Bottom of the scale.", "As low as it gets.", "One out of five."],
        2: ["Below average.", "Room for improvement.", "Middling at best."],
        3: ["Right down the middle.", "Average. Perfectly average.", "Textbook middle."],
        4: ["Above average. Genuinely strong.", "This is where it gets interesting.", "Four out of five. Solid."],
        5: ["Top of the scale. No higher to go.", "Perfect score. Full marks.", "Five out of five. Maxed out."],
    },
}

# Section intro rotations (selected deterministically per slug)
ROAST_MARKETING_INTROS = [
    "Here's the pitch. What the website wants you to believe.",
    "Let's start with what they put on the registration page.",
    "The marketing version. The one with nice photos.",
    "Every race has a highlight reel. Here's theirs.",
]
ROAST_REALITY_INTROS = [
    "Now the stuff that doesn't make the brochure.",
    "Now for the part the registration page leaves out.",
    "And here's what they don't mention in the promo video.",
    "Time for the fine print.",
]
ROAST_DATA_INTROS = [
    "The scores that tell the real story.",
    "Let the numbers do the talking.",
    "The data doesn't care about your feelings.",
    "Fourteen dimensions. No opinions. Just scores.",
]
SYR_SCORE_INTROS = [
    "Let's go through the scores.",
    "Fourteen dimensions. Here's where it lands.",
    "Time to break down the scorecard.",
    "The numbers. All fourteen of them.",
]
SYR_REMAINING_INTROS = [
    "And the rest of the scorecard.",
    "The rest. Quick-fire.",
    "The rest, in rapid succession.",
]
SYR_STRENGTH_INTROS = [
    "What {name} does well.",
    "Where {name} earns its score.",
    "The case for {name}.",
    "What {name} gets right.",
]
SYR_WEAKNESS_INTROS = [
    "What they don't put on the website.",
    "Now the other side.",
    "The fine print.",
    "What the brochure conveniently omits.",
]
SYR_LOGISTICS_INTROS = [
    "Here's the practical stuff.",
    "The logistics. What you actually need to know.",
    "Travel, lodging, and the unsexy details.",
]

# Head-to-head round narration templates
ROUND_TIE_TEMPLATES = [
    "{label}. Both scored {s1} out of 5. Dead even.",
    "{label}. {s1} to {s2}. Identical. Nobody wins this one.",
    "{label}. Same score. {s1} apiece. Moving on.",
]
ROUND_CLOSE_TEMPLATES = [
    "{label}. Slight edge to {winner}. {hi} to {lo}.",
    "{label}. {winner} takes it by one. {hi} to {lo}.",
    "{label}. Close call. {winner} edges it. {hi} to {lo}.",
]
ROUND_CLEAR_TEMPLATES = [
    "{label}. {winner} wins this round. {hi} to {lo}.",
    "{label}. Clear advantage {winner}. {hi} to {lo}.",
    "{label}. {winner} takes it. {hi} to {lo}. No argument.",
]
ROUND_BLOWOUT_TEMPLATES = [
    "{label}. {winner} takes this one and it's not close. {hi} to {lo}.",
    "{label}. Not even competitive. {winner} runs away with it. {hi} to {lo}.",
    "{label}. Blowout. {winner} dominates. {hi} to {lo}.",
]
ROUND_FINALE_TEMPLATES = [
    "{label}. The big one. {hi} to {lo}. {winner} takes the round that matters.",
    "{label}. Saved the best for last. {hi} to {lo}. {winner} closes it out.",
    "{label}. Final round. {hi} to {lo}. That's the gap that decides it.",
]

# Tier-reveal deadpan tags
TIER_TAGS = {
    1: "Elite company.",
    2: "Strong field.",
    3: "Solid middle.",
    4: "Work in progress.",
}

# Head-to-head verdict closers
H2H_WINNER_CLOSERS = [
    "The data picked a side.",
    "Not even a controversial call.",
    "The scorecards don't lie.",
]
H2H_TIE_CLOSERS = [
    "Do both. Problem solved.",
    "The only wrong answer is neither.",
    "Different races. Same tier of suffering.",
]


def _extract_first_sentence(text):
    """Extract the first sentence from explanation text as race-specific color.

    Returns empty string if too short (<5 words) or too long (>25 words).
    """
    if not text:
        return ""
    match = re.match(r'^([^.!?]+[.!?])', text)
    if not match:
        return ""
    sentence = match.group(1).strip()
    words = sentence.split()
    if len(words) < 5 or len(words) > 25:
        return ""
    return sentence


def _narrate_score(dim, score, slug, rd=None, compact=False):
    """Narrate a dimension score with personality.

    Combines: score statement + deadpan quip + (optional) explanation excerpt.
    compact=True skips explanation for short-format time budgets.
    """
    label = DIM_LABELS.get(dim, dim)
    quips = SCORE_QUIPS.get(dim, SCORE_QUIPS["_default"]).get(
        score, SCORE_QUIPS["_default"].get(score, [""])
    )
    idx = _stable_hash(slug + dim) % len(quips) if quips else 0
    quip = quips[idx] if quips else ""

    parts = [f"{label}. {score} out of 5."]
    if quip:
        parts.append(quip)
    if not compact and rd:
        excerpt = _extract_first_sentence(
            rd["explanations"][dim]["explanation"]
        )
        if excerpt:
            parts.append(excerpt)

    return " ".join(parts)


def _pick_intro(slug, intro_list):
    """Deterministically select a section intro from a rotation list."""
    idx = _stable_hash(slug) % len(intro_list)
    return intro_list[idx]


def _narrate_round(dim, s1, s2, name1, name2, slug_pair, is_finale=False):
    """Narrate a head-to-head round with energy based on score delta."""
    label = DIM_LABELS.get(dim, dim)
    delta = abs(s1 - s2)
    winner = name1 if s1 > s2 else name2 if s2 > s1 else None
    hi, lo = max(s1, s2), min(s1, s2)

    idx = _stable_hash(slug_pair + dim)

    if is_finale and delta >= 1:
        templates = ROUND_FINALE_TEMPLATES
    elif delta == 0:
        templates = ROUND_TIE_TEMPLATES
    elif delta == 1:
        templates = ROUND_CLOSE_TEMPLATES
    elif delta == 2:
        templates = ROUND_CLEAR_TEMPLATES
    else:
        templates = ROUND_BLOWOUT_TEMPLATES

    template = templates[idx % len(templates)]
    return template.format(
        label=label, winner=winner or "neither",
        s1=s1, s2=s2, hi=hi, lo=lo,
        name1=name1, name2=name2,
    )


# ── Trope Detection ──────────────────────────────────────────


def detect_tropes(rd):
    """Analyze race data and return ranked list of applicable story tropes.

    Each trope: {name, tension, mechanism, hook_text, engagement_q}
    Ranked by narrative strength (strongest first).
    """
    tropes = []
    scores = {dim: rd["explanations"][dim]["score"] for dim in ALL_DIMS}
    tier = rd["tier"]
    score = rd["overall_score"]
    name = rd["name"]
    tier_name = TIER_NAMES.get(tier, "Roster")

    # ── Underdog Reveal: low tier/prestige but has a perfect 5 somewhere
    if tier >= 3 and any(scores[d] == 5 for d in ALL_DIMS):
        best_dim = max(ALL_DIMS, key=lambda d: scores[d])
        best_label = DIM_LABELS.get(best_dim, best_dim)
        tropes.append({
            "name": "underdog_reveal",
            "tension": (
                f"{name} is {tier_name}. Score: {score}. "
                f"But it scored a PERFECT 5 for {best_label}. "
                f"How does a {tier_name} race beat Elite races on {best_label}?"
            ),
            "mechanism": "Von Restorff effect — the outlier demands attention. "
                         "Underdog arcs trigger prediction error (brain expected low, got high).",
            "hook_text": f"This {tier_name} race scored higher than Unbound on {best_label}.",
            "engagement_q": f"Should a perfect {best_label} score bump {name} up a tier?",
            "strength": 9,
        })

    # ── Betrayal / Exposé: high prestige but bad value/expenses
    if scores.get("prestige", 0) >= 4 and (
        scores.get("value", 5) <= 2 or scores.get("expenses", 5) <= 2
    ):
        tropes.append({
            "name": "expose",
            "tension": (
                f"Everyone says {name} is a must-do race. "
                f"Prestige: {scores['prestige']}/5. "
                f"But Value? {scores.get('value', '?')}/5. "
                f"Expenses? {scores.get('expenses', '?')}/5. "
                f"The data tells a different story."
            ),
            "mechanism": "Cognitive dissonance — viewer believed X was good, "
                         "specific counter-evidence triggers emotional demand for resolution.",
            "hook_text": f"{name} has a dirty secret the brochure won't tell you.",
            "engagement_q": f"Is {name} overrated or worth every dollar?",
            "strength": 8,
        })

    # ── David vs Goliath: race outscores a higher-tier race on multiple dims
    # (detected in head-to-head context, placeholder for single-race briefs)
    if tier >= 3 and score >= 50:
        high_dims = [d for d in ALL_DIMS if scores[d] >= 4]
        if len(high_dims) >= 3:
            tropes.append({
                "name": "david_vs_goliath",
                "tension": (
                    f"{name} sits in {tier_name}. Score: {score}. "
                    f"But it scores 4+ on {len(high_dims)} dimensions. "
                    f"Some Elite races can't say that."
                ),
                "mechanism": "Loss aversion — framing around what elite races LACK "
                             "that this underdog HAS.",
                "hook_text": f"This {tier_name} race beats half the Elite tier.",
                "engagement_q": f"Name an Elite race with worse scores than {name}.",
                "strength": 7,
            })

    # ── Prestige Override: tier doesn't match raw score
    override_reason = rd["rating"].get("tier_override_reason", "")
    if "prestige" in override_reason.lower():
        natural_tier = _score_to_tier_name(score)
        tropes.append({
            "name": "prestige_override",
            "tension": (
                f"{name} scored {score}/100. "
                f"That's {natural_tier} by the numbers. "
                f"But prestige bumped it to {tier_name}. "
                f"Should reputation override data?"
            ),
            "mechanism": "Zeigarnik effect — the unresolved question "
                         "(is the override fair?) demands closure.",
            "hook_text": f"{name}'s tier was OVERRIDDEN. Here's why.",
            "engagement_q": "Should prestige count more than the numbers?",
            "strength": 8,
        })

    # ── Extreme Stat: any dimension at 5 with rich explanation
    for dim in ALL_DIMS:
        if scores.get(dim, 0) == 5:
            expl = rd["explanations"][dim]["explanation"]
            if len(expl) > 80:
                label = DIM_LABELS.get(dim, dim)
                tropes.append({
                    "name": f"extreme_{dim}",
                    "tension": (
                        f"{name}: perfect 5/5 for {label}. "
                        f"The highest possible rating. "
                        f"Out of 328 races, how many hit that?"
                    ),
                    "mechanism": "Curiosity gap (specific) — knowing a perfect score exists "
                                 "but not why triggers dopamine anticipation.",
                    "hook_text": f"Only a handful of races score 5/5 on {label}. {name} is one.",
                    "engagement_q": f"What race deserves a perfect {label} score?",
                    "strength": 6,
                })
                break  # Only first extreme

    # ── Gatekeeping Callout: high expenses but good race
    if scores.get("expenses", 5) <= 2 and score >= 60:
        tropes.append({
            "name": "gatekeeping_callout",
            "tension": (
                f"{name} scores {score}/100. {tier_name}. "
                f"But Expenses: {scores.get('expenses', '?')}/5. "
                f"This race is pricing out the people who'd love it most."
            ),
            "mechanism": "Tribal identity — position viewer as the savvy insider "
                         "who refuses to overpay. Us vs them.",
            "hook_text": f"You probably can't afford {name}. And that's the point.",
            "engagement_q": f"Should great races be affordable? Or is exclusivity the appeal?",
            "strength": 5,
        })

    # ── Hidden Gem: high adventure/experience, low prestige
    if (scores.get("adventure", 0) >= 4 or scores.get("experience", 0) >= 4) and \
       scores.get("prestige", 5) <= 2:
        tropes.append({
            "name": "hidden_gem",
            "tension": (
                f"{name}: Adventure {scores.get('adventure', '?')}/5. "
                f"Experience {scores.get('experience', '?')}/5. "
                f"Prestige? {scores.get('prestige', '?')}/5. "
                f"Nobody's talking about this race."
            ),
            "mechanism": "FOMO / loss aversion — the viewer is MISSING something. "
                         "Losses feel 2.5x stronger than equivalent gains.",
            "hook_text": f"The best race you've never heard of.",
            "engagement_q": f"What's the most underrated gravel race you've done?",
            "strength": 7,
        })

    # ── Fallback: standard tier reveal
    tropes.append({
        "name": "tier_reveal",
        "tension": (
            f"We rated 328 gravel races on 14 dimensions. "
            f"{name}: {tier_name}. {score}/100."
        ),
        "mechanism": "Countdown / ranking — inherent escalation and social comparison.",
        "hook_text": f"328 races. 14 dimensions. Where does {name} land?",
        "engagement_q": f"Where would YOU rank {name}? Drop your tier.",
        "strength": 4,
    })

    tropes.sort(key=lambda t: t["strength"], reverse=True)
    return tropes


def _score_to_tier_name(score):
    if score >= 80:
        return "Elite"
    elif score >= 60:
        return "Contender"
    elif score >= 45:
        return "Solid"
    return "Roster"


# ── Beat Generators (per format) ─────────────────────────────


def brief_tier_reveal(rd):
    """Generate production brief for a tier-reveal Short."""
    tropes = detect_tropes(rd)
    trope = tropes[0]
    hooks = analyze_hooks(rd)
    name = rd["name"]
    slug = rd["slug"]
    tier = rd["tier"]
    score = rd["overall_score"]
    tier_name = TIER_NAMES.get(tier, "Roster")
    location = rd["vitals"]["location"]
    distance = rd["vitals"]["distance"]

    # Top 3 dimensions for evidence
    dims_sorted = sorted(
        ALL_DIMS, key=lambda d: rd["explanations"][d]["score"], reverse=True
    )
    top_dims = dims_sorted[:3]

    # Build evidence lines
    evidence = []
    for dim in top_dims:
        s = rd["explanations"][dim]["score"]
        label = DIM_LABELS.get(dim, dim)
        evidence.append({"dimension": label, "score": s, "max": 5})

    # Hook narration trimmed to 5 seconds at fast pace
    hook_narration = _trim_narration(trope["hook_text"], 5)

    beats = [
        {
            "id": "hook",
            "label": "HOOK",
            "time_range": "0:00-0:05",
            "duration_sec": 5,
            "narration": hook_narration,
            "text_on_screen": trope["hook_text"].split(".")[0] + ".",
            "visual": "Bold text overlay + avatar reaction",
            "avatar_pose": _pick_avatar("hook", trope["name"], tier),
            "broll_sources": [],
            "music_bpm": BPM["reveal"],
            "volume_db": VOLUME_DB["burst"],
            "cut_frequency_sec": CUT_FREQUENCY["short"],
            "editing_note": "Pattern interrupt. Maximum visual stimulation. "
                           "Text appears word-by-word (kinetic typography).",
            "psych_mechanism": trope["mechanism"],
        },
        {
            "id": "setup",
            "label": "SETUP",
            "time_range": "0:05-0:10",
            "duration_sec": 5,
            "narration": f"{name}. {location}. {distance}.",
            "text_on_screen": f"{name} | {location}",
            "visual": "Race card with location pin + route preview",
            "avatar_pose": "presenting",
            "broll_sources": _get_broll_sources(rd, "location"),
            "music_bpm": BPM["building"],
            "volume_db": VOLUME_DB["narration"],
            "cut_frequency_sec": CUT_FREQUENCY["short"],
            "editing_note": "Quick establishing shot. Show race card, "
                           "then cut to route map or location footage.",
        },
        {
            "id": "evidence",
            "label": "EVIDENCE",
            "time_range": "0:10-0:22",
            "duration_sec": 12,
            "narration": " ".join(
                _narrate_score(dim, rd["explanations"][dim]["score"],
                               slug, compact=True)
                for dim in top_dims
            ),
            "text_on_screen": "Score cards cycling",
            "visual": "Animated score cards — one per dimension",
            "avatar_pose": "thinking",
            "broll_sources": [],
            "music_bpm": BPM["tension"],
            "volume_db": VOLUME_DB["narration"],
            "cut_frequency_sec": (2, 3),
            "editing_note": "Each dimension gets 4-5 seconds. Visual change on EVERY score. "
                           "Use Von Restorff: if any score is 5/5 or 1/5, isolate it visually "
                           "(different color flash, avatar reaction shot). "
                           "[RIFF HERE] after any extreme score.",
            "evidence_data": evidence,
        },
        {
            "id": "reveal",
            "label": "REVEAL",
            "time_range": "0:22-0:28",
            "duration_sec": 6,
            "narration": f"{name}. {tier_name}. {score} out of 100. {TIER_TAGS.get(tier, '')}".strip(),
            "text_on_screen": f"{tier_name.upper()} — {score}/100",
            "visual": "Tier badge animation + full score",
            "avatar_pose": _pick_avatar("reveal", trope["name"], tier),
            "broll_sources": [],
            "music_bpm": BPM["reveal"],
            "volume_db": VOLUME_DB["burst"],
            "cut_frequency_sec": CUT_FREQUENCY["short"],
            "editing_note": "SILENCE for 0.5s before reveal (long-form technique adapted). "
                           "Then: tier badge slams in. Avatar reaction. "
                           "This is the Von Restorff moment — make it visually distinct. "
                           "[RIFF HERE] after tier badge lands.",
        },
        {
            "id": "cta",
            "label": "CTA + LOOP",
            "time_range": "0:28-0:33",
            "duration_sec": 5,
            "narration": f"Full breakdown. Free prep kit. Link in bio.",
            "text_on_screen": f"gravelgodcycling.com/race/{slug}",
            "visual": "URL overlay + engagement question text",
            "avatar_pose": "pointing",
            "broll_sources": [],
            "music_bpm": BPM["building"],
            "volume_db": VOLUME_DB["transition"],
            "cut_frequency_sec": CUT_FREQUENCY["short"],
            "editing_note": "Design for LOOP: the final frame should visually connect "
                           "back to the hook frame. On TikTok, seamless loops = replays = "
                           "the strongest algorithmic signal.",
            "engagement_question": trope["engagement_q"],
        },
    ]

    return _build_brief(
        slug=slug,
        format_name="tier-reveal",
        platform="TikTok / Instagram Reels / YouTube Shorts",
        duration_target=DURATION_TARGETS["tier-reveal"],
        story_arc="hook-setup-evidence-reveal-loop",
        trope=trope,
        beats=beats,
        retention_targets=RETENTION_TARGETS["short"],
        thumbnail_prompt=_thumbnail_prompt(rd, trope, "tier-reveal"),
        rd=rd,
    )


def brief_suffering_map(rd):
    """Generate production brief for a suffering-map Short."""
    zones = rd["course"].get("suffering_zones", [])
    if not zones:
        return None

    name = rd["name"]
    slug = rd["slug"]
    distance = rd["vitals"]["distance"]

    zone_beats = []
    hook_sec = 5  # Hook duration

    # Enforce Short format ceiling: hook + zones + 5s CTA <= SHORT_MAX_SEC
    max_zone_total = SHORT_MAX_SEC - hook_sec - 5
    num_zones = len(zones)
    seconds_per_zone = max(3, min(8, max_zone_total // max(num_zones, 1)))

    # If too many zones to fit, truncate to what fits
    max_zones = max_zone_total // seconds_per_zone
    if num_zones > max_zones:
        zones = zones[:max_zones]
        num_zones = max_zones

    for i, zone in enumerate(zones):
        mile = zone.get("mile", "?")
        label = zone.get("label", zone.get("named_section", "Unknown"))
        desc = to_spoken(zone.get("desc", ""))
        start_sec = hook_sec + (i * seconds_per_zone)
        end_sec = start_sec + seconds_per_zone

        # Validate narration fits the zone duration
        narration_text = f"Mile {mile}. {label}. {desc}"
        narration_text = _trim_narration(narration_text, seconds_per_zone)

        is_last_zone = (i == num_zones - 1)
        zone_note = (
            f"Zone marker {i+1} appears on map. "
            "Progressive color intensity (green→yellow→red)."
        )
        if is_last_zone:
            zone_note += " [RIFF HERE] after final zone reveal."

        zone_beats.append({
            "id": f"zone_{i+1}",
            "label": f"ZONE {i+1}: Mile {mile}",
            "time_range": f"{_fmt_time(start_sec)}-{_fmt_time(end_sec)}",
            "duration_sec": seconds_per_zone,
            "narration": narration_text,
            "text_on_screen": f"MILE {mile}: {label}",
            "visual": "Route map with zone marker animation",
            "avatar_pose": "suffering" if is_last_zone else "pointing",
            "broll_sources": _get_broll_sources(rd, "terrain"),
            "music_bpm": BPM["tension"],
            "volume_db": VOLUME_DB["narration"],
            "cut_frequency_sec": CUT_FREQUENCY["short"],
            "editing_note": zone_note,
        })

    total_zone_sec = num_zones * seconds_per_zone
    total_sec = hook_sec + total_zone_sec + 5

    beats = [
        {
            "id": "hook",
            "label": "HOOK",
            "time_range": f"0:00-{_fmt_time(hook_sec)}",
            "duration_sec": hook_sec,
            "narration": _trim_narration(
                f"Here's where {name} breaks you. {distance}. Zone by zone.",
                hook_sec,
            ),
            "text_on_screen": f"{name} — Where It Hurts",
            "visual": "Full route map, then zoom into first zone",
            "avatar_pose": "suffering",
            "broll_sources": _get_broll_sources(rd, "route"),
            "music_bpm": BPM["tension"],
            "volume_db": VOLUME_DB["burst"],
            "cut_frequency_sec": CUT_FREQUENCY["short"],
            "editing_note": "Start with full route visible, then rapid zoom in. "
                           "Ominous music hit. Avatar suffering face.",
        },
        *zone_beats,
        {
            "id": "cta",
            "label": "CTA + LOOP",
            "time_range": f"{_fmt_time(hook_sec + total_zone_sec)}-{_fmt_time(total_sec)}",
            "duration_sec": 5,
            "narration": "Full suffering breakdown on the site. Link in bio.",
            "text_on_screen": f"gravelgodcycling.com/race/{slug}",
            "visual": "Full map with all zones lit up",
            "avatar_pose": "pointing",
            "broll_sources": [],
            "music_bpm": BPM["building"],
            "volume_db": VOLUME_DB["transition"],
            "cut_frequency_sec": CUT_FREQUENCY["short"],
            "editing_note": "Loop design: end with zoomed-out map that connects "
                           "back to the opening frame.",
            "engagement_question": "Which zone would end your race? Comment the mile marker.",
        },
    ]

    return _build_brief(
        slug=slug,
        format_name="suffering-map",
        platform="TikTok / Instagram Reels / YouTube Shorts",
        duration_target=DURATION_TARGETS["suffering-map"],
        story_arc="hook-sequential-zones-loop",
        trope={"name": "countdown", "mechanism": "Sequential escalation + anticipation",
               "hook_text": f"Where {name} breaks you", "strength": 6},
        beats=beats,
        retention_targets=RETENTION_TARGETS["short"],
        thumbnail_prompt=f"South Park style cartoon cyclist in agony, route map background, "
                         f"red zone markers, '{name}' text --ar 9:16 --cref [CHARACTER_URL]",
        rd=rd,
    )


def brief_roast(rd):
    """Generate production brief for a race roast (3-5 min)."""
    tropes = detect_tropes(rd)
    trope = tropes[0]
    name = rd["name"]
    slug = rd["slug"]
    score = rd["overall_score"]
    tier = rd["tier"]
    tier_name = TIER_NAMES.get(tier, "Roster")
    verdict = rd["biased_opinion"]["verdict"]

    strengths = rd["biased_opinion"]["strengths"]
    weaknesses = rd["biased_opinion"]["weaknesses"]
    bottom_line = to_spoken(rd["biased_opinion"]["bottom_line"])

    # Worst 3 dimensions for roast material
    dims_by_score = sorted(ALL_DIMS, key=lambda d: rd["explanations"][d]["score"])
    worst_dims = dims_by_score[:3]
    roast_data = []
    for dim in worst_dims:
        s = rd["explanations"][dim]["score"]
        label = DIM_LABELS.get(dim, dim)
        roast_data.append({"dimension": label, "score": s, "max": 5})

    beats = [
        {
            "id": "hook",
            "label": "HOOK",
            "time_range": "0:00-0:10",
            "duration_sec": 10,
            "narration": (
                f"We gave {name} the verdict: {verdict}. "
                f"{tier_name} tier. {score} out of 100. "
                f"Let me tell you what that really means."
            ),
            "text_on_screen": f"{name}: {verdict}",
            "visual": "Verdict badge slam + tier badge + avatar",
            "avatar_pose": "mustache_twirl",
            "broll_sources": _get_broll_sources(rd, "location"),
            "music_bpm": BPM["tension"],
            "volume_db": VOLUME_DB["burst"],
            "cut_frequency_sec": CUT_FREQUENCY["mid"],
            "editing_note": "Open with verdict like a boxing title card. "
                           "Avatar with villain energy. Music: ominous build. "
                           "PROMISE the viewer they'll learn the real story.",
            "psych_mechanism": "Curiosity gap + cognitive dissonance (verdict vs expectation).",
        },
        {
            "id": "marketing_pitch",
            "label": "WHAT THEY TELL YOU",
            "time_range": "0:10-0:50",
            "duration_sec": 40,
            "narration": _pick_intro(slug, ROAST_MARKETING_INTROS),
            "text_on_screen": "THE PITCH",
            "visual": "Marketing highlights overlay — strengths as bullet points",
            "avatar_pose": "skeptical",
            "broll_sources": _get_broll_sources(rd, "marketing"),
            "music_bpm": BPM["building"],
            "volume_db": VOLUME_DB["narration"],
            "cut_frequency_sec": CUT_FREQUENCY["mid"],
            "editing_note": "Read strengths in an exaggerated 'promotional voice.' "
                           "Avatar side-eyes camera. Bright, clean visuals — "
                           "this is the 'too good to be true' section. "
                           "CONTRAST PATTERN: this calm section sets up the burst at 0:50.",
            "content_data": {"strengths": strengths or ["No specific strengths listed"]},
        },
        {
            "id": "reality_check",
            "label": "WHAT THEY DON'T TELL YOU",
            "time_range": "0:50-1:50",
            "duration_sec": 60,
            "narration": _pick_intro(slug, ROAST_REALITY_INTROS),
            "text_on_screen": "THE REALITY",
            "visual": "Red flag overlay — weaknesses with warning icons",
            "avatar_pose": "facepalm",
            "broll_sources": _get_broll_sources(rd, "terrain"),
            "music_bpm": BPM["tension"],
            "volume_db": VOLUME_DB["narration"],
            "cut_frequency_sec": CUT_FREQUENCY["mid"],
            "editing_note": "BURST SEQUENCE at 0:50 transition (pattern interrupt). "
                           "5-10 quick cuts: meme reaction, avatar facepalm, "
                           "red overlay flash, warning sound. Then settle into analysis. "
                           "Each weakness gets its own visual card + avatar reaction.",
            "meme_insert": {
                "timing": "0:50",
                "trigger": "Section transition",
                "suggested_clip": "shocked_pikachu or record_scratch",
                "duration_sec": 1.5,
            },
            "content_data": {"weaknesses": weaknesses or ["No weaknesses listed"]},
        },
        {
            "id": "data_evidence",
            "label": "THE NUMBERS DON'T LIE",
            "time_range": "1:50-2:50",
            "duration_sec": 60,
            "narration": _pick_intro(slug, ROAST_DATA_INTROS) + " " + " ".join(
                _narrate_score(dim, rd["explanations"][dim]["score"],
                               slug, rd=rd)
                for dim in worst_dims
            ),
            "text_on_screen": "THE DATA",
            "visual": "Score cards — lowest 3 dimensions with explanations",
            "avatar_pose": "thinking",
            "broll_sources": [],
            "music_bpm": BPM["tension"],
            "volume_db": VOLUME_DB["narration"],
            "cut_frequency_sec": CUT_FREQUENCY["mid"],
            "editing_note": "RE-ENGAGEMENT BEAT — this is the ~2 min mark. "
                           "Start with the least bad score, escalate to worst. "
                           "Each score reveal: brief silence (0.5s), then number slams in. "
                           "Avatar reaction scales with how bad the score is. "
                           "Von Restorff: visually isolate the worst score (different color, "
                           "bigger text, longer hold). "
                           "[RIFF HERE] after the worst score reveal.",
            "evidence_data": roast_data,
        },
        {
            "id": "verdict",
            "label": "THE BOTTOM LINE",
            "time_range": "2:50-3:30",
            "duration_sec": 40,
            "narration": bottom_line,
            "text_on_screen": f"{verdict} — {score}/100",
            "visual": "Verdict card + final tier badge",
            "avatar_pose": _pick_avatar("verdict", trope["name"], tier),
            "broll_sources": [],
            "music_bpm": BPM["reveal"],
            "volume_db": VOLUME_DB["burst"],
            "cut_frequency_sec": CUT_FREQUENCY["mid"],
            "editing_note": "PAYOFF. Close the open loop from the hook. "
                           "Avatar delivers final take directly to camera. "
                           "End ABRUPTLY — never signal 'we're wrapping up.' "
                           "MrBeast rule: cut to CTA mid-energy.",
        },
        {
            "id": "cta",
            "label": "CTA",
            "time_range": "3:30-3:45",
            "duration_sec": 15,
            "narration": f"Full breakdown. All 14 dimensions. Free prep kit. Link in bio.",
            "text_on_screen": f"gravelgodcycling.com/race/{slug}",
            "visual": "URL overlay + engagement question",
            "avatar_pose": "pointing",
            "broll_sources": [],
            "music_bpm": BPM["building"],
            "volume_db": VOLUME_DB["transition"],
            "cut_frequency_sec": CUT_FREQUENCY["mid"],
            "editing_note": "Keep energy up. Don't wind down.",
            "engagement_question": f"Roast or defend {name}. Go.",
        },
    ]

    return _build_brief(
        slug=slug,
        format_name="roast",
        platform="All platforms",
        duration_target=DURATION_TARGETS["roast"],
        story_arc="expose: pitch → reality → data → verdict",
        trope=trope,
        beats=beats,
        retention_targets=RETENTION_TARGETS["mid"],
        thumbnail_prompt=_thumbnail_prompt(rd, trope, "roast"),
        rd=rd,
    )


def brief_should_you_race(rd):
    """Generate production brief for a Should You Race deep-dive (8-12 min)."""
    tropes = detect_tropes(rd)
    trope = tropes[0]
    name = rd["name"]
    slug = rd["slug"]
    score = rd["overall_score"]
    tier = rd["tier"]
    tier_name = TIER_NAMES.get(tier, "Roster")
    character = to_spoken(rd["course"]["character"])

    # All 14 dims sorted by score
    dims_by_score = sorted(
        ALL_DIMS, key=lambda d: rd["explanations"][d]["score"], reverse=True
    )
    top_dims = dims_by_score[:8]
    remaining_dims = dims_by_score[8:]

    strengths = rd["biased_opinion"]["strengths"]
    weaknesses = rd["biased_opinion"]["weaknesses"]
    verdict_label = rd["biased_opinion"]["verdict"]
    should_you = to_spoken(rd["final_verdict"]["should_you_race"])
    alternatives = to_spoken(rd["final_verdict"]["alternatives"])

    logi = rd["logistics"]
    logistics_items = []
    if logi.get("airport"):
        logistics_items.append(f"Fly into: {to_spoken(logi['airport'])}")
    if logi.get("lodging_strategy"):
        logistics_items.append(f"Lodging: {to_spoken(logi['lodging_strategy'])}")
    if rd["vitals"].get("entry_cost"):
        logistics_items.append(f"Entry: {rd['vitals']['entry_cost']}")

    location = rd["vitals"]["location"]
    distance = rd["vitals"]["distance"]

    beats = [
        {
            "id": "hook",
            "label": "HOOK + PROMISE",
            "time_range": "0:00-0:15",
            "duration_sec": 15,
            "narration": (
                f"Should you race {name}? "
                f"I rated 328 gravel races on 14 dimensions. "
                f"{name} scored {score} out of 100. {tier_name} tier. "
                f"Here's what that actually means for your season."
            ),
            "text_on_screen": f"Should You Race {name}?",
            "visual": "Title card + tier badge + avatar",
            "avatar_pose": "presenting",
            "broll_sources": _get_broll_sources(rd, "hero"),
            "music_bpm": BPM["building"],
            "volume_db": VOLUME_DB["narration"],
            "cut_frequency_sec": (10, 15),
            "editing_note": "STATE THE PREMISE IN 8 SECONDS. "
                           "Clear value prop: 'I rated 328 races. Here's where this one lands.' "
                           "This is the 8-second decision window. "
                           "Viewers who stay past 15s are 58% more likely to finish.",
            "psych_mechanism": "Curiosity gap (specific) + IKEA effect "
                              "(viewer predicts the tier before reveal).",
        },
        {
            "id": "course",
            "label": "THE COURSE",
            "time_range": "0:15-1:15",
            "duration_sec": 60,
            "narration": f"{name}. {location}. {distance}. {character}",
            "text_on_screen": f"{name} | {location} | {distance}",
            "visual": "Route map + terrain footage",
            "avatar_pose": "presenting",
            "broll_sources": _get_broll_sources(rd, "route"),
            "music_bpm": BPM["calm"],
            "volume_db": VOLUME_DB["narration"],
            "cut_frequency_sec": CUT_FREQUENCY["long"],
            "editing_note": "Let the course breathe. Show the route map, "
                           "then cut to terrain-specific B-roll. "
                           "This is the SETUP phase — grounding the viewer "
                           "before the data analysis. Pacing: 25-40 sec cuts.",
        },
        {
            "id": "scores_top",
            "label": "THE SCORES — Top 8",
            "time_range": "1:15-4:15",
            "duration_sec": 180,
            "narration": _pick_intro(slug, SYR_SCORE_INTROS) + " " + " ".join(
                _narrate_score(dim, rd["explanations"][dim]["score"],
                               slug, rd=rd)
                for dim in top_dims
            ),
            "text_on_screen": "14 DIMENSIONS",
            "visual": "Score cards — 8 expanded dimensions",
            "avatar_pose": "thinking",
            "broll_sources": [],
            "music_bpm": BPM["building"],
            "volume_db": VOLUME_DB["narration"],
            "cut_frequency_sec": CUT_FREQUENCY["long"],
            "editing_note": "PROGRESSIVE RHYTHM: start tight (15-20 sec per dimension), "
                           "slow down for the most interesting scores (30-40 sec). "
                           "Each score: number appears, brief pause, explanation. "
                           "Avatar reacts to extreme scores (5/5 = chef_kiss, 1/5 = facepalm). "
                           "RE-ENGAGEMENT at 3:00 mark: insert a surprising score reveal "
                           "or a meme reaction to break the pattern.",
            "evidence_data": [
                {"dimension": DIM_LABELS.get(d, d),
                 "score": rd["explanations"][d]["score"], "max": 5}
                for d in top_dims
            ],
            "meme_insert": {
                "timing": "~3:00",
                "trigger": "3-minute retention dip prevention",
                "suggested_clip": "avatar reaction to most extreme score",
                "duration_sec": 2,
            },
        },
        {
            "id": "scores_remaining",
            "label": "THE SCORES — Also Scored",
            "time_range": "4:15-5:00",
            "duration_sec": 45,
            "narration": _pick_intro(slug, SYR_REMAINING_INTROS) + " " + " ".join(
                _narrate_score(dim, rd["explanations"][dim]["score"],
                               slug, compact=True)
                for dim in remaining_dims
            ),
            "text_on_screen": None,
            "visual": "Quick-fire score list — remaining 6 dimensions",
            "avatar_pose": "counting",
            "broll_sources": [],
            "music_bpm": BPM["building"],
            "volume_db": VOLUME_DB["narration"],
            "cut_frequency_sec": (5, 10),
            "editing_note": "FAST PACING — 7 seconds per dimension. "
                           "Quick-fire energy change from the deep analysis above. "
                           "This is a PATTERN INTERRUPT through pacing shift.",
            "evidence_data": [
                {"dimension": DIM_LABELS.get(d, d),
                 "score": rd["explanations"][d]["score"], "max": 5}
                for d in remaining_dims
            ],
        },
        {
            "id": "strengths",
            "label": "STRENGTHS",
            "time_range": "5:00-5:45",
            "duration_sec": 45,
            "narration": _pick_intro(slug, SYR_STRENGTH_INTROS).format(name=name),
            "text_on_screen": "STRENGTHS",
            "visual": "Strengths list overlay with positive visual treatment",
            "avatar_pose": "thumbs_up",
            "broll_sources": _get_broll_sources(rd, "positive"),
            "music_bpm": BPM["building"],
            "volume_db": VOLUME_DB["narration"],
            "cut_frequency_sec": CUT_FREQUENCY["long"],
            "editing_note": "Warm energy. Each strength gets its own card. "
                           "Avatar genuinely positive.",
            "content_data": {"strengths": strengths or []},
        },
        {
            "id": "weaknesses",
            "label": "WEAKNESSES",
            "time_range": "5:45-6:30",
            "duration_sec": 45,
            "narration": _pick_intro(slug, SYR_WEAKNESS_INTROS),
            "text_on_screen": "WEAKNESSES",
            "visual": "Weaknesses list with warning visual treatment",
            "avatar_pose": "facepalm",
            "broll_sources": [],
            "music_bpm": BPM["tension"],
            "volume_db": VOLUME_DB["narration"],
            "cut_frequency_sec": CUT_FREQUENCY["long"],
            "editing_note": "MIDPOINT RE-ENGAGEMENT. This is ~55% through. "
                           "Open with burst sequence (quick cuts, warning sounds). "
                           "Then deliver weaknesses honestly. "
                           "Preview what's coming: 'Now, should you actually do this race?' "
                           "[RIFF HERE] at the transition.",
            "content_data": {"weaknesses": weaknesses or []},
            "meme_insert": {
                "timing": "~5:45",
                "trigger": "Midpoint re-engagement",
                "suggested_clip": "record_scratch or 'but wait' meme",
                "duration_sec": 1.5,
            },
        },
        {
            "id": "logistics",
            "label": "LOGISTICS",
            "time_range": "6:30-7:30",
            "duration_sec": 60,
            "narration": _pick_intro(slug, SYR_LOGISTICS_INTROS),
            "text_on_screen": "LOGISTICS",
            "visual": "Map + logistics card overlay",
            "avatar_pose": "presenting",
            "broll_sources": _get_broll_sources(rd, "logistics"),
            "music_bpm": BPM["calm"],
            "volume_db": VOLUME_DB["narration"],
            "cut_frequency_sec": CUT_FREQUENCY["long"],
            "editing_note": "Utility section. Lower energy, practical value. "
                           "Hybrid Tempo: alternate fast logistics items (10-15 sec) "
                           "with slow map visuals (30 sec).",
            "content_data": {"logistics": logistics_items},
        },
        {
            "id": "verdict",
            "label": "VERDICT",
            "time_range": "7:30-8:30",
            "duration_sec": 60,
            "narration": (
                f"Verdict: {verdict_label}. {should_you}"
            ),
            "text_on_screen": f"{verdict_label} — {score}/100",
            "visual": "Verdict badge + full scorecard summary",
            "avatar_pose": _pick_avatar("verdict", trope["name"], tier),
            "broll_sources": [],
            "music_bpm": BPM["reveal"],
            "volume_db": VOLUME_DB["burst"],
            "cut_frequency_sec": CUT_FREQUENCY["long"],
            "editing_note": "CLOSE THE MAIN LOOP. 0.5s silence before verdict. "
                           "Tier badge slams in. Avatar delivers final take. "
                           "DO NOT signal 'wrapping up' — maintain energy.",
        },
        {
            "id": "alternatives",
            "label": "ALTERNATIVES",
            "time_range": "8:30-9:15",
            "duration_sec": 45,
            "narration": f"If {name} isn't quite right for you. {alternatives}",
            "text_on_screen": "ALTERNATIVES",
            "visual": "Race cards for alternative races",
            "avatar_pose": "shrug",
            "broll_sources": [],
            "music_bpm": BPM["building"],
            "volume_db": VOLUME_DB["narration"],
            "cut_frequency_sec": CUT_FREQUENCY["long"],
            "editing_note": "Bonus value — viewers who reach this point are highly engaged. "
                           "Cross-reference other videos/races.",
        },
        {
            "id": "cta",
            "label": "CTA",
            "time_range": "9:15-9:45",
            "duration_sec": 30,
            "narration": (
                f"Full breakdown on the site. Fourteen scored dimensions. "
                f"Free race prep kit. Link in the description."
            ),
            "text_on_screen": f"gravelgodcycling.com/race/{slug}",
            "visual": "URL + engagement question + end screen",
            "avatar_pose": "pointing",
            "broll_sources": [],
            "music_bpm": BPM["building"],
            "volume_db": VOLUME_DB["transition"],
            "cut_frequency_sec": CUT_FREQUENCY["long"],
            "editing_note": "End ABRUPTLY after CTA. No 'thanks for watching' wind-down.",
            "engagement_question": (
                f"Have you raced {name}? Did we get the score right? "
                f"Drop it in the comments."
            ),
        },
    ]

    return _build_brief(
        slug=slug,
        format_name="should-you-race",
        platform="YouTube",
        duration_target=DURATION_TARGETS["should-you-race"],
        story_arc="promise → course → data-staircase → pro/con → verdict → alternatives",
        trope=trope,
        beats=beats,
        retention_targets=RETENTION_TARGETS["long"],
        thumbnail_prompt=_thumbnail_prompt(rd, trope, "should-you-race"),
        rd=rd,
    )


def brief_head_to_head(rd1, rd2):
    """Generate production brief for a head-to-head comparison (5-8 min)."""
    name1, name2 = rd1["name"], rd2["name"]
    slug1, slug2 = rd1["slug"], rd2["slug"]
    score1, score2 = rd1["overall_score"], rd2["overall_score"]
    tier1, tier2 = rd1["tier"], rd2["tier"]
    tn1 = TIER_NAMES.get(tier1, "Roster")
    tn2 = TIER_NAMES.get(tier2, "Roster")
    v1, v2 = rd1["vitals"], rd2["vitals"]

    # Rank dims by difference, take top 5
    all_diffs = []
    for dim in ALL_DIMS:
        s1 = rd1["explanations"][dim]["score"]
        s2 = rd2["explanations"][dim]["score"]
        all_diffs.append((dim, s1, s2, abs(s1 - s2)))
    all_diffs.sort(key=lambda x: x[3], reverse=True)
    top_diffs = [d for d in all_diffs if d[3] >= 1][:5]
    if len(top_diffs) < 3:
        top_diffs = all_diffs[:5]

    # Save the BIGGEST difference for last (escalation)
    top_diffs_reordered = top_diffs[1:] + [top_diffs[0]] if top_diffs else []

    # Determine winner by round wins (primary), then score (tiebreaker)
    wins1 = sum(1 for _, s1, s2, _ in top_diffs_reordered if s1 > s2)
    wins2 = sum(1 for _, s1, s2, _ in top_diffs_reordered if s2 > s1)
    if wins1 > wins2:
        winner, loser = name1, name2
    elif wins2 > wins1:
        winner, loser = name2, name1
    elif score1 > score2:
        winner, loser = name1, name2
    elif score2 > score1:
        winner, loser = name2, name1
    else:
        winner, loser = None, None
    winner_rounds = max(wins1, wins2)
    loser_rounds = min(wins1, wins2)

    # Build verdict narration with personality
    _h2h_hash = _stable_hash(f"{slug1}-{slug2}")
    if winner:
        _closer = H2H_WINNER_CLOSERS[_h2h_hash % len(H2H_WINNER_CLOSERS)]
        verdict_narration = (
            f"{winner} takes it. {winner_rounds} rounds to {loser_rounds}. "
            f"{score1 if winner == name1 else score2} out of 100 vs "
            f"{score2 if winner == name1 else score1}. {_closer}"
        )
    else:
        _closer = H2H_TIE_CLOSERS[_h2h_hash % len(H2H_TIE_CLOSERS)]
        verdict_narration = f"Dead heat. {wins1} rounds each. {_closer}"

    # Build dimension comparison beats
    dim_beats = []
    for i, (dim, s1, s2, delta) in enumerate(top_diffs_reordered):
        label = DIM_LABELS.get(dim, dim)
        adv = name1 if s1 > s2 else name2
        start_sec = 25 + (i * 50)
        end_sec = start_sec + 50

        dim_beats.append({
            "id": f"dim_{i+1}",
            "label": f"ROUND {i+1}: {label}",
            "time_range": f"{_fmt_time(start_sec)}-{_fmt_time(end_sec)}",
            "duration_sec": 50,
            "narration": _narrate_round(
                dim, s1, s2, name1, name2,
                f"{slug1}-{slug2}",
                is_finale=(i == len(top_diffs_reordered) - 1),
            ),
            "text_on_screen": f"{label}: {name1} {s1}/5 vs {name2} {s2}/5",
            "visual": "Split-screen score comparison",
            "avatar_pose": "thinking" if delta <= 1 else "mind_blown",
            "broll_sources": [],
            "music_bpm": BPM["tension"] if i < len(top_diffs_reordered) - 1 else BPM["reveal"],
            "volume_db": VOLUME_DB["narration"],
            "cut_frequency_sec": CUT_FREQUENCY["mid"],
            "editing_note": (
                f"Round {i+1} of {len(top_diffs_reordered)}. "
                f"{'BIGGEST GAP — save dramatic energy for this one. [RIFF HERE] after score reveal. ' if i == len(top_diffs_reordered)-1 else ''}"
                f"Split-screen: each race gets its score simultaneously. "
                f"Winner side gets a subtle glow/pulse."
            ),
            "comparison_data": {
                "dimension": label,
                name1: s1,
                name2: s2,
                "delta": delta,
                "advantage": adv,
            },
        })

    total_dim_sec = len(top_diffs_reordered) * 50
    verdict_start = 25 + total_dim_sec

    beats = [
        {
            "id": "hook",
            "label": "HOOK",
            "time_range": "0:00-0:10",
            "duration_sec": 10,
            "narration": (
                f"{name1} versus {name2}. "
                f"One entry fee. Two options. "
                f"Five rounds of data. Let's settle this."
            ),
            "text_on_screen": f"{name1} vs {name2}",
            "visual": "Split screen — both race logos/images",
            "avatar_pose": "versus",
            "broll_sources": [
                *_get_broll_sources(rd1, "hero"),
                *_get_broll_sources(rd2, "hero"),
            ],
            "music_bpm": BPM["tension"],
            "volume_db": VOLUME_DB["burst"],
            "cut_frequency_sec": CUT_FREQUENCY["mid"],
            "editing_note": "Boxing match energy. Split-screen slam. "
                           "Avatar in boxing stance. "
                           "IKEA EFFECT: 'Predict the winner before I reveal it.'",
            "psych_mechanism": "IKEA effect (prediction) + tribal identity (pick a side).",
        },
        {
            "id": "tale_of_tape",
            "label": "TALE OF THE TAPE",
            "time_range": "0:10-0:25",
            "duration_sec": 15,
            "narration": (
                f"{name1}. {v1['location']}. {v1['distance']}. {tn1}, {score1}/100. "
                f"{name2}. {v2['location']}. {v2['distance']}. {tn2}, {score2}/100."
            ),
            "text_on_screen": "TALE OF THE TAPE",
            "visual": "Side-by-side race stat cards",
            "avatar_pose": "presenting",
            "broll_sources": [],
            "music_bpm": BPM["building"],
            "volume_db": VOLUME_DB["narration"],
            "cut_frequency_sec": CUT_FREQUENCY["mid"],
            "editing_note": "Quick stats comparison. Establish both races before diving in.",
        },
        *dim_beats,
        {
            "id": "verdict",
            "label": "VERDICT",
            "time_range": f"{_fmt_time(verdict_start)}-{_fmt_time(verdict_start + 45)}",
            "duration_sec": 45,
            "narration": verdict_narration,
            "text_on_screen": f"WINNER: {winner or 'TIE'}",
            "visual": "Winner announcement + final score overlay",
            "avatar_pose": "excited" if winner else "shrug",
            "broll_sources": [],
            "music_bpm": BPM["reveal"],
            "volume_db": VOLUME_DB["burst"],
            "cut_frequency_sec": CUT_FREQUENCY["mid"],
            "editing_note": "SURPRISE WINNER technique: even if one was clearly better, "
                           "delay the reveal. Build through dimensions first. "
                           "[RIFF HERE] after verdict lands. "
                           "End ABRUPTLY after verdict.",
        },
        {
            "id": "cta",
            "label": "CTA",
            "time_range": f"{_fmt_time(verdict_start + 45)}-{_fmt_time(verdict_start + 60)}",
            "duration_sec": 15,
            "narration": "Full breakdowns for both on the site. Links in bio.",
            "text_on_screen": "gravelgodcycling.com",
            "visual": "URL overlay + engagement question",
            "avatar_pose": "pointing",
            "broll_sources": [],
            "music_bpm": BPM["building"],
            "volume_db": VOLUME_DB["transition"],
            "cut_frequency_sec": CUT_FREQUENCY["mid"],
            "engagement_question": "Which one are you picking? Drop it in the comments.",
        },
    ]

    combined_slug = f"{slug1}-vs-{slug2}"
    return _build_brief(
        slug=combined_slug,
        format_name="head-to-head",
        platform="All platforms",
        duration_target=DURATION_TARGETS["head-to-head"],
        story_arc="versus: tale-of-tape → round-by-round-escalation → verdict",
        trope={"name": "david_vs_goliath", "mechanism": "Prediction + tribal identity",
               "hook_text": f"{name1} vs {name2}", "strength": 7},
        beats=beats,
        retention_targets=RETENTION_TARGETS["mid"],
        thumbnail_prompt=(
            f"South Park style split screen, two cartoon cyclists facing off, "
            f"'{name1}' vs '{name2}' bold text, "
            f"boxing match energy --ar 16:9 --cref [CHARACTER_URL]"
        ),
        rd=rd1,
    )


# ── Helpers ───────────────────────────────────────────────────


def _fmt_time(seconds):
    """Format seconds to M:SS string."""
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _check_wpm(text, duration_sec):
    """Check if narration text is speakable in the given duration.

    Returns (wpm, is_feasible, severity).
    severity: 'ok', 'fast', 'too_fast', 'impossible'
    """
    words = len(text.split())
    if duration_sec <= 0:
        return (0, False, "impossible") if words > 0 else (0, True, "ok")
    wpm = (words / duration_sec) * 60
    if wpm <= WPM_COMFORTABLE:
        return wpm, True, "ok"
    if wpm <= WPM_FAST:
        return wpm, True, "fast"
    if wpm <= WPM_MAX:
        return wpm, True, "too_fast"
    return wpm, False, "impossible"


def _trim_narration(text, duration_sec, target_wpm=WPM_FAST):
    """Trim narration to fit within duration at target speaking rate.

    Removes trailing sentences until it fits. Returns trimmed text.
    """
    words = text.split()
    max_words = int((target_wpm / 60) * duration_sec)
    if len(words) <= max_words:
        return text
    # Trim to max_words, try to end at a sentence boundary
    trimmed = " ".join(words[:max_words])
    # Find last sentence-ending punctuation
    for i in range(len(trimmed) - 1, max(0, len(trimmed) - 20), -1):
        if trimmed[i] in ".!?":
            return trimmed[:i + 1]
    return trimmed + "."


def _pick_avatar(beat_type, trope_name, tier):
    """Select the best avatar reaction pose for a beat + trope combo."""
    if beat_type == "hook":
        mapping = {
            "underdog_reveal": "mind_blown",
            "expose": "skeptical",
            "david_vs_goliath": "versus",
            "prestige_override": "shocked",
            "gatekeeping_callout": "mustache_twirl",
            "hidden_gem": "excited",
        }
        return mapping.get(trope_name, "shocked")

    if beat_type == "reveal":
        if tier == 1:
            return "excited"
        elif tier == 2:
            return "thumbs_up"
        elif tier == 3:
            return "shrug"
        return "facepalm"

    if beat_type == "verdict":
        if tier <= 2:
            return "thumbs_up"
        return "thinking"

    return "presenting"


def _get_broll_sources(rd, context):
    """Generate B-roll sourcing queries from race data."""
    sources = []
    name = rd["name"]
    slug = rd["slug"]
    location = rd["vitals"]["location"]
    terrain_val = rd.get("terrain", {})
    if isinstance(terrain_val, dict):
        terrain = terrain_val.get("primary", "gravel")
    else:
        terrain = str(terrain_val) if terrain_val else "gravel"

    # RWGPS route map
    rwgps_id = rd["course"].get("ridewithgps_id")
    if rwgps_id:
        sources.append({
            "type": "rwgps",
            "id": rwgps_id,
            "url": f"https://ridewithgps.com/routes/{rwgps_id}",
            "use": "Route map overlay",
        })

    # Race website (only if it's actually a URL)
    official_site = rd["logistics"].get("official_site", "")
    if official_site and isinstance(official_site, str) and \
       official_site.startswith(("http://", "https://")):
        sources.append({
            "type": "race_website",
            "url": official_site,
            "use": "Hero image, branding reference",
        })

    # YouTube search queries based on context
    yt_queries = {
        "hero": [f"{name} gravel race", f"{name} cycling {date.today().year}"],
        "location": [f"{location} drone", f"{location} landscape"],
        "terrain": [f"{name} course preview", f"gravel cycling {terrain}"],
        "route": [f"{name} route map", f"{name} course walkthrough"],
        "marketing": [f"{name} official trailer", f"{name} promo video"],
        "positive": [f"{name} finish line", f"{name} race highlights"],
        "logistics": [f"{location} travel guide", f"{name} race day"],
    }
    for query in yt_queries.get(context, [f"{name} gravel race"]):
        sources.append({
            "type": "youtube_search",
            "query": query,
            "use": f"B-roll: {context}",
        })

    return sources


def _thumbnail_prompt(rd, trope, format_name=""):
    """Generate a Midjourney thumbnail prompt.

    Uses --ar 9:16 for Short formats, --ar 16:9 for long/mid-form.
    """
    name = rd["name"]
    tier = rd["tier"]
    tier_name = TIER_NAMES.get(tier, "Roster")
    trope_name = trope["name"]

    # Trope-specific visual direction
    visual_cues = {
        "underdog_reveal": "shocked expression, hidden gem sparkle effect",
        "expose": "skeptical squinting, red warning flags background",
        "david_vs_goliath": "boxing stance, David vs Goliath framing",
        "prestige_override": "confused face, question marks floating",
        "gatekeeping_callout": "crossed arms, velvet rope background",
        "hidden_gem": "excited pointing, treasure chest",
        "tier_reveal": "dramatic reveal pose, tier badge prominent",
    }
    cue = visual_cues.get(trope_name, "dramatic pose")

    # Short formats use vertical aspect ratio
    short_formats = ("tier-reveal", "suffering-map", "data-drops")
    aspect_ratio = "9:16" if format_name in short_formats else "16:9"

    return (
        f"South Park style flat cutout character, {cue}, "
        f"'{name}' bold text, tier badge '{tier_name.upper()}', "
        f"high contrast red/yellow/white, cycling gear, "
        f"handlebar mustache --ar {aspect_ratio} --cref [CHARACTER_URL]"
    )


def _build_brief(slug, format_name, platform, duration_target, story_arc,
                 trope, beats, retention_targets, thumbnail_prompt, rd):
    """Assemble the final production brief JSON."""
    # Calculate total narration words and validate WPM per beat
    total_words = 0
    wpm_warnings = []
    for beat in beats:
        narration = beat.get("narration", "")
        duration = beat.get("duration_sec", 0)
        words = len(narration.split())
        total_words += words

        if narration and duration > 0:
            wpm, feasible, severity = _check_wpm(narration, duration)
            beat["narration_wpm"] = round(wpm, 1)
            if severity in ("too_fast", "impossible"):
                warning = (
                    f"Beat '{beat.get('id', '?')}': {round(wpm)}WPM "
                    f"({words}w/{duration}s) — {severity}"
                )
                wpm_warnings.append(warning)
                beat["wpm_warning"] = warning

    # Collect all avatar assets needed
    avatar_assets = list({
        beat.get("avatar_pose", "presenting") for beat in beats
    })

    # Collect all meme inserts
    meme_inserts = [
        beat["meme_insert"] for beat in beats if "meme_insert" in beat
    ]

    # Total duration from beats
    total_duration = sum(beat.get("duration_sec", 0) for beat in beats)

    return {
        "slug": slug,
        "format": format_name,
        "platform": platform,
        "race_name": rd["name"],
        "race_tier": rd["tier"],
        "race_score": rd["overall_score"],
        "duration_target_range": list(duration_target),
        "estimated_duration_sec": total_duration,
        "estimated_spoken_words": total_words,
        "story_arc": story_arc,
        "primary_trope": {
            "name": trope["name"],
            "hook_text": trope.get("hook_text", ""),
            "mechanism": trope.get("mechanism", ""),
        },
        "retention_targets": retention_targets,
        "beats": beats,
        "avatar_assets_needed": sorted(avatar_assets),
        "meme_inserts": meme_inserts,
        "thumbnail_prompt": thumbnail_prompt,
        "narration_feasibility": {
            "total_words": total_words,
            "total_duration_sec": total_duration,
            "overall_wpm": round((total_words / max(total_duration, 1)) * 60, 1),
            "warnings": wpm_warnings,
            "feasible": len(wpm_warnings) == 0,
        },
        "content_pillars": _classify_pillar(format_name),
        "cross_platform_notes": _cross_platform_notes(format_name),
        "production_checklist": _production_checklist(format_name),
    }


def _classify_pillar(format_name):
    """Map format to content pillar strategy."""
    pillars = {
        "tier-reveal": "Tier List / Rankings (flagship, highest engagement)",
        "should-you-race": "Race Profiles (evergreen SEO content)",
        "head-to-head": "Comparisons (high shareability)",
        "roast": "Hot Takes / Controversy (debate-driven comments)",
        "suffering-map": "Data Visualization (authority-building)",
        "data-drops": "Stats & Facts (loop potential, high completion)",
    }
    return pillars.get(format_name, "General")


def _cross_platform_notes(format_name):
    """Platform-specific posting guidance."""
    if format_name in ("tier-reveal", "suffering-map", "data-drops"):
        return {
            "tiktok": "Post natively. Design for loop replay. Trending audio optional.",
            "instagram_reels": "Same cut. Add location tag for race area.",
            "youtube_shorts": "Same cut. Pin comment with link to full breakdown.",
            "twitter_x": "Post thumbnail still + hot take as tweet text.",
        }
    elif format_name in ("roast", "head-to-head"):
        return {
            "youtube": "Primary platform. Enable mid-roll ads if >8 min.",
            "extract_shorts": "Pull 3-5 Short clips from hot take moments within 48hrs.",
            "twitter_x": "Post the most controversial data point as a standalone take.",
            "instagram_reels": "Edit down to 60-90s highlight reel.",
        }
    else:  # should-you-race
        return {
            "youtube": "Primary platform. SEO-optimize title for '[Race Name] review'.",
            "extract_shorts": "Pull 3-5 Shorts: hook, biggest surprise score, verdict.",
            "blog": "Cross-reference the race profile page for search traffic.",
            "instagram_reels": "60-90s 'highlight reel' version.",
        }


def _production_checklist(format_name):
    """Per-format production checklist."""
    base = [
        "[ ] Avatar reaction poses generated (check avatar_assets_needed)",
        "[ ] B-roll sourced (check broll_sources in each beat)",
        "[ ] Music track selected (check BPM targets per beat)",
        "[ ] Text-on-screen prepped (check text_on_screen per beat)",
        "[ ] Captions/subtitles generated (MANDATORY — 15-25% retention boost)",
        "[ ] Thumbnail generated from thumbnail_prompt",
    ]

    if format_name in ("tier-reveal", "suffering-map", "data-drops"):
        base.append("[ ] Loop point tested (final frame → opening frame)")
        base.append("[ ] Test 3-second hold rate with fresh eyes")
    else:
        base.append("[ ] Mid-roll ad break positioned (if >8 min)")
        base.append("[ ] End screen cards configured")
        base.append("[ ] 3-5 Short clips extracted for cross-posting")

    return base


# ── CLI ───────────────────────────────────────────────────────


def write_brief(brief, output_dir):
    """Write a brief to JSON file."""
    fmt = brief["format"]
    slug = brief["slug"]
    out_path = Path(output_dir) / fmt / f"{slug}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(brief, f, indent=2, ensure_ascii=False)
    return out_path


def has_sufficient_data(rd, format_name):
    """Check if a race has enough data for a given format."""
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


def main():
    parser = argparse.ArgumentParser(
        description="Generate production video briefs from gravel race profiles."
    )
    parser.add_argument("slug", nargs="?", help="Race slug (e.g., unbound-200)")
    parser.add_argument(
        "--format",
        choices=FORMATS,
        help="Brief format to generate",
    )
    parser.add_argument("--all", action="store_true", help="Generate for all races")
    parser.add_argument("--top", type=int, help="Generate for top N races")
    parser.add_argument(
        "--head-to-head", nargs=2, metavar="SLUG",
        help="Compare two races head-to-head",
    )
    parser.add_argument("--data-dir", default=str(RACE_DATA_DIR))
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    modes = sum([
        bool(args.slug),
        args.all,
        bool(args.top),
        bool(args.head_to_head),
    ])
    if modes == 0:
        parser.error("Provide a slug, --all, --top N, or --head-to-head SLUG SLUG")
    if modes > 1:
        parser.error("Use only one mode at a time")

    # Head-to-head
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
        brief = brief_head_to_head(rd1, rd2)
        if args.dry_run:
            print(f"[DRY RUN] head-to-head: {slug1} vs {slug2}")
        else:
            path = write_brief(brief, args.output_dir)
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
    per_race_formats = ["tier-reveal", "should-you-race", "roast", "suffering-map"]
    if args.format:
        per_race_formats = [args.format]

    # Generate
    total = 0
    skipped = 0
    wpm_count = 0
    for slug in slugs:
        rd = load_race(slug, args.data_dir)
        if not rd:
            print(f"WARNING: Race not found: {slug}", file=sys.stderr)
            continue

        for fmt in per_race_formats:
            if fmt in ("head-to-head", "data-drops"):
                continue

            sufficient, reason = has_sufficient_data(rd, fmt)
            if not sufficient:
                skipped += 1
                if not (args.all or args.top):
                    print(f"  skipped {slug}/{fmt} ({reason})")
                continue

            if fmt == "tier-reveal":
                brief = brief_tier_reveal(rd)
            elif fmt == "should-you-race":
                brief = brief_should_you_race(rd)
            elif fmt == "roast":
                brief = brief_roast(rd)
            elif fmt == "suffering-map":
                brief = brief_suffering_map(rd)
                if brief is None:
                    skipped += 1
                    continue
            else:
                continue

            # Report WPM warnings
            wpm_warns = brief.get("narration_feasibility", {}).get("warnings", [])
            if wpm_warns:
                wpm_count += len(wpm_warns)
                if not (args.all or args.top):
                    for w in wpm_warns:
                        print(f"  WPM WARNING: {w}", file=sys.stderr)

            if args.dry_run:
                print(f"[DRY RUN] {fmt}: {slug}")
            else:
                path = write_brief(brief, args.output_dir)
                print(f"  wrote {path}")
            total += 1

    skip_msg = f", {skipped} skipped (insufficient data)" if skipped else ""
    wpm_msg = f", {wpm_count} WPM warnings" if wpm_count else ""
    if args.dry_run:
        print(f"\n{total} briefs would be generated{skip_msg}{wpm_msg}.")
    else:
        print(f"\n{total} briefs generated{skip_msg}{wpm_msg}.")


if __name__ == "__main__":
    main()
