#!/usr/bin/env python3
"""Generate /race/{slug}/training-plan/ pages — northstar Phase 2.

Commercial-intent SEO: targets "{race} training plan" queries, the space
where competitors fight generic head terms and we have 757 race-specific
data assets. Anti-shill structure: the page IS the free preparation guide
(demand profile, training shape, phase timeline, fueling math, FAQ) and the
product is the personalization of it.

Every number on the page is derived from race JSON + race-pack data — no
fabricated claims. FAQ answers come from the same scoring data behind the
rating.

Usage:
    python3 wordpress/generate_training_plan_pages.py --all
    python3 wordpress/generate_training_plan_pages.py unbound-200

Deploy:
    python3 scripts/push_wordpress.py --sync-plan-pages
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from brand_tokens import (
    get_tokens_css,
    get_font_face_css,
    get_preload_hints,
    get_ga4_head_snippet,
)
from shared_header import get_site_header_html, get_site_header_css, get_site_header_js
from shared_footer import get_mega_footer_html
from cookie_consent import get_consent_banner_html
from generate_neo_brutalist import (
    parse_event_dates,
    _safe_json_for_script,
    WORKOUT_SHOWCASE,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
RACE_PACKS_DIR = PROJECT_ROOT / "web" / "race-packs"
OUTPUT_DIR = PROJECT_ROOT / "wordpress" / "output" / "training-plan"

SITE_BASE_URL = "https://gravelgodcycling.com"
QUESTIONNAIRE_URL = f"{SITE_BASE_URL}/questionnaire/"

DIM_LABELS = {
    "durability": "Durability",
    "climbing": "Climbing",
    "vo2_power": "VO2 Power",
    "threshold": "Threshold",
    "technical": "Technical",
    "heat_resilience": "Heat",
    "altitude": "Altitude",
    "race_specificity": "Race Specificity",
}

# What a top demand means for training emphasis — used in "what it takes"
DEMAND_TRAINING = {
    "durability": "long rides that build late-race resilience — the final "
                  "third of this race is decided by who prepared for hour "
                  "four, not who has the best one-hour power",
    "climbing": "sustained climbing strength: low-cadence work, threshold "
                "repeats, and long rides with real elevation",
    "vo2_power": "repeated hard surges — VO2 intervals that prepare you for "
                 "attacks, rollers, and group splits",
    "threshold": "time at threshold: the steady, uncomfortable pace this "
                 "course holds you at for long stretches",
    "technical": "bike-handling under fatigue — skills work belongs in the "
                 "plan, not just fitness",
    "heat_resilience": "heat preparation: acclimatization protocols in the "
                       "final 2-3 weeks plus a fueling plan that survives "
                       "high sweat rates",
    "altitude": "altitude strategy: arrive early or arrive fit — the plan "
                "has to pick one and prepare for it",
    "race_specificity": "race-simulation days that rehearse the exact "
                        "demands of this course — terrain, fueling, pacing",
}


def esc(text) -> str:
    if text is None or text == "":
        return ""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def load_race(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("race", data)


def load_pack(slug: str) -> dict:
    p = RACE_PACKS_DIR / f"{slug}.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def est_hours(rd: dict) -> float:
    """Mid-pack duration estimate: 14 mph baseline, slowed by climbing."""
    vitals = rd.get("vitals", {})
    dist = vitals.get("distance_mi") or 0
    try:
        dist = float(dist)
    except (TypeError, ValueError):
        return 0
    if dist <= 0:
        return 0
    elev = vitals.get("elevation_ft") or 0
    try:
        elev = float(elev)
    except (TypeError, ValueError):
        elev = 0
    speed = 14.0
    if dist > 0 and elev / dist > 80:   # >80 ft/mi is a climbing race
        speed = 12.0
    if dist > 0 and elev / dist > 120:
        speed = 10.5
    return dist / speed


def fueling_numbers(hours: float) -> dict:
    if hours <= 0:
        return {}
    return {
        "hours": round(hours, 1),
        "carbs_low": int(hours * 60),
        "carbs_high": int(hours * 90),
        "cals": int(hours * 250 + 200),
        "bottles": max(2, int(hours * 0.75)),
    }


# ── Sections ─────────────────────────────────────────────────


def build_hero(rd: dict, pack: dict) -> str:
    name = rd["name"]
    slug = rd["slug"]
    vitals = rd.get("vitals", {})
    rating = rd.get("gravel_god_rating", {})
    tier = rating.get("tier", "")
    score = rating.get("overall_score", "")

    facts = []
    if vitals.get("distance_mi"):
        facts.append(f"{vitals['distance_mi']} mi")
    if vitals.get("elevation_ft"):
        try:
            facts.append(f"{int(float(vitals['elevation_ft'])):,} ft of climbing")
        except (TypeError, ValueError):
            pass
    if vitals.get("date_specific"):
        facts.append(esc(vitals["date_specific"]))
    if tier and score:
        facts.append(f"Tier {tier} &middot; GG Score {score}")
    facts_line = " &middot; ".join(facts)

    cd_start, _ = parse_event_dates(vitals.get("date_specific", ""))
    date_attr = f' data-race-date="{esc(cd_start)}"' if cd_start else ""

    return f'''<section class="gg-tpp-hero"{date_attr} id="tpp-hero">
  <p class="gg-tpp-kicker">TRAINING PLAN</p>
  <h1>How to Train for {esc(name)}</h1>
  <p class="gg-tpp-facts">{facts_line}</p>
  <p class="gg-tpp-lede">This is what {esc(name)} actually asks of you &mdash;
  from the same data behind our rating. The whole preparation picture is on
  this page, free. If you want it built around your hours, your schedule,
  and your fitness, that&rsquo;s what the custom plan is for.</p>
  <div class="gg-tpp-hero-cta">
    <a href="{QUESTIONNAIRE_URL}?race={esc(slug)}" class="gg-btn" data-cta="tpp_hero_build" id="gg-tpp-hero-cta">BUILD MY PLAN &mdash; $15/WK</a>
    <span class="gg-tpp-countdown" id="gg-tpp-countdown"></span>
  </div>
</section>'''


def build_demands(rd: dict, pack: dict) -> str:
    demands = pack.get("demands", {})
    if not demands:
        return ""
    bars = []
    for key in DIM_LABELS:
        v = demands.get(key, 0)
        bars.append(
            f'<div class="gg-tpp-demand">'
            f'<span class="gg-tpp-demand-label">{esc(DIM_LABELS[key])}</span>'
            f'<div class="gg-tpp-demand-track"><div class="gg-tpp-demand-fill" style="width:{v * 10}%"></div></div>'
            f'<span class="gg-tpp-demand-score">{esc(v)}</span></div>'
        )
    top3 = sorted(((k, v) for k, v in demands.items() if k in DIM_LABELS),
                  key=lambda kv: kv[1], reverse=True)[:3]
    emphasis = "".join(
        f"<li><strong>{esc(DIM_LABELS[k])} ({v}/10):</strong> "
        f"{esc(DEMAND_TRAINING[k])}.</li>"
        for k, v in top3 if v > 0)

    return f'''<section class="gg-tpp-section" id="demands">
  <h2>What {esc(rd["name"])} Demands</h2>
  <div class="gg-tpp-demand-grid">
    {"".join(bars)}
  </div>
  <h3>So your training has to prioritize:</h3>
  <ul class="gg-tpp-emphasis">{emphasis}</ul>
</section>'''


def build_workouts(rd: dict, pack: dict) -> str:
    """Key workout types from the race's archetype mapping."""
    cards = []
    for tc in pack.get("top_categories", [])[:6]:
        if len(cards) >= 3:
            break
        for w in tc.get("workouts", []):
            sc = WORKOUT_SHOWCASE.get(w)
            if sc:
                cards.append(
                    f'<div class="gg-tpp-workout">'
                    f'<h4>{esc(w.replace("_", " "))}</h4>'
                    f'<p class="gg-tpp-workout-cat">{esc(tc["category"].replace("_", " ").upper())}</p>'
                    f'<p>{esc(sc.get("why", sc.get("description", "")))[:220]}</p>'
                    f'</div>')
                break
    if not cards:
        return ""
    return f'''<section class="gg-tpp-section" id="key-workouts">
  <h2>The Key Workouts</h2>
  <p>Selected from our archetype library against this course&rsquo;s demand
  profile. The race page has <a href="/race/{esc(rd["slug"])}/#train-for-race">the
  full set with execution protocols</a>.</p>
  <div class="gg-tpp-workout-grid">
    {"".join(cards)}
  </div>
</section>'''


def build_timeline(rd: dict) -> str:
    name = esc(rd["name"])
    rows = [
        ("16+ weeks out", "Base", "Aerobic volume, strength foundation, long-ride habit. "
         "Boring on purpose. This is where the race is actually won."),
        ("10&ndash;15 weeks out", "Build", "Intensity arrives: threshold and VO2 work layered "
         "onto the base. Long rides start resembling race demands."),
        ("4&ndash;9 weeks out", "Peak", "Race-specific simulation: course-profile long rides, "
         "fueling rehearsal at race intensity, equipment locked in."),
        ("2&ndash;3 weeks out", "Taper", "Volume drops, intensity stays. You will feel like "
         "you&rsquo;re losing fitness. You aren&rsquo;t."),
        ("Race week", "Race", "Sleep, carbs, logistics. Nothing new. "
         "The work is done."),
    ]
    body = "".join(
        f'<tr><td class="gg-tpp-tl-when">{w}</td>'
        f'<td class="gg-tpp-tl-phase">{p}</td><td>{d}</td></tr>'
        for w, p, d in rows)
    return f'''<section class="gg-tpp-section" id="timeline">
  <h2>The Timeline</h2>
  <p>A proper {name} build is 12&ndash;16 weeks. Less than 8 and you&rsquo;re
  maintaining fitness, not building it &mdash; still worth structuring, but
  be honest about what it is.</p>
  <table class="gg-tpp-timeline">
    <thead><tr><th>When</th><th>Phase</th><th>What matters</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</section>'''


def build_fueling(rd: dict) -> str:
    hours = est_hours(rd)
    f = fueling_numbers(hours)
    if not f:
        return ""
    name = esc(rd["name"])
    return f'''<section class="gg-tpp-section" id="fueling">
  <h2>The Fueling Math</h2>
  <p>At a mid-pack pace, {name} is roughly a <strong>{f["hours"]}-hour</strong>
  effort. That means:</p>
  <ul class="gg-tpp-fueling">
    <li><strong>{f["carbs_low"]}&ndash;{f["carbs_high"]}g of carbohydrate</strong> during the race (60&ndash;90g/hr)</li>
    <li><strong>~{f["cals"]:,} calories</strong> burned &mdash; you cannot eat it all back; you can only stay ahead of the bonk</li>
    <li><strong>{f["bottles"]}+ bottles</strong> minimum, more in heat</li>
  </ul>
  <p>Gut training starts 6+ weeks out &mdash; race-day fueling at race
  intensity is a trained skill, not a plan you read once. The free
  <a href="/race/{esc(rd["slug"])}/prep-kit/" data-cta="tpp_prep_kit">{name} prep kit</a>
  has the full protocol and a personalized fueling calculator.</p>
</section>'''


def load_sku_link(slug: str) -> dict:
    """TP static-plan links for this race's SKU family (northstar P3.1).

    Reads data/tp-sku-map.json (race → family, from assign_tp_skus.py) and
    data/tp-sku-links.json (family → {weeks: TP url}, filled as the TP
    marketplace plans get published). Returns {} until links exist, so the
    section renders nothing — safe to ship ahead of the TP builds.
    """
    try:
        sku_map = json.loads((PROJECT_ROOT / "data" / "tp-sku-map.json").read_text())
        links = json.loads((PROJECT_ROOT / "data" / "tp-sku-links.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    family = sku_map.get(slug)
    if not family:
        return {}
    fam_links = {w: u for w, u in links.get(family, {}).items() if u}
    return {"family": family, "links": fam_links} if fam_links else {}


def build_static_plan(rd: dict) -> str:
    sku = load_sku_link(rd["slug"])
    if not sku:
        return ""
    fam_label = sku["family"].replace("-", " ").title()
    links = "\n    ".join(
        f'<a href="{esc(u)}" class="gg-btn gg-btn--outline" data-cta="tpp_static_sku" rel="noopener" target="_blank">{w}-WEEK PLAN &rarr;</a>'
        for w, u in sorted(sku["links"].items(), key=lambda kv: int(kv[0])))
    return f"""<section class="gg-tpp-section" id="ready-made">
  <h2>Not Ready for Custom? The Ready-Made Version.</h2>
  <p>{esc(rd["name"])} maps to our <strong>{esc(fam_label)}</strong> family
  &mdash; a structured plan built from the same workout library, sold on
  TrainingPeaks. Fixed structure, lower price. The custom plan adapts all of
  it to your hours and schedule; this one asks you to adapt to it.</p>
  <div class="gg-tpp-cta-row">
    {links}
  </div>
</section>"""


def build_faq(rd: dict, pack: dict) -> tuple[str, list]:
    """Race-specific FAQ + (question, answer) pairs for schema."""
    name = rd["name"]
    vitals = rd.get("vitals", {})
    rating = rd.get("gravel_god_rating", {})
    tier = rating.get("tier")
    hours = est_hours(rd)
    demands = pack.get("demands", {})

    qa = []
    qa.append((
        f"How long do I need to train for {name}?",
        "12-16 weeks of structured training is the honest answer for a "
        "strong result. 8 weeks is workable if you have an aerobic base. "
        "Under 6 weeks, focus on pacing, fueling, and equipment — fitness "
        "is mostly fixed at that point."))

    dist = vitals.get("distance_mi")
    if dist and hours:
        qa.append((
            f"How many hours a week do I need to train for {name}?",
            f"Most riders prepare for this distance ({dist} miles, roughly "
            f"{round(hours, 1)} hours at mid-pack pace) on 6-10 hours a "
            "week. The non-negotiable is the weekly long ride — that's "
            "where race durability comes from. The rest is making your "
            "limited hours specific."))

    qa.append((
        f"Do I need a power meter to train for {name}?",
        "No. Power makes training more precise, but heart rate or RPE-based "
        "plans work. What matters is structure: easy days actually easy, "
        "hard days actually hard."))

    if demands:
        top = max((k for k in demands if k in DIM_LABELS),
                  key=lambda k: demands[k], default=None)
        if top:
            qa.append((
                f"What makes {name} hard?",
                f"{DIM_LABELS[top]} is the defining demand "
                f"({demands[top]}/10 on our demand profile). Training that "
                f"ignores it produces a fit rider who still has a bad day. "
                f"Specifically: {DEMAND_TRAINING[top]}."))

    if tier:
        beginner = ("Yes, with honest pacing. " if str(tier) in ("3", "4")
                    else "It's a serious target for a first-timer. ")
        qa.append((
            f"Is {name} suitable for beginners?",
            beginner + "The course doesn't care about your experience "
            "level — it cares whether you prepared for its specific "
            "demands. Structure beats heroics."))

    items = "".join(
        f'<details class="gg-tpp-faq-item"><summary>{esc(q)}</summary>'
        f'<p>{esc(a)}</p></details>'
        for q, a in qa)
    html = f'''<section class="gg-tpp-section" id="faq">
  <h2>Questions</h2>
  {items}
</section>'''
    return html, qa


def build_cta(rd: dict) -> str:
    name = esc(rd["name"])
    slug = esc(rd["slug"])
    return f'''<section class="gg-tpp-section gg-tpp-cta-section" id="get-plan">
  <h2>Everything above, built around your life.</h2>
  <p>The free version of preparing for {name} is this page plus the
  <a href="/race/{slug}/prep-kit/" data-cta="tpp_cta_kit">prep kit</a>.
  The custom version is a plan built from your hours, your schedule, your
  fitness markers, and this exact course &mdash; delivered to your
  TrainingPeaks calendar the same day.</p>
  <div class="gg-tpp-cta-row">
    <a href="{QUESTIONNAIRE_URL}?race={slug}" class="gg-btn" data-cta="tpp_footer_build" id="gg-tpp-footer-cta">BUILD MY PLAN &mdash; $15/WK</a>
    <a href="/race/{slug}/" class="gg-btn gg-btn--outline" data-cta="tpp_race_page">READ THE {name.upper()} REVIEW</a>
  </div>
  <p class="gg-tpp-guarantee">7-day full refund. Same-day delivery. $249 cap.</p>
</section>'''


def build_json_ld(rd: dict, qa: list, canonical: str) -> str:
    name = rd["name"]
    data = [
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in qa
            ],
        },
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": f"How to Train for {name}",
            "description": f"Training plan guide for {name}: demand profile, key workouts, timeline, and fueling math.",
            "url": canonical,
            "author": {"@type": "Person", "name": "Matti Rowe"},
            "publisher": {"@type": "Organization", "name": "Gravel God Cycling"},
            "breadcrumb": {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Races", "item": f"{SITE_BASE_URL}/race/"},
                    {"@type": "ListItem", "position": 2, "name": name, "item": f"{SITE_BASE_URL}/race/{rd['slug']}/"},
                    {"@type": "ListItem", "position": 3, "name": "Training Plan", "item": canonical},
                ],
            },
        },
    ]
    return _safe_json_for_script(data, ensure_ascii=False, separators=(",", ":"))


def build_css() -> str:
    return '''
.gg-tpp-page { max-width: 860px; margin: 0 auto; padding: 0 20px 60px; font-family: var(--gg-font-editorial); color: var(--gg-color-primary-brown); }
.gg-tpp-kicker { font-family: var(--gg-font-data); font-size: 11px; font-weight: 700; letter-spacing: 3px; color: var(--gg-color-secondary-brown); margin: 28px 0 8px; }
.gg-tpp-hero h1 { font-family: var(--gg-font-data); font-size: clamp(26px, 5vw, 40px); text-transform: uppercase; letter-spacing: 0.03em; line-height: 1.15; margin: 0 0 10px; color: #000; }
.gg-tpp-facts { font-family: var(--gg-font-data); font-size: 12px; letter-spacing: 1px; text-transform: uppercase; color: var(--gg-color-secondary-brown); margin: 0 0 16px; }
.gg-tpp-lede { font-size: 16px; line-height: 1.65; max-width: 640px; margin: 0 0 18px; }
.gg-tpp-hero-cta { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; margin-bottom: 8px; }
.gg-tpp-countdown { font-family: var(--gg-font-data); font-size: 11px; font-weight: 700; letter-spacing: 2px; color: var(--gg-color-teal); }
.gg-btn { display: inline-block; font-family: var(--gg-font-data); font-size: 13px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; text-decoration: none; padding: 13px 26px; background: var(--gg-color-primary-brown); color: var(--gg-color-warm-paper); border: 3px solid #000; }
.gg-btn:hover { background: var(--gg-color-teal); }
.gg-btn--outline { background: transparent; color: var(--gg-color-teal); border-color: var(--gg-color-teal); }
.gg-btn--outline:hover { background: var(--gg-color-teal); color: #fff; }
.gg-tpp-section { margin: 44px 0; padding-top: 28px; border-top: 3px solid #000; }
.gg-tpp-section h2 { font-family: var(--gg-font-data); font-size: 20px; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 14px; color: #000; }
.gg-tpp-section h3 { font-family: var(--gg-font-data); font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin: 22px 0 10px; }
.gg-tpp-demand-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 28px; }
.gg-tpp-demand { display: flex; align-items: center; gap: 8px; }
.gg-tpp-demand-label { font-family: var(--gg-font-data); font-size: 11px; width: 110px; min-width: 90px; text-transform: uppercase; letter-spacing: 1px; }
.gg-tpp-demand-track { flex: 1; height: 7px; background: var(--gg-color-cream); border: 1px solid var(--gg-color-tan); }
.gg-tpp-demand-fill { height: 100%; background: var(--gg-color-teal); }
.gg-tpp-demand-score { font-family: var(--gg-font-data); font-size: 11px; width: 18px; text-align: right; }
.gg-tpp-emphasis li { margin-bottom: 10px; line-height: 1.6; }
.gg-tpp-workout-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }
.gg-tpp-workout { border: 3px solid #000; background: var(--gg-color-warm-paper); padding: 16px; }
.gg-tpp-workout h4 { font-family: var(--gg-font-data); font-size: 15px; margin: 0 0 4px; text-transform: uppercase; }
.gg-tpp-workout-cat { font-family: var(--gg-font-data); font-size: 10px; letter-spacing: 2px; color: var(--gg-color-teal); margin: 0 0 10px; }
.gg-tpp-workout p { font-size: 13px; line-height: 1.55; margin: 0; }
.gg-tpp-timeline { width: 100%; border-collapse: collapse; font-size: 14px; }
.gg-tpp-timeline th { font-family: var(--gg-font-data); font-size: 11px; text-transform: uppercase; letter-spacing: 1px; text-align: left; border-bottom: 3px solid #000; padding: 8px 10px 8px 0; }
.gg-tpp-timeline td { border-bottom: 1px solid var(--gg-color-tan); padding: 12px 10px 12px 0; vertical-align: top; line-height: 1.55; }
.gg-tpp-tl-when { font-family: var(--gg-font-data); font-size: 12px; white-space: nowrap; }
.gg-tpp-tl-phase { font-family: var(--gg-font-data); font-weight: 700; text-transform: uppercase; font-size: 12px; color: var(--gg-color-teal); }
.gg-tpp-fueling li { margin-bottom: 8px; line-height: 1.6; }
.gg-tpp-faq-item { border: 2px solid #000; margin-bottom: 10px; background: #fff; }
.gg-tpp-faq-item summary { font-family: var(--gg-font-data); font-size: 14px; font-weight: 600; padding: 14px 16px; cursor: pointer; }
.gg-tpp-faq-item p { padding: 0 16px 14px; margin: 0; line-height: 1.6; }
.gg-tpp-cta-section { background: var(--gg-color-warm-paper); border: 4px solid #000; padding: 28px; }
.gg-tpp-cta-row { display: flex; gap: 12px; flex-wrap: wrap; margin: 18px 0 10px; }
.gg-tpp-guarantee { font-family: var(--gg-font-data); font-size: 11px; letter-spacing: 1px; text-transform: uppercase; color: var(--gg-color-secondary-brown); margin: 0; }
a { color: var(--gg-color-teal); }
@media (max-width: 640px) { .gg-tpp-demand-grid { grid-template-columns: 1fr; } .gg-tpp-cta-row { flex-direction: column; } .gg-tpp-cta-row .gg-btn { text-align: center; } }
'''


def build_js() -> str:
    """Countdown + dynamic price (mirrors prep strip / server pricing)."""
    return '''
(function() {
  var hero = document.getElementById('tpp-hero');
  if (!hero) return;
  var dateStr = hero.getAttribute('data-race-date');
  if (!dateStr) return;
  var race = new Date(dateStr + 'T00:00:00');
  if (isNaN(race.getTime())) return;
  var today = new Date(); today.setHours(0, 0, 0, 0);
  var days = Math.ceil((race - today) / 86400000);
  if (days <= 7) return;
  var weeks = Math.max(4, Math.ceil(days / 7));
  var price = Math.min(weeks * 15, 249);
  var cd = document.getElementById('gg-tpp-countdown');
  if (cd) cd.textContent = weeks + ' WEEKS UNTIL RACE DAY';
  ['gg-tpp-hero-cta', 'gg-tpp-footer-cta'].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.textContent = 'BUILD MY ' + weeks + '-WEEK PLAN — $' + price;
  });
})();
(function() {
  if (typeof gtag !== 'function') return;
  document.querySelectorAll('a[data-cta]').forEach(function(link) {
    link.addEventListener('click', function() {
      gtag('event', 'cta_click', {
        cta_type: this.dataset.cta.indexOf('build') !== -1 ? 'build_plan' : 'other',
        cta_text: this.textContent.trim().slice(0, 50),
        cta_section: 'training_plan_page',
        cta_href: this.getAttribute('href') || ''
      });
    });
  });
})();
'''


def generate_page(rd: dict, pack: dict) -> str:
    slug = rd["slug"]
    name = rd["name"]
    canonical = f"{SITE_BASE_URL}/race/{slug}/training-plan/"

    hero = build_hero(rd, pack)
    demands = build_demands(rd, pack)
    workouts = build_workouts(rd, pack)
    timeline = build_timeline(rd)
    fueling = build_fueling(rd)
    static_plan = build_static_plan(rd)
    faq_html, qa = build_faq(rd, pack)
    cta = build_cta(rd)
    jsonld = build_json_ld(rd, qa, canonical)

    title = f"{name} Training Plan: How to Train for {name} | Gravel God"
    meta = (f"How to train for {name}: demand profile, key workouts, "
            f"12-16 week timeline, and fueling math — from the race data "
            f"behind our rating. Custom plans from $15/week.")

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(meta)}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(meta)}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:type" content="article">
  <meta property="og:image" content="{SITE_BASE_URL}/og/{esc(slug)}.jpg">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">
  <script type="application/ld+json">{jsonld}</script>
  {get_preload_hints("/race/assets/fonts")}
  <style>
{get_font_face_css("/race/assets/fonts")}
{get_tokens_css()}
{get_site_header_css()}
{build_css()}
  </style>
  {get_ga4_head_snippet()}
</head>
<body>
{get_site_header_html()}
<div class="gg-tpp-page">
{hero}
{demands}
{workouts}
{timeline}
{fueling}
{static_plan}
{faq_html}
{cta}
</div>
{get_mega_footer_html()}
<script>
{get_site_header_js()}
{build_js()}
</script>
{get_consent_banner_html()}
</body>
</html>'''


# SITE-SYNC S3 (docs/specs/SITE_SYNC_SPEC.md): fabricated race pages removed
# 2026-07, 301-redirected to state/region best-of hubs. race-data/*.json is
# KEPT for the audit trail but must never regenerate a page.
REMOVED_FABRICATED_SLUGS = {
    "black-forest-gravel",
    "ozark-gravel",
    "pirate-cycling-league-gravel",
    "grasslands-100",
    "balkan-gravel",
    "greek-gravel",
    "natchez-trace-gran-fondo",
    "walburg-dirty-30",
    "flint-hills-death-ride",
    "kal-tour-dirty-100",
}


def main():
    parser = argparse.ArgumentParser(description="Generate training-plan SEO pages")
    parser.add_argument("slug", nargs="?", help="Single race slug")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    files = ([RACE_DATA_DIR / f"{args.slug}.json"] if args.slug
             else [f for f in sorted(RACE_DATA_DIR.glob("*.json"))
                   if f.stem not in REMOVED_FABRICATED_SLUGS])

    done = skipped = 0
    for f in files:
        rd = load_race(f)
        rd.setdefault("slug", f.stem)
        pack = load_pack(f.stem)
        if not pack.get("demands"):
            skipped += 1
            continue
        html = generate_page(rd, pack)
        (OUTPUT_DIR / f"{f.stem}.html").write_text(html, encoding="utf-8")
        done += 1

    print(f"Generated {done} training-plan pages ({skipped} skipped — no race pack)")


if __name__ == "__main__":
    main()
