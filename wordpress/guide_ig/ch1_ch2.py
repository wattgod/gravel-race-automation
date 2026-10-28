"""Handbook charts, rebuilt: chapters 1 and 2 (poster panels).

Exports RENDERERS (asset_id -> render(block) -> html), CSS and JS.
All selectors are prefixed .gg-ig-a- so groups cannot clash.
"""
import html as _html
import json
import re
from pathlib import Path

from guide_ig import glyph

RACE_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "race-data"


def _e(text) -> str:
    """HTML-escape any value. 0 prints as 0."""
    return _html.escape(str(text))


def _panel(kind: str, tone: str, eyebrow: str, title: str, big: str, big_cap: str,
           body: str, block: dict, extra_cls: str = "", pre: str = "") -> str:
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
        f'<div class="gg-ig-a__body">{pre}{body}{cap}</div>'
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
            f'<button type="button" class="gg-ig-a-ge__top" aria-pressed="false">'
            f'<span class="gg-ig-a-ge__num">{i:02d}</span>'
            f'<span class="gg-ig-a-ge__name">{_e(name)}</span>'
            f'<span class="gg-ig-a-ge__box" aria-hidden="true"></span>'
            f'</button>'
            f'<div class="gg-ig-a-ge__desc">{_e(desc)}</div>'
            f'<div class="gg-ig-a-ge__tip">'
            f'<span class="gg-ig-a-ge__tiplabel">Tip</span>'
            f'<span>{_e(tip)}</span>'
            f'</div>'
            f'</div>'
        )
    body = f'<div class="gg-ig-a-ge__grid">{"".join(cards)}</div>'
    n = len(GEAR_ITEMS)
    pre = (
        f'<div class="gg-ig-a-ctl gg-ig-a-ge__count" data-total="{n}">'
        f'<span class="gg-ig-a-ge__packed" role="status" aria-live="polite">0 of {n} packed</span>'
        f'<span class="gg-ig-a-ge__pips" aria-hidden="true">'
        + "".join('<i class="gg-ig-a-ge__pip"></i>' for _ in range(n))
        + '</span></div>'
    )
    return _panel("ge", "light", "CH 1 · GEAR", "Essential Gear for Race Day",
                  str(n), "things you actually need", body, block, pre=pre)


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


def _hours_range(text: str):
    """'3-5 hrs/wk' -> (3, 5)."""
    lo, hi = re.match(r"(\d+)-(\d+)", text).groups()
    return int(lo), int(hi)


def render_rider_grid(block: dict) -> str:
    cards = []
    for r in RIDERS:
        lo, hi = _hours_range(r["hours"])
        flag = (
            '<span class="gg-ig-a-rg__flag">Biggest group</span>'
            if r["name"] == "Finisher" else ""
        )
        cards.append(
            f'<div class="gg-ig-a-rg__card" data-name="{_e(r["name"])}" data-lo="{lo}" data-hi="{hi}">'
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
    lo_all = min(_hours_range(r["hours"])[0] for r in RIDERS)
    hi_all = max(_hours_range(r["hours"])[1] for r in RIDERS)
    pre = (
        f'<div class="gg-ig-a-ctl gg-ig-a-rg__ctl">'
        f'<label class="gg-ig-a-rg__lab" for="gg-ig-a-rg-hrs">Your hours a week</label>'
        f'<input id="gg-ig-a-rg-hrs" class="gg-ig-a-rg__range" type="range" min="{lo_all}" max="{hi_all}"'
        f' step="1" value="6" aria-describedby="gg-ig-a-rg-match">'
        f'<output class="gg-ig-a-rg__hrs" for="gg-ig-a-rg-hrs">6 hrs</output>'
        f'<span id="gg-ig-a-rg-match" class="gg-ig-a-rg__match" role="status" aria-live="polite"></span></div>'
    )
    return _panel("rg", "dark", "CH 1 · RIDERS", "Four Rider Archetypes",
                  f"{lo_all}–{hi_all}", "hours a week across four profiles", body, block, pre=pre)


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
            f'<li class="gg-ig-a-hs__row{hot}" data-i="{i}">'
            f'<span class="gg-ig-a-hs__label">{_e(label)}</span>'
            f'<span class="gg-ig-a-hs__track" aria-hidden="true">'
            f'<span class="gg-ig-a-hs__fill" style="width:{w:.1f}%"></span></span>'
            f'<span class="gg-ig-a-hs__val">{_e(pct)}</span>'
            f'<span class="gg-ig-a-hs__tip">{_e(tip)}</span>'
            f'</li>'
        )
    body = f'<ol class="gg-ig-a-hs__list">{"".join(rows)}</ol>'
    picks = "".join(
        f'<button type="button" class="gg-ig-a-pick" data-i="{i}" data-share="{val:g}"'
        f' data-tip="{_e(tip)}" aria-pressed="false">{_e(label)}</button>'
        for i, (label, _pct, val, tip) in enumerate(HIERARCHY)
    )
    pre = (
        f'<div class="gg-ig-a-ctl gg-ig-a-hs__ctl" data-min="{min(h[2] for h in HIERARCHY):g}">'
        f'<div class="gg-ig-a-hs__picks" role="group" aria-label="Pick a factor">{picks}</div>'
        f'<div class="gg-ig-a-hs__read" role="status" aria-live="polite">'
        f'<span class="gg-ig-a-hs__rshare"></span><span class="gg-ig-a-hs__rtxt"></span></div></div>'
    )
    return _panel("hs", "light", "CH 1 · SPEED",
                  "The Hierarchy of Speed: What Actually Makes You Faster",
                  "70%", "of your speed is fitness", body, block, pre=pre)


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
            f'<li class="gg-ig-a-td__li"><button type="button" class="gg-ig-a-td__row{hot}"'
            f' aria-pressed="false" data-tier="{_e(label)}" data-count="{count}" data-pct="{pct}"'
            f' data-tip="{_e(tip)}">'
            f'<span class="gg-ig-a-td__tier">{_e(label)}</span>'
            f'<span class="gg-ig-a-td__track" aria-hidden="true">'
            f'<span class="gg-ig-a-td__fill" style="width:{count / top * 100:.1f}%"></span></span>'
            f'<span class="gg-ig-a-td__num">{_e(count)}<small>{_e(pct)}%</small></span>'
            f'<span class="gg-ig-a-td__tip">{_e(tip)}</span>'
            f'</button></li>'
        )
    body = f'<ol class="gg-ig-a-td__list">{"".join(rows)}</ol>'
    pre = (
        f'<div class="gg-ig-a-ctl gg-ig-a-td__detail" data-total="{total}" role="status" aria-live="polite">'
        f'<span class="gg-ig-a-td__dtier"></span><span class="gg-ig-a-td__dcount"></span>'
        f'<span class="gg-ig-a-td__dtip"></span></div>'
    )
    return _panel("td", "dark", "CH 2 · TIERS", "How We Tier 328 Gravel Races",
                  str(total), "gravel races in four tiers", body, block, pre=pre)


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


def _gpanel(kind: str, eyebrow: str, title: str, card: str, block: dict) -> str:
    """GG title band + Glyph card on a light ground + gold-ruled caption."""
    caption = block.get("caption", "")
    cap = f'<div class="gg-ig-a__cap">{_e(caption)}</div>' if caption else ""
    return (
        f'<figure class="gg-ig-a gg-ig-a--light gg-ig-a-{kind}" role="figure">'
        f'<div class="gg-ig-a__head"><div class="gg-ig-a__eyebrow">{_e(eyebrow)}</div>'
        f'<div class="gg-ig-a__title">{_e(title)}</div></div>'
        f'<div class="gg-ig-a__body gg-ig-a-eg-body">{card}{cap}</div></figure>'
    )


_CP_PEAK_MILE = max(PROFILE, key=lambda p: p[1])[0]


def _cp_series():
    """Elevation (ft) at every whole mile: a monotone curve through the 21 profile points."""
    f = glyph.mono_curve([(float(m), float(e)) for m, e, _ in PROFILE])
    return [int(round(f(float(m)))) for m in range(PROFILE[-1][0] + 1)]


def _cp_seg(mile: int) -> int:
    """Which 5-mile segment a mile sits in (mile 100 belongs to the last one)."""
    return min(mile // 5, len(PROFILE) - 2)


def _cp_text(mile: int):
    """Header strings for a mile (mirrored by the script's update())."""
    g = PROFILE[_cp_seg(mile) + 1][2]
    name = dict((k, n) for k, n, _ in _CP_CLASSES)[_cp_class(g)]
    arrow = "▲ " if g > 0 else "▼ " if g < 0 else ""
    return f"{_cp_series()[mile]:,}", f"{arrow}{abs(g)}% · {name}", f"Mile {mile}" + (" · peak" if mile == _CP_PEAK_MILE else "")


def render_course_profile(block: dict) -> str:
    W, H = 1000, 300
    max_mile = PROFILE[-1][0]
    span = _CP_HI - _CP_LO
    elev = _cp_series()
    xs = lambda m: m / max_mile * W  # noqa: E731
    ys = lambda e: H - (e - _CP_LO) / span * H  # noqa: E731

    polys = []
    miles_by = {k: 0 for k, _, _ in _CP_CLASSES}
    for i in range(len(PROFILE) - 1):
        m1, m2 = PROFILE[i][0], PROFILE[i + 1][0]
        cls = _cp_class(PROFILE[i + 1][2])
        miles_by[cls] += m2 - m1
        top = [(xs(m), ys(elev[m])) for m in range(m1, m2 + 1)]
        pts = [(xs(m1), H)] + top + [(xs(m2), H)]
        polys.append(
            f'<path class="gg-ig-a-eg-seg gg-ig-a-eg-seg--{cls}" data-seg="{i}" '
            f'd="{glyph.line_path(pts, close=True)}"/>'
        )
    line = glyph.line_path([(xs(m), ys(e)) for m, e in enumerate(elev)])
    refs = "".join(
        f'<line class="gg-ig-a-eg-ref" x1="0" x2="{W}" y1="{ys(v):.1f}" y2="{ys(v):.1f}"/>'
        for v in range(_CP_LO + 500, _CP_HI, 500)
    )
    svg = (
        f'<svg class="gg-eg-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">'
        f'{"".join(polys)}{refs}<path class="gg-ig-a-eg-case" d="{line}"/>'
        f'<path class="gg-ig-a-eg-hero" d="{line}"/></svg>'
    )
    yl = "".join(
        f'<span class="gg-ig-a-eg-yl{" gg-ig-a-eg-yl--top" if v == _CP_HI else ""}" '
        f'style="top:{(_CP_HI - v) / span * 100:.1f}%">{v:,}</span>'
        for v in range(_CP_LO + 500, _CP_HI + 1, 500)
    )
    peak = max(PROFILE, key=lambda p: p[1])
    px, py = peak[0] / max_mile * 100, (_CP_HI - peak[1]) / span * 100
    hot = [(PROFILE[i], PROFILE[i + 1]) for i in range(len(PROFILE) - 1)
           if _cp_class(PROFILE[i + 1][2]) == "brutal"]
    notes = [
        f'<span class="gg-ig-a-eg-note" style="left:{px:.1f}%;top:{py:.1f}%">Peak {peak[1]:,} ft</span>'
    ]
    for a, b in hot:
        hx = b[0] / max_mile * 100
        hy = (_CP_HI - max(a[1], b[1])) / span * 100
        notes.append(
            f'<span class="gg-ig-a-eg-note gg-ig-a-eg-note--l" style="left:{hx:.1f}%;top:{hy:.1f}%">'
            f'{abs(b[2])}% grade</span>'
        )
    num, chip, when = _cp_text(_CP_PEAK_MILE)
    dot = f'<i class="gg-eg-pt" data-eg-pt style="left:{px:.1f}%;top:{py:.1f}%"></i>'
    pw = glyph.scrub_wrap(
        "ch2-cp", svg + yl + "".join(notes) + dot, len(elev), _CP_PEAK_MILE,
        "Scrub the 100 miles", f"Mile {_CP_PEAK_MILE}: {num} ft, {chip}", mode="point",
    )
    ruler = "".join(
        f'<span class="gg-ig-a-eg-xt" style="left:{m / max_mile * 100:.1f}%">{m}{" mi" if m == max_mile else ""}</span>'
        for m in range(0, max_mile + 1, 20)
    )
    plot = (
        f'<div class="gg-ig-a-eg-plot">{pw}</div>'
        f'<div class="gg-ig-a-eg-ruler" aria-hidden="true">{ruler}</div>'
    )
    keys = "".join(
        f'<span class="gg-ig-a-eg-key" data-eg-cls="{k}"><i class="gg-ig-a-eg-sw gg-ig-a-eg-seg--{k}"></i>'
        f'{_e(n)} <b>{miles_by[k]} mi</b></span>'
        for k, n, _ in _CP_CLASSES
    )
    desc = (
        f"Elevation profile over {max_mile} miles, from {PROFILE[0][1]:,} ft up to a peak of "
        f"{peak[1]:,} ft at mile {peak[0]}, shaded by gradient class. "
        + " ".join(f"{n} {r}: {miles_by[k]} miles." for k, n, r in _CP_CLASSES)
    )
    classes = [k for k, _, _ in _CP_CLASSES]
    data = {
        "elev": elev,
        "seg": [_cp_seg(m) for m in range(len(elev))],
        "grade": [PROFILE[_cp_seg(m) + 1][2] for m in range(len(elev))],
        "cls": [classes.index(_cp_class(PROFILE[_cp_seg(m) + 1][2])) for m in range(len(elev))],
        "keys": classes,
        "names": [n for _, n, _ in _CP_CLASSES],
        "peak": _CP_PEAK_MILE, "lo": _CP_LO, "hi": _CP_HI,
    }
    card = glyph.glyph_card(
        "Course profile", glyph.readout(num, "ft", chip, when, keys),
        plot, data=data, describedby="gg-eg-cp-d", description=desc,
    )
    return _gpanel("cp", "CH 2 · COURSE", "Reading the Course Profile: Gradient by Segment", card, block)


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
        side = " gg-ig-a-fs__name--r" if x > 60 else ""
        label = f'<span class="gg-ig-a-fs__name{side}">{_e(name)}</span>'
        marks.append(
            f'<span class="gg-ig-a-fs__pt gg-ig-a-fs__pt--{_e(tier.lower())}"'
            f' data-tier="{_e(tier)}" style="left:{x:.1f}%;bottom:{y:.1f}%">{_e(tier[1:])}{label}</span>'
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
            f'<div class="gg-ig-a-fs__group gg-ig-a-fs__group--{tier.lower()}" data-tier="{tier}">'
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
    pills = [f'<button type="button" class="gg-ig-a-pick" data-tier="" aria-pressed="true">All {len(SCATTER)}</button>']
    for tier in ("T1", "T2", "T3", "T4"):
        k = sum(1 for s in SCATTER if s[3] == tier)
        pills.append(
            f'<button type="button" class="gg-ig-a-pick" data-tier="{tier}" aria-pressed="false">{tier} · {k}</button>'
        )
    pre = (
        f'<div class="gg-ig-a-ctl gg-ig-a-fs__ctl" role="group" aria-label="Show a tier">'
        f'{"".join(pills)}</div>'
    )
    return _panel("fs", "dark", "CH 2 · FIELDS",
                  "Field Size vs. Race Duration: What You’re Getting Into",
                  big, f"riders at the biggest start. {small} at the smallest.", body, block, pre=pre)


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

/* interactive controls (hidden until the script adds .is-live) */
.gg-ig-a-ctl{display:none;margin:0 0 22px}
.gg-ig-a.is-live .gg-ig-a-ctl{display:flex;flex-wrap:wrap;align-items:center;gap:10px 16px}
.gg-ig-a-pick{min-height:48px;padding:8px 18px;font-size:15px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;background:var(--a-bg);color:var(--a-ink);border:3px solid var(--a-line)}
.gg-ig-a-pick[aria-pressed="true"]{background:var(--a-ink);color:var(--a-bg)}

/* gear essentials: tickable */
.gg-ig-a-ge__count{gap:16px}
.gg-ig-a-ge__packed{font-family:var(--gg-font-data);font-size:22px;font-weight:700;font-variant-numeric:tabular-nums}
.gg-ig-a-ge__pips{display:flex;gap:6px}
.gg-ig-a-ge__pip{display:block;width:34px;height:14px;border:3px solid var(--gg-color-dark-brown);background:transparent}
.gg-ig-a-ge__pip.is-on{background:var(--gg-color-gold)}
button.gg-ig-a-ge__top{appearance:none;width:100%;border:0;border-radius:0;text-align:left;min-height:64px;margin:0;cursor:pointer;color:inherit}
.gg-ig-a-ge__name{flex:1;min-width:0}
.gg-ig-a-ge__box{flex:none;width:30px;height:30px;border:3px solid var(--gg-color-light-gold);position:relative}
.gg-ig-a-ge__card.is-packed .gg-ig-a-ge__box{background:var(--gg-color-light-gold)}
.gg-ig-a-ge__card.is-packed .gg-ig-a-ge__box::after{content:"";position:absolute;left:7px;top:1px;width:8px;height:15px;border:solid var(--gg-color-dark-brown);border-width:0 3px 3px 0;transform:rotate(45deg)}
.gg-ig-a.is-live .gg-ig-a-ge__card:not(.is-packed){background:var(--gg-color-warm-paper)}
.gg-ig-a.is-live .gg-ig-a-ge__card.is-packed{border-color:var(--gg-color-gold)}

/* rider grid: hours slider */
.gg-ig-a-rg__lab{font-family:var(--gg-font-data);font-size:14px;font-weight:700;letter-spacing:2px;text-transform:uppercase}
.gg-ig-a-rg__range{flex:1 1 220px;min-width:140px;max-width:420px;min-height:44px;margin:0;accent-color:var(--gg-color-light-gold);cursor:pointer}
.gg-ig-a-rg__range:focus-visible{outline:3px solid var(--a-focus);outline-offset:2px}
.gg-ig-a-rg__hrs{font-family:var(--gg-font-data);font-size:26px;font-weight:700;color:var(--gg-color-light-gold);min-width:5ch;font-variant-numeric:tabular-nums}
.gg-ig-a-rg__match{font-family:var(--gg-font-data);font-size:16px;font-weight:700;flex:1 1 200px}
.gg-ig-a.is-live .gg-ig-a-rg__card{transition:opacity .15s,transform .15s}
.gg-ig-a.is-live .gg-ig-a-rg__card.is-dim{opacity:.45}
.gg-ig-a.is-live .gg-ig-a-rg__card.is-lit{border-color:var(--gg-color-light-gold);outline:4px solid var(--gg-color-light-gold);outline-offset:3px;transform:translateY(-4px)}
@media(prefers-reduced-motion:reduce){.gg-ig-a.is-live .gg-ig-a-rg__card{transition:none}.gg-ig-a.is-live .gg-ig-a-rg__card.is-lit{transform:none}}

/* hierarchy: pick a factor */
.gg-ig-a-hs__ctl{display:none}
.gg-ig-a.is-live .gg-ig-a-hs__ctl{display:grid;gap:14px}
.gg-ig-a-hs__picks{display:flex;flex-wrap:wrap;gap:10px}
.gg-ig-a-hs__read{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 18px;padding:14px 16px;border:3px solid var(--gg-color-dark-brown);background:var(--gg-color-white)}
.gg-ig-a-hs__rshare{font-family:var(--gg-font-data);font-size:30px;font-weight:700;line-height:1;font-variant-numeric:tabular-nums}
.gg-ig-a-hs__rtxt{flex:1 1 260px;font-size:16px;line-height:1.45;min-width:0}
.gg-ig-a.is-live .gg-ig-a-hs__row{opacity:.5}
.gg-ig-a.is-live .gg-ig-a-hs__row.is-sel{opacity:1}
.gg-ig-a.is-live .gg-ig-a-hs__tip{display:none}

/* tier distribution: tap a tier */
.gg-ig-a-td__detail{display:none}
.gg-ig-a.is-live .gg-ig-a-td__detail{display:grid;grid-template-columns:auto 1fr;gap:4px 20px;align-items:baseline;padding:16px 18px;border:3px solid var(--gg-color-light-gold);background:var(--gg-color-near-black)}
.gg-ig-a-td__dtier{font-family:var(--gg-font-data);font-size:52px;font-weight:700;line-height:1;color:var(--gg-color-light-gold)}
.gg-ig-a-td__dcount{font-family:var(--gg-font-data);font-size:22px;font-weight:700;font-variant-numeric:tabular-nums}
.gg-ig-a-td__dtip{grid-column:1 / 3;font-size:18px;line-height:1.45;color:var(--gg-color-sand)}
button.gg-ig-a-td__row{appearance:none;display:grid;width:100%;margin:0;padding:6px 0;background:transparent;color:inherit;border:0;text-align:left;min-height:56px}
.gg-ig-a-td__row.is-top .gg-ig-a-td__tier{color:var(--gg-color-light-gold)}
.gg-ig-a.is-live button.gg-ig-a-td__row{opacity:.55;cursor:pointer}
.gg-ig-a.is-live button.gg-ig-a-td__row[aria-pressed="true"]{opacity:1}
.gg-ig-a.is-live button.gg-ig-a-td__row[aria-pressed="true"] .gg-ig-a-td__track{border-color:var(--gg-color-light-gold)}
.gg-ig-a.is-live button.gg-ig-a-td__row[aria-pressed="true"] .gg-ig-a-td__fill{background:var(--gg-color-light-gold)}
.gg-ig-a.is-live .gg-ig-a-td__tip{display:none}
@media(max-width:600px){.gg-ig-a-td__dtier{font-size:40px}.gg-ig-a-td__dtip{grid-column:1 / 3}}

/* field scatter: tier filter */
.gg-ig-a-fs__ctl{margin-bottom:44px}
.gg-ig-a-fs__name{display:none}
.gg-ig-a-fs__pt--t1 .gg-ig-a-fs__name{display:block}
.gg-ig-a-fs.is-sel .gg-ig-a-fs__name{display:none}
.gg-ig-a-fs.is-sel .gg-ig-a-fs__pt{opacity:.22}
.gg-ig-a-fs.is-sel .gg-ig-a-fs__group{opacity:.4}
.gg-ig-a-fs.is-sel-t1 .gg-ig-a-fs__pt--t1,.gg-ig-a-fs.is-sel-t2 .gg-ig-a-fs__pt--t2,.gg-ig-a-fs.is-sel-t3 .gg-ig-a-fs__pt--t3,.gg-ig-a-fs.is-sel-t4 .gg-ig-a-fs__pt--t4{opacity:1;z-index:2}
.gg-ig-a-fs.is-sel-t1 .gg-ig-a-fs__pt--t1 .gg-ig-a-fs__name,.gg-ig-a-fs.is-sel-t2 .gg-ig-a-fs__pt--t2 .gg-ig-a-fs__name,.gg-ig-a-fs.is-sel-t3 .gg-ig-a-fs__pt--t3 .gg-ig-a-fs__name,.gg-ig-a-fs.is-sel-t4 .gg-ig-a-fs__pt--t4 .gg-ig-a-fs__name{display:block}
.gg-ig-a-fs.is-sel-t1 .gg-ig-a-fs__group--t1,.gg-ig-a-fs.is-sel-t2 .gg-ig-a-fs__group--t2,.gg-ig-a-fs.is-sel-t3 .gg-ig-a-fs__group--t3,.gg-ig-a-fs.is-sel-t4 .gg-ig-a-fs__group--t4{opacity:1;border-color:var(--gg-color-light-gold)}

/* course profile: Glyph card */
.gg-ig-a-eg-body{background:var(--gg-color-warm-paper)}
.gg-ig-a-eg-body .gg-eg{margin:0}
.gg-ig-a-eg-body .gg-ig-a__cap{margin-top:20px!important}
.gg-ig-a-eg-plot{position:relative;height:230px}
.gg-ig-a-eg-plot .gg-eg-pw{position:absolute;inset:0}
.gg-ig-a-eg-seg{stroke:none}
.gg-ig-a-eg-seg--flat{fill:color-mix(in srgb,var(--eg-ink) 7%,var(--eg-card));background:color-mix(in srgb,var(--eg-ink) 7%,var(--eg-card))}
.gg-ig-a-eg-seg--mod{fill:color-mix(in srgb,var(--eg-ink) 15%,var(--eg-card));background:color-mix(in srgb,var(--eg-ink) 15%,var(--eg-card))}
.gg-ig-a-eg-seg--steep{fill:color-mix(in srgb,var(--eg-ink) 28%,var(--eg-card));background:color-mix(in srgb,var(--eg-ink) 28%,var(--eg-card))}
.gg-ig-a-eg-seg--brutal{fill:color-mix(in srgb,var(--eg-ride) 42%,var(--eg-card));background:color-mix(in srgb,var(--eg-ride) 42%,var(--eg-card))}
.gg-ig-a-cp .gg-eg.is-scrub .gg-ig-a-eg-seg{opacity:.5}
.gg-ig-a-cp .gg-eg.is-scrub .gg-ig-a-eg-seg.is-on{opacity:1}
.gg-ig-a-eg-ref{stroke:var(--eg-none);stroke-width:1;vector-effect:non-scaling-stroke}
.gg-ig-a-eg-case{fill:none;stroke:var(--eg-card);stroke-width:6.25;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}
.gg-ig-a-eg-hero{fill:none;stroke:var(--eg-ink);stroke-width:2.75;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}
.gg-ig-a-eg-yl{position:absolute;left:2px;transform:translateY(-100%);font-family:var(--eg-mono);font-size:11px;color:var(--eg-ink3);text-shadow:0 0 3px var(--eg-card),0 0 3px var(--eg-card)}
.gg-ig-a-eg-yl--top{transform:translateY(3px)}
.gg-ig-a-eg-note{position:absolute;transform:translate(-50%,-170%);font-family:var(--eg-mono);font-size:11px;font-weight:700;color:var(--eg-ink2);white-space:nowrap;pointer-events:none;text-shadow:0 0 3px var(--eg-card),0 0 3px var(--eg-card)}
.gg-ig-a-eg-note--l{transform:translate(-105%,-130%)}
.gg-ig-a-eg-ruler{position:relative;height:24px;border-top:1px solid var(--eg-ink3)}
.gg-ig-a-eg-xt{position:absolute;top:5px;transform:translateX(-50%);font-family:var(--eg-mono);font-size:11px;color:var(--eg-ink3);white-space:nowrap}
.gg-ig-a-eg-xt::before{content:"";position:absolute;left:50%;top:-6px;height:5px;border-left:1px solid var(--eg-ink3)}
.gg-ig-a-eg-xt:first-child{transform:none}
.gg-ig-a-eg-xt:last-child{transform:translateX(-100%)}
.gg-ig-a-eg-key{display:inline-flex;align-items:center;gap:6px;padding:4px 8px 4px 4px;border-radius:999px!important;font-family:var(--eg-mono);font-size:12px;color:var(--eg-ink2);border:1px solid transparent}
.gg-ig-a-eg-key b{color:var(--eg-ink)}
.gg-ig-a-eg-key.is-on{border-color:var(--eg-cobalt);color:var(--eg-ink)}
.gg-ig-a-eg-sw{display:inline-block;width:14px;height:14px;border-radius:3px!important;box-shadow:inset 0 0 0 1px var(--eg-none)!important}
@media(max-width:600px){.gg-ig-a-eg-body{padding:12px}.gg-ig-a-eg-plot{height:190px}.gg-ig-a-eg-note--l{display:none}.gg-ig-a-eg-xt:nth-last-child(2){display:none}}

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


JS = r"""
(function(){
  /* interactive panels announce themselves so their controls appear */
  document.querySelectorAll(".gg-ig-a").forEach(function(f){ f.classList.add("is-live"); });

  /* gear essentials: tick off what is packed */
  document.querySelectorAll(".gg-ig-a-ge").forEach(function(root){
    var cards=root.querySelectorAll(".gg-ig-a-ge__card");
    var out=root.querySelector(".gg-ig-a-ge__packed");
    var pips=root.querySelectorAll(".gg-ig-a-ge__pip");
    function count(){
      var n=0;
      cards.forEach(function(c){
        if(c.classList.contains("is-packed")){ n++; }
      });
      pips.forEach(function(p,i){ p.classList.toggle("is-on",i<n); });
      if(out){ out.textContent=n+" of "+cards.length+" packed"; }
    }
    cards.forEach(function(c){
      var b=c.querySelector("button");
      if(!b){ return; }
      b.addEventListener("click",function(){
        var on=!c.classList.contains("is-packed");
        c.classList.toggle("is-packed",on);
        b.setAttribute("aria-pressed",on?"true":"false");
        count();
      });
    });
  });

  /* rider grid: light the profiles that cover your hours */
  document.querySelectorAll(".gg-ig-a-rg").forEach(function(root){
    var inp=root.querySelector(".gg-ig-a-rg__range");
    var hrs=root.querySelector(".gg-ig-a-rg__hrs");
    var match=root.querySelector(".gg-ig-a-rg__match");
    var cards=root.querySelectorAll(".gg-ig-a-rg__card");
    if(!inp){ return; }
    function show(){
      var h=parseFloat(inp.value)||0;
      var names=[];
      cards.forEach(function(c){
        var lo=parseFloat(c.getAttribute("data-lo")), hi=parseFloat(c.getAttribute("data-hi"));
        var on=h>=lo&&h<=hi;
        c.classList.toggle("is-lit",on);
        c.classList.toggle("is-dim",!on);
        if(on){ names.push(c.getAttribute("data-name")); }
      });
      if(hrs){ hrs.textContent=h+" hrs"; }
      if(match){ match.textContent=names.length?names.join(" or "):"Below the first profile"; }
    }
    inp.addEventListener("input",show);
    show();
  });

  /* hierarchy of speed: pick a factor, read its share */
  document.querySelectorAll(".gg-ig-a-hs").forEach(function(root){
    var picks=root.querySelectorAll(".gg-ig-a-pick");
    var rows=root.querySelectorAll(".gg-ig-a-hs__row");
    var share=root.querySelector(".gg-ig-a-hs__rshare");
    var txt=root.querySelector(".gg-ig-a-hs__rtxt");
    var ctl=root.querySelector(".gg-ig-a-hs__ctl");
    if(!ctl||!picks.length){ return; }
    var min=parseFloat(ctl.getAttribute("data-min"))||1;
    var smallest=picks[picks.length-1].textContent;
    function pick(i){
      var b=picks[i];
      var v=parseFloat(b.getAttribute("data-share"));
      picks.forEach(function(o,k){ o.setAttribute("aria-pressed",k===i?"true":"false"); });
      rows.forEach(function(r,k){ r.classList.toggle("is-sel",k===i); });
      var r=v/min;
      var rs=r>=10?String(Math.round(r)):String(Math.round(r*10)/10);
      if(share){ share.textContent=v+"%"; }
      if(txt){
        txt.textContent=b.textContent+" is "+v+"% of speed"+(r>1?", "+rs+"x the weight of "+smallest+". ":". ")+b.getAttribute("data-tip");
      }
    }
    picks.forEach(function(b,i){ b.addEventListener("click",function(){ pick(i); }); });
    pick(0);
  });

  /* tier distribution: tap a tier */
  document.querySelectorAll(".gg-ig-a-td").forEach(function(root){
    var rows=root.querySelectorAll("button.gg-ig-a-td__row");
    var box=root.querySelector(".gg-ig-a-td__detail");
    if(!box||!rows.length){ return; }
    var total=parseFloat(box.getAttribute("data-total"))||1;
    function pick(b){
      rows.forEach(function(o){ o.setAttribute("aria-pressed",o===b?"true":"false"); });
      box.querySelector(".gg-ig-a-td__dtier").textContent=b.getAttribute("data-tier");
      box.querySelector(".gg-ig-a-td__dcount").textContent=b.getAttribute("data-count")+" of "+total+" races, "+b.getAttribute("data-pct")+"%";
      box.querySelector(".gg-ig-a-td__dtip").textContent=b.getAttribute("data-tip");
    }
    rows.forEach(function(b){ b.addEventListener("click",function(){ pick(b); }); });
    pick(rows[0]);
  });

  /* field scatter: tier filter */
  document.querySelectorAll(".gg-ig-a-fs").forEach(function(root){
    var btns=root.querySelectorAll(".gg-ig-a-pick");
    btns.forEach(function(b){
      b.addEventListener("click",function(){
        var t=(b.getAttribute("data-tier")||"").toLowerCase();
        ["t1","t2","t3","t4"].forEach(function(k){ root.classList.remove("is-sel-"+k); });
        root.classList.toggle("is-sel",t!=="");
        if(t){ root.classList.add("is-sel-"+t); }
        btns.forEach(function(o){ o.setAttribute("aria-pressed",o===b?"true":"false"); });
      });
    });
  });

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
          if(ar){ ar.textContent=on?(dir==="asc"?"\u2191":"\u2193"):""; }
        });
        ths.forEach(function(t){
          if(parseInt(t.getAttribute("data-col"),10)===col){ t.setAttribute("aria-sort",dir==="asc"?"ascending":"descending"); }
          else { t.removeAttribute("aria-sort"); }
        });
      });
    });
  });
})();

/* course profile: scrub the miles */
GGEG.register("ch2-cp", function (i, c) {
  var d = c.data, st = c.state;
  var e = d.elev[i], g = d.grade[i], k = d.cls[i], s = d.seg[i];
  var txt = String(e).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  var chip = (g > 0 ? "▲ " : (g < 0 ? "▼ " : "")) + Math.abs(g) + "% · " + d.names[k];
  c.set("num", txt);
  c.set("chip", chip);
  c.set("when", "Mile " + i + (i === d.peak ? " · peak" : ""));
  var pt = c.q("[data-eg-pt]");
  if (pt) { pt.style.left = (i / (c.n - 1) * 100) + "%"; pt.style.top = ((d.hi - e) / (d.hi - d.lo) * 100) + "%"; }
  var j;
  for (j = 0; j < st.segs.length; j++) st.segs[j].classList.toggle("is-on", j === s);
  for (j = 0; j < st.keys.length; j++) st.keys[j].classList.toggle("is-on", st.keys[j].getAttribute("data-eg-cls") === d.keys[k]);
  return "Mile " + i + ": " + txt + " ft, " + chip;
}, function (c) {
  c.state.segs = c.card.querySelectorAll("[data-seg]");
  c.state.keys = c.card.querySelectorAll("[data-eg-cls]");
});
"""
