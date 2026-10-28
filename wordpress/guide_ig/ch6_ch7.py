"""Handbook charts for chapters 6 and 7 (race day + race week), rebuilt 2026-10-28.

Assets: ch6-three-acts, ch6-psych-phases, ch7-race-week-countdown, ch7-weather-matrix.
All selectors use the .gg-ig-d- prefix.
"""
import html as _html


def _e(value) -> str:
    """HTML-escape any value. 0 prints as 0."""
    return _html.escape(str(value), quote=True)


def _shell(tone: str, asset_id: str, alt: str, eyebrow: str, title: str, body: str,
           caption: str) -> str:
    cap = f'<p class="gg-ig-d-cap">{_e(caption)}</p>' if caption else ""
    aria = f' aria-label="{_e(alt)}"' if alt else ""
    return (
        f'<figure class="gg-ig-d gg-ig-d--{tone}" data-asset-id="{_e(asset_id)}"'
        f' role="figure"{aria}>'
        f'<header class="gg-ig-d-head">'
        f'<span class="gg-ig-d-eyebrow">{_e(eyebrow)}</span>'
        f'<h3 class="gg-ig-d-title">{_e(title)}</h3></header>'
        f'{body}{cap}</figure>'
    )


# ── Chapter 6: three acts ───────────────────────────────────

ACTS = [
    ("ACT 1", "Restraint", "0–40%", 40, "M 0,30 Q 30,28 60,25 Q 90,22 120,20",
     ["Hold 10% below target power", "Ignore early surges", "Settle into rhythm",
      "Bank nothing — save everything"]),
    ("ACT 2", "Resilience", "40–75%", 35, "M 0,20 Q 30,15 60,18 Q 90,22 120,15",
     ["Commit to target effort", "Process-focus: next aid, next climb",
      "Fuel relentlessly on schedule", "Acknowledge pain, don't chase it"]),
    ("ACT 3", "Resolve", "75–100%", 25, "M 0,25 Q 30,30 60,20 Q 90,10 120,5",
     ["Unlock remaining reserves", "Shorten mental horizon: 10 min at a time",
      "Draw on training memories", "This is what you came for"]),
]


def render_three_acts(block: dict) -> str:
    bar = "".join(
        f'<span class="gg-ig-d-acts-seg gg-ig-d-acts-seg--{i + 1}" style="flex:{w} 1 0">'
        f'{_e(num)}</span>'
        for i, (num, _t, _r, w, _s, _l) in enumerate(ACTS)
    )
    cols = []
    for i, (num, title, rng, _w, spark, items) in enumerate(ACTS):
        lis = "".join(f"<li>{_e(s)}</li>" for s in items)
        cols.append(
            f'<section class="gg-ig-d-act gg-ig-d-act--{i + 1}">'
            f'<span class="gg-ig-d-act-num">{_e(num)}</span>'
            f'<h4 class="gg-ig-d-act-name">{_e(title)}</h4>'
            f'<div class="gg-ig-d-act-range">{_e(rng)}</div>'
            f'<svg class="gg-ig-d-act-spark" viewBox="0 0 120 40" aria-hidden="true"'
            f' focusable="false"><path d="{_e(spark)}"/></svg>'
            f'<ul class="gg-ig-d-act-list">{lis}</ul></section>'
        )
    body = (
        f'<div class="gg-ig-d-body">'
        f'<div class="gg-ig-d-acts-bar" aria-hidden="true">{bar}</div>'
        f'<div class="gg-ig-d-acts">{"".join(cols)}</div></div>'
    )
    return _shell("dark", block.get("asset_id", "ch6-three-acts"), block.get("alt", ""),
                  "CH 6 · RACE DAY", "The Three Acts of Every Gravel Race", body,
                  block.get("caption", ""))


# ── Chapter 6: psychological phases ─────────────────────────

PHASES = [
    ("Honeymoon", 0.00, 0.20,
     "Adrenaline and excitement carry you. Danger: going out too fast.",
     ["Adrenaline masks fatigue — heart rate is 10-15 bpm above target",
      "Biggest mistake: going out at 110% because it feels easy",
      "Strategy: set a hard ceiling on power/pace for the first 30 minutes"]),
    ("Shattering", 0.20, 0.40,
     "Reality hits. Fatigue and doubt creep in. Stay process-focused.",
     ["The adrenaline wears off and true fatigue reveals itself",
      "Doubt whispers: 'Why did I sign up for this?'",
      "Strategy: focus on the next aid station, not the finish line"]),
    ("Dark Patch", 0.40, 0.60,
     "The low point. Mantras, small goals, and fuel get you through.",
     ["Glycogen depletion + cumulative fatigue = mental low point",
      "This is where races are lost — most DNFs happen here",
      "Strategy: mantras, 10-min mental chunks, force calories in"]),
    ("Second Wind", 0.60, 0.80,
     "Energy returns. The body adapts and endorphins kick in.",
     ["Endorphins finally arrive, fat oxidation stabilizes",
      "Mental clarity returns — you remember why you love this",
      "Strategy: ride the wave, increase effort slightly if legs respond"]),
    ("Final Push", 0.80, 1.00,
     "The finish is close. Draw on everything you trained for.",
     ["The finish is tangible — pain tolerance increases when the end is near",
      "Crowd energy and course familiarity (if you pre-rode) carry you",
      "Strategy: empty the tank, leave nothing for the parking lot"]),
]

MOOD = [
    (0.00, 0.70), (0.05, 0.85), (0.10, 0.90), (0.15, 0.80), (0.20, 0.65),
    (0.25, 0.50), (0.30, 0.35), (0.35, 0.25), (0.40, 0.20), (0.45, 0.12),
    (0.50, 0.08), (0.55, 0.15), (0.60, 0.30), (0.65, 0.50), (0.70, 0.65),
    (0.75, 0.72), (0.80, 0.68), (0.85, 0.60), (0.90, 0.70), (0.95, 0.85),
    (1.00, 0.95),
]


def _smooth_path(pts) -> str:
    """Catmull-Rom spline through pts, as cubic Bezier segments."""
    d = [f"M {pts[0][0]:.1f},{pts[0][1]:.1f}"]
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C {c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return " ".join(d)


def render_psych_phases(block: dict) -> str:
    w, h = 1000, 300
    pts = [(f * w, h - 20 - m * (h - 40)) for f, m in MOOD]
    low = min(MOOD, key=lambda p: p[1])
    lx, ly = low[0] * w, h - 20 - low[1] * (h - 40)
    bands = "".join(
        f'<rect class="gg-ig-d-psy-band gg-ig-d-psy-band--{"dark" if name == "Dark Patch" else i % 2}"'
        f' x="{s * w:.0f}" y="0" width="{(e - s) * w:.0f}" height="{h}"/>'
        for i, (name, s, e, _t, _d) in enumerate(PHASES)
    )
    svg = (
        f'<svg class="gg-ig-d-psy-svg" viewBox="0 0 {w} {h}" role="img"'
        f' aria-label="Mood curve across race progress: high at the start, lowest in the Dark Patch'
        f' between 40 and 60 percent, then recovering to the finish">'
        f'{bands}<path class="gg-ig-d-psy-line" d="{_smooth_path(pts)}"/>'
        f'<circle class="gg-ig-d-psy-low" cx="{lx:.0f}" cy="{ly:.0f}" r="13"/></svg>'
    )
    cards = []
    for name, s, e, tip, details in PHASES:
        rng = f"{round(s * 100)}–{round(e * 100)}%"
        dark = " gg-ig-d-psy-card--dark" if name == "Dark Patch" else ""
        lis = "".join(f"<li>{_e(d)}</li>" for d in details)
        cards.append(
            f'<section class="gg-ig-d-psy-card{dark}">'
            f'<span class="gg-ig-d-psy-range">{_e(rng)}</span>'
            f'<h4 class="gg-ig-d-psy-name">{_e(name)}</h4>'
            f'<p class="gg-ig-d-psy-tip">{_e(tip)}</p>'
            f'<ul class="gg-ig-d-psy-list">{lis}</ul></section>'
        )
    body = (
        f'<div class="gg-ig-d-body">'
        f'<div class="gg-ig-d-hero"><span class="gg-ig-d-big">40–60%</span>'
        f'<span class="gg-ig-d-herolbl">of the race: the Dark Patch</span></div>'
        f'<div class="gg-ig-d-psy-chart"><div class="gg-ig-d-psy-axis" aria-hidden="true">'
        f'<span>HIGH</span><span>LOW</span></div>{svg}</div>'
        f'<div class="gg-ig-d-psy-cards">{"".join(cards)}</div></div>'
    )
    return _shell("light", block.get("asset_id", "ch6-psych-phases"), block.get("alt", ""),
                  "CH 6 · MINDSET", "The Mental Arc: Excitement to Emptiness to Resolve",
                  body, block.get("caption", ""))


# ── Chapter 7: race week countdown ──────────────────────────

DAYS = [
    ("MON", "Easy spin", "30-45 min Z2. Legs loose, nothing hard.",
     ["Spin 30-45 minutes in Zone 2", "Focus on smooth pedaling, no intensity",
      "Hydrate well — start pre-loading electrolytes"]),
    ("TUE", "Openers", "3x1 min Z4 surges in a Z2 ride. Wake up legs.",
     ["Warm up 15 min Z2", "3×1 min at Zone 4 with 3 min recovery",
      "Cool down 10 min. Legs should feel snappy, not tired."]),
    ("WED", "Rest day", "Off the bike. Walk, stretch, hydrate.",
     ["Completely off the bike", "Light walk or stretching only",
      "Focus on sleep quality — aim for 8+ hours"]),
    ("THU", "Shakeout", "20-30 min easy spin. Bike check.",
     ["20-30 min very easy spin", "Check tire pressure, brakes, shifting",
      "Lube chain, charge computer and lights"]),
    ("FRI", "Rest + prep", "Lay out gear. Charge devices. Sleep early.",
     ["Lay out ALL race gear — kit, nutrition, tools",
      "Charge every device: GPS, phone, lights",
      "Bed by 9 PM. Pre-race sleep matters more than race-night sleep."]),
    ("SAT", "Travel day", "Drive to venue. Packet pickup. Course preview.",
     ["Drive to venue, check into lodging", "Packet pickup and gear check",
      "Short course preview ride if possible (30 min max)"]),
    ("SUN", "RACE DAY", "Execute the plan. Trust the training.",
     ["Wake 3 hours before start, eat 600-800 cal breakfast",
      "Arrive 90 min early for setup and warm-up",
      "Execute your pacing plan. Trust the training. Enjoy the ride."]),
]


def render_race_week_countdown(block: dict) -> str:
    last = len(DAYS) - 1
    tiles, panels = [], []
    for i, (abbr, task, note, details) in enumerate(DAYS):
        race = " gg-ig-d-wk-tile--race" if i == last else ""
        sel = "true" if i == last else "false"
        tiles.append(
            f'<button type="button" class="gg-ig-d-wk-tile{race}" data-day="{i}"'
            f' aria-pressed="{sel}" aria-label="{_e(abbr)}: {_e(task)}">'
            f'<span class="gg-ig-d-wk-t">T−{last - i}</span>'
            f'<span class="gg-ig-d-wk-abbr">{_e(abbr)}</span>'
            f'<span class="gg-ig-d-wk-task">{_e(task)}</span></button>'
        )
        lis = "".join(f"<li>{_e(d)}</li>" for d in details)
        panels.append(
            f'<div class="gg-ig-d-wk-panel" data-day="{i}">'
            f'<div class="gg-ig-d-wk-ph"><span class="gg-ig-d-wk-pabbr">{_e(abbr)}</span>'
            f'<span class="gg-ig-d-wk-ptask">{_e(task)}</span></div>'
            f'<p class="gg-ig-d-wk-note">{_e(note)}</p>'
            f'<ul class="gg-ig-d-wk-list">{lis}</ul></div>'
        )
    body = (
        f'<div class="gg-ig-d-body gg-ig-d-wk">'
        f'<div class="gg-ig-d-hero"><span class="gg-ig-d-big">7</span>'
        f'<span class="gg-ig-d-herolbl">days out</span></div>'
        f'<div class="gg-ig-d-wk-strip">{"".join(tiles)}</div>'
        f'<div class="gg-ig-d-wk-panels" aria-live="polite">{"".join(panels)}</div></div>'
    )
    return _shell("dark", block.get("asset_id", "ch7-race-week-countdown"),
                  block.get("alt", ""), "CH 7 · RACE WEEK",
                  "Race Week: Seven Days Out", body, block.get("caption", ""))


# ── Chapter 7: weather matrix ───────────────────────────────

TEMPS = ["<50", "50-60", "60-75", "75-90", ">90"]
WINDS = ["Calm", "5-10", "10-15", "15-20", "20+"]
# 0 optimal, 1 minor, 2 moderate, 3 significant, 4 severe, 5 dangerous  [temp][wind]
MATRIX = [
    [3, 3, 4, 5, 5],
    [1, 2, 3, 4, 4],
    [0, 0, 1, 2, 3],
    [1, 2, 2, 3, 4],
    [3, 4, 4, 5, 5],
]
LEVELS = ["Optimal", "Minor", "Moderate", "Significant", "Severe", "Dangerous"]
TIPS = [
    ["Cold + calm: manageable with layers", "Cold + light wind: wind chill factor",
     "Cold + moderate wind: significant chill, numbness risk",
     "Cold + strong wind: hypothermia risk, avoid if possible",
     "Cold + extreme wind: dangerous conditions"],
    ["Cool + calm: dress warmly at start", "Cool + light wind: arm warmers may suffice",
     "Cool + moderate wind: headwind sections drain energy",
     "Cool + strong wind: major energy tax on exposed sections",
     "Cool + extreme wind: crosswinds dangerous on descents"],
    ["Ideal + calm: optimal racing conditions", "Ideal + light wind: near-perfect",
     "Ideal + moderate wind: minor impact, draft when possible",
     "Ideal + strong wind: moderate energy cost, plan for headwinds",
     "Ideal + extreme wind: significant impact despite good temp"],
    ["Warm + calm: hydration critical", "Warm + light wind: some cooling effect",
     "Warm + moderate wind: hot wind = worse than calm",
     "Warm + strong wind: dehydration risk accelerates",
     "Warm + extreme wind: severe conditions, reduce pace 15%"],
    ["Hot + calm: dangerous heat stress",
     "Hot + any wind: false cooling, dehydration critical",
     "Hot + moderate wind: heat illness risk high",
     "Hot + strong wind: extreme conditions, DNS consideration",
     "Hot + extreme wind: do not race"],
]


def render_weather_matrix(block: dict) -> str:
    cells = ['<span class="gg-ig-d-mx-corner" aria-hidden="true">TEMP \u00b0F</span>']
    for wd in WINDS:
        cells.append(f'<span class="gg-ig-d-mx-col">{_e(wd)}</span>')
    for ti, temp in enumerate(TEMPS):
        cells.append(f'<span class="gg-ig-d-mx-row">{_e(temp)}</span>')
        for wi, wd in enumerate(WINDS):
            lv = MATRIX[ti][wi]
            tip = TIPS[ti][wi]
            sweet = " gg-ig-d-mx-cell--on" if (ti, wi) == (2, 1) else ""
            cells.append(
                f'<button type="button" class="gg-ig-d-mx-cell gg-ig-d-mx-cell--{lv}{sweet}"'
                f' data-tip="{_e(tip)}" data-level="{_e(LEVELS[lv])}"'
                f' aria-label="{_e(tip)}. Impact {lv}, {_e(LEVELS[lv])}">{lv}</button>'
            )
    legend = "".join(
        f'<li><span class="gg-ig-d-mx-chip gg-ig-d-mx-cell--{i}">{i}</span>{_e(n)}</li>'
        for i, n in enumerate(LEVELS)
    )
    body = (
        f'<div class="gg-ig-d-body gg-ig-d-mx">'
        f'<div class="gg-ig-d-hero"><span class="gg-ig-d-big">60–75°F</span>'
        f'<span class="gg-ig-d-herolbl">with light wind is the sweet spot. '
        f'Anything beyond that costs watts.</span></div>'
        f'<div class="gg-ig-d-mx-wrap">'
        f'<div class="gg-ig-d-mx-axisx">WIND (MPH) →</div>'
        f'<div class="gg-ig-d-mx-grid">{"".join(cells)}</div>'
        f'</div>'
        f'<p class="gg-ig-d-mx-read" aria-live="polite" data-default="{_e(TIPS[2][1])}">'
        f'{_e(TIPS[2][1])}</p>'
        f'<ul class="gg-ig-d-mx-legend">{legend}</ul></div>'
    )
    return _shell("light", block.get("asset_id", "ch7-weather-matrix"), block.get("alt", ""),
                  "CH 7 · WEATHER", "Weather Impact Matrix: Wind × Temperature",
                  body, block.get("caption", ""))


RENDERERS = {
    "ch6-three-acts": render_three_acts,
    "ch6-psych-phases": render_psych_phases,
    "ch7-race-week-countdown": render_race_week_countdown,
    "ch7-weather-matrix": render_weather_matrix,
}

CSS = """
.gg-ig-d{margin:0 0 24px;border:3px solid var(--gg-color-dark-brown);border-radius:0;box-shadow:none;background:var(--gg-color-warm-paper);color:var(--gg-color-dark-brown);font-family:var(--gg-font-editorial);overflow:hidden;box-sizing:border-box;max-width:100%}
.gg-ig-d *{box-sizing:border-box}
.gg-ig-d-head{background:var(--gg-color-dark-brown);padding:20px 24px 22px;border-bottom:3px solid var(--gg-color-dark-brown)}
.gg-ig-d-eyebrow{display:block;font-family:var(--gg-font-data);font-size:14px;font-weight:700;letter-spacing:3px;color:var(--gg-color-light-gold);margin-bottom:8px}
.gg-ig-d-title{margin:0;font-family:var(--gg-font-editorial);font-size:30px;font-weight:700;line-height:1.15;color:var(--gg-color-white)}
.gg-ig-d-body{padding:24px;min-width:0}
.gg-ig-d--dark .gg-ig-d-body{background:var(--gg-color-dark-brown);color:var(--gg-color-warm-paper)}
.gg-ig-d-hero{display:flex;align-items:baseline;gap:20px;flex-wrap:wrap;margin:0 0 24px}
.gg-ig-d-big{font-family:var(--gg-font-data);font-size:84px;font-weight:700;line-height:.95;letter-spacing:-3px;color:var(--gg-color-dark-brown);background:var(--gg-color-light-gold);padding:6px 14px 10px;border:3px solid var(--gg-color-dark-brown)}
.gg-ig-d--dark .gg-ig-d-big{background:none;border:0;padding:0;color:var(--gg-color-light-gold)}
.gg-ig-d-herolbl{font-family:var(--gg-font-data);font-size:16px;font-weight:700;line-height:1.4;max-width:30ch}
.gg-ig-d p.gg-ig-d-cap{margin:0;padding:16px 24px 16px 22px;border-left:6px solid var(--gg-color-light-gold);font-family:var(--gg-font-editorial);font-style:italic;font-size:16px;line-height:1.5;background:var(--gg-color-warm-paper);color:var(--gg-color-dark-brown);border-top:3px solid var(--gg-color-dark-brown)}
.gg-ig-d--dark p.gg-ig-d-cap{background:var(--gg-color-dark-brown);color:var(--gg-color-warm-paper);border-top-color:var(--gg-color-primary-brown)}
/* three acts */
.gg-ig-d-acts-bar{display:flex;gap:3px;margin:0 0 20px;height:34px}
.gg-ig-d-acts-seg{display:flex;align-items:center;padding:0 10px;font-family:var(--gg-font-data);font-size:14px;font-weight:700;letter-spacing:2px;overflow:hidden;white-space:nowrap}
.gg-ig-d-acts-seg--1{background:var(--gg-color-secondary-brown);color:var(--gg-color-white)}
.gg-ig-d-acts-seg--2{background:var(--gg-color-tan);color:var(--gg-color-dark-brown)}
.gg-ig-d-acts-seg--3{background:var(--gg-color-light-gold);color:var(--gg-color-dark-brown)}
.gg-ig-d-acts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:3px;background:var(--gg-color-primary-brown);border:3px solid var(--gg-color-primary-brown)}
.gg-ig-d-act{background:var(--gg-color-dark-brown);padding:20px 18px 22px;min-width:0}
.gg-ig-d-act--3{background:var(--gg-color-light-gold);color:var(--gg-color-dark-brown)}
.gg-ig-d-act-num{display:block;font-family:var(--gg-font-data);font-size:14px;font-weight:700;letter-spacing:3px;color:var(--gg-color-light-gold)}
.gg-ig-d-act--3 .gg-ig-d-act-num{color:var(--gg-color-dark-brown)}
.gg-ig-d-act-name{margin:4px 0 10px;font-family:var(--gg-font-editorial);font-size:32px;font-weight:700;line-height:1.1;color:var(--gg-color-white);overflow-wrap:anywhere}
.gg-ig-d-act--3 .gg-ig-d-act-name{color:var(--gg-color-dark-brown)}
.gg-ig-d-act-range{font-family:var(--gg-font-data);font-size:36px;font-weight:700;letter-spacing:-1px;line-height:1;color:var(--gg-color-light-gold);white-space:nowrap}
.gg-ig-d-act--3 .gg-ig-d-act-range{color:var(--gg-color-dark-brown)}
.gg-ig-d-act-spark{display:block;width:100%;height:44px;margin:14px 0 16px}
.gg-ig-d-act-spark path{fill:none;stroke:var(--gg-color-warm-paper);stroke-width:4;stroke-linecap:square;vector-effect:non-scaling-stroke}
.gg-ig-d-act--3 .gg-ig-d-act-spark path{stroke:var(--gg-color-dark-brown)}
.gg-ig-d-act-list{list-style:none;margin:0;padding:0}
.gg-ig-d-act-list li{position:relative;padding:0 0 0 22px;margin:0 0 10px;font-size:16px;line-height:1.4}
.gg-ig-d-act-list li::before{content:"";position:absolute;left:0;top:.5em;width:10px;height:10px;background:var(--gg-color-light-gold)}
.gg-ig-d-act--3 .gg-ig-d-act-list li::before{background:var(--gg-color-dark-brown)}
/* psych phases */
.gg-ig-d-psy-chart{position:relative;display:flex;gap:10px;margin:0 0 20px}
.gg-ig-d-psy-axis{display:flex;flex-direction:column;justify-content:space-between;font-family:var(--gg-font-data);font-size:12px;font-weight:700;letter-spacing:1px;padding:4px 0;color:var(--gg-color-dark-brown);writing-mode:vertical-rl;transform:rotate(180deg)}
.gg-ig-d-psy-svg{display:block;flex:1 1 auto;min-width:0;width:100%;height:auto;border:3px solid var(--gg-color-dark-brown);background:var(--gg-color-warm-paper)}
.gg-ig-d-psy-band--0{fill:var(--gg-color-warm-paper)}
.gg-ig-d-psy-band--1{fill:var(--gg-color-sand)}
.gg-ig-d-psy-band--dark{fill:var(--gg-color-light-gold)}
.gg-ig-d-psy-line{fill:none;stroke:var(--gg-color-dark-brown);stroke-width:7;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}
.gg-ig-d-psy-low{fill:var(--gg-color-dark-brown);stroke:var(--gg-color-warm-paper);stroke-width:4;vector-effect:non-scaling-stroke}
.gg-ig-d-psy-cards{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:0;border:3px solid var(--gg-color-dark-brown)}
.gg-ig-d-psy-card{padding:16px 14px 18px;border-left:3px solid var(--gg-color-dark-brown);min-width:0}
.gg-ig-d-psy-card:first-child{border-left:0}
.gg-ig-d-psy-card:nth-child(odd){background:var(--gg-color-warm-paper)}
.gg-ig-d-psy-card:nth-child(even){background:var(--gg-color-sand)}
.gg-ig-d-psy-card--dark{background:var(--gg-color-dark-brown)!important;color:var(--gg-color-warm-paper)}
.gg-ig-d-psy-range{display:block;font-family:var(--gg-font-data);font-size:14px;font-weight:700;letter-spacing:1px;color:var(--gg-color-primary-brown)}
.gg-ig-d-psy-card--dark .gg-ig-d-psy-range{color:var(--gg-color-light-gold)}
.gg-ig-d-psy-name{margin:2px 0 8px;font-family:var(--gg-font-editorial);font-size:22px;font-weight:700;line-height:1.15;overflow-wrap:anywhere}
.gg-ig-d .gg-ig-d-psy-card--dark .gg-ig-d-psy-tip,.gg-ig-d .gg-ig-d-psy-card--dark .gg-ig-d-psy-list{color:var(--gg-color-warm-paper)}
.gg-ig-d-psy-card--dark .gg-ig-d-psy-name{color:var(--gg-color-light-gold)}
.gg-ig-d p.gg-ig-d-psy-tip{margin:0 0 10px;font-size:15px;font-weight:700;line-height:1.35}
.gg-ig-d-psy-list{margin:0;padding:0 0 0 16px;font-size:14px;line-height:1.4}
.gg-ig-d-psy-list li{margin:0 0 6px}
/* race week */
.gg-ig-d-wk-strip{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:3px;margin:0 0 20px}
.gg-ig-d-wk-tile{appearance:none;display:flex;flex-direction:column;align-items:flex-start;justify-content:space-between;gap:6px;min-height:104px;padding:10px 10px 12px;border:3px solid var(--gg-color-primary-brown);border-radius:0;background:var(--gg-color-dark-brown);color:var(--gg-color-warm-paper);text-align:left;cursor:pointer;font:inherit;min-width:0}
.gg-ig-d-wk-tile:hover{border-color:var(--gg-color-light-gold)}
.gg-ig-d-wk-tile:focus-visible{outline:3px solid var(--gg-color-light-teal);outline-offset:2px}
.gg-ig-d-wk-tile[aria-pressed="true"]{background:var(--gg-color-warm-paper);color:var(--gg-color-dark-brown);border-color:var(--gg-color-warm-paper)}
.gg-ig-d-wk-tile--race{background:var(--gg-color-light-gold);color:var(--gg-color-dark-brown);border-color:var(--gg-color-light-gold)}
.gg-ig-d-wk-tile--race[aria-pressed="true"]{border-color:var(--gg-color-warm-paper)}
.gg-ig-d-wk-t{font-family:var(--gg-font-data);font-size:14px;font-weight:700;opacity:.9}
.gg-ig-d-wk-abbr{font-family:var(--gg-font-data);font-size:24px;font-weight:700;line-height:1;letter-spacing:-1px}
.gg-ig-d-wk-task{font-family:var(--gg-font-editorial);font-size:15px;font-weight:700;line-height:1.2;overflow-wrap:anywhere}
.gg-ig-d-wk-panel{border:3px solid var(--gg-color-warm-paper);padding:18px 20px;margin:0 0 3px}
.gg-ig-d-wk--js .gg-ig-d-wk-panel[hidden]{display:none}
.gg-ig-d-wk-ph{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
.gg-ig-d-wk-pabbr{font-family:var(--gg-font-data);font-size:44px;font-weight:700;line-height:1;color:var(--gg-color-light-gold)}
.gg-ig-d-wk-ptask{font-family:var(--gg-font-editorial);font-size:28px;font-weight:700;color:var(--gg-color-white)}
.gg-ig-d p.gg-ig-d-wk-note{margin:10px 0 12px;font-size:18px;line-height:1.4;font-style:italic;color:var(--gg-color-sand)}
.gg-ig-d-wk-list{margin:0;padding:0;list-style:none}
.gg-ig-d-wk-list li{position:relative;padding:0 0 0 22px;margin:0 0 8px;font-size:16px;line-height:1.45}
.gg-ig-d-wk-list li::before{content:"";position:absolute;left:0;top:.5em;width:10px;height:10px;background:var(--gg-color-light-gold)}
/* weather matrix */
.gg-ig-d-mx-wrap{display:grid;grid-template-columns:minmax(0,1fr);gap:8px}
.gg-ig-d-mx-corner{display:flex;align-items:center;font-family:var(--gg-font-data);font-size:12px;font-weight:700;letter-spacing:1px;line-height:1.1}
.gg-ig-d-mx-axisx{font-family:var(--gg-font-data);font-size:12px;font-weight:700;letter-spacing:2px}
.gg-ig-d-mx-axisx{padding-left:63px}
.gg-ig-d-mx-grid{display:grid;grid-template-columns:60px repeat(5,minmax(0,1fr));gap:3px}
.gg-ig-d-mx-col,.gg-ig-d-mx-row{display:flex;align-items:center;justify-content:center;font-family:var(--gg-font-data);font-size:14px;font-weight:700;min-height:44px}
.gg-ig-d-mx-cell{appearance:none;display:flex;align-items:center;justify-content:center;min-height:60px;border:3px solid var(--gg-color-dark-brown);border-radius:0;font-family:var(--gg-font-data);font-size:28px;font-weight:700;cursor:pointer;padding:0}
.gg-ig-d-mx-cell:focus-visible{outline:3px solid var(--gg-color-teal);outline-offset:2px;position:relative;z-index:1}
.gg-ig-d-mx-cell--0{background:var(--gg-color-light-gold);color:var(--gg-color-dark-brown)}
.gg-ig-d-mx-cell--1{background:var(--gg-color-sand);color:var(--gg-color-dark-brown)}
.gg-ig-d-mx-cell--2{background:var(--gg-color-tan);color:var(--gg-color-dark-brown)}
.gg-ig-d-mx-cell--3{background:var(--gg-color-secondary-brown);color:var(--gg-color-white)}
.gg-ig-d-mx-cell--4{background:var(--gg-color-primary-brown);color:var(--gg-color-white)}
.gg-ig-d-mx-cell--5{background:var(--gg-color-near-black);color:var(--gg-color-light-gold)}
.gg-ig-d-mx-cell--on{outline:4px solid var(--gg-color-dark-brown);outline-offset:-7px}
.gg-ig-d p.gg-ig-d-mx-read{margin:16px 0;padding:14px 16px;min-height:60px;border:3px solid var(--gg-color-dark-brown);background:var(--gg-color-white);font-family:var(--gg-font-data);font-size:16px;font-weight:700;line-height:1.4}
.gg-ig-d-mx-legend{display:flex;flex-wrap:wrap;gap:8px 18px;margin:0;padding:0;list-style:none;font-family:var(--gg-font-data);font-size:14px;font-weight:700}
.gg-ig-d-mx-legend li{display:flex;align-items:center;gap:8px}
.gg-ig-d-mx-chip{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border:3px solid var(--gg-color-dark-brown);font-size:14px}
@media (max-width:860px){
.gg-ig-d-acts{grid-template-columns:minmax(0,1fr)}
.gg-ig-d-psy-cards{grid-template-columns:minmax(0,1fr)}
.gg-ig-d-psy-card{border-left:0;border-top:3px solid var(--gg-color-dark-brown)}
.gg-ig-d-psy-card:first-child{border-top:0}
}
@media (max-width:600px){
.gg-ig-d-head{padding:16px 16px 18px}
.gg-ig-d-title{font-size:25px}
.gg-ig-d-body{padding:16px}
.gg-ig-d-big{font-size:56px;letter-spacing:-2px}
.gg-ig-d-hero{gap:10px;margin-bottom:18px}
.gg-ig-d-cap{padding:14px 16px 14px 14px}
.gg-ig-d-acts-seg{padding:0 6px;letter-spacing:0;font-size:14px}
.gg-ig-d-act-name{font-size:30px}
.gg-ig-d-psy-axis{display:none}
.gg-ig-d-wk-strip{gap:2px}
.gg-ig-d-wk-tile{min-height:64px;padding:8px 4px;align-items:center;justify-content:center}
.gg-ig-d-wk-t,.gg-ig-d-wk-task{display:none}
.gg-ig-d-wk-abbr{font-size:16px;letter-spacing:0}
.gg-ig-d-wk-pabbr{font-size:36px}
.gg-ig-d-wk-ptask{font-size:24px}
.gg-ig-d-wk-panel{padding:14px}
.gg-ig-d-mx-axisx{padding-left:44px}.gg-ig-d-mx-corner{font-size:12px;letter-spacing:0}
.gg-ig-d-mx-grid{grid-template-columns:42px repeat(5,minmax(0,1fr));gap:2px}
.gg-ig-d-mx-col,.gg-ig-d-mx-row{font-size:12px}
.gg-ig-d-mx-cell{min-height:48px;font-size:22px;border-width:2px}
}
"""

JS = """
(function(){
var wk=document.querySelectorAll('.gg-ig-d-wk');
wk.forEach(function(root){
  var tiles=root.querySelectorAll('.gg-ig-d-wk-tile');
  var panels=root.querySelectorAll('.gg-ig-d-wk-panel');
  function pick(i){
    tiles.forEach(function(t){t.setAttribute('aria-pressed',t.getAttribute('data-day')===String(i)?'true':'false');});
    panels.forEach(function(p){p.hidden=p.getAttribute('data-day')!==String(i);});
  }
  root.classList.add('gg-ig-d-wk--js');
  tiles.forEach(function(t){t.addEventListener('click',function(){pick(t.getAttribute('data-day'));});});
  pick(panels.length-1);
});
var mx=document.querySelectorAll('.gg-ig-d-mx');
mx.forEach(function(root){
  var read=root.querySelector('.gg-ig-d-mx-read');
  var cells=root.querySelectorAll('.gg-ig-d-mx-cell[data-tip]');
  function show(c){
    cells.forEach(function(x){x.classList.remove('gg-ig-d-mx-cell--on');});
    c.classList.add('gg-ig-d-mx-cell--on');
    read.textContent=c.getAttribute('data-tip')+' ('+c.getAttribute('data-level')+')';
  }
  cells.forEach(function(c){
    c.addEventListener('click',function(){show(c);});
    c.addEventListener('focus',function(){show(c);});
  });
});
})();
"""
