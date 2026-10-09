"""Editorial shell: the Gravel God article page ("D: Gravel God x Endure Glyph").

One open reading column (680px measure), a quiet contents list in the left
margin (a sticky "Contents" bar below 1280px), an optional "In short" claim
list, the plans/coaching ladder, the site header and footer. Glyphs appear
only where they encode something: dots = state (read / current / ahead),
outline vs solid = planned vs actual in figures, chamfer = an action (real
buttons only). Design source: ~/specs/gg-article-mocks-2026-10-07/
directions/glyph/shell.html (Matt picked it 2026-10-08).

API for generators (articles, and later blog preview / recap / roundup)
-----------------------------------------------------------------------

    from datetime import date
    from editorial_shell import ArticleMeta, Claim, HeroImage, OgImage, render_editorial_page

    meta = ArticleMeta(
        slug="unbound-200-preview",
        canonical_url="https://gravelgodcycling.com/blog/unbound-200-preview/",
        title="Unbound 200 Race Preview | Gravel God",       # <title>
        description="...",                                    # meta description
        headline="Unbound 200 Race Preview",                  # the h1
        date_published=date(2026, 5, 1),
        kicker="Tier 1 · Emporia, KS",                        # mono line above the h1
        dek="...",                                            # italic line under the h1
        robots="noindex, follow",                             # previews are noindex
        hero=HeroImage(src=".../og.jpg", alt="...", width=1200, height=630),
        og_image=OgImage(url=".../og.jpg", width=1200, height=630),
        json_ld=({"@context": "https://schema.org", ...},),   # dicts or raw JSON strings
    )
    page = render_editorial_page(meta, body_html, in_short=None, ladder=True)

All ArticleMeta strings are PLAIN TEXT; the shell escapes them. `body_html`
is trusted HTML the caller already escaped. Its contract:

- A run of `<section class="gg-blog-section">` blocks. Each `<h2>` becomes a
  Contents entry and is numbered 01, 02, ... by CSS; h2/h3 get stable ids
  (slug of their text) unless they already have one. A section with class
  `gg-references` is styled as sources and left out of Contents/numbering.
- `<!--GG:IN_SHORT-->` places the "In short" list; without the marker it
  goes first. `<!--GG:LADDER-->` places the ladder; without it, the ladder
  goes right before the references section (or at the end).
- Styled building blocks: `.gg-article-img-inline` (inline image),
  `.gg-case-study` (sand aside), `.gg-subscribe-callout` (mid-body subscribe;
  see render_subscribe_callout), `figure.gg-fig` with `p.kick` and
  `figcaption` (figure frame; chart internals are the caller's extra_css).
  Wrap a figure in `<div class="slot" data-slot="name">` to get the mono
  figure type and a scroll target.

`in_short`: a sequence of Claim(text_html, href, link_label, section). The
dot next to a claim fills once the reader has passed h2 number `section`
(0-based). `ladder`: True = default lead line, a str = custom lead (plain
text), False = no ladder. Ladder prices and claims render from
data/pricing.json; never type a price into a generator. `contents=False`
hides the contents list (very short pages).

Analytics: get_ga4_head_snippet() (consent defaults + GA4) in the head, the
consent banner + legal footer at the end of the body, and, when
meta.track_article_events is true, the article events: article_scroll_depth
(25/50/75/100), article_deep_read (75%+ only, the funnel metric) and
article_cta_click for any element with data-event="article_cta_click"
(ladder buttons, subscribe links, header subscribe).
"""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Sequence

import pricing
from brand_tokens import (
    get_favicon_head_snippet,
    get_font_face_css,
    get_ga4_head_snippet,
    get_preload_hints,
)
from cookie_consent import get_consent_banner_html
from shared_header import GG_LOGO_SVG

SITE_URL = "https://gravelgodcycling.com"
SUBSTACK_URL = "https://gravelgodcycling.substack.com"
WORDS_PER_MINUTE = 250

NAV_LINKS = (
    ("/gravel-races/", "Races"),
    ("/products/training-plans/", "Training Plans"),
    ("/coaching/", "Coaching"),
    ("/articles/", "Articles"),
    ("/about/", "About"),
)

DEFAULT_LADDER_LEAD = (
    "See how we actually structure plans — polarized, race-specific, "
    "built for your life."
)

# Ladder destinations (fixed by Matt, 2026-10-08).
CUSTOM_PLAN_URL = "/products/training-plans/"
SEASON_PLAN_URL = "/season-plan/"
COACHING_URL = "/coaching/"


# ── Data types ────────────────────────────────────────────────


@dataclass(frozen=True)
class HeroImage:
    src: str
    alt: str
    width: int
    height: int


@dataclass(frozen=True)
class OgImage:
    url: str
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class Claim:
    """One "In short" line: a claim and the link to its proof."""

    text_html: str  # trusted HTML (entities allowed)
    href: str  # usually "#fig-..." or "#<h2 id>"
    link_label: str  # plain text, e.g. "See the graph · §01"
    section: int  # 0-based h2 index; the dot fills once it has been read


@dataclass(frozen=True)
class ArticleMeta:
    slug: str
    canonical_url: str
    title: str
    description: str
    headline: str
    date_published: date
    kicker: str = ""
    dek: str = ""
    byline: str = "Gravel God"
    robots: str = "index, follow"
    og_title: str | None = None
    og_description: str | None = None
    og_type: str = "article"
    og_image: OgImage | None = None
    hero: HeroImage | None = None
    json_ld: Sequence[dict | str] = field(default_factory=tuple)
    track_article_events: bool = True

    @property
    def date_display(self) -> str:
        d = self.date_published
        return f"{d:%B} {d.day}, {d.year}"


# ── Helpers ───────────────────────────────────────────────────


def esc(text: str) -> str:
    """Escape plain text for HTML text and double-quoted attributes."""
    return html.escape(str(text), quote=False).replace('"', "&quot;")


def _strip_tags(fragment: str) -> str:
    return re.sub(r"<[^>]+>", "", fragment)


def _slug(fragment: str) -> str:
    text = html.unescape(_strip_tags(fragment)).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:60]


def word_count(body_html: str) -> int:
    no_markup = re.sub(r"<(script|style|template)\b.*?</\1>", " ", body_html, flags=re.S)
    return len(re.sub(r"<[^>]+>", " ", no_markup).split())


def reading_minutes(body_html: str) -> int:
    return max(1, round(word_count(body_html) / WORDS_PER_MINUTE))


def add_heading_ids(body_html: str) -> tuple[str, list[tuple[str, str]]]:
    """Give every h2/h3 a stable id; return (html, contents).

    contents = [(id, label_html)] for each h2 outside the references section,
    in document order. Duplicate slugs get -2, -3 ...
    """
    used: set[str] = set(re.findall(r'\bid="([^"]+)"', body_html))
    contents: list[tuple[str, str]] = []
    ref_start = body_html.find("gg-references")

    def add(m: re.Match) -> str:
        tag, attrs, inner = m.group(1), m.group(2), m.group(3)
        idm = re.search(r'\bid="([^"]+)"', attrs)
        if idm:
            sid, out = idm.group(1), m.group(0)
        else:
            base = _slug(inner) or tag
            sid, n = base, 2
            while sid in used:
                sid, n = f"{base}-{n}", n + 1
            used.add(sid)
            out = f'<{tag}{attrs} id="{sid}">{inner}</{tag}>'
        in_refs = ref_start != -1 and m.start() > ref_start
        if tag == "h2" and not in_refs:
            contents.append((sid, _strip_tags(inner).strip()))
        return out

    out = re.sub(r"<(h2|h3)(\b[^>]*)>(.*?)</\1>", add, body_html, flags=re.S)
    return out, contents


def _number_word(n: int) -> str:
    words = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
    return words[n] if 0 <= n < len(words) else str(n)


def _cta_attrs(label: str) -> str:
    return f' data-event="article_cta_click" data-label="{esc(label)}"'


def _btn(href: str, text: str, label: str, extra_class: str = "") -> str:
    cls = f"btn {extra_class}".strip()
    return (
        f'<a class="{cls}" href="{esc(href)}"{_cta_attrs(label)}>{esc(text)} '
        '<span class="chev" aria-hidden="true">&rsaquo;</span></a>'
    )


# ── Blocks ────────────────────────────────────────────────────


def render_contents(contents: Sequence[tuple[str, str]]) -> str:
    items = "\n".join(f'  <li><a href="#{sid}">{label}</a></li>' for sid, label in contents)
    return f'<ol class="toc">\n{items}\n</ol>'


def render_in_short(claims: Sequence[Claim]) -> str:
    rows = "\n".join(
        f'    <li data-sec="{c.section}"><p>{c.text_html}</p>'
        f'<a class="ev" href="{esc(c.href)}">{esc(c.link_label)}</a></li>'
        for c in claims
    )
    return (
        '<div class="slot slot-summary" data-slot="summary">\n'
        '<aside class="inshort" aria-label="In short">\n'
        '  <p class="kick">In short</p>\n'
        f"  <ol>\n{rows}\n  </ol>\n"
        "</aside>\n</div>"
    )


def ladder_offers() -> list[dict]:
    """The three ladder rungs, every number read from data/pricing.json."""
    race = pricing.RACE_PLAN
    season = pricing.SEASON_PLAN
    coaching = pricing.PRICING["products"]["coaching"]
    return [
        {
            "key": "custom_plan",
            "kicker": "One race",
            "name": race["name"],
            "price": f'{race["weekly_rate_display"]}/week · capped at {race["cap_display"]}',
            "desc": (
                "One race, periodised to your date, in your TrainingPeaks calendar "
                f'within {race["delivery_hours"]} hours. {race["refund_window_days"]}-day refund.'
            ),
            "href": CUSTOM_PLAN_URL,
            "button": "Get a custom plan",
        },
        {
            "key": "season_plan",
            "kicker": "Whole year",
            "name": season["name"],
            "price": season["price_display"],
            "desc": (
                f'Every A/B/C race of the year, up to {season["max_weeks"]} weeks, '
                f'{_number_word(season["scheduled_rebuilds"])} scheduled rebuilds.'
            ),
            "href": SEASON_PLAN_URL,
            "button": "See the season plan",
        },
        {
            "key": "coaching",
            "kicker": "A human",
            "name": coaching["name"],
            "price": f'From {coaching["from_display"]} every {coaching["interval_weeks"]} weeks',
            "desc": coaching["summary"],
            "href": COACHING_URL,
            "button": "See coaching",
        },
    ]


def render_ladder(lead: str = DEFAULT_LADDER_LEAD) -> str:
    main, *pair = ladder_offers()

    def rung_text(o: dict) -> str:
        return (
            f'<span class="k">{esc(o["kicker"])}</span>\n'
            f'      <strong>{esc(o["name"])}</strong>\n'
            f'      <span class="price">{esc(o["price"])}</span>\n'
            f'      <span class="d">{esc(o["desc"])}</span>'
        )

    pair_html = "\n".join(
        f'    <div class="rung">\n      {rung_text(o)}\n'
        f'      {_btn(o["href"], o["button"], o["key"])}\n    </div>'
        for o in pair
    )
    return (
        '<div class="slot slot-ladder" data-slot="ladder">\n'
        '<aside class="ladder" aria-label="Training plans and coaching">\n'
        f'  <p class="lead">{esc(lead)}</p>\n'
        '  <div class="rung main">\n'
        f'    <div>\n      {rung_text(main)}\n    </div>\n'
        f'    {_btn(main["href"], main["button"], main["key"])}\n'
        "  </div>\n"
        f'  <div class="pair">\n{pair_html}\n  </div>\n'
        "</aside>\n</div>"
    )


def render_subscribe_callout(text_html: str, link_text: str, sub_name_html: str, label: str) -> str:
    """Mid-body subscribe block (.gg-subscribe-callout), tracked as article_cta_click."""
    return (
        '<div class="gg-subscribe-callout">\n'
        f"  <p>{text_html}</p>\n"
        f'  <a href="{SUBSTACK_URL}" target="_blank" rel="noopener"{_cta_attrs(label)}>{esc(link_text)} &rarr;</a>\n'
        f'  <p class="gg-sub-name">{sub_name_html}</p>\n'
        "</div>"
    )


def _logo() -> str:
    return GG_LOGO_SVG.replace('class="gg-logo-mark"', 'class="gg-logo" fill="currentColor"', 1)


def render_header() -> str:
    nav = "".join(f'<a href="{href}">{label}</a>' for href, label in NAV_LINKS)
    sub = (
        f'<a class="btn" href="{SUBSTACK_URL}"{_cta_attrs("substack_header")}>Subscribe '
        '<span class="chev" aria-hidden="true">&rsaquo;</span></a>'
    )
    return f"""<header class="site">
  <div class="in">
    <a class="brand" href="/">{_logo()}<span>Gravel God</span></a>
    <nav class="nav" aria-label="Site">{nav}</nav>
    {sub}
    <details class="menu">
      <summary>MENU</summary>
      <div class="drop">{nav}<a href="{SUBSTACK_URL}">Subscribe &rsaquo;</a></div>
    </details>
  </div>
</header>"""


def render_footer() -> str:
    nav = "".join(f'<a href="{href}">{label}</a>' for href, label in NAV_LINKS)
    return f"""<footer class="foot">
  <div class="in">
    <div>
      <h3>Slow, Mid, 38s</h3>
      <p class="pitch">More like this every week. Training science without the marketing. Race intel without the fluff.</p>
      <a class="btn" href="{SUBSTACK_URL}" target="_blank" rel="noopener"{_cta_attrs("substack_bottom")}>Subscribe to Slow, Mid, 38s <span class="chev" aria-hidden="true">&rsaquo;</span></a>
      <p class="fine">Free &mdash; Unsubscribe anytime</p>
    </div>
    <nav aria-label="Footer">{nav}<a href="{SUBSTACK_URL}">Substack</a></nav>
  </div>
  <div class="base"><span>&copy; Gravel God Cycling</span></div>
</footer>"""


def render_hero(meta: ArticleMeta, minutes: int) -> str:
    kick = f'      <p class="kick-top">{esc(meta.kicker)}</p>\n' if meta.kicker else ""
    dek = f'      <p class="dek">{esc(meta.dek)}</p>\n' if meta.dek else ""
    by = f"{esc(meta.byline)} &middot; {esc(meta.date_display)} &middot; {minutes} min read"
    img = ""
    cls = "frame hero"
    if meta.hero:
        h = meta.hero
        img = (
            f'\n    <figure class="hero-img"><img src="{esc(h.src)}" alt="{esc(h.alt)}" '
            f'width="{h.width}" height="{h.height}" loading="eager"></figure>'
        )
    else:
        cls += " no-img"
    return (
        f'  <div class="{cls}">\n    <div class="txt">\n{kick}'
        f"      <h1>{esc(meta.headline)}</h1>\n{dek}"
        f'      <p class="by">{by}</p>\n    </div>{img}\n  </div>'
    )


def _json_ld_script(block: dict | str) -> str:
    text = block if isinstance(block, str) else json.dumps(block, indent=2, ensure_ascii=False)
    text = text.replace("</", "<\\/")
    return f'  <script type="application/ld+json">{text}</script>'


def render_head(meta: ArticleMeta, extra_head: str = "", extra_css: str = "") -> str:
    lines = [
        '  <meta charset="UTF-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f'  <meta name="robots" content="{esc(meta.robots)}">',
        f"  <title>{esc(meta.title)}</title>",
        f'  <meta name="description" content="{esc(meta.description)}">',
        f'  <meta property="og:title" content="{esc(meta.og_title or meta.title)}">',
        f'  <meta property="og:description" content="{esc(meta.og_description or meta.description)}">',
        f'  <meta property="og:url" content="{esc(meta.canonical_url)}">',
        f'  <meta property="og:type" content="{esc(meta.og_type)}">',
    ]
    if meta.og_image:
        lines.append(f'  <meta property="og:image" content="{esc(meta.og_image.url)}">')
        if meta.og_image.width and meta.og_image.height:
            lines.append(f'  <meta property="og:image:width" content="{meta.og_image.width}">')
            lines.append(f'  <meta property="og:image:height" content="{meta.og_image.height}">')
    lines += [
        '  <meta property="og:site_name" content="Gravel God">',
        f'  <link rel="canonical" href="{esc(meta.canonical_url)}">',
        get_favicon_head_snippet().rstrip(),
    ]
    lines += [_json_ld_script(b) for b in meta.json_ld]
    lines += [get_ga4_head_snippet().rstrip(), "  " + get_preload_hints().strip()]
    if extra_head:
        lines.append(extra_head.rstrip())
    lines.append(f"  <style>\n{get_font_face_css()}\n{SHELL_CSS}\n{extra_css}\n  </style>")
    return "\n".join(lines)


def render_article_events_js(slug: str) -> str:
    """article_scroll_depth / article_deep_read (75%+) / article_cta_click."""
    s = json.dumps(slug)
    return f"""<script>
  // Article-specific GA4 events
  (function() {{
    // Scroll depth tracking (25%, 50%, 75%, 100%)
    var depths = [25, 50, 75, 100];
    var fired = {{}};
    function getScrollPercent() {{
      var h = document.documentElement;
      var b = document.body;
      var st = window.pageYOffset || h.scrollTop || b.scrollTop || 0;
      var sh = Math.max(h.scrollHeight, b.scrollHeight) - Math.max(h.clientHeight, b.clientHeight);
      return sh > 0 ? Math.round((st / sh) * 100) : 0;
    }}
    window.addEventListener('scroll', function() {{
      var pct = getScrollPercent();
      for (var i = 0; i < depths.length; i++) {{
        if (pct >= depths[i] && !fired[depths[i]]) {{
          fired[depths[i]] = true;
          if (typeof gtag === 'function') {{
            gtag('event', 'article_scroll_depth', {{
              'article_slug': {s},
              'depth_threshold': depths[i]
            }});
            // Fire separate deep-read event at 75%+ for funnel tracking
            if (depths[i] >= 75) {{
              gtag('event', 'article_deep_read', {{
                'article_slug': {s},
                'depth_threshold': depths[i]
              }});
            }}
          }}
        }}
      }}
    }}, {{passive: true}});

    // CTA click tracking
    document.querySelectorAll('[data-event="article_cta_click"]').forEach(function(el) {{
      el.addEventListener('click', function() {{
        if (typeof gtag === 'function') {{
          gtag('event', 'article_cta_click', {{
            'article_slug': {s},
            'cta_label': el.getAttribute('data-label') || 'unknown'
          }});
        }}
      }});
    }});
  }})();
  </script>"""


# Contents scrollspy: read / current / ahead dots, the phone bar's label,
# and the "In short" dots. Progressive enhancement only: everything is
# visible and every link works without it.
SHELL_JS = """<script>
(function(){
  var heads=[].slice.call(document.querySelectorAll('#article section.gg-blog-section:not(.gg-references) h2'));
  var lists=[].slice.call(document.querySelectorAll('ol.toc')).map(function(ol){return [].slice.call(ol.children);});
  var claims=[].slice.call(document.querySelectorAll('.inshort li'));
  var now=document.getElementById('now'), mini=document.getElementById('mini');
  var dots=mini?heads.map(function(){var i=document.createElement('i'); mini.appendChild(i); return i;}):[];
  var tm=document.getElementById('tocm');
  if(tm) tm.addEventListener('click',function(e){ if(e.target.closest('ol.toc a')) tm.open=false; });
  function update(){
    var line=innerHeight*0.35, cur=-1;
    heads.forEach(function(h,i){ if(h.getBoundingClientRect().top<line) cur=i; });
    lists.forEach(function(list){ list.forEach(function(li,i){
      li.classList.toggle('read',i<cur); li.classList.toggle('cur',i===cur);
    });});
    dots.forEach(function(d,i){ d.className=i<cur?'read':(i===cur?'cur':''); });
    claims.forEach(function(li){ li.classList.toggle('read',+li.dataset.sec<cur); });
    if(now) now.textContent=cur<0?'Intro':String(cur+1).padStart(2,'0')+'  '+heads[cur].textContent;
  }
  addEventListener('scroll',update,{passive:true}); addEventListener('resize',update); update();
})();
</script>"""


# ── Page ──────────────────────────────────────────────────────

IN_SHORT_MARKER = "<!--GG:IN_SHORT-->"
LADDER_MARKER = "<!--GG:LADDER-->"
_REFERENCES_RE = re.compile(r'<section class="gg-blog-section gg-references"')


def _place(body: str, marker: str, block: str, *, default: str) -> str:
    if marker in body:
        return body.replace(marker, block, 1)
    if default == "start":
        return block + "\n" + body
    m = _REFERENCES_RE.search(body)
    if m:
        return body[: m.start()] + block + "\n" + body[m.start():]
    return body + "\n" + block


def render_editorial_page(
    meta: ArticleMeta,
    body_html: str,
    *,
    in_short: Sequence[Claim] | None = None,
    ladder: bool | str = True,
    contents: bool = True,
    extra_head: str = "",
    extra_css: str = "",
    extra_body_end: str = "",
) -> str:
    """Render a full editorial page. See the module docstring for the contract."""
    minutes = reading_minutes(body_html)
    body = body_html
    body = _place(body, IN_SHORT_MARKER, render_in_short(in_short) if in_short else "", default="start")
    if ladder:
        lead = ladder if isinstance(ladder, str) else DEFAULT_LADDER_LEAD
        body = _place(body, LADDER_MARKER, render_ladder(lead), default="refs")
    else:
        body = body.replace(LADDER_MARKER, "")
    body, toc = add_heading_ids(body)

    if contents and toc:
        toc_html = render_contents(toc)
        toc_bar = f"""  <details class="toc-m" id="tocm">
    <summary><span class="mini" id="mini" aria-hidden="true"></span><span class="now" id="now">Intro</span><span class="tog">Contents</span></summary>
    {toc_html}
  </details>
"""
        rail = f"""    <nav class="rail" aria-label="Contents">
      <div class="stick">
        <p class="lbl">Contents</p>
        {toc_html}
      </div>
    </nav>
"""
    else:
        toc_bar = rail = ""

    events = render_article_events_js(meta.slug) if meta.track_article_events else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{render_head(meta, extra_head, extra_css)}
</head>
<body>
{render_header()}

<main>
{render_hero(meta, minutes)}

{toc_bar}
  <div class="frame body-row">
{rail}    <article class="article" id="article">
{body.strip()}
    </article>
  </div>
</main>

{render_footer()}
{SHELL_JS}
{extra_body_end}
{events}
{get_consent_banner_html()}
</body>
</html>
"""


# ── CSS ───────────────────────────────────────────────────────
# Weights cap at 700: the self-hosted Source Serif 4 and Sometype Mono
# files cover 400-700, so 800 would only be faux-bolded.

SHELL_CSS = """
:root{
  --paper:#f5efe6; --sand:#ede4d8; --sand2:#e3d7c7;
  --ink:#2a211b; --ink2:#59473c; --ink3:#6b5a4e; --brown:#3a2e25;
  --teal:#178079; --teal-ink:#11635e; --gold:#7d6508; --cobalt:#4a78b0; --cobalt-deep:#3c6599;
  --caution:#ef6c00; --caution-text:#9e4400; --stop:#c62828; --hole:#1a1410; --fig:#fbf7f1;
  --mono:'Sometype Mono',ui-monospace,Menlo,monospace;
  --serif:'Source Serif 4',Georgia,serif;
  --chamfer:polygon(0 0,calc(100% - 12px) 0,100% 12px,100% 100%,12px 100%,0 calc(100% - 12px));
  --col:680px; --gap:56px; --side:min(280px,calc(50vw - 340px - 32px - 56px));
}
*{box-sizing:border-box}
html{scroll-padding-top:72px}
html,body{margin:0;background:var(--paper);color:var(--ink)}
body{font-family:var(--serif);-webkit-font-smoothing:antialiased;overflow-x:hidden}
a{color:inherit}
:focus-visible{outline:3px solid var(--cobalt);outline-offset:2px}

/* action = chamfer. Real buttons only. */
.btn{display:inline-flex;align-items:center;gap:8px;font:700 14px var(--mono);letter-spacing:.05em;text-transform:uppercase;text-decoration:none;
  color:#fff;background:var(--teal-ink);padding:12px 18px;clip-path:var(--chamfer);border:0;cursor:pointer;white-space:nowrap}
.btn .chev{font-size:17px;line-height:1}
.btn:hover{background:#0c4f4b}

/* state = dot. ahead: ring / read: filled ink / current: filled cobalt with halo */
.toc{list-style:none;margin:0;padding:0}
.toc li{position:relative;padding-left:26px}
.toc li::before{content:"";position:absolute;left:0;top:9px;width:14px;height:14px;border-radius:50%;box-shadow:inset 0 0 0 2.5px var(--ink3)}
.toc li.read::before{background:var(--ink);box-shadow:none}
.toc li.cur::before{background:var(--cobalt-deep);box-shadow:0 0 0 3px var(--paper),0 0 0 5.5px var(--cobalt-deep)}
.toc a{display:block;padding:5px 0;text-decoration:none;font:400 15px/1.35 var(--serif);color:var(--ink2)}
.toc a:hover{color:var(--ink);text-decoration:underline;text-underline-offset:3px}
.toc li.read a{color:var(--ink)}
.toc li.cur a{color:var(--ink);font-weight:700}

/* header */
.site{background:var(--brown);color:var(--paper)}
.site .in{max-width:1296px;margin:0 auto;padding:0 32px;height:64px;display:flex;align-items:center;gap:28px}
.brand{display:flex;align-items:center;gap:10px;text-decoration:none;font:700 16px var(--mono);letter-spacing:.06em;text-transform:uppercase;white-space:nowrap}
.gg-logo{height:34px;width:auto;display:block}
.nav{display:flex;gap:22px;margin-left:auto}
.nav a{font:700 14px var(--mono);letter-spacing:.04em;text-transform:uppercase;text-decoration:none;color:var(--paper);padding:8px 0}
.nav a:hover{text-decoration:underline;text-underline-offset:5px;text-decoration-thickness:3px}
.site .btn{background:var(--teal)}
.menu{display:none;position:relative;margin-left:auto}
.menu summary{list-style:none;font:700 14px var(--mono);letter-spacing:.06em;color:var(--paper);padding:9px 12px;box-shadow:inset 0 0 0 2px var(--paper);cursor:pointer}
.menu summary::-webkit-details-marker{display:none}
.menu .drop{position:absolute;right:0;top:46px;background:var(--brown);padding:8px 0;min-width:230px;z-index:30;box-shadow:0 12px 32px rgba(0,0,0,.3)}
.menu .drop a{display:block;padding:12px 18px;font:700 15px var(--mono);text-transform:uppercase;text-decoration:none;color:var(--paper)}

/* layout */
.frame{max-width:calc(var(--col) + 64px);margin:0 auto;padding:0 32px}

/* hero */
.hero{display:grid;grid-template-columns:minmax(0,1fr) 190px;column-gap:28px;padding-top:36px;padding-bottom:28px;align-items:start}
.hero.no-img{grid-template-columns:minmax(0,1fr)}
.kick-top{font:700 13px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--teal-ink);margin:0 0 14px}
h1{font:700 60px/1.0 var(--serif);letter-spacing:-.025em;margin:0 0 16px;font-optical-sizing:auto;text-wrap:balance}
.dek{font:italic 400 22px/1.4 var(--serif);color:var(--ink2);margin:0 0 16px;max-width:36em}
.by{font:500 14px var(--mono);letter-spacing:.02em;color:var(--ink2);margin:0}
.hero-img{margin:0}
.hero-img img{width:100%;height:auto;display:block;background:var(--sand)}

/* contents: phone/tablet sticky bar */
.toc-m{position:sticky;top:0;z-index:20;background:var(--sand);margin:0 0 28px}
.toc-m summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:12px;min-height:48px;padding:0 32px}
.toc-m summary::-webkit-details-marker{display:none}
.toc-m .mini{display:flex;gap:6px;flex:none}
.toc-m .mini i{width:10px;height:10px;border-radius:50%;box-shadow:inset 0 0 0 2px var(--ink3)}
.toc-m .mini i.read{background:var(--ink);box-shadow:none}
.toc-m .mini i.cur{background:var(--cobalt-deep);box-shadow:none;width:22px;border-radius:5px}
.toc-m .now{font:700 13px var(--mono);color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;flex:1}
.toc-m .tog{font:700 13px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--ink)}
.toc-m .tog::after{content:" +"}
.toc-m[open] .tog::after{content:" \\2212"}
.toc-m .toc{padding:4px 32px 14px}
.toc-m summary,.toc-m .toc{max-width:calc(var(--col) + 64px);margin-left:auto;margin-right:auto}
.toc-m .toc li.cur::before{box-shadow:0 0 0 3px var(--sand),0 0 0 5.5px var(--cobalt-deep)}
.rail{display:none}

/* article */
.article{counter-reset:blk;min-width:0}
.article p,.article li{font-size:20px;line-height:1.62}
.article p{margin:0 0 1.05em}
.gg-blog-section{margin:0}
.gg-blog-section:not(.gg-references) h2{counter-increment:blk}
.article h2{font:700 36px/1.12 var(--serif);letter-spacing:-.015em;margin:72px 0 22px;text-wrap:balance}
.article h2::before{content:counter(blk,decimal-leading-zero);display:block;font:700 14px var(--mono);letter-spacing:.1em;color:var(--ink3);margin-bottom:8px}
.article .gg-blog-section:first-of-type h2,.slot-summary + .gg-blog-section h2{margin-top:8px}
.gg-references h2::before{content:"Sources"}
.article h3{font:700 26px/1.2 var(--serif);margin:44px 0 14px}
.article h4{font:700 15px var(--mono);letter-spacing:.06em;text-transform:uppercase;margin:0 0 16px}
.gg-blog-section ul,.gg-blog-section ol{padding-left:1.2em;margin:0 0 1.1em}
.article li{margin:0 0 .45em}
.article li::marker{color:var(--ink3)}
.article blockquote{margin:0 0 1.05em;padding:0 0 0 20px;box-shadow:inset 4px 0 0 var(--ink3);font-style:italic}
sup{line-height:0}
sup a{font:700 13px var(--mono);text-decoration:none;color:var(--teal-ink);padding:0 2px}
sup a:hover{text-decoration:underline}
.gg-article-img-inline{margin:28px 0 30px}
.gg-article-img-inline img{display:block;width:100%;max-width:440px;height:auto;margin:0 auto}
.gg-case-study{background:var(--sand);padding:24px 24px 10px;margin:0 0 28px}
.gg-case-study p,.gg-case-study li{font-size:18px}
.gg-subscribe-callout{background:var(--brown);color:var(--paper);padding:28px 30px;margin:56px 0 0}
.gg-subscribe-callout p{font-size:20px;margin:0 0 18px}
.gg-subscribe-callout a{display:inline-block;font:700 14px var(--mono);letter-spacing:.05em;text-transform:uppercase;text-decoration:none;color:#fff;background:var(--teal);padding:12px 18px;clip-path:var(--chamfer)}
.gg-subscribe-callout .gg-sub-name{font:700 13px var(--mono);letter-spacing:.05em;text-transform:uppercase;margin:16px 0 0;color:#e2d6c7}
.gg-references p{font:500 15px/1.55 var(--mono);color:var(--ink2)}

/* figures: frame + caption; chart internals belong to the page */
.article .kick,.kick{font:700 13px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--ink3);margin:0 0 10px}
.slot{font-family:var(--mono)}
.slot figure{margin:0}
.gg-fig{background:var(--fig);padding:24px 26px;margin:0}
.gg-fig figcaption{font:500 15px/1.5 var(--mono);color:var(--ink2);margin:14px 0 0}

/* in short: claims that link to their proof; dot fills once that section is read */
.slot-summary{margin:0 0 40px}
.inshort{background:var(--sand);padding:20px 22px 6px}
.inshort ol{list-style:none;margin:0;padding:0}
.article .inshort li{position:relative;padding:0 0 18px 30px;font:400 18px/1.45 var(--serif);margin:0}
.inshort li::before{content:"";position:absolute;left:0;top:5px;width:16px;height:16px;border-radius:50%;box-shadow:inset 0 0 0 2.5px var(--ink3)}
.inshort li.read::before{background:var(--ink);box-shadow:none}
.article .inshort li p{margin:0 0 4px;font-size:18px;line-height:1.45}
.inshort .ev{font:700 13px/1.4 var(--mono);color:var(--cobalt-deep);text-decoration:underline;text-underline-offset:3px;text-decoration-thickness:2px}
.inshort .ev:hover{color:var(--ink)}

/* ladder: custom plan leads, then season, then coaching */
.slot-ladder{margin:56px 0 10px}
.article .ladder .lead{font:600 25px/1.3 var(--serif);margin:0 0 20px}
.rung{color:var(--ink)}
.rung .k{display:block;font:700 12px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--ink3);margin-bottom:6px}
.rung strong{display:block;font:700 26px/1.1 var(--serif)}
.rung .price{display:block;font:700 17px var(--mono);margin:8px 0}
.rung .d{display:block;font:400 17px/1.45 var(--serif);margin:0 0 16px}
.rung.main{background:var(--gold);color:#fff;padding:26px 26px 24px;display:grid;grid-template-columns:minmax(0,1fr) auto;column-gap:24px;align-items:end}
.rung.main .k{color:#f4ead0}
.rung.main strong{font-size:32px}
.rung.main .d{margin:0;max-width:30em}
.rung.main .btn{background:var(--paper);color:var(--ink)}
.rung.main .btn:hover{background:#fff}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:6px}
.pair .rung{background:var(--sand);padding:22px;display:flex;flex-direction:column}
.pair .rung .d{flex:1}
.pair .btn{background:var(--ink);align-self:flex-start}
.pair .btn:hover{background:#000}

/* footer */
.foot{background:var(--brown);color:var(--paper);margin-top:56px}
.foot .in{max-width:1296px;margin:0 auto;padding:44px 32px 30px;display:grid;grid-template-columns:1.4fr 1fr;gap:40px}
.foot h3{font:700 30px/1.15 var(--serif);margin:0 0 8px}
.foot .pitch{font:400 19px/1.45 var(--serif);color:var(--paper);margin:0 0 18px;max-width:34em}
.foot .fine{font:700 13px var(--mono);letter-spacing:.05em;text-transform:uppercase;color:#e2d6c7;margin:14px 0 0}
.foot .btn{background:var(--teal)}
.foot nav{display:grid;grid-template-columns:1fr 1fr;gap:6px 24px;align-content:start}
.foot nav a{font:700 14px var(--mono);text-transform:uppercase;text-decoration:none;padding:6px 0}
.foot .base{max-width:1296px;margin:0 auto;padding:0 32px 28px;font:700 12px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:#d9cbbb}

/* wide: open column; quiet contents in the left margin, "In short" in the right */
@media (min-width:1280px){
  .frame{max-width:none;display:grid;grid-template-columns:minmax(0,1fr) var(--col) minmax(0,1fr);column-gap:var(--gap)}
  .hero,.hero.no-img{grid-template-columns:minmax(0,1fr) var(--col) minmax(0,1fr)}
  .hero .txt{grid-column:2}
  .hero-img{grid-column:3;width:var(--side);margin-top:6px}
  .toc-m{display:none}
  .body-row{padding-top:12px}
  .rail{display:block;grid-column:1;justify-self:end;width:var(--side)}
  .rail .stick{position:sticky;top:28px}
  .rail .lbl{font:700 13px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--ink3);margin:6px 0 10px}
  .article{grid-column:2}
  .slot-summary{float:right;width:var(--side);margin:0 calc(-1 * (var(--side) + var(--gap))) 20px 0}
  .inshort{background:none;padding:0}
  .slot-summary + .gg-blog-section h2{margin-top:0}
}
@media (max-width:900px){
  .nav,.site .btn{display:none}
  .menu{display:block}
}
@media (max-width:640px){
  .site .in{padding:0 16px;height:58px;gap:12px}
  .frame{padding:0 16px}
  .hero{grid-template-columns:1fr;padding-top:22px;padding-bottom:20px}
  .kick-top{margin-bottom:10px}
  h1{font-size:42px;margin-bottom:12px}
  .dek{font-size:19px;margin-bottom:12px}
  .hero-img{margin-top:18px}
  .hero-img img{aspect-ratio:4/3;object-fit:cover;object-position:50% 30%}
  .toc-m{margin:0 0 24px}
  .toc-m summary{padding:0 16px}
  .toc-m .toc{padding:4px 16px 14px}
  .toc-m .mini{gap:5px}
  .article p,.article li{font-size:18px;line-height:1.6}
  .article h2{font-size:29px;margin-top:56px}
  .article h3{font-size:23px}
  .gg-case-study{padding:20px 16px 8px}
  .gg-case-study p,.gg-case-study li{font-size:17px}
  .inshort{padding:18px 16px 4px}
  .article .inshort li,.article .inshort li p{font-size:17px}
  .gg-fig{padding:18px 14px}
  .article .ladder .lead{font-size:21px}
  .rung.main{grid-template-columns:1fr;padding:22px 18px}
  .rung.main strong{font-size:28px}
  .rung.main .d{margin-bottom:16px}
  .pair{grid-template-columns:1fr}
  .foot .in{grid-template-columns:1fr;padding:34px 16px 24px}
  .foot .base{padding:0 16px 24px}
  .gg-subscribe-callout{padding:22px 18px}
}
h2[id],h3[id],[data-slot],figure[id]{scroll-margin-top:72px}
"""
