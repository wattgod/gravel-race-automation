"""Render functions for ledger-backed receipts (spec §5.5, §6.3 G1 still).

Every function returns an HTML string. Every value from the ledger is
escaped, and every element that names or quotes an athlete sits inside an
element carrying ``data-receipt-id`` so tests/test_no_unsourced_proof.py can
trace it back to an approved ledger entry.

Class prefixes: ``gg-receipt-*``, ``gg-exchange-*``, ``gg-archetype-*``.
"testimonial" never appears in a class name (the guard bans it).

The exchange carousel has no autoplay, so it needs no pause control
(WCAG 2.2.2). It is a CSS scroll-snap track that scrolls by hand without JS;
the JS adds prev/next buttons, a counter and arrow keys, and sends a GA
event only from a click or key press.
"""
from __future__ import annotations

import datetime as _dt
import html
from typing import Iterable, List, Optional, Sequence

from receipts_data import (
    ABILITIES,
    ABILITY_LABELS,
    AGE_BANDS,
    PRODUCT_LABELS,
    Exchange,
    Receipt,
    Result,
)

MEDIA_URL_PREFIX = "/athletes/media"
STORIES_PAGE_URL = "/athletes/"

_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December")


def esc(value) -> str:
    """Escape for text and quoted attributes. None renders empty; 0 renders "0"."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def month_year(value: str) -> str:
    """'2026-03-14' or '2026-03' -> 'March 2026'."""
    try:
        year, month = int(value[:4]), int(value[5:7])
        return f"{_MONTHS[month - 1]} {year}"
    except (ValueError, IndexError, TypeError):
        return esc(value)


def _paragraphs(text: str, cls: str) -> str:
    parts = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    return "".join(f'<p class="{cls}">{esc(p)}</p>' for p in parts)


def media_url(exchange: Exchange) -> str:
    return f"{MEDIA_URL_PREFIX}/{exchange.media_name}"


# ── Pieces ───────────────────────────────────────────────────────────────


def render_meta(r: Receipt) -> str:
    bits = [r.age_group, ABILITY_LABELS[r.ability], PRODUCT_LABELS[r.product]]
    if r.hours_per_week is not None:
        hours = int(r.hours_per_week) if float(r.hours_per_week).is_integer() else r.hours_per_week
        bits.append(f"{hours} hrs/week")
    return " &middot; ".join(esc(b) for b in bits)


def render_result(res: Result) -> str:
    detail = [esc(res.date)]
    if res.placing and res.field:
        detail.append(f"{esc(res.placing)} of {esc(res.field)}")
    elif res.placing:
        detail.append(esc(res.placing))
    if res.time:
        detail.append(esc(res.time))
    return (f'<li class="gg-receipt-result">'
            f'<a class="gg-receipt-result-link" href="{esc(res.official_url)}" '
            f'target="_blank" rel="noopener" data-proof="timing">{esc(res.event)}</a> '
            f'<span class="gg-receipt-result-detail">{" &middot; ".join(detail)}</span></li>')


def render_results(r: Receipt) -> str:
    if not r.results:
        return ""
    return f'<ul class="gg-receipt-results">{"".join(render_result(x) for x in r.results)}</ul>'


def render_quote(r: Receipt) -> str:
    if not r.quote:
        return ""
    return (f'<blockquote class="gg-receipt-quote">'
            f'<p>&ldquo;{esc(r.quote)}&rdquo;</p></blockquote>')


def render_disclosure(r: Receipt) -> str:
    if r.material_connection.kind == "none" or not r.material_connection.display:
        return ""
    return f'<p class="gg-receipt-disclosure">{esc(r.material_connection.display)}</p>'


# ── G1 receipt card (still) ──────────────────────────────────────────────


def render_receipt_card(r: Receipt) -> str:
    return (
        f'<article class="gg-receipt-card" data-receipt-id="{esc(r.id)}">'
        f'<header class="gg-receipt-head">'
        f'<span class="gg-receipt-name">{esc(r.public_name)}</span>'
        f'<span class="gg-receipt-meta">{render_meta(r)}</span>'
        f'</header>'
        f'{render_results(r)}{render_quote(r)}{render_disclosure(r)}'
        f'</article>'
    )


# ── Exchange carousel ────────────────────────────────────────────────────


def render_exchange_slide(ex: Exchange, r: Receipt, index: int, total: int) -> str:
    return (
        f'<figure class="gg-exchange-slide" data-receipt-id="{esc(r.id)}" '
        f'data-exchange-id="{esc(ex.id)}" role="group" aria-roledescription="slide" '
        f'aria-label="{index} of {total}">'
        f'<img class="gg-exchange-img" src="{esc(media_url(ex))}" '
        f'width="{int(ex.width)}" height="{int(ex.height)}" loading="lazy" decoding="async" '
        f'alt="{esc(ex.alt)}">'
        f'<figcaption class="gg-exchange-caption">'
        f'<a class="gg-exchange-who" href="#{esc(r.anchor)}">{esc(r.public_name)}</a> '
        f'<span class="gg-exchange-when">{esc(month_year(ex.date))}</span>'
        f'</figcaption></figure>'
    )


def render_exchange_carousel(receipts: Sequence[Receipt], *, label: str,
                             carousel_id: str = "gg-exchange-track") -> str:
    """All approved exchanges, best rank first. '' when there are none."""
    by_id = {r.id: r for r in receipts}
    exchanges = sorted((ex for r in receipts for ex in r.exchanges),
                       key=lambda ex: (ex.rank, ex.date, ex.receipt_id, ex.id))
    if not exchanges:
        return ""
    total = len(exchanges)
    slides = "".join(render_exchange_slide(ex, by_id[ex.receipt_id], i, total)
                     for i, ex in enumerate(exchanges, 1))
    track_id = esc(carousel_id)
    return (
        f'<div class="gg-exchange" data-exchange-carousel aria-roledescription="carousel" '
        f'aria-label="{esc(label)}">'
        f'<div class="gg-exchange-track" id="{track_id}" tabindex="0" '
        f'aria-label="{esc(label)}: scroll sideways or use the arrow keys">{slides}</div>'
        f'<div class="gg-exchange-nav">'
        f'<button type="button" class="gg-exchange-btn" data-exchange-prev '
        f'aria-controls="{track_id}" aria-label="Previous exchange">&larr;</button>'
        f'<span class="gg-exchange-counter" data-exchange-counter aria-live="polite">1 / {total}</span>'
        f'<button type="button" class="gg-exchange-btn" data-exchange-next '
        f'aria-controls="{track_id}" aria-label="Next exchange">&rarr;</button>'
        f'</div></div>'
    )


def get_exchange_carousel_js() -> str:
    """Prev/next, counter and arrow keys. No timers, no autoplay; GA events
    fire only inside click and keydown handlers."""
    return '''<script>
(function() {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.querySelectorAll('[data-exchange-carousel]').forEach(function(root) {
    var track = root.querySelector('.gg-exchange-track');
    var prev = root.querySelector('[data-exchange-prev]');
    var next = root.querySelector('[data-exchange-next]');
    var counter = root.querySelector('[data-exchange-counter]');
    if (!track || !prev || !next) return;
    var slides = track.querySelectorAll('.gg-exchange-slide');
    var total = slides.length;
    if (!total) return;
    root.classList.add('gg-exchange--js');

    function current() {
      var left = track.scrollLeft;
      // Scrolled to the end: the last slides fit in view and can't snap to
      // the left edge, so the last one counts as current.
      if (left >= track.scrollWidth - track.clientWidth - 2) return total - 1;
      var best = 0;
      var bestDist = Infinity;
      for (var i = 0; i < total; i++) {
        var d = Math.abs(slides[i].offsetLeft - track.offsetLeft - left);
        if (d < bestDist) { bestDist = d; best = i; }
      }
      return best;
    }
    function update() {
      if (counter) counter.textContent = (current() + 1) + ' / ' + total;
      prev.disabled = current() === 0;
      next.disabled = current() === total - 1;
    }
    function go(i) {
      var target = Math.max(0, Math.min(total - 1, i));
      track.scrollTo({ left: slides[target].offsetLeft - track.offsetLeft,
                       behavior: reduce ? 'auto' : 'smooth' });
    }
    function track_event(action) {
      if (typeof gtag === 'function') gtag('event', 'exchange_carousel', { action: action });
    }
    prev.addEventListener('click', function() { go(current() - 1); track_event('prev'); });
    next.addEventListener('click', function() { go(current() + 1); track_event('next'); });
    track.addEventListener('keydown', function(e) {
      if (e.key === 'ArrowLeft') { e.preventDefault(); go(current() - 1); track_event('key_prev'); }
      else if (e.key === 'ArrowRight') { e.preventDefault(); go(current() + 1); track_event('key_next'); }
    });
    track.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    update();
  });
})();
</script>'''


# ── Archetype grid ───────────────────────────────────────────────────────


def render_archetype_grid(receipts: Sequence[Receipt], *, caption: str) -> str:
    """Age band x ability. Covered cells list athletes linking to their story;
    uncovered cells say so. Nothing is padded."""
    head = "".join(f'<th scope="col">{esc(ABILITY_LABELS[a])}</th>' for a in ABILITIES)
    rows = []
    for band in AGE_BANDS:
        cells = []
        for ability in ABILITIES:
            here = [r for r in receipts if r.age_band == band and r.ability == ability]
            if here:
                items = "".join(
                    f'<li class="gg-archetype-athlete" data-receipt-id="{esc(r.id)}">'
                    f'<a href="#{esc(r.anchor)}">{esc(r.public_name)}</a></li>'
                    for r in here)
                cells.append(f'<td class="gg-archetype-cell">'
                             f'<ul class="gg-archetype-list">{items}</ul></td>')
            else:
                cells.append('<td class="gg-archetype-cell gg-archetype-empty">'
                             '<span aria-hidden="true">&mdash;</span>'
                             '<span class="gg-archetype-sr">none yet</span></td>')
        rows.append(f'<tr><th scope="row">{esc(band)}</th>{"".join(cells)}</tr>')
    return (
        f'<div class="gg-archetype-wrap"><table class="gg-archetype-grid">'
        f'<caption class="gg-archetype-caption">{esc(caption)}</caption>'
        f'<thead><tr><th scope="col">Age</th>{head}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


# ── Story block ──────────────────────────────────────────────────────────


def render_story(r: Receipt) -> str:
    story = ""
    if r.story is not None:
        if r.story.voice == "athlete":
            # The athlete's own words: quoted, untouched.
            story = (f'<blockquote class="gg-receipt-story-quote">'
                     f'{_paragraphs(r.story.text, "gg-receipt-story-text")}</blockquote>')
        else:
            story = f'<div class="gg-receipt-story-body">{_paragraphs(r.story.text, "gg-receipt-story-text")}</div>'
    tenure = f"Coached since {month_year(r.coached_since)}"
    return (
        f'<article class="gg-receipt-story" id="{esc(r.anchor)}" data-receipt-id="{esc(r.id)}">'
        f'<h3 class="gg-receipt-story-name">{esc(r.public_name)}</h3>'
        f'<p class="gg-receipt-story-meta">{render_meta(r)}</p>'
        f'<p class="gg-receipt-story-tenure">{esc(tenure)}</p>'
        f'{story}{render_quote(r)}{render_results(r)}{render_disclosure(r)}'
        f'</article>'
    )


def render_stories(receipts: Iterable[Receipt]) -> str:
    return "".join(render_story(r) for r in receipts)


# ── Count and verification lines ─────────────────────────────────────────

VERIFICATION_LINE = ("Every story here is from a coached athlete who approved the wording "
                     "in writing. Results link to official timing.")


def render_count_line(coached_count: Optional[int], coached_since: str, as_of: str) -> str:
    """Spec §3.3 opt-out-inclusive count. The number is ledger-backed and
    carries data-receipts-count so the proof guard can check it."""
    if coached_count is None:
        return ""
    as_of_txt = ""
    if as_of:
        try:
            d = _dt.date.fromisoformat(as_of)
            as_of_txt = f" (as of {_MONTHS[d.month - 1]} {d.day}, {d.year})"
        except ValueError:
            as_of_txt = ""
    return (f'<p class="gg-receipt-count" data-receipts-count="{int(coached_count)}">'
            f'{int(coached_count)} athletes coached since {esc(coached_since)}; those who '
            f'chose not to be named appear only in this count{esc(as_of_txt)}.</p>')


def render_verification_line() -> str:
    return f'<p class="gg-receipt-verification">{esc(VERIFICATION_LINE)}</p>'


# ── CSS ──────────────────────────────────────────────────────────────────


def get_receipts_css() -> str:
    """Brand tokens only: no hex, no radius, no shadow."""
    return '''
.gg-receipt-card, .gg-receipt-story { border: var(--gg-border-standard); background: var(--gg-color-warm-paper); padding: var(--gg-spacing-lg); }
.gg-receipt-head { display: flex; flex-wrap: wrap; gap: var(--gg-spacing-xs) var(--gg-spacing-md); align-items: baseline; margin-bottom: var(--gg-spacing-sm); }
.gg-receipt-name, .gg-receipt-story-name { font-family: var(--gg-font-data); font-size: var(--gg-font-size-sm); font-weight: var(--gg-font-weight-bold); letter-spacing: var(--gg-letter-spacing-wide); text-transform: uppercase; color: var(--gg-color-dark-brown); margin: 0; }
.gg-receipt-meta, .gg-receipt-story-meta, .gg-receipt-story-tenure { font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); letter-spacing: var(--gg-letter-spacing-wide); text-transform: uppercase; color: var(--gg-color-secondary-brown); margin: 0; }
.gg-receipt-story-tenure { margin-bottom: var(--gg-spacing-md); color: var(--gg-color-teal); font-weight: var(--gg-font-weight-bold); }
.gg-receipt-results { list-style: none; margin: var(--gg-spacing-md) 0 0; padding: 0; border-top: var(--gg-border-subtle); }
.gg-receipt-result { font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); color: var(--gg-color-dark-brown); padding: var(--gg-spacing-xs) 0; border-bottom: var(--gg-border-subtle); }
.gg-receipt-result-link { color: var(--gg-color-teal); font-weight: var(--gg-font-weight-bold); text-decoration: underline; }
.gg-receipt-result-link:hover { color: var(--gg-color-gold); }
.gg-receipt-result-detail { color: var(--gg-color-secondary-brown); }
.gg-receipt-quote, .gg-receipt-story-quote { margin: var(--gg-spacing-md) 0 0; padding: 0 0 0 var(--gg-spacing-md); border-left: var(--gg-border-width-heavy) solid var(--gg-color-gold); }
.gg-receipt-quote p, .gg-receipt-story-text { font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-base); line-height: var(--gg-line-height-prose); color: var(--gg-color-dark-brown); margin: 0 0 var(--gg-spacing-sm); max-width: 640px; }
.gg-receipt-disclosure { font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); color: var(--gg-color-secondary-brown); margin: var(--gg-spacing-sm) 0 0; }
.gg-receipt-count, .gg-receipt-verification { font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); line-height: var(--gg-line-height-relaxed); color: var(--gg-color-secondary-brown); margin: 0 0 var(--gg-spacing-sm); max-width: 720px; }
.gg-receipt-stories { display: grid; gap: var(--gg-spacing-lg); }

.gg-exchange { border: var(--gg-border-standard); background: var(--gg-color-sand); }
.gg-exchange-track { display: flex; align-items: flex-start; gap: var(--gg-spacing-md); overflow-x: auto; scroll-snap-type: x mandatory; overscroll-behavior-x: contain; padding: var(--gg-spacing-md); -webkit-overflow-scrolling: touch; }
.gg-exchange-track:focus-visible { outline: 3px solid var(--gg-color-gold); outline-offset: -3px; }
.gg-exchange-slide { flex: 0 0 auto; width: min(85%, 480px); scroll-snap-align: start; margin: 0; border: var(--gg-border-standard); background: var(--gg-color-warm-paper); }
.gg-exchange-img { display: block; width: 100%; height: auto; border-bottom: var(--gg-border-subtle); }
.gg-exchange-caption { display: flex; justify-content: space-between; gap: var(--gg-spacing-sm); padding: var(--gg-spacing-xs) var(--gg-spacing-sm); font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); letter-spacing: var(--gg-letter-spacing-wide); text-transform: uppercase; color: var(--gg-color-secondary-brown); }
.gg-exchange-who { color: var(--gg-color-dark-brown); font-weight: var(--gg-font-weight-bold); text-decoration: none; }
.gg-exchange-who:hover { color: var(--gg-color-teal); }
.gg-exchange-nav { display: none; align-items: center; justify-content: center; gap: var(--gg-spacing-md); padding: var(--gg-spacing-sm); border-top: var(--gg-border-subtle); }
.gg-exchange--js .gg-exchange-nav { display: flex; }
.gg-exchange-btn { min-width: 44px; min-height: 44px; font-family: var(--gg-font-data); font-size: var(--gg-font-size-md); font-weight: var(--gg-font-weight-bold); background: var(--gg-color-warm-paper); color: var(--gg-color-dark-brown); border: var(--gg-border-standard); cursor: pointer; transition: background-color var(--gg-transition-hover), color var(--gg-transition-hover); }
.gg-exchange-btn:hover { background: var(--gg-color-dark-brown); color: var(--gg-color-warm-paper); }
.gg-exchange-btn:disabled { cursor: default; color: var(--gg-color-tan); background: var(--gg-color-warm-paper); }
.gg-exchange-counter { font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-bold); letter-spacing: var(--gg-letter-spacing-wider); color: var(--gg-color-secondary-brown); min-width: 64px; text-align: center; }
@media (prefers-reduced-motion: reduce) { .gg-exchange-track { scroll-behavior: auto; } }

.gg-archetype-wrap { overflow-x: auto; }
.gg-archetype-grid { width: 100%; border-collapse: collapse; border: var(--gg-border-standard); background: var(--gg-color-warm-paper); }
.gg-archetype-caption { caption-side: top; text-align: left; font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); letter-spacing: var(--gg-letter-spacing-wide); text-transform: uppercase; color: var(--gg-color-secondary-brown); padding-bottom: var(--gg-spacing-xs); }
.gg-archetype-grid th, .gg-archetype-grid td { border: var(--gg-border-subtle); padding: var(--gg-spacing-sm); vertical-align: top; text-align: left; }
.gg-archetype-grid th { font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); font-weight: var(--gg-font-weight-bold); letter-spacing: var(--gg-letter-spacing-wide); text-transform: uppercase; color: var(--gg-color-dark-brown); background: var(--gg-color-sand); }
.gg-archetype-list { list-style: none; margin: 0; padding: 0; }
.gg-archetype-athlete a { font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); color: var(--gg-color-teal); }
.gg-archetype-empty { font-family: var(--gg-font-data); color: var(--gg-color-secondary-brown); }
.gg-archetype-sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
'''
