"""Handbook charts, rebuilt: chapters 1 and 2 (poster panels).

Exports RENDERERS (asset_id -> render(block) -> html), CSS and JS.
All selectors are prefixed .gg-ig-a- so groups cannot clash.
"""
import html as _html
import json
from pathlib import Path

RACE_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "race-data"


def _e(text) -> str:
    """HTML-escape any value. 0 prints as 0."""
    return _html.escape(str(text))


def _panel(kind: str, tone: str, eyebrow: str, title: str, big: str, big_cap: str,
           body: str, block: dict, extra_cls: str = "") -> str:
    """One poster panel: dark header band, loud number, visual, caption."""
    caption = block.get("caption", "")
    cap = f'<div class="gg-ig-a__cap">{_e(caption)}</div>' if caption else ""
    alt = block.get("alt", "")
    aria = f' aria-label="{_e(alt)}"' if alt else ""
    cls = f"gg-ig-a gg-ig-a--{tone} gg-ig-a-{kind}"
    if extra_cls:
        cls += f" {extra_cls}"
    return (
        f'<figure class="{cls}" role="figure"{aria}>'
        f'<div class="gg-ig-a__head">'
        f'<div class="gg-ig-a__eyebrow">{_e(eyebrow)}</div>'
        f'<div class="gg-ig-a__title">{_e(title)}</div>'
        f'</div>'
        f'<div class="gg-ig-a__hero">'
        f'<span class="gg-ig-a__big">{_e(big)}</span>'
        f'<span class="gg-ig-a__bigcap">{_e(big_cap)}</span>'
        f'</div>'
        f'<div class="gg-ig-a__body">{body}{cap}</div>'
        f'</figure>'
    )


# ── CH1 · gear essentials ───────────────────────────────────

GEAR_ITEMS = [
    ("Bike Frame", "Your foundation. Gravel-specific geometry, tire clearance, and mounting points.",
     "Look for 45mm+ tire clearance and multiple bottle mounts"),
    ("Tires", "The single biggest performance variable. 40-50mm for most courses.",
     "Run 38-42mm for fast courses, 45-50mm for chunky terrain"),
    ("Helmet", "Non-negotiable safety. MIPS preferred. Ventilation matters for long days.",
     "MIPS or WaveCel for rotational impact protection"),
    ("Repair Kit", "Tubes/plugs, multi-tool, CO2. Practice repairs before race day.",
     "Carry both a tube and plugs — plugs fail on sidewall cuts"),
    ("Hydration", "Bottles or pack. Know your course's water availability.",
     "Two bottles minimum; pack for courses with 30+ mile gaps between aid"),
]


def render_gear_essentials(block: dict) -> str:
    cards = []
    for i, (name, desc, tip) in enumerate(GEAR_ITEMS, start=1):
        cards.append(
            f'<div class="gg-ig-a-ge__card">'
            f'<div class="gg-ig-a-ge__top">'
            f'<span class="gg-ig-a-ge__num">{i:02d}</span>'
            f'<span class="gg-ig-a-ge__name">{_e(name)}</span>'
            f'</div>'
            f'<div class="gg-ig-a-ge__desc">{_e(desc)}</div>'
            f'<div class="gg-ig-a-ge__tip">'
            f'<span class="gg-ig-a-ge__tiplabel">Tip</span>'
            f'<span>{_e(tip)}</span>'
            f'</div>'
            f'</div>'
        )
    body = f'<div class="gg-ig-a-ge__grid">{"".join(cards)}</div>'
    return _panel("ge", "light", "CH 1 · GEAR", "Essential Gear for Race Day",
                  str(len(GEAR_ITEMS)), "things you actually need", body, block)


# ── CH1 · rider grid ────────────────────────────────────────

RIDERS = [
    {"name": "Ayahuasca", "hours": "3-5 hrs/wk", "ftp_range": "100-160W", "ftp_pct": 25,
     "goal": "Finish upright", "reality": "Survival mode", "tier": "T4",
     "detail": "First-timers and casual riders. Focus on completing the distance, "
               "not competing. Build slowly with 3-4 rides per week."},
    {"name": "Finisher", "hours": "5-8 hrs/wk", "ftp_range": "160-220W", "ftp_pct": 50,
     "goal": "Finish strong", "reality": "Solid mid-pack", "tier": "T3-T4",
     "detail": "The biggest category. Consistent training pays off — "
               "structured intervals 2x/week plus one long ride builds real fitness."},
    {"name": "Competitor", "hours": "8-12 hrs/wk", "ftp_range": "220-280W", "ftp_pct": 75,
     "goal": "Top 25%", "reality": "Age group podium", "tier": "T2-T3",
     "detail": "Serious athletes balancing training with life. Periodized plans, "
               "race-specific prep, and dialed nutrition separate you from finishers."},
    {"name": "Podium", "hours": "12-20 hrs/wk", "ftp_range": "280-400W", "ftp_pct": 100,
     "goal": "Win or podium", "reality": "Elite-level prep", "tier": "T1",
     "detail": "Full commitment. Double days, altitude camps, race recon. "
               "Every marginal gain matters when the field is this deep."},
]


def render_rider_grid(block: dict) -> str:
    cards = []
    for r in RIDERS:
        flag = (
            '<span class="gg-ig-a-rg__flag">Biggest group</span>'
            if r["name"] == "Finisher" else ""
        )
        cards.append(
            f'<div class="gg-ig-a-rg__card">'
            f'<div class="gg-ig-a-rg__top">'
            f'<div class="gg-ig-a-rg__name">{_e(r["name"])}</div>{flag}'
            f'<div class="gg-ig-a-rg__hours">{_e(r["hours"])}</div>'
            f'<div class="gg-ig-a-rg__bar" aria-hidden="true">'
            f'<span style="width:{int(r["ftp_pct"])}%"></span></div>'
            f'<div class="gg-ig-a-rg__ftp"><span class="gg-ig-a-rg__ftplabel">FTP</span>'
            f'<span>{_e(r["ftp_range"])}</span></div>'
            f'</div>'
            f'<dl class="gg-ig-a-rg__facts">'
            f'<div><dt>Goal</dt><dd>{_e(r["goal"])}</dd></div>'
            f'<div><dt>Reality</dt><dd>{_e(r["reality"])}</dd></div>'
            f'<div><dt>Races</dt><dd>{_e(r["tier"])}</dd></div>'
            f'</dl>'
            f'<div class="gg-ig-a-rg__detail">{_e(r["detail"])}</div>'
            f'</div>'
        )
    body = f'<div class="gg-ig-a-rg__grid">{"".join(cards)}</div>'
    return _panel("rg", "dark", "CH 1 · RIDERS", "Four Rider Archetypes",
                  "3–20", "hours a week across four profiles", body, block)


# ── CH1 · hierarchy of speed ────────────────────────────────

HIERARCHY = [
    ("Fitness", "70%", 70.0, "+50W FTP = ~2mph faster. Train more, spend less."),
    ("Pacing", "20%", 20.0, "Even pacing beats heroic surges. Discipline > talent."),
    ("Nutrition", "8%", 8.0, "Proper fueling prevents bonking — worth 30+ min in long races."),
    ("Bike Handling", "1.5%", 1.5, "Cornering, descending, loose-surface skills save minutes."),
    ("Equipment", "0.5%", 0.5, "Marginal gains: lighter wheels, aero bars. Matters least."),
]


def render_hierarchy(block: dict) -> str:
    top = max(h[2] for h in HIERARCHY)
    rows = []
    for i, (label, pct, val, tip) in enumerate(HIERARCHY):
        w = max(val / top * 100.0, 1.2)
        hot = " is-top" if i == 0 else ""
        rows.append(
            f'<li class="gg-ig-a-hs__row{hot}">'
            f'<span class="gg-ig-a-hs__label">{_e(label)}</span>'
            f'<span class="gg-ig-a-hs__track" aria-hidden="true">'
            f'<span class="gg-ig-a-hs__fill" style="width:{w:.1f}%"></span></span>'
            f'<span class="gg-ig-a-hs__val">{_e(pct)}</span>'
            f'<span class="gg-ig-a-hs__tip">{_e(tip)}</span>'
            f'</li>'
        )
    body = f'<ol class="gg-ig-a-hs__list">{"".join(rows)}</ol>'
    return _panel("hs", "light", "CH 1 · SPEED",
                  "The Hierarchy of Speed: What Actually Makes You Faster",
                  "70%", "of your speed is fitness", body, block)


# ── CH1 · gear weight (toggles) ─────────────────────────────

GEAR_WEIGHT = [
    ("Frame", "Gravel bike frame", 8.5, True,
     "Carbon: 7.5-8.5 kg, Alloy: 9-10.5 kg, Steel: 10-12 kg"),
    ("Wheels", "Wheelset", 1.8, True,
     "Carbon: 1.3-1.6 kg, Alloy: 1.7-2.1 kg. Biggest speed gain per gram."),
    ("Tires", "40-50mm gravel tires", 0.7, True,
     "Lighter tires roll faster but puncture more. Run tubeless always."),
    ("Hydration", "2 bottles + cage", 1.5, True,
     "2 bottles = 1.5 kg water + cage. Pack adds 0.5 kg but carries more."),
    ("Repair Kit", "Tubes, plugs, CO2, tool", 0.5, True,
     "Minimum: tube, plugs, CO2, multi-tool, tire lever = 0.5 kg"),
    ("Nutrition", "8hr race fuel", 0.8, True,
     "24 gels = ~0.8 kg. Don’t cut fuel to save weight — bonking costs more."),
    ("Electronics", "GPS, lights, sensors", 0.3, True,
     "GPS head unit + sensors. Lights for early-morning starts."),
    ("Aero Bars", "Clip-on extensions", 0.4, False,
     "Legal at most gravel events. Saves watts on flat/wind sections."),
]


def render_gear_weight(block: dict) -> str:
    total = sum(w for _, _, w, on, _ in GEAR_WEIGHT if on)
    heaviest = max(w for _, _, w, _, _ in GEAR_WEIGHT)
    rows = []
    for name, desc, weight, on, tip in GEAR_WEIGHT:
        state = "on" if on else "off"
        rows.append(
            f'<li class="gg-ig-a-gw__li">'
            f'<button type="button" class="gg-ig-a-gw__item is-{state}"'
            f' data-weight="{weight}" aria-pressed="{"true" if on else "false"}">'
            f'<span class="gg-ig-a-gw__check" aria-hidden="true"></span>'
            f'<span class="gg-ig-a-gw__what">'
            f'<span class="gg-ig-a-gw__name">{_e(name)}</span>'
            f'<span class="gg-ig-a-gw__desc">{_e(desc)}</span>'
            f'</span>'
            f'<span class="gg-ig-a-gw__bar" aria-hidden="true">'
            f'<span style="width:{weight / heaviest * 100:.1f}%"></span></span>'
            f'<span class="gg-ig-a-gw__kg">{weight:.1f}<small> kg</small></span>'
            f'</button>'
            f'<div class="gg-ig-a-gw__tip">{_e(tip)}</div>'
            f'</li>'
        )
    body = f'<ul class="gg-ig-a-gw__list">{"".join(rows)}</ul>'
    out = _panel("gw", "dark", "CH 1 · WEIGHT",
                 "Gear Weight Budget: Where Every Gram Goes",
                 f"{total:.1f}", "kg total — tap a part to add or drop it", body, block)
    # live total: mark the number so the script can update it and announce it
    return out.replace(
        f'<span class="gg-ig-a__big">{total:.1f}</span>',
        f'<span class="gg-ig-a__big gg-ig-a-gw__total" role="status" aria-live="polite">{total:.1f}</span>',
        1,
    )


# ── CH2 · scoring dimensions ────────────────────────────────

DIM_KEYS = [
    ("Logistics", "logistics"), ("Length", "length"),
    ("Technicality", "technicality"), ("Elevation", "elevation"),
    ("Climate", "climate"), ("Altitude", "altitude"),
    ("Adventure", "adventure"), ("Prestige", "prestige"),
    ("Race Quality", "race_quality"), ("Experience", "experience"),
    ("Community", "community"), ("Field Depth", "field_depth"),
    ("Value", "value"), ("Expenses", "expenses"),
]
DIM_TIPS = {
    "Logistics": "Travel complexity, registration difficulty, permit requirements",
    "Length": "Total race distance — longer races score higher",
    "Technicality": "Surface difficulty, navigation challenges, technical terrain",
    "Elevation": "Total climbing relative to distance",
    "Climate": "Heat, cold, wind, altitude exposure risks",
    "Altitude": "Maximum elevation and time spent above 5,000ft",
    "Adventure": "Remoteness, scenery, exploration factor",
    "Prestige": "Historical significance, brand recognition, media coverage",
    "Race Quality": "Organization, course marking, aid station quality",
    "Experience": "Overall rider experience, post-race atmosphere",
    "Community": "Local engagement, volunteer quality, spectator support",
    "Field Depth": "Pro presence, competitive depth, field size",
    "Value": "Registration cost relative to what you get",
    "Expenses": "Total trip cost: travel, lodging, gear requirements",
}
_UNBOUND_FALLBACK = {
    "logistics": 4, "length": 5, "technicality": 3, "elevation": 3,
    "climate": 5, "altitude": 1, "adventure": 5, "prestige": 5,
    "race_quality": 5, "experience": 5, "community": 5,
    "field_depth": 5, "value": 3, "expenses": 2,
}
_RACE_SCORES = {
    "mid-south-100": [3, 4, 3, 2, 4, 1, 3, 4, 5, 5, 5, 4, 4, 3],
    "leadville-100": [4, 5, 4, 5, 4, 5, 5, 5, 4, 5, 4, 4, 3, 2],
}


def _unbound_scores() -> list:
    rating = dict(_UNBOUND_FALLBACK)
    path = RACE_DATA_DIR / "unbound-200.json"
    try:
        rating = json.loads(path.read_text(encoding="utf-8"))["race"]["gravel_god_rating"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    out = []
    for _label, key in DIM_KEYS:
        try:
            v = int(rating.get(key, 0))
        except (TypeError, ValueError):
            v = 0
        out.append(max(0, min(5, v)))
    return out


def render_scoring_dimensions(block: dict) -> str:
    unbound = _unbound_scores()
    races = [
        ("unbound-200", "Unbound 200", unbound),
        ("mid-south-100", "Mid South", _RACE_SCORES["mid-south-100"]),
        ("leadville-100", "Leadville", _RACE_SCORES["leadville-100"]),
    ]
    toggles = []
    for i, (rid, label, scores) in enumerate(races):
        pressed = "true" if i == 0 else "false"
        toggles.append(
            f'<button type="button" class="gg-ig-a-sd__race" aria-pressed="{pressed}"'
            f' data-race="{_e(rid)}"'
            f' data-scores="{_e(",".join(str(s) for s in scores))}">{_e(label)}</button>'
        )
    rows = []
    for i, (label, _key) in enumerate(DIM_KEYS):
        score = unbound[i]
        pips = "".join(
            f'<span class="gg-ig-a-sd__pip{" is-on" if p < score else ""}"></span>'
            for p in range(5)
        )
        rows.append(
            f'<li class="gg-ig-a-sd__row">'
            f'<span class="gg-ig-a-sd__label">{_e(label)}</span>'
            f'<span class="gg-ig-a-sd__pips" aria-hidden="true">{pips}</span>'
            f'<span class="gg-ig-a-sd__val">{score}<small>/5</small></span>'
            f'<span class="gg-ig-a-sd__tip">{_e(DIM_TIPS.get(label, ""))}</span>'
            f'</li>'
        )
    body = (
        f'<div class="gg-ig-a-sd__toggles" role="group" aria-label="Compare races">'
        f'{"".join(toggles)}</div>'
        f'<ol class="gg-ig-a-sd__list">{"".join(rows)}</ol>'
    )
    return _panel("sd", "light", "CH 2 · SCORING", "Inside the Rating: 14 Scoring Dimensions",
                  str(len(DIM_KEYS)), "dimensions, each scored 1 to 5", body, block)


# ── CH2 · tier distribution ─────────────────────────────────

TIERS = [
    ("T1", 25, 8, "Unbound, BWR, Leadville — the bucket-list events"),
    ("T2", 73, 22, "SBT GRVL, Gravel Worlds, Mid South — strong fields, great courses"),
    ("T3", 154, 47, "Regional favorites with solid organization and community"),
    ("T4", 76, 23, "Local or niche events — great entry points for beginners"),
]


def render_tier_distribution(block: dict) -> str:
    total = sum(t[1] for t in TIERS)
    top = max(t[1] for t in TIERS)
    rows = []
    for label, count, pct, tip in TIERS:
        hot = " is-top" if label == "T1" else ""
        rows.append(
            f'<li class="gg-ig-a-td__row{hot}">'
            f'<span class="gg-ig-a-td__tier">{_e(label)}</span>'
            f'<span class="gg-ig-a-td__track" aria-hidden="true">'
            f'<span class="gg-ig-a-td__fill" style="width:{count / top * 100:.1f}%"></span></span>'
            f'<span class="gg-ig-a-td__num">{_e(count)}<small>{_e(pct)}%</small></span>'
            f'<span class="gg-ig-a-td__tip">{_e(tip)}</span>'
            f'</li>'
        )
    body = f'<ol class="gg-ig-a-td__list">{"".join(rows)}</ol>'
    return _panel("td", "dark", "CH 2 · TIERS", "How We Tier 328 Gravel Races",
                  str(total), "gravel races in four tiers", body, block)


# ── CH2 · course profile ────────────────────────────────────

# (mile, elevation_ft, gradient%)
PROFILE = [
    (0, 1200, 0), (5, 1350, 3), (10, 1800, 9), (15, 2200, 8),
    (20, 1900, -6), (25, 1600, -6), (30, 1700, 2), (35, 2400, 14),
    (40, 2800, 8), (45, 2500, -6), (50, 2100, -8), (55, 1800, -6),
    (60, 1400, -8), (65, 1500, 2), (70, 1800, 6), (75, 2000, 4),
    (80, 1600, -8), (85, 1300, -6), (90, 1200, -2), (95, 1250, 1),
    (100, 1200, -1),
]
_CP_LO, _CP_HI = 1000, 3000
_CP_CLASSES = [
    ("flat", "Flat", "under 3%"),
    ("mod", "Moderate", "3-6%"),
    ("steep", "Steep", "6-10%"),
    ("brutal", "Brutal", "10%+"),
]


def _cp_class(grad: int) -> str:
    g = abs(grad)
    if g >= 10:
        return "brutal"
    if g >= 6:
        return "steep"
    if g >= 3:
        return "mod"
    return "flat"


def render_course_profile(block: dict) -> str:
    max_mile = PROFILE[-1][0]
    span = _CP_HI - _CP_LO

    def xy(mile, elev):
        return mile / max_mile * 1000.0, 400.0 - (elev - _CP_LO) / span * 400.0

    polys = []
    miles_by = {k: 0 for k, _, _ in _CP_CLASSES}
    for i in range(len(PROFILE) - 1):
        m1, e1, _g1 = PROFILE[i]
        m2, e2, g2 = PROFILE[i + 1]
        cls = _cp_class(g2)
        miles_by[cls] += m2 - m1
        x1, y1 = xy(m1, e1)
        x2, y2 = xy(m2, e2)
        polys.append(
            f'<polygon class="gg-ig-a-cp__seg gg-ig-a-cp__seg--{cls}"'
            f' points="{x1:.1f},400 {x1:.1f},{y1:.1f} {x2:.1f},{y2:.1f} {x2:.1f},400"/>'
        )
    line_pts = " ".join(f"{xy(m, e)[0]:.1f},{xy(m, e)[1]:.1f}" for m, e, _ in PROFILE)

    yl = []
    for elev in range(_CP_LO, _CP_HI + 1, 500):
        pct = (elev - _CP_LO) / span * 100
        yl.append(
            f'<span class="gg-ig-a-cp__ytick" style="bottom:{pct:.1f}%">{elev:,}</span>'
        )
    grid = []
    for elev in range(_CP_LO + 500, _CP_HI, 500):
        pct = (elev - _CP_LO) / span * 100
        grid.append(f'<span class="gg-ig-a-cp__gridline" style="bottom:{pct:.1f}%"></span>')
    xl = []
    for mile in range(0, max_mile + 1, 20):
        xl.append(
            f'<span class="gg-ig-a-cp__xtick" style="left:{mile / max_mile * 100:.1f}%">{mile}</span>'
        )

    peak = max(PROFILE, key=lambda p: p[1])
    peak_x = peak[0] / max_mile * 100
    peak_y = (peak[1] - _CP_LO) / span * 100
    brutal = [(PROFILE[i], PROFILE[i + 1]) for i in range(len(PROFILE) - 1)
              if _cp_class(PROFILE[i + 1][2]) == "brutal"]
    marks = [
        f'<span class="gg-ig-a-cp__mark" style="left:{peak_x:.1f}%;bottom:{peak_y:.1f}%">'
        f'{peak[1]:,} ft</span>'
    ]
    for a, b in brutal:
        mid = (a[0] + b[0]) / 2 / max_mile * 100
        ey = (max(a[1], b[1]) - _CP_LO) / span * 100
        marks.append(
            f'<span class="gg-ig-a-cp__mark gg-ig-a-cp__mark--l gg-ig-a-cp__mark--hot"'
            f' style="left:{mid:.1f}%;bottom:{ey:.1f}%">{abs(b[2])}% grade</span>'
        )

    legend = "".join(
        f'<li class="gg-ig-a-cp__key"><span class="gg-ig-a-cp__sw gg-ig-a-cp__seg--{k}"></span>'
        f'<span class="gg-ig-a-cp__keytxt"><b>{_e(name)}</b> {_e(rng)}</span>'
        f'<span class="gg-ig-a-cp__miles">{miles_by[k]} mi</span></li>'
        for k, name, rng in _CP_CLASSES
    )
    body = (
        f'<div class="gg-ig-a-cp__chart" role="img"'
        f' aria-label="Elevation profile over {max_mile} miles from {PROFILE[0][1]:,} ft,'
        f' peaking at {peak[1]:,} ft near mile {peak[0]}, coloured by gradient">'
        f'<span class="gg-ig-a-cp__ylabel" aria-hidden="true">ft</span>'
        f'<div class="gg-ig-a-cp__plot" aria-hidden="true">'
        f'{"".join(grid)}'
        f'<svg class="gg-ig-a-cp__svg" viewBox="0 0 1000 400" preserveAspectRatio="none"'
        f' focusable="false" aria-hidden="true">{"".join(polys)}'
        f'<polyline class="gg-ig-a-cp__line" points="{line_pts}"/></svg>'
        f'{"".join(marks)}{"".join(yl)}{"".join(xl)}'
        f'<span class="gg-ig-a-cp__xlabel">miles</span>'
        f'</div></div>'
        f'<ul class="gg-ig-a-cp__legend">{legend}</ul>'
    )
    return _panel("cp", "light", "CH 2 · COURSE",
                  "Reading the Course Profile: Gradient by Segment",
                  f"{max_mile} MI", f"from {PROFILE[0][1]:,} to {peak[1]:,} ft, colored by gradient",
                  body, block)


# ── CH2 · field scatter ─────────────────────────────────────

# (name, field_size, median_hrs, tier)
SCATTER = [
    ("Unbound 200", 4000, 12.5, "T1"), ("BWR", 1200, 7.5, "T1"),
    ("Leadville", 2500, 10.0, "T1"), ("SBT GRVL", 3500, 6.0, "T1"),
    ("Mid South", 3000, 5.5, "T2"), ("Gravel Worlds", 800, 11.0, "T2"),
    ("Steamboat", 2000, 7.0, "T2"), ("The Rift", 600, 8.5, "T2"),
    ("Rooted VT", 500, 6.5, "T3"), ("Grasshopper", 300, 5.0, "T3"),
    ("Rule of 3", 400, 8.0, "T3"), ("Ochoco", 200, 9.0, "T3"),
    ("Local Gravel", 100, 4.0, "T4"), ("County Gravel", 150, 5.5, "T4"),
    ("Backroads 50", 80, 3.5, "T4"), ("Farm Gravel", 120, 4.5, "T4"),
]
_FS_MAX_FIELD = 4500
_FS_MAX_HRS = 14


def render_field_scatter(block: dict) -> str:
    marks = []
    for name, field, hrs, tier in SCATTER:
        x = field / _FS_MAX_FIELD * 100
        y = hrs / _FS_MAX_HRS * 100
        label = ""
        if tier == "T1":
            side = " gg-ig-a-fs__name--r" if x > 60 else ""
            label = f'<span class="gg-ig-a-fs__name{side}">{_e(name)}</span>'
        marks.append(
            f'<span class="gg-ig-a-fs__pt gg-ig-a-fs__pt--{_e(tier.lower())}"'
            f' style="left:{x:.1f}%;bottom:{y:.1f}%">{_e(tier[1:])}{label}</span>'
        )
    grid = []
    yt = []
    for hrs in range(0, _FS_MAX_HRS + 1, 2):
        pct = hrs / _FS_MAX_HRS * 100
        if hrs:
            grid.append(f'<span class="gg-ig-a-fs__hline" style="bottom:{pct:.1f}%"></span>')
        if hrs % 4 == 0:
            yt.append(f'<span class="gg-ig-a-fs__ytick" style="bottom:{pct:.1f}%">{hrs}h</span>')
    xt = []
    for field in range(0, _FS_MAX_FIELD, 1000):
        pct = field / _FS_MAX_FIELD * 100
        xt.append(f'<span class="gg-ig-a-fs__xtick" style="left:{pct:.1f}%">{field:,}</span>')

    groups = []
    for tier in ("T1", "T2", "T3", "T4"):
        items = "".join(
            f'<li><span class="gg-ig-a-fs__gname">{_e(n)}</span>'
            f'<span class="gg-ig-a-fs__gval">{f:,} · {h:g}h</span></li>'
            for n, f, h, t in SCATTER if t == tier
        )
        groups.append(
            f'<div class="gg-ig-a-fs__group gg-ig-a-fs__group--{tier.lower()}">'
            f'<div class="gg-ig-a-fs__ghead"><span class="gg-ig-a-fs__chip gg-ig-a-fs__pt--{tier.lower()}">'
            f'{tier[1:]}</span>Tier {tier[1:]}</div><ul>{items}</ul></div>'
        )
    body = (
        f'<div class="gg-ig-a-fs__chart" role="img"'
        f' aria-label="Scatter of field size against median finish time for {len(SCATTER)} races;'
        f' bigger fields and longer finishes are mostly tier 1, small fields and shorter finishes tier 4">'
        f'<div class="gg-ig-a-fs__plot" aria-hidden="true">{"".join(grid)}{"".join(marks)}'
        f'{"".join(yt)}{"".join(xt)}'
        f'<span class="gg-ig-a-fs__xlabel">field size (riders)</span>'
        f'<span class="gg-ig-a-fs__ylabel">median finish</span>'
        f'</div></div>'
        f'<div class="gg-ig-a-fs__groups">{"".join(groups)}</div>'
    )
    big = f"{max(s[1] for s in SCATTER):,}"
    small = min(s[1] for s in SCATTER)
    return _panel("fs", "dark", "CH 2 · FIELDS",
                  "Field Size vs. Race Duration: What You’re Getting Into",
                  big, f"riders at the biggest start. {small} at the smallest.", body, block)


# ── CH2 · race table ────────────────────────────────────────

TABLE_HEADERS = ["Race", "Tier", "Distance", "Elevation", "Score", "Field"]
TABLE_ROWS = [
    ["Unbound 200", "T1", "200 mi", "11,000 ft", "94", "4,000"],
    ["Belgian Waffle Ride", "T1", "137 mi", "10,800 ft", "92", "1,200"],
    ["Leadville 100", "T1", "100 mi", "12,600 ft", "90", "2,500"],
    ["SBT GRVL", "T1", "141 mi", "9,400 ft", "88", "3,500"],
    ["Mid South 100", "T2", "100 mi", "4,800 ft", "78", "3,000"],
    ["Gravel Worlds", "T2", "150 mi", "8,200 ft", "76", "800"],
    ["Steamboat Gravel", "T2", "140 mi", "8,800 ft", "72", "2,000"],
    ["Rooted Vermont", "T3", "90 mi", "7,500 ft", "62", "500"],
    ["Grasshopper", "T3", "65 mi", "6,200 ft", "55", "300"],
    ["Rule of Three", "T3", "120 mi", "6,800 ft", "52", "400"],
]
# default direction when a sort chip is first pressed: asc for text/tier, desc for numbers
_TABLE_DIR = ["asc", "asc", "desc", "desc", "desc", "desc"]


def _num(text) -> int:
    digits = "".join(ch for ch in str(text) if ch.isdigit())
    return int(digits) if digits else 0


def render_race_table(block: dict) -> str:
    chips = []
    for i, h in enumerate(TABLE_HEADERS):
        active = h == "Score"
        chips.append(
            f'<button type="button" class="gg-ig-a-rt__chip" data-col="{i}"'
            f' data-dir="{_TABLE_DIR[i]}" aria-pressed="{"true" if active else "false"}">'
            f'{_e(h)}<span class="gg-ig-a-rt__arrow" aria-hidden="true">'
            f'{"↓" if active else ""}</span></button>'
        )
    th = "".join(
        f'<th scope="col" data-col="{i}"'
        f'{" aria-sort=\"descending\"" if h == "Score" else ""}>{_e(h)}</th>'
        for i, h in enumerate(TABLE_HEADERS)
    )
    trs = []
    for row in TABLE_ROWS:
        cells = []
        for i, c in enumerate(row):
            label = TABLE_HEADERS[i]
            sort = _num(c) if i else c.lower()
            if i == 1:
                inner = f'<span class="gg-ig-a-rt__tier gg-ig-a-rt__tier--{_e(c.lower())}">{_e(c)}</span>'
            elif i == 4:
                inner = (f'<span class="gg-ig-a-rt__score">{_e(c)}</span>'
                         f'<span class="gg-ig-a-rt__sbar" aria-hidden="true">'
                         f'<span style="width:{min(_num(c), 100)}%"></span></span>')
            else:
                inner = _e(c)
            cls = ["gg-ig-a-rt__td"] + (["gg-ig-a-rt__td--name"] if i == 0 else [])
            cells.append(
                f'<td class="{" ".join(cls)}" data-label="{_e(label)}" data-sort="{_e(sort)}">{inner}</td>'
            )
        trs.append(f'<tr>{"".join(cells)}</tr>')
    body = (
        f'<div class="gg-ig-a-rt__sort" role="group" aria-label="Sort races by">'
        f'<span class="gg-ig-a-rt__sortlabel">Sort by</span>{"".join(chips)}</div>'
        f'<table class="gg-ig-a-rt__table"><thead><tr>{th}</tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table>'
    )
    top = max(TABLE_ROWS, key=lambda r: _num(r[4]))
    return _panel("rt", "light", "CH 2 · RACES", "Race Comparison: Sorting the Field",
                  top[4], f"top score, {top[0]}. Sort to find your race.", body, block)


RENDERERS = {
    "ch1-gear-essentials": render_gear_essentials,
    "ch1-rider-grid": render_rider_grid,
    "ch1-hierarchy-of-speed": render_hierarchy,
    "ch1-gear-weight": render_gear_weight,
    "ch2-scoring-dimensions": render_scoring_dimensions,
    "ch2-tier-distribution": render_tier_distribution,
    "ch2-course-profile": render_course_profile,
    "ch2-field-scatter": render_field_scatter,
    "ch2-race-table": render_race_table,
}


CSS = """
.gg-ig-a{--a-ink:var(--gg-color-dark-brown);--a-ink2:var(--gg-color-primary-brown);--a-bg:var(--gg-color-warm-paper);--a-line:var(--gg-color-dark-brown);--a-acc:var(--gg-color-gold);--a-focus:var(--gg-color-teal);box-sizing:border-box;margin:24px 0;padding:0;border:3px solid var(--gg-color-dark-brown);background:var(--a-bg);color:var(--a-ink);font-family:var(--gg-font-editorial);width:100%;max-width:100%;min-width:0;overflow:hidden}
.gg-ig-a *,.gg-ig-a *::before,.gg-ig-a *::after{box-sizing:border-box}
.gg-ig-a--dark{--a-ink:var(--gg-color-warm-paper);--a-ink2:var(--gg-color-sand);--a-bg:var(--gg-color-dark-brown);--a-line:var(--gg-color-warm-paper);--a-acc:var(--gg-color-light-gold);--a-focus:var(--gg-color-light-teal)}
.gg-ig-a button{font-family:var(--gg-font-data);cursor:pointer;border-radius:0}
.gg-ig-a button:focus-visible{outline:3px solid var(--a-focus);outline-offset:2px}
.gg-ig-a ul,.gg-ig-a ol{list-style:none;margin:0;padding:0}
.gg-ig-a p,.gg-ig-a dl,.gg-ig-a dd,.gg-ig-a dt{margin:0}
.gg-ig-a__head{background:var(--gg-color-dark-brown);padding:20px 28px 22px;border-bottom:3px solid var(--gg-color-dark-brown)}
.gg-ig-a__eyebrow{font-family:var(--gg-font-data);font-size:14px;font-weight:700;letter-spacing:3px;color:var(--gg-color-light-gold);margin-bottom:8px}
.gg-ig-a__title{font-family:var(--gg-font-editorial);font-size:clamp(22px,4.6vw,32px);font-weight:700;line-height:1.15;color:var(--gg-color-white);overflow-wrap:anywhere}
.gg-ig-a__hero{display:flex;align-items:baseline;flex-wrap:wrap;gap:4px 20px;padding:20px 28px;border-bottom:3px solid var(--gg-color-dark-brown)}
.gg-ig-a--light .gg-ig-a__hero{background:var(--gg-color-light-gold);color:var(--gg-color-dark-brown)}
.gg-ig-a--dark .gg-ig-a__hero{background:var(--gg-color-near-black);color:var(--gg-color-warm-paper);border-bottom-color:var(--gg-color-light-gold)}
.gg-ig-a__big{font-family:var(--gg-font-data);font-size:clamp(56px,11vw,96px);font-weight:700;line-height:.95;letter-spacing:-2px;font-variant-numeric:tabular-nums}
.gg-ig-a--dark .gg-ig-a__big{color:var(--gg-color-light-gold)}
.gg-ig-a__bigcap{font-family:var(--gg-font-data);font-size:16px;font-weight:700;letter-spacing:1px;text-transform:uppercase;line-height:1.35;flex:1 1 220px;min-width:0}
.gg-ig-a__body{padding:28px}
.gg-ig-a__cap{margin-top:28px!important;padding:6px 0 6px 18px;border-left:6px solid var(--a-acc);font-family:var(--gg-font-editorial);font-style:italic;font-size:16px;line-height:1.5;color:var(--a-ink);width:100%}
@media(max-width:600px){.gg-ig-a{margin:16px 0}.gg-ig-a__head,.gg-ig-a__hero{padding-left:16px;padding-right:16px}.gg-ig-a__body{padding:16px}.gg-ig-a__big{letter-spacing:-1px}}

.gg-ig-a-rg__card,.gg-ig-a-ge__tip,.gg-ig-a-hs__tip,.gg-ig-a-td__tip,.gg-ig-a-sd__tip,.gg-ig-a-fs__group li,.gg-ig-a-gw__tip,.gg-ig-a-cp__keytxt{font-family:var(--gg-font-editorial)}
/* gear essentials */
.gg-ig-a-ge__grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,250px),1fr));gap:16px}
.gg-ig-a-ge__card{display:flex;flex-direction:column;border:3px solid var(--gg-color-dark-brown);background:var(--gg-color-white);min-width:0}
.gg-ig-a-ge__top{display:flex;align-items:center;gap:14px;background:var(--gg-color-dark-brown);padding:14px 16px}
.gg-ig-a-ge__num{font-family:var(--gg-font-data);font-size:32px;font-weight:700;line-height:1;color:var(--gg-color-light-gold)}
.gg-ig-a-ge__name{font-size:22px;font-weight:700;line-height:1.15;color:var(--gg-color-white)}
.gg-ig-a-ge__desc{padding:16px;font-size:16px;line-height:1.5;flex:1}
.gg-ig-a-ge__tip{display:flex;flex-direction:column;gap:4px;padding:12px 16px 14px;background:var(--gg-color-light-gold);border-top:3px solid var(--gg-color-dark-brown);font-size:15px;line-height:1.45;font-weight:600}
.gg-ig-a-ge__tiplabel{font-family:var(--gg-font-data);font-size:14px;font-weight:700;letter-spacing:2px;text-transform:uppercase}

/* rider grid */
.gg-ig-a-rg__grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr));gap:16px}
.gg-ig-a-rg__card{background:var(--gg-color-warm-paper);color:var(--gg-color-dark-brown);border:3px solid var(--gg-color-light-gold);display:flex;flex-direction:column;min-width:0}
.gg-ig-a-rg__top{padding:16px;border-bottom:3px solid var(--gg-color-dark-brown);position:relative}
.gg-ig-a-rg__name{font-size:26px;font-weight:700;line-height:1.1}
.gg-ig-a-rg__flag{display:inline-block;margin-top:8px;padding:3px 8px;background:var(--gg-color-dark-brown);color:var(--gg-color-light-gold);font-family:var(--gg-font-data);font-size:14px;font-weight:700;letter-spacing:1px;text-transform:uppercase}
.gg-ig-a-rg__hours{font-family:var(--gg-font-data);font-size:26px;font-weight:700;margin-top:10px;font-variant-numeric:tabular-nums}
.gg-ig-a-rg__bar{height:18px;margin:12px 0 8px;background:var(--gg-color-tan);border:2px solid var(--gg-color-dark-brown)}
.gg-ig-a-rg__bar span{display:block;height:100%;background:var(--gg-color-dark-brown)}
.gg-ig-a-rg__ftp{display:flex;gap:10px;align-items:baseline;font-family:var(--gg-font-data);font-size:18px;font-weight:700}
.gg-ig-a-rg__ftplabel{font-size:14px;letter-spacing:2px;color:var(--gg-color-primary-brown)}
.gg-ig-a-rg__facts{padding:12px 16px;display:grid;gap:8px}
.gg-ig-a-rg__facts div{display:grid;grid-template-columns:84px 1fr;gap:8px;align-items:baseline}
.gg-ig-a-rg__facts dt{font-family:var(--gg-font-data);font-size:14px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--gg-color-primary-brown)}
.gg-ig-a-rg__facts dd{font-size:16px;font-weight:700;line-height:1.3}
.gg-ig-a-rg__detail{margin:0;padding:12px 16px 16px;border-top:3px solid var(--gg-color-dark-brown);font-size:15px;line-height:1.5;background:var(--gg-color-sand);flex:1}

/* hierarchy of speed */
.gg-ig-a-hs__list{display:grid;gap:18px}
.gg-ig-a-hs__row{display:grid;grid-template-columns:minmax(110px,160px) 1fr 84px;gap:4px 16px;align-items:center}
.gg-ig-a-hs__label{font-family:var(--gg-font-data);font-size:16px;font-weight:700;text-transform:uppercase;letter-spacing:.5px}
.gg-ig-a-hs__track{display:block;height:34px;border:3px solid var(--gg-color-dark-brown);background:var(--gg-color-sand)}
.gg-ig-a-hs__fill{display:block;height:100%;background:var(--gg-color-dark-brown)}
.gg-ig-a-hs__row.is-top .gg-ig-a-hs__fill{background:var(--gg-color-gold)}
.gg-ig-a-hs__val{font-family:var(--gg-font-data);font-size:24px;font-weight:700;text-align:right;font-variant-numeric:tabular-nums}
.gg-ig-a-hs__tip{grid-column:2 / 4;font-size:15px;line-height:1.45;color:var(--gg-color-primary-brown)}
@media(max-width:600px){.gg-ig-a-hs__row{grid-template-columns:1fr auto}.gg-ig-a-hs__label{grid-column:1}.gg-ig-a-hs__val{grid-column:2;grid-row:1}.gg-ig-a-hs__track{grid-column:1 / 3}.gg-ig-a-hs__tip{grid-column:1 / 3}}

/* gear weight */
.gg-ig-a-gw__list{display:grid;gap:12px}
.gg-ig-a-gw__item{display:grid;grid-template-columns:28px minmax(0,1.2fr) minmax(0,1fr) 84px;gap:14px;align-items:center;width:100%;min-height:56px;padding:10px 14px;text-align:left;background:var(--gg-color-near-black);color:var(--gg-color-warm-paper);border:3px solid var(--gg-color-light-gold)}
.gg-ig-a-gw__item.is-off{border-color:var(--gg-color-secondary-brown);background:transparent;color:var(--gg-color-sand)}
.gg-ig-a-gw__check{width:26px;height:26px;border:3px solid var(--gg-color-light-gold);background:transparent;position:relative}
.gg-ig-a-gw__item.is-on .gg-ig-a-gw__check{background:var(--gg-color-light-gold)}
.gg-ig-a-gw__item.is-on .gg-ig-a-gw__check::after{content:"";position:absolute;left:6px;top:1px;width:7px;height:13px;border:solid var(--gg-color-dark-brown);border-width:0 3px 3px 0;transform:rotate(45deg)}
.gg-ig-a-gw__item.is-off .gg-ig-a-gw__check{border-color:var(--gg-color-warm-brown)}
.gg-ig-a-gw__what{display:flex;flex-direction:column;gap:2px;min-width:0}
.gg-ig-a-gw__name{font-family:var(--gg-font-data);font-size:18px;font-weight:700;text-transform:uppercase;letter-spacing:.5px}
.gg-ig-a-gw__desc{font-family:var(--gg-font-editorial);font-size:15px}
.gg-ig-a-gw__bar{display:block;height:20px;background:rgba(245,239,230,.14)}
.gg-ig-a-gw__bar span{display:block;height:100%;background:var(--gg-color-light-gold)}
.gg-ig-a-gw__item.is-off .gg-ig-a-gw__bar span{background:var(--gg-color-secondary-brown)}
.gg-ig-a-gw__kg{font-family:var(--gg-font-data);font-size:24px;font-weight:700;text-align:right;font-variant-numeric:tabular-nums}
.gg-ig-a-gw__kg small{font-size:14px;font-weight:700}
.gg-ig-a-gw__item.is-off .gg-ig-a-gw__kg{text-decoration:line-through}
.gg-ig-a-gw__tip{margin:6px 0 0!important;padding-left:17px;font-size:15px;line-height:1.45;color:var(--gg-color-sand)}
@media(max-width:600px){.gg-ig-a-gw__item{grid-template-columns:28px 1fr auto;gap:8px 12px}.gg-ig-a-gw__bar{grid-column:1 / 4;grid-row:2}}

/* scoring dimensions */
.gg-ig-a-sd__toggles{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:24px}
.gg-ig-a-sd__race{min-height:48px;padding:10px 20px;font-size:16px;font-weight:700;letter-spacing:1px;text-transform:uppercase;background:var(--gg-color-warm-paper);color:var(--gg-color-dark-brown);border:3px solid var(--gg-color-dark-brown)}
.gg-ig-a-sd__race[aria-pressed="true"]{background:var(--gg-color-dark-brown);color:var(--gg-color-light-gold)}
.gg-ig-a-sd__list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px 36px}
.gg-ig-a-sd__row{display:grid;grid-template-columns:1fr auto 52px;gap:2px 14px;align-items:center;padding-bottom:14px;border-bottom:3px solid var(--gg-color-tan)}
.gg-ig-a-sd__label{font-family:var(--gg-font-data);font-size:16px;font-weight:700;text-transform:uppercase;letter-spacing:.5px}
.gg-ig-a-sd__pips{display:flex;gap:4px}
.gg-ig-a-sd__pip{width:22px;height:22px;border:3px solid var(--gg-color-dark-brown);background:transparent}
.gg-ig-a-sd__pip.is-on{background:var(--gg-color-dark-brown)}
.gg-ig-a-sd__val{font-family:var(--gg-font-data);font-size:24px;font-weight:700;text-align:right;font-variant-numeric:tabular-nums}
.gg-ig-a-sd__val small{font-size:14px}
.gg-ig-a-sd__tip{grid-column:1 / 4;font-size:15px;line-height:1.4;color:var(--gg-color-primary-brown)}
@media(max-width:820px){.gg-ig-a-sd__list{grid-template-columns:1fr}}
@media(max-width:600px){.gg-ig-a-sd__pip{width:18px;height:18px}.gg-ig-a-sd__row{gap:2px 10px}}

/* tier distribution */
.gg-ig-a-td__list{display:grid;gap:22px}
.gg-ig-a-td__row{display:grid;grid-template-columns:64px 1fr 120px;gap:4px 18px;align-items:center}
.gg-ig-a-td__tier{font-family:var(--gg-font-data);font-size:36px;font-weight:700;line-height:1}
.gg-ig-a-td__track{display:block;height:40px;border:3px solid var(--gg-color-warm-paper)}
.gg-ig-a-td__fill{display:block;height:100%;background:var(--gg-color-warm-paper)}
.gg-ig-a-td__row.is-top .gg-ig-a-td__fill{background:var(--gg-color-light-gold)}
.gg-ig-a-td__row.is-top .gg-ig-a-td__track{border-color:var(--gg-color-light-gold)}
.gg-ig-a-td__row.is-top .gg-ig-a-td__tier{color:var(--gg-color-light-gold)}
.gg-ig-a-td__num{font-family:var(--gg-font-data);font-size:32px;font-weight:700;text-align:right;font-variant-numeric:tabular-nums;display:flex;flex-direction:column;align-items:flex-end;line-height:1}
.gg-ig-a-td__num small{font-size:16px;margin-top:4px;color:var(--gg-color-sand)}
.gg-ig-a-td__tip{grid-column:2 / 4;font-size:16px;line-height:1.45;color:var(--gg-color-sand)}
@media(max-width:600px){.gg-ig-a-td__row{grid-template-columns:auto 1fr auto}.gg-ig-a-td__tier{grid-column:1}.gg-ig-a-td__num{grid-column:3;grid-row:1}.gg-ig-a-td__track{grid-column:2;grid-row:1;height:32px}.gg-ig-a-td__tip{grid-column:1 / 4}.gg-ig-a-td__tier{font-size:30px}}

/* course profile */
.gg-ig-a-cp__chart{position:relative;margin:36px 8px 44px 56px}
.gg-ig-a-cp__plot{position:relative;height:clamp(220px,38vw,380px);border-left:3px solid var(--gg-color-dark-brown);border-bottom:3px solid var(--gg-color-dark-brown)}
.gg-ig-a-cp__svg{position:absolute;inset:0;width:100%;height:100%;display:block}
.gg-ig-a-cp__seg--flat{fill:var(--gg-color-tan);background:var(--gg-color-tan)}
.gg-ig-a-cp__seg--mod{fill:var(--gg-color-teal);background:var(--gg-color-teal)}
.gg-ig-a-cp__seg--steep{fill:var(--gg-color-gold);background:var(--gg-color-gold)}
.gg-ig-a-cp__seg--brutal{fill:var(--gg-color-error);background:var(--gg-color-error)}
.gg-ig-a-cp__seg{stroke:var(--gg-color-warm-paper);stroke-width:1;vector-effect:non-scaling-stroke}
.gg-ig-a-cp__line{fill:none;stroke:var(--gg-color-dark-brown);stroke-width:4;stroke-linejoin:miter;vector-effect:non-scaling-stroke}
.gg-ig-a-cp__gridline{position:absolute;left:0;right:0;border-top:2px dashed var(--gg-color-dark-brown);opacity:.25}
.gg-ig-a-cp__ytick{position:absolute;left:-58px;width:50px;text-align:right;transform:translateY(50%);font-family:var(--gg-font-data);font-size:12px;font-weight:700;color:var(--gg-color-dark-brown)}
.gg-ig-a-cp__xtick{position:absolute;bottom:-28px;transform:translateX(-50%);font-family:var(--gg-font-data);font-size:12px;font-weight:700;color:var(--gg-color-dark-brown)}
.gg-ig-a-cp__xtick:first-of-type{transform:none}
.gg-ig-a-cp__xlabel{position:absolute;right:0;bottom:-48px;font-family:var(--gg-font-data);font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase}
.gg-ig-a-cp__ylabel{position:absolute;left:-56px;top:-30px;font-family:var(--gg-font-data);font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase}
.gg-ig-a-cp__mark{position:absolute;transform:translate(8px,-130%);white-space:nowrap;padding:2px 8px;background:var(--gg-color-dark-brown);color:var(--gg-color-white);font-family:var(--gg-font-data);font-size:14px;font-weight:700}
.gg-ig-a-cp__mark--l{transform:translate(-100%,-130%)}
.gg-ig-a-cp__mark--hot{background:var(--gg-color-error)}
.gg-ig-a-cp__legend{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,200px),1fr));gap:12px}
.gg-ig-a-cp__key{display:grid;grid-template-columns:24px 1fr auto;gap:10px;align-items:center;padding:8px 10px;border:3px solid var(--gg-color-dark-brown);background:var(--gg-color-white)}
.gg-ig-a-cp__sw{width:24px;height:24px;border:2px solid var(--gg-color-dark-brown);display:block}
.gg-ig-a-cp__keytxt{font-size:15px;line-height:1.25}
.gg-ig-a-cp__keytxt b{display:block;font-family:var(--gg-font-data);font-size:14px;text-transform:uppercase;letter-spacing:.5px}
.gg-ig-a-cp__miles{font-family:var(--gg-font-data);font-size:18px;font-weight:700;font-variant-numeric:tabular-nums}
@media(max-width:600px){.gg-ig-a-cp__chart{margin:32px 4px 44px 52px}.gg-ig-a-cp__plot{height:240px}.gg-ig-a-cp__line{stroke-width:3}}

/* field scatter */
.gg-ig-a-fs__chart{margin:20px 8px 56px 52px}
.gg-ig-a-fs__plot{position:relative;height:clamp(260px,42vw,420px);border-left:3px solid var(--gg-color-warm-paper);border-bottom:3px solid var(--gg-color-warm-paper)}
.gg-ig-a-fs__hline{position:absolute;left:0;right:0;border-top:2px dashed var(--gg-color-warm-paper);opacity:.22}
.gg-ig-a-fs__ytick{position:absolute;left:-52px;width:44px;text-align:right;transform:translateY(50%);font-family:var(--gg-font-data);font-size:12px;font-weight:700}
.gg-ig-a-fs__xtick{position:absolute;bottom:-28px;transform:translateX(-50%);font-family:var(--gg-font-data);font-size:12px;font-weight:700}
.gg-ig-a-fs__xlabel{position:absolute;left:50%;bottom:-52px;transform:translateX(-50%);font-family:var(--gg-font-data);font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;white-space:nowrap}
.gg-ig-a-fs__ylabel{position:absolute;left:-52px;top:-26px;font-family:var(--gg-font-data);font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;white-space:nowrap}
.gg-ig-a-fs__pt,.gg-ig-a-fs__chip{display:flex;align-items:center;justify-content:center;font-family:var(--gg-font-data);font-size:14px;font-weight:700;border:3px solid var(--gg-color-warm-paper)}
.gg-ig-a-fs__pt{position:absolute;width:26px;height:26px;transform:translate(-50%,50%)}
.gg-ig-a-fs__chip{width:30px;height:30px;flex:none}
.gg-ig-a-fs__pt--t1{background:var(--gg-color-light-gold);color:var(--gg-color-dark-brown);border-color:var(--gg-color-light-gold)}
.gg-ig-a-fs__pt--t2{background:var(--gg-color-warm-paper);color:var(--gg-color-dark-brown)}
.gg-ig-a-fs__pt--t3{background:var(--gg-color-tan);color:var(--gg-color-dark-brown);border-color:var(--gg-color-tan)}
.gg-ig-a-fs__pt--t4{background:var(--gg-color-dark-brown);color:var(--gg-color-warm-paper);border-color:var(--gg-color-warm-paper)}
.gg-ig-a-fs__name{position:absolute;left:50%;bottom:100%;transform:translateX(-4px);margin-bottom:4px;white-space:nowrap;font-family:var(--gg-font-data);font-size:14px;font-weight:700;color:var(--gg-color-warm-paper);padding:0 4px;background:var(--gg-color-dark-brown)}
.gg-ig-a-fs__name--r{left:auto;right:50%;transform:translateX(4px)}
.gg-ig-a-fs__groups{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));gap:16px}
.gg-ig-a-fs__group{border:3px solid var(--gg-color-warm-paper);padding:12px 14px}
.gg-ig-a-fs__ghead{display:flex;align-items:center;gap:10px;font-family:var(--gg-font-data);font-size:16px;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}
.gg-ig-a-fs__group li{display:flex;justify-content:space-between;gap:10px;font-size:15px;line-height:1.5;padding:2px 0}
.gg-ig-a-fs__gval{font-family:var(--gg-font-data);font-size:14px;font-weight:700;white-space:nowrap;font-variant-numeric:tabular-nums}
@media(max-width:600px){.gg-ig-a-fs__chart{margin:16px 4px 56px 48px}.gg-ig-a-fs__pt{width:22px;height:22px;font-size:12px;border-width:2px}.gg-ig-a-fs__plot{height:300px}}

/* race table */
.gg-ig-a-rt__sort{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:20px}
.gg-ig-a-rt__sortlabel{font-family:var(--gg-font-data);font-size:14px;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-right:4px}
.gg-ig-a-rt__chip{min-height:44px;padding:8px 14px;font-size:14px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;background:var(--gg-color-warm-paper);color:var(--gg-color-dark-brown);border:3px solid var(--gg-color-dark-brown);display:inline-flex;align-items:center;gap:6px}
.gg-ig-a-rt__chip[aria-pressed="true"]{background:var(--gg-color-dark-brown);color:var(--gg-color-light-gold)}
.gg-ig-a-rt__arrow{display:inline-block;min-width:1ch}
.gg-ig-a-rt__table{width:100%;border-collapse:collapse;border:3px solid var(--gg-color-dark-brown);background:var(--gg-color-white);table-layout:auto}
.gg-ig-a-rt__table th{background:var(--gg-color-dark-brown);color:var(--gg-color-light-gold);font-family:var(--gg-font-data);font-size:14px;font-weight:700;letter-spacing:1px;text-transform:uppercase;text-align:left;padding:12px 14px;border:0}
.gg-ig-a-rt__table td{padding:14px;border-top:3px solid var(--gg-color-dark-brown);font-family:var(--gg-font-data);font-size:16px;font-weight:700;font-variant-numeric:tabular-nums;vertical-align:middle;color:var(--gg-color-dark-brown)}
.gg-ig-a-rt__td--name{font-family:var(--gg-font-editorial)!important;font-size:18px!important}
.gg-ig-a-rt__tier{display:inline-block;min-width:40px;text-align:center;padding:2px 8px;border:3px solid var(--gg-color-dark-brown);font-size:16px}
.gg-ig-a-rt__tier--t1{background:var(--gg-color-light-gold)}
.gg-ig-a-rt__score{display:block;font-size:22px}
.gg-ig-a-rt__sbar{display:block;height:8px;margin-top:4px;background:var(--gg-color-sand);min-width:60px}
.gg-ig-a-rt__sbar span{display:block;height:100%;background:var(--gg-color-dark-brown)}
@media(max-width:700px){
.gg-ig-a-rt__table,.gg-ig-a-rt__table tbody{display:block}
.gg-ig-a-rt__table thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.gg-ig-a-rt__table tr{display:grid;grid-template-columns:1fr 1fr;gap:10px 12px;padding:14px;border-top:3px solid var(--gg-color-dark-brown)}
.gg-ig-a-rt__table tr:first-child{border-top:0}
.gg-ig-a-rt__table td{display:block;border:0;padding:0;font-size:16px}
.gg-ig-a-rt__table td::before{content:attr(data-label);display:block;font-size:14px;letter-spacing:1px;text-transform:uppercase;color:var(--gg-color-primary-brown)}
.gg-ig-a-rt__td--name{grid-column:1 / 3;font-size:20px!important}
.gg-ig-a-rt__td--name::before{display:none!important}
}
"""


JS = """
(function(){
  /* gear weight toggles */
  document.querySelectorAll(".gg-ig-a-gw").forEach(function(root){
    var total=root.querySelector(".gg-ig-a-gw__total");
    var items=root.querySelectorAll(".gg-ig-a-gw__item");
    function recompute(){
      var sum=0;
      items.forEach(function(b){ if(b.getAttribute("aria-pressed")==="true"){ sum+=parseFloat(b.getAttribute("data-weight"))||0; } });
      if(total){ total.textContent=sum.toFixed(1); }
    }
    items.forEach(function(b){
      b.addEventListener("click",function(){
        var on=b.getAttribute("aria-pressed")!=="true";
        b.setAttribute("aria-pressed",on?"true":"false");
        b.classList.toggle("is-on",on);
        b.classList.toggle("is-off",!on);
        recompute();
      });
    });
  });

  /* scoring dimensions: switch race */
  document.querySelectorAll(".gg-ig-a-sd").forEach(function(root){
    var btns=root.querySelectorAll(".gg-ig-a-sd__race");
    var rows=root.querySelectorAll(".gg-ig-a-sd__row");
    btns.forEach(function(b){
      b.addEventListener("click",function(){
        var scores=(b.getAttribute("data-scores")||"").split(",");
        btns.forEach(function(o){ o.setAttribute("aria-pressed",o===b?"true":"false"); });
        rows.forEach(function(row,i){
          var s=parseInt(scores[i],10)||0;
          row.querySelectorAll(".gg-ig-a-sd__pip").forEach(function(p,k){ p.classList.toggle("is-on",k<s); });
          var v=row.querySelector(".gg-ig-a-sd__val");
          if(v){
            while(v.firstChild){ v.removeChild(v.firstChild); }
            v.appendChild(document.createTextNode(String(s)));
            var sm=document.createElement("small");
            sm.textContent="/5";
            v.appendChild(sm);
          }
        });
      });
    });
  });

  /* race table: sort chips */
  document.querySelectorAll(".gg-ig-a-rt").forEach(function(root){
    var chips=root.querySelectorAll(".gg-ig-a-rt__chip");
    var tbody=root.querySelector("tbody");
    var ths=root.querySelectorAll("th[data-col]");
    var dirs={};
    chips.forEach(function(chip){
      chip.addEventListener("click",function(){
        var col=parseInt(chip.getAttribute("data-col"),10);
        var cur=dirs[col];
        var dir=(chip.getAttribute("aria-pressed")==="true"&&cur)?(cur==="asc"?"desc":"asc"):chip.getAttribute("data-dir");
        dirs[col]=dir;
        var rows=Array.prototype.slice.call(tbody.querySelectorAll("tr"));
        rows.sort(function(a,b){
          var x=a.children[col].getAttribute("data-sort");
          var y=b.children[col].getAttribute("data-sort");
          var nx=parseFloat(x), ny=parseFloat(y);
          var c=(!isNaN(nx)&&!isNaN(ny)&&String(nx)===x&&String(ny)===y)?(nx-ny):(x<y?-1:(x>y?1:0));
          return dir==="asc"?c:-c;
        });
        rows.forEach(function(r){ tbody.appendChild(r); });
        chips.forEach(function(o){
          var on=o===chip;
          o.setAttribute("aria-pressed",on?"true":"false");
          var ar=o.querySelector(".gg-ig-a-rt__arrow");
          if(ar){ ar.textContent=on?(dir==="asc"?"\\u2191":"\\u2193"):""; }
        });
        ths.forEach(function(t){
          if(parseInt(t.getAttribute("data-col"),10)===col){ t.setAttribute("aria-sort",dir==="asc"?"ascending":"descending"); }
          else { t.removeAttribute("aria-sort"); }
        });
      });
    });
  });
})();
"""
