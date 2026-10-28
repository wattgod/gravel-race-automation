"""Handbook charts for Chapter 4 (Recovery) and Chapter 5 (Fueling).

Round 2 (2026-10-28): six Endure Glyph cards inside the Gravel God panel
(execution gap, recovery dashboard, traffic light, sleep debt, glycogen, calorie burn)
and four poster panels with live inputs (bonk math, macro split, fueling timeline,
hydration calculator). All numbers come from the round-1 renderers; every model is
stated beside the code that uses it. CSS prefix: .gg-ig-c-
"""
import html as _html

from guide_ig import glyph

_NAME = "ch4_ch5"
P = "gg-ig-c"


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


def _gpanel(block, eyebrow, title, card):
    """GG title band + Glyph card + gold-ruled caption."""
    return _panel("eg", "light", eyebrow, title, card, block.get("caption", ""))


def _g(v) -> str:
    return f"{v:g}"


def _areas(xs, ys, ty):
    """Filled areas between a polyline and the horizontal line y=ty.

    Returns [(side, path)] where side is 1 when the line is below ty (y larger), else -1.
    Crossings are inserted so each fill ends exactly on the target line.
    """
    runs = []

    def push(s, pt):
        if runs and runs[-1][0] == s:
            runs[-1][1].append(pt)
        else:
            runs.append([s, [pt]])

    for k in range(len(xs)):
        d0 = ys[k] - ty
        s0 = 1 if d0 > 0 else -1
        push(s0, (xs[k], ys[k]))
        if k + 1 < len(xs):
            d1 = ys[k + 1] - ty
            s1 = 1 if d1 > 0 else -1
            if s0 != s1:
                x = xs[k] + d0 / (d0 - d1) * (xs[k + 1] - xs[k])
                push(s0, (x, ty))
                push(s1, (x, ty))
    out = []
    for s, pts in runs:
        poly = pts + [(pts[-1][0], ty), (pts[0][0], ty)]
        out.append((s, glyph.line_path(poly, close=True)))
    return out


def _yl(label, pct, top=False) -> str:
    cls = f"{P}-eg-yl" + (f" {P}-eg-yl--top" if top else "")
    return f'<span class="{cls}" style="top:{pct:.1f}%">{_e(label)}</span>'


# ── Chapter 4 ───────────────────────────────────────────────

_GAP_PLAN = 85
_GAP = [("Int 1", 95), ("Int 2", 78), ("Int 3", 55), ("Int 4", 84), ("Int 5", 83), ("Int 6", 85)]
_GAP_GRP = ["chased"] * 3 + ["steady"] * 3
_GAP_TEXT = {  # shown in the header when nothing is scrubbed: num, chip, when, note
    "chased": ["95→55", "Int 1 to 3", "Chased watts", "Starts hot, fades to 55"],
    "steady": ["83-85", "within 2 of plan", "Steady", "All within 2 of plan"],
}


def render_execution_gap(block: dict) -> str:
    W, H, YMAX = 600, 200, 110
    y = lambda v: H * (1 - v / YMAX)  # noqa: E731
    n = len(_GAP)
    parts = [f'<line class="{P}-eg-ref" x1="0" x2="{W}" y1="{y(100):.1f}" y2="{y(100):.1f}"/>',
             f'<line class="{P}-eg-ref" x1="0" x2="{W}" y1="{H}" y2="{H}"/>']
    for i, (_lab, act) in enumerate(_GAP):
        x0 = i * (W / n) + 14
        w = W / n - 28
        top, bot = sorted((y(act), y(_GAP_PLAN)))
        parts.append(
            f'<g class="{P}-eg-bar" data-g="{_GAP_GRP[i]}">'
            f'<rect class="{P}-eg-dev" x="{x0:.1f}" y="{top:.1f}" width="{w:.1f}" height="{bot - top:.1f}"/>'
            f'<rect class="{P}-eg-done" x="{x0:.1f}" y="{y(act):.1f}" width="{w:.1f}" height="{H - y(act):.1f}"/>'
            f'<rect class="{P}-eg-planbox" x="{x0:.1f}" y="{y(_GAP_PLAN):.1f}" width="{w:.1f}" height="{H - y(_GAP_PLAN):.1f}"/>'
            f'</g>'
        )
    svg = (f'<svg class="gg-eg-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">'
           f'{"".join(parts)}</svg>')
    plot = (f'<div class="{P}-eg-plot">{svg}{_yl("100", (1 - 100 / YMAX) * 100, True)}{_yl("0", 100)}'
            f'<i class="gg-eg-pt" data-eg-pt style="display:none"></i></div>')
    vt = f"Int 1: {_GAP[0][1]}% FTP, plan {_GAP_PLAN}"
    pw = glyph.scrub_wrap("ch4-gap", plot, n, 0, "Scrub the six intervals", vt, mode="band")
    xl = "".join(f'<span data-g="{_GAP_GRP[i]}">{_e(lab)}</span>' for i, (lab, _a) in enumerate(_GAP))
    t = _GAP_TEXT["chased"]
    extra = glyph.capsule(f"{_GAP_PLAN}%", "Plan", "ink", "dotted") + f'<span data-eg-f="note">{_e(t[3])}</span>'
    head = glyph.readout(t[0], "% FTP", t[1], t[2], extra)
    seg = (
        f'<span class="gg-eg-seg" role="group" aria-label="Which intervals">'
        f'<button type="button" data-grp="chased" aria-pressed="true">Chased watts</button>'
        f'<button type="button" data-grp="steady" aria-pressed="false">Steady</button></span>'
    )
    desc = (
        f"Six intervals planned at {_GAP_PLAN}% of FTP. Done: "
        + ", ".join(f"{lab} {a}%" for lab, a in _GAP)
        + ". Intervals 1 to 3 chase watts: the start is hot at 95% and fades to 55%. "
        "Intervals 4 to 6 hold 83-85%, all within 2% of target."
    )
    card = glyph.glyph_card(
        "Plan vs done", head,
        f'{pw}<div class="{P}-eg-xl {P}-eg-xl--6" aria-hidden="true">{xl}</div>',
        controls_html=seg,
        data={"plan": _GAP_PLAN, "act": [a for _l, a in _GAP], "lab": [l for l, _a in _GAP],
              "grp": _GAP_GRP, "gt": _GAP_TEXT, "ymax": YMAX},
        describedby="gg-eg-gap-d", description=desc,
    )
    return _gpanel(block, "CH 4 · EXECUTION", "The Execution Gap: Plan vs. Reality", card)


# Readiness thresholds come from the guide's own text:
#   traffic light  GO: slept 7+ h, HR normal, no soreness
#                  CAUTION: slept 5-7 h, slightly elevated HR, moderate fatigue
#                  STOP: slept <5 h, elevated HR, illness or sharp pain
#   recovery dash  soreness self-rated 1-5: below 3 = modify, below 2 = rest day
_SIGNALS = [
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
_REC_WORD = ["GO", "CAUTION", "REST"]


def _mark(level_key: str) -> str:
    return f'<span class="{P}-mk {P}-mk--{level_key}" aria-hidden="true"></span>'


def _short(action: str) -> str:
    """First sentence of the guide's action text."""
    return action.split(". ")[0].rstrip(".")


def _call_head(word, mark_key, chip, when, extra="") -> str:
    return (
        f'<div class="gg-eg-read"><p class="gg-eg-main">'
        f'<span class="{P}-mk {P}-mk--{mark_key}" data-mk aria-hidden="true"></span>'
        f'<b class="gg-eg-num" data-eg-f="num">{_e(word)}</b>'
        f'<span class="gg-eg-chip" data-eg-f="chip">{_e(chip)}</span></p>'
        f'<p class="gg-eg-when" data-eg-f="when">{_e(when)}</p></div>'
        + (f'<div class="gg-eg-extra">{extra}</div>' if extra else "")
    )


def render_traffic_light(block: dict) -> str:
    rows = []
    for k, (key, word, label, criteria, action) in enumerate(_SIGNALS):
        on = " is-on" if k == 0 else ""
        rows.append(
            f'<li class="{P}-tl-row{on}" data-lv="{k}">{_mark(key)}'
            f'<div><p class="{P}-tl-word"><b>{_e(word)}</b><span>{_e(label)}</span></p>'
            f'<p><i>IF</i> {_e(criteria)}</p><p><i>THEN</i> {_e(action)}</p></div></li>'
        )

    def seg(name, label, opts):
        b = "".join(
            f'<button type="button" data-{name}="{i}" aria-pressed="{"true" if i == 0 else "false"}">{_e(o)}</button>'
            for i, o in enumerate(opts)
        )
        return f'<span class="gg-eg-seg" role="group" aria-label="{_e(label)}">{b}</span>'

    controls = (
        f'<label class="gg-eg-field {P}-wide">Sleep'
        f'<input type="range" class="{P}-rin" min="3" max="10" step="0.5" value="7.5" data-in="sleep" '
        f'aria-label="Hours slept"><output data-out="sleep">7.5 h</output></label>'
        + seg("hr", "Resting heart rate", ["HR normal", "Slightly up", "Elevated"])
        + seg("body", "How the body feels", ["Fresh", "Tired", "Ill or hurt"])
    )
    head = _call_head("GO", "go", _short(_SIGNALS[0][4]), "Today",
                      f'<span data-eg-f="then">{_e(_SIGNALS[0][4])}</span>')
    desc = ("Go, Caution, Stop. " + " ".join(f"{s[2]}: IF {s[3]}. THEN {s[4]}" for s in _SIGNALS))
    card = glyph.glyph_card(
        "Today's call", head, f'<ul class="{P}-tl">{"".join(rows)}</ul>',
        controls_html="", describedby="gg-eg-tl-d", description=desc,
        data={"then": [s[4] for s in _SIGNALS], "short": [_short(s[4]) for s in _SIGNALS],
              "word": [s[1] for s in _SIGNALS]},
    )
    # inputs live above the list; shown only when script runs (the call is fully static without it)
    card = card.replace(f'<div class="gg-eg-plotbox">', f'<div class="{P}-tl-in gg-eg-controls">{controls}</div><div class="gg-eg-plotbox">', 1)
    return _gpanel(block, "CH 4 · AUTOREGULATION", "The Go / Caution / No-Go Framework", card)


_REC = [
    # key, label, value, unit, min, max, step, tick, hint
    ("sleep", "Sleep", 7.2, "hrs avg", 3, 10, 0.1, 7, "Target 7+ hours"),
    ("hrv", "HRV", 65, "ms rMSSD", 20, 100, 1, 65, "Track trends, not one reading"),
    ("sore", "Muscle readiness", 3, "/5 soreness", 1, 5, 1, 3, "Below 3 modify, below 2 rest"),
]


def render_recovery_dash(block: dict) -> str:
    rows = []
    for key, label, v, unit, mn, mx, st, tick, hint in _REC:
        rows.append(
            f'<div class="{P}-rrow" data-row="{key}">'
            f'<div class="{P}-rtop"><span class="{P}-rname">{_e(label)}</span>'
            f'<span class="{P}-rval"><b data-v="{key}">{_e(_g(v))}</b><i>{_e(unit)}</i></span></div>'
            f'{glyph.meter(v, mx, tick)}'
            f'<p class="{P}-rhint">{_e(hint)}</p>'
            f'<input type="range" class="{P}-rin" min="{mn}" max="{mx}" step="{st}" value="{_g(v)}" '
            f'data-in="{key}" aria-label="{_e(label)}, {_e(unit)}"></div>'
        )
    head = _call_head("GO", "go", "Sleep and soreness on target", "This morning",
                      f'<span data-eg-f="then">{_e(_SIGNALS[0][4])}</span>')
    desc = (
        "Recovery dashboard. Sleep 7.2 hours average, target 7 or more hours. HRV 65 ms rMSSD, "
        "track trends not single readings. Muscle readiness 3 out of 5 soreness: below 3 modify the "
        "workout, below 2 rest day. Slept 5 to 7 hours is Caution; under 5 hours is Rest. "
        "Set the three readings to see the call."
    )
    card = glyph.glyph_card(
        "Recovery this morning", head, f'<div class="{P}-rrows">{"".join(rows)}</div>',
        describedby="gg-eg-rec-d", description=desc,
        data={"then": [s[4] for s in _SIGNALS], "word": _REC_WORD},
    )
    return _gpanel(block, "CH 4 · RECOVERY", "Recovery Dashboard: Three Metrics That Matter", card)


_SLEEP = [("Mon", 6.5), ("Tue", 5.5), ("Wed", 8.5), ("Thu", 6.0), ("Fri", 7.0), ("Sat", 9.0), ("Sun", 6.5)]
_SLEEP_NEED = 8.0


def _minus(v: float) -> str:
    return ("−" if v < 0 else "+" if v > 0 else "") + _g(abs(v))


def render_sleep_debt(block: dict) -> str:
    W, H, LO, HI = 700, 200, 4.0, 10.0
    need = _SLEEP_NEED
    n = len(_SLEEP)
    y = lambda v: H * (HI - min(HI, max(LO, v))) / (HI - LO)  # noqa: E731
    xs = [(i + 0.5) / n * W for i in range(n)]
    ys = [y(a) for _d, a in _SLEEP]
    debt = sum(need - a for _d, a in _SLEEP if a < need)
    surplus = sum(a - need for _d, a in _SLEEP if a > need)
    net = debt - surplus
    areas = "".join(
        f'<path class="{P}-eg-area {P}-eg-area--{"short" if s > 0 else "over"}" d="{d}"/>'
        for s, d in _areas(xs, ys, y(need))
    )
    svg = (
        f'<svg class="gg-eg-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">'
        f'<g data-areas>{areas}</g>'
        f'<line class="{P}-eg-ref" x1="0" x2="{W}" y1="{y(need):.1f}" y2="{y(need):.1f}" data-target/>'
        f'<path class="{P}-eg-case" d="{glyph.line_path(list(zip(xs, ys)))}" data-line-c/>'
        f'<path class="{P}-eg-hero" d="{glyph.line_path(list(zip(xs, ys)))}" data-line/></svg>'
    )
    dots = "".join(
        f'<i class="{P}-eg-dot" data-dot="{i}" style="left:{(i + 0.5) / n * 100:.2f}%;top:{ys[i] / H * 100:.1f}%"></i>'
        for i in range(n)
    )
    plot = (
        f'<div class="{P}-eg-plot {P}-eg-plot--sleep">{svg}{dots}'
        f'<span class="{P}-eg-yl" data-target-l style="top:{y(need) / H * 100:.1f}%">{_g(need)} h need</span>'
        f'<i class="gg-eg-pt" data-eg-pt style="display:none"></i></div>'
    )
    vt = f"{_SLEEP[0][0]}: {_g(_SLEEP[0][1])} h, {_minus(_SLEEP[0][1] - need)} h vs need"
    pw = glyph.scrub_wrap("ch4-sleep", plot, n, 0, "Scrub the seven nights", vt, mode="band")
    xl = "".join(
        f'<span>{_e(d)}<i data-dl="{i}" class="{P}-eg-d--{"short" if a < need else "over"}">'
        f'{_minus(a - need)}</i></span>'
        for i, (d, a) in enumerate(_SLEEP)
    )
    chip = f"{_g(debt)} h short · {_g(surplus)} h banked"
    head = glyph.readout(_g(net), "h debt", chip, "Race week")
    inputs = "".join(
        f'<label class="gg-eg-field {P}-nin">{_e(d)}<input type="number" inputmode="decimal" min="0" max="16" '
        f'step="0.5" value="{_g(a)}" data-h="{i}" aria-label="{_e(d)} hours slept"></label>'
        for i, (d, a) in enumerate(_SLEEP)
    )
    controls = (
        inputs + f'<label class="gg-eg-field {P}-nin">Need<input type="number" inputmode="decimal" min="4" '
        f'max="12" step="0.5" value="{_g(need)}" data-need aria-label="Hours needed per night"></label>'
    )
    desc = (
        "Hours slept each night in race week against a need of 8 hours: "
        + ", ".join(f"{d} {_g(a)}" for d, a in _SLEEP)
        + f". {_g(debt)} hours short on the short nights, {_g(surplus)} hours banked on the long nights, "
        f"net debt {_g(net)} hours."
    )
    card = glyph.glyph_card(
        "Sleep vs need", head,
        f'{pw}<div class="{P}-eg-xl {P}-eg-xl--7" aria-hidden="true">{xl}</div>',
        controls_html=controls,
        data={"h": [a for _d, a in _SLEEP], "days": [d for d, _a in _SLEEP], "need": need,
              "W": W, "H": H, "lo": LO, "hi": HI},
        describedby="gg-eg-sleep-d", description=desc,
    )
    return _gpanel(block, "CH 4 · SLEEP", "Sleep Debt: The Hidden Performance Killer", card)


# ── Chapter 5 ───────────────────────────────────────────────

_TIMELINE = [
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


def render_fueling_timeline(block: dict) -> str:
    items = []
    for k, (t, title, summary, detail) in enumerate(_TIMELINE):
        items.append(
            f'<li class="gg-ig-c-step">'
            f'<span class="gg-ig-c-steptime">{_e(t)}<span class="gg-ig-c-clock" data-clock="{k}"></span></span>'
            f'<span class="gg-ig-c-stepdot" aria-hidden="true"></span>'
            f'<div class="gg-ig-c-stepbody">'
            f'<strong>{_e(title)}</strong>'
            f'<span class="gg-ig-c-stepsum">{_e(summary)}</span>'
            f'<span class="gg-ig-c-stepdet">{_e(detail)}</span>'
            f'</div></li>'
        )
    start = (
        '<div class="gg-ig-c-field gg-ig-c-field--time">'
        '<label class="gg-ig-c-flabel" for="gg-ig-c-tl-start">Race start</label>'
        '<input type="time" id="gg-ig-c-tl-start" class="gg-ig-c-time" data-start>'
        '</div>'
    )
    body = (_stat("75", "g carbs / hr", "Start at minute 15-20, then every 20 minutes")
            + f'<div class="gg-ig-c-tl" data-timeline>{start}<ol class="gg-ig-c-steps">{"".join(items)}</ol></div>')
    return _panel("timeline", "dark", "CH 5 · RACE DAY",
                  "Race Day Fueling: Hour by Hour", body, block.get("caption", ""))


_GEL_G = 25  # grams of carbohydrate per gel: round-1 pairs 600 g with 24 gels


def render_bonk_math(block: dict) -> str:
    hours, rate = 8, 75
    total = hours * rate
    gels_n = -(-total // _GEL_G)
    gels = "".join(f'<span class="gg-ig-c-gel" aria-hidden="true">{i}</span>' for i in range(1, gels_n + 1))

    def field(key, label, mn, mx, val, step, shown):
        fid = f"gg-ig-c-bm-{key}"
        return (
            f'<div class="gg-ig-c-field">'
            f'<label class="gg-ig-c-flabel" for="{fid}">{_e(label)}</label>'
            f'<input type="range" id="{fid}" class="gg-ig-c-slider" data-in="{key}" min="{mn}" max="{mx}" '
            f'value="{val}" step="{step}">'
            f'<output class="gg-ig-c-fval" for="{fid}" data-val="{key}">{_e(shown)}</output></div>'
        )

    fields = (field("hours", "Race Hours", 1, 12, hours, 0.5, f"{hours} hrs")
              + field("rate", "Carbs / hr", 30, 120, rate, 5, f"{rate} g"))
    hero = (
        '<div class="gg-ig-c-hero gg-ig-c-hero--eq" aria-live="polite">'
        f'<span class="gg-ig-c-big" data-out="eq">{hours} &times; {rate}g = {total}g</span>'
        f'<span class="gg-ig-c-note" data-out="note">{hours} hours &times; {rate}g carbs/hr = {total}g total carbohydrate</span>'
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
        f'<div class="gg-ig-c-gels" data-gels>{gels}</div>'
        f'<p class="gg-ig-c-gelnote" aria-live="polite"><strong data-out="gels">= {gels_n} gels</strong> '
        f'(or equivalent, {_GEL_G}g each)</p>'
    )
    body = f'<div class="gg-ig-c-bonk"><div class="gg-ig-c-fields">{fields}</div>{hero}{tiles}{grid}</div>'
    return _panel("bonk", "light", "CH 5 · FUEL MATH",
                  "The Math Behind the Bonk", body, block.get("caption", ""))


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
        '<div class="gg-ig-c-res"><span class="gg-ig-c-kicker">Sodium / hr</span>'
        '<span class="gg-ig-c-resnum" data-out="sodium">750 mg</span>'
        '<span class="gg-ig-c-ressub" data-out="sodiumtotal">4,500 mg total</span></div>'
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


# Glycogen model (the chart's own): unfed and 75 g/hr curves are the round-1 points; the fed
# curve at any other rate scales linearly between them: fed(c) = unfed + c/75 * (fed75 - unfed),
# kept inside 0-100%. At 0 g/hr it equals unfed, at 75 g/hr it equals the round-1 curve.
_GLY_UNFED = [(0, 100), (2, 65), (4, 25), (6, 5)]
_GLY_FED = [(0, 100), (2, 80), (4, 55), (6, 35)]
_GLY_RATE = 75
_GLY_W, _GLY_H = 600, 220


def render_glycogen_gauge(block: dict) -> str:
    W, H = _GLY_W, _GLY_H
    px = lambda h: h / 6 * W  # noqa: E731
    py = lambda v: H * (1 - v / 100)  # noqa: E731
    un = [(px(h), py(v)) for h, v in _GLY_UNFED]
    fd = [(px(h), py(v)) for h, v in _GLY_FED]
    band = glyph.line_path(fd + un[::-1], close=True)
    refs = "".join(
        f'<line class="{P}-eg-ref" x1="0" x2="{W}" y1="{py(v):.1f}" y2="{py(v):.1f}"/>' for v in (0, 50, 100)
    )
    svg = (
        f'<svg class="gg-eg-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">'
        f'{refs}<path class="{P}-eg-area {P}-eg-area--over" d="{band}" data-band/>'
        f'<path class="{P}-eg-sec" d="{glyph.line_path(un)}"/>'
        f'<path class="{P}-eg-case" d="{glyph.line_path(fd)}" data-fed-c/>'
        f'<path class="{P}-eg-hero" d="{glyph.line_path(fd)}" data-fed/></svg>'
    )
    plot = (
        f'<div class="{P}-eg-plot">{svg}{_yl("100", 0, True)}{_yl("50", 50)}{_yl("0", 100)}'
        f'<i class="gg-eg-pt" data-eg-pt style="left:100%;top:{100 - _GLY_FED[-1][1]}%"></i></div>'
    )
    vt = f"Hour 6: {_GLY_FED[-1][1]}% left with {_GLY_RATE} g per hour, {_GLY_UNFED[-1][1]}% without"
    pw = glyph.scrub_wrap("ch5-glyco", plot, 7, 6, "Scrub hours 0 to 6", vt, mode="point")
    ends = (
        f'<div class="{P}-eg-ends"><div data-end="fed" style="top:{100 - _GLY_FED[-1][1]}%">'
        f'{glyph.capsule(f"{_GLY_FED[-1][1]}%", "Fed", "ink", "dotted")}</div>'
        f'<div data-end="un" style="top:{100 - _GLY_UNFED[-1][1]}%">'
        f'{glyph.capsule(f"{_GLY_UNFED[-1][1]}%", "Unfed", "pink", "dotted")}</div></div>'
    )
    xl = "".join(f'<span>{"Start" if h == 0 else f"Hr {h}"}</span>' for h in range(0, 7, 2))
    chip = f"+{_GLY_FED[-1][1] - _GLY_UNFED[-1][1]} vs unfed"
    extra = glyph.capsule(f"{_GLY_UNFED[-1][1]}%", "Unfed", "pink", field="unf") + f'<span data-eg-f="note">at {_GLY_RATE} g/hr</span>'
    head = glyph.readout(f"{_GLY_FED[-1][1]}", "% left", chip, "Hour 6", extra)
    controls = (
        f'<label class="gg-eg-field {P}-wide">Carbs per hour'
        f'<input type="range" class="{P}-rin" min="0" max="120" step="5" value="{_GLY_RATE}" data-rate '
        f'aria-label="Carbohydrate intake in grams per hour"><output data-rate-out>{_GLY_RATE} g</output></label>'
    )
    desc = (
        "Glycogen remaining over a six hour ride. Without fueling: "
        + ", ".join(f"{'start' if h == 0 else f'hour {h}'} {v}%" for h, v in _GLY_UNFED)
        + ". Glycogen depleted by hour 4, bonk inevitable. With 75 g per hour: "
        + ", ".join(f"{'start' if h == 0 else f'hour {h}'} {v}%" for h, v in _GLY_FED)
        + ". Steady depletion but manageable. Other rates scale linearly between the two curves."
    )
    card = glyph.glyph_card(
        "Glycogen left", head,
        f'<div class="{P}-eg-wrap {P}-eg-wrap--g">{pw}{ends}</div>'
        f'<div class="{P}-eg-xl {P}-eg-xl--gly {P}-eg-xl--pr" aria-hidden="true">{xl}</div>',
        controls_html=controls,
        data={"un": _GLY_UNFED, "fed": _GLY_FED, "base": _GLY_RATE, "W": W, "H": H},
        describedby="gg-eg-gly-d", description=desc,
    )
    return _gpanel(block, "CH 5 · GLYCOGEN", "Glycogen Depletion: Fed vs. Unfed", card)


# Daily macro ranges as the guide gives them. Grams per day use only the guide's g/kg figures
# (carbs 6-10, protein 1.6-2.2); fat has no g/kg range in the text, so it stays a percent.
_MACROS = [
    ("carb", "Carbohydrates", "55-65%", 60,
     "Primary fuel source. 6-10g/kg body weight on training days.", (6, 10)),
    ("protein", "Protein", "15-20%", 18,
     "Muscle repair and adaptation. 1.6-2.2g/kg. Spread across meals.", (1.6, 2.2)),
    ("fat", "Fat", "20-30%", 22,
     "Essential for hormones and long-effort fat oxidation.", None),
]
_MACRO_KG = 70


def _grams(rng, kg) -> str:
    if not rng:
        return "No g/kg range given"
    return f"{round(rng[0] * kg):,}-{round(rng[1] * kg):,} g a day"


def render_macro_split(block: dict) -> str:
    segs = "".join(
        f'<span class="gg-ig-c-seg gg-ig-c-seg--{k}" style="--w:{pct}%"></span>'
        for k, _n, _r, pct, _t, _g_ in _MACROS
    )
    rows = "".join(
        f'<div class="gg-ig-c-macro">'
        f'<span class="gg-ig-c-swatch gg-ig-c-swatch--{k}" aria-hidden="true"></span>'
        f'<span class="gg-ig-c-macroname">{_e(n)}</span>'
        f'<span class="gg-ig-c-macrorange">{_e(r)}</span>'
        f'<p class="gg-ig-c-macrog" data-g="{k}">{_e(_grams(g, _MACRO_KG))}</p>'
        f'<p class="gg-ig-c-macrotip">{_e(t)}</p></div>'
        for k, n, r, _p, t, g in _MACROS
    )
    weight = (
        '<div class="gg-ig-c-wt">'
        '<label class="gg-ig-c-flabel" for="gg-ig-c-ms-wt">Body weight</label>'
        f'<input type="number" id="gg-ig-c-ms-wt" class="gg-ig-c-num" inputmode="decimal" min="30" max="200" '
        f'step="0.5" value="{_MACRO_KG}" data-wt>'
        '<span class="gg-ig-c-unitseg" role="group" aria-label="Weight unit">'
        '<button type="button" data-unit="kg" aria-pressed="true">kg</button>'
        '<button type="button" data-unit="lb" aria-pressed="false">lb</button></span></div>'
    )
    body = (_stat("55-65", "% carbs", "Carbs are the primary fuel for gravel")
            + f'<div class="gg-ig-c-stack" aria-hidden="true">{segs}</div>'
            + f'<div class="gg-ig-c-macwrap" data-macros>{weight}<div class="gg-ig-c-macros">{rows}</div></div>')
    return _panel("macro", "dark", "CH 5 · NUTRITION",
                  "Daily Macro Split for Endurance Athletes", body, block.get("caption", ""))


_CAL = [("Hr 1", 700, 700), ("Hr 2", 650, 1350), ("Hr 3", 600, 1950), ("Hr 4", 580, 2530),
        ("Hr 5", 550, 3080), ("Hr 6", 520, 3600), ("Hr 7", 500, 4100), ("Hr 8", 480, 4580)]
_CAL_FOOD = 2400  # the round-1 note: only ~2,400 cal can be absorbed from food


def render_calorie_burn(block: dict) -> str:
    W, H, YMAX, BMAX = 640, 220, 4600, 750
    n = len(_CAL)
    slot = W / n
    bars = []
    for i, (_l, cal, _c) in enumerate(_CAL):
        h = cal / BMAX * H * 0.42
        bars.append(
            f'<rect class="{P}-eg-cb{" is-on" if i == n - 1 else ""}" data-bar="{i}" x="{i * slot + 12:.1f}" '
            f'y="{H - h:.1f}" width="{slot - 24:.1f}" height="{h:.1f}"/>'
        )
    pts = [((i + 0.5) * slot, H * (1 - c / YMAX)) for i, (_l, _a, c) in enumerate(_CAL)]
    food_y = H * (1 - _CAL_FOOD / YMAX)
    svg = (
        f'<svg class="gg-eg-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">'
        f'<line class="{P}-eg-ref" x1="0" x2="{W}" y1="{H}" y2="{H}"/>'
        f'<line class="{P}-eg-ref {P}-eg-ref--food" x1="0" x2="{W}" y1="{food_y:.1f}" y2="{food_y:.1f}"/>'
        f'{"".join(bars)}'
        f'<path class="{P}-eg-case" d="{glyph.line_path(pts)}"/>'
        f'<path class="{P}-eg-hero" d="{glyph.line_path(pts)}"/></svg>'
    )
    last = _CAL[-1]
    plot = (
        f'<div class="{P}-eg-plot">{svg}'
        f'<i class="gg-eg-pt" data-eg-pt style="left:{(n - 0.5) / n * 100:.2f}%;top:{(1 - last[2] / YMAX) * 100:.1f}%"></i></div>'
    )
    vt = f"{last[0]}: {_fmt(last[1])} cal burned, {_fmt(last[2])} total"
    pw = glyph.scrub_wrap("ch5-cal", plot, n, n - 1, "Scrub the eight hours", vt, mode="band")
    ends = (
        f'<div class="{P}-eg-ends"><div style="top:{(1 - last[2] / YMAX) * 100:.1f}%">'
        f'{glyph.capsule(_fmt(last[2]), "Burned", "ink", "dotted")}</div>'
        f'<div style="top:{food_y / H * 100:.1f}%">{glyph.capsule(_fmt(_CAL_FOOD), "Food", "teal", "dotted")}</div></div>'
    )
    xl = "".join(f'<span><i class="{P}-hr">Hr </i>{_e(l[3:])}</span>' for l, _a, _c in _CAL)
    deficit = max(0, last[2] - _CAL_FOOD)
    extra = (glyph.capsule(_fmt(deficit), "Deficit", "pink", field="def")
             + '<span>only ~2,400 cal can be absorbed from food</span>')
    head = glyph.readout(_fmt(last[2]), "cal", f"+{_fmt(last[1])} this hour", f"Hour {n}", extra)
    desc = (
        "Calories burned over an 8-hour race, hour by hour with the running total: "
        + ", ".join(f"{l} {_fmt(a)} burned, {_fmt(c)} total" for l, a, c in _CAL)
        + ". Only about 2,400 calories can be absorbed from food."
    )
    card = glyph.glyph_card(
        "Calories burned", head,
        f'<div class="{P}-eg-wrap {P}-eg-wrap--g">{pw}{ends}</div>'
        f'<div class="{P}-eg-xl {P}-eg-xl--8 {P}-eg-xl--pr" aria-hidden="true">{xl}</div>',
        data={"cal": [a for _l, a, _c in _CAL], "cum": [c for _l, _a, c in _CAL], "food": _CAL_FOOD, "ymax": YMAX},
        describedby="gg-eg-cal-d", description=desc,
    )
    return _gpanel(block, "CH 5 · ENERGY", "Calorie Burn by Hour: The Energy Deficit", card)


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
.gg-ig-c-k-eg .gg-ig-c-body{padding:20px 20px 22px}
.gg-ig-c--dark .gg-ig-c-body{background:var(--gg-color-dark-brown);color:var(--gg-color-warm-paper)}
.gg-ig-c .gg-ig-c-cap{margin:32px 0 0;padding:6px 0 6px 18px;border-left:6px solid var(--gg-color-light-gold);font-family:var(--gg-font-editorial);font-style:italic;font-size:16px;line-height:1.5;color:inherit}
.gg-ig-c-k-eg .gg-ig-c-cap{margin-top:20px}
.gg-ig-c-body p{margin:0;color:inherit;font-size:inherit;line-height:inherit}

/* loud number */
.gg-ig-c-hero{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 16px;margin:0 0 28px}
.gg-ig-c-big{font-family:var(--gg-font-data);font-weight:700;font-size:clamp(52px,12vw,88px);line-height:.95;letter-spacing:-2px;font-variant-numeric:tabular-nums;color:var(--gg-color-dark-brown)}
.gg-ig-c--dark .gg-ig-c-big{color:var(--gg-color-light-gold)}
.gg-ig-c--light .gg-ig-c-hero{background:var(--gg-color-light-gold);border:3px solid var(--gg-color-dark-brown);padding:18px 20px}
.gg-ig-c--light .gg-ig-c-hero .gg-ig-c-big{color:var(--gg-color-dark-brown)}
.gg-ig-c-unit{font-family:var(--gg-font-data);font-size:18px;font-weight:700;letter-spacing:2px;text-transform:uppercase}
.gg-ig-c-note{flex-basis:100%;font-size:16px;line-height:1.45}
.gg-ig-c-kicker{display:block;font-family:var(--gg-font-data);font-size:14px;font-weight:700;letter-spacing:2px;text-transform:uppercase}
.gg-ig-c--dark .gg-ig-c-kicker{color:var(--gg-color-tan)}
.gg-ig-c-hero--eq .gg-ig-c-big{font-size:clamp(34px,7.4vw,72px);letter-spacing:-1px;white-space:nowrap}

/* Glyph plots (SVG paths are classed; var() lives here, never in attributes) */
.gg-ig-c-eg-plot{position:relative;height:200px}
.gg-ig-c-eg-plot--sleep{height:200px}
.gg-ig-c-eg-wrap{position:relative}
.gg-ig-c-eg-wrap--g{padding-right:112px}
.gg-ig-c-eg-ref{stroke:var(--eg-none);stroke-width:1;vector-effect:non-scaling-stroke}
.gg-ig-c-eg-ref--food{stroke-dasharray:4 3}
.gg-ig-c-eg-yl{position:absolute;left:2px;transform:translateY(-100%);font-family:var(--eg-mono);font-size:11px;color:var(--eg-ink3);text-shadow:0 0 3px var(--eg-card),0 0 3px var(--eg-card)}
.gg-ig-c-eg-yl--top{transform:translateY(3px)}
.gg-ig-c-eg-case{fill:none;stroke:var(--eg-card);stroke-width:6.25;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}
.gg-ig-c-eg-hero{fill:none;stroke:var(--eg-ink);stroke-width:2.75;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}
.gg-ig-c-eg-sec{fill:none;stroke:var(--eg-fat);stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}
.gg-ig-c-eg-area{stroke:none}
.gg-ig-c-eg-area--short{fill:color-mix(in srgb,var(--eg-fat) 16%,var(--eg-card))}
.gg-ig-c-eg-area--over{fill:color-mix(in srgb,var(--eg-form) 16%,var(--eg-card))}
.gg-ig-c-eg-done{fill:var(--eg-ink)}
.gg-ig-c-eg-planbox{fill:none;stroke:var(--eg-ink);stroke-width:2;stroke-dasharray:0 5;stroke-linecap:round;vector-effect:non-scaling-stroke}
.gg-ig-c-eg-dev{fill:color-mix(in srgb,var(--eg-fat) 16%,var(--eg-card));stroke:none}
.gg-ig-c-eg-bar{transition:opacity .15s}
.gg-ig-c-eg-cb{fill:var(--eg-none)}
.gg-ig-c-eg-cb.is-on{fill:var(--eg-ink2)}
.gg-ig-c-eg-dot{position:absolute;width:10px;height:10px;margin:-5px 0 0 -5px;border-radius:50%!important;background:var(--eg-ink);box-shadow:0 0 0 2px var(--eg-card);pointer-events:none}
.gg-ig-c-eg-ends{position:absolute;right:0;top:0;width:108px;height:200px}
.gg-ig-c-eg-ends>div{position:absolute;left:8px;transform:translateY(-50%)}
.gg-ig-c-eg-xl{display:grid;margin-top:6px;font-family:var(--eg-mono);font-size:11px;color:var(--eg-ink3);text-align:center}
.gg-ig-c-eg-xl--6{grid-template-columns:repeat(6,minmax(0,1fr))}
.gg-ig-c-eg-xl--7{grid-template-columns:repeat(7,minmax(0,1fr))}
.gg-ig-c-eg-xl--8{grid-template-columns:repeat(8,minmax(0,1fr))}
.gg-ig-c-eg-xl--gly{display:flex;justify-content:space-between}
.gg-ig-c-eg-xl--pr{padding-right:112px}
.gg-ig-c-eg-xl i{display:block;font-style:normal;font-weight:700}
.gg-ig-c-eg-d--short{color:var(--eg-fat)}
.gg-ig-c-eg-d--over{color:var(--eg-form)}
.gg-ig-c-k-eg .gg-eg[data-grp="chased"] .gg-ig-c-eg-bar[data-g="steady"],.gg-ig-c-k-eg .gg-eg[data-grp="steady"] .gg-ig-c-eg-bar[data-g="chased"]{opacity:.4}
.gg-ig-c-k-eg .gg-eg[data-grp="chased"] .gg-ig-c-eg-xl span[data-g="steady"],.gg-ig-c-k-eg .gg-eg[data-grp="steady"] .gg-ig-c-eg-xl span[data-g="chased"]{opacity:.45}
.gg-ig-c-k-eg .gg-eg-pw[data-eg-scrub="ch4-gap"]{height:200px}

/* readiness marks: GO dot, CAUTION ring, REST square (shape, not colour) */
.gg-ig-c-k-eg .gg-eg-chip{white-space:normal;line-height:1.3}
.gg-ig-c-mk{display:inline-block;width:18px;height:18px;align-self:center;flex:none}
.gg-ig-c-mk--go{border-radius:50%!important;background:var(--eg-ink)}
.gg-ig-c-mk--caution{border-radius:50%!important;border:3px solid var(--eg-ink);background:transparent}
.gg-ig-c-mk--stop,.gg-ig-c-mk--rest{border-radius:2px!important;background:var(--eg-ink)}
.gg-ig-c-tl{list-style:none;margin:0;padding:0;display:grid;gap:8px}
.gg-ig-c-tl-row{display:flex;gap:12px;align-items:flex-start;padding:10px 12px;border-radius:8px!important;box-shadow:inset 0 0 0 1px var(--eg-line)!important;opacity:.62;margin:0}
.gg-ig-c-tl-row.is-on{opacity:1;background:var(--eg-paper);box-shadow:inset 0 0 0 2px var(--eg-ink)!important}
.gg-ig-c-tl-row .gg-ig-c-mk{margin-top:3px}
.gg-ig-c-tl-row p{font-size:13px;line-height:1.4;color:var(--eg-ink2);margin:2px 0 0}
.gg-ig-c-tl-row p i{font-family:var(--eg-mono);font-style:normal;font-weight:700;font-size:11px;color:var(--eg-ink3);margin-right:4px}
.gg-ig-c-tl-word{display:flex;flex-wrap:wrap;gap:2px 10px;align-items:baseline;margin:0}
.gg-ig-c-tl-word b{font-family:var(--eg-mono);font-weight:800;font-size:14px;color:var(--eg-ink)}
.gg-ig-c-tl-word span{font-family:var(--eg-mono);font-size:11px;color:var(--eg-ink3)}
.gg-ig-c-tl-in{margin:12px 0 0}
.gg-ig-c-rrows{display:grid;gap:14px}
.gg-ig-c-rrow{display:grid;gap:6px}
.gg-ig-c-rtop{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.gg-ig-c-rname{font-weight:600;font-size:13px;color:var(--eg-ink2)}
.gg-ig-c-rval b{font-family:var(--eg-mono);font-weight:800;font-size:20px;font-variant-numeric:tabular-nums;color:var(--eg-ink)}
.gg-ig-c-rval i{font-family:var(--eg-mono);font-style:normal;font-size:11px;color:var(--eg-ink3);margin-left:6px}
.gg-ig-c-rhint{font-family:var(--eg-mono);font-size:11px;color:var(--eg-ink3)}
.gg-ig-c-rin{width:100%;min-height:44px;margin:0;accent-color:var(--eg-cobalt);cursor:pointer}
.gg-ig-c-k-eg .gg-eg:not(.is-live) .gg-ig-c-rin,.gg-ig-c-k-eg .gg-eg:not(.is-live) .gg-ig-c-tl-in{display:none}
.gg-ig-c-k-eg .gg-eg .gg-ig-c-wide{flex:1 1 220px}
.gg-ig-c-k-eg .gg-eg .gg-ig-c-wide .gg-ig-c-rin{flex:1;min-width:120px}
.gg-ig-c-k-eg .gg-eg .gg-ig-c-nin input{width:64px}
.gg-ig-c-k-eg .gg-eg .gg-eg-field output{white-space:nowrap}

/* fueling timeline */
.gg-ig-c-steps{list-style:none;margin:0;padding:0;position:relative}
.gg-ig-c-steps::before{content:"";position:absolute;top:14px;bottom:14px;left:190px;width:6px;background:var(--gg-color-secondary-brown);transform:translateX(-50%)}
.gg-ig-c-step{display:grid;grid-template-columns:160px 60px minmax(0,1fr);align-items:start;padding:0 0 26px;margin:0;position:relative}
.gg-ig-c-step:last-child{padding-bottom:0}
.gg-ig-c-steptime{font-family:var(--gg-font-data);font-size:18px;font-weight:700;color:var(--gg-color-light-gold);text-align:right;padding-top:1px}
.gg-ig-c-clock{display:block;font-size:15px;color:var(--gg-color-white);font-variant-numeric:tabular-nums}
.gg-ig-c-clock:empty{display:none}
.gg-ig-c-stepdot{width:26px;height:26px;background:var(--gg-color-light-gold);border:4px solid var(--gg-color-dark-brown);outline:3px solid var(--gg-color-light-gold);justify-self:center;margin-top:0;position:relative}
.gg-ig-c-stepbody{display:flex;flex-direction:column;gap:4px;min-width:0}
.gg-ig-c-stepbody strong{font-size:24px;line-height:1.2;color:var(--gg-color-white)}
.gg-ig-c-stepsum{font-size:18px;line-height:1.4;color:var(--gg-color-warm-paper);font-weight:600}
.gg-ig-c-stepdet{font-size:16px;line-height:1.5;color:var(--gg-color-sand)}
.gg-ig-c-field--time{margin:0 0 24px}
.gg-ig-c-time,.gg-ig-c-num{font-family:var(--gg-font-data);font-size:20px;font-weight:700;min-height:48px;padding:0 12px;border:3px solid var(--gg-color-tan);background:var(--gg-color-near-black);color:var(--gg-color-light-gold);border-radius:0;margin:0}
.gg-ig-c-time:focus-visible,.gg-ig-c-num:focus-visible,.gg-ig-c-unitseg button:focus-visible{outline:3px solid var(--gg-color-light-teal);outline-offset:2px}
.gg-ig-c-time[aria-invalid="true"],.gg-ig-c-num[aria-invalid="true"]{border-color:var(--gg-color-error)}

/* paired stat tiles, gels (bonk math) */
.gg-ig-c-pair{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:0 0 24px}
.gg-ig-c-tile{border:3px solid var(--gg-color-dark-brown);background:var(--gg-color-white);padding:16px 18px;display:flex;flex-direction:column;gap:6px;min-width:0}
.gg-ig-c-tilenum{font-family:var(--gg-font-data);font-size:clamp(40px,9vw,64px);font-weight:700;line-height:1;letter-spacing:-1px;font-variant-numeric:tabular-nums}
.gg-ig-c-tilelab{font-size:16px;line-height:1.35}
.gg-ig-c-tile--hot{background:var(--gg-color-dark-brown);color:var(--gg-color-warm-paper)}
.gg-ig-c-tile--hot .gg-ig-c-tilenum{color:var(--gg-color-light-gold)}
.gg-ig-c-gels{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:6px}
.gg-ig-c-gel{aspect-ratio:1/1.1;background:var(--gg-color-dark-brown);color:var(--gg-color-light-gold);display:flex;align-items:center;justify-content:center;font-family:var(--gg-font-data);font-size:14px;font-weight:700;border-bottom:6px solid var(--gg-color-light-gold)}
.gg-ig-c .gg-ig-c-gelnote{margin-top:12px;font-size:18px}

/* sliders: hydration, bonk math */
.gg-ig-c-fields{display:grid;gap:8px;margin:0 0 24px}
.gg-ig-c-field{display:grid;grid-template-columns:170px minmax(0,1fr) 90px;gap:16px;align-items:center;min-height:52px}
.gg-ig-c-flabel{font-family:var(--gg-font-data);font-size:15px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--gg-color-warm-paper)}
.gg-ig-c--light .gg-ig-c-flabel{color:var(--gg-color-dark-brown)}
.gg-ig-c-fval{font-family:var(--gg-font-data);font-size:20px;font-weight:700;color:var(--gg-color-light-gold);font-variant-numeric:tabular-nums;white-space:nowrap}
.gg-ig-c--light .gg-ig-c-fval{color:var(--gg-color-dark-brown)}
.gg-ig-c-slider{-webkit-appearance:none;appearance:none;width:100%;height:44px;background:transparent;margin:0;cursor:pointer}
.gg-ig-c-slider::-webkit-slider-runnable-track{height:14px;background:var(--gg-color-near-black);border:3px solid var(--gg-color-tan)}
.gg-ig-c-slider::-moz-range-track{height:8px;background:var(--gg-color-near-black);border:3px solid var(--gg-color-tan)}
.gg-ig-c-slider::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:28px;height:44px;margin-top:-17px;background:var(--gg-color-light-gold);border:3px solid var(--gg-color-near-black);border-radius:0}
.gg-ig-c-slider::-moz-range-thumb{width:22px;height:38px;background:var(--gg-color-light-gold);border:3px solid var(--gg-color-near-black);border-radius:0}
.gg-ig-c-slider:focus-visible{outline:3px solid var(--gg-color-light-teal);outline-offset:2px}
.gg-ig-c-results{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.gg-ig-c-res{border:3px solid var(--gg-color-secondary-brown);padding:14px 16px;display:flex;flex-direction:column;gap:6px;min-width:0}
.gg-ig-c-resnum{font-family:var(--gg-font-data);font-size:clamp(24px,5vw,34px);font-weight:700;color:var(--gg-color-white);font-variant-numeric:tabular-nums}
.gg-ig-c-ressub{font-family:var(--gg-font-data);font-size:14px;font-weight:700;color:var(--gg-color-tan);font-variant-numeric:tabular-nums}

/* macro split */
.gg-ig-c-stack{display:flex;height:56px;border:3px solid var(--gg-color-warm-paper);margin:0 0 24px}
.gg-ig-c-seg{display:block;width:var(--w);height:100%}
.gg-ig-c-seg--carb{background:var(--gg-color-light-gold)}
.gg-ig-c-seg--protein{background:var(--gg-color-white);border-left:3px solid var(--gg-color-dark-brown);border-right:3px solid var(--gg-color-dark-brown)}
.gg-ig-c-seg--fat{background:var(--gg-color-secondary-brown)}
.gg-ig-c-swatch{flex:0 0 22px;width:22px;height:22px;margin-top:3px;border:3px solid var(--gg-color-warm-paper)}
.gg-ig-c-swatch--carb{background:var(--gg-color-light-gold)}
.gg-ig-c-swatch--protein{background:var(--gg-color-white)}
.gg-ig-c-swatch--fat{background:var(--gg-color-secondary-brown)}
.gg-ig-c-wt{display:flex;flex-wrap:wrap;align-items:center;gap:10px 14px;margin:0 0 24px}
.gg-ig-c-num{width:120px;text-align:right}
.gg-ig-c-unitseg{display:inline-flex;border:3px solid var(--gg-color-tan)}
.gg-ig-c-unitseg button{appearance:none;border:0;border-radius:0;margin:0;min-height:42px;min-width:56px;background:transparent;color:var(--gg-color-warm-paper);font-family:var(--gg-font-data);font-size:16px;font-weight:700;cursor:pointer}
.gg-ig-c-unitseg button[aria-pressed="true"]{background:var(--gg-color-light-gold);color:var(--gg-color-near-black)}
.gg-ig-c-macros{display:grid;gap:18px}
.gg-ig-c-macro{display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:4px 14px;align-items:baseline}
.gg-ig-c-macro .gg-ig-c-swatch{align-self:center;margin-top:0}
.gg-ig-c-macroname{font-size:22px;font-weight:700;color:var(--gg-color-white)}
.gg-ig-c-macrorange{font-family:var(--gg-font-data);font-size:24px;font-weight:700;color:var(--gg-color-light-gold)}
.gg-ig-c .gg-ig-c-macrog{grid-column:2 / -1;font-family:var(--gg-font-data);font-size:20px;font-weight:700;color:var(--gg-color-white);font-variant-numeric:tabular-nums}
.gg-ig-c .gg-ig-c-macrotip{grid-column:2 / -1;font-size:16px;line-height:1.45;color:var(--gg-color-sand)}
.gg-ig-c-macwrap:not(.is-live) .gg-ig-c-wt{display:none}

@media (max-width:720px){
.gg-ig-c-head{padding:16px 16px 18px}
.gg-ig-c .gg-ig-c-title{font-size:26px}
.gg-ig-c-body{padding:20px 16px 18px}
.gg-ig-c-k-eg .gg-ig-c-body{padding:12px 10px 16px}
.gg-ig-c-results{grid-template-columns:1fr}
.gg-ig-c-res{flex-direction:row;flex-wrap:wrap;align-items:baseline;justify-content:space-between}
.gg-ig-c-steps::before{left:13px}
.gg-ig-c-step{grid-template-columns:26px minmax(0,1fr);gap:0 16px;padding-bottom:24px}
.gg-ig-c-steptime{grid-column:2;grid-row:1;text-align:left;padding:0 0 6px}
.gg-ig-c-clock{display:inline;margin-left:10px}
.gg-ig-c-stepdot{grid-column:1;grid-row:1 / span 2}
.gg-ig-c-stepbody{grid-column:2;grid-row:2}
.gg-ig-c-field{grid-template-columns:minmax(0,1fr) auto;gap:0 12px}
.gg-ig-c-slider{grid-column:1 / -1;grid-row:2}
.gg-ig-c-gels{grid-template-columns:repeat(6,minmax(0,1fr))}
.gg-ig-c-macro{grid-template-columns:22px minmax(0,1fr)}
.gg-ig-c-macrorange{grid-column:2;grid-row:2}
.gg-ig-c .gg-ig-c-macrog{grid-column:2;grid-row:3}
.gg-ig-c .gg-ig-c-macrotip{grid-column:2;grid-row:4}
.gg-ig-c-pair{gap:10px}
.gg-ig-c-pair--wide{grid-template-columns:1fr}
.gg-ig-c-tile{padding:12px}
.gg-ig-c-hero--eq .gg-ig-c-big{white-space:normal}
.gg-ig-c-eg-wrap--g{padding-right:52px}
.gg-ig-c-eg-ends{width:48px}
.gg-ig-c-eg-xl--pr{padding-right:52px}
.gg-ig-c-eg-ends>div{left:4px}
.gg-ig-c-eg-ends .gg-eg-capl{display:none}
.gg-ig-c-eg-xl{font-size:10px}
.gg-ig-c-eg-xl i.gg-ig-c-hr{display:none}
.gg-ig-c-eg-plot{height:170px}
.gg-ig-c-k-eg .gg-eg-pw[data-eg-scrub="ch4-gap"]{height:170px}
}
"""


JS = r"""
/* Chapter 4-5 charts */
(function () {
  function comma(n) { return Math.round(n).toLocaleString("en-US"); }
  function trim(v, d) { return String(parseFloat(v.toFixed(d))); }
  function minus(v, d) { return (v < 0 ? "−" : v > 0 ? "+" : "") + trim(Math.abs(v), d); }
  function press(btns, pick) {
    for (var k = 0; k < btns.length; k++) btns[k].setAttribute("aria-pressed", pick(btns[k]) ? "true" : "false");
  }
  function setW(el, v) { if (el) el.style.width = v + "%"; }

  /* execution gap */
  GGEG.register("ch4-gap", function (i, c) {
    var d = c.data, st = c.state, pt = c.q("[data-eg-pt]");
    var a = d.act[i], vs = a - d.plan;
    if (!c.scrubbing) {
      var t = d.gt[st.grp];
      c.set("num", t[0]); c.set("unit", "% FTP"); c.set("chip", t[1]); c.set("when", t[2]); c.set("note", t[3]);
      if (pt) pt.style.display = "none";
    } else {
      c.set("num", String(a)); c.set("unit", "% FTP");
      c.set("chip", vs === 0 ? "on plan" : minus(vs, 0) + " vs plan");
      c.set("when", d.lab[i] + " · " + (d.grp[i] === "chased" ? "chased" : "steady"));
      c.set("note", vs === 0 ? "On plan" : Math.abs(vs) + (vs < 0 ? " under plan" : " over plan"));
      if (pt) {
        pt.style.display = "";
        pt.style.left = ((i + 0.5) / c.n * 100) + "%";
        pt.style.top = ((1 - a / d.ymax) * 100) + "%";
      }
    }
    return d.lab[i] + ": " + a + "% FTP, " + (vs === 0 ? "on plan" : Math.abs(vs) + (vs < 0 ? " under" : " over") + " plan");
  }, function (c) {
    var st = c.state;
    st.grp = "chased";
    c.card.setAttribute("data-grp", st.grp);
    var btns = c.card.querySelectorAll("[data-grp]");
    var seg = [];
    for (var k = 0; k < btns.length; k++) if (btns[k].tagName === "BUTTON") seg.push(btns[k]);
    for (k = 0; k < seg.length; k++) {
      seg[k].addEventListener("click", function (e) {
        st.grp = e.currentTarget.getAttribute("data-grp");
        c.card.setAttribute("data-grp", st.grp);
        press(seg, function (b) { return b.getAttribute("data-grp") === st.grp; });
        c.refresh();
      });
    }
  });

  /* sleep debt */
  GGEG.register("ch4-sleep", function (i, c) {
    var d = c.data, st = c.state, h = st.h, need = st.need, k;
    var debt = 0, sur = 0;
    for (k = 0; k < h.length; k++) { if (h[k] < need) debt += need - h[k]; else if (h[k] > need) sur += h[k] - need; }
    var net = debt - sur;
    var pt = c.q("[data-eg-pt]");
    if (!c.scrubbing) {
      c.set("num", trim(Math.abs(net), 1)); c.set("unit", net >= 0 ? "h debt" : "h ahead");
      c.set("chip", trim(debt, 1) + " h short · " + trim(sur, 1) + " h banked"); c.set("when", "Race week");
      if (pt) pt.style.display = "none";
    } else {
      c.set("num", trim(h[i], 1)); c.set("unit", "h · " + d.days[i]);
      c.set("chip", h[i] === need ? "on need" : minus(h[i] - need, 1) + " h vs need"); c.set("when", d.days[i]);
      if (pt) { pt.style.display = ""; pt.style.left = ((i + 0.5) / h.length * 100) + "%"; pt.style.top = (yOf(st, h[i]) / d.H * 100) + "%"; }
    }
    return d.days[i] + ": " + trim(h[i], 1) + " h, " + minus(h[i] - need, 1) + " h vs need";
  }, function (c) {
    var d = c.data, st = c.state, card = c.card, NS = "http://www.w3.org/2000/svg";
    st.h = d.h.slice(); st.need = d.need; st.d = d;
    var ins = card.querySelectorAll("input[data-h]");
    function redraw() {
      var n = st.h.length, xs = [], ys = [], k, pts = "";
      for (k = 0; k < n; k++) { xs.push((k + 0.5) / n * d.W); ys.push(yOf(st, st.h[k])); pts += (k ? "L" : "M") + xs[k].toFixed(1) + "," + ys[k].toFixed(1); }
      var ty = yOf(st, st.need);
      card.querySelector("[data-line]").setAttribute("d", pts);
      card.querySelector("[data-line-c]").setAttribute("d", pts);
      var tl = card.querySelector("[data-target]");
      tl.setAttribute("y1", ty.toFixed(1)); tl.setAttribute("y2", ty.toFixed(1));
      var tx = card.querySelector("[data-target-l]");
      tx.style.top = (ty / d.H * 100) + "%"; tx.textContent = trim(st.need, 1) + " h need";
      var g = card.querySelector("[data-areas]");
      while (g.firstChild) g.removeChild(g.firstChild);
      var runs = [];
      function push(s, p) { if (runs.length && runs[runs.length - 1].s === s) runs[runs.length - 1].p.push(p); else runs.push({ s: s, p: [p] }); }
      for (k = 0; k < n; k++) {
        var d0 = ys[k] - ty, s0 = d0 > 0 ? 1 : -1;
        push(s0, [xs[k], ys[k]]);
        if (k + 1 < n) {
          var d1 = ys[k + 1] - ty, s1 = d1 > 0 ? 1 : -1;
          if (s0 !== s1) { var x = xs[k] + d0 / (d0 - d1) * (xs[k + 1] - xs[k]); push(s0, [x, ty]); push(s1, [x, ty]); }
        }
      }
      for (k = 0; k < runs.length; k++) {
        var p = runs[k].p.slice(), dd = "";
        p.push([p[p.length - 1][0], ty]); p.push([p[0][0], ty]);
        for (var m = 0; m < p.length; m++) dd += (m ? "L" : "M") + p[m][0].toFixed(1) + "," + p[m][1].toFixed(1);
        var el = document.createElementNS(NS, "path");
        el.setAttribute("class", "gg-ig-c-eg-area gg-ig-c-eg-area--" + (runs[k].s > 0 ? "short" : "over"));
        el.setAttribute("d", dd + "Z");
        g.appendChild(el);
      }
      for (k = 0; k < n; k++) {
        var dot = card.querySelector('[data-dot="' + k + '"]');
        if (dot) dot.style.top = (ys[k] / d.H * 100) + "%";
        var dl = card.querySelector('[data-dl="' + k + '"]');
        if (dl) {
          var df = st.h[k] - st.need;
          dl.textContent = minus(df, 1);
          dl.className = "gg-ig-c-eg-d--" + (st.h[k] < st.need ? "short" : "over");
        }
      }
    }
    st.redraw = redraw;
    function onIn(inp, key, idx, lo, hi) {
      inp.addEventListener("input", function () {
        var v = parseFloat(inp.value);
        if (!isFinite(v) || v < lo || v > hi) { inp.setAttribute("aria-invalid", "true"); return; }
        inp.removeAttribute("aria-invalid");
        if (key === "need") st.need = v; else st.h[idx] = v;
        redraw(); c.refresh();
      });
    }
    for (var k = 0; k < ins.length; k++) onIn(ins[k], "h", parseInt(ins[k].getAttribute("data-h"), 10), 0, 16);
    var nd = card.querySelector("input[data-need]");
    if (nd) onIn(nd, "need", 0, 4, 12);
  });
  function yOf(st, v) {
    var d = st.d, c = Math.min(d.hi, Math.max(d.lo, v));
    return d.H * (d.hi - c) / (d.hi - d.lo);
  }

  /* glycogen */
  function interp(pts, h) {
    for (var k = 0; k < pts.length - 1; k++) {
      if (h <= pts[k + 1][0]) { var f = (h - pts[k][0]) / (pts[k + 1][0] - pts[k][0]); return pts[k][1] + f * (pts[k + 1][1] - pts[k][1]); }
    }
    return pts[pts.length - 1][1];
  }
  function fedAt(d, rate, h) {
    var u = interp(d.un, h), f = interp(d.fed, h);
    return Math.min(100, Math.max(0, u + rate / d.base * (f - u)));
  }
  GGEG.register("ch5-glyco", function (i, c) {
    var d = c.data, st = c.state, f = fedAt(d, st.rate, i), u = interp(d.un, i);
    var diff = Math.round(f) - Math.round(u);
    c.set("num", String(Math.round(f))); c.set("unit", "% left");
    c.set("chip", minus(diff, 0) + " vs unfed"); c.set("when", i === 0 ? "Start" : "Hour " + i);
    c.set("unf", Math.round(u) + "%"); c.set("note", "at " + st.rate + " g/hr");
    var pt = c.q("[data-eg-pt]");
    if (pt) { pt.style.left = (i / 6 * 100) + "%"; pt.style.top = (100 - f) + "%"; }
    return (i === 0 ? "Start" : "Hour " + i) + ": " + Math.round(f) + "% left at " + st.rate + " g per hour, " + Math.round(u) + "% unfed";
  }, function (c) {
    var d = c.data, st = c.state, card = c.card;
    st.rate = d.base;
    var inp = card.querySelector("input[data-rate]"), out = card.querySelector("[data-rate-out]");
    function redraw() {
      var hs = [0, 2, 4, 6], k, p = "", band = "";
      var fy = [];
      for (k = 0; k < hs.length; k++) {
        var x = hs[k] / 6 * d.W, y = d.H * (1 - fedAt(d, st.rate, hs[k]) / 100);
        fy.push([x, y]);
        p += (k ? "L" : "M") + x.toFixed(1) + "," + y.toFixed(1);
      }
      band = p;
      for (k = hs.length - 1; k >= 0; k--) band += "L" + (hs[k] / 6 * d.W).toFixed(1) + "," + (d.H * (1 - interp(d.un, hs[k]) / 100)).toFixed(1);
      card.querySelector("[data-fed]").setAttribute("d", p);
      card.querySelector("[data-fed-c]").setAttribute("d", p);
      card.querySelector("[data-band]").setAttribute("d", band + "Z");
      var end = card.querySelector('[data-end="fed"]'), v = fedAt(d, st.rate, 6);
      end.style.top = (100 - v) + "%";
      var cap = end.querySelector(".gg-eg-cap");
      if (cap) cap.textContent = Math.round(v) + "%";
      if (out) out.textContent = st.rate + " g";
    }
    if (inp) inp.addEventListener("input", function () {
      var v = parseFloat(inp.value);
      if (!isFinite(v)) return;
      st.rate = Math.min(120, Math.max(0, v));
      redraw(); c.refresh();
    });
  });

  /* calorie burn */
  GGEG.register("ch5-cal", function (i, c) {
    var d = c.data, tot = d.cum[i], burn = d.cal[i];
    c.set("num", comma(tot)); c.set("unit", "cal"); c.set("chip", "+" + comma(burn) + " this hour");
    c.set("when", "Hour " + (i + 1)); c.set("def", comma(Math.max(0, tot - d.food)));
    var bars = c.card.querySelectorAll("[data-bar]");
    for (var k = 0; k < bars.length; k++) bars[k].setAttribute("class", "gg-ig-c-eg-cb" + (k === i ? " is-on" : ""));
    var pt = c.q("[data-eg-pt]");
    if (pt) { pt.style.left = ((i + 0.5) / c.n * 100) + "%"; pt.style.top = ((1 - tot / d.ymax) * 100) + "%"; }
    return "Hour " + (i + 1) + ": " + comma(burn) + " cal burned, " + comma(tot) + " total";
  });

  /* readiness: traffic light and recovery dashboard (guide thresholds, see ch4_ch5.py) */
  function level(sleep, hr, body) {
    var s = sleep < 5 ? 2 : (sleep < 7 ? 1 : 0);
    return Math.max(s, hr, body);
  }
  function setCall(card, d, lv, word, chip, markKey) {
    var num = card.querySelector('[data-eg-f="num"]'), ch = card.querySelector('[data-eg-f="chip"]');
    if (num) num.textContent = word;
    if (ch) ch.textContent = chip;
    var mk = card.querySelector("[data-mk]");
    if (mk) mk.className = "gg-ig-c-mk gg-ig-c-mk--" + markKey;
  }
  var tl = document.querySelectorAll(".gg-ig-c-tl");
  for (var t = 0; t < tl.length; t++) (function (list) {
    var card = list.closest(".gg-eg");
    if (!card) return;
    var d = {}, isl = card.querySelector("script.gg-eg-data");
    try { d = JSON.parse(isl.textContent); } catch (e) { return; }
    var st = { sleep: 7.5, hr: 0, body: 0 };
    var keys = ["go", "caution", "stop"];
    function show() {
      var lv = level(st.sleep, st.hr, st.body);
      var rows = list.querySelectorAll(".gg-ig-c-tl-row");
      for (var k = 0; k < rows.length; k++) rows[k].className = "gg-ig-c-tl-row" + (k === lv ? " is-on" : "");
      setCall(card, d, lv, d.word[lv], d.short[lv], keys[lv]);
      var th = card.querySelector('[data-eg-f="then"]');
      if (th) th.textContent = d.then[lv];
    }
    var sl = card.querySelector("input[data-in='sleep']"), out = card.querySelector("[data-out='sleep']");
    if (sl) sl.addEventListener("input", function () { st.sleep = parseFloat(sl.value); if (out) out.textContent = trim(st.sleep, 1) + " h"; show(); });
    function seg(name) {
      var bs = card.querySelectorAll("button[data-" + name + "]");
      for (var k = 0; k < bs.length; k++) bs[k].addEventListener("click", function (e) {
        st[name] = parseInt(e.currentTarget.getAttribute("data-" + name), 10);
        press(bs, function (b) { return parseInt(b.getAttribute("data-" + name), 10) === st[name]; });
        show();
      });
    }
    seg("hr"); seg("body");
    card.classList.add("is-live");
  })(tl[t]);

  var rr = document.querySelectorAll(".gg-ig-c-rrows");
  for (var r = 0; r < rr.length; r++) (function (wrap) {
    var card = wrap.closest(".gg-eg");
    if (!card) return;
    var d = {}, isl = card.querySelector("script.gg-eg-data");
    try { d = JSON.parse(isl.textContent); } catch (e) { return; }
    var keys = ["go", "caution", "rest"];
    var st = {};
    function row(key) { return wrap.querySelector('[data-row="' + key + '"]'); }
    function show() {
      var sleep = st.sleep, sore = st.sore;
      var ls = sleep < 5 ? 2 : (sleep < 7 ? 1 : 0), lo = sore < 2 ? 2 : (sore < 3 ? 1 : 0);
      var lv = Math.max(ls, lo), why = [];
      if (ls === lv && lv > 0) why.push("Sleep under " + (lv === 2 ? 5 : 7) + " h");
      if (lo === lv && lv > 0) why.push("Soreness under " + (lv === 2 ? 2 : 3));
      setCall(card, d, lv, d.word[lv], lv === 0 ? "Sleep and soreness on target" : why.join(" · "), keys[lv]);
      var then = card.querySelector('[data-eg-f="then"]');
      if (then) then.textContent = d.then[lv];
      var names = ["sleep", "hrv", "sore"];
      for (var k = 0; k < names.length; k++) {
        var rw = row(names[k]), m = rw.querySelector(".gg-eg-meter b"), inp = rw.querySelector("input");
        var mx = parseFloat(inp.max), v = st[names[k]];
        setW(m, Math.max(0, Math.min(100, v / mx * 100)));
        rw.querySelector("[data-v]").textContent = trim(v, 1);
      }
    }
    var names = ["sleep", "hrv", "sore"];
    for (var k = 0; k < names.length; k++) (function (key) {
      var inp = row(key).querySelector("input");
      st[key] = parseFloat(inp.value);
      inp.addEventListener("input", function () { var v = parseFloat(inp.value); if (isFinite(v)) { st[key] = v; show(); } });
    })(names[k]);
    card.classList.add("is-live");
  })(rr[r]);

  /* bonk math */
  var bm = document.querySelectorAll(".gg-ig-c-bonk");
  for (var b = 0; b < bm.length; b++) (function (root) {
    var GEL = 25;
    var hrs = root.querySelector("input[data-in='hours']"), rate = root.querySelector("input[data-in='rate']");
    var grid = root.querySelector("[data-gels]");
    function o(n) { return root.querySelector("[data-out='" + n + "']"); }
    function update() {
      var h = parseFloat(hrs.value), c = parseFloat(rate.value), total = h * c, gels = Math.ceil(total / GEL - 1e-9);
      root.querySelector("[data-val='hours']").textContent = trim(h, 1) + " hrs";
      root.querySelector("[data-val='rate']").textContent = c + " g";
      o("eq").textContent = trim(h, 1) + " × " + c + "g = " + comma(total) + "g";
      o("note").textContent = trim(h, 1) + " hours × " + c + "g carbs/hr = " + comma(total) + "g total carbohydrate";
      o("gels").textContent = "= " + gels + " gels";
      while (grid.firstChild) grid.removeChild(grid.firstChild);
      for (var k = 1; k <= gels; k++) {
        var s = document.createElement("span");
        s.className = "gg-ig-c-gel"; s.setAttribute("aria-hidden", "true"); s.textContent = String(k);
        grid.appendChild(s);
      }
    }
    hrs.addEventListener("input", update); rate.addEventListener("input", update);
  })(bm[b]);

  /* macro split: grams from the guide's g/kg ranges (carbs 6-10, protein 1.6-2.2) */
  var mc = document.querySelectorAll("[data-macros]");
  for (var m = 0; m < mc.length; m++) (function (root) {
    var wt = root.querySelector("input[data-wt]"), btns = root.querySelectorAll("button[data-unit]");
    var unit = "kg", R = { carb: [6, 10], protein: [1.6, 2.2] };
    function kg() { var v = parseFloat(wt.value); return unit === "kg" ? v : v / 2.20462; }
    function update() {
      var w = kg();
      if (!isFinite(w) || w < 30 || w > 200) { wt.setAttribute("aria-invalid", "true"); return; }
      wt.removeAttribute("aria-invalid");
      for (var key in R) {
        var el = root.querySelector("[data-g='" + key + "']");
        if (el) el.textContent = comma(R[key][0] * w) + "-" + comma(R[key][1] * w) + " g a day";
      }
    }
    wt.addEventListener("input", update);
    for (var k = 0; k < btns.length; k++) btns[k].addEventListener("click", function (e) {
      var to = e.currentTarget.getAttribute("data-unit");
      if (to === unit) return;
      var w = kg();
      if (isFinite(w)) wt.value = to === "kg" ? trim(w, 1) : trim(w * 2.20462, 0);
      unit = to;
      wt.min = unit === "kg" ? "30" : "66"; wt.max = unit === "kg" ? "200" : "441"; wt.step = unit === "kg" ? "0.5" : "1";
      press(btns, function (x) { return x.getAttribute("data-unit") === unit; });
      update();
    });
    root.classList.add("is-live");
  })(mc[m]);

  /* fueling timeline: clock times from the race start */
  var tm = document.querySelectorAll("[data-timeline]");
  for (var q = 0; q < tm.length; q++) (function (root) {
    var inp = root.querySelector("input[data-start]");
    var OFF = [[-180], [-30], [0], [15, 20], null];
    function clock(min) {
      min = ((min % 1440) + 1440) % 1440;
      var h = Math.floor(min / 60), mm = min % 60, ap = h >= 12 ? "PM" : "AM";
      return ((h % 12) || 12) + ":" + (mm < 10 ? "0" : "") + mm + " " + ap;
    }
    function update() {
      var v = inp.value, ok = /^\d{2}:\d{2}$/.test(v), base = 0;
      if (ok) base = parseInt(v.slice(0, 2), 10) * 60 + parseInt(v.slice(3), 10);
      for (var k = 0; k < OFF.length; k++) {
        var el = root.querySelector("[data-clock='" + k + "']");
        if (!el) continue;
        if (!ok || !OFF[k]) { el.textContent = ""; continue; }
        el.textContent = OFF[k].length === 1 ? clock(base + OFF[k][0]) : clock(base + OFF[k][0]) + "-" + clock(base + OFF[k][1]);
      }
    }
    inp.addEventListener("input", update);
  })(tm[q]);

  /* hydration calculator.
     Fluid per hour = 500 ml + heat + effort. Heat adds 5 ml per degree F above 60 up to 90 F
     (150 ml, as in round 1), then 2.5 ml per degree up to 110 F (200 ml). Effort adds 12.5 ml per
     step above 1. Top of the range is 750 ml/hr, the guide's own upper bound. Sodium is 1.2 mg per
     ml, which keeps 500-750 ml/hr inside the guide's 500-1000 mg/hr. */
  document.querySelectorAll(".gg-ig-c-hydra").forEach(function (root) {
    var inputs = {};
    root.querySelectorAll("input[data-in]").forEach(function (el) { inputs[el.getAttribute("data-in")] = el; });
    function out(name) { return root.querySelector("[data-out='" + name + "']"); }
    function update() {
      var dur = parseFloat(inputs.duration.value);
      var temp = parseFloat(inputs.temp.value);
      var inten = parseFloat(inputs.intensity.value);
      var heat = temp <= 90 ? Math.max(0, (temp - 60) * 5) : 150 + (temp - 90) * 2.5;
      var rate = 500 + heat + (inten - 1) * 12.5;
      var total = rate * dur;
      var sodiumRate = rate * 1.2;
      var vals = { duration: dur + " hrs", temp: temp + "°F", intensity: inten + " / 5" };
      Object.keys(vals).forEach(function (k) {
        var o = root.querySelector("[data-val='" + k + "']");
        if (o) o.textContent = vals[k];
      });
      out("fluid").textContent = comma(total);
      out("sodium").textContent = comma(sodiumRate) + " mg";
      out("sodiumtotal").textContent = comma(sodiumRate * dur) + " mg total";
      out("rate").textContent = comma(rate) + " ml";
      out("bottles").textContent = "~" + (rate / 500).toFixed(1);
    }
    Object.keys(inputs).forEach(function (k) { inputs[k].addEventListener("input", update); });
    update();
  });
})();
"""
