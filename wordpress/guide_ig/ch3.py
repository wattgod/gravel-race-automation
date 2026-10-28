"""Chapter 3 (Training) charts, rebuilt as poster panels.

Static markup: SVG draws only the lines and fills (stretched, non-scaling
strokes); every label, tick and marker is HTML so text stays a real 14px+ at
any width. No script needed.
"""
import html as _html
import math

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
_TSB = [-5, -15, -19, -7, -15, -13, 3, -10, 0, 28, 37, 40]


def render_pmc_chart(block: dict) -> str:
    W, H = 1200, 300

    def line(vals):
        return _smooth([((i + 0.5) / 12 * W, H - v / 100 * H) for i, v in enumerate(vals)])

    grid = "".join(
        f'<line class="{P}-pmc-grid" x1="0" y1="{H - v / 100 * H:.1f}" x2="{W}" y2="{H - v / 100 * H:.1f}"/>'
        for v in (0, 50, 100)
    )
    svg = (
        f'<svg class="{P}-pmc-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">'
        f'{grid}<path class="{P}-pmc-atl" d="{line(_ATL)}"/><path class="{P}-pmc-ctl" d="{line(_CTL)}"/></svg>'
    )
    yt = "".join(
        f'<span style="top:{100 - v}%">{v}</span>' for v in (0, 50, 100)
    )
    bars = []
    for i, v in enumerate(_TSB):
        sign = "pos" if v >= 0 else "neg"
        key = " " + P + "-pmc-bar--key" if i in (9, 11) else ""
        txt = f"+{v}" if v > 0 else str(v)
        bars.append(
            f'<div class="{P}-pmc-col"><span class="{P}-pmc-bar {P}-pmc-bar--{sign}{key}" '
            f'style="--h:{abs(v) / 75 * 100:.1f}"><b>{_e(txt)}</b></span></div>'
        )
    wk = "".join(f'<span>{i}</span>' for i in range(1, 13))
    legend = (
        f'<ul class="{P}-pmc-legend">'
        f'<li><span class="{P}-pmc-sw {P}-pmc-sw--ctl"></span><strong>CTL</strong> Fitness</li>'
        f'<li><span class="{P}-pmc-sw {P}-pmc-sw--atl"></span><strong>ATL</strong> Fatigue</li>'
        f'<li><span class="{P}-pmc-sw {P}-pmc-sw--tsb"></span><strong>TSB</strong> Form</li></ul>'
    )
    defs = (
        f'<dl class="{P}-pmc-defs">'
        f'<div><dt>CTL · Fitness</dt><dd>Chronic Training Load — your long-term fitness trend</dd></div>'
        f'<div><dt>ATL · Fatigue</dt><dd>Acute Training Load — recent fatigue from hard training</dd></div>'
        f'<div><dt>TSB · Form</dt><dd>Training Stress Balance — positive = fresh, negative = fatigued</dd></div></dl>'
    )
    body = (
        f'{legend}'
        f'<div class="{P}-pmc" role="img" aria-label="{_alt(block, "12-week performance management chart: fitness (CTL) climbs from 25 to 78, fatigue (ATL) swings, form (TSB) turns positive at week 10 for race week")}">'
        f'<div class="{P}-pmc-hl" aria-hidden="true"><span>RACE READY</span></div>'
        f'<p class="{P}-pmc-cap">Fitness and fatigue</p>'
        f'<div class="{P}-pmc-top"><div class="{P}-pmc-yt" aria-hidden="true">{yt}</div>'
        f'<div class="{P}-pmc-plot">{svg}</div></div>'
        f'<p class="{P}-pmc-cap">Form (CTL minus ATL)</p>'
        f'<div class="{P}-pmc-bot"><div class="{P}-pmc-zero" aria-hidden="true"><span>0</span></div>'
        f'<div class="{P}-pmc-bars">{"".join(bars)}</div></div>'
        f'<div class="{P}-pmc-wk"><span class="{P}-pmc-wkl">WK</span><div class="{P}-pmc-wks">{wk}</div></div></div>'
        f'{defs}'
    )
    return _panel(
        block, "dark", "CH 3 · LOAD", "The Performance Management Chart: Fitness, Fatigue, Form",
        "+28",
        "Form at week 10: fitness 78 over fatigue 50. Go positive before race day.",
        body, "CTL builds slowly. ATL spikes fast. TSB tells you when to race.",
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
_PD_ZONES = [
    ("Z2", "Endurance", 138, 188, 1),
    ("Z3", "Tempo", 188, 225, 2),
    ("Z4", "Threshold", 225, 263, 3),
]


def render_power_duration(block: dict) -> str:
    W, H = 1000, 400
    t0, t1 = math.log10(5), math.log10(28800)
    wmin, wmax = 100, 1000

    def ux(s):
        return (math.log10(s) - t0) / (t1 - t0)

    def uy(w):
        return (wmax - w) / (wmax - wmin)

    path = _smooth([(ux(s) * W, uy(w) * H) for s, w in _PD])
    grid = "".join(
        f'<line class="{P}-pd-grid" x1="0" y1="{uy(w) * H:.1f}" x2="{W}" y2="{uy(w) * H:.1f}"/>'
        for w in (200, 400, 600, 800, 1000)
    )
    svg = (
        f'<svg class="{P}-pd-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">'
        f'{grid}<path class="{P}-pd-line" d="{path}"/></svg>'
    )
    bands = "".join(
        f'<div class="{P}-pd-band {P}-pd-band--{n}" style="top:{uy(hi) * 100:.2f}%;height:{(hi - lo) / (wmax - wmin) * 100:.2f}%">'
        f'<span>{code}</span></div>'
        for code, _, lo, hi, n in _PD_ZONES
    )
    marks = "".join(
        f'<span class="{P}-mark" style="left:{ux(s) * 100:.2f}%;top:{uy(w) * 100:.2f}%" aria-hidden="true">{i}</span>'
        for i, (s, w, _, _) in enumerate(_PD_KEYS, 1)
    )
    yt = "".join(f'<span style="top:{uy(w) * 100:.2f}%">{w}W</span>' for w in (200, 400, 600, 800, 1000))
    xt = "".join(
        f'<span style="left:{ux(s) * 100:.2f}%">{lbl}</span>'
        for s, lbl in ((5, "5s"), (60, "1m"), (300, "5m"), (1200, "20m"), (3600, "1h"), (14400, "4h"), (28800, "8h"))
    )
    chips = "".join(
        f'<li class="{P}-pd-chip {P}-pd-chip--{n}"><b>{code}</b> {_e(name)} <span>{lo}–{hi} W</span></li>'
        for code, name, lo, hi, n in _PD_ZONES
    )
    tiles = "".join(
        f'<li class="{P}-pd-tile"><span class="{P}-mark {P}-mark--static" aria-hidden="true">{i}</span>'
        f'<div><span class="{P}-pd-tl">{_e(lbl)}</span><b class="{P}-pd-tw">{w} W</b>'
        f'<span class="{P}-pd-tt">{_e(tip)}</span></div></li>'
        for i, (s, w, lbl, tip) in enumerate(_PD_KEYS, 1)
    )
    body = (
        f'<div class="{P}-pd" role="img" aria-label="{_alt(block, "Power-duration curve for a 250 W FTP rider: 900 W at 5 seconds falling to 170 W at 8 hours, with Z2 to Z4 bands between 138 and 263 W")}">'
        f'<div class="{P}-pd-yt" aria-hidden="true">{yt}</div>'
        f'<div class="{P}-pd-plot">{bands}{svg}{marks}</div>'
        f'<div class="{P}-pd-xt" aria-hidden="true">{xt}</div></div>'
        f'<ul class="{P}-pd-chips">{chips}</ul>'
        f'<ul class="{P}-pd-tiles">{tiles}</ul>'
    )
    return _panel(
        block, "dark", "CH 3 · POWER", "Your Power-Duration Curve: What You Can Sustain",
        "195 W",
        "Gravel racing is a 4-8 hour effort. Your 20-minute power matters less than your 4-hour power.",
        body, "The power-duration curve — your physiological fingerprint as a rider.",
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

JS = ""

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
/* pmc */
.gg-ig-b-pmc-legend{display:flex;flex-wrap:wrap;gap:8px 26px;margin-bottom:18px;font-family:var(--gg-font-data);font-size:15px}
.gg-ig-b-pmc-legend li{display:flex;align-items:center;gap:10px}
.gg-ig-b-pmc-legend strong{color:var(--gg-color-white)}
.gg-ig-b-pmc-sw{display:inline-block;width:34px;height:0;border-top:5px solid var(--gg-color-light-gold)}
.gg-ig-b-pmc-sw--atl{border-top:5px dashed var(--gg-color-warm-paper)}
.gg-ig-b-pmc-sw--tsb{height:14px;border-top:0;width:20px;background:var(--gg-color-light-gold)}
.gg-ig-b-pmc{position:relative;--gut:40px;padding-top:30px}
.gg-ig-b-pmc-hl{position:absolute;top:0;bottom:30px;left:calc(var(--gut) + (100% - var(--gut)) * 9 / 12);width:calc((100% - var(--gut)) / 12);background:var(--gg-color-light-gold);opacity:1;background:color-mix(in srgb,var(--gg-color-light-gold) 22%,transparent);border-left:3px solid var(--gg-color-light-gold);border-right:3px solid var(--gg-color-light-gold);z-index:0}
.gg-ig-b-pmc-hl span{position:absolute;bottom:100%;left:50%;transform:translateX(-50%);margin-bottom:4px;white-space:nowrap;font-family:var(--gg-font-data);font-weight:700;font-size:14px;color:var(--gg-color-light-gold)}
.gg-ig-b-pmc-cap{position:relative;z-index:1;font-family:var(--gg-font-data);font-size:14px;letter-spacing:1px;text-transform:uppercase;color:var(--gg-color-sand);margin:0 0 6px var(--gut)}
.gg-ig-b-pmc-top{position:relative;z-index:1;display:flex;height:240px;margin-bottom:18px}
.gg-ig-b-pmc-yt{position:relative;flex:0 0 var(--gut);font-family:var(--gg-font-data);font-size:12px;color:var(--gg-color-sand)}
.gg-ig-b-pmc-yt span{position:absolute;right:8px;transform:translateY(-50%)}
.gg-ig-b-pmc-plot{position:relative;flex:1;min-width:0}
.gg-ig-b-pmc-svg{position:absolute;inset:0;width:100%;height:100%;display:block;overflow:visible}
.gg-ig-b-pmc-grid{stroke:var(--gg-color-sand);stroke-opacity:.35;stroke-width:1;vector-effect:non-scaling-stroke}
.gg-ig-b-pmc-ctl{fill:none;stroke:var(--gg-color-light-gold);stroke-width:6;vector-effect:non-scaling-stroke;stroke-linecap:round}
.gg-ig-b-pmc-atl{fill:none;stroke:var(--gg-color-warm-paper);stroke-width:4;stroke-dasharray:10 7;vector-effect:non-scaling-stroke}
.gg-ig-b-pmc-bot{position:relative;z-index:1;display:flex;height:200px}
.gg-ig-b-pmc-zero{flex:0 0 var(--gut);position:relative;font-family:var(--gg-font-data);font-size:12px;color:var(--gg-color-sand)}
.gg-ig-b-pmc-zero span{position:absolute;right:8px;top:60%;transform:translateY(-50%)}
.gg-ig-b-pmc-bars{position:relative;flex:1;display:flex;min-width:0;border-top:0}
.gg-ig-b-pmc-bars::after{content:"";position:absolute;left:0;right:0;top:60%;border-top:2px solid var(--gg-color-sand)}
.gg-ig-b-pmc-col{position:relative;flex:1;min-width:0}
.gg-ig-b-pmc-bar{position:absolute;left:14%;right:14%}
.gg-ig-b-pmc-bar--pos{bottom:40%;height:calc(var(--h) * 1%);background:var(--gg-color-light-gold)}
.gg-ig-b-pmc-bar--neg{top:60%;height:calc(var(--h) * 1%);background:color-mix(in srgb,var(--gg-color-sand) 55%,transparent)}
.gg-ig-b-pmc-bar b{position:absolute;left:50%;transform:translateX(-50%);font-family:var(--gg-font-data);font-size:14px;line-height:1;font-weight:700;color:var(--gg-color-warm-paper);display:none}
.gg-ig-b-pmc-bar--pos b{bottom:100%;margin-bottom:4px}
.gg-ig-b-pmc-bar--neg b{top:100%;margin-top:4px}
.gg-ig-b-pmc-bar--key b{display:block;color:var(--gg-color-light-gold);font-size:16px}
.gg-ig-b-pmc-wk{position:relative;z-index:1;display:flex;margin-top:8px;font-family:var(--gg-font-data);font-size:12px;color:var(--gg-color-sand)}
.gg-ig-b-pmc-wkl{flex:0 0 var(--gut);text-align:right;padding-right:8px}
.gg-ig-b-pmc-wks{flex:1;display:flex;min-width:0}
.gg-ig-b-pmc-wks span{flex:1;text-align:center}
.gg-ig-b-pmc-defs{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px 24px;margin-top:24px}
.gg-ig-b-pmc-defs dt{font-family:var(--gg-font-data);font-weight:700;font-size:15px;color:var(--gg-color-light-gold);margin-bottom:3px}
.gg-ig-b-pmc-defs dd{font-size:15px;line-height:1.4;color:var(--gg-color-sand)}
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
.gg-ig-b-pd{position:relative;display:grid;grid-template-columns:52px 1fr;grid-template-rows:auto 28px;padding-right:14px}
.gg-ig-b-pd-yt{position:relative;height:440px;font-family:var(--gg-font-data);font-size:12px;color:var(--gg-color-sand)}
.gg-ig-b-pd-yt span{position:absolute;right:8px;transform:translateY(-50%)}
.gg-ig-b-pd-yt em{position:absolute;left:0;bottom:-26px;font-style:normal;font-size:12px;letter-spacing:1px}
.gg-ig-b-pd-plot{position:relative;height:440px;border-left:3px solid var(--gg-color-sand);border-bottom:3px solid var(--gg-color-sand)}
.gg-ig-b-pd-svg{position:absolute;inset:0;width:100%;height:100%;display:block;overflow:visible}
.gg-ig-b-pd-grid{stroke:var(--gg-color-sand);stroke-opacity:.28;stroke-width:1;vector-effect:non-scaling-stroke}
.gg-ig-b-pd-line{fill:none;stroke:var(--gg-color-light-gold);stroke-width:6;vector-effect:non-scaling-stroke;stroke-linecap:round;stroke-linejoin:round}
.gg-ig-b-pd-band{position:absolute;left:0;right:0;background:color-mix(in srgb,var(--gg-color-warm-paper) 16%,transparent);border-top:1px solid var(--gg-color-sand)}
.gg-ig-b-pd-band--2{background:color-mix(in srgb,var(--gg-color-warm-paper) 10%,transparent)}
.gg-ig-b-pd-band--3{background:color-mix(in srgb,var(--gg-color-warm-paper) 18%,transparent)}
.gg-ig-b-pd-band--1{background:color-mix(in srgb,var(--gg-color-warm-paper) 10%,transparent)}
.gg-ig-b-pd-band span{position:absolute;left:8px;top:50%;transform:translateY(-50%);font-family:var(--gg-font-data);font-weight:700;font-size:12px;line-height:1;color:var(--gg-color-white)}
.gg-ig-b-pd-xt{grid-column:2;position:relative;height:28px;font-family:var(--gg-font-data);font-size:12px;color:var(--gg-color-sand)}
.gg-ig-b-pd-xt span{position:absolute;top:8px;transform:translateX(-50%)}
.gg-ig-b-pd-xt span:last-child{transform:translateX(-80%)}
.gg-ig-b-pd-chips{display:flex;flex-wrap:wrap;gap:8px 12px;margin:22px 0 18px;font-size:15px}
.gg-ig-b-pd-chip{border:2px solid var(--gg-color-sand);padding:6px 12px;font-family:var(--gg-font-data);color:var(--gg-color-warm-paper)}
.gg-ig-b-pd-chip b{color:var(--gg-color-white)}
.gg-ig-b-pd-chip span{color:var(--gg-color-light-gold);font-variant-numeric:tabular-nums;margin-left:4px}
.gg-ig-b-pd-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}
.gg-ig-b-pd-tile{display:flex;gap:12px;align-items:flex-start;border-top:3px solid var(--gg-color-light-gold);padding-top:12px}
.gg-ig-b-pd-tl{display:block;font-family:var(--gg-font-data);font-size:14px;letter-spacing:1px;text-transform:uppercase;color:var(--gg-color-sand)}
.gg-ig-b-pd-tw{display:block;font-family:var(--gg-font-data);font-size:34px;line-height:1.1;color:var(--gg-color-light-gold)}
.gg-ig-b-pd-tt{display:block;font-size:15px;line-height:1.4;color:var(--gg-color-warm-paper);margin-top:2px}
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
.gg-ig-b-pmc{--gut:30px}
.gg-ig-b-pmc-top{height:190px}
.gg-ig-b-pmc-bot{height:150px}
.gg-ig-b-pmc-bar{left:8%;right:8%}
.gg-ig-b-pmc-hl span{left:auto;right:-6px;transform:none}
.gg-ig-b-tp-ph{padding:8px 8px}
.gg-ig-b-tp-ph b{font-size:14px}
.gg-ig-b-tp-row{height:96px}
.gg-ig-b-pd{grid-template-columns:40px 1fr;padding-right:12px}
.gg-ig-b-pd-yt,.gg-ig-b-pd-plot{height:330px}
.gg-ig-b-pd-xt span:last-child{display:none}
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
.gg-ig-b-pmc-bar b{display:block}
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


CSS = _scope(_CSS_RAW)
