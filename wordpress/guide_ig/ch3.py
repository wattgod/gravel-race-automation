"""Chapter 3 (Training) charts, rebuilt as poster panels.

Static markup: SVG draws only the lines and fills (stretched, non-scaling
strokes); every label, tick and marker is HTML so text stays a real 14px+ at
any width. No script needed.
"""
import html as _html
import math

from guide_ig import glyph

P = "gg-ig-b"


def _e(v) -> str:
    """Escape any value for HTML. 0 prints as 0."""
    return _html.escape("" if v is None else str(v), quote=True)


def _smooth(pts):
    """Monotone cubic through points -> SVG path (no overshoot, passes every point)."""
    n = len(pts)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    d = [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) for i in range(n - 1)]
    m = [d[0]] + [
        (d[i - 1] + d[i]) / 2 if d[i - 1] * d[i] > 0 else 0 for i in range(1, n - 1)
    ] + [d[-1]]
    for i in range(n - 1):
        if d[i] == 0:
            m[i] = m[i + 1] = 0
            continue
        a, b = m[i] / d[i], m[i + 1] / d[i]
        s = a * a + b * b
        if s > 9:
            t = 3 / math.sqrt(s)
            m[i], m[i + 1] = t * a * d[i], t * b * d[i]
    out = [f"M{xs[0]:.1f},{ys[0]:.1f}"]
    for i in range(n - 1):
        h = xs[i + 1] - xs[i]
        out.append(
            f"C{xs[i] + h / 3:.1f},{ys[i] + m[i] * h / 3:.1f} "
            f"{xs[i + 1] - h / 3:.1f},{ys[i + 1] - m[i + 1] * h / 3:.1f} "
            f"{xs[i + 1]:.1f},{ys[i + 1]:.1f}"
        )
    return " ".join(out)


def _panel(block, theme, eyebrow, title, hero, hero_text, body, default_caption=""):
    cap = block.get("caption") or default_caption
    cap_html = f'<figcaption class="{P}-cap">{_e(cap)}</figcaption>' if cap else ""
    return (
        f'<figure class="{P}-panel {P}-panel--{theme}">'
        f'<header class="{P}-head"><p class="{P}-eyebrow">{_e(eyebrow)}</p>'
        f'<h3 class="{P}-title">{_e(title)}</h3></header>'
        f'<div class="{P}-hero"><p class="{P}-hero-num">{_e(hero)}</p>'
        f'<p class="{P}-hero-text">{_e(hero_text)}</p></div>'
        f'<div class="{P}-body">{body}</div>'
        f'{cap_html}</figure>'
    )


def _alt(block, fallback):
    return _e(block.get("alt") or fallback)


# ── 1. Supercompensation ────────────────────────────────────

_SC_PTS = [
    (0.00, 0), (0.05, 5), (0.10, -10), (0.15, -80), (0.20, -120), (0.25, -100),
    (0.30, -60), (0.35, -20), (0.40, 0), (0.45, 30), (0.50, 55), (0.55, 70),
    (0.60, 65), (0.65, 50), (0.70, 30), (0.75, 15), (0.80, 5), (0.85, 0),
    (0.90, -5), (0.95, -8), (1.00, -10),
]
_SC_STAGES = [
    (0.10, -10, "Training stress", "The workout itself — muscle fiber damage and glycogen depletion"),
    (0.20, -120, "Fatigue", "Performance dips below baseline as body repairs damage"),
    (0.35, -20, "Recovery", "Repair and adaptation — sleep, nutrition, and easy days"),
    (0.55, 70, "Supercompensation", "The window where fitness exceeds previous baseline — train again here"),
    (0.80, 5, "Detraining", "Wait too long and you lose the adaptation gains"),
]


def render_supercompensation(block: dict) -> str:
    W, H = 1000, 400
    lo, hi = -150, 100  # offset range shown

    def y(off):
        return (hi - off) / (hi - lo) * H

    pts = [(f * W, y(o)) for f, o in _SC_PTS]
    path = _smooth(pts)
    base = y(0)
    area = f"{path} L{W},{base:.1f} L0,{base:.1f} Z"
    svg = (
        f'<svg class="{P}-sc-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">'
        f'<defs><clipPath id="{P}-sc-up"><rect x="0" y="0" width="{W}" height="{base:.1f}"/></clipPath>'
        f'<clipPath id="{P}-sc-dn"><rect x="0" y="{base:.1f}" width="{W}" height="{H - base:.1f}"/></clipPath></defs>'
        f'<path class="{P}-sc-up" d="{area}" clip-path="url(#{P}-sc-up)"/>'
        f'<path class="{P}-sc-dn" d="{area}" clip-path="url(#{P}-sc-dn)"/>'
        f'<line class="{P}-sc-base" x1="0" y1="{base:.1f}" x2="{W}" y2="{base:.1f}"/>'
        f'<path class="{P}-sc-line" d="{path}"/></svg>'
    )
    marks = []
    legend = []
    for i, (fx, off, name, tip) in enumerate(_SC_STAGES, 1):
        marks.append(
            f'<span class="{P}-mark" style="left:{fx * 100:.1f}%;top:{y(off) / H * 100:.1f}%" aria-hidden="true">{i}</span>'
        )
        legend.append(
            f'<li class="{P}-sc-step"><span class="{P}-mark {P}-mark--static" aria-hidden="true">{i}</span>'
            f'<div><strong class="{P}-sc-name">{_e(name)}</strong>'
            f'<span class="{P}-sc-tip">{_e(tip)}</span></div></li>'
        )
    body = (
        f'<div class="{P}-sc-plot" role="img" aria-label="{_alt(block, "Supercompensation curve: stress drops fitness below baseline, recovery brings it back, then it overshoots before fading")}">'
        f'{svg}{"".join(marks)}</div>'
        f'<p class="{P}-sc-key"><span class="{P}-sc-dash" aria-hidden="true"></span>Baseline: where you started</p>'
        f'<ol class="{P}-sc-steps">{"".join(legend)}</ol>'
    )
    return _panel(
        block, "dark", "CH 3 · RECOVERY", "Supercompensation: Why Rest Makes You Faster",
        "REST = FASTER",
        "You don’t get faster during the workout — you get faster during recovery.",
        body, "The foundational model — train, recover, adapt, repeat.",
    )


# ── 2. Zone spectrum ────────────────────────────────────────

_ZONES = [
    ("Z1", "Active Recovery", "≤55%", 0, 55, "Easy spinning, <55% FTP. Promotes blood flow and recovery."),
    ("Z2", "Endurance", "55-75%", 55, 75, "55-75% FTP. The foundation of all gravel training."),
    ("Z3", "Tempo", "76-90%", 76, 90, "76-90% FTP. Comfortably hard — the sweet spot for long rides."),
    ("Z4", "Threshold", "91-105%", 91, 105, "91-105% FTP. Race pace for short-course gravel events."),
    ("Z5", "VO2max", "106-120%", 106, 120, "106-120% FTP. Hard intervals that build top-end power."),
    ("Z6", "Anaerobic", "121-150%", 121, 150, "121-150% FTP. Short punchy efforts for climbs and surges."),
    ("Z7", "Neuromuscular", "Max", 150, 170, "Max effort sprints. Rarely needed in gravel racing."),
]


def render_zone_spectrum(block: dict) -> str:
    span = 170.0
    rows = []
    for code, name, rng, a, b, desc in _ZONES:
        hot = code in ("Z2", "Z3", "Z4")
        rows.append(
            f'<li class="{P}-zn-row{" " + P + "-zn-row--hot" if hot else ""}">'
            f'<div class="{P}-zn-info"><span class="{P}-zn-code">{_e(code)}</span>'
            f'<span class="{P}-zn-name">{_e(name)}</span>'
            f'<span class="{P}-zn-range">{_e(rng)}</span></div>'
            f'<div class="{P}-zn-viz"><div class="{P}-zn-track">'
            f'<span class="{P}-zn-bar" style="left:{a / span * 100:.2f}%;width:{(b - a) / span * 100:.2f}%"></span></div>'
            f'<p class="{P}-zn-desc">{_e(desc)}</p></div></li>'
        )
    ticks = "".join(
        f'<span style="left:{t / span * 100:.2f}%">{t}%</span>' for t in (0, 50, 100, 150)
    )
    body = (
        f'<div class="{P}-zn" role="img" aria-label="{_alt(block, "Seven training zones from Z1 Active Recovery to Z7 Neuromuscular on a percent of FTP scale; Z2 to Z4 highlighted")}">'
        f'<div class="{P}-zn-axis" aria-hidden="true"><span class="{P}-zn-axis-pad"></span>'
        f'<div class="{P}-zn-ticks">{ticks}</div></div>'
        f'<ol class="{P}-zn-list">{"".join(rows)}</ol></div>'
    )
    return _panel(
        block, "light", "CH 3 · ZONES", "The Seven Training Zones",
        "Z2–Z4",
        "Gravel racing lives in Zones 2–4. Build your base there before chasing intensity.",
        body, "The zone spectrum — from recovery spin to redline effort.",
    )


# ── 3. Performance management chart ─────────────────────────

_CTL = [25, 30, 36, 43, 50, 57, 63, 70, 75, 78, 72, 65]
_ATL = [30, 45, 55, 50, 65, 70, 60, 80, 75, 50, 35, 25]
def _glyph_panel(block, eyebrow, title, card, default_caption=""):
    """GG title band + Glyph card on a light ground + gold-ruled caption."""
    cap = block.get("caption") or default_caption
    cap_html = f'<figcaption class="{P}-cap">{_e(cap)}</figcaption>' if cap else ""
    return (
        f'<figure class="{P}-panel {P}-panel--light">'
        f'<header class="{P}-head"><p class="{P}-eyebrow">{_e(eyebrow)}</p>'
        f'<h3 class="{P}-title">{_e(title)}</h3></header>'
        f'<div class="{P}-eg-body">{card}</div>{cap_html}</figure>'
    )


_TSB = [-5, -15, -19, -7, -15, -13, 3, -10, 0, 28, 37, 40]
_PMC_NOW = 9  # week 10: race ready; weeks 11-12 are the taper plan


def _pmc_weekly_load():
    """Weekly load (~) implied by the fatigue line. ATL is a 7-day exponential average, so a
    steady daily load L through a week moves it from a0 to L + (a0 - L)/e. Solving for L and
    times 7 gives the week's load. Week 1 has no earlier week: unknown (None), drawn hatched."""
    k = math.exp(-1)
    return [None] + [round(7 * (_ATL[i] - _ATL[i - 1] * k) / (1 - k)) for i in range(1, 12)]


def _pmc_text(i, load):
    """Header strings for week index i (mirrored by the script's update())."""
    d = _CTL[i] - _CTL[i - 1] if i else 0
    chip = "first week" if i == 0 else f'{"▲" if d > 0 else "▼" if d < 0 else "="} {abs(d)} vs wk {i}'
    when = f"Week {i + 1}" + (" · now" if i == _PMC_NOW else " · plan" if i > _PMC_NOW else "")
    ld = "⚡ no prior week" if load[i] is None else f"⚡ ~{load[i]} that week"
    form = f"+{_TSB[i]}" if _TSB[i] > 0 else str(_TSB[i])
    return chip, when, ld, form


def render_pmc_chart(block: dict) -> str:
    W, LH, BH = 1200, 240, 56
    load = _pmc_weekly_load()
    xs = [(i + 0.5) / 12 * W for i in range(12)]
    ys = lambda v: LH * (1 - v / 100)  # noqa: E731
    cs = glyph.mono_sample([(xs[i], ys(_CTL[i])) for i in range(12)], 24)
    fs = glyph.mono_sample([(xs[i], ys(_ATL[i])) for i in range(12)], 24)
    cut = _PMC_NOW * 24

    # difference band: teal where fitness leads, pink where fatigue does
    runs = []

    def push(sign, t, b):
        if runs and runs[-1][0] == sign:
            runs[-1][1].append(t)
            runs[-1][2].append(b)
        else:
            runs.append([sign, [t], [b]])

    for k in range(len(cs)):
        d0 = fs[k][1] - cs[k][1]
        s0 = 1 if d0 >= 0 else -1
        push(s0, cs[k], fs[k])
        if k + 1 < len(cs):
            d1 = fs[k + 1][1] - cs[k + 1][1]
            s1 = 1 if d1 >= 0 else -1
            if s0 != s1:
                t = d0 / (d0 - d1)
                x = cs[k][0] + t * (cs[k + 1][0] - cs[k][0])
                y = cs[k][1] + t * (cs[k + 1][1] - cs[k][1])
                push(s0, (x, y), (x, y))
                push(s1, (x, y), (x, y))
    band = "".join(
        f'<path class="{P}-eg-band {P}-eg-band--{"teal" if s > 0 else "pink"}" '
        f'd="{glyph.line_path(top + bot[::-1], close=True)}"/>'
        for s, top, bot in runs
    )
    refs = "".join(
        f'<line class="{P}-eg-ref" x1="0" x2="{W}" y1="{ys(v):.1f}" y2="{ys(v):.1f}"/>' for v in (0, 50, 100)
    )
    lines = (
        f'<path class="{P}-eg-fat" d="{glyph.line_path(fs[:cut + 1])}"/>'
        f'<path class="{P}-eg-fat {P}-eg-plan" d="{glyph.line_path(fs[cut:])}"/>'
        f'<path class="{P}-eg-case" d="{glyph.line_path(cs[:cut + 1])}"/>'
        f'<path class="{P}-eg-hero" d="{glyph.line_path(cs[:cut + 1])}"/>'
        f'<path class="{P}-eg-hero {P}-eg-plan" d="{glyph.line_path(cs[cut:])}"/>'
    )
    svg_lines = (
        f'<svg class="gg-eg-svg" viewBox="0 0 {W} {LH}" preserveAspectRatio="none" aria-hidden="true">'
        f'{band}{refs}{lines}</svg>'
    )
    top_load = max(v for v in load if v)
    bars = [glyph.hatch_def("gg-eg-hatch-pmc")]
    for i in range(12):
        x = xs[i] - 24
        if load[i] is None:
            bars.append(f'<rect class="{P}-eg-hat" x="{x:.1f}" y="{BH - 26}" width="48" height="26" fill="url(#gg-eg-hatch-pmc)"/>')
            continue
        h = load[i] / top_load * (BH - 6)
        cls = f"{P}-eg-bar" + (f" {P}-eg-bar--plan" if i > _PMC_NOW else "")
        bars.append(f'<rect class="{cls}" x="{x:.1f}" y="{BH - h:.1f}" width="48" height="{h:.1f}"/>')
    svg_bars = (
        f'<svg class="gg-eg-svg" viewBox="0 0 {W} {BH}" preserveAspectRatio="none" aria-hidden="true">'
        f'{"".join(bars)}</svg>'
    )
    ylab = "".join(
        f'<span class="{P}-eg-yl{" " + P + "-eg-yl--top" if v == 100 else ""}" style="top:{100 - v}%">{v}</span>'
        for v in (100, 50, 0)
    )
    nowx = xs[_PMC_NOW] / W * 100
    plot = (
        f'<div class="{P}-eg-past" style="width:{nowx:.2f}%"></div>'
        f'<div class="{P}-eg-lines">{svg_lines}{ylab}'
        f'<span class="{P}-eg-plan-l" style="left:{nowx:.2f}%">Plan</span>'
        f'<span class="{P}-eg-note" style="left:{nowx:.2f}%;top:{100 - _CTL[_PMC_NOW]}%">Race ready</span>'
        f'<i class="gg-eg-pt" data-eg-pt style="left:{nowx:.2f}%;top:{100 - _CTL[_PMC_NOW]}%"></i></div>'
        f'<div class="{P}-eg-bars">{svg_bars}</div>'
    )
    chip, when, ld, form = _pmc_text(_PMC_NOW, load)
    vt = f"Week {_PMC_NOW + 1}: {_CTL[_PMC_NOW]} fitness, {_ATL[_PMC_NOW]} fatigue, form {form}"
    pw = glyph.scrub_wrap("ch3-pmc", plot, 12, _PMC_NOW, "Scrub the 12 weeks", vt, mode="band")
    ends = (
        f'<div class="{P}-eg-ends">'
        f'<div style="top:{100 - _CTL[11]}%">{glyph.capsule(_CTL[11], "Fitness", "ink", "dotted")}</div>'
        f'<div style="top:{100 - (_CTL[11] + _ATL[11]) / 2}%">{glyph.capsule(f"+{_TSB[11]}", "Form", "teal", "dotted")}</div>'
        f'<div style="top:{100 - _ATL[11]}%">{glyph.capsule(_ATL[11], "Fatigue", "pink", "dotted")}</div></div>'
        f'<span class="{P}-eg-loadl">⚡ load</span>'
    )
    extra = (
        glyph.capsule(_ATL[_PMC_NOW], "Fatigue", "pink", field="fat")
        + glyph.capsule(form, "Form", "teal", field="form")
        + f'<span data-eg-f="load">{_e(ld)}</span>'
    )
    head = glyph.readout(_CTL[_PMC_NOW], "fitness", chip, when, extra)
    alt = block.get("alt") or "12-week performance management chart: fitness climbs from 25 to 78, fatigue swings, form turns positive at week 10 for race week"
    desc = (
        f"{alt}. Chronic Training Load (fitness): {', '.join(map(str, _CTL))}. "
        f"Acute Training Load (fatigue): {', '.join(map(str, _ATL))}. "
        f"Training Stress Balance (form), fitness minus fatigue: "
        f"{', '.join(('+' if v > 0 else '') + str(v) for v in _TSB)}. "
        "Weeks 11 and 12 are planned. Week 10 is race ready."
    )
    data = {"fit": _CTL, "fat": _ATL, "frm": _TSB, "load": load, "now": _PMC_NOW}
    card = glyph.glyph_card(
        "Fitness, fatigue, form", head,
        f'<div class="{P}-eg-wrap">{pw}{ends}</div>',
        data=data, describedby="gg-eg-pmc-d", description=desc,
    )
    return _glyph_panel(
        block, "CH 3 · LOAD", "The Performance Management Chart: Fitness, Fatigue, Form", card,
        "CTL builds slowly. ATL spikes fast. TSB tells you when to race.",
    )


# ── 4. Training phases ──────────────────────────────────────

_VOL = [0.30, 0.40, 0.55, 0.65, 0.75, 0.85, 0.90, 0.80, 0.65, 0.50, 0.35, 0.25]
_INT = [0.15, 0.18, 0.20, 0.25, 0.30, 0.45, 0.60, 0.75, 0.85, 0.80, 0.50, 0.30]
_PHASES = [
    ("BASE", "WK 1–5", 5, "base", "Weeks 1-5: Long Z2 rides, build aerobic engine. 3-5 rides/week."),
    ("BUILD", "WK 6–9", 4, "build", "Weeks 6-9: Add intervals, tempo, and race-specificity."),
    ("PEAK / TAPER", "WK 10–12", 3, "peak", "Weeks 10-12: Reduce volume 40%, maintain intensity, rest up."),
]


def render_training_phases(block: dict) -> str:
    def phase_of(i):
        return "base" if i < 5 else ("build" if i < 9 else "peak")

    def row(label, vals, kind):
        cols = "".join(
            f'<div class="{P}-tp-col {P}-tp-col--{phase_of(i)}"><span class="{P}-tp-bar {P}-tp-bar--{kind}" '
            f'style="--h:{v * 100:.0f}"></span></div>'
            for i, v in enumerate(vals)
        )
        return f'<p class="{P}-tp-label">{label}</p><div class="{P}-tp-row">{cols}</div>'

    heads = "".join(
        f'<div class="{P}-tp-ph {P}-tp-ph--{k}" style="flex:{w}"><b>{_e(n)}</b><span>{_e(wk)}</span></div>'
        for n, wk, w, k, _ in _PHASES
    )
    wk = "".join(f'<span>{i}</span>' for i in range(1, 13))
    cards = "".join(
        f'<li class="{P}-tp-card {P}-tp-card--{k}"><b>{_e(n)}</b><span>{_e(t)}</span></li>'
        for n, _, _, k, t in _PHASES
    )
    body = (
        f'<div class="{P}-tp" role="img" aria-label="{_alt(block, "12-week periodization: volume builds through Base and peaks in week 7, intensity ramps through Build and peaks in week 9, both fall into the taper")}">'
        f'<div class="{P}-tp-heads">{heads}</div>'
        f'{row("VOLUME", _VOL, "vol")}{row("INTENSITY", _INT, "int")}'
        f'<div class="{P}-tp-wk" aria-hidden="true">{wk}</div>'
        f'<p class="{P}-tp-wkl">WEEK</p></div>'
        f'<ul class="{P}-tp-cards">{cards}</ul>'
    )
    return _panel(
        block, "light", "CH 3 · PERIODIZATION", "Periodization: Building Fitness in Three Phases",
        "12 WEEKS",
        "Base → Build → Peak. Skip base and your peak will have no foundation.",
        body, "The 12-week build: volume peaks in Base, intensity peaks in Build, both taper for race day.",
    )


# ── 5. Power-duration ───────────────────────────────────────

_PD = [
    (5, 900), (10, 750), (30, 500), (60, 380), (120, 310), (300, 270), (600, 255),
    (1200, 250), (1800, 245), (3600, 235), (7200, 220), (14400, 195), (28800, 170),
]
_PD_KEYS = [
    (60, 380, "1-min power", "Punch power for steep climbs and surges"),
    (1200, 250, "FTP (20 min)", "Your sustainable race-pace power"),
    (14400, 195, "4-hr power", "Long-race power — typically 78% of FTP"),
]
_PD_N = 201
_PD_DEF = 184  # index nearest 4 h, the round-1 hero (195 W)
_PD_WMIN, _PD_WMAX = 100, 1000
# Coggan % of FTP (round 1: 138-188 / 188-225 / 225-263 W at 250 W)
_PD_ZONES = [
    ("Z2", "Endurance", 55, 75, 1),
    ("Z3", "Tempo", 75, 90, 2),
    ("Z4", "Threshold", 90, 105, 3),
]
_PD_FTP, _PD_KG = 250, 75


def _pd_round(x):
    return int(math.floor(x + 0.5))


def _pd_dur(s):
    """Duration label, mirrored by the script (5 s, 1 min, 1.5 min, 20 min, 4 h)."""
    def trim(v, d):
        return f"{round(v, d):.{d}f}".rstrip("0").rstrip(".") if d else str(int(round(v)))
    if s < 60:
        return f"{int(round(s))} s"
    if s < 3600:
        m = s / 60
        return f"{trim(m, 1 if m < 10 else 0)} min"
    return f"{trim(s / 3600, 1)} h"


def render_power_duration(block: dict) -> str:
    W, H = 1000, 400
    a, b = math.log10(5), math.log10(28800)
    curve = glyph.mono_curve([(math.log10(s), w) for s, w in _PD])
    samples = []
    for k in range(_PD_N):
        ls = a + (b - a) * k / (_PD_N - 1)
        samples.append((ls, curve(ls)))
    watts = [round(w, 1) for _, w in samples]
    ux = glyph.log_scale(5, 28800, 0, 100)
    uy = lambda w: (_PD_WMAX - w) / (_PD_WMAX - _PD_WMIN) * 100  # noqa: E731
    pts = [((ls - a) / (b - a) * W, (_PD_WMAX - w) / (_PD_WMAX - _PD_WMIN) * H) for ls, w in samples]
    path = glyph.line_path(pts)
    area = glyph.line_path(pts + [(W, H), (0, H)], close=True)
    svg_area = (
        f'<svg class="gg-eg-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">'
        f'<path class="{P}-eg-area" d="{area}"/></svg>'
    )
    svg = (
        f'<svg class="gg-eg-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">'
        f'<path class="{P}-eg-case" d="{path}"/><path class="{P}-eg-hero {P}-eg-hero--ride" d="{path}"/></svg>'
    )
    bands = "".join(
        f'<div class="{P}-eg-zb {P}-eg-zb--{n}" data-eg-zb="{i}" '
        f'style="top:{uy(_pd_round(hi / 100 * _PD_FTP)):.2f}%;'
        f'height:{(_pd_round(hi / 100 * _PD_FTP) - _pd_round(lo / 100 * _PD_FTP)) / (_PD_WMAX - _PD_WMIN) * 100:.2f}%">'
        f'<span>{code}</span></div>'
        for i, (code, _, lo, hi, n) in enumerate(_PD_ZONES)
    )
    ticks = "".join(
        f'<div class="{P}-eg-tk" style="top:{uy(v):.2f}%"><span>{v}</span></div>' for v in (250, 500, 750)
    )
    keys = "".join(
        f'<div class="{P}-eg-key{" " + P + "-eg-key--end" if s > 10000 else ""}" data-eg-key="{i}" '
        f'style="left:{ux(s):.2f}%;top:{uy(w):.2f}%">{glyph.capsule(f"{w} W", "", "ride", "outlined")}</div>'
        for i, (s, w, _, _) in enumerate(_PD_KEYS)
    )
    f0 = _PD_DEF / (_PD_N - 1)
    w0 = round(watts[_PD_DEF])
    plot = (
        f'{svg_area}{bands}<div class="{P}-eg-ticks" data-eg-ticks>{ticks}</div>{svg}{keys}'
        f'<i class="gg-eg-pt" data-eg-pt style="left:{f0 * 100:.2f}%;top:{uy(watts[_PD_DEF]):.2f}%"></i>'
    )
    vt = f"{_pd_dur(5 * (28800 / 5) ** f0)}: {w0} W"
    pw = glyph.scrub_wrap("ch3-pd", plot, _PD_N, _PD_DEF, "Scrub along durations", vt, mode="point")
    xt = "".join(
        f'<span class="{P}-eg-xt{" " + P + "-eg-xt--opt" if opt else ""}" style="left:{ux(s):.2f}%">{lbl}</span>'
        for s, lbl, opt in ((5, "5 s", 0), (60, "1 min", 0), (300, "5 min", 1), (1200, "20 min", 0), (3600, "1 h", 1), (14400, "4 h", 0), (28800, "8 h", 2))
    )
    ruler = f'<div class="{P}-eg-ruler" aria-hidden="true">{xt}</div>'
    zr = lambda lo, hi: f"{_pd_round(lo / 100 * _PD_FTP)}–{_pd_round(hi / 100 * _PD_FTP)} W"  # noqa: E731
    ledger = "".join(
        f'<li><span class="{P}-eg-zs {P}-eg-zb--{n}"></span><b>{code}</b> {_e(name)} '
        f'<span class="{P}-eg-zr" data-eg-zr="{i}">{zr(lo, hi)}</span></li>'
        for i, (code, name, lo, hi, n) in enumerate(_PD_ZONES)
    )
    controls = (
        f'<span class="gg-eg-seg" role="group" aria-label="Unit">'
        f'<button type="button" data-eg-unit="w" aria-pressed="true">W</button>'
        f'<button type="button" data-eg-unit="wkg" aria-pressed="false">W/kg</button></span>'
        f'<label class="gg-eg-field">Weight<input type="number" inputmode="decimal" min="30" max="200" step="0.5" '
        f'value="{_PD_KG}" data-eg-in="kg" aria-label="Rider weight in kilograms"> kg</label>'
        f'<label class="gg-eg-field">FTP<input type="number" inputmode="numeric" min="100" max="500" step="1" '
        f'value="{_PD_FTP}" data-eg-in="ftp" aria-label="Functional threshold power in watts"> W</label>'
    )
    pct = _pd_round(w0 / _PD_FTP * 100)
    dlt = w0 - _PD_FTP
    extra = glyph.capsule(f"{dlt:+d}".replace("+0", "0"), "vs FTP", "ride", "filled", field="delta")
    head = glyph.readout(w0, "W", f"{pct}% of FTP", _pd_dur(5 * (28800 / 5) ** f0), extra)
    alt = block.get("alt") or "Power-duration curve for a 250 W FTP rider: 900 W at 5 seconds falling to 170 W at 8 hours, with Z2 to Z4 bands between 138 and 263 W"
    desc = (
        f"{alt}. Key points: " + "; ".join(f"{lbl} {w} W at {_pd_dur(s)}" for s, w, lbl, _ in _PD_KEYS)
        + ". Zones as percent of FTP: " + "; ".join(f"{c} {name} {lo} to {hi}%" for c, name, lo, hi, _ in _PD_ZONES) + "."
    )
    data = {
        "w": watts, "s0": 5, "s1": 28800, "ftp": _PD_FTP, "kg": _PD_KG, "wmin": _PD_WMIN, "wmax": _PD_WMAX,
        "zones": [[c, lo, hi] for c, _, lo, hi, _ in _PD_ZONES],
        "keys": [[s, w] for s, w, _, _ in _PD_KEYS],
    }
    card = glyph.glyph_card(
        "Power duration curve", head,
        f'{pw}{ruler}<ul class="{P}-eg-zl">{ledger}</ul>',
        controls_html=controls, data=data, describedby="gg-eg-pd-d", description=desc,
    )
    return _glyph_panel(
        block, "CH 3 · POWER", "Your Power-Duration Curve: What You Can Sustain", card,
        "The power-duration curve — your physiological fingerprint as a rider.",
    )


# ── 6. Season Gantt ─────────────────────────────────────────

# (name, start month, end month, dates, description) on a Nov-to-Nov grid (0 = 1 Nov)
_GANTT = [
    ("Off-Season", 0, 1.5, "Nov – mid Dec", "Active recovery, cross-training, mental reset", "off"),
    ("Base 1", 1.5, 5, "Mid Dec – Mar", "Aerobic foundation, long Z2 rides, consistency", "base"),
    ("Base 2", 5, 7, "Apr – May", "Add tempo work, longer rides, race-surface training", "base"),
    ("Build", 7, 9.5, "Jun – mid Aug", "Intervals, race simulation, peak training load", "build"),
    ("Race Season", 9.5, 12, "Mid Aug – Oct", "A-race taper, B-race maintenance, peak performance", "race"),
    ("Transition", 12, 13, "Nov", "Deload, reflect, plan next year. Ride for fun.", "trans"),
]
_MONTHS = ["Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov"]


def render_gantt_season(block: dict) -> str:
    n = 13
    months = "".join(
        f'<span><i class="{P}-gt-full">{m}</i><i class="{P}-gt-short">{m[0]}</i></span>' for m in _MONTHS
    )
    rows = "".join(
        f'<li class="{P}-gt-row"><div class="{P}-gt-info"><b class="{P}-gt-name">{_e(name)}</b>'
        f'<span class="{P}-gt-dates">{_e(dates)}</span>'
        f'<span class="{P}-gt-desc">{_e(desc)}</span></div>'
        f'<div class="{P}-gt-track"><span class="{P}-gt-bar {P}-gt-bar--{k}" '
        f'style="left:{a / n * 100:.2f}%;width:{(b - a) / n * 100:.2f}%"></span></div></li>'
        for name, a, b, dates, desc, k in _GANTT
    )
    body = (
        f'<div class="{P}-gt" role="img" aria-label="{_alt(block, "A 12-month season: off-season, two base blocks, build, race season, then transition")}">'
        f'<div class="{P}-gt-months" aria-hidden="true"><span class="{P}-gt-pad"></span><div class="{P}-gt-mgrid">{months}</div></div>'
        f'<ol class="{P}-gt-list">{rows}</ol></div>'
    )
    return _panel(
        block, "light", "CH 3 · SEASON", "The Annual Training Calendar: 12 Months at a Glance",
        "6 BLOCKS",
        "Build backwards from your A-race. Every month has a purpose — even the off-season.",
        body, "A full season planned — stack race-specific blocks with recovery windows.",
    )


# ── 7. Before / after ───────────────────────────────────────

_BA = [
    ("FTP", "180W", "250W", "39% increase"),
    ("4hr Power", "140W", "195W", "Sustained race power"),
    ("Recovery HR", "95 bpm", "68 bpm", "Faster bounce-back"),
    ("Time to Exhaustion", "3.5 hrs", "7+ hrs", "Double the endurance"),
    ("Body Comp", "22% BF", "15% BF", "Power-to-weight gains"),
    ("Race Finish", "Bottom 25%", "Top 35%", "Mid-pack competitive"),
]


def render_before_after(block: dict) -> str:
    rows = "".join(
        f'<li class="{P}-ba-row"><p class="{P}-ba-metric">{_e(m)}</p>'
        f'<p class="{P}-ba-before">{_e(b)}</p>'
        f'<p class="{P}-ba-after">{_e(a)}</p>'
        f'<p class="{P}-ba-note">{_e(note)}</p></li>'
        for m, b, a, note in _BA
    )
    body = (
        f'<div class="{P}-ba-cols"><p><b>BEFORE</b><span>Untrained / 3 months</span></p>'
        f'<p><b>AFTER</b><span>12 months structured training</span></p></div>'
        f'<ul class="{P}-ba-list" aria-label="{_alt(block, "Before and after training: FTP 180 W to 250 W, 4 hour power 140 W to 195 W")}">{rows}</ul>'
    )
    return _panel(
        block, "dark", "CH 3 · RESULTS", "12 Months of Structured Training: Before vs. After",
        "+39%",
        "FTP from 180W to 250W. Consistent training transforms everything. A year of focused work can move you up two tiers.",
        body, "12 weeks of consistent training — the numbers do not lie.",
    )


RENDERERS = {
    "ch3-supercompensation": render_supercompensation,
    "ch3-zone-spectrum": render_zone_spectrum,
    "ch3-pmc-chart": render_pmc_chart,
    "ch3-training-phases": render_training_phases,
    "ch3-power-duration": render_power_duration,
    "ch3-gantt-season": render_gantt_season,
    "ch3-before-after": render_before_after,
}

JS = r"""
GGEG.register("ch3-pmc", function (i, c) {
  var d = c.data;
  var dd = i ? d.fit[i] - d.fit[i - 1] : 0;
  var chip = i === 0 ? "first week" : ((dd > 0 ? "▲" : dd < 0 ? "▼" : "=") + " " + Math.abs(dd) + " vs wk " + i);
  var when = "Week " + (i + 1) + (i === d.now ? " · now" : (i > d.now ? " · plan" : ""));
  var form = GGEG.signed(d.frm[i], 0);
  c.set("num", String(d.fit[i]));
  c.set("chip", chip);
  c.set("when", when);
  c.set("fat", String(d.fat[i]));
  c.set("form", form);
  c.set("load", d.load[i] === null ? "⚡ no prior week" : "⚡ ~" + d.load[i] + " that week");
  var pt = c.q("[data-eg-pt]");
  if (pt) { pt.style.left = ((i + 0.5) / 12 * 100) + "%"; pt.style.top = (100 - d.fit[i]) + "%"; }
  return "Week " + (i + 1) + ": " + d.fit[i] + " fitness, " + d.fat[i] + " fatigue, form " + form;
});

(function () {
  function dur(s) {
    function trim(v, dp) { return dp ? String(parseFloat(v.toFixed(dp))) : String(Math.round(v)); }
    if (s < 60) return Math.round(s) + " s";
    if (s < 3600) { var m = s / 60; return trim(m, m < 10 ? 1 : 0) + " min"; }
    return trim(s / 3600, 1) + " h";
  }
  function r(x) { return Math.floor(x + 0.5); }
  function nice(unit, kg, wmin, wmax) {
    var lo = wmin, hi = wmax;
    if (unit === "wkg") { lo = lo / kg; hi = hi / kg; }
    var steps = [0.5, 1, 2, 3, 4, 5, 10, 20, 25, 50, 100, 150, 200, 250, 300, 400, 500];
    for (var k = 0; k < steps.length; k++) {
      var st = steps[k], list = [];
      for (var v = Math.ceil(lo / st) * st; v < hi; v += st) list.push(v);
      if (list.length >= 2 && list.length <= 3) return list;
    }
    return [];
  }
  function num(u, w, kg, ftp) { return u === "w" ? String(r(w)) : GGEG.fmt(w / kg, 2); }
  GGEG.register("ch3-pd", function (i, c) {
    var d = c.data, st = c.state;
    var w = d.w[i], f = i / (c.n - 1), s = d.s0 * Math.pow(d.s1 / d.s0, f);
    var u = st.unit, label = dur(s);
    var delta = u === "w" ? GGEG.signed(r(w) - st.ftp, 0) : GGEG.signed(w / st.kg - st.ftp / st.kg, 2);
    c.set("num", num(u, w, st.kg));
    c.set("unit", u === "w" ? "W" : "W/kg");
    c.set("chip", r(w / st.ftp * 100) + "% of FTP");
    c.set("when", label);
    c.set("delta", delta === "" ? "0" : delta);
    var pt = c.q("[data-eg-pt]");
    if (pt) { pt.style.left = (f * 100) + "%"; pt.style.top = ((d.wmax - w) / (d.wmax - d.wmin) * 100) + "%"; }
    return label + ": " + num(u, w, st.kg) + (u === "w" ? " W" : " W/kg") + ", " + r(w / st.ftp * 100) + "% of FTP";
  }, function (c) {
    var d = c.data, card = c.card;
    var st = c.state;
    st.unit = "w"; st.kg = d.kg; st.ftp = d.ftp;
    function top(w) { return ((d.wmax - w) / (d.wmax - d.wmin) * 100) + "%"; }
    function render() {
      var u = st.unit, k, v;
      var tk = card.querySelector("[data-eg-ticks]");
      if (tk) {
        while (tk.firstChild) tk.removeChild(tk.firstChild);
        var list = nice(u, st.kg, d.wmin, d.wmax);
        for (k = 0; k < list.length; k++) {
          v = list[k];
          var row = document.createElement("div");
          row.className = "gg-ig-b-eg-tk";
          row.style.top = top(u === "w" ? v : v * st.kg);
          var sp = document.createElement("span");
          sp.textContent = String(parseFloat(v.toFixed(2)));
          row.appendChild(sp);
          tk.appendChild(row);
        }
      }
      for (k = 0; k < d.zones.length; k++) {
        var lo = r(d.zones[k][1] / 100 * st.ftp), hi = r(d.zones[k][2] / 100 * st.ftp);
        var band = card.querySelector('[data-eg-zb="' + k + '"]');
        if (band) { band.style.top = top(hi); band.style.height = ((hi - lo) / (d.wmax - d.wmin) * 100) + "%"; }
        var zr = card.querySelector('[data-eg-zr="' + k + '"]');
        if (zr) zr.textContent = u === "w" ? lo + "–" + hi + " W" : GGEG.fmt(lo / st.kg, 2) + "–" + GGEG.fmt(hi / st.kg, 2) + " W/kg";
      }
      for (k = 0; k < d.keys.length; k++) {
        var kc = card.querySelector('[data-eg-key="' + k + '"] .gg-eg-cap');
        if (kc) kc.textContent = u === "w" ? d.keys[k][1] + " W" : GGEG.fmt(d.keys[k][1] / st.kg, 2) + " W/kg";
      }
      var bs = card.querySelectorAll("[data-eg-unit]");
      for (k = 0; k < bs.length; k++) bs[k].setAttribute("aria-pressed", bs[k].getAttribute("data-eg-unit") === u ? "true" : "false");
    }
    var bs = card.querySelectorAll("[data-eg-unit]");
    for (var k = 0; k < bs.length; k++) {
      bs[k].addEventListener("click", function (e) {
        st.unit = e.currentTarget.getAttribute("data-eg-unit");
        render();
        c.refresh();
      });
    }
    function bind(name, key, lo, hi) {
      var inp = card.querySelector('[data-eg-in="' + name + '"]');
      if (!inp) return;
      inp.addEventListener("input", function () {
        var v = parseFloat(inp.value);
        if (!isFinite(v) || v < lo || v > hi) { inp.setAttribute("aria-invalid", "true"); return; }
        inp.removeAttribute("aria-invalid");
        st[key] = v;
        render();
        c.refresh();
      });
    }
    bind("kg", "kg", 30, 200);
    bind("ftp", "ftp", 100, 500);
    render();
  });
})();
"""


_CSS_RAW = """
.gg-ig-b-panel{--b-ink:var(--gg-color-dark-brown);--b-acc:var(--gg-color-light-gold);box-sizing:border-box;width:100%;max-width:100%;margin:0 0 28px;border:3px solid var(--gg-color-dark-brown);overflow:hidden;font-family:var(--gg-font-editorial);line-height:1.4}
.gg-ig-b-panel *{box-sizing:border-box;font-family:inherit}
.gg-ig-b-panel ul,.gg-ig-b-panel ol,.gg-ig-b-panel dl,.gg-ig-b-panel dd,.gg-ig-b-panel p{margin:0;padding:0;list-style:none}
.gg-ig-b-panel li{font-size:inherit;line-height:inherit;color:inherit;margin:0}
.gg-ig-b-panel p{color:inherit}
.gg-ig-b-panel--light{background:var(--gg-color-warm-paper);color:var(--gg-color-dark-brown)}
.gg-ig-b-panel--dark{background:var(--gg-color-dark-brown);color:var(--gg-color-warm-paper)}
.gg-ig-b-head{background:var(--gg-color-dark-brown);padding:22px 28px 20px;border-bottom:3px solid var(--gg-color-dark-brown)}
.gg-ig-b-panel--dark .gg-ig-b-head{border-bottom-color:var(--gg-color-light-gold)}
.gg-ig-b-eyebrow{font-family:var(--gg-font-data);font-size:14px;letter-spacing:2px;text-transform:uppercase;color:var(--gg-color-light-gold);margin:0 0 8px}
.gg-ig-b-title{font-family:var(--gg-font-editorial);font-size:30px;line-height:1.15;font-weight:700;color:var(--gg-color-white);margin:0;padding:0;text-transform:none;letter-spacing:0}
.gg-ig-b-hero{display:flex;align-items:center;gap:12px 32px;padding:26px 28px;flex-wrap:wrap}
.gg-ig-b-hero-num{font-family:var(--gg-font-data);font-weight:700;font-size:80px;line-height:1;letter-spacing:-2px;font-variant-numeric:tabular-nums;white-space:normal;overflow-wrap:anywhere}
.gg-ig-b-hero-text{flex:1 1 280px;font-size:19px;line-height:1.4;font-weight:600;min-width:0}
.gg-ig-b-panel--light .gg-ig-b-hero{background:var(--gg-color-light-gold);color:var(--gg-color-dark-brown);border-bottom:3px solid var(--gg-color-dark-brown)}
.gg-ig-b-panel--dark .gg-ig-b-hero-num{color:var(--gg-color-light-gold)}
.gg-ig-b-panel--dark .gg-ig-b-hero-text{color:var(--gg-color-sand)}
.gg-ig-b-body{padding:24px 28px 26px}
.gg-ig-b-cap{margin:0 28px 28px;padding:4px 0 4px 16px;border-left:6px solid var(--gg-color-light-gold);font-family:var(--gg-font-editorial);font-style:italic;font-size:16px;line-height:1.5}
.gg-ig-b-panel--dark .gg-ig-b-cap{color:var(--gg-color-sand)}
.gg-ig-b-mark{position:absolute;transform:translate(-50%,-50%);width:28px;height:28px;display:flex;align-items:center;justify-content:center;background:var(--gg-color-light-gold);color:var(--gg-color-near-black);border:3px solid var(--gg-color-near-black);font-family:var(--gg-font-data);font-weight:700;font-size:14px;line-height:1;z-index:2}
.gg-ig-b-mark--static{position:static;transform:none;flex:0 0 28px}
/* supercompensation */
.gg-ig-b-sc-plot{position:relative;height:340px;border-bottom:3px solid var(--gg-color-sand);margin:6px 14px 12px}
.gg-ig-b-sc-svg{position:absolute;inset:0;width:100%;height:100%;display:block;overflow:visible}
.gg-ig-b-sc-line{fill:none;stroke:var(--gg-color-light-gold);stroke-width:5;vector-effect:non-scaling-stroke;stroke-linejoin:round}
.gg-ig-b-sc-up{fill:var(--gg-color-light-gold);fill-opacity:.28}
.gg-ig-b-sc-dn{fill:var(--gg-color-warm-paper);fill-opacity:.14}
.gg-ig-b-sc-base{stroke:var(--gg-color-sand);stroke-width:2;stroke-dasharray:8 6;vector-effect:non-scaling-stroke}
.gg-ig-b-sc-key{display:flex;align-items:center;gap:10px;font-family:var(--gg-font-data);font-size:14px;color:var(--gg-color-sand);margin:0 14px 20px}
.gg-ig-b-sc-dash{width:34px;border-top:3px dashed var(--gg-color-sand);display:inline-block}
.gg-ig-b-sc-steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px 24px}
.gg-ig-b-sc-step{display:flex;gap:12px;align-items:flex-start}
.gg-ig-b-sc-name{display:block;font-size:17px;color:var(--gg-color-white);margin-bottom:2px}
.gg-ig-b-sc-tip{display:block;font-size:15px;line-height:1.4;color:var(--gg-color-sand)}
/* zones */
.gg-ig-b-zn-axis{display:flex;margin-bottom:6px}
.gg-ig-b-zn-axis-pad{flex:0 0 250px}
.gg-ig-b-zn-ticks{position:relative;flex:1;height:18px;font-family:var(--gg-font-data);font-size:12px;color:var(--gg-color-primary-brown)}
.gg-ig-b-zn-ticks span{position:absolute;top:0;transform:translateX(-50%)}
.gg-ig-b-zn-ticks span:first-child{transform:none}
.gg-ig-b-zn-list{display:block}
.gg-ig-b-zn-row{display:flex;gap:18px;padding:10px 0;border-top:3px solid var(--gg-color-sand)}
.gg-ig-b-zn-info{flex:0 0 232px;display:grid;grid-template-columns:auto 1fr;grid-template-areas:"c n" "c r";column-gap:12px;align-items:center}
.gg-ig-b-zn-code{grid-area:c;font-family:var(--gg-font-data);font-weight:700;font-size:26px}
.gg-ig-b-zn-name{grid-area:n;font-weight:700;font-size:17px;line-height:1.2}
.gg-ig-b-zn-range{grid-area:r;font-family:var(--gg-font-data);font-size:15px;font-variant-numeric:tabular-nums}
.gg-ig-b-zn-viz{flex:1;min-width:0}
.gg-ig-b-zn-track{position:relative;height:24px;background:var(--gg-color-sand)}
.gg-ig-b-zn-bar{position:absolute;top:0;bottom:0;background:var(--gg-color-primary-brown);min-width:8px}
.gg-ig-b-zn-row--hot .gg-ig-b-zn-bar{background:var(--gg-color-gold)}
.gg-ig-b-zn-desc{font-size:15px;line-height:1.35;margin-top:5px}
/* training phases */
.gg-ig-b-tp-heads{display:flex;gap:3px;margin-bottom:14px}
.gg-ig-b-tp-ph{min-width:0;padding:10px 12px;border:3px solid var(--gg-color-dark-brown);display:flex;flex-direction:column;gap:2px;font-family:var(--gg-font-data);line-height:1.15}
.gg-ig-b-tp-ph b{font-size:16px;overflow-wrap:anywhere}
.gg-ig-b-tp-ph span{font-size:14px}
.gg-ig-b-tp-ph--base{background:var(--gg-color-tan)}
.gg-ig-b-tp-ph--build{background:var(--gg-color-light-gold)}
.gg-ig-b-tp-ph--peak{background:var(--gg-color-dark-brown);color:var(--gg-color-white)}
.gg-ig-b-tp-label{font-family:var(--gg-font-data);font-weight:700;font-size:14px;letter-spacing:2px;margin:6px 0 4px}
.gg-ig-b-tp-row{display:flex;height:120px;border-bottom:3px solid var(--gg-color-dark-brown);margin-bottom:10px}
.gg-ig-b-tp-col{flex:1;min-width:0;position:relative;border-left:1px solid var(--gg-color-tan)}
.gg-ig-b-tp-col:first-child{border-left:0}
.gg-ig-b-tp-col--build{background:color-mix(in srgb,var(--gg-color-light-gold) 18%,transparent)}
.gg-ig-b-tp-col--peak{background:color-mix(in srgb,var(--gg-color-dark-brown) 10%,transparent)}
.gg-ig-b-tp-bar{position:absolute;left:12%;right:12%;bottom:0;height:calc(var(--h) * 1%)}
.gg-ig-b-tp-bar--vol{background:var(--gg-color-dark-brown)}
.gg-ig-b-tp-bar--int{background:var(--gg-color-gold)}
.gg-ig-b-tp-wk{display:flex;font-family:var(--gg-font-data);font-size:12px}
.gg-ig-b-tp-wk span{flex:1;text-align:center}
.gg-ig-b-tp-wkl{font-family:var(--gg-font-data);font-size:12px;letter-spacing:2px;text-align:center;margin-top:2px}
.gg-ig-b-tp-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-top:22px}
.gg-ig-b-tp-card{border:3px solid var(--gg-color-dark-brown);padding:12px 14px;display:flex;flex-direction:column;gap:4px;background:var(--gg-color-white)}
.gg-ig-b-tp-card b{font-family:var(--gg-font-data);font-size:15px;letter-spacing:1px}
.gg-ig-b-tp-card span{font-size:16px;line-height:1.4}
.gg-ig-b-tp-card--base{border-top:10px solid var(--gg-color-tan)}
.gg-ig-b-tp-card--build{border-top:10px solid var(--gg-color-light-gold)}
.gg-ig-b-tp-card--peak{border-top:10px solid var(--gg-color-dark-brown)}
/* power duration */
/* gantt */
.gg-ig-b-gt-months{display:flex;gap:18px;margin-bottom:6px}
.gg-ig-b-gt-pad{flex:0 0 270px}
.gg-ig-b-gt-mgrid{flex:1;display:grid;grid-template-columns:repeat(13,1fr);font-family:var(--gg-font-data);font-size:12px;text-align:center;min-width:0}
.gg-ig-b-gt-mgrid i{font-style:normal}
.gg-ig-b-gt-short{display:none}
.gg-ig-b-gt-row{display:flex;gap:18px;align-items:center;padding:10px 0;border-top:3px solid var(--gg-color-sand)}
.gg-ig-b-gt-info{flex:0 0 270px;display:grid;gap:1px}
.gg-ig-b-gt-name{font-size:20px;line-height:1.15}
.gg-ig-b-gt-dates{font-family:var(--gg-font-data);font-size:14px;font-weight:700}
.gg-ig-b-gt-desc{font-size:15px;line-height:1.35}
.gg-ig-b-gt-track{position:relative;flex:1;min-width:0;height:44px;background-image:linear-gradient(90deg,transparent calc(100% - 1px),var(--gg-color-tan) 0);background-size:calc(100% / 13) 100%}
.gg-ig-b-gt-bar{position:absolute;top:0;bottom:0;border:3px solid var(--gg-color-dark-brown)}
.gg-ig-b-gt-bar--off{background:var(--gg-color-tan)}
.gg-ig-b-gt-bar--base{background:var(--gg-color-secondary-brown)}
.gg-ig-b-gt-bar--build{background:var(--gg-color-light-gold)}
.gg-ig-b-gt-bar--race{background:var(--gg-color-dark-brown)}
.gg-ig-b-gt-bar--trans{background:var(--gg-color-sand)}
/* before / after */
.gg-ig-b-ba-cols,.gg-ig-b-ba-row{display:grid;grid-template-columns:1fr 1fr;gap:0 24px}
.gg-ig-b-ba-cols p{border-bottom:3px solid var(--gg-color-light-gold);padding-bottom:8px;margin-bottom:6px}
.gg-ig-b-ba-cols b{display:block;font-family:var(--gg-font-data);font-size:18px;letter-spacing:2px;color:var(--gg-color-white)}
.gg-ig-b-ba-cols span{font-size:15px;color:var(--gg-color-sand)}
.gg-ig-b-ba-row{padding:12px 0 14px;border-bottom:1px solid color-mix(in srgb,var(--gg-color-sand) 35%,transparent)}
.gg-ig-b-ba-metric{grid-column:1/-1;font-family:var(--gg-font-data);font-size:14px;letter-spacing:1px;text-transform:uppercase;color:var(--gg-color-sand);margin-bottom:4px}
.gg-ig-b-ba-before{font-family:var(--gg-font-data);font-size:30px;line-height:1.1;color:var(--gg-color-tan);font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.gg-ig-b-ba-after{font-family:var(--gg-font-data);font-size:44px;line-height:1;font-weight:700;color:var(--gg-color-light-gold);font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.gg-ig-b-ba-note{grid-column:1/-1;font-size:16px;color:var(--gg-color-warm-paper);margin-top:6px}
.gg-ig-b-ba-row{align-items:baseline}
@media (max-width:700px){
.gg-ig-b-head{padding:18px 16px 16px}
.gg-ig-b-title{font-size:24px}
.gg-ig-b-hero{padding:20px 16px;gap:10px}
.gg-ig-b-hero-num{font-size:52px;letter-spacing:-1px}
.gg-ig-b-hero-text{font-size:17px;flex-basis:100%}
.gg-ig-b-body{padding:18px 16px 20px}
.gg-ig-b-cap{margin:0 16px 22px}
.gg-ig-b-sc-plot{height:260px;margin:6px 14px 12px}
.gg-ig-b-sc-key{margin:0 0 18px}
.gg-ig-b-zn-axis-pad{display:none}
.gg-ig-b-zn-row{flex-direction:column;gap:8px}
.gg-ig-b-zn-info{flex:none}
.gg-ig-b-tp-ph{padding:8px 8px}
.gg-ig-b-tp-ph b{font-size:14px}
.gg-ig-b-tp-row{height:96px}
.gg-ig-b-gt-months{display:block}
.gg-ig-b-gt-pad{display:none}
.gg-ig-b-gt-full{display:none}
.gg-ig-b-gt-short{display:inline}
.gg-ig-b-gt-row{flex-direction:column;align-items:stretch;gap:8px}
.gg-ig-b-gt-info{flex:none}
.gg-ig-b-gt-track{flex:none;height:36px}
.gg-ig-b-ba-before{font-size:22px}
.gg-ig-b-ba-after{font-size:30px}
.gg-ig-b-ba-cols{gap:0 14px}
.gg-ig-b-ba-row{gap:0 14px}
}
@media (min-width:701px){
}
"""


def _scope(css: str) -> str:
    """Raise specificity so the guide's generic `.gg-guide-chapter-body p` rules cannot win."""
    import re

    def fix(m):
        sels, body = m.group(1), m.group(2)
        out = []
        for sel in sels.split(","):
            sel = sel.strip()
            out.append(sel if sel.startswith(".gg-ig-b-panel") else ".gg-ig-b-panel " + sel)
        return ",".join(out) + "{" + body + "}"

    return re.sub(r"(?m)^([^@{}\n]+)\{([^}]*)\}", fix, css)


_EG_CSS = """
.gg-ig-b-eg-body{padding:20px 20px 20px}
.gg-ig-b-eg-wrap{position:relative;padding-right:100px}
.gg-ig-b-eg-past{position:absolute;left:0;top:0;bottom:0;background:var(--eg-past)}
.gg-ig-b-eg-lines{position:relative;height:220px}
.gg-ig-b-eg-bars{position:relative;height:56px;margin-top:6px}
.gg-ig-b-eg-ref{stroke:var(--eg-none);stroke-width:1;vector-effect:non-scaling-stroke}
.gg-ig-b-eg-yl{position:absolute;left:2px;transform:translateY(-100%);font-family:var(--eg-mono);font-size:11px;color:var(--eg-ink3);text-shadow:0 0 3px var(--eg-card),0 0 3px var(--eg-card)}
.gg-ig-b-eg-yl--top{transform:translateY(3px)}
.gg-ig-b-eg-band{stroke:none}
.gg-ig-b-eg-band--teal{fill:color-mix(in srgb,var(--eg-form) 16%,var(--eg-card))}
.gg-ig-b-eg-band--pink{fill:color-mix(in srgb,var(--eg-fat) 16%,var(--eg-card))}
.gg-ig-b-eg-case{fill:none;stroke:var(--eg-card);stroke-width:6.25;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}
.gg-ig-b-eg-hero{fill:none;stroke:var(--eg-ink);stroke-width:2.75;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}
.gg-ig-b-eg-hero--ride{stroke:var(--eg-ride)}
.gg-ig-b-eg-fat{fill:none;stroke:var(--eg-fat);stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}
.gg-ig-b-eg-plan{stroke-width:2;stroke-dasharray:0 5}
.gg-ig-b-eg-bar{fill:var(--eg-ink2)}
.gg-ig-b-eg-bar--plan{fill:none;stroke:var(--eg-ink);stroke-width:2;stroke-dasharray:0 5;stroke-linecap:round;vector-effect:non-scaling-stroke}
.gg-ig-b-eg-plan-l{position:absolute;top:2px;margin-left:8px;font-family:var(--eg-mono);font-size:11px;color:var(--eg-ink3)}
.gg-ig-b-eg-note{position:absolute;transform:translate(-50%,-190%);font-family:var(--eg-mono);font-size:11px;font-weight:700;color:var(--eg-ink2);white-space:nowrap;text-shadow:0 0 3px var(--eg-card),0 0 3px var(--eg-card)}
.gg-ig-b-eg-ends{position:absolute;right:0;top:0;width:96px;height:220px}
.gg-ig-b-eg-ends>div{position:absolute;left:8px;transform:translateY(-50%)}
.gg-ig-b-eg-loadl{position:absolute;right:0;bottom:2px;width:96px;padding-left:8px;font-family:var(--eg-mono);font-size:11px;color:var(--eg-ink3)}
.gg-ig-b-eg-area{fill:color-mix(in srgb,var(--eg-ride) 16%,var(--eg-card));stroke:none}
.gg-ig-b-eg-zb{position:absolute;left:0;right:0}
.gg-ig-b-eg-zb--1{background:color-mix(in srgb,var(--eg-ink) 8%,transparent)}
.gg-ig-b-eg-zb--2{background:color-mix(in srgb,var(--eg-ink) 14%,transparent)}
.gg-ig-b-eg-zb--3{background:color-mix(in srgb,var(--eg-ink) 20%,transparent)}
.gg-ig-b-eg-zb span{position:absolute;left:4px;top:50%;transform:translateY(-50%);font-family:var(--eg-mono);font-size:11px;font-weight:700;color:var(--eg-ink2);line-height:1}
.gg-ig-b-eg-tk{position:absolute;left:0;right:0;border-top:1px solid var(--eg-none)}
.gg-ig-b-eg-tk span{position:absolute;right:2px;bottom:1px;font-family:var(--eg-mono);font-size:11px;color:var(--eg-ink3);text-shadow:0 0 3px var(--eg-card),0 0 3px var(--eg-card)}
.gg-ig-b-eg-key{position:absolute;transform:translate(-50%,-165%);z-index:2;pointer-events:none}
.gg-ig-b-eg-key--end{transform:translate(-92%,-165%)}
.gg-ig-b-eg-ticks{position:absolute;inset:0;pointer-events:none}
.gg-ig-b-eg-ruler{position:relative;height:24px;border-top:1px solid var(--eg-ink3);margin-top:0}
.gg-ig-b-eg-xt{position:absolute;top:5px;transform:translateX(-50%);font-family:var(--eg-mono);font-size:11px;color:var(--eg-ink3);white-space:nowrap}
.gg-ig-b-eg-xt::before{content:"";position:absolute;left:50%;top:-6px;height:5px;border-left:1px solid var(--eg-ink3)}
.gg-ig-b-eg-xt:first-child{transform:none}
.gg-ig-b-eg-xt--opt:last-child{transform:translateX(-100%)}
.gg-ig-b-eg-zl{display:flex;flex-wrap:wrap;gap:6px 18px;list-style:none;margin:8px 0 0;padding:0;font-family:var(--eg-mono);font-size:12px;color:var(--eg-ink2)}
.gg-ig-b-eg-zl li{display:flex;align-items:center;gap:6px;margin:0;padding:0}
.gg-ig-b-eg-zs{display:inline-block;width:12px;height:12px;border-radius:2px!important;box-shadow:inset 0 0 0 1px var(--eg-none)!important}
.gg-ig-b-eg-zr{font-weight:700;color:var(--eg-ink);font-variant-numeric:tabular-nums}
.gg-eg-pw[data-eg-scrub="ch3-pd"]{height:270px}
@media (max-width:700px){
.gg-ig-b-eg-body{padding:14px 12px 14px}
.gg-ig-b-eg-wrap{padding-right:50px}
.gg-ig-b-eg-lines{height:190px}
.gg-ig-b-eg-ends{width:46px;height:190px}
.gg-ig-b-eg-ends>div{left:4px}
.gg-ig-b-eg-ends .gg-eg-capl{display:none}
.gg-ig-b-eg-loadl{width:46px;padding-left:4px}
.gg-ig-b-eg-xt--opt{display:none}
.gg-eg-pw[data-eg-scrub="ch3-pd"]{height:230px}
.gg-ig-b-eg-key[data-eg-key="1"],.gg-ig-b-eg-zb span{display:none}
}
"""

CSS = _scope(_CSS_RAW + _EG_CSS)
