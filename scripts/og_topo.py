#!/usr/bin/env python3
"""
Topo — the Gravel God Open Graph share-card system (1200x630).

One frame for the whole business: a field colour per pillar (teal race
ratings, gold training plans, near-black coaching), contour lines, the GG
mark, a chamfered tag that labels its own number, and a strip naming all
three pillars with the card's own pillar lit. Approved Oct 2026 after a
review pass for legibility at iMessage-bubble size (~340px wide): every
number carries a >=28px label, one secondary line per card, contours washed
out behind the text.

Cards are HTML rendered by headless Chromium (Playwright — already a repo
requirement; CI installs the browser). Fonts are the repo's guide/fonts TTFs
served through a route, so rendering is identical on any machine.

Field teal #145f5a and gold #c9a92c are deliberately richer than the site
tokens (these are dark/bold cards, the site is paper); every text pair on
them clears WCAG AA.

Used by:
    scripts/generate_og_images.py    — /og/{race-slug}.jpg
    scripts/generate_homepage_og.py  — /og/homepage.jpg (site-wide fallback)
    scripts/generate_page_og.py      — /og/page-*.jpg (plans, coaching, season review)
    scripts/generate_course_og.py    — /course/assets/*-og.png
"""

from __future__ import annotations

import html
import io
import math
import random
import sys
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "wordpress"))

from shared_header import GG_LOGO_SVG  # noqa: E402

W, H = 1200, 630
FONT_DIR = REPO_ROOT / "guide" / "fonts"
OG_OUTPUT_DIR = REPO_ROOT / "wordpress" / "output" / "og"
_ORIGIN = "https://og.render"


class OGCardError(Exception):
    """Raised instead of shipping a card whose text overflowed."""


# pillar -> (field, contour, contour opacity, text, secondary, kicker, tag bg, tag fg)
FIELDS = {
    "races":    ("#145f5a", "#f5efe6", .10, "#f5efe6", "rgba(245,239,230,.86)", "#f5efe6", "#c9a92c", "#1a1613"),
    "plans":    ("#c9a92c", "#1a1613", .07, "#1a1613", "rgba(26,22,19,.84)", "#1a1613", "#1a1613", "#c9a92c"),
    "coaching": ("#1a1613", "#c9a92c", .11, "#f5efe6", "rgba(245,239,230,.84)", "#c9a92c", "#c9a92c", "#1a1613"),
}
PILLARS = (("races", "RACE RATINGS"), ("plans", "TRAINING PLANS"), ("coaching", "COACHING"))

_FONT_CSS = """
@font-face{font-family:SS;src:url(/fonts/SourceSerif4-Variable.ttf);font-weight:200 900}
@font-face{font-family:SS;font-style:italic;src:url(/fonts/SourceSerif4-Italic-Variable.ttf);font-weight:200 900}
@font-face{font-family:SM;src:url(/fonts/SometypeMono-Regular.ttf);font-weight:400}
@font-face{font-family:SM;src:url(/fonts/SometypeMono-Bold.ttf);font-weight:700}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1200px;height:630px;overflow:hidden}
.card{position:relative;width:1200px;height:630px;overflow:hidden}
.mono{font-family:SM;font-weight:700;text-transform:uppercase}
.serif{font-family:SS;font-weight:700}
.mark{fill:currentColor;height:72px;width:auto;display:block}
.kicker{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.clamp{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden}
"""

# Shrinks each .fit headline from its size until it fits its max lines, then
# reports whether anything still overflows (body[data-og] = ok | overflow).
_FIT_JS = """
(() => {
  let ok = true;
  for (const el of document.querySelectorAll('.fit')) {
    const max = +el.dataset.lines, min = +el.dataset.min;
    let size = parseFloat(getComputedStyle(el).fontSize);
    const lines = () => el.getBoundingClientRect().height / (size * 1.02);
    while (lines() > max + 0.2 && size > min) { size -= 2; el.style.fontSize = size + 'px'; }
    if (lines() > max + 0.2) ok = false;
  }
  for (const el of document.querySelectorAll('.box')) {
    if (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1) ok = false;
  }
  document.body.dataset.og = ok ? 'ok' : 'overflow';
})();
"""


def e(text) -> str:
    return html.escape(str(text), quote=True)


def _seed(key: str) -> int:
    return zlib.crc32(key.encode("utf-8"))  # stable across runs (hash() is salted)


def topo_svg(key: str, color: str, opacity: float) -> str:
    """Contour lines: concentric, harmonically wobbled rings around three
    seeded centres. Deterministic per key, so a race's card never changes
    unless its data does."""
    rng = random.Random(_seed(key))
    paths = []
    for _ in range(3):
        cx, cy = rng.uniform(200, W), rng.uniform(-50, H + 50)
        harm = [(rng.uniform(.04, .16), rng.randint(2, 5), rng.uniform(0, 6.28)) for _ in range(3)]
        for k in range(1, 15):
            r0 = k * 34
            pts = []
            for j in range(181):
                t = 2 * math.pi * j / 180
                rr = r0 * (1 + sum(a * math.sin(f * t + p + k * .13) for a, f, p in harm))
                pts.append(f"{cx + rr * math.cos(t):.1f},{cy + rr * math.sin(t) * .78:.1f}")
            heavy = k % 5 == 0
            paths.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" '
                         f'stroke-opacity="{opacity * 2.2 if heavy else opacity}" '
                         f'stroke-width="{2.4 if heavy else 1.4}"/>')
    return f'<svg width="{W}" height="{H}" style="position:absolute;inset:0">{"".join(paths)}</svg>'


def _strip(active: str | None, f) -> str:
    _, _, _, text, muted, _, tag_bg, tag_fg = f
    items = []
    for key, label in PILLARS:
        if key == active:
            style = f"background:{tag_bg};color:{tag_fg};padding:6px 12px"
        else:
            style = f"color:{text};opacity:{1 if active == 'all' else .62};padding:6px 0"
        items.append(f'<span style="{style}">{label}</span>')
    return (f'<div style="position:absolute;left:64px;right:64px;bottom:0;height:84px;'
            f'border-top:2px solid {muted};display:flex;align-items:center;justify-content:space-between">'
            f'<div class="mono" style="font-size:20px;letter-spacing:2px;display:flex;gap:26px;align-items:center">'
            f'{"".join(items)}</div>'
            f'<div class="mono" style="font-size:18px;letter-spacing:2px;color:{text};opacity:.8">'
            f'GRAVELGODCYCLING.COM</div></div>')


def _tag(f, label: str, value: str, prefix: str = "") -> str:
    *_, tag_bg, tag_fg = f
    pre = (f'<span style="font-size:34px;font-style:italic;font-weight:500">{e(prefix)} </span>'
           if prefix else "")
    width = 350 if prefix else 292
    return (f'<div class="box" style="position:absolute;right:64px;bottom:118px;width:{width}px;height:196px;'
            f'background:{tag_bg};clip-path:polygon(0 0,calc(100% - 34px) 0,100% 34px,100% 100%,0 100%);'
            f'padding:24px 26px;color:{tag_fg};overflow:hidden">'
            f'<div class="mono" style="font-size:28px;letter-spacing:2px;line-height:1;white-space:nowrap">{e(label)}</div>'
            f'<div class="serif" style="font-size:96px;line-height:1;margin-top:18px;white-space:nowrap">'
            f'{pre}{e(value)}</div></div>')


def _frame(pillar: str, active: str | None, key: str, inner: str) -> str:
    f = FIELDS[pillar]
    bg, line, op, text, *_ = f
    logo = GG_LOGO_SVG.replace('class="gg-logo-mark"', 'class="mark"')
    return (f'<div class="card" style="background:{bg}">'
            f'{topo_svg(key, line, op)}'
            f'<div style="position:absolute;inset:0;background:linear-gradient(90deg,{bg} 0%,{bg}e6 38%,{bg}00 72%)"></div>'
            f'<div style="position:absolute;left:64px;top:46px;color:{text}">{logo}</div>'
            f'{inner}{_strip(active, f)}</div>')


def _headline(f, kicker: str, title_html: str, size: int, *, line: str | None = None,
              serif_line: bool = False, width: int = 740, lines: int = 2, min_size: int = 56) -> str:
    _, _, _, text, muted, accent, *_ = f
    sec = ""
    if line:
        if serif_line:
            sec = (f'<div class="clamp" style="font-family:SS;font-size:32px;line-height:1.3;'
                   f'color:{muted};margin-top:20px">{e(line)}</div>')
        else:
            sec = (f'<div class="mono kicker" style="font-size:24px;letter-spacing:2px;color:{muted};'
                   f'margin-top:22px">{e(line)}</div>')
    return (f'<div class="stack" style="position:absolute;left:64px;top:172px;width:{width}px">'
            f'<div class="mono kicker" style="font-size:24px;letter-spacing:3px;color:{accent}">{e(kicker)}</div>'
            f'<div class="serif fit" data-lines="{lines}" data-min="{min_size}" '
            f'style="font-size:{size}px;line-height:1.02;color:{text};margin-top:14px">{title_html}</div>'
            f'{sec}</div>')


# ── Card builders (return inner HTML) ───────────────────────────

def race_card(*, key: str, tier_label: str, location: str, name: str, verdict: str, score) -> str:
    f = FIELDS["races"]
    kicker = f"{tier_label} · {location}" if location else tier_label
    return _frame("races", "races", key,
                  _headline(f, kicker, e(name), 88, line=verdict or None, serif_line=True, width=756)
                  + _tag(f, "LAB SCORE", str(score)))


def pillar_card(*, pillar: str, key: str, kicker: str, title_html: str, size: int = 84,
                line: str | None = None, serif_line: bool = False, tag: tuple | None = None,
                lines: int = 2, width: int = 740, active: str | None = "pillar") -> str:
    f = FIELDS[pillar]
    tag_html = _tag(f, *tag) if tag else ""
    return _frame(pillar, pillar if active == "pillar" else active, key,
                  _headline(f, kicker, title_html, size, line=line, serif_line=serif_line,
                            width=width, lines=lines) + tag_html)


def ladder_card(*, key: str, rows: list[tuple[str, str, str]]) -> str:
    """Homepage / fallback: the race -> plan -> coaching ladder."""
    f = FIELDS["races"]
    _, _, _, text, muted, _, tag_bg, _ = f
    body = "".join(
        f'<div style="display:flex;align-items:center;height:124px;'
        f'{"border-top:2px solid " + muted + ";" if i else ""}">'
        f'<div class="mono" style="font-size:26px;color:{tag_bg};width:78px">{e(n)}</div>'
        f'<div class="serif" style="font-size:76px;line-height:1;color:{text};flex:1;white-space:nowrap">{e(t)}</div>'
        f'<div class="mono" style="font-size:24px;color:{muted};letter-spacing:2px;text-align:right;'
        f'white-space:nowrap">{e(d)}</div></div>'
        for i, (n, t, d) in enumerate(rows))
    return _frame("races", "all", key,
                  f'<div class="box" style="position:absolute;left:64px;right:64px;top:150px;height:372px;'
                  f'overflow:hidden">{body}</div>')


def page_html(inner: str) -> str:
    return (f"<!doctype html><html><head><meta charset=utf-8><style>{_FONT_CSS}</style></head>"
            f"<body>{inner}</body></html>")


# ── Renderer ────────────────────────────────────────────────────

class Renderer:
    """One headless Chromium for a whole batch of cards.

        with Renderer() as r:
            r.render(race_card(...), out / "unbound-200.jpg")
    """

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - environment guard
            raise OGCardError(
                "Playwright is required to render OG cards: pip install -r requirements.txt "
                "&& python -m playwright install chromium") from exc
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self._page = self._browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        self._html = ""
        self._page.route(f"{_ORIGIN}/**", self._serve)
        return self

    def _serve(self, route):
        path = route.request.url[len(_ORIGIN):]
        if path.startswith("/fonts/"):
            font = FONT_DIR / Path(path).name
            return route.fulfill(body=font.read_bytes(), content_type="font/ttf")
        return route.fulfill(body=self._html, content_type="text/html; charset=utf-8")

    def render(self, inner: str, out_path: Path) -> Path:
        from PIL import Image

        self._html = page_html(inner)
        self._page.goto(f"{_ORIGIN}/card", wait_until="load")
        self._page.evaluate("document.fonts.ready")
        self._page.evaluate(_FIT_JS)
        if self._page.evaluate("document.body.dataset.og") != "ok":
            raise OGCardError(f"{out_path.name}: text overflows the card")
        png = self._page.screenshot(type="png")
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.open(io.BytesIO(png)).convert("RGB")
        if out_path.suffix.lower() == ".png":
            img.save(out_path, "PNG", optimize=True)
        else:
            img.save(out_path, "JPEG", quality=88, optimize=True, progressive=True)
        return out_path

    def __exit__(self, *exc):
        self._browser.close()
        self._pw.stop()
        return False
