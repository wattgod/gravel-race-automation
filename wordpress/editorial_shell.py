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
        hero=HeroImage(src=".../og.jpg", alt="...", width=1200, height=630, layout="wide"),
        og_image=OgImage(url=".../og.jpg", width=1200, height=630),
        json_ld=({"@context": "https://schema.org", ...},),   # dicts or raw JSON strings
    )
    page = render_editorial_page(meta, body_html, in_short=None, ladder=True)

All ArticleMeta strings are PLAIN TEXT; the shell escapes them. `body_html`
is trusted HTML the caller already escaped. Its contract:

- A run of section blocks: `<section class="gg-blog-section">` or
  `<div class="gg-blog-section">` (roundups). One rule (see outline()):
  every h2 inside a section and not inside a `gg-references` element is a
  contents heading. It gets a Contents entry, a `data-toc` attribute, the
  01, 02, ... number (CSS) and a scrollspy dot (JS). h2/h3 get stable ids
  (slug of their text) unless they already have one. The `gg-references`
  block is styled as sources.
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
data/pricing.json; never type a price into a generator. The contents list
(rail + sticky bar) renders only when the body has at least
MIN_CONTENTS_HEADINGS (2) contents headings; `contents=False` hides it
regardless. On wide screens only one margin rail shows at a time: with "In
short" beside the opening, the contents rail appears once it has scrolled
past (SHELL_JS; without JS both show). Ladder buttons carry
data-cta="custom_plan|season_plan|coaching", so a page that also includes
blog_tracking.get_plan_intent_tracking_script() (pass it in extra_body_end)
gets the canonical cta_click for them.

Essay components (opt-in; a page that uses none renders byte-for-byte as
before, with no extra CSS or JS):

- `Picture` / `render_picture()`: <picture> with WebP + @2x, a PNG/JPEG
  fallback and an optional art-directed phone crop (`PhoneCrop`, used below
  PHONE_MAX_PX). `Picture.from_stem("img/scene-x", alt, w, h, phone=(w, h))`
  follows the img/ naming: x.png, x@2x.png, x.webp, x@2x.webp, x-m.webp,
  x-m@2x.webp. `HeroImage.from_picture(pic)` puts one in the hero.
- `EssayFigure`: a picture (the still), an optional `PlayOnceVideo` (muted,
  playsinline; plays once when half visible, holds its last frame, then
  offers a replay button; the still without JS or under
  prefers-reduced-motion, and the poster is attached only when the clip
  shows) and an optional caption. `width="column"` runs the full column instead of 440px.
- `SvgFigure`: trusted inline SVG with kicker, title and caption; with
  `phone_svg` phones get that overview plus a "Zoom in" toggle that reveals
  the detailed SVG in a sideways-scrolling region.
- `DataTable`: a sortable table (buttons in the headers, aria-sort, a
  polite live region) on wide screens and one card per row below 640px.
  `TableRow.links` are per-row citation links shown after the last cell.
- Chart draw-in: put `data-draw-in` on a figure and `data-draw="grow|
  grow-x|fade|rise|wipe"` on its parts. Stagger with `--draw-i` (an index,
  110ms apart; inherited, so set it on a column) and `--draw-at` (a base
  delay); `--draw-dur` overrides the duration. At rest the chart is
  complete: only the shell JS empties it while it is off-screen and plays it
  once at 15% visible, so without JS or with reduced motion nothing moves.

Placing them: pass `figures=[...]` to render_editorial_page. Each figure
sets `marker` (replaces `<!--GG:FIGURE name-->` in the body) or `after` (an
exact snippet of the body source, entities as written, found exactly once;
the figure goes after the outermost paragraph, list, quote, heading, table or
figure that contains it, never inside an <li> or a blockquote). Adding a
figure is one line in the article source, e.g.
`EssayFigure(Picture.from_stem("img/meme", "alt", 1200, 900), after="lmao.)")`.
Unknown or unused markers raise ValueError. The essay JS is one body script
marked ESSAY_JS_MARKER; it's emitted only on pages that use a video, an SVG
zoom, a table or data-draw-in (a blog page that opts in must allow that
marker in scripts/validate_blog_content.py).

`in_short_on_phone="after_intro"` (with in_short) shows "In short" after the
first section on phones, so the opening paragraph gets the first screen.

`ArticleMeta.show_read_time`: True (default) puts "N min read" in the hero
byline; previews, recaps and roundups that aren't read top to bottom pass
False.

`ArticleMeta.byline_date`: None (default) shows date_display in the byline,
"" hides the date, any other string is shown as given.

`HeroImage.layout`: "portrait" (default) sits in the right margin beside the
headline; "wide" runs the full reading column under it (1200x630 OG cards).

Class hooks: `ArticleMeta.hero_class` adds classes to the hero frame
(`<div class="frame hero ...">`), `HeroImage.figure_class` to the hero
`<figure class="hero-img ...">`; blog pages pass "gg-blog-hero" and
"gg-blog-hero-img". Plain class names only (ValueError otherwise).

Validator hooks: HERO_FRAME_CLASS starts every hero frame's class list and
SHELL_BODY_SCRIPT_MARKERS identify the shell's own body scripts (header
hamburger JS, contents scrollspy); scripts/validate_blog_content.py reads
both from here.

Header: shared_header.get_site_header_html(meta.nav_active) and its JS, so
the nav and its dropdowns are single-sourced with the rest of the site; the
shell only restyles it with CSS and adds a Subscribe button (render_header
raises if shared_header's markup changes so the button can't be placed).
The footer nav is the header's top-level links (header_nav_links()), so the
two can't drift either.

Warnings: add_heading_ids() warns (UserWarning) when the body has <h2>s but
none of them is a contents heading, i.e. the body broke the section rule.

Analytics: get_ga4_head_snippet() (consent defaults + GA4) in the head, the
consent banner + legal footer at the end of the body, and the article
events when meta.tracks_article_events: article_scroll_depth (25/50/75/100),
article_deep_read (75%+ only, the funnel metric) and article_cta_click for
any element with data-event="article_cta_click". track_article_events=None
(default) means on only when robots is indexable, so noindex blog pages never
pollute the article funnel; True/False forces it.
"""
from __future__ import annotations

import html
import json
import re
import warnings
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from typing import Literal, Sequence

import pricing
from brand_tokens import (
    get_favicon_head_snippet,
    get_font_face_css,
    get_ga4_head_snippet,
    get_preload_hints,
)
from cookie_consent import get_consent_banner_html
from shared_header import get_site_header_html, get_site_header_js

SITE_URL = "https://gravelgodcycling.com"
SUBSTACK_URL = "https://gravelgodcycling.substack.com"
WORDS_PER_MINUTE = 250

DEFAULT_LADDER_LEAD = (
    "See how we actually structure plans — polarized, race-specific, "
    "built for your life."
)

# Ladder destinations (fixed by Matt, 2026-10-08).
CUSTOM_PLAN_URL = "/products/training-plans/"
SEASON_PLAN_URL = "/season-plan/"
COACHING_URL = "/coaching/"


# ── Data types ────────────────────────────────────────────────


HeroLayout = Literal["portrait", "wide"]


@dataclass(frozen=True)
class HeroImage:
    """The hero picture. layout="portrait" (default) sits in the right margin
    beside the headline; layout="wide" runs the full reading column under the
    headline, for 1200x630 OG-style images (blog previews, recaps)."""

    src: str
    alt: str
    width: int
    height: int
    layout: HeroLayout = "portrait"
    # Extra classes on the <figure class="hero-img ...">, e.g. "gg-blog-hero-img"
    # (the hook the blog validator and index tooling key on).
    figure_class: str = ""
    # A responsive <picture> (WebP, @2x, phone crop) instead of the plain
    # <img>; use HeroImage.from_picture().
    picture: "Picture | None" = None

    def __post_init__(self) -> None:
        if self.layout not in ("portrait", "wide"):
            raise ValueError(f"HeroImage.layout must be 'portrait' or 'wide', not {self.layout!r}")
        _check_class_list(self.figure_class, "HeroImage.figure_class")

    @classmethod
    def from_picture(cls, pic: "Picture", layout: HeroLayout = "portrait", figure_class: str = "") -> "HeroImage":
        return cls(src=pic.src, alt=pic.alt, width=pic.width, height=pic.height,
                   layout=layout, figure_class=figure_class, picture=pic)


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
    # None = on only for indexable pages, so noindex blog previews/recaps
    # never fire article_* events. Pass True/False to force it.
    track_article_events: bool | None = None
    # Which shared-header item is current: "races", "products", "services",
    # "articles", "about" or None.
    nav_active: str | None = "articles"
    # "N min read" in the hero byline. Articles keep it; previews, recaps
    # and roundups (scanned, not read through) can turn it off.
    show_read_time: bool = True
    # Extra classes on the hero frame (<div class="frame hero ...">), e.g.
    # "gg-blog-hero" for blog previews and recaps.
    hero_class: str = ""
    # The date in the hero byline. None (default) = date_display (e.g.
    # "March 26, 2026"); "" = no date; any other string is shown as given.
    byline_date: str | None = None

    def __post_init__(self) -> None:
        _check_class_list(self.hero_class, "ArticleMeta.hero_class")

    @property
    def is_indexable(self) -> bool:
        return "noindex" not in self.robots.lower()

    @property
    def tracks_article_events(self) -> bool:
        if self.track_article_events is None:
            return self.is_indexable
        return self.track_article_events

    @property
    def date_display(self) -> str:
        d = self.date_published
        return f"{d:%B} {d.day}, {d.year}"

    @property
    def byline_date_text(self) -> str:
        """The byline's date text: byline_date if given, else date_display."""
        return self.date_display if self.byline_date is None else self.byline_date


def _check_class_list(value: str, name: str) -> None:
    """Extra-class fields take plain class names separated by spaces."""
    if not re.fullmatch(r"[A-Za-z0-9_ -]*", value):
        raise ValueError(f"{name} must be class names separated by spaces, not {value!r}")


# ── Helpers ───────────────────────────────────────────────────


def esc(text: str) -> str:
    """Escape plain text for HTML text and double-quoted attributes."""
    return html.escape(str(text), quote=False).replace('"', "&quot;")


# One tag's attributes, allowing ">" inside quoted values.
_ATTRS = r"""(?:[^>"']|"[^"]*"|'[^']*')*"""


def _strip_tags(fragment: str) -> str:
    return re.sub(rf"<{_ATTRS}>", "", fragment)


def _slug(fragment: str) -> str:
    text = html.unescape(_strip_tags(fragment)).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:60]


def word_count(body_html: str) -> int:
    no_markup = re.sub(r"<(script|style|template)\b.*?</\1>", " ", body_html, flags=re.S)
    return len(re.sub(r"<[^>]+>", " ", no_markup).split())


def reading_minutes(body_html: str) -> int:
    return max(1, round(word_count(body_html) / WORDS_PER_MINUTE))


# ── Sections: the one rule ────────────────────────────────────
# A *section* is any <section> or <div> whose class list has gg-blog-section
# (articles and previews use <section>, roundups use <div>). Anything inside
# an element whose class list has gg-references is the *references* block.
# A *contents heading* is an h2 inside a section and not inside references.
# Contents entries, the 01/02/... numbers (CSS: h2[data-toc]) and the
# scrollspy (JS: h2[data-toc]) all follow from that one decision, made here.

_CLASS_RE = re.compile(r"[^\s]+")


def _classes(attrs: list[tuple[str, str | None]]) -> set[str]:
    for name, value in attrs:
        if name == "class" and value:
            return set(_CLASS_RE.findall(value))
    return set()


@dataclass(frozen=True)
class Outline:
    references_start: int | None  # offset of the first references block
    toc_h2_starts: frozenset[int]  # offsets of the "<h2" of contents headings


class _OutlineParser(HTMLParser):
    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=True)
        self._line_starts = [0]
        for m in re.finditer("\n", text):
            self._line_starts.append(m.end())
        self._stack: list[tuple[str, bool, bool]] = []  # (tag, is_section, is_refs)
        self.references_start: int | None = None
        self.toc_h2_starts: set[int] = set()

    def _offset(self) -> int:
        line, col = self.getpos()
        return self._line_starts[line - 1] + col

    def handle_starttag(self, tag, attrs):
        if tag in ("section", "div"):
            cls = _classes(attrs)
            refs = "gg-references" in cls
            if refs and self.references_start is None and not any(r for _, _, r in self._stack):
                self.references_start = self._offset()
            self._stack.append((tag, "gg-blog-section" in cls, refs))
        elif tag == "h2":
            in_section = any(sec for _, sec, _ in self._stack)
            in_refs = any(r for _, _, r in self._stack)
            if in_section and not in_refs:
                self.toc_h2_starts.add(self._offset())

    def handle_endtag(self, tag):
        if tag in ("section", "div"):
            for i in range(len(self._stack) - 1, -1, -1):
                if self._stack[i][0] == tag:
                    del self._stack[i:]
                    break


def outline(body_html: str) -> Outline:
    """Apply the section rule to body_html (see the comment above)."""
    parser = _OutlineParser(body_html)
    parser.feed(body_html)
    parser.close()
    return Outline(parser.references_start, frozenset(parser.toc_h2_starts))


def add_heading_ids(body_html: str) -> tuple[str, list[tuple[str, str]]]:
    """Give every h2/h3 a stable id and mark contents headings; return (html, contents).

    contents = [(id, label_html)] for each contents heading (see the section
    rule), in document order; those h2s also get a data-toc attribute, which
    the CSS numbers and the scrollspy follows. Duplicate slugs get -2, -3 ...
    """
    used: set[str] = set(re.findall(r'\bid="([^"]+)"', body_html))
    toc_starts = outline(body_html).toc_h2_starts
    contents: list[tuple[str, str]] = []

    def add(m: re.Match) -> str:
        tag, attrs, inner = m.group(1), m.group(2), m.group(3)
        idm = re.search(r'\bid="([^"]+)"', attrs)
        if idm:
            sid = idm.group(1)
        else:
            base = _slug(inner) or tag
            sid, n = base, 2
            while sid in used:
                sid, n = f"{base}-{n}", n + 1
            used.add(sid)
            attrs = f'{attrs} id="{sid}"'
        if tag == "h2" and m.start() in toc_starts:
            contents.append((sid, _strip_tags(inner).strip()))
            if "data-toc" not in attrs:
                attrs += " data-toc"
        return f"<{tag}{attrs}>{inner}</{tag}>"

    out = re.sub(rf"<(h2|h3)\b({_ATTRS})>(.*?)</\1>", add, body_html, flags=re.S | re.I)
    if not contents and re.search(r"<h2\b", body_html, re.I):
        warnings.warn(
            "body has <h2> headings but none is a contents heading: wrap them in "
            '<section class="gg-blog-section"> (or a div with that class) outside gg-references',
            UserWarning,
            stacklevel=2,
        )
    return out, contents


def _number_word(n: int) -> str:
    words = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
    return words[n] if 0 <= n < len(words) else str(n)


def _cta_attrs(label: str) -> str:
    return f' data-event="article_cta_click" data-label="{esc(label)}"'


def _btn(href: str, text: str, label: str, extra_class: str = "", *, cta: str | None = None) -> str:
    """A chamfered button. cta= adds data-cta, which blog_tracking's plan-intent
    script (a[data-cta][href*=...]) picks up as the canonical cta_click."""
    cls = f"btn {extra_class}".strip()
    cta_attr = f' data-cta="{esc(cta)}"' if cta else ""
    return (
        f'<a class="{cls}" href="{esc(href)}"{_cta_attrs(label)}{cta_attr}>{esc(text)} '
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
        f'      {_btn(o["href"], o["button"], o["key"], cta=o["key"])}\n    </div>'
        for o in pair
    )
    return (
        '<div class="slot slot-ladder" data-slot="ladder">\n'
        '<aside class="ladder" aria-label="Training plans and coaching">\n'
        f'  <p class="lead">{esc(lead)}</p>\n'
        '  <div class="rung main">\n'
        f'    <div>\n      {rung_text(main)}\n    </div>\n'
        f'    {_btn(main["href"], main["button"], main["key"], cta=main["key"])}\n'
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


_HEADER_SUBSCRIBE_ANCHOR = '<button class="gg-hamburger"'


def render_header(active: str | None = "articles") -> str:
    """The site's shared header (shared_header.get_site_header_html), so nav
    links and dropdowns stay single-sourced; the shell restyles it with CSS
    and adds its Subscribe button beside the nav.

    Raises RuntimeError if the shared header no longer contains the
    hamburger button the Subscribe button is placed before."""
    header = get_site_header_html(active)
    if _HEADER_SUBSCRIBE_ANCHOR not in header:
        raise RuntimeError(
            f"shared_header.get_site_header_html() no longer contains {_HEADER_SUBSCRIBE_ANCHOR!r}; "
            "update editorial_shell._HEADER_SUBSCRIBE_ANCHOR so the Subscribe button still renders"
        )
    sub = (
        f'<a class="btn gg-hdr-sub" href="{SUBSTACK_URL}"{_cta_attrs("substack_header")}>Subscribe '
        '<span class="chev" aria-hidden="true">&rsaquo;</span></a>\n    '
    )
    return header.replace(_HEADER_SUBSCRIBE_ANCHOR, sub + _HEADER_SUBSCRIBE_ANCHOR, 1)


class _HeaderNavParser(HTMLParser):
    """Collects the top-level links of the desktop nav (.gg-site-header-nav),
    skipping the dropdown entries."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._stack: list[tuple[str, set[str]]] = []
        self._href: str | None = None
        self._text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def _inside(self, cls: str) -> bool:
        return any(cls in c for _, c in self._stack)

    def handle_starttag(self, tag, attrs):
        if tag == "a" and self._inside("gg-site-header-nav") and not self._inside("gg-site-header-dropdown"):
            self._href = dict(attrs).get("href") or ""
            self._text = []
        if tag not in ("a", "img", "br", "path", "meta", "link", "input"):
            self._stack.append((tag, _classes(attrs)))

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None
            return
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                break


def header_nav_links() -> tuple[tuple[str, str], ...]:
    """(href, label) for each top-level item of the shared header's desktop
    nav, in order, read from shared_header.get_site_header_html(). The footer
    renders these, so header and footer navs come from one source."""
    parser = _HeaderNavParser()
    parser.feed(get_site_header_html(None))
    parser.close()
    if not parser.links:
        raise RuntimeError("no top-level links found in shared_header.get_site_header_html()")
    return tuple(parser.links)


def render_footer() -> str:
    nav = "".join(f'<a href="{esc(href)}">{esc(label.title())}</a>' for href, label in header_nav_links())
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


# Every hero frame's class list starts with this (render_hero); the blog
# validator recognises shell pages by it.
HERO_FRAME_CLASS = "frame hero"


def _join_classes(*parts: str) -> str:
    return " ".join(p for part in parts for p in part.split())


# Long words in the h1. The h1 never breaks a word except as a last resort
# (overflow-wrap), so a headline whose longest word is wider than the column
# gets a tier class that sizes the h1 to the column (CSS: h1.h1-long-N).
# Width is estimated in "units" of one Source Serif 4 Bold lowercase glyph
# (~0.55em incl. the h1's -0.025em tracking); capitals are ~1.2 units.
# Each tier's CSS --h1-w is its ceiling in em (units x 0.55), so every word
# in the tier fits. Words of 13 units or less fit the 42px phone h1 at 360px
# (328px column) and the 60px desktop h1 beside a portrait image (462px), so
# ordinary titles get no class and keep their sizes.
H1_LONG_WORD_FITS = 13.0
H1_LONG_TIERS: tuple[tuple[float, str], ...] = (
    (15.0, "h1-long-1"),
    (17.0, "h1-long-2"),
    (19.5, "h1-long-3"),
    (float("inf"), "h1-long-4"),  # >23 units can still hit overflow-wrap
)
_H1_WORD_SPLIT = re.compile(r"[\s\u00ad\-\u2010-\u2015/]+")


def h1_word_units(word: str) -> float:
    return sum(1.2 if c.isupper() else 1.0 for c in word)


def h1_long_word_class(headline: str) -> str:
    """The h1 tier class for a headline's longest word, or "" if it fits."""
    units = max((h1_word_units(w) for w in _H1_WORD_SPLIT.split(headline)), default=0.0)
    if units <= H1_LONG_WORD_FITS:
        return ""
    return next(cls for limit, cls in H1_LONG_TIERS if units <= limit)


def render_hero(meta: ArticleMeta, minutes: int) -> str:
    kick = f'      <p class="kick-top">{esc(meta.kicker)}</p>\n' if meta.kicker else ""
    dek = f'      <p class="dek">{esc(meta.dek)}</p>\n' if meta.dek else ""
    by = esc(meta.byline)
    if meta.byline_date_text:
        by += f" &middot; {esc(meta.byline_date_text)}"
    if meta.show_read_time:
        by += f" &middot; {minutes} min read"
    img = ""
    cls = HERO_FRAME_CLASS
    if meta.hero:
        h = meta.hero
        if h.layout == "wide":
            cls += " wide"
        fig_cls = _join_classes("hero-img", h.figure_class)
        if h.picture:
            inner = render_picture(h.picture, eager=True)
        else:
            inner = (f'<img src="{esc(h.src)}" alt="{esc(h.alt)}" '
                     f'width="{h.width}" height="{h.height}" loading="eager">')
        img = f'\n    <figure class="{fig_cls}">{inner}</figure>'
    else:
        cls += " no-img"
    cls = _join_classes(cls, meta.hero_class)
    long_cls = h1_long_word_class(meta.headline)
    h1_open = f'<h1 class="{long_cls}">' if long_cls else "<h1>"
    return (
        f'  <div class="{cls}">\n    <div class="txt">\n{kick}'
        f"      {h1_open}{esc(meta.headline)}</h1>\n{dek}"
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


# Substrings that identify the shell's own body <script>s, so a validator
# can allow exactly these (tests pin each to one script of a rendered page).
HEADER_JS_MARKER = "getElementById('gg-hamburger')"  # shared_header.get_site_header_js()
SCROLLSPY_JS_MARKER = "h2[data-toc]"  # SHELL_JS
SHELL_BODY_SCRIPT_MARKERS = (HEADER_JS_MARKER, SCROLLSPY_JS_MARKER)

# Fewer contents headings than this and the Contents list + bar are left out.
MIN_CONTENTS_HEADINGS = 2
# The phone Contents bar draws one dot per section up to this many; past it the
# dots collapse into one progress bar (20 dots overflowed a 390px screen).
MINI_DOTS_MAX = 10

# Contents scrollspy: read / current / ahead dots, the phone bar's label,
# and the "In short" dots. Progressive enhancement only: everything is
# visible and every link works without it.
SHELL_JS = """<script>
(function(){
  var heads=[].slice.call(document.querySelectorAll('#article h2[data-toc]'));
  var lists=[].slice.call(document.querySelectorAll('ol.toc')).map(function(ol){return [].slice.call(ol.children);});
  var claims=[].slice.call(document.querySelectorAll('.inshort li'));
  var now=document.getElementById('now'), mini=document.getElementById('mini');
  var many=!!(mini&&mini.classList.contains('many')), fill=null;
  if(many){ var bar=document.createElement('i'); bar.className='bar'; fill=document.createElement('b'); bar.appendChild(fill); mini.appendChild(bar); }
  var dots=(mini&&!many)?heads.map(function(){var i=document.createElement('i'); mini.appendChild(i); return i;}):[];
  var tm=document.getElementById('tocm');
  if(tm) tm.addEventListener('click',function(e){ if(e.target.closest('ol.toc a')) tm.open=false; });
  // One margin rail at a time on wide screens: while "In short" is beside the
  // text, the Contents rail waits; it appears once "In short" has scrolled past.
  var rail=document.querySelector('nav.rail'), sum=document.querySelector('.slot-summary');
  function gate(){ if(rail&&sum) rail.classList.toggle('wait',sum.getBoundingClientRect().bottom>28); }
  function update(){
    gate();
    var line=innerHeight*0.35, cur=-1;
    heads.forEach(function(h,i){ if(h.getBoundingClientRect().top<line) cur=i; });
    lists.forEach(function(list){ list.forEach(function(li,i){
      li.classList.toggle('read',i<cur); li.classList.toggle('cur',i===cur);
    });});
    dots.forEach(function(d,i){ d.className=i<cur?'read':(i===cur?'cur':''); });
    if(fill) fill.style.width=((cur+1)/heads.length*100)+'%';
    claims.forEach(function(li){ li.classList.toggle('read',+li.dataset.sec<cur); });
    if(now) now.textContent=cur<0?'Intro':String(cur+1).padStart(2,'0')+'  '+heads[cur].textContent;
  }
  addEventListener('scroll',update,{passive:true}); addEventListener('resize',update); update();
})();
</script>"""


# ── Essay components (opt-in) ─────────────────────────────────
# See the module docstring. Every component renders trusted HTML; plain-text
# fields are escaped here.

PHONE_MAX_PX = 640  # phone crops, table cards and the SVG overview apply at or below this width


@dataclass(frozen=True)
class PhoneCrop:
    """An art-directed crop served at or below PHONE_MAX_PX."""

    src: str
    width: int
    height: int
    src_2x: str = ""
    type: str = "image/webp"


@dataclass(frozen=True)
class Picture:
    """A responsive image. `src` (+ `src_2x`) is the PNG/JPEG fallback, `webp`
    (+ `webp_2x`) the preferred source, `phone` an optional phone crop."""

    src: str
    alt: str
    width: int
    height: int
    src_2x: str = ""
    webp: str = ""
    webp_2x: str = ""
    phone: PhoneCrop | None = None

    @classmethod
    def from_stem(
        cls,
        stem: str,
        alt: str,
        width: int,
        height: int,
        *,
        ext: str = "png",
        retina: bool = True,
        webp: bool = True,
        phone: tuple[int, int] | None = None,
    ) -> "Picture":
        """stem="img/scene-tablet" -> img/scene-tablet.png (+@2x), .webp
        (+@2x) and, with phone=(w, h), img/scene-tablet-m.webp (+@2x)."""
        crop = None
        if phone:
            crop = PhoneCrop(f"{stem}-m.webp", phone[0], phone[1], f"{stem}-m@2x.webp" if retina else "")
        return cls(
            src=f"{stem}.{ext}",
            alt=alt,
            width=width,
            height=height,
            src_2x=f"{stem}@2x.{ext}" if retina else "",
            webp=f"{stem}.webp" if webp else "",
            webp_2x=f"{stem}@2x.webp" if webp and retina else "",
            phone=crop,
        )

    def files(self) -> tuple[str, ...]:
        """Every path this picture references (for asset checks)."""
        paths = [self.src, self.src_2x, self.webp, self.webp_2x]
        if self.phone:
            paths += [self.phone.src, self.phone.src_2x]
        return tuple(p for p in paths if p)


def _srcset(one: str, two: str) -> str:
    return f"{esc(one)} 1x, {esc(two)} 2x" if two else esc(one)


def render_picture(pic: Picture, *, eager: bool = False) -> str:
    """<picture class="gg-pic">: phone crop source, WebP source, fallback <img>."""
    cls = "gg-pic gg-pic-art" if pic.phone else "gg-pic"
    out = f'<picture class="{cls}">'
    if pic.phone:
        p = pic.phone
        out += (f'<source media="(max-width: {PHONE_MAX_PX}px)" type="{esc(p.type)}" '
                f'srcset="{_srcset(p.src, p.src_2x)}" width="{p.width}" height="{p.height}">')
    if pic.webp:
        out += f'<source type="image/webp" srcset="{_srcset(pic.webp, pic.webp_2x)}">'
    srcset = f' srcset="{_srcset(pic.src, pic.src_2x)}"' if pic.src_2x else ""
    load = 'loading="eager" fetchpriority="high"' if eager else 'loading="lazy"'
    out += (f'<img src="{esc(pic.src)}"{srcset} alt="{esc(pic.alt)}" width="{pic.width}" '
            f'height="{pic.height}" {load} decoding="async"></picture>')
    return out


@dataclass(frozen=True)
class PlayOnceVideo:
    """A short muted clip that plays once when half visible and holds its
    last frame. sources = ((src, mime), ...) in preference order. On phones,
    phone_aspect ("900/760") crops it with object-fit: cover at phone_position.
    poster (use WebP) is attached by the essay JS only when the video will be
    shown; without JS or under reduced motion the picture's still shows instead
    and neither the poster nor the clip is fetched."""

    sources: tuple[tuple[str, str], ...]
    poster: str
    width: int
    height: int
    phone_aspect: str = ""
    phone_position: str = "50% 50%"
    replay_label: str = "Replay animation"

    def __post_init__(self) -> None:
        if not self.sources:
            raise ValueError("PlayOnceVideo needs at least one source")
        if self.phone_aspect and not re.fullmatch(r"\d+(\.\d+)?\s*/\s*\d+(\.\d+)?", self.phone_aspect):
            raise ValueError(f"PlayOnceVideo.phone_aspect must look like '900/760', not {self.phone_aspect!r}")
        if not re.fullmatch(r"[0-9a-z.% -]+", self.phone_position):
            raise ValueError(f"PlayOnceVideo.phone_position must be a CSS position, not {self.phone_position!r}")


FigureWidth = Literal["inline", "column"]


@dataclass(frozen=True)
class EssayFigure:
    """A picture (and optionally a play-once video) with an optional caption.
    Place it with `marker` or `after` (module docstring)."""

    picture: Picture
    video: PlayOnceVideo | None = None
    caption_html: str = ""
    id: str = ""
    width: FigureWidth = "inline"
    marker: str = ""
    after: str = ""

    def __post_init__(self) -> None:
        if self.width not in ("inline", "column"):
            raise ValueError(f"EssayFigure.width must be 'inline' or 'column', not {self.width!r}")


_REPLAY_ICON = ('<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2.5a5.5 5.5 0 1 1-5.2 3.7l1.4.5A4 4 0 1 0 '
                '8 4v2.2L4.6 3.3 8 .4z"/></svg>')


def _id_attr(value: str) -> str:
    return f' id="{esc(value)}"' if value else ""


def render_essay_figure(fig: EssayFigure) -> str:
    cls = "gg-essay-fig" + (" is-column" if fig.width == "column" else "")
    still = render_picture(fig.picture)
    if fig.video:
        v = fig.video
        srcs = "".join(f'<source src="{esc(s)}" type="{esc(t)}">' for s, t in v.sources)
        crop = ""
        if v.phone_aspect:
            crop = f' class="gg-vid-crop" style="--ph-ar:{v.phone_aspect};--ph-pos:{v.phone_position}"'
        media = (
            f'<div class="gg-media has-video" data-play-once>'
            f'<video muted playsinline preload="none" data-poster="{esc(v.poster)}" width="{v.width}" height="{v.height}"'
            f'{crop} aria-label="{esc(fig.picture.alt)}">{srcs}</video>'
            f'<button class="gg-replay" type="button" aria-label="{esc(v.replay_label)}" hidden>{_REPLAY_ICON}</button>'
            f"{still}</div>"
        )
    else:
        media = f'<div class="gg-media">{still}</div>'
    cap = f"\n  <figcaption>{fig.caption_html}</figcaption>" if fig.caption_html else ""
    return f'<figure class="{cls}"{_id_attr(fig.id)}>\n  {media}{cap}\n</figure>'


@dataclass(frozen=True)
class SvgFigure:
    """Inline SVG evidence figure. `svg` is the detailed drawing (trusted);
    `phone_svg` an optional overview for phones, with a "Zoom in" toggle that
    reveals the detail, panned sideways at detail_min_width px."""

    id: str
    svg: str
    kicker: str = ""
    title: str = ""
    caption_html: str = ""
    phone_svg: str = ""
    phone_note_html: str = ""
    detail_min_width: int = 720
    zoom_label: str = "Zoom in"
    marker: str = ""
    after: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("SvgFigure.id is required (the zoom toggle and title point at it)")
        if "<svg" not in self.svg:
            raise ValueError("SvgFigure.svg must contain an <svg> element")


def render_svg_figure(fig: SvgFigure) -> str:
    fid = esc(fig.id)
    label = f' aria-labelledby="{fid}-h"' if fig.title else ""
    kick = f'\n  <p class="kick">{esc(fig.kicker)}</p>' if fig.kicker else ""
    title = f'\n  <h5 id="{fid}-h">{esc(fig.title)}</h5>' if fig.title else ""
    mini = ""
    if fig.phone_svg:
        note = f'\n    <p class="gg-svg-note">{fig.phone_note_html}</p>' if fig.phone_note_html else ""
        mini = (
            f'\n  <div class="gg-svg-mini">{fig.phone_svg}{note}\n'
            f'    <button class="gg-svg-zoom" type="button" aria-expanded="false" aria-controls="{fid}-detail" '
            f'data-label="{esc(fig.zoom_label)}">{esc(fig.zoom_label)}</button>\n  </div>'
            '\n  <p class="gg-svg-hint" aria-hidden="true">Swipe the chart &rarr;</p>'
        )
    cls = "gg-svgfig gg-fig" + (" has-mini" if fig.phone_svg else "")
    cap = f"\n  <figcaption>{fig.caption_html}</figcaption>" if fig.caption_html else ""
    return (
        f'<figure class="{cls}" id="{fid}"{label}>{kick}{title}{mini}\n'
        f'  <div class="gg-svg-detail" id="{fid}-detail" tabindex="0" role="region" '
        f'aria-label="Diagram, scrolls sideways" style="--svg-min:{int(fig.detail_min_width)}px">{fig.svg}</div>'
        f"{cap}\n</figure>"
    )


ColumnKind = Literal["text", "num"]
CardRole = Literal["title", "aside", "fact", "row"]


@dataclass(frozen=True)
class TableColumn:
    """label: plain text. kind="num" sorts numerically. card: where the
    column goes on a phone card ("title" heading, "aside" beside it, "fact"
    in the two-up facts row, "row" as a labelled line)."""

    label: str
    kind: ColumnKind = "text"
    width: str = ""
    card: CardRole = "row"
    sortable: bool = True

    def __post_init__(self) -> None:
        if self.width and not re.fullmatch(r"\d+(\.\d+)?(%|px|em|rem)", self.width):
            raise ValueError(f"TableColumn.width must be a CSS length, not {self.width!r}")


@dataclass(frozen=True)
class TableCell:
    """html: trusted HTML ("" = not stated, rendered as an em dash).
    sort: the sort key (a number for num columns); None = the cell's text.
    note_html: a quieter second line."""

    html: str
    sort: str | float | int | None = None
    note_html: str = ""


@dataclass(frozen=True)
class TableLink:
    href: str
    text: str
    label: str  # accessible name, e.g. "Abstract on PubMed (ref 9)"


@dataclass(frozen=True)
class TableRow:
    cells: tuple[TableCell, ...]
    links: tuple[TableLink, ...] = ()


@dataclass(frozen=True)
class DataTable:
    """A sortable table on wide screens, cards on phones. Rows render sorted
    ascending by column `sort_by` (None = as given)."""

    id: str
    title: str
    columns: tuple[TableColumn, ...]
    rows: tuple[TableRow, ...]
    kicker: str = ""
    intro_html: str = ""
    footnote_html: str = ""
    sort_by: int | None = None
    marker: str = ""
    after: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("DataTable.id is required")
        n = len(self.columns)
        for i, row in enumerate(self.rows):
            if len(row.cells) != n:
                raise ValueError(f"DataTable row {i} has {len(row.cells)} cells, expected {n}")
        if self.sort_by is not None and not 0 <= self.sort_by < n:
            raise ValueError(f"DataTable.sort_by {self.sort_by} is out of range")
        if sum(c.card == "title" for c in self.columns) != 1:
            raise ValueError("DataTable needs exactly one column with card='title'")


_NA = '<span class="na">&mdash;</span>'


def _sort_value(col: TableColumn, cell: TableCell) -> str:
    if cell.sort is not None:
        return str(cell.sort)
    if not cell.html:
        return ""
    return " ".join(html.unescape(_strip_tags(re.sub(r"<sup\b.*?</sup>", "", cell.html, flags=re.S))).split())


def _cell_html(cell: TableCell) -> str:
    out = cell.html or _NA
    if cell.note_html:
        out += f'<span class="who">{cell.note_html}</span>'
    return out


def _links_html(links: Sequence[TableLink]) -> str:
    return "".join(
        f' <a class="gg-cite" href="{esc(l.href)}" target="_blank" rel="noopener" aria-label="{esc(l.label)}">{esc(l.text)}</a>'
        for l in links
    )


def _sorted_rows(t: DataTable) -> list[TableRow]:
    if t.sort_by is None:
        return list(t.rows)
    col = t.columns[t.sort_by]

    def key(row: TableRow):
        v = _sort_value(col, row.cells[t.sort_by])
        if v == "":
            return (1, 0, "")
        return (0, float(v), "") if col.kind == "num" else (0, 0, v.lower())

    return sorted(t.rows, key=key)


def render_data_table(t: DataTable) -> str:
    tid = esc(t.id)
    rows = _sorted_rows(t)
    last = len(t.columns) - 1
    cols = "".join(f'<col style="width:{c.width}">' if c.width else "<col>" for c in t.columns)

    def th(i: int, c: TableColumn) -> str:
        sort = ' aria-sort="ascending"' if t.sort_by == i else ""
        if not c.sortable:
            return f'<th scope="col">{esc(c.label)}</th>'
        return (f'<th scope="col" data-type="{c.kind}"{sort}><button type="button">{esc(c.label)}'
                '<span class="ar" aria-hidden="true"></span></button></th>')

    def td(i: int, c: TableColumn, cell: TableCell, row: TableRow) -> str:
        cls = ' class="num"' if c.kind == "num" else ""
        links = _links_html(row.links) if i == last else ""
        return f'<td{cls} data-v="{esc(_sort_value(c, cell))}">{_cell_html(cell)}{links}</td>'

    head = "".join(th(i, c) for i, c in enumerate(t.columns))
    body = "\n      ".join(
        "<tr>" + "".join(td(i, c, r.cells[i], r) for i, c in enumerate(t.columns)) + "</tr>" for r in rows
    )

    def card(r: TableRow) -> str:
        title = aside = ""
        facts, lines = [], []
        for i, c in enumerate(t.columns):
            cell = r.cells[i]
            links = _links_html(r.links) if i == last else ""
            if c.card == "title":
                title = cell.html or _NA
            elif c.card == "aside":
                aside = f'<span class="gg-card-aside">{_cell_html(cell)}</span>'
            elif c.card == "fact":
                facts.append(f"<div><dt>{esc(c.label)}</dt><dd>{_cell_html(cell)}{links}</dd></div>")
            else:
                lines.append(f'<p class="gg-card-row"><span class="lbl">{esc(c.label)}</span>{_cell_html(cell)}{links}</p>')
        dl = f'<dl class="gg-card-facts">{"".join(facts)}</dl>' if facts else ""
        return (f'<li class="gg-card"><p class="gg-card-h"><span class="gg-card-name">{title}</span>{aside}</p>'
                f'{dl}{"".join(lines)}</li>')

    cards = "\n    ".join(card(r) for r in rows)
    kick = f'\n  <p class="kick">{esc(t.kicker)}</p>' if t.kicker else ""
    hint = '<span class="gg-sort-hint">Click a column to sort. </span>'
    intro = f'\n  <p class="sub">{hint}{t.intro_html}</p>'
    foot = f'{t.footnote_html} ' if t.footnote_html else ""
    return f"""<figure class="gg-table" id="{tid}" aria-labelledby="{tid}-h">{kick}
  <h5 id="{tid}-h">{esc(t.title)}</h5>{intro}
  <div class="gg-table-wrap" tabindex="0" role="region" aria-labelledby="{tid}-h">
    <table class="gg-sortable">
      <colgroup>{cols}</colgroup>
      <thead><tr>{head}</tr></thead>
      <tbody>
      {body}
      </tbody>
    </table>
  </div>
  <ol class="gg-cards" aria-labelledby="{tid}-h">
    {cards}
  </ol>
  <p class="fn">{foot}<span class="gg-sr" aria-live="polite" data-sort-status></span></p>
</figure>"""


Figure = EssayFigure | SvgFigure | DataTable


def render_figure(fig: Figure) -> str:
    if isinstance(fig, EssayFigure):
        return render_essay_figure(fig)
    if isinstance(fig, SvgFigure):
        return render_svg_figure(fig)
    if isinstance(fig, DataTable):
        return render_data_table(fig)
    raise TypeError(f"not a figure: {fig!r}")


FIGURE_MARKER_RE = re.compile(r"<!--GG:FIGURE ([a-z0-9-]+)-->")
# Blocks a figure can follow. A snippet inside an <li>, a <p> in a blockquote
# or a heading lands after the outermost of these that holds it, never inside.
_FIGURE_BLOCKS = frozenset({"p", "ul", "ol", "dl", "blockquote", "figure", "table", "pre",
                            "h1", "h2", "h3", "h4", "h5", "h6"})
_VOID_TAGS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
                        "source", "track", "wbr"})


class _BlockSpanParser(HTMLParser):
    """(start, end) source offsets of every _FIGURE_BLOCKS element."""

    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=True)
        self._line_starts = [0] + [m.end() for m in re.finditer("\n", text)]
        self._text = text
        self._open: list[tuple[str, int]] = []
        self.spans: list[tuple[int, int]] = []

    def _offset(self) -> int:
        line, col = self.getpos()
        return self._line_starts[line - 1] + col

    def handle_starttag(self, tag, attrs):
        if tag not in _VOID_TAGS:
            self._open.append((tag, self._offset()))

    def handle_endtag(self, tag):
        if not any(t == tag for t, _ in self._open):
            return
        end = self._text.index(">", self._offset()) + 1
        while self._open:
            t, start = self._open.pop()
            if t in _FIGURE_BLOCKS:
                self.spans.append((start, end))
            if t == tag:
                break


def _enclosing_block_end(body: str, at: int) -> int | None:
    """End offset of the outermost figure-able block holding offset `at`."""
    p = _BlockSpanParser(body)
    p.feed(body)
    p.close()
    holding = [(start, end) for start, end in p.spans if start < at <= end]
    return min(holding)[1] if holding else None


def place_figures(body: str, figures: Sequence[Figure]) -> str:
    """Put each figure at its marker or after the outermost block (paragraph,
    list, quote, heading, table, figure) holding its `after` snippet. Raises ValueError on a missing/duplicate anchor or a body marker
    that no figure claims."""
    for fig in figures:
        if bool(fig.marker) == bool(fig.after):
            raise ValueError(f"{type(fig).__name__} needs exactly one of marker= or after=")
        block = render_figure(fig)
        if fig.marker:
            tag = f"<!--GG:FIGURE {fig.marker}-->"
            if body.count(tag) != 1:
                raise ValueError(f"marker {tag} found {body.count(tag)} times in the body, expected once")
            body = body.replace(tag, block, 1)
        else:
            n = body.count(fig.after)
            if n != 1:
                raise ValueError(f"after={fig.after[:60]!r} found {n} times in the body, expected once")
            end = _enclosing_block_end(body, body.index(fig.after) + len(fig.after))
            if end is None:
                raise ValueError(f"after={fig.after[:60]!r} is not inside a paragraph, list, quote, "
                                 "heading, table or figure")
            body = body[:end] + "\n" + block + body[end:]
    left = FIGURE_MARKER_RE.findall(body)
    if left:
        raise ValueError(f"body markers without a figure: {left}")
    return body


def _uses_essay_js(body: str, figures: Sequence[Figure]) -> bool:
    if "data-draw-in" in body:
        return True
    for f in figures:
        if isinstance(f, DataTable) or (isinstance(f, SvgFigure) and f.phone_svg):
            return True
        if isinstance(f, EssayFigure) and f.video:
            return True
    return False


class _SectionEndParser(HTMLParser):
    """Offset just past the end of the first gg-blog-section that starts at or after `start`."""

    def __init__(self, text: str, start: int) -> None:
        super().__init__(convert_charrefs=True)
        self._line_starts = [0] + [m.end() for m in re.finditer("\n", text)]
        self._text, self._start = text, start
        self._depth = 0
        self._tag: str | None = None
        self.end: int | None = None

    def _offset(self) -> int:
        line, col = self.getpos()
        return self._line_starts[line - 1] + col

    def handle_starttag(self, tag, attrs):
        if self.end is not None:
            return
        if self._tag is None:
            if tag in ("section", "div") and "gg-blog-section" in _classes(attrs) and self._offset() >= self._start:
                self._tag, self._depth = tag, 1
        elif tag == self._tag:
            self._depth += 1

    def handle_endtag(self, tag):
        if self._tag is None or self.end is not None or tag != self._tag:
            return
        self._depth -= 1
        if self._depth == 0:
            off = self._offset()
            self.end = self._text.index(">", off) + 1


def _section_end_after(body: str, start: int) -> int | None:
    p = _SectionEndParser(body, start)
    p.feed(body)
    p.close()
    return p.end


ESSAY_JS_MARKER = "gg-essay-js"

# Play-once videos, chart draw-in, SVG zoom toggles, sortable tables. All
# progressive enhancement: without it every figure is complete and readable.
ESSAY_JS = """<script>
/* gg-essay-js */
(function(){
  var RM=matchMedia('(prefers-reduced-motion: reduce)'), IO='IntersectionObserver' in window;
  function each(sel,fn){ [].forEach.call(document.querySelectorAll(sel),fn); }

  /* play once at 50% visible, hold the last frame, offer replay; the still until .is-live, and under reduced motion (CSS) */
  each('[data-play-once]',function(box){
    var v=box.querySelector('video'), b=box.querySelector('.gg-replay'); if(!v) return;
    var done=false, seen=false, poster=v.getAttribute('data-poster');
    v.loop=false;
    function live(){ if(box.classList.contains('is-live')) return; if(poster) v.poster=poster; box.classList.add('is-live'); }
    function go(){ if(v.preload==='none') v.preload='auto'; var p=v.play(); if(p&&p.catch) p.catch(function(){}); }
    function sync(){ if(RM.matches){ v.pause(); return; } live(); if(done) return; if(seen) go(); else v.pause(); }
    v.addEventListener('ended',function(){ done=true; box.setAttribute('data-played','1'); if(b) b.hidden=false; });
    if(b) b.addEventListener('click',function(){ b.hidden=true; v.currentTime=0; go(); });
    if(IO){ new IntersectionObserver(function(es){
      var e=es[0]; if(e.isIntersecting && v.preload==='none') v.preload='metadata';
      seen=e.intersectionRatio>=0.5; sync(); },{threshold:[0,0.5]}).observe(box); }
    else seen=true;
    if(RM.addEventListener) RM.addEventListener('change',sync);
    sync();
  });

  /* draw-in: empty the chart only while it is off-screen, play it once at 15% visible */
  each('[data-draw-in]',function(fig){
    if(!IO) return;
    var done=false;
    var io=new IntersectionObserver(function(es){
      var e=es[0];
      if(done||RM.matches) return;
      if(!e.isIntersecting){ fig.classList.add('is-armed'); return; }
      if(e.intersectionRatio>=0.15 && fig.classList.contains('is-armed')){
        done=true; io.disconnect();
        fig.classList.remove('is-armed'); fig.classList.add('is-playing');
        var end=0;
        [].forEach.call(fig.querySelectorAll('[data-draw]'),function(el){
          var cs=getComputedStyle(el), t=function(s){ return parseFloat(s)*(/ms$/.test(s)?1:1000)||0; };
          end=Math.max(end,t(cs.animationDelay)+t(cs.animationDuration));
        });
        setTimeout(function(){ fig.classList.remove('is-playing'); fig.setAttribute('data-drawn','1'); },end+100);
      }
    },{threshold:[0,0.15]});
    io.observe(fig);
  });

  /* SVG figures on phones: overview by default, the detail on request */
  each('.gg-svg-zoom',function(b){
    var fig=b.closest('.gg-svgfig'), label=b.getAttribute('data-label');
    b.addEventListener('click',function(){
      var on=!fig.classList.contains('is-zoomed');
      fig.classList.toggle('is-zoomed',on);
      b.setAttribute('aria-expanded',String(on)); b.textContent=on?'Hide detail':label;
    });
  });

  /* sortable tables: blanks always sort last */
  each('table.gg-sortable',function(t){
    var ths=[].slice.call(t.querySelectorAll('thead th')), body=t.tBodies[0];
    var live=t.closest('figure').querySelector('[data-sort-status]');
    ths.forEach(function(th,ci){
      var btn=th.querySelector('button'); if(!btn) return;
      btn.addEventListener('click',function(){
        var dir=th.getAttribute('aria-sort')==='ascending'?'descending':'ascending', num=th.getAttribute('data-type')==='num';
        ths.forEach(function(o){ o.removeAttribute('aria-sort'); });
        th.setAttribute('aria-sort',dir);
        var rows=[].slice.call(body.rows);
        rows.sort(function(a,b){
          var x=a.cells[ci].getAttribute('data-v')||'', y=b.cells[ci].getAttribute('data-v')||'';
          if(!x||!y) return !x===!y?0:(!x?1:-1);
          var r=num?(+x - +y):x.localeCompare(y);
          return dir==='ascending'?r:-r;
        });
        rows.forEach(function(r){ body.appendChild(r); });
        if(live) live.textContent='Sorted by '+btn.textContent.trim()+', '+dir+'.';
      });
    });
  });
})();
</script>"""

# Styles for the essay components, emitted only on pages that use them.
ESSAY_CSS = """
/* essay figures: still / play-once video + caption */
.gg-essay-fig{margin:28px 0 30px}
.gg-media{position:relative;max-width:440px;margin:0 auto}
.gg-essay-fig.is-column .gg-media{max-width:none}
.gg-pic{display:block}
.gg-media img,.gg-media video{display:block;width:100%;height:auto;background:var(--sand)}
.gg-media.has-video video{display:none}
.gg-media.has-video .gg-pic{display:block}
.gg-media.has-video.is-live video{display:block}
.gg-media.has-video.is-live .gg-pic{display:none}
.gg-replay{position:absolute;right:8px;bottom:8px;width:40px;height:40px;border:0;cursor:pointer;padding:0;
  background:rgba(26,20,16,.66);color:#fff;display:flex;align-items:center;justify-content:center;clip-path:var(--chamfer)}
.gg-replay[hidden]{display:none}
.gg-replay svg{width:16px;height:16px;fill:currentColor}
.gg-essay-fig figcaption{font:500 15px/1.5 var(--mono);color:var(--ink2);margin:12px auto 0;max-width:440px}
.gg-essay-fig.is-column figcaption{max-width:none}
.hero-img .gg-pic{display:block}
@media (max-width:640px){
  .hero:not(.wide) .hero-img .gg-pic-art img{aspect-ratio:auto;object-fit:fill}
  .gg-media video.gg-vid-crop{aspect-ratio:var(--ph-ar);object-fit:cover;object-position:var(--ph-pos,50% 50%)}
}
@media (prefers-reduced-motion:reduce){
  .gg-media.has-video.is-live video,.gg-replay{display:none}
  .gg-media.has-video.is-live .gg-pic{display:block}
}

/* inline SVG figures; phones get the overview + "Zoom in" when there is one */
.gg-svgfig{margin:28px 0 30px;padding:22px 24px 18px}
.gg-svgfig .kick{margin-bottom:6px}
.gg-svgfig h5,.gg-table h5{font:700 24px/1.2 var(--serif);margin:0 0 14px;color:var(--ink)}
.gg-svgfig svg{display:block;width:100%;height:auto}
.gg-svgfig svg text{font-family:var(--mono)}
.gg-svg-detail{overflow-x:auto;-webkit-overflow-scrolling:touch}
.gg-svg-detail:focus-visible,.gg-table-wrap:focus-visible{outline:3px solid var(--cobalt);outline-offset:2px}
.gg-svgfig figcaption{font-size:14px;margin-top:12px}
.gg-svgfig figcaption a{color:var(--cobalt-deep);text-underline-offset:3px}
.gg-svg-mini,.gg-svgfig .gg-svg-hint{display:none}
.gg-svgfig .gg-svg-note{font:500 12px/1.5 var(--mono);color:var(--ink2);margin:8px 0 10px}
.gg-svg-zoom{font:700 13px var(--mono);letter-spacing:.04em;text-transform:uppercase;color:var(--cobalt-deep);background:none;border:0;cursor:pointer;
  height:40px;padding:0 12px;box-shadow:inset 0 0 0 2px var(--cobalt-deep)}
@media (max-width:640px){
  .gg-svgfig{padding:18px 14px}
  .gg-svgfig h5,.gg-table h5{font-size:21px}
  .gg-svg-detail svg{min-width:var(--svg-min,720px)}
  .gg-svgfig.has-mini .gg-svg-mini{display:block}
  .gg-svgfig.has-mini:not(.is-zoomed) .gg-svg-detail{display:none}
  .gg-svgfig.is-zoomed .gg-svg-hint{display:block;font:700 12px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--ink3);margin:12px 0 6px}
}

/* sortable table; one card per row on phones */
.gg-table{background:var(--fig);padding:22px 24px 16px;margin:30px 0}
.gg-table h5{margin-bottom:6px}
.article .gg-table .sub{font:500 14px/1.5 var(--mono);color:var(--ink2);margin:0 0 14px}
.gg-table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
.gg-sortable{border-collapse:collapse;width:100%;table-layout:fixed;font:500 13px/1.45 var(--mono);color:var(--ink)}
.gg-sortable th,.gg-sortable td{text-align:left;vertical-align:top;padding:10px 10px 10px 0;box-shadow:inset 0 -1px 0 var(--sand2)}
.gg-sortable thead th{padding:0;box-shadow:inset 0 -3px 0 var(--ink);vertical-align:bottom;font:700 12px var(--mono);letter-spacing:.06em;text-transform:uppercase}
.gg-sortable th button{all:unset;box-sizing:border-box;display:flex;align-items:center;gap:6px;width:100%;cursor:pointer;padding:6px 10px 10px 0;
  font:700 12px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--ink)}
.gg-sortable th button:focus-visible{outline:3px solid var(--cobalt);outline-offset:-1px}
.gg-sortable th button .ar{width:10px;height:10px;flex:none;opacity:.35;background:linear-gradient(var(--ink),var(--ink)) center/2px 100% no-repeat}
.gg-sortable th[aria-sort] button .ar{opacity:1;background:none;width:0;height:0;border:5px solid transparent}
.gg-sortable th[aria-sort="ascending"] button .ar{border-bottom:7px solid var(--cobalt-deep);border-top-width:0}
.gg-sortable th[aria-sort="descending"] button .ar{border-top:7px solid var(--cobalt-deep);border-bottom-width:0}
.gg-sortable td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.gg-sortable td.num .who{white-space:normal}
.gg-sortable td:first-child{font-weight:700}
.gg-table .who{display:block;color:var(--ink2);font-size:12px;font-weight:500}
.gg-table sup a{font-size:12px}
.gg-table .na{color:var(--ink3)}
.gg-table .gg-cite{color:var(--cobalt-deep);text-underline-offset:3px}
.article .gg-table .fn{font:500 13px/1.5 var(--mono);color:var(--ink2);margin:12px 0 0}
.gg-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.gg-cards{display:none;list-style:none;margin:0;padding:0}
@media (max-width:640px){
  .gg-table{padding:18px 14px 12px}
  .gg-table-wrap,.gg-sort-hint{display:none}
  .gg-table .gg-cards{display:block;padding:0}
  .article .gg-cards > li.gg-card{background:var(--paper);padding:14px 14px 4px;margin:0 0 10px;font:500 14px/1.45 var(--mono);color:var(--ink)}
  .article .gg-card p{margin:0 0 10px;font:500 14px/1.45 var(--mono)}
  .article .gg-card .gg-card-h{display:flex;justify-content:space-between;align-items:baseline;gap:12px;font:700 18px/1.3 var(--serif)}
  .gg-card-h sup a{font:500 12px var(--mono)}
  .gg-card-aside{font:700 14px var(--mono);font-variant-numeric:tabular-nums;color:var(--ink2)}
  .gg-card-facts{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0 0 10px;padding:0 0 10px;box-shadow:inset 0 -1px 0 var(--sand2)}
  .gg-card-facts dt,.gg-card .lbl{display:block;font:700 12px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--ink2);margin:0 0 2px}
  .gg-card-facts dd{margin:0;font:700 14px/1.4 var(--mono);font-variant-numeric:tabular-nums}
}

/* chart draw-in: complete at rest; JS adds .is-armed (off-screen) then .is-playing (once) */
[data-draw-in] [data-draw="grow"]{transform-origin:50% 100%}
[data-draw-in] [data-draw="grow-x"]{transform-origin:0 50%}
[data-draw-in].is-armed [data-draw="grow"]{transform:scaleY(0)}
[data-draw-in].is-armed [data-draw="grow-x"]{transform:scaleX(0)}
[data-draw-in].is-armed [data-draw="fade"],[data-draw-in].is-armed [data-draw="rise"]{opacity:0}
[data-draw-in].is-armed [data-draw="wipe"]{clip-path:inset(0 100% 0 0)}
[data-draw-in].is-playing [data-draw]{animation-duration:var(--draw-dur,.6s);animation-delay:calc(var(--draw-i,0) * 110ms + var(--draw-at,0ms));
  animation-fill-mode:backwards;animation-timing-function:cubic-bezier(.2,.75,.25,1)}
[data-draw-in].is-playing [data-draw="grow"]{animation-name:gg-draw-grow}
[data-draw-in].is-playing [data-draw="grow-x"]{animation-name:gg-draw-grow-x}
[data-draw-in].is-playing [data-draw="fade"]{animation-name:gg-draw-fade;animation-timing-function:ease-out}
[data-draw-in].is-playing [data-draw="rise"]{animation-name:gg-draw-rise;animation-timing-function:ease-out}
[data-draw-in].is-playing [data-draw="wipe"]{animation-name:gg-draw-wipe;animation-timing-function:ease-out}
@keyframes gg-draw-grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes gg-draw-grow-x{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes gg-draw-fade{from{opacity:0}to{opacity:1}}
@keyframes gg-draw-rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@keyframes gg-draw-wipe{from{clip-path:inset(0 100% 0 0)}to{clip-path:inset(0 0 0 0)}}
@media (prefers-reduced-motion:reduce){
  [data-draw-in] [data-draw]{animation:none!important;transform:none!important;opacity:1!important;clip-path:none!important}
}
/* print the finished chart, even one still armed off-screen */
@media print{
  [data-draw-in] [data-draw]{animation:none!important;transform:none!important;opacity:1!important;clip-path:none!important}
}

/* "In short" after the intro on phones (in_short_on_phone="after_intro") */
.slot-summary-m{display:none}
@media (max-width:640px){
  .slot-summary.has-phone-copy{display:none}
  .slot-summary-m{display:block;margin:8px 0 40px}
}
"""


# ── Page ──────────────────────────────────────────────────────

IN_SHORT_MARKER = "<!--GG:IN_SHORT-->"
InShortOnPhone = Literal["first", "after_intro"]
LADDER_MARKER = "<!--GG:LADDER-->"


def _place(body: str, marker: str, block: str, *, default: str) -> str:
    if marker in body:
        return body.replace(marker, block, 1)
    if default == "start":
        return block + "\n" + body
    refs = outline(body).references_start
    if refs is not None:
        return body[:refs] + block + "\n" + body[refs:]
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
    figures: Sequence[Figure] = (),
    in_short_on_phone: InShortOnPhone = "first",
) -> str:
    """Render a full editorial page. See the module docstring for the contract."""
    if in_short_on_phone not in ("first", "after_intro"):
        raise ValueError(f"in_short_on_phone must be 'first' or 'after_intro', not {in_short_on_phone!r}")
    minutes = reading_minutes(body_html)
    body = body_html
    if figures:
        body = place_figures(body, figures)
    # After placement, so data-draw-in inside a placed figure gets the JS.
    essay_js = _uses_essay_js(body, figures)
    uses_essay = bool(figures) or essay_js or bool(meta.hero and meta.hero.picture)
    summary = render_in_short(in_short) if in_short else ""
    if summary and in_short_on_phone == "after_intro":
        uses_essay = True
        phone = summary.replace('class="slot slot-summary" data-slot="summary"',
                                'class="slot slot-summary-m" data-slot="summary-phone"', 1)
        summary = summary.replace('class="slot slot-summary"', 'class="slot slot-summary has-phone-copy"', 1)
        body = _place(body, IN_SHORT_MARKER, summary, default="start")
        end = _section_end_after(body, body.index(summary) + len(summary))
        if end is None:
            raise ValueError('in_short_on_phone="after_intro" needs a gg-blog-section after "In short"')
        body = body[:end] + "\n" + phone + body[end:]
    else:
        body = _place(body, IN_SHORT_MARKER, summary, default="start")
    if ladder:
        lead = ladder if isinstance(ladder, str) else DEFAULT_LADDER_LEAD
        body = _place(body, LADDER_MARKER, render_ladder(lead), default="refs")
    else:
        body = body.replace(LADDER_MARKER, "")
    body, toc = add_heading_ids(body)

    if contents and len(toc) >= MIN_CONTENTS_HEADINGS:
        toc_html = render_contents(toc)
        mini_cls = "mini many" if len(toc) > MINI_DOTS_MAX else "mini"
        toc_bar = f"""  <details class="toc-m" id="tocm">
    <summary><span class="{mini_cls}" id="mini" aria-hidden="true"></span><span class="now" id="now">Intro</span><span class="tog">Contents</span></summary>
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

    events = render_article_events_js(meta.slug) if meta.tracks_article_events else ""
    if uses_essay:
        extra_css = ESSAY_CSS + "\n" + extra_css
    if essay_js:
        extra_body_end = ESSAY_JS + ("\n" + extra_body_end if extra_body_end else "")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{render_head(meta, extra_head, extra_css)}
</head>
<body>
{render_header(meta.nav_active)}

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
<script>{get_site_header_js()}</script>
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

/* header: shared_header.get_site_header_html(), restyled. Static (not
   sticky) so the Contents bar owns the top edge while reading. */
.gg-site-header{position:relative;z-index:40;background:var(--brown);color:var(--paper)}
.gg-site-header-inner{max-width:1296px;margin:0 auto;padding:0 32px;height:64px;display:flex;align-items:center;gap:28px}
.gg-site-header-logo{display:flex;align-items:center;color:var(--paper)}
.gg-site-header-logo .gg-logo-mark{height:38px;width:auto;display:block;fill:currentColor}
.gg-site-header-nav{display:flex;align-items:center;gap:22px;margin-left:auto;height:100%}
.gg-site-header-item{position:relative;height:100%;display:flex;align-items:center}
.gg-site-header-nav > a,.gg-site-header-item > a{font:700 14px var(--mono);letter-spacing:.04em;text-transform:uppercase;text-decoration:none;color:var(--paper);padding:8px 0}
.gg-site-header-nav > a:hover,.gg-site-header-item > a:hover,.gg-site-header-nav a[aria-current="page"]{text-decoration:underline;text-underline-offset:5px;text-decoration-thickness:3px}
.gg-site-header-dropdown{display:none;position:absolute;top:100%;left:-18px;min-width:240px;padding:8px 0;background:var(--brown);box-shadow:0 12px 32px rgba(0,0,0,.3);z-index:50}
.gg-site-header-item:hover .gg-site-header-dropdown,.gg-site-header-item:focus-within .gg-site-header-dropdown{display:block}
.gg-site-header-dropdown a{display:block;padding:10px 18px;font:700 13px var(--mono);letter-spacing:.03em;text-transform:uppercase;text-decoration:none;color:var(--paper)}
.gg-site-header-dropdown a:hover{background:#2c231c;text-decoration:underline;text-underline-offset:4px}
.gg-site-header .btn{background:var(--teal)}
.gg-hamburger{display:none;margin-left:auto;background:none;border:0;cursor:pointer;width:48px;height:48px;padding:12px;flex-direction:column;justify-content:center;align-items:center;gap:5px;box-shadow:inset 0 0 0 2px var(--paper)}
.gg-hamburger-bar{display:block;width:22px;height:2px;background:var(--paper);transition:transform .15s}
.gg-hamburger.is-open .gg-hamburger-bar:nth-child(1){transform:translateY(7px) rotate(45deg)}
.gg-hamburger.is-open .gg-hamburger-bar:nth-child(2){opacity:0}
.gg-hamburger.is-open .gg-hamburger-bar:nth-child(3){transform:translateY(-7px) rotate(-45deg)}
.gg-mobile-nav{display:none;flex-direction:column;padding:0 32px 14px;background:var(--brown)}
.gg-mobile-nav.is-open{display:flex}
.gg-mobile-nav-group{box-shadow:inset 0 -1px 0 rgba(245,239,230,.25)}
.gg-mobile-nav-toggle{display:flex;align-items:center;justify-content:space-between;width:100%;min-height:48px;padding:0;background:none;border:0;cursor:pointer;font:700 15px var(--mono);letter-spacing:.04em;text-transform:uppercase;color:var(--paper)}
.gg-mobile-nav-toggle::after{content:"+";font-size:20px;font-weight:400}
.gg-mobile-nav-toggle[aria-expanded="true"]::after{content:"\\2212"}
.gg-mobile-nav-sub{display:none;flex-direction:column;padding:0 0 10px 16px}
.gg-mobile-nav-sub.is-open{display:flex}
.gg-mobile-nav-sub a{display:block;padding:11px 0;font:400 15px var(--mono);color:var(--paper);text-decoration:none}
.gg-mobile-nav-link{display:flex;align-items:center;min-height:48px;font:700 15px var(--mono);letter-spacing:.04em;text-transform:uppercase;color:var(--paper);text-decoration:none}
.gg-mobile-nav a:hover{text-decoration:underline;text-underline-offset:4px}

/* layout */
.frame{max-width:calc(var(--col) + 64px);margin:0 auto;padding:0 32px}

/* hero */
.hero{display:grid;grid-template-columns:minmax(0,1fr) 190px;column-gap:28px;padding-top:36px;padding-bottom:28px;align-items:start}
.hero.no-img{grid-template-columns:minmax(0,1fr)}
.kick-top{font:700 13px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--teal-ink);margin:0 0 14px}
h1{font:700 60px/1.0 var(--serif);letter-spacing:-.025em;margin:0 0 16px;font-optical-sizing:auto;text-wrap:balance;overflow-wrap:break-word}
/* long-word h1 (render_hero): size to the column so the longest word fits */
h1.h1-long-1{--h1-w:8.25}
h1.h1-long-2{--h1-w:9.35}
h1.h1-long-3{--h1-w:10.75}
h1.h1-long-4{--h1-w:12.65}
.hero h1[class*="h1-long-"]{font-size:min(60px,calc(min(var(--col),100vw - 64px) / var(--h1-w)))}
.hero:not(.no-img):not(.wide) h1[class*="h1-long-"]{font-size:min(60px,calc(min(var(--col) - 218px,100vw - 282px) / var(--h1-w)))}
.dek{font:italic 400 22px/1.4 var(--serif);color:var(--ink2);margin:0 0 16px;max-width:36em}
.by{font:500 14px var(--mono);letter-spacing:.02em;color:var(--ink2);margin:0}
.hero-img{margin:0}
.hero-img img{width:100%;height:auto;display:block;background:var(--sand)}
.hero.wide{grid-template-columns:minmax(0,1fr)}
.hero.wide .hero-img{margin-top:24px}

/* contents: phone/tablet sticky bar */
.toc-m{position:sticky;top:0;z-index:20;background:var(--sand);margin:0 0 28px}
.toc-m summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:12px;min-height:48px;padding:0 32px}
.toc-m summary::-webkit-details-marker{display:none}
.toc-m .mini{display:flex;gap:6px;flex:0 1 auto;min-width:0;overflow:hidden}
.toc-m .mini.many{flex:0 1 96px}
.toc-m .mini .bar{flex:1 1 auto;display:block;position:relative;width:100%;height:6px;border-radius:3px;box-shadow:inset 0 0 0 1.5px var(--ink3);overflow:hidden}
.toc-m .mini .bar b{position:absolute;left:0;top:0;bottom:0;width:0;background:var(--cobalt-deep)}
.toc-m .mini i{flex:none;width:10px;height:10px;border-radius:50%;box-shadow:inset 0 0 0 2px var(--ink3)}
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
.article h2[data-toc]{counter-increment:blk}
.article h2{font:700 36px/1.12 var(--serif);letter-spacing:-.015em;margin:72px 0 22px;text-wrap:balance}
.article h2[data-toc]::before,.gg-references h2::before{display:block;font:700 14px var(--mono);letter-spacing:.1em;color:var(--ink3);margin-bottom:8px}
.article h2[data-toc]::before{content:counter(blk,decimal-leading-zero)}
.article > .gg-blog-section:first-child h2:first-child,.slot-summary + .gg-blog-section h2{margin-top:8px}
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

/* wide: open column; quiet contents in the left margin, "In short" in the right.
   One rail at a time: with "In short", SHELL_JS holds the contents rail back
   (.rail.wait) until "In short" has scrolled past. */
@media (min-width:1280px){
  .frame{max-width:none;display:grid;grid-template-columns:minmax(0,1fr) var(--col) minmax(0,1fr);column-gap:var(--gap)}
  .hero,.hero.no-img,.hero.wide{grid-template-columns:minmax(0,1fr) var(--col) minmax(0,1fr)}
  .hero .txt{grid-column:2}
  .hero-img{grid-column:3;width:var(--side);margin-top:6px}
  .hero.wide .hero-img{grid-column:2;width:auto;margin-top:24px}
  .hero h1[class*="h1-long-"],.hero:not(.no-img):not(.wide) h1[class*="h1-long-"]{font-size:min(60px,calc(var(--col) / var(--h1-w)))}
  .toc-m{display:none}
  .body-row{padding-top:12px}
  .rail{display:block;grid-column:1;justify-self:end;width:var(--side)}
  .rail .stick{position:sticky;top:28px}
  .rail .lbl{font:700 13px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--ink3);margin:6px 0 10px}
  .rail .stick{transition:opacity .25s,visibility .25s}
  .rail.wait .stick{opacity:0;visibility:hidden}
  .article{grid-column:2}
  .slot-summary{float:right;width:var(--side);margin:0 calc(-1 * (var(--side) + var(--gap))) 20px 0}
  .inshort{background:none;padding:0}
  .slot-summary + .gg-blog-section h2{margin-top:0}
}
@media (prefers-reduced-motion:reduce){.rail .stick{transition:none}}
@media (max-width:900px){
  .gg-site-header-nav,.gg-hdr-sub{display:none}
  .gg-hamburger{display:flex}
}
@media (max-width:640px){
  .gg-site-header-inner{padding:0 16px;height:58px;gap:12px}
  .gg-site-header-logo .gg-logo-mark{height:34px}
  .gg-mobile-nav{padding:0 16px 12px}
  .frame{padding:0 16px}
  .hero{grid-template-columns:1fr;padding-top:22px;padding-bottom:20px}
  .kick-top{margin-bottom:10px}
  h1{font-size:42px;margin-bottom:12px}
  .hero h1[class*="h1-long-"],.hero:not(.no-img):not(.wide) h1[class*="h1-long-"]{font-size:min(42px,calc((100vw - 32px) / var(--h1-w)))}
  .dek{font-size:19px;margin-bottom:12px}
  .hero-img{margin-top:18px}
  .hero:not(.wide) .hero-img img{aspect-ratio:4/3;object-fit:cover;object-position:50% 30%}
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
