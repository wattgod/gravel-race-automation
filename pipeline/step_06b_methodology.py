"""
Step 6b: Generate Internal Methodology Document

Produces methodology.json and methodology.md in the athlete directory.
Pure deterministic logic — reads from derived, profile, plan_config, and template metadata.
No AI. Every field uses if/elif logic against the derived data.

This document explains WHY the plan was built the way it was — for operator review
and athlete transparency.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def generate_methodology(
    profile: Dict,
    derived: Dict,
    plan_config: Dict,
    schedule: Dict,
    athlete_dir: Path,
):
    """Generate methodology.json and methodology.md in the athlete directory."""
    template = plan_config["template"]
    template_meta = template.get("plan_metadata", {})
    weeks = template.get("weeks", [])

    doc = {
        "athlete_summary": _athlete_summary(profile, derived, plan_config),
        "why_this_plan": _why_this_plan(profile, derived, plan_config),
        "template_selection": _template_selection(derived, plan_config, template_meta),
        "periodization": _periodization(derived, plan_config, weeks),
        "scaling": _scaling(derived, profile, template_meta),
        "accommodations": _accommodations(profile),
        "weekly_structure": _weekly_structure(schedule),
        "key_workouts_per_phase": _key_workouts_per_phase(derived),
        "generated_at": datetime.now().isoformat(),
    }

    # Write JSON
    with open(athlete_dir / "methodology.json", "w") as f:
        json.dump(doc, f, indent=2)

    # Write Markdown
    md = _render_markdown(doc)
    with open(athlete_dir / "methodology.md", "w") as f:
        f.write(md)

    return doc


# ── Section Builders ─────────────────────────────────────────


def _athlete_summary(profile: Dict, derived: Dict, plan_config: Dict) -> Dict:
    demographics = profile.get("demographics", {})
    primary_race = profile.get("primary_race", {})
    return {
        "name": profile.get("name", "Unknown"),
        "age": demographics.get("age"),
        "sex": demographics.get("sex"),
        "tier": derived.get("tier"),
        "level": derived.get("level"),
        "weekly_hours": derived.get("weekly_hours"),
        "target_event": f"{primary_race.get('name', 'Unknown')} {primary_race.get('distance_miles', '')}mi",
        "plan_duration_weeks": plan_config.get("plan_duration"),
        "plan_start": derived.get("plan_start_date"),
        "race_date": derived.get("race_date"),
    }


def _why_this_plan(profile: Dict, derived: Dict, plan_config: Dict) -> str:
    tier = derived.get("tier", "")
    level = derived.get("level", "")
    hours = derived.get("weekly_hours", "")
    age = profile.get("demographics", {}).get("age")
    race_distance = derived.get("race_distance_miles")
    injuries = profile.get("health", {}).get("injuries_limitations", "")

    reasons = []

    if level == "masters":
        reasons.append(
            f"Masters classification (age {age}) — recovery every 3 weeks, "
            f"HRV-guided intensity, mandatory strength training for bone density "
            f"and injury prevention."
        )
    elif age and age >= 40:
        reasons.append(
            f"Age {age} — recovery every 3 weeks for accelerated recovery needs."
        )

    if tier == "finisher":
        reasons.append(
            f"Finisher tier ({hours} hrs/week) — emphasizes completion over "
            f"competition. Builds durability, fueling confidence, and time-in-saddle."
        )
    elif tier == "compete":
        reasons.append(
            f"Compete tier ({hours} hrs/week) — balanced high-intensity and "
            f"endurance work targeting race-specific performance."
        )
    elif tier == "podium":
        reasons.append(
            f"Podium tier ({hours} hrs/week) — high-volume polarized approach "
            f"maximizing both aerobic base and top-end power."
        )
    elif tier == "time_crunched":
        reasons.append(
            f"Time-crunched tier ({hours} hrs/week) — threshold/sweet-spot focused "
            f"approach maximizing fitness gains per hour invested."
        )

    if race_distance and race_distance >= 80:
        reasons.append(
            f"Long-distance event ({race_distance}mi) — fueling practice and "
            f"mental durability are as important as fitness."
        )

    if injuries and injuries.lower() not in ("na", "none", "n/a", ""):
        # Only claim "accommodations applied" if there are actual exercise modifications
        # GI/reflux conditions affect nutrition guidance, not exercise selection
        _msk_keywords = ("knee", "chondromalacia", "patella", "acl", "mcl", "meniscus",
                         "back", "spine", "lumbar", "herniat", "disc", "l4", "l5", "sciatica",
                         "hip resurfac", "hip replac", "labral", "hip impingement",
                         "shoulder", "rotator", "wrist", "ankle")
        _gi_keywords = ("reflux", "gerd", "acid", "gi issue", "gastro", "ibs", "crohn")
        lower_injuries = injuries.lower()
        has_msk = any(kw in lower_injuries for kw in _msk_keywords)
        has_gi = any(kw in lower_injuries for kw in _gi_keywords)
        if has_msk:
            reasons.append(
                f"Injury accommodations applied — see accommodations section for "
                f"exercise modifications."
            )
        if has_gi:
            reasons.append(
                f"GI/nutrition accommodations applied — modified fueling guidance "
                f"in long ride and race day workouts."
            )

    if plan_config.get("extended"):
        reasons.append(
            f"Template extended from {plan_config.get('template', {}).get('plan_metadata', {}).get('base_weeks', 12)} "
            f"to {plan_config.get('plan_duration')} weeks to fill available lead time."
        )

    return " ".join(reasons) if reasons else "Standard plan configuration."


def _template_selection(derived: Dict, plan_config: Dict, template_meta: Dict) -> Dict:
    template_key = plan_config.get("template_key", "unknown")
    plan_duration = plan_config.get("plan_duration", 12)
    base_weeks = template_meta.get("base_weeks", 12)
    extended = plan_config.get("extended", False)

    rationale_parts = [
        f"{derived.get('tier', '').title()} tier",
        f"({derived.get('weekly_hours', '')} hrs/week)",
    ]
    if derived.get("level") == "masters":
        age = derived.get("age") or "50+"
        rationale_parts.append(f"+ Masters level (age {age}, 50+ override)")
    else:
        rationale_parts.append(f"+ {derived.get('level', '').title()} level")

    if extended:
        rationale_parts.append(
            f". Extended from {base_weeks} to {plan_duration} weeks to fill lead time."
        )

    return {
        "template_key": template_key,
        "base_weeks": base_weeks,
        "extended_to": plan_duration if extended else None,
        "rationale": " ".join(rationale_parts),
    }


def _periodization(derived: Dict, plan_config: Dict, weeks: List[Dict]) -> Dict:
    plan_duration = plan_config.get("plan_duration", 12)
    cadence = derived.get("recovery_week_cadence", 3)
    is_masters = derived.get("is_masters", False)

    # Detect recovery weeks from template
    # Include: weeks explicitly marked as recovery (focus text or cadence-enforced)
    # Exclude: taper/race weeks that have low volume but sharp intensity
    recovery_weeks = [
        w["week_number"] for w in weeks
        if (
            # Cadence-enforced recovery (focus set by extension logic)
            "recovery" in w.get("focus", "").lower()
        ) or (
            # Template recovery weeks (low volume, not taper/race)
            w.get("volume_percent", 100) <= 65
            and w["week_number"] <= plan_duration - 4
            and "taper" not in w.get("focus", "").lower()
            and "race" not in w.get("focus", "").lower()
        )
    ]

    # Determine phase boundaries
    base_end = int(plan_duration * 0.4)
    build_end = plan_duration - 2
    phases = [
        {
            "phase": "Base",
            "weeks": f"1-{base_end}",
            "focus": "Aerobic foundation, technique, strength",
        },
        {
            "phase": "Build",
            "weeks": f"{base_end + 1}-{build_end}",
            "focus": "Race-specific intensity, VO2max, threshold",
        },
        {
            "phase": "Peak/Taper",
            "weeks": f"{build_end + 1}-{plan_duration}",
            "focus": "Sharpening, volume reduction, race prep",
        },
    ]

    model = "Block periodization"
    if is_masters:
        model += f" with {cadence}-week recovery cadence (masters)"
    else:
        model += f" with {cadence}-week recovery cadence"

    cadence_rationale = (
        f"Every {cadence}{'rd' if cadence == 3 else 'th'} week for "
        f"{'40+ athletes (accelerated recovery needs)' if is_masters else 'standard recovery rhythm'}"
    )

    return {
        "model": model,
        "phases": phases,
        "recovery_weeks": recovery_weeks,
        "recovery_cadence": cadence,
        "rationale": cadence_rationale,
    }


def _scaling(derived: Dict, profile: Dict, template_meta: Dict) -> Dict:
    athlete_hours = derived.get("weekly_hours", "")
    template_hours = template_meta.get("target_hours", athlete_hours)
    longest_ride = profile.get("fitness", {}).get("longest_ride_hours", "")

    # Compute scale factor
    a_lo, a_hi = _parse_range(athlete_hours)
    t_lo, t_hi = _parse_range(template_hours)
    a_mid = (a_lo + a_hi) / 2
    t_mid = (t_lo + t_hi) / 2
    scale = max(0.4, min(1.0, a_mid / t_mid)) if t_mid > 0 else 1.0

    lr_lo, lr_hi = _parse_range(longest_ride) if longest_ride else (0, 0)

    rationale = (
        f"Athlete can ride {lr_lo}-{lr_hi} hours; "
        f"template designed for {t_lo}-{t_hi} hour athletes. "
        f"{scale:.2f}x scale brings all durations into range."
    ) if scale < 0.99 else "No scaling needed — athlete capacity matches template design."

    return {
        "duration_scale": round(scale, 2),
        "athlete_hours": athlete_hours,
        "template_hours": template_hours,
        "long_ride_cap_hours": lr_hi if lr_hi > 0 else None,
        "long_ride_floor_hours": max(1.0, lr_lo) if lr_lo > 0 else 1.0,
        "rationale": rationale,
    }


def _accommodations(profile: Dict) -> Dict:
    injuries = profile.get("health", {}).get("injuries_limitations", "")
    if not injuries or injuries.lower() in ("na", "none", "n/a", ""):
        injuries = "None reported"

    # Build strength modification notes from injuries
    strength_mods = []
    nutrition_mods = []
    injuries_lower = injuries.lower()
    if any(kw in injuries_lower for kw in ("knee", "chondromalacia", "patella", "acl", "mcl", "meniscus")):
        strength_mods.append(
            "Exercises modified: Bulgarian Split Squat → Wall Sit, "
            "Step-Ups → Glute Bridge, Heavy Squat → Light controlled-depth Goblet Squat. "
            "No full-depth squatting."
        )
    if any(kw in injuries_lower for kw in ("hip resurfac", "hip replac", "labral", "hip impingement")):
        strength_mods.append(
            "Exercises modified: Limited depth on all squats, "
            "Bulgarian Split Squat → Glute Bridge. No deep hip flexion under load."
        )
    if any(kw in injuries_lower for kw in ("back", "spine", "lumbar", "herniat", "disc", "l4", "l5", "sciatica")):
        strength_mods.append(
            "Exercises modified: Romanian Deadlift → Bird Dog, "
            "Barbell Squat → Light Goblet Squat, Farmer's Carry → Pallof Press. "
            "No heavy axial spinal loading."
        )
    if "shoulder" in injuries_lower:
        strength_mods.append("Modify upper body exercises for shoulder range of motion")
    if any(kw in injuries_lower for kw in ("reflux", "gerd", "acid", "gi issue", "gastro", "ibs", "crohn")):
        nutrition_mods.append(
            "GI-safe nutrition: 30-40g carbs/hour (not standard 60-80g), "
            "no caffeine, easily digestible foods only. Gradual gut training on long rides."
        )

    return {
        "injuries": injuries,
        "strength_modifications": "; ".join(strength_mods) if strength_mods else "None required",
        "nutrition_modifications": "; ".join(nutrition_mods) if nutrition_mods else "None required",
    }


def _weekly_structure(schedule: Dict) -> Dict:
    """Build weekly structure from athlete's schedule preferences.

    Note: This reflects the athlete's stated schedule preferences (off days,
    long ride days, interval days). Actual workout content varies by phase
    and week — recovery weeks replace intervals/long rides with easy rides,
    and template workouts may override default session types.
    """
    days = schedule.get("days", {})
    day_order = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    structure = {}
    for day in day_order:
        info = days.get(day, {"session": "rest"})
        structure[day] = info.get("session", "rest")
    structure["_note"] = (
        "This shows the athlete's preferred schedule. Actual workouts vary by phase: "
        "recovery weeks replace intervals/long rides with easy rides, "
        "and template workouts may adjust session types."
    )
    return structure


def _key_workouts_per_phase(derived: Dict) -> Dict:
    tier = derived.get("tier", "finisher")
    level = derived.get("level", "intermediate")

    base_workouts = ["Zone 2 Endurance", "Foundation Strength", "FTP Test"]
    build_workouts = ["Sweet Spot / Threshold", "VO2max Intervals", "Long Ride w/ Race Nutrition"]
    taper_workouts = ["Openers", "Short VO2max Sharpener", "Race Simulation"]

    if tier == "finisher":
        build_workouts = ["Sweet Spot", "Tempo Endurance", "Long Ride w/ Race Nutrition"]
    elif tier == "podium":
        build_workouts = ["VO2max Intervals", "Threshold Repeats", "Race Simulation Ride"]

    if level == "masters":
        base_workouts.append("Mandatory Recovery Week (every 3 weeks)")

    return {
        "base": base_workouts,
        "build": build_workouts,
        "taper": taper_workouts,
    }


# ── Markdown Renderer ────────────────────────────────────────


def _render_markdown(doc: Dict) -> str:
    lines = []
    a = doc["athlete_summary"]
    lines.append(f"# Training Plan Methodology — {a['name']}")
    lines.append("")
    lines.append(f"**Generated:** {doc['generated_at']}")
    lines.append("")

    # Athlete Summary
    lines.append("## Athlete Summary")
    lines.append("")
    lines.append(f"| Field | Value |")
    lines.append(f"|-------|-------|")
    for k, v in a.items():
        lines.append(f"| {k.replace('_', ' ').title()} | {v} |")
    lines.append("")

    # Why This Plan
    lines.append("## Why This Plan")
    lines.append("")
    lines.append(doc["why_this_plan"])
    lines.append("")

    # Template Selection
    ts = doc["template_selection"]
    lines.append("## Template Selection")
    lines.append("")
    lines.append(f"- **Template:** {ts['template_key']}")
    lines.append(f"- **Base weeks:** {ts['base_weeks']}")
    if ts.get("extended_to"):
        lines.append(f"- **Extended to:** {ts['extended_to']} weeks")
    lines.append(f"- **Rationale:** {ts['rationale']}")
    lines.append("")

    # Periodization
    p = doc["periodization"]
    lines.append("## Periodization")
    lines.append("")
    lines.append(f"**Model:** {p['model']}")
    lines.append("")
    lines.append("| Phase | Weeks | Focus |")
    lines.append("|-------|-------|-------|")
    for phase in p["phases"]:
        lines.append(f"| {phase['phase']} | {phase['weeks']} | {phase['focus']} |")
    lines.append("")
    lines.append(f"**Recovery weeks:** {', '.join(f'W{w}' for w in p['recovery_weeks'])}")
    lines.append(f"**Recovery cadence:** Every {p['recovery_cadence']} weeks")
    lines.append(f"**Rationale:** {p['rationale']}")
    lines.append("")

    # Scaling
    s = doc["scaling"]
    lines.append("## Duration Scaling")
    lines.append("")
    lines.append(f"- **Scale factor:** {s['duration_scale']}x")
    lines.append(f"- **Athlete hours:** {s['athlete_hours']}")
    lines.append(f"- **Template hours:** {s['template_hours']}")
    if s.get("long_ride_cap_hours"):
        lines.append(f"- **Long ride cap:** {s['long_ride_cap_hours']}h")
    lines.append(f"- **Long ride floor:** {s['long_ride_floor_hours']}h")
    lines.append(f"- **Rationale:** {s['rationale']}")
    lines.append("")

    # Accommodations
    acc = doc["accommodations"]
    lines.append("## Accommodations")
    lines.append("")
    lines.append(f"- **Injuries/Limitations:** {acc['injuries']}")
    lines.append(f"- **Strength modifications:** {acc['strength_modifications']}")
    lines.append(f"- **Nutrition modifications:** {acc.get('nutrition_modifications', 'None required')}")
    lines.append("")

    # Weekly Structure
    ws = doc["weekly_structure"]
    lines.append("## Weekly Structure")
    lines.append("")
    if ws.get("_note"):
        lines.append(f"*{ws['_note']}*")
        lines.append("")
    lines.append("| Day | Session |")
    lines.append("|-----|---------|")
    for day, session in ws.items():
        if day.startswith("_"):
            continue
        lines.append(f"| {day.title()} | {session.replace('_', ' ').title()} |")
    lines.append("")

    # Key Workouts
    kw = doc["key_workouts_per_phase"]
    lines.append("## Key Workouts Per Phase")
    lines.append("")
    for phase, workouts in kw.items():
        lines.append(f"### {phase.title()}")
        for w in workouts:
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines) + "\n"


# ── Helpers ──────────────────────────────────────────────────


def _parse_range(val: str):
    """Parse '5-7' → (5.0, 7.0), '15+' → (15.0, 20.0)."""
    if not val:
        return (0.0, 0.0)
    val = str(val).strip()
    if val.endswith("+"):
        lo = float(val[:-1])
        return (lo, lo + 5.0)
    if "-" in val:
        parts = val.split("-", 1)
        return (float(parts[0]), float(parts[1]))
    try:
        v = float(val)
        return (v, v)
    except ValueError:
        return (0.0, 0.0)
