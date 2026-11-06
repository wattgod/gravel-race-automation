"""Chapter 3 (Training) charts as Endure Glyph cards inside Gravel God panels.

SVG draws only lines and fills (stretched, non-scaling strokes); every label, tick and
marker is HTML so text stays a real 11px+ at any width. Scripts (JS below) add the scrub
and the controls; with no script each chart shows its default state in full.
"""
import html as _html
import math

from guide_ig import glyph

P = "gg-ig-b"


def _e(v) -> str:
    """Escape any value for HTML. 0 prints as 0."""
    return _html.escape("" if v is None else str(v), quote=True)


# ── 1. Supercompensation ────────────────────────────────────

# Model points: (fraction of the 20-day cycle, level vs baseline). One point per day.
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
_SC_DAYS = 20
_SC_DEF = 11  # the overshoot peak: "train again here"
_SC_LVL = [o for _, o in _SC_PTS]
_SC_ANCH = [(round(f * _SC_DAYS), n) for f, _, n, _ in _SC_STAGES]
_SC_LO, _SC_HI = -170, 100


def _signed(v):
    return "0" if v == 0 else f"{v:+d}"


def _sc_stage(day):
    best, bd = 0, 10 ** 9
    for k, (d, _) in enumerate(_SC_ANCH):
        if abs(d - day) < bd:
            best, bd = k, abs(d - day)
    return _SC_ANCH[best][1]


def _sc_verdict(day):
    """Where a hard session on `day` lands, read straight from the curve (mirrored in JS)."""
    lv = _SC_LVL[day]
    mi = min(range(len(_SC_LVL)), key=lambda k: (_SC_LVL[k], k))
    rec = next((k for k in range(mi + 1, len(_SC_LVL)) if _SC_LVL[k] >= 0), len(_SC_LVL))
    if lv == 0:
        return "Lands at baseline: no boost yet"
    if lv > 0 and day < rec:
        return f"Lands before the dip: {_signed(lv)} vs baseline"
    if lv > 0:
        return f"Lands on the overshoot: {_signed(lv)} above baseline"
    if day < rec:
        return f"Lands in the fatigue hole: {-lv} below baseline"
    return f"Lands after the overshoot faded: {-lv} below baseline"


def render_supercompensation(block: dict) -> str:
    W, H = 1000, 220
    n = _SC_DAYS + 1
    yp = lambda v: (_SC_HI - v) / (_SC_HI - _SC_LO)  # noqa: E731  (0 top .. 1 bottom)
    pts = [(f * W, yp(o) * H) for f, o in _SC_PTS]
    cs = glyph.mono_sample(pts, 12)
    base = yp(0) * H
    path = glyph.line_path(cs)
    area = glyph.line_path(cs + [(W, base), (0, base)], close=True)
    svg = (
        f'<svg class="gg-eg-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">'
        f'<defs><clipPath id="{P}-sc-up"><rect x="0" y="0" width="{W}" height="{base:.1f}"/></clipPath>'
        f'<clipPath id="{P}-sc-dn"><rect x="0" y="{base:.1f}" width="{W}" height="{H - base:.1f}"/></clipPath></defs>'
        f'<path class="{P}-eg-band {P}-eg-band--teal" d="{area}" clip-path="url(#{P}-sc-up)"/>'
        f'<path class="{P}-eg-band {P}-eg-band--pink" d="{area}" clip-path="url(#{P}-sc-dn)"/>'
        f'<line class="{P}-eg-ref" x1="0" x2="{W}" y1="{base:.1f}" y2="{base:.1f}"/>'
        f'<path class="{P}-eg-case" d="{path}"/><path class="{P}-eg-hero" d="{path}"/></svg>'
    )
    notes = (
        f'<span class="{P}-eg-note2" style="left:{4 / _SC_DAYS * 100:.1f}%;top:{yp(-120) * 100:.1f}%">Dip</span>'
        f'<span class="{P}-eg-note2 {P}-eg-note2--up" style="left:{15 / _SC_DAYS * 100:.1f}%;top:{yp(22) * 100:.1f}%">Overshoot</span>'
        f'<span class="{P}-eg-note2 {P}-eg-note2--l" style="left:0;top:{yp(0) * 100:.1f}%">Baseline</span>'
    )
    nh = (
        f'<div class="{P}-eg-nh" data-eg-nh style="left:{_SC_DEF / _SC_DAYS * 100:.2f}%">'
        f'<span>Hard session</span></div>'
    )
    pt = (
        f'<i class="gg-eg-pt" data-eg-pt style="left:{_SC_DEF / _SC_DAYS * 100:.2f}%;'
        f'top:{yp(_SC_LVL[_SC_DEF]) * 100:.2f}%"></i>'
    )
    plot = f"{svg}{notes}{nh}{pt}"
    vt = f"Day {_SC_DEF}: {_signed(_SC_LVL[_SC_DEF])} vs baseline, {_sc_stage(_SC_DEF)}"
    pw = glyph.scrub_wrap("ch3-sc", plot, n, _SC_DEF, "Scrub the 20 days", vt, mode="point")
    xt = "".join(
        f'<span class="{P}-eg-xt{" " + P + "-eg-xt--end" if d == _SC_DAYS else ""}" '
        f'style="left:{d / _SC_DAYS * 100:.1f}%">{"day " if d == _SC_DAYS else ""}{d}</span>'
        for d in (0, 5, 10, 15, 20)
    )
    ends = (
        f'<div class="{P}-eg-ends"><div style="top:{yp(_SC_LVL[-1]) * 100:.1f}%">'
        f'{glyph.capsule(_signed(_SC_LVL[-1]), "Fitness", "ink", "filled")}</div></div>'
    )
    wrap = f'<div class="{P}-eg-wrap">{pw}<div class="{P}-eg-ruler" aria-hidden="true">{xt}</div>{ends}</div>'
    controls = (
        f'<label class="gg-eg-field">Next hard session'
        f'<input class="{P}-eg-rng" type="range" min="0" max="{_SC_DAYS}" step="1" value="{_SC_DEF}" '
        f'data-eg-in="nh" aria-label="Day of your next hard session">'
        f'<span data-eg-f="nhday">Day {_SC_DEF}</span></label>'
    )
    extra = f'<span data-eg-f="verdict">{_e(_sc_verdict(_SC_DEF))}</span>'
    head = glyph.readout(
        _signed(_SC_LVL[_SC_DEF]), "vs baseline", _sc_stage(_SC_DEF), f"Day {_SC_DEF}", extra,
    )
    alt = block.get("alt") or "Supercompensation curve: stress drops fitness below baseline, recovery brings it back, then it overshoots before fading"
    desc = (
        f"{alt}. REST = FASTER: you get faster during recovery, not during the workout. "
        + " ".join(f"{n_}: {t}." for _, _, n_, t in _SC_STAGES)
        + " Level against baseline by day, 0 to 20: " + ", ".join(_signed(v) for v in _SC_LVL) + "."
    )
    data = {
        "lvl": _SC_LVL, "days": _SC_DAYS, "lo": _SC_LO, "hi": _SC_HI, "def": _SC_DEF,
        "stages": [[d, n_] for d, n_ in _SC_ANCH],
    }
    card = glyph.glyph_card(
        "Fitness after a hard session", head, wrap, controls_html=controls,
        data=data, describedby="gg-eg-sc-d", description=desc,
    )
    return _glyph_panel(
        block, "CH 3 · RECOVERY", "Supercompensation: Why Rest Makes You Faster", card,
        "The foundational model — train, recover, adapt, repeat.",
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
_ZN_FTP = 250
_ZN_SPAN = 170.0
_ZN_HOME = "Gravel racing lives in Zones 2–4."


def _zn_w(i, ftp):
    """Watts text for zone i at this FTP (mirrored in JS). Z1 has only a ceiling, Z7 none."""
    _, _, _, a, b, _ = _ZONES[i]
    r = lambda p: int(math.floor(p / 100 * ftp + 0.5))  # noqa: E731
    if i == 0:
        return f"≤ {r(b)} W"
    if i == len(_ZONES) - 1:
        return "Max"
    return f"{r(a)}–{r(b)} W"


def _zn_home_w(ftp):
    r = lambda p: int(math.floor(p / 100 * ftp + 0.5))  # noqa: E731
    return f"{r(55)}–{r(105)} W"


def render_zone_spectrum(block: dict) -> str:
    rows = []
    for i, (code, name, rng, a, b, _) in enumerate(_ZONES):
        hot = code in ("Z2", "Z3", "Z4")
        m = (
            f'<span class="gg-eg-meter {P}-eg-zm{"" if hot else " " + P + "-eg-zm--cool"}">'
            f'<b style="left:{a / _ZN_SPAN * 100:.2f}%;width:{(b - a) / _ZN_SPAN * 100:.2f}%"></b>'
            f'<i class="gg-eg-tick" style="left:{100 / _ZN_SPAN * 100:.2f}%"></i></span>'
        )
        rows.append(
            f'<li><button type="button" class="{P}-eg-row {P}-eg-zrow" data-eg-row="{i}" aria-pressed="false">'
            f'<span class="{P}-eg-rc">{_e(code)}</span><span class="{P}-eg-rn">{_e(name)}</span>'
            f'<span class="{P}-eg-rm">{m}</span>'
            f'<span class="{P}-eg-rp">{_e(rng)}</span>'
            f'<span class="{P}-eg-rw" data-eg-w="{i}">{_e(_zn_w(i, _ZN_FTP))}</span></button></li>'
        )
    axis = "".join(
        f'<span style="left:{t / _ZN_SPAN * 100:.2f}%">{t}%</span>' for t in (0, 50, 100, 150)
    )
    plot = (
        f'<div data-eg-live="ch3-zones"><div class="{P}-eg-zax" aria-hidden="true"><span class="{P}-eg-zaxp"></span>'
        f'<span class="{P}-eg-zaxm">{axis}</span></div>'
        f'<ul class="{P}-eg-rows">{"".join(rows)}</ul></div>'
    )
    controls = (
        f'<label class="gg-eg-field">FTP<input type="number" inputmode="numeric" min="100" max="500" step="1" '
        f'value="{_ZN_FTP}" data-eg-in="ftp" aria-label="Functional threshold power in watts"> W</label>'
    )
    head = glyph.readout(
        "Z2–Z4", "", _zn_home_w(_ZN_FTP), f"FTP {_ZN_FTP} W",
        f'<span data-eg-f="txt">{_e(_ZN_HOME)}</span>',
    )
    alt = block.get("alt") or "Seven training zones from Z1 Active Recovery to Z7 Neuromuscular on a percent of FTP scale; Z2 to Z4 highlighted"
    desc = f"{alt}. " + " ".join(f"{c} {n_} {r_}: {d}" for c, n_, r_, _, _, d in _ZONES)
    data = {"ftp": _ZN_FTP, "home": _ZN_HOME, "zones": [list(z) for z in _ZONES]}
    card = glyph.glyph_card(
        "Training zones", head, plot, controls_html=controls,
        data=data, describedby="gg-eg-zn-d", description=desc,
    )
    return _glyph_panel(
        block, "CH 3 · ZONES", "The Seven Training Zones", card,
        "The zone spectrum — from recovery spin to redline effort.",
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
_TP_SUMMARY = "Base wk 1–5 · Build wk 6–9 · Peak / Taper wk 10–12"


def _tp_phase(i):
    return 0 if i < 5 else (1 if i < 9 else 2)


def render_training_phases(block: dict) -> str:
    W, H = 1200, 100
    cols = "".join(
        f'<span class="{P}-eg-cw"><i class="{P}-eg-col {P}-eg-col--{_PHASES[_tp_phase(i)][3]}" '
        f'style="--h:{v * 100:.0f}%;--a:{30 + 70 * v:.0f}%"></i></span>'
        for i, v in enumerate(_VOL)
    )
    ipts = [((i + 0.5) / 12 * W, (1 - v) * H) for i, v in enumerate(_INT)]
    ipath = glyph.line_path(ipts)
    refs = "".join(
        f'<line class="{P}-eg-ref" x1="0" x2="{W}" y1="{(1 - v) * H:.1f}" y2="{(1 - v) * H:.1f}"/>' for v in (0.5, 1.0)
    )
    svg = (
        f'<svg class="gg-eg-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">'
        f'{refs}<path class="{P}-eg-case" d="{ipath}"/><path class="{P}-eg-hero" d="{ipath}"/></svg>'
    )
    ylab = "".join(
        f'<span class="{P}-eg-yl{" " + P + "-eg-yl--top" if v == 100 else ""}" style="top:{100 - v}%">{v}</span>'
        for v in (100, 50)
    )
    pt = (
        f'<i class="gg-eg-pt" data-eg-pt style="left:{(6 + 0.5) / 12 * 100:.2f}%;top:{(1 - _INT[6]) * 100:.1f}%"></i>'
    )
    plot = f'<div class="{P}-eg-colrow">{cols}</div>{svg}{ylab}{pt}'
    wi = 6
    vt = f"Week {wi + 1}: {_PHASES[_tp_phase(wi)][0]}, volume {round(_VOL[wi] * 100)}%, intensity {round(_INT[wi] * 100)}%"
    pw = glyph.scrub_wrap("ch3-tp", plot, 12, wi, "Scrub the 12 weeks", vt, mode="band")
    band = "".join(
        f'<div class="{P}-eg-ph {P}-eg-ph--{k}" style="flex:{w}"><b>{_e(n_)}</b><span>{_e(wk)}</span></div>'
        for n_, wk, w, k, _ in _PHASES
    )
    wkr = "".join(f"<span>{i}</span>" for i in range(1, 13))
    # end capsules, spread so the two never overlap
    t_int, t_vol = (1 - _INT[11]) * 100, (1 - _VOL[11]) * 100
    if abs(t_vol - t_int) < 14:
        t_vol = t_int + 14
    ends = (
        f'<div class="{P}-eg-ends"><div style="top:{t_int:.1f}%">{glyph.capsule(round(_INT[11] * 100), "Intensity", "ink", "filled")}</div>'
        f'<div style="top:{t_vol:.1f}%">{glyph.capsule(round(_VOL[11] * 100), "Volume", "ink", "outlined")}</div></div>'
    )
    wrap = (
        f'<div class="{P}-eg-wrap">{pw}'
        f'<div class="{P}-eg-phband" aria-hidden="true">{band}</div>'
        f'<div class="{P}-eg-wkr" aria-hidden="true">{wkr}</div>{ends}</div>'
    )
    extra = (
        f'<span class="{P}-eg-os">{glyph.capsule("", "Volume", "ink", "outlined", field="vol")}</span>'
        f'<span class="{P}-eg-os">{glyph.capsule("", "Intensity", "ink", "filled", field="int")}</span>'
        f'<span data-eg-f="txt">{_e(_TP_SUMMARY)}</span>'
    )
    head = glyph.readout(12, "weeks", "Base → Build → Peak", "3 phases", extra)
    alt = block.get("alt") or "12-week periodization: volume builds through Base and peaks in week 7, intensity ramps through Build and peaks in week 9, both fall into the taper"
    desc = (
        f"{alt}. " + " ".join(t for *_, t in _PHASES)
        + " Volume by week, percent of the scale: " + ", ".join(str(round(v * 100)) for v in _VOL)
        + ". Intensity: " + ", ".join(str(round(v * 100)) for v in _INT) + "."
    )
    data = {
        "vol": [round(v * 100) for v in _VOL], "int": [round(v * 100) for v in _INT],
        "phases": [[n_, k, t] for n_, _, _, k, t in _PHASES], "summary": _TP_SUMMARY,
    }
    card = glyph.glyph_card(
        "Twelve-week build", head, wrap, data=data, describedby="gg-eg-tp-d", description=desc,
    )
    return _glyph_panel(
        block, "CH 3 · PERIODIZATION", "Periodization: Building Fitness in Three Phases", card,
        "The 12-week build: volume peaks in Base, intensity peaks in Build, both taper for race day.",
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


# ── 6. Season band ──────────────────────────────────────────

# (name, start month, end month, description, kind) counted in months from the plan start
_GANTT = [
    ("Off-Season", 0, 1.5, "Active recovery, cross-training, mental reset", "off"),
    ("Base 1", 1.5, 5, "Aerobic foundation, long Z2 rides, consistency", "base"),
    ("Base 2", 5, 7, "Add tempo work, longer rides, race-surface training", "base"),
    ("Build", 7, 9.5, "Intervals, race simulation, peak training load", "build"),
    ("Race Season", 9.5, 12, "A-race taper, B-race maintenance, peak performance", "race"),
    ("Transition", 12, 13, "Deload, reflect, plan next year. Ride for fun.", "trans"),
]
_MONTHS12 = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_GT_ANCHOR = 9.5  # the A race opens the Race Season block: 9.5 months after the plan starts
_GT_RACE_DEF = 7  # August
_GT_N = 13


def _gt_start(race_month):
    """Plan start month (0 = Jan) so the A race lands mid race_month."""
    return (race_month - int(_GT_ANCHOR)) % 12


def _gt_pos(s, p, is_end):
    """Month label for position p months after the plan start (mirrored in JS)."""
    if p - math.floor(p) == 0.5:
        return "mid " + _MONTHS12[(s + int(math.floor(p))) % 12]
    k = math.ceil(p) - 1 if is_end else int(math.floor(p))
    return _MONTHS12[(s + int(k)) % 12]


def _gt_dates(s, a, b):
    x, y = _gt_pos(s, a, False), _gt_pos(s, b, True)
    t = x if x == y else f"{x} – {y}"
    return t[0].upper() + t[1:]


def render_gantt_season(block: dict) -> str:
    s = _gt_start(_GT_RACE_DEF)
    n = _GT_N
    band = "".join(
        f'<span class="{P}-eg-gseg {P}-eg-gseg--{k}" style="left:{a / n * 100:.2f}%;width:{(b - a) / n * 100:.2f}%" '
        f'title="{_e(name)}"></span>'
        for name, a, b, _, k in _GANTT
    )
    flag = (
        f'<span class="{P}-eg-gflag" style="left:{_GT_ANCHOR / n * 100:.2f}%">'
        f'{glyph.capsule("A", "", "ink", "outlined")}</span>'
    )
    ruler = "".join(
        f'<span data-eg-mo="{k}"><i class="{P}-eg-gfull">{_MONTHS12[(s + k) % 12]}</i>'
        f'<i class="{P}-eg-gshort">{_MONTHS12[(s + k) % 12][0]}</i></span>'
        for k in range(n)
    )
    rows = "".join(
        f'<li class="{P}-eg-gr"><span class="{P}-eg-gsw {P}-eg-gseg--{k}"></span>'
        f'<b class="{P}-eg-gn">{_e(name)}</b>'
        f'<span class="{P}-eg-gd" data-eg-d="{i}">{_e(_gt_dates(s, a, b))}</span>'
        f'<span class="{P}-eg-gx">{_e(desc)}</span></li>'
        for i, (name, a, b, desc, k) in enumerate(_GANTT)
    )
    plot = (
        f'<div data-eg-live="ch3-gantt"><div class="{P}-eg-gband">{band}{flag}</div>'
        f'<div class="{P}-eg-gruler" aria-hidden="true">{ruler}</div>'
        f'<ol class="{P}-eg-gl">{rows}</ol></div>'
    )
    opts = "".join(
        f'<option value="{m}"{" selected" if m == _GT_RACE_DEF else ""}>{_MONTHS12[m]}</option>' for m in range(12)
    )
    controls = (
        f'<label class="gg-eg-field">A race month<select class="{P}-eg-sel" data-eg-in="race" '
        f'aria-label="Month of your A race">{opts}</select></label>'
    )
    head = glyph.readout(
        _MONTHS12[s], "start", f"A race: mid {_MONTHS12[_GT_RACE_DEF]}", f"{len(_GANTT)} blocks",
        f'<span data-eg-f="txt">Blocks build backwards from the A race.</span>',
    )
    alt = block.get("alt") or "A 12-month season: off-season, two base blocks, build, race season, then transition"
    desc = (
        f"{alt}. Starting {_MONTHS12[s]} for an A race in mid {_MONTHS12[_GT_RACE_DEF]}: "
        + "; ".join(f"{name} {_gt_dates(s, a, b)}" for name, a, b, _, _ in _GANTT) + "."
    )
    data = {
        "blocks": [[name, a, b, k] for name, a, b, _, k in _GANTT], "months": _MONTHS12,
        "anchor": _GT_ANCHOR, "race": _GT_RACE_DEF,
    }
    card = glyph.glyph_card(
        "Season plan", head, plot, controls_html=controls,
        data=data, describedby="gg-eg-gt-d", description=desc,
    )
    return _glyph_panel(
        block, "CH 3 · SEASON", "The Annual Training Calendar: 12 Months at a Glance", card,
        "A full season planned — stack race-specific blocks with recovery windows.",
    )


# ── 7. Before / after ───────────────────────────────────────

# (metric, before text, after text, before value, after value, meter max, change, note)
_BA = [
    ("FTP", "180W", "250W", 180, 250, 300, "+39%", "39% increase"),
    ("4hr Power", "140W", "195W", 140, 195, 300, "+39%", "Sustained race power"),
    ("Recovery HR", "95 bpm", "68 bpm", 95, 68, 120, "-27 bpm", "Faster bounce-back"),
    ("Time to Exhaustion", "3.5 hrs", "7+ hrs", 3.5, 7, 8, "2x+", "Double the endurance"),
    ("Body Comp", "22% BF", "15% BF", 22, 15, 30, "-7 pts", "Power-to-weight gains"),
    # percentile of the field beaten: Bottom 25% -> 25, Top 35% -> 65
    ("Race Finish", "Bottom 25%", "Top 35%", 25, 65, 100, "+40 pts", "Mid-pack competitive"),
]
_BA_WHEN = "12 months"


def render_before_after(block: dict) -> str:
    rows = "".join(
        f'<li><button type="button" class="{P}-eg-row {P}-eg-brow" data-eg-row="{i}" aria-pressed="false">'
        f'<span class="{P}-eg-bm">{_e(m)}</span>'
        f'<span class="{P}-eg-bv">{_e(bt)} → {_e(at)}</span>'
        f'<span class="{P}-eg-rm">{glyph.meter(av, mx, tick=bv)}</span>'
        f'<span class="{P}-eg-bc">{glyph.capsule(chg, "", "ink", "filled")}</span></button></li>'
        for i, (m, bt, at, bv, av, mx, chg, _) in enumerate(_BA)
    )
    key = (
        f'<p class="{P}-eg-bkey" aria-hidden="true"><i class="{P}-eg-bkb"></i>After'
        f'<i class="gg-eg-tick {P}-eg-bkt"></i>Before</p>'
    )
    plot = f'<div data-eg-live="ch3-ba">{key}<ul class="{P}-eg-rows">{rows}</ul></div>'
    m, bt, at, _, _, _, chg, note = _BA[0]
    head = glyph.readout(chg, m, f"{bt} → {at}", _BA_WHEN, f'<span data-eg-f="txt">{_e(note)}</span>')
    alt = block.get("alt") or "Before and after training: FTP 180 W to 250 W, 4 hour power 140 W to 195 W"
    desc = f"{alt}. Untrained, then 12 months of structured training. " + "; ".join(
        f"{m_}: {b_} to {a_}, {c_}" for m_, b_, a_, _, _, _, c_, _ in _BA
    ) + "."
    data = {"rows": [[m_, b_, a_, c_, n_] for m_, b_, a_, _, _, _, c_, n_ in _BA], "when": _BA_WHEN}
    card = glyph.glyph_card(
        "Before and after", head, plot, data=data, describedby="gg-eg-ba-d", description=desc,
    )
    return _glyph_panel(
        block, "CH 3 · RESULTS", "12 Months of Structured Training: Before vs. After", card,
        "12 weeks of consistent training — the numbers do not lie.",
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


JS_B = r"""
(function () {
  function r(x) { return Math.floor(x + 0.5); }
  function setf(card, key, t) {
    var n = card.querySelector('[data-eg-f="' + key + '"]');
    if (n) n.textContent = t;
  }
  function sg(v) { return v === 0 ? "0" : GGEG.signed(v, 0); }
  // Cards with no scrub plot: bind row pickers / inputs ourselves.
  function live(id, fn) {
    var els = document.querySelectorAll('[data-eg-live="' + id + '"]');
    for (var k = 0; k < els.length; k++) {
      var el = els[k];
      if (el.getAttribute("data-eg-lbound")) continue;
      el.setAttribute("data-eg-lbound", "1");
      var card = el.closest(".gg-eg");
      if (!card) continue;
      var data = {};
      var isl = card.querySelector("script.gg-eg-data");
      if (isl) { try { data = JSON.parse(isl.textContent); } catch (e) { data = {}; } }
      card.classList.add("is-live");
      fn(el, card, data);
    }
  }
  function pick(el, show) {
    var rows = el.querySelectorAll("[data-eg-row]");
    var cur = -1;
    function paint() {
      for (var k = 0; k < rows.length; k++) rows[k].setAttribute("aria-pressed", k === cur ? "true" : "false");
      show(cur);
    }
    for (var k = 0; k < rows.length; k++) {
      rows[k].addEventListener("click", function (e) {
        var i = parseInt(e.currentTarget.getAttribute("data-eg-row"), 10);
        cur = cur === i ? -1 : i;
        paint();
      });
    }
    paint();
    return paint;
  }

  // 1. Supercompensation
  function stageOf(d, day) {
    var best = 0, bd = 1e9;
    for (var k = 0; k < d.stages.length; k++) {
      var dd = Math.abs(d.stages[k][0] - day);
      if (dd < bd) { bd = dd; best = k; }
    }
    return d.stages[best][1];
  }
  function verdict(d, day) {
    var lv = d.lvl[day], mi = 0, k, rec = d.lvl.length;
    for (k = 0; k < d.lvl.length; k++) if (d.lvl[k] < d.lvl[mi]) mi = k;
    for (k = mi + 1; k < d.lvl.length; k++) if (d.lvl[k] >= 0) { rec = k; break; }
    if (lv === 0) return "Lands at baseline: no boost yet";
    if (lv > 0 && day < rec) return "Lands before the dip: " + sg(lv) + " vs baseline";
    if (lv > 0) return "Lands on the overshoot: " + sg(lv) + " above baseline";
    if (day < rec) return "Lands in the fatigue hole: " + (-lv) + " below baseline";
    return "Lands after the overshoot faded: " + (-lv) + " below baseline";
  }
  GGEG.register("ch3-sc", function (i, c) {
    var d = c.data, lv = d.lvl[i];
    c.set("num", sg(lv));
    c.set("chip", stageOf(d, i));
    c.set("when", "Day " + i);
    var pt = c.q("[data-eg-pt]");
    if (pt) {
      pt.style.left = (i / d.days * 100) + "%";
      pt.style.top = ((d.hi - lv) / (d.hi - d.lo) * 100) + "%";
    }
    return "Day " + i + ": " + sg(lv) + " vs baseline, " + stageOf(d, i);
  }, function (c) {
    var d = c.data, inp = c.q('[data-eg-in="nh"]'), mk = c.q("[data-eg-nh]");
    if (!inp) return;
    function go() {
      var day = parseInt(inp.value, 10);
      if (!isFinite(day)) return;
      day = Math.min(d.days, Math.max(0, day));
      if (mk) mk.style.left = (day / d.days * 100) + "%";
      c.set("nhday", "Day " + day);
      c.set("verdict", verdict(d, day));
    }
    inp.addEventListener("input", go);
    go();
  });

  // 2. Zone ledger
  live("ch3-zones", function (el, card, d) {
    var ftp = d.ftp, cur = -1;
    function w(i) {
      var z = d.zones[i];
      if (i === 0) return "≤ " + r(z[4] / 100 * ftp) + " W";
      if (i === d.zones.length - 1) return "Max";
      return r(z[3] / 100 * ftp) + "–" + r(z[4] / 100 * ftp) + " W";
    }
    function show(i) {
      cur = i;
      var k;
      for (k = 0; k < d.zones.length; k++) {
        var s = el.querySelector('[data-eg-w="' + k + '"]');
        if (s) s.textContent = w(k);
      }
      if (i < 0) {
        setf(card, "num", "Z2–Z4");
        setf(card, "unit", "");
        setf(card, "chip", r(0.55 * ftp) + "–" + r(1.05 * ftp) + " W");
        setf(card, "when", "FTP " + ftp + " W");
        setf(card, "txt", d.home);
      } else {
        var z = d.zones[i];
        setf(card, "num", z[0]);
        setf(card, "unit", z[1]);
        setf(card, "chip", w(i));
        setf(card, "when", z[2] + " FTP");
        setf(card, "txt", z[5]);
      }
    }
    var paint = pick(el, show);
    var inp = card.querySelector('[data-eg-in="ftp"]');
    if (inp) inp.addEventListener("input", function () {
      var v = parseFloat(inp.value);
      if (!isFinite(v) || v < 100 || v > 500) { inp.setAttribute("aria-invalid", "true"); return; }
      inp.removeAttribute("aria-invalid");
      ftp = v;
      show(cur);
    });
  });

  // 4. Training phases
  GGEG.register("ch3-tp", function (i, c) {
    var d = c.data, ph = d.phases[i < 5 ? 0 : (i < 9 ? 1 : 2)];
    if (!c.scrubbing) {
      c.set("num", "12");
      c.set("unit", "weeks");
      c.set("chip", "Base → Build → Peak");
      c.set("when", "3 phases");
      c.set("txt", d.summary);
    } else {
      c.set("num", String(d.vol[i]));
      c.set("unit", "% volume");
      c.set("chip", ph[0]);
      c.set("when", "Week " + (i + 1));
      c.set("vol", d.vol[i] + "%");
      c.set("int", d.int[i] + "%");
      c.set("txt", ph[2]);
    }
    var pt = c.q("[data-eg-pt]");
    if (pt) { pt.style.left = ((i + 0.5) / 12 * 100) + "%"; pt.style.top = (100 - d.int[i]) + "%"; }
    return "Week " + (i + 1) + ": " + ph[0] + ", volume " + d.vol[i] + "%, intensity " + d.int[i] + "%";
  });

  // 6. Season band
  live("ch3-gantt", function (el, card, d) {
    function pos(s, p, isEnd) {
      if (p - Math.floor(p) === 0.5) return "mid " + d.months[(s + Math.floor(p)) % 12];
      var k = isEnd ? Math.ceil(p) - 1 : Math.floor(p);
      return d.months[(s + k) % 12];
    }
    function dates(s, a, b) {
      var x = pos(s, a, false), y = pos(s, b, true);
      var t = x === y ? x : x + " – " + y;
      return t.charAt(0).toUpperCase() + t.slice(1);
    }
    function go(m) {
      var s = ((m - Math.floor(d.anchor)) % 12 + 12) % 12, k;
      var mo = el.querySelectorAll("[data-eg-mo]");
      for (k = 0; k < mo.length; k++) {
        var nm = d.months[(s + k) % 12], is = mo[k].querySelectorAll("i");
        if (is[0]) is[0].textContent = nm;
        if (is[1]) is[1].textContent = nm.charAt(0);
      }
      for (k = 0; k < d.blocks.length; k++) {
        var cell = el.querySelector('[data-eg-d="' + k + '"]');
        if (cell) cell.textContent = dates(s, d.blocks[k][1], d.blocks[k][2]);
      }
      setf(card, "num", d.months[s]);
      setf(card, "chip", "A race: mid " + d.months[m]);
    }
    var sel = card.querySelector('[data-eg-in="race"]');
    if (sel) sel.addEventListener("change", function () {
      var m = parseInt(sel.value, 10);
      if (isFinite(m)) go(m);
    });
  });

  // 7. Before / after
  live("ch3-ba", function (el, card, d) {
    pick(el, function (i) {
      var row = d.rows[i < 0 ? 0 : i];
      setf(card, "num", row[3]);
      setf(card, "unit", row[0]);
      setf(card, "chip", row[1] + " → " + row[2]);
      setf(card, "when", d.when);
      setf(card, "txt", row[4]);
    });
  });
})();
"""

JS = JS + JS_B


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
.gg-ig-b-body{padding:24px 28px 26px}
.gg-ig-b-cap{margin:0 28px 28px;padding:4px 0 4px 16px;border-left:6px solid var(--gg-color-light-gold);font-family:var(--gg-font-editorial);font-style:italic;font-size:16px;line-height:1.5}
.gg-ig-b-panel--dark .gg-ig-b-cap{color:var(--gg-color-sand)}
/* power duration */
@media (max-width:700px){
.gg-ig-b-head{padding:18px 16px 16px}
.gg-ig-b-title{font-size:24px}
.gg-ig-b-body{padding:18px 16px 20px}
.gg-ig-b-cap{margin:0 16px 22px}
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

_EG2_CSS = """
.gg-eg-pw[data-eg-scrub="ch3-sc"]{height:220px}
.gg-eg-pw[data-eg-scrub="ch3-tp"]{height:180px}
.gg-ig-b-eg-note2{position:absolute;transform:translate(-50%,8px);font-family:var(--eg-mono);font-size:11px;font-weight:700;color:var(--eg-ink2);white-space:nowrap;text-shadow:0 0 3px var(--eg-card),0 0 3px var(--eg-card);pointer-events:none}
.gg-ig-b-eg-note2--up{transform:translate(-50%,-150%)}
.gg-ig-b-eg-note2--l{transform:translate(0,-130%);left:4px!important;color:var(--eg-ink3)}
.gg-ig-b-eg-nh{position:absolute;top:0;bottom:0;width:0;border-left:2px dotted var(--eg-ride);pointer-events:none;z-index:2}
.gg-ig-b-eg-nh span{position:absolute;bottom:4px;left:6px;font-family:var(--eg-mono);font-size:11px;font-weight:700;color:var(--eg-ride);white-space:nowrap;text-shadow:0 0 3px var(--eg-card),0 0 3px var(--eg-card)}
.gg-ig-b-eg-rng{width:150px;min-height:44px;margin:0 4px;accent-color:var(--eg-ride)}
.gg-ig-b-eg-xt--end{transform:translateX(-100%)}
.gg-ig-b-eg-rows{display:block;max-width:660px}
.gg-ig-b-eg-rows li{display:block;margin:0;padding:0}
.gg-ig-b-eg-row{appearance:none;display:grid;align-items:center;width:100%;min-height:44px;margin:0;padding:6px 8px;background:transparent;border:0;border-radius:8px!important;font-family:var(--eg-mono);color:var(--eg-ink);text-align:left;cursor:pointer}
.gg-ig-b-eg-row:hover{background:var(--eg-paper)}
.gg-ig-b-eg-row[aria-pressed="true"]{background:var(--eg-control);box-shadow:inset 3px 0 0 var(--eg-cobalt)!important}
.gg-ig-b-eg-zrow{grid-template-columns:30px 124px minmax(90px,1fr) 66px 74px;gap:0 10px}
.gg-ig-b-eg-rc{font-weight:800;font-size:14px}
.gg-ig-b-eg-rn{font-family:var(--eg-prose);font-weight:600;font-size:14px;color:var(--eg-ink2)}
.gg-ig-b-eg-rp{font-size:12px;color:var(--eg-ink3);text-align:right;white-space:nowrap}
.gg-ig-b-eg-rw{font-size:12px;font-weight:700;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.gg-ig-b-eg-rm{min-width:0}
.gg-ig-b-eg-zm b{left:0}
.gg-ig-b-eg-zm--cool b{background:var(--eg-none)}
.gg-ig-b-eg-zax{max-width:660px;display:grid;grid-template-columns:30px 124px minmax(90px,1fr) 66px 74px;gap:0 10px;padding:0 8px;height:18px;font-family:var(--eg-mono);font-size:11px;color:var(--eg-ink3)}
.gg-ig-b-eg-zaxp{grid-column:1/3}
.gg-ig-b-eg-zaxm{position:relative}
.gg-ig-b-eg-zaxm span{position:absolute;top:0;transform:translateX(-50%)}
.gg-ig-b-eg-zaxm span:first-child{transform:none}
.gg-ig-b-eg-brow{grid-template-columns:130px minmax(90px,1fr) 78px;grid-template-areas:"m v v" "r r c";gap:2px 10px}
.gg-ig-b-eg-bm{grid-area:m;font-family:var(--eg-prose);font-weight:600;font-size:14px;color:var(--eg-ink2)}
.gg-ig-b-eg-bv{grid-area:v;font-size:12px;color:var(--eg-ink3);font-variant-numeric:tabular-nums}
.gg-ig-b-eg-brow .gg-ig-b-eg-rm{grid-area:r}
.gg-ig-b-eg-bc{grid-area:c;justify-self:start}
.gg-ig-b-eg-bkey{display:flex;align-items:center;gap:6px;font-family:var(--eg-mono);font-size:11px;color:var(--eg-ink3);margin:0 8px 6px!important}
.gg-ig-b-eg-bkb{display:inline-block;width:18px;height:10px;background:var(--eg-ink);border-radius:2px!important}
.gg-ig-b-eg-bkt{position:static!important;display:inline-block;height:14px;margin:0 0 0 10px!important}
.gg-ig-b-eg-colrow{position:absolute;inset:0;display:flex;gap:3px;align-items:flex-end}
.gg-ig-b-eg-cw{flex:1;min-width:0;height:100%;display:flex;align-items:flex-end}
.gg-ig-b-eg-col{display:block;width:100%;height:var(--h);border-radius:2px 2px 0 0!important;background:color-mix(in srgb,var(--ph) var(--a),var(--eg-card))}
.gg-ig-b-eg-col--base{--ph:var(--eg-none)}
.gg-ig-b-eg-col--build{--ph:var(--eg-ride)}
.gg-ig-b-eg-col--peak{--ph:var(--eg-form)}
.gg-ig-b-eg-phband{display:flex;gap:3px;margin-top:6px}
.gg-ig-b-eg-ph{min-width:0;padding:5px 6px;border-radius:4px!important;font-family:var(--eg-mono);font-size:11px;line-height:1.2;color:var(--eg-ink);display:flex;flex-direction:column;gap:1px}
.gg-ig-b-eg-ph b{font-weight:800;overflow-wrap:anywhere}
.gg-ig-b-eg-ph--base{background:color-mix(in srgb,var(--eg-none) 55%,var(--eg-card))}
.gg-ig-b-eg-ph--build{background:color-mix(in srgb,var(--eg-ride) 40%,var(--eg-card))}
.gg-ig-b-eg-ph--peak{background:color-mix(in srgb,var(--eg-form) 40%,var(--eg-card))}
.gg-ig-b-eg-wkr{display:flex;margin-top:4px;font-family:var(--eg-mono);font-size:11px;color:var(--eg-ink3)}
.gg-ig-b-eg-wkr span{flex:1;text-align:center}
.gg-eg:not(.is-scrub) .gg-ig-b-eg-os{display:none}
.gg-ig-b-eg-gband{position:relative;height:30px;background:var(--eg-paper);border-radius:4px!important}
.gg-ig-b-eg-gseg{position:absolute;top:0;bottom:0;border-radius:3px!important;border-right:2px solid var(--eg-card)}
.gg-ig-b-eg-gseg--off,.gg-ig-b-eg-gseg--trans{background:var(--eg-none)}
.gg-ig-b-eg-gseg--base{background:var(--eg-ink3)}
.gg-ig-b-eg-gseg--build{background:var(--eg-ride)}
.gg-ig-b-eg-gseg--race{background:var(--eg-ink)}
.gg-ig-b-eg-gflag{position:absolute;top:50%;transform:translate(-50%,-50%);z-index:2}
.gg-ig-b-eg-gruler{display:grid;grid-template-columns:repeat(13,1fr);margin-top:4px;font-family:var(--eg-mono);font-size:11px;color:var(--eg-ink3);text-align:center}
.gg-ig-b-eg-gruler span{border-left:1px solid var(--eg-none);padding-top:3px;min-width:0}
.gg-ig-b-eg-gruler i{font-style:normal}
.gg-ig-b-eg-gshort{display:none}
.gg-ig-b-eg-gl{display:block;margin-top:12px}
.gg-ig-b-eg-gr{display:grid;grid-template-columns:14px 104px 138px 1fr;gap:2px 10px;align-items:baseline;padding:7px 0;border-top:1px solid var(--eg-line);margin:0}
.gg-ig-b-eg-gsw{display:inline-block;width:12px;height:12px;border-radius:2px!important;align-self:center;position:static!important;border:0!important}
.gg-ig-b-eg-gn{font-family:var(--eg-prose);font-weight:600;font-size:14px;color:var(--eg-ink)}
.gg-ig-b-eg-gd{font-family:var(--eg-mono);font-weight:700;font-size:12px;color:var(--eg-ink);white-space:nowrap}
.gg-ig-b-eg-gx{font-size:12px;color:var(--eg-ink3);line-height:1.35}
.gg-ig-b-eg-sel{min-height:44px;font-family:var(--eg-mono);font-weight:700;font-size:14px;color:var(--eg-ink);background:var(--eg-card);border:1px solid var(--eg-none);border-radius:8px!important;padding:0 8px;margin:0}
@media (max-width:700px){
.gg-eg-pw[data-eg-scrub="ch3-sc"]{height:190px}
.gg-eg-pw[data-eg-scrub="ch3-tp"]{height:150px}
.gg-ig-b-eg-rng{width:90px}
.gg-eg-field span{white-space:nowrap}
.gg-ig-b-eg-zrow{grid-template-columns:28px minmax(0,1fr) 78px;grid-template-areas:"c n w" "m m p";gap:4px 8px}
.gg-ig-b-eg-zrow .gg-ig-b-eg-rc{grid-area:c}
.gg-ig-b-eg-zrow .gg-ig-b-eg-rn{grid-area:n}
.gg-ig-b-eg-zrow .gg-ig-b-eg-rm{grid-area:m}
.gg-ig-b-eg-zrow .gg-ig-b-eg-rp{grid-area:p}
.gg-ig-b-eg-zrow .gg-ig-b-eg-rw{grid-area:w}
.gg-ig-b-eg-zax{display:none}
.gg-ig-b-eg-brow{grid-template-columns:1fr 78px;grid-template-areas:"m m" "v v" "r c"}
.gg-ig-b-eg-gfull{display:none}
.gg-ig-b-eg-gshort{display:inline}
.gg-ig-b-eg-gr{grid-template-columns:14px 1fr auto;grid-template-areas:"s n d" "x x x"}
.gg-ig-b-eg-gr .gg-ig-b-eg-gsw{grid-area:s}
.gg-ig-b-eg-gr .gg-ig-b-eg-gn{grid-area:n}
.gg-ig-b-eg-gr .gg-ig-b-eg-gd{grid-area:d}
.gg-ig-b-eg-gr .gg-ig-b-eg-gx{grid-area:x;padding-left:24px}
.gg-ig-b-eg-ph{padding:4px 4px}
}
"""

CSS = _scope(_CSS_RAW + _EG_CSS + _EG2_CSS)
