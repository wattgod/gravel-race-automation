"""Endure Glyph kit for the Handbook charts (shared by every guide_ig group).

A Glyph card sits INSIDE the Gravel God panel: white card, 1px edge, header that is the
readout, one cobalt scrub point, capsules, dotted plan. Source of truth for the look:
endurelabs docs/brand/endure-glyph-guidelines.md section 5.16.

Exports
  Python helpers  esc, safe_json, linear, log_scale, line_path, mono_curve, mono_sample,
                  capsule, meter, hatch_def, readout, scrub_wrap, glyph_card
  TOKENS_CSS      the ONE block that may hold hex values (Glyph tokens, scoped to .gg-eg)
  CSS             TOKENS_CSS plus the card/header/capsule/meter/hairline rules (var() only)
  JS              window.GGEG: scrub controller shared by every Glyph chart

Scrub contract
  scrub_wrap() renders an element with data-eg-scrub="<id>", data-eg-n, data-eg-def,
  data-eg-mode ("band": n slots, "point": n points). A group registers
  GGEG.register(id, update, setup): update(i, ctx) draws index i and may return the
  aria-valuetext; setup(ctx) runs once. ctx.set(field, text) writes textContent into
  [data-eg-f="field"] in the card; ctx.q(sel) queries the card; ctx.refresh() redraws.
  The card's JSON data island (<script type="application/json" class="gg-eg-data">) is
  parsed once into ctx.data. No innerHTML anywhere.
"""
import html as _html
import math
import re

ENDURE_URL = "https://endurelabs.app/?utm_source=gravelgod&utm_medium=handbook&utm_campaign=guide-charts"


def esc(v) -> str:
    """Escape any value for HTML. 0 prints as 0."""
    return _html.escape("" if v is None else str(v), quote=True)


def safe_json(obj) -> str:
    """JSON that cannot close or confuse the <script> element it sits in."""
    import json

    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    return (
        raw.replace("</", "<\\/").replace("<!--", "<\\!--")
        .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    )


# ── scales and paths ────────────────────────────────────────

def linear(d0, d1, r0, r1):
    """Linear scale from the domain d0..d1 to the range r0..r1."""
    span = (d1 - d0) or 1
    return lambda v: r0 + (v - d0) / span * (r1 - r0)


def log_scale(d0, d1, r0, r1):
    """Log10 scale from the domain d0..d1 (both > 0) to the range r0..r1."""
    a, b = math.log10(d0), math.log10(d1)
    return lambda v: r0 + (math.log10(v) - a) / (b - a) * (r1 - r0)


def line_path(points, close=False) -> str:
    """Straight-segment SVG path through (x, y) points (use mono_sample for curves)."""
    if not points:
        return ""
    out = [f"M{points[0][0]:.1f},{points[0][1]:.1f}"]
    out += [f"L{x:.1f},{y:.1f}" for x, y in points[1:]]
    if close:
        out.append("Z")
    return " ".join(out)


def _slopes(xs, ys):
    n = len(xs)
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
    return m


def mono_curve(pts):
    """Monotone cubic through (x, y) points -> f(x). Passes every point, never overshoots."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    m = _slopes(xs, ys)

    def f(x):
        x = min(max(x, xs[0]), xs[-1])
        i = 0
        while i < len(xs) - 2 and x > xs[i + 1]:
            i += 1
        h = xs[i + 1] - xs[i]
        t = (x - xs[i]) / h
        t2, t3 = t * t, t * t * t
        return (
            (2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h * m[i]
            + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * h * m[i + 1]
        )

    return f


def mono_sample(pts, per_seg=24):
    """Dense (x, y) samples along the monotone cubic, every data point included."""
    f = mono_curve(pts)
    out = []
    for i in range(len(pts) - 1):
        x0, x1 = pts[i][0], pts[i + 1][0]
        for k in range(per_seg):
            x = x0 + (x1 - x0) * k / per_seg
            out.append((x, f(x)))
    out.append(pts[-1])
    return out


# ── markup helpers ──────────────────────────────────────────

def capsule(value, label="", tone="ink", style="filled", field=None, label_field=None) -> str:
    """A number in a capsule of its colour, name beside it in the same colour.

    tone: ink | pink | teal | ride.  style: filled | dotted | outlined.
    """
    f = f' data-eg-f="{esc(field)}"' if field else ""
    lf = f' data-eg-f="{esc(label_field)}"' if label_field else ""
    lab = f'<span class="gg-eg-capl gg-eg-t-{esc(tone)}"{lf}>{esc(label)}</span>' if label else ""
    return (
        f'<span class="gg-eg-capw"><span class="gg-eg-cap gg-eg-cap--{esc(tone)} '
        f'gg-eg-cap--{esc(style)}"{f}>{esc(value)}</span>{lab}</span>'
    )


def meter(value, max_value, tick=None) -> str:
    """Glyph meter: 10px ink bar on a paper track, optional 2px target tick."""
    top = max_value or 1
    pct = max(0.0, min(100.0, value / top * 100))
    t = ""
    if tick is not None:
        t = f'<i class="gg-eg-tick" style="left:{max(0.0, min(100.0, tick / top * 100)):.1f}%"></i>'
    return f'<span class="gg-eg-meter"><b style="width:{pct:.1f}%"></b>{t}</span>'


def hatch_def(pattern_id="gg-eg-hatch") -> str:
    """SVG <defs> with the 45 degree hatch used for 'not known'."""
    pid = esc(pattern_id)
    return (
        f'<defs><pattern id="{pid}" width="6" height="6" patternUnits="userSpaceOnUse" '
        f'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" class="gg-eg-hatchline" '
        f'stroke-width="2"/></pattern></defs>'
    )


def readout(num, unit="", chip="", when="", extra="") -> str:
    """Header readout: one bold mono number, small unit, change chip; `when` shows at right.

    Fields (data-eg-f): num, unit, chip, when. `extra` is a row of capsules/notes.
    """
    chip_html = f'<span class="gg-eg-chip" data-eg-f="chip">{esc(chip)}</span>' if chip != "" else ""
    return (
        f'<div class="gg-eg-read"><p class="gg-eg-main"><b class="gg-eg-num" data-eg-f="num">{esc(num)}</b>'
        f'<span class="gg-eg-unit" data-eg-f="unit">{esc(unit)}</span>{chip_html}</p>'
        f'<p class="gg-eg-when" data-eg-f="when">{esc(when)}</p></div>'
        + (f'<div class="gg-eg-extra">{extra}</div>' if extra else "")
    )


def scrub_wrap(chart_id, inner, n, default, label, valuetext, mode="band") -> str:
    """The scrubbable plot: a focusable slider that carries the hairline."""
    return (
        f'<div class="gg-eg-pw" data-eg-scrub="{esc(chart_id)}" data-eg-n="{int(n)}" '
        f'data-eg-def="{int(default)}" data-eg-mode="{esc(mode)}" tabindex="0" role="slider" '
        f'aria-label="{esc(label)}" aria-valuemin="0" aria-valuemax="{int(n) - 1}" '
        f'aria-valuenow="{int(default)}" aria-valuetext="{esc(valuetext)}">{inner}</div>'
    )


def glyph_card(name, readout_html, plot_html, foot=True, controls_html="",
               data=None, describedby="", description="") -> str:
    """One Glyph card: name, readout, optional controls, plot, 'Built on Endure Labs' footer.

    `data` is serialised into a JSON data island; `description` is the hidden sentence form
    of the chart (screen readers only), tied to the card by `describedby`.
    """
    island = (
        f'<script type="application/json" class="gg-eg-data">{safe_json(data)}</script>'
        if data is not None else ""
    )
    desc = f'<p class="gg-eg-sr" id="{esc(describedby)}">{esc(description)}</p>' if describedby else ""
    ctrl = f'<div class="gg-eg-controls">{controls_html}</div>' if controls_html else ""
    foot_html = (
        f'<p class="gg-eg-foot">Built on <a href="{ENDURE_URL}" target="_blank" rel="noopener">'
        f'Endure Labs</a></p>' if foot else ""
    )
    dby = f' aria-describedby="{esc(describedby)}"' if describedby else ""
    return (
        f'<div class="gg-eg" role="group" aria-label="{esc(name)}"{dby}>'
        f'<p class="gg-eg-name">{esc(name)}</p>'
        f'<div class="gg-eg-live" aria-live="polite">{readout_html}</div>'
        f'{ctrl}<div class="gg-eg-plotbox">{plot_html}</div>{foot_html}{desc}{island}</div>'
    )


# ── CSS ─────────────────────────────────────────────────────

# The only place hex values live (Glyph tokens, guidelines sections 3.1, 3.3, 3.4, 3.5).
TOKENS_CSS = """
.gg-eg{--eg-card:#FFFFFF;--eg-edge:#E1E4EA;--eg-line:#E6E8EC;--eg-past:#FAFAFB;--eg-control:#EEF1F5;--eg-paper:#F2F4F7;--eg-ink:#142A3C;--eg-ink2:#3B475A;--eg-ink3:#5B6678;--eg-none:#AAB3C0;--eg-cobalt:#2563EB;--eg-fat:#DB2777;--eg-form:#0E7490;--eg-ride:#7C3AED;--eg-shadow:0 1px 2px rgba(15,23,42,.06);--eg-mono:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,monospace;--eg-prose:'Geist',system-ui,-apple-system,'Segoe UI',sans-serif}
"""

_CSS_BODY = """
.gg-eg{box-sizing:border-box;position:relative;background:var(--eg-card);color:var(--eg-ink);border-radius:10px;box-shadow:inset 0 0 0 1px var(--eg-edge),var(--eg-shadow);padding:16px 16px 12px;font-family:var(--eg-prose);font-size:14px;line-height:1.35;text-align:left;max-width:100%;min-width:0}
.gg-eg *{box-sizing:border-box}
.gg-eg p{margin:0;padding:0;font-family:inherit;font-size:inherit;color:inherit;letter-spacing:0;text-transform:none}
.gg-eg .gg-eg-name{font-family:var(--eg-prose);font-weight:600;font-size:14px;color:var(--eg-ink2);margin:0 0 6px}
.gg-eg .gg-eg-read{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.gg-eg .gg-eg-main{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 8px;min-width:0}
.gg-eg .gg-eg-num{font-family:var(--eg-mono);font-weight:800;font-size:28px;line-height:1.1;font-variant-numeric:tabular-nums;color:var(--eg-ink)}
.gg-eg .gg-eg-unit{font-family:var(--eg-mono);font-size:12px;color:var(--eg-ink3)}
.gg-eg .gg-eg-chip{font-family:var(--eg-mono);font-weight:700;font-size:12px;line-height:1;background:var(--eg-control);color:var(--eg-ink);border-radius:999px;padding:6px 10px;white-space:nowrap}
.gg-eg .gg-eg-when{font-family:var(--eg-mono);font-size:11px;font-weight:500;color:var(--eg-ink3);text-align:right;white-space:nowrap;padding-top:6px}
.gg-eg.is-scrub .gg-eg-when{color:var(--eg-cobalt);font-weight:700}
.gg-eg .gg-eg-extra{display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px;margin-top:8px;font-family:var(--eg-mono);font-size:12px;color:var(--eg-ink2)}
.gg-eg .gg-eg-capw{display:inline-flex;align-items:center;gap:6px;font-family:var(--eg-mono);font-size:12px;font-weight:700}
.gg-eg .gg-eg-cap{display:inline-block;min-width:26px;text-align:center;font-family:var(--eg-mono);font-weight:800;font-size:12px;line-height:19px;height:19px;border-radius:10px;padding:0 8px;font-variant-numeric:tabular-nums;border:2px solid transparent;white-space:nowrap}
.gg-eg .gg-eg-cap--filled.gg-eg-cap--ink{background:var(--eg-ink);color:var(--eg-card)}
.gg-eg .gg-eg-cap--filled.gg-eg-cap--pink{background:var(--eg-fat);color:var(--eg-card)}
.gg-eg .gg-eg-cap--filled.gg-eg-cap--teal{background:var(--eg-form);color:var(--eg-card)}
.gg-eg .gg-eg-cap--filled.gg-eg-cap--ride{background:var(--eg-ride);color:var(--eg-card)}
.gg-eg .gg-eg-cap--dotted,.gg-eg .gg-eg-cap--outlined{background:var(--eg-card);border-style:dotted;line-height:15px}
.gg-eg .gg-eg-cap--outlined{border-style:solid;border-width:1.5px}
.gg-eg .gg-eg-cap--dotted.gg-eg-cap--ink,.gg-eg .gg-eg-cap--outlined.gg-eg-cap--ink{border-color:var(--eg-ink);color:var(--eg-ink)}
.gg-eg .gg-eg-cap--dotted.gg-eg-cap--pink,.gg-eg .gg-eg-cap--outlined.gg-eg-cap--pink{border-color:var(--eg-fat);color:var(--eg-fat)}
.gg-eg .gg-eg-cap--dotted.gg-eg-cap--teal,.gg-eg .gg-eg-cap--outlined.gg-eg-cap--teal{border-color:var(--eg-form);color:var(--eg-form)}
.gg-eg .gg-eg-cap--dotted.gg-eg-cap--ride,.gg-eg .gg-eg-cap--outlined.gg-eg-cap--ride{border-color:var(--eg-ride);color:var(--eg-ride)}
.gg-eg .gg-eg-t-ink{color:var(--eg-ink)}.gg-eg .gg-eg-t-pink{color:var(--eg-fat)}.gg-eg .gg-eg-t-teal{color:var(--eg-form)}.gg-eg .gg-eg-t-ride{color:var(--eg-ride)}
.gg-eg .gg-eg-meter{position:relative;display:block;height:10px;background:var(--eg-paper);border-radius:2px}
.gg-eg .gg-eg-meter b{position:absolute;left:0;top:0;bottom:0;background:var(--eg-ink);border-radius:2px}
.gg-eg .gg-eg-tick{position:absolute;top:-2px;bottom:-2px;width:2px;margin-left:-1px;background:var(--eg-ink)}
.gg-eg .gg-eg-hatchline{stroke:var(--eg-none)}
.gg-eg .gg-eg-plotbox{margin-top:14px;position:relative}
.gg-eg .gg-eg-pw{position:relative;touch-action:pan-y;outline:none;-webkit-tap-highlight-color:transparent;cursor:crosshair}
.gg-eg .gg-eg-pw:focus-visible{outline:2px solid var(--eg-cobalt);outline-offset:3px}
.gg-eg .gg-eg-pw::after{content:"";position:absolute;top:0;bottom:0;left:var(--eg-x,0);width:1px;margin-left:-.5px;background:var(--eg-cobalt);display:none;pointer-events:none;z-index:3}
.gg-eg.is-scrub .gg-eg-pw::after{display:block}
.gg-eg .gg-eg-pt{position:absolute;width:12px;height:12px;margin:-6px 0 0 -6px;border-radius:50%;background:var(--eg-cobalt);box-shadow:0 0 0 3px var(--eg-card);z-index:4;pointer-events:none}
.gg-eg .gg-eg-svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible;display:block}
.gg-eg .gg-eg-controls{display:none;flex-wrap:wrap;align-items:center;gap:8px 14px;margin-top:12px}
.gg-eg.is-live .gg-eg-controls{display:flex}
.gg-eg .gg-eg-seg{display:inline-flex;background:var(--eg-control);border-radius:999px;padding:3px}
.gg-eg .gg-eg-seg button{appearance:none;border:0;background:transparent;color:var(--eg-ink2);font-family:var(--eg-mono);font-weight:700;font-size:12px;min-height:44px;min-width:56px;padding:0 14px;border-radius:999px;cursor:pointer;margin:0}
.gg-eg .gg-eg-seg button[aria-pressed="true"]{background:var(--eg-cobalt);color:var(--eg-card)}
.gg-eg button:focus-visible,.gg-eg input:focus-visible,.gg-eg a:focus-visible{outline:2px solid var(--eg-cobalt);outline-offset:2px}
.gg-eg .gg-eg-field{display:inline-flex;align-items:center;gap:6px;font-family:var(--eg-mono);font-size:12px;font-weight:700;color:var(--eg-ink2)}
.gg-eg .gg-eg-field input{width:76px;min-height:44px;font-family:var(--eg-mono);font-weight:700;font-size:14px;color:var(--eg-ink);background:var(--eg-card);border:1px solid var(--eg-none);border-radius:8px;padding:0 8px;margin:0;text-align:right}
.gg-eg .gg-eg-field input[aria-invalid="true"]{border-color:var(--eg-ink)}
.gg-eg .gg-eg-foot{margin-top:10px;font-family:var(--eg-mono);font-size:11px;color:var(--eg-ink3)}
.gg-eg .gg-eg-foot a{color:var(--eg-ink3);text-decoration:underline;text-underline-offset:2px}
.gg-eg .gg-eg-sr{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}
@media (max-width:560px){
.gg-eg{padding:14px 12px 10px}
.gg-eg .gg-eg-num{font-size:26px}
}
@media (prefers-reduced-motion:reduce){
.gg-eg *{transition:none!important;animation:none!important}
}
"""

# The Handbook page forces border-radius:0 and box-shadow:none with !important (neo-brutalist
# reset); the Glyph card needs its own radius and edge, so these two properties win back.
_CSS_BODY = re.sub(r"(border-radius|box-shadow):([^;}]+)", r"\1:\2!important", _CSS_BODY)

CSS = TOKENS_CSS + _CSS_BODY


# ── JS ──────────────────────────────────────────────────────

JS = r"""
var GGEG = window.GGEG = window.GGEG || {};
GGEG.reg = GGEG.reg || {};
GGEG.fmt = function (v, d) {
  var s = (Math.round(v * Math.pow(10, d)) / Math.pow(10, d)).toFixed(d);
  return s;
};
GGEG.signed = function (v, d) {
  var s = GGEG.fmt(Math.abs(v), d || 0);
  return (v > 0 ? "+" : (v < 0 ? "-" : "")) + s;
};
GGEG.register = function (id, update, setup) {
  GGEG.reg[id] = { update: update, setup: setup };
  var els = document.querySelectorAll('[data-eg-scrub="' + id + '"]');
  for (var k = 0; k < els.length; k++) GGEG.bind(els[k], GGEG.reg[id]);
};
GGEG.bind = function (el, spec) {
  if (el.getAttribute("data-eg-bound")) return;
  el.setAttribute("data-eg-bound", "1");
  var card = el.closest(".gg-eg");
  if (!card) return;
  var data = {};
  var island = card.querySelector("script.gg-eg-data");
  if (island) { try { data = JSON.parse(island.textContent); } catch (e) { data = {}; } }
  var n = parseInt(el.getAttribute("data-eg-n"), 10) || 1;
  var def = parseInt(el.getAttribute("data-eg-def"), 10) || 0;
  var mode = el.getAttribute("data-eg-mode") || "band";
  var cur = def;
  var fields = {};
  var nodes = card.querySelectorAll("[data-eg-f]");
  for (var k = 0; k < nodes.length; k++) fields[nodes[k].getAttribute("data-eg-f")] = nodes[k];
  var ctx = {
    el: el, card: card, data: data, n: n, def: def, x: 0, scrubbing: false, state: {},
    set: function (key, text) { if (fields[key]) fields[key].textContent = text; },
    q: function (sel) { return card.querySelector(sel); },
    refresh: function () { show(cur, ctx.scrubbing); }
  };
  function clamp(v, a, b) { return Math.min(b, Math.max(a, v)); }
  function show(i, scrub) {
    i = clamp(i, 0, n - 1);
    cur = i;
    var frac = mode === "band" ? (i + 0.5) / n : (n > 1 ? i / (n - 1) : 0);
    ctx.x = frac;
    ctx.scrubbing = scrub;
    el.style.setProperty("--eg-x", (frac * 100) + "%");
    card.classList.toggle("is-scrub", scrub);
    var t = spec.update(i, ctx);
    el.setAttribute("aria-valuenow", String(i));
    if (typeof t === "string") el.setAttribute("aria-valuetext", t);
  }
  function idxAt(clientX) {
    var r = el.getBoundingClientRect();
    var f = clamp((clientX - r.left) / (r.width || 1), 0, 1);
    return mode === "band" ? Math.min(n - 1, Math.floor(f * n)) : Math.round(f * (n - 1));
  }
  function reset() { show(def, false); }
  var down = false;
  el.addEventListener("pointerdown", function (e) {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    down = true;
    try { el.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
    show(idxAt(e.clientX), true);
  });
  el.addEventListener("pointermove", function (e) {
    if (e.pointerType === "mouse" || down) show(idxAt(e.clientX), true);
  });
  function release() { down = false; reset(); }
  el.addEventListener("pointerup", function (e) { if (e.pointerType !== "mouse") release(); else down = false; });
  el.addEventListener("pointercancel", release);
  el.addEventListener("pointerleave", function (e) { if (e.pointerType === "mouse" && !down) reset(); });
  el.addEventListener("blur", reset);
  el.addEventListener("keydown", function (e) {
    var big = mode === "band" ? 3 : Math.max(2, Math.round(n / 20));
    var step = e.shiftKey ? big : 1;
    var next = null;
    if (e.key === "ArrowRight" || e.key === "ArrowUp") next = cur + step;
    else if (e.key === "ArrowLeft" || e.key === "ArrowDown") next = cur - step;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = n - 1;
    else if (e.key === "Escape") { reset(); return; }
    if (next === null) return;
    e.preventDefault();
    show(next, true);
  });
  card.classList.add("is-live");
  if (spec.setup) spec.setup(ctx);
  show(def, false);
};
"""
