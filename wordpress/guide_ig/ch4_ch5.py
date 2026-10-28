"""Handbook charts for Chapter 4 (Recovery) and Chapter 5 (Fueling), rebuilt 2026-10-28.

Ten poster panels, alternating dark and light bodies. All numbers come from the
old renderers in guide_infographics.py. CSS prefix: .gg-ig-c-
"""
import html as _html

_NAME = "ch4_ch5"


def _e(x) -> str:
    """HTML-escape; 0 prints as 0, None prints as nothing."""
    return "" if x is None else _html.escape(str(x))


def _fmt(n) -> str:
    return f"{n:,}"


def _panel(kind: str, tone: str, eyebrow: str, title: str, body: str, caption: str) -> str:
    cap = f'<p class="gg-ig-c-cap">{_e(caption)}</p>' if caption else ""
    return (
        f'<figure class="gg-ig-c gg-ig-c--{tone} gg-ig-c-k-{kind}">'
        f'<header class="gg-ig-c-head">'
        f'<span class="gg-ig-c-eyebrow">{_e(eyebrow)}</span>'
        f'<h3 class="gg-ig-c-title">{_e(title)}</h3>'
        f'</header>'
        f'<div class="gg-ig-c-body">{body}{cap}</div>'
        f'</figure>'
    )


def _stat(big: str, unit: str = "", note: str = "") -> str:
    u = f'<span class="gg-ig-c-unit">{_e(unit)}</span>' if unit else ""
    n = f'<span class="gg-ig-c-note">{_e(note)}</span>' if note else ""
    return f'<div class="gg-ig-c-hero"><span class="gg-ig-c-big">{_e(big)}</span>{u}{n}</div>'


# ── Chapter 4 ───────────────────────────────────────────────


def render_execution_gap(block: dict) -> str:
    plan = 85
    intervals = [("Int 1", 95), ("Int 2", 78), ("Int 3", 55),
                 ("Int 4", 84), ("Int 5", 83), ("Int 6", 85)]
    cols = []
    for i, (label, actual) in enumerate(intervals):
        good = "good" if i >= 3 else "bad"
        cols.append(
            f'<div class="gg-ig-c-col">'
            f'<span class="gg-ig-c-colval">{actual}%</span>'
            f'<div class="gg-ig-c-track" aria-hidden="true">'
            f'<div class="gg-ig-c-colbar gg-ig-c-colbar--{good}" style="--v:{actual}"></div>'
            f'</div>'
            f'<span class="gg-ig-c-collab">{_e(label)}</span>'
            f'</div>'
        )
    chart = (
        f'<div class="gg-ig-c-gap" style="--plan:{plan}">'
        f'<div class="gg-ig-c-cols">{"".join(cols)}</div>'
        f'</div>'
    )
    legend = (
        '<div class="gg-ig-c-legend">'
        '<div class="gg-ig-c-legitem"><span class="gg-ig-c-swatch gg-ig-c-swatch--bad" aria-hidden="true"></span>'
        '<div><strong>Chasing Watts</strong>'
        '<span>Int 1-3: starts hot (95%), fades to 55%</span></div></div>'
        '<div class="gg-ig-c-legitem"><span class="gg-ig-c-swatch gg-ig-c-swatch--good" aria-hidden="true"></span>'
        '<div><strong>Consistent Execution</strong>'
        '<span>Int 4-6: holds 83-85% — all within 2% of target</span></div></div>'
        '<div class="gg-ig-c-legitem gg-ig-c-legitem--plan"><span class="gg-ig-c-swatch gg-ig-c-swatch--plan" aria-hidden="true"></span>'
        '<div><strong>Dashed line = plan</strong><span>85% FTP on every interval</span></div></div>'
        '</div>'
    )
    body = _stat("95→55", "% FTP", "Chasing watts: Int 1 to Int 3") + chart + legend
    return _panel("gap", "dark", "CH 4 · EXECUTION",
                  "The Execution Gap: Plan vs. Reality", body, block.get("caption", ""))


def render_traffic_light(block: dict) -> str:
    signals = [
        ("go", "GO", "GREEN — Go",
         "Slept 7+ hrs, resting HR normal, motivation high, no soreness",
         "Execute as planned. Full intensity."),
        ("caution", "CAUTION", "YELLOW — Caution",
         "Slept 5-7 hrs, slightly elevated HR, moderate fatigue",
         "Reduce intensity 5-10%. Shorten intervals. Monitor feel."),
        ("stop", "STOP", "RED — Stop",
         "Slept <5 hrs, elevated HR, illness symptoms, sharp pain",
         "Rest or Z1 only. Recovery is training. Come back tomorrow."),
    ]
    tiles = []
    for state, word, label, criteria, action in signals:
        tiles.append(
            f'<div class="gg-ig-c-sig gg-ig-c-sig--{state}">'
            f'<div class="gg-ig-c-sighead">'
            f'<span class="gg-ig-c-sigword">{_e(word)}</span>'
            f'<span class="gg-ig-c-siglabel">{_e(label)}</span></div>'
            f'<div class="gg-ig-c-sigbody">'
            f'<span class="gg-ig-c-kicker">IF</span><p>{_e(criteria)}</p>'
            f'<span class="gg-ig-c-kicker">THEN</span><p class="gg-ig-c-do">{_e(action)}</p>'
            f'</div></div>'
        )
    body = f'<div class="gg-ig-c-sigs">{"".join(tiles)}</div>'
    return _panel("light", "light", "CH 4 · AUTOREGULATION",
                  "The Go / Caution / No-Go Framework", body, block.get("caption", ""))


def render_recovery_dash(block: dict) -> str:
    gauges = [
        ("Sleep Quality", 7.2, 10, "hrs avg",
         "7+ hours correlates with 15-20% better recovery scores"),
        ("HRV Score", 65, 100, "ms rMSSD",
         "Higher HRV = better parasympathetic recovery. Track trends, not single readings."),
        ("Muscle Readiness", 3, 5, "/5 soreness",
         "Self-rated 1-5. Below 3 = modify workout. Below 2 = rest day."),
    ]
    tiles = []
    for label, value, mx, unit, tip in gauges:
        pct = round(value / mx * 100)
        tiles.append(
            f'<div class="gg-ig-c-gauge">'
            f'<span class="gg-ig-c-kicker">{_e(label)}</span>'
            f'<div class="gg-ig-c-gnum"><span class="gg-ig-c-big gg-ig-c-big--md">{_e(value)}</span>'
            f'<span class="gg-ig-c-unit">{_e(unit)}</span></div>'
            f'<div class="gg-ig-c-meter" aria-hidden="true"><div class="gg-ig-c-meterfill" style="--w:{pct}%"></div></div>'
            f'<p class="gg-ig-c-gtip">{_e(tip)}</p>'
            f'</div>'
        )
    body = f'<div class="gg-ig-c-gauges">{"".join(tiles)}</div>'
    return _panel("recovery", "dark", "CH 4 · RECOVERY",
                  "Recovery Dashboard: Three Metrics That Matter", body, block.get("caption", ""))


def render_sleep_debt(block: dict) -> str:
    days = [("Mon", 6.5), ("Tue", 5.5), ("Wed", 8.5), ("Thu", 6.0),
            ("Fri", 7.0), ("Sat", 9.0), ("Sun", 6.5)]
    need = 8.0
    debt = sum(need - a for _, a in days if a < need)
    surplus = sum(a - need for _, a in days if a > need)
    net = debt - surplus
    cols = []
    for name, hrs in days:
        diff = hrs - need
        state = "short" if diff < 0 else "over"
        sign = "−" if diff < 0 else "+"
        cols.append(
            f'<div class="gg-ig-c-col">'
            f'<span class="gg-ig-c-colval">{hrs:g}</span>'
            f'<div class="gg-ig-c-track" aria-hidden="true">'
            f'<div class="gg-ig-c-colbar gg-ig-c-colbar--{state}" style="--v:{hrs * 10:g}"></div></div>'
            f'<span class="gg-ig-c-collab">{_e(name)}</span>'
            f'<span class="gg-ig-c-delta gg-ig-c-delta--{state}">{sign}{abs(diff):g}<span class="gg-ig-c-hs">h</span></span>'
            f'</div>'
        )
    chart = (
        f'<div class="gg-ig-c-gap gg-ig-c-sleep" style="--plan:{need * 10:g}">'
        f'<div class="gg-ig-c-cols">{"".join(cols)}</div></div>'
        f'<p class="gg-ig-c-axisnote">Dashed line = {need:g} hours needed</p>'
    )
    body = _stat(f"{net:g}", "hrs debt",
                 f"Race week: {debt:g} h short, {surplus:g} h banked") + chart
    return _panel("sleep", "light", "CH 4 · SLEEP",
                  "Sleep Debt: The Hidden Performance Killer", body, block.get("caption", ""))


# ── Chapter 5 ───────────────────────────────────────────────


def render_fueling_timeline(block: dict) -> str:
    markers = [
        ("T-3 hrs", "Pre-race meal",
         "600-800 cal, low fiber, familiar foods",
         "Oatmeal + banana + honey is the classic. Eat what you practiced."),
        ("T-30 min", "Top off",
         "Gel or drink, 30-50g carbs",
         "One gel or half a bottle of drink mix. Nothing new, nothing heavy."),
        ("Start", "Race begins",
         "Start fueling at min 15-20, not later",
         "Set a timer. By the time you feel hungry, you are already behind."),
        ("Every 20 min", "Steady intake",
         "75g carbs/hr from gels, chews, drink mix",
         "Mix sources: gels + chews + liquid. Trained gut absorbs 90-120g/hr."),
        ("Ongoing", "Hydration",
         "500-750ml/hr, sodium 500-1000mg/hr",
         "Adjust for heat. Clear urine = good. Dark = drink more. Cramping = more sodium."),
    ]
    items = []
    for t, title, summary, detail in markers:
        items.append(
            f'<li class="gg-ig-c-step">'
            f'<span class="gg-ig-c-steptime">{_e(t)}</span>'
            f'<span class="gg-ig-c-stepdot" aria-hidden="true"></span>'
            f'<div class="gg-ig-c-stepbody">'
            f'<strong>{_e(title)}</strong>'
            f'<span class="gg-ig-c-stepsum">{_e(summary)}</span>'
            f'<span class="gg-ig-c-stepdet">{_e(detail)}</span>'
            f'</div></li>'
        )
    body = (_stat("75", "g carbs / hr", "Start at minute 15-20, then every 20 minutes")
            + f'<ol class="gg-ig-c-steps">{"".join(items)}</ol>')
    return _panel("timeline", "dark", "CH 5 · RACE DAY",
                  "Race Day Fueling: Hour by Hour", body, block.get("caption", ""))


def render_bonk_math(block: dict) -> str:
    gels = "".join(
        f'<span class="gg-ig-c-gel" aria-hidden="true">{i}</span>' for i in range(1, 25)
    )
    hero = (
        '<div class="gg-ig-c-hero gg-ig-c-hero--eq">'
        '<span class="gg-ig-c-big">8 &times; 75g = 600g</span>'
        '<span class="gg-ig-c-note">8 hours &times; 75g carbs/hr = 600g total carbohydrate</span>'
        '</div>'
    )
    tiles = (
        '<div class="gg-ig-c-pair gg-ig-c-pair--wide">'
        '<div class="gg-ig-c-tile"><span class="gg-ig-c-tilenum">~2,000</span>'
        '<span class="gg-ig-c-tilelab">calories of glycogen stored</span></div>'
        '<div class="gg-ig-c-tile gg-ig-c-tile--hot"><span class="gg-ig-c-tilenum">4,000+</span>'
        '<span class="gg-ig-c-tilelab">calories burned in an 8-hour race</span></div>'
        '</div>'
    )
    grid = (
        f'<div class="gg-ig-c-gels">{gels}</div>'
        '<p class="gg-ig-c-gelnote"><strong>= 24 gels</strong> (or equivalent)</p>'
    )
    return _panel("bonk", "light", "CH 5 · FUEL MATH",
                  "The Math Behind the Bonk", hero + tiles + grid, block.get("caption", ""))


def render_hydration_calc(block: dict) -> str:
    def field(key, label, mn, mx, val, step, shown, aria):
        fid = f"gg-ig-c-hy-{key}"
        return (
            f'<div class="gg-ig-c-field">'
            f'<label class="gg-ig-c-flabel" for="{fid}">{_e(label)}</label>'
            f'<input type="range" id="{fid}" class="gg-ig-c-slider" data-in="{key}"'
            f' min="{mn}" max="{mx}" value="{val}" step="{step}" aria-label="{_e(aria)}">'
            f'<output class="gg-ig-c-fval" for="{fid}" data-val="{key}">{_e(shown)}</output>'
            f'</div>'
        )

    fields = (
        field("duration", "Race Duration", 2, 12, 6, 0.5, "6 hrs", "Race duration in hours")
        + field("temp", "Temperature", 50, 110, 80, 5, "80°F", "Temperature in Fahrenheit")
        + field("intensity", "Intensity", 1, 5, 3, 1, "3 / 5", "Effort intensity 1 to 5")
    )
    results = (
        '<div class="gg-ig-c-results" aria-live="polite">'
        '<div class="gg-ig-c-res"><span class="gg-ig-c-kicker">Sodium</span>'
        '<span class="gg-ig-c-resnum" data-out="sodium">4,500 mg</span></div>'
        '<div class="gg-ig-c-res"><span class="gg-ig-c-kicker">Fluid / hr</span>'
        '<span class="gg-ig-c-resnum" data-out="rate">625 ml</span></div>'
        '<div class="gg-ig-c-res"><span class="gg-ig-c-kicker">Bottles / hr</span>'
        '<span class="gg-ig-c-resnum" data-out="bottles">~1.3</span></div>'
        '</div>'
    )
    body = (
        '<div class="gg-ig-c-hydra">'
        '<div class="gg-ig-c-hero"><span class="gg-ig-c-big" data-out="fluid" aria-live="polite">3,750</span>'
        '<span class="gg-ig-c-unit">ml total fluid</span></div>'
        f'<div class="gg-ig-c-fields">{fields}</div>'
        f'{results}'
        '</div>'
    )
    return _panel("hydra-wrap", "dark", "CH 5 · HYDRATION",
                  "Hydration Calculator: Dial In Your Fluid Plan", body, block.get("caption", ""))


def render_glycogen_gauge(block: dict) -> str:
    scenarios = [
        ("unfed", "Without Fueling",
         [("Start", 100), ("Hour 2", 65), ("Hour 4", 25), ("Hour 6", 5)],
         "Glycogen depleted by hour 4. Bonk inevitable."),
        ("fed", "With 75g/hr Fueling",
         [("Start", 100), ("Hour 2", 80), ("Hour 4", 55), ("Hour 6", 35)],
         "Steady depletion but manageable. Finish strong."),
    ]
    panels = []
    for kind, title, pts, summary in scenarios:
        rows = "".join(
            f'<div class="gg-ig-c-hbar">'
            f'<span class="gg-ig-c-hlab">{_e(lab)}</span>'
            f'<div class="gg-ig-c-htrack" aria-hidden="true">'
            f'<div class="gg-ig-c-hfill gg-ig-c-hfill--{kind}" style="--w:{pct}%"></div></div>'
            f'<span class="gg-ig-c-hval">{pct}%</span></div>'
            for lab, pct in pts
        )
        panels.append(
            f'<div class="gg-ig-c-scen gg-ig-c-scen--{kind}">'
            f'<div class="gg-ig-c-scentitle">{_e(title)}</div>'
            f'{rows}<p class="gg-ig-c-scensum">{_e(summary)}</p></div>'
        )
    stats = (
        '<div class="gg-ig-c-pair">'
        '<div class="gg-ig-c-tile gg-ig-c-tile--hot"><span class="gg-ig-c-tilenum">5%</span>'
        '<span class="gg-ig-c-tilelab">left at hour 6, without fueling</span></div>'
        '<div class="gg-ig-c-tile gg-ig-c-tile--teal"><span class="gg-ig-c-tilenum">35%</span>'
        '<span class="gg-ig-c-tilelab">left at hour 6, with 75g/hr</span></div>'
        '</div>'
    )
    body = stats + f'<div class="gg-ig-c-scens">{"".join(panels)}</div>'
    return _panel("glyco", "light", "CH 5 · GLYCOGEN",
                  "Glycogen Depletion: Fed vs. Unfed", body, block.get("caption", ""))


def render_macro_split(block: dict) -> str:
    macros = [
        ("carb", "Carbohydrates", "55-65%", 60,
         "Primary fuel source. 6-10g/kg body weight on training days."),
        ("protein", "Protein", "15-20%", 18,
         "Muscle repair and adaptation. 1.6-2.2g/kg. Spread across meals."),
        ("fat", "Fat", "20-30%", 22,
         "Essential for hormones and long-effort fat oxidation."),
    ]
    segs = "".join(
        f'<span class="gg-ig-c-seg gg-ig-c-seg--{k}" style="--w:{pct}%"></span>'
        for k, _n, _r, pct, _t in macros
    )
    rows = "".join(
        f'<div class="gg-ig-c-macro">'
        f'<span class="gg-ig-c-swatch gg-ig-c-swatch--{k}" aria-hidden="true"></span>'
        f'<span class="gg-ig-c-macroname">{_e(n)}</span>'
        f'<span class="gg-ig-c-macrorange">{_e(r)}</span>'
        f'<p class="gg-ig-c-macrotip">{_e(t)}</p></div>'
        for k, n, r, _p, t in macros
    )
    body = (_stat("55-65", "% carbs", "Carbs are the primary fuel for gravel")
            + f'<div class="gg-ig-c-stack" aria-hidden="true">{segs}</div>'
            + f'<div class="gg-ig-c-macros">{rows}</div>')
    return _panel("macro", "dark", "CH 5 · NUTRITION",
                  "Daily Macro Split for Endurance Athletes", body, block.get("caption", ""))


def render_calorie_burn(block: dict) -> str:
    hours = [("Hr 1", 700, 700), ("Hr 2", 650, 1350), ("Hr 3", 600, 1950),
             ("Hr 4", 580, 2530), ("Hr 5", 550, 3080), ("Hr 6", 520, 3600),
             ("Hr 7", 500, 4100), ("Hr 8", 480, 4580)]
    mx = 750
    rows = "".join(
        f'<div class="gg-ig-c-crow">'
        f'<span class="gg-ig-c-hlab">{_e(lab)}</span>'
        f'<div class="gg-ig-c-htrack" aria-hidden="true">'
        f'<div class="gg-ig-c-hfill gg-ig-c-hfill--cal" style="--w:{round(cal / mx * 100)}%"></div></div>'
        f'<span class="gg-ig-c-hval">{_fmt(cal)}</span>'
        f'<span class="gg-ig-c-cum">{_fmt(cum)}</span></div>'
        for lab, cal, cum in hours
    )
    head = (
        '<div class="gg-ig-c-crow gg-ig-c-crow--head" aria-hidden="true">'
        '<span></span><span></span><span class="gg-ig-c-hval">BURN</span>'
        '<span class="gg-ig-c-cum">TOTAL</span></div>'
    )
    body = (_stat(_fmt(4580), "cal", "Burned over an 8-hour race; only ~2,400 cal can be absorbed from food")
            + f'<div class="gg-ig-c-cal">{head}{rows}</div>')
    return _panel("cal", "light", "CH 5 · ENERGY",
                  "Calorie Burn by Hour: The Energy Deficit", body, block.get("caption", ""))


RENDERERS = {
    "ch4-execution-gap": render_execution_gap,
    "ch4-traffic-light": render_traffic_light,
    "ch4-recovery-dash": render_recovery_dash,
    "ch4-sleep-debt": render_sleep_debt,
    "ch5-fueling-timeline": render_fueling_timeline,
    "ch5-bonk-math": render_bonk_math,
    "ch5-hydration-calc": render_hydration_calc,
    "ch5-glycogen-gauge": render_glycogen_gauge,
    "ch5-macro-split": render_macro_split,
    "ch5-calorie-burn": render_calorie_burn,
}


CSS = """
/* ── Chapters 4-5 charts (.gg-ig-c-) ── */
.gg-ig-c{--ig-ink:var(--gg-color-dark-brown);margin:40px 0;border:3px solid var(--gg-color-dark-brown);border-radius:0;box-shadow:none;background:var(--gg-color-warm-paper);color:var(--gg-color-dark-brown);font-family:var(--gg-font-editorial);box-sizing:border-box;max-width:100%;min-width:0}
.gg-ig-c *,.gg-ig-c *::before,.gg-ig-c *::after{box-sizing:border-box}
.gg-ig-c-head{background:var(--gg-color-dark-brown);padding:20px 24px 22px;border-bottom:3px solid var(--gg-color-dark-brown)}
.gg-ig-c--dark .gg-ig-c-head{background:var(--gg-color-near-black);border-bottom-color:var(--gg-color-light-gold)}
.gg-ig-c-eyebrow{display:block;font-family:var(--gg-font-data);font-size:14px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:var(--gg-color-light-gold);margin-bottom:8px}
.gg-ig-c .gg-ig-c-title{margin:0;padding:0;font-family:var(--gg-font-editorial);font-size:30px;font-weight:700;line-height:1.15;letter-spacing:0;text-transform:none;color:var(--gg-color-white)}
.gg-ig-c-body{padding:28px 24px 24px;min-width:0}
.gg-ig-c--dark .gg-ig-c-body{background:var(--gg-color-dark-brown);color:var(--gg-color-warm-paper)}
.gg-ig-c .gg-ig-c-cap{margin:32px 0 0;padding:6px 0 6px 18px;border-left:6px solid var(--gg-color-light-gold);font-family:var(--gg-font-editorial);font-style:italic;font-size:16px;line-height:1.5;color:inherit}
.gg-ig-c-body p{margin:0;color:inherit;font-size:inherit;line-height:inherit}

/* loud number */
.gg-ig-c-hero{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 16px;margin:0 0 28px}
.gg-ig-c-big{font-family:var(--gg-font-data);font-weight:700;font-size:clamp(52px,12vw,88px);line-height:.95;letter-spacing:-2px;font-variant-numeric:tabular-nums;color:var(--gg-color-dark-brown)}
.gg-ig-c-big--md{font-size:clamp(52px,9vw,72px)}
.gg-ig-c--dark .gg-ig-c-big{color:var(--gg-color-light-gold)}
.gg-ig-c--light .gg-ig-c-hero{background:var(--gg-color-light-gold);border:3px solid var(--gg-color-dark-brown);padding:18px 20px}
.gg-ig-c--light .gg-ig-c-hero .gg-ig-c-big{color:var(--gg-color-dark-brown)}
.gg-ig-c-unit{font-family:var(--gg-font-data);font-size:18px;font-weight:700;letter-spacing:2px;text-transform:uppercase}
.gg-ig-c-note{flex-basis:100%;font-size:16px;line-height:1.45}
.gg-ig-c-kicker{display:block;font-family:var(--gg-font-data);font-size:14px;font-weight:700;letter-spacing:2px;text-transform:uppercase}
.gg-ig-c--dark .gg-ig-c-kicker{color:var(--gg-color-tan)}
.gg-ig-c-hero--eq .gg-ig-c-big{font-size:clamp(34px,7.4vw,72px);letter-spacing:-1px;white-space:nowrap}

/* vertical column charts: execution gap, sleep debt */
.gg-ig-c-gap{position:relative;margin:0 0 24px}
.gg-ig-c-cols{display:grid;grid-template-columns:repeat(var(--n,6),minmax(0,1fr));gap:10px;position:relative}
.gg-ig-c-sleep .gg-ig-c-cols{--n:7}
.gg-ig-c-col{display:flex;flex-direction:column;align-items:stretch;text-align:center;min-width:0}
.gg-ig-c-colval{font-family:var(--gg-font-data);font-size:16px;font-weight:700;line-height:1;margin-bottom:6px;font-variant-numeric:tabular-nums}
.gg-ig-c-track{position:relative;height:240px;background:rgba(122,105,93,.18);border-bottom:3px solid currentColor;display:flex;align-items:flex-end}
.gg-ig-c--dark .gg-ig-c-track{background:rgba(255,255,255,.07)}
.gg-ig-c-colbar{width:100%;height:calc(var(--v) * 1%)}
.gg-ig-c-colbar--bad{background:var(--gg-color-secondary-brown)}
.gg-ig-c--dark .gg-ig-c-colbar--bad{background:var(--gg-color-tan)}
.gg-ig-c-colbar--good{background:var(--gg-color-light-gold)}
.gg-ig-c-colbar--short{background:var(--gg-color-dark-brown)}
.gg-ig-c-colbar--over{background:var(--gg-color-light-gold)}
.gg-ig-c-collab{font-family:var(--gg-font-data);font-size:14px;font-weight:700;margin-top:8px}
.gg-ig-c-delta{font-family:var(--gg-font-data);font-size:14px;font-weight:700;margin-top:2px;font-variant-numeric:tabular-nums}
.gg-ig-c-delta--short{color:var(--gg-color-error)}
.gg-ig-c-delta--over{color:var(--gg-color-teal)}
.gg-ig-c-track::after{content:"";position:absolute;left:0;right:0;bottom:calc(var(--plan) * 1% - 2px);height:4px;z-index:2;background:repeating-linear-gradient(90deg,var(--gg-color-near-black) 0 8px,var(--gg-color-white) 8px 16px)}
.gg-ig-c .gg-ig-c-axisnote{margin-top:12px;font-family:var(--gg-font-data);font-size:14px;font-weight:700}
.gg-ig-c-legend{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}
.gg-ig-c-legitem{display:flex;gap:12px;align-items:flex-start}
.gg-ig-c-legitem strong{display:block;font-size:18px;line-height:1.25;color:var(--gg-color-white)}
.gg-ig-c-legitem span:not(.gg-ig-c-swatch){display:block;font-size:16px;line-height:1.4;margin-top:2px}
.gg-ig-c-swatch{flex:0 0 22px;width:22px;height:22px;margin-top:3px;border:3px solid var(--gg-color-warm-paper)}
.gg-ig-c-swatch--bad{background:var(--gg-color-tan)}
.gg-ig-c-swatch--good,.gg-ig-c-swatch--carb{background:var(--gg-color-light-gold)}
.gg-ig-c-swatch--plan{background:transparent;border-style:dashed}
.gg-ig-c-swatch--protein{background:var(--gg-color-white)}
.gg-ig-c-swatch--fat{background:var(--gg-color-secondary-brown)}

/* traffic light tiles */
.gg-ig-c-sigs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.gg-ig-c-sig{border:3px solid var(--gg-color-dark-brown);background:var(--gg-color-white);display:flex;flex-direction:column;min-width:0}
.gg-ig-c-sighead{padding:16px 18px 14px;border-bottom:3px solid var(--gg-color-dark-brown)}
.gg-ig-c-sig--go .gg-ig-c-sighead{background:var(--gg-color-teal);color:var(--gg-color-white)}
.gg-ig-c-sig--caution .gg-ig-c-sighead{background:var(--gg-color-light-gold);color:var(--gg-color-dark-brown)}
.gg-ig-c-sig--stop .gg-ig-c-sighead{background:var(--gg-color-error);color:var(--gg-color-white)}
.gg-ig-c-sigword{display:block;font-family:var(--gg-font-data);font-size:clamp(40px,10vw,56px);font-weight:700;line-height:1;letter-spacing:-1px}
.gg-ig-c-siglabel{display:block;font-family:var(--gg-font-data);font-size:14px;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-top:8px}
.gg-ig-c-sigbody{padding:16px 18px 20px;display:flex;flex-direction:column;gap:6px}
.gg-ig-c-sigbody .gg-ig-c-kicker{color:var(--gg-color-secondary-brown);margin-top:6px}
.gg-ig-c .gg-ig-c-sigbody p{font-size:17px;line-height:1.45}
.gg-ig-c .gg-ig-c-sigbody .gg-ig-c-do{font-weight:700;font-size:18px}

/* recovery gauges */
.gg-ig-c-gauges{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.gg-ig-c-gauge{border:3px solid var(--gg-color-secondary-brown);padding:18px;min-width:0;display:flex;flex-direction:column;gap:10px}
.gg-ig-c-gnum{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px}
.gg-ig-c-gnum .gg-ig-c-unit{font-size:14px;letter-spacing:1px;color:var(--gg-color-tan)}
.gg-ig-c-meter{height:22px;background:var(--gg-color-near-black);border:3px solid var(--gg-color-near-black)}
.gg-ig-c-meterfill{height:100%;width:var(--w);background:var(--gg-color-light-gold)}
.gg-ig-c .gg-ig-c-gtip{font-size:16px;line-height:1.45}

/* fueling timeline */
.gg-ig-c-steps{list-style:none;margin:0;padding:0;position:relative}
.gg-ig-c-steps::before{content:"";position:absolute;top:14px;bottom:14px;left:190px;width:6px;background:var(--gg-color-secondary-brown);transform:translateX(-50%)}
.gg-ig-c-step{display:grid;grid-template-columns:160px 60px minmax(0,1fr);align-items:start;padding:0 0 26px;margin:0;position:relative}
.gg-ig-c-step:last-child{padding-bottom:0}
.gg-ig-c-steptime{font-family:var(--gg-font-data);font-size:18px;font-weight:700;color:var(--gg-color-light-gold);text-align:right;padding-top:1px}
.gg-ig-c-stepdot{width:26px;height:26px;background:var(--gg-color-light-gold);border:4px solid var(--gg-color-dark-brown);outline:3px solid var(--gg-color-light-gold);justify-self:center;margin-top:0;position:relative}
.gg-ig-c-stepbody{display:flex;flex-direction:column;gap:4px;min-width:0}
.gg-ig-c-stepbody strong{font-size:24px;line-height:1.2;color:var(--gg-color-white)}
.gg-ig-c-stepsum{font-size:18px;line-height:1.4;color:var(--gg-color-warm-paper);font-weight:600}
.gg-ig-c-stepdet{font-size:16px;line-height:1.5;color:var(--gg-color-sand)}

/* paired stat tiles (bonk math, glycogen) */
.gg-ig-c-pair{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:0 0 24px}
.gg-ig-c-tile{border:3px solid var(--gg-color-dark-brown);background:var(--gg-color-white);padding:16px 18px;display:flex;flex-direction:column;gap:6px;min-width:0}
.gg-ig-c-tilenum{font-family:var(--gg-font-data);font-size:clamp(40px,9vw,64px);font-weight:700;line-height:1;letter-spacing:-1px;font-variant-numeric:tabular-nums}
.gg-ig-c-tilelab{font-size:16px;line-height:1.35}
.gg-ig-c-tile--hot{background:var(--gg-color-dark-brown);color:var(--gg-color-warm-paper)}
.gg-ig-c-tile--hot .gg-ig-c-tilenum{color:var(--gg-color-light-gold)}
.gg-ig-c-tile--teal{background:var(--gg-color-teal);color:var(--gg-color-white)}
.gg-ig-c-gels{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:6px}
.gg-ig-c-gel{aspect-ratio:1/1.1;background:var(--gg-color-dark-brown);color:var(--gg-color-light-gold);display:flex;align-items:center;justify-content:center;font-family:var(--gg-font-data);font-size:14px;font-weight:700;border-bottom:6px solid var(--gg-color-light-gold)}
.gg-ig-c .gg-ig-c-gelnote{margin-top:12px;font-size:18px}

/* hydration calculator */
.gg-ig-c-fields{display:grid;gap:8px;margin:0 0 24px}
.gg-ig-c-field{display:grid;grid-template-columns:170px minmax(0,1fr) 90px;gap:16px;align-items:center;min-height:52px}
.gg-ig-c-flabel{font-family:var(--gg-font-data);font-size:15px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--gg-color-warm-paper)}
.gg-ig-c-fval{font-family:var(--gg-font-data);font-size:20px;font-weight:700;color:var(--gg-color-light-gold);font-variant-numeric:tabular-nums;white-space:nowrap}
.gg-ig-c-slider{-webkit-appearance:none;appearance:none;width:100%;height:44px;background:transparent;margin:0;cursor:pointer}
.gg-ig-c-slider::-webkit-slider-runnable-track{height:14px;background:var(--gg-color-near-black);border:3px solid var(--gg-color-tan)}
.gg-ig-c-slider::-moz-range-track{height:8px;background:var(--gg-color-near-black);border:3px solid var(--gg-color-tan)}
.gg-ig-c-slider::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:28px;height:44px;margin-top:-17px;background:var(--gg-color-light-gold);border:3px solid var(--gg-color-near-black);border-radius:0}
.gg-ig-c-slider::-moz-range-thumb{width:22px;height:38px;background:var(--gg-color-light-gold);border:3px solid var(--gg-color-near-black);border-radius:0}
.gg-ig-c-slider:focus-visible{outline:3px solid var(--gg-color-light-teal);outline-offset:2px}
.gg-ig-c-results{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.gg-ig-c-res{border:3px solid var(--gg-color-secondary-brown);padding:14px 16px;display:flex;flex-direction:column;gap:6px;min-width:0}
.gg-ig-c-resnum{font-family:var(--gg-font-data);font-size:clamp(24px,5vw,34px);font-weight:700;color:var(--gg-color-white);font-variant-numeric:tabular-nums}

/* horizontal bars: glycogen, calories */
.gg-ig-c-scens{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.gg-ig-c-scen{border:3px solid var(--gg-color-dark-brown);background:var(--gg-color-white);padding:16px 18px 18px;min-width:0}
.gg-ig-c-scentitle{font-family:var(--gg-font-data);font-size:15px;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:14px}
.gg-ig-c-hbar,.gg-ig-c-crow{display:grid;grid-template-columns:64px minmax(0,1fr) 56px;gap:12px;align-items:center;margin-bottom:10px}
.gg-ig-c-hlab{font-family:var(--gg-font-data);font-size:14px;font-weight:700}
.gg-ig-c-htrack{height:28px;background:var(--gg-color-sand);border:3px solid var(--gg-color-dark-brown)}
.gg-ig-c-hfill{height:100%;width:var(--w)}
.gg-ig-c-hfill--unfed{background:var(--gg-color-dark-brown)}
.gg-ig-c-hfill--fed{background:var(--gg-color-teal)}
.gg-ig-c-hfill--cal{background:var(--gg-color-dark-brown)}
.gg-ig-c-hval,.gg-ig-c-cum{font-family:var(--gg-font-data);font-size:16px;font-weight:700;text-align:right;font-variant-numeric:tabular-nums}
.gg-ig-c .gg-ig-c-scensum{margin-top:12px;font-size:17px;line-height:1.4;font-weight:600}
.gg-ig-c-cal .gg-ig-c-crow{grid-template-columns:48px minmax(0,1fr) 52px 60px;margin-bottom:8px}
.gg-ig-c-crow--head{margin-bottom:4px}
.gg-ig-c-crow--head span{font-family:var(--gg-font-data);font-size:12px;font-weight:700;letter-spacing:1px;color:var(--gg-color-secondary-brown)}
.gg-ig-c-cal .gg-ig-c-htrack{height:26px}

/* macro split */
.gg-ig-c-stack{display:flex;height:56px;border:3px solid var(--gg-color-warm-paper);margin:0 0 24px}
.gg-ig-c-seg{display:block;width:var(--w);height:100%}
.gg-ig-c-seg--carb{background:var(--gg-color-light-gold)}
.gg-ig-c-seg--protein{background:var(--gg-color-white);border-left:3px solid var(--gg-color-dark-brown);border-right:3px solid var(--gg-color-dark-brown)}
.gg-ig-c-seg--fat{background:var(--gg-color-secondary-brown)}
.gg-ig-c-macros{display:grid;gap:18px}
.gg-ig-c-macro{display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:4px 14px;align-items:baseline}
.gg-ig-c-macro .gg-ig-c-swatch{align-self:center;margin-top:0}
.gg-ig-c-macroname{font-size:22px;font-weight:700;color:var(--gg-color-white)}
.gg-ig-c-macrorange{font-family:var(--gg-font-data);font-size:24px;font-weight:700;color:var(--gg-color-light-gold)}
.gg-ig-c .gg-ig-c-macrotip{grid-column:2 / -1;font-size:16px;line-height:1.45;color:var(--gg-color-sand)}

@media (max-width:720px){
.gg-ig-c-head{padding:16px 16px 18px}
.gg-ig-c .gg-ig-c-title{font-size:26px}
.gg-ig-c-body{padding:20px 16px 18px}
.gg-ig-c-sigs,.gg-ig-c-gauges,.gg-ig-c-scens,.gg-ig-c-legend{grid-template-columns:1fr}
.gg-ig-c-results{grid-template-columns:1fr}
.gg-ig-c-res{flex-direction:row;align-items:baseline;justify-content:space-between}
.gg-ig-c-cols{gap:6px}
.gg-ig-c-track{height:200px}
.gg-ig-c-collab{font-size:12px}
.gg-ig-c-steps::before{left:13px}
.gg-ig-c-step{grid-template-columns:26px minmax(0,1fr);gap:0 16px;padding-bottom:24px}
.gg-ig-c-steptime{grid-column:2;grid-row:1;text-align:left;padding:0 0 6px}
.gg-ig-c-stepdot{grid-column:1;grid-row:1 / span 2}
.gg-ig-c-stepbody{grid-column:2;grid-row:2}
.gg-ig-c-field{grid-template-columns:minmax(0,1fr) auto;gap:0 12px}
.gg-ig-c-slider{grid-column:1 / -1;grid-row:2}
.gg-ig-c-gels{grid-template-columns:repeat(6,minmax(0,1fr))}
.gg-ig-c-macro{grid-template-columns:22px minmax(0,1fr)}
.gg-ig-c-macrorange{grid-column:2;grid-row:2}
.gg-ig-c .gg-ig-c-macrotip{grid-column:2;grid-row:3}
.gg-ig-c-cal .gg-ig-c-crow{grid-template-columns:40px minmax(0,1fr) 44px 54px;gap:8px}
.gg-ig-c-pair{gap:10px}
.gg-ig-c-pair--wide{grid-template-columns:1fr}
.gg-ig-c-hs{display:none}
.gg-ig-c-delta{font-size:12px}
.gg-ig-c-tile{padding:12px}
.gg-ig-c-hero--eq .gg-ig-c-big{white-space:normal}
}
@media (prefers-reduced-motion:no-preference){
.gg-ig-c-meterfill,.gg-ig-c-hfill,.gg-ig-c-colbar{transition:none}
}
"""


JS = """
/* Chapter 4-5 charts: hydration calculator */
document.querySelectorAll(".gg-ig-c-hydra").forEach(function(root){
  var inputs={};
  root.querySelectorAll("input[data-in]").forEach(function(el){inputs[el.getAttribute("data-in")]=el;});
  function out(name){return root.querySelector("[data-out='"+name+"']");}
  function fmt(n){return Math.round(n).toLocaleString("en-US");}
  function update(){
    var dur=parseFloat(inputs.duration.value);
    var temp=parseFloat(inputs.temp.value);
    var inten=parseFloat(inputs.intensity.value);
    var heat=Math.min(150,Math.max(0,(temp-60)*5));
    var rate=500+heat+(inten-1)*12.5;
    var total=rate*dur;
    var sodiumRate=rate*1.2;
    var vals={duration:dur+" hrs",temp:temp+"\\u00b0F",intensity:inten+" / 5"};
    Object.keys(vals).forEach(function(k){
      var o=root.querySelector("[data-val='"+k+"']");
      if(o)o.textContent=vals[k];
    });
    out("fluid").textContent=fmt(total);
    out("sodium").textContent=fmt(sodiumRate*dur)+" mg";
    out("rate").textContent=fmt(rate)+" ml";
    out("bottles").textContent="~"+(rate/500).toFixed(1);
  }
  Object.keys(inputs).forEach(function(k){inputs[k].addEventListener("input",update);});
  update();
});
"""
