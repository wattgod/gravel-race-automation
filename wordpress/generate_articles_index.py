#!/usr/bin/env python3
"""
Generate the essay listing page, gravelgodcycling.com/articles/.

Built on the editorial shell (editorial_shell.py: "Gravel God x Endure
Glyph"): the same head (favicon, fonts, GA4 with consent defaults), site
header + Subscribe, footer and consent banner as the essays, and the shell's
tokens for type and colour. One card per essay: OG image, headline, dek,
date and reading time. The newest essay leads; the rest follow in a grid.

Data, so a new essay needs no change here:
- Which essays, and their dates: every entry in web/blog-index.json with
  category "article" (url + date required), newest first.
- What the card shows: read from the committed essay page,
  wordpress/articles/<slug>/index.html (the h1, the dek, og:image and its
  size, "N min read"), so the card always matches the page and its share
  card. An essay without a committed page falls back to its blog-index.json
  title (minus " | Gravel God"), excerpt and og_image.

Writes wordpress/articles/index.html (tracked, like the essays);
tests/test_articles_index.py fails if it is stale. Deploy: SCP it to
public_html/articles/index.html, then flush the SiteGround cache.

Usage:
    python3 wordpress/generate_articles_index.py
"""
from __future__ import annotations

import html as html_mod
import json
import re
import sys
import warnings
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cookie_consent import get_consent_banner_html  # noqa: E402
from editorial_shell import ArticleMeta, esc, render_footer, render_head, render_header  # noqa: E402
from shared_header import get_site_header_js  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_JSON = PROJECT_ROOT / "web" / "blog-index.json"
ARTICLES_DIR = PROJECT_ROOT / "wordpress" / "articles"
OUTPUT_PATH = ARTICLES_DIR / "index.html"
SITE_URL = "https://gravelgodcycling.com"

PAGE_TITLE = "Articles — Gravel God Cycling"
PAGE_DESCRIPTION = "In-depth articles on gravel cycling training, nutrition, and race strategy from Gravel God."
OG_DESCRIPTION = "In-depth articles on gravel cycling training, nutrition, and race strategy."
HEADLINE = "Hot Takes"
DEK = "In-depth articles on training, racing, and not being slow"
KICKER = "Essays"
EMPTY_TEXT = "More articles coming soon."

_TITLE_SUFFIX_RE = re.compile(r"\s*\|\s*Gravel God\s*$")


@dataclass(frozen=True)
class Essay:
    slug: str
    url: str
    headline: str
    dek: str
    published: date
    og_image: str = ""
    og_width: int | None = None
    og_height: int | None = None
    minutes: int | None = None

    @property
    def date_display(self) -> str:
        d = self.published
        return f"{d:%B} {d.day}, {d.year}"


# ── Data ──────────────────────────────────────────────────────


def _text(fragment: str) -> str:
    """Plain text of an HTML fragment (tags dropped, entities decoded)."""
    return " ".join(html_mod.unescape(re.sub(r"<[^>]+>", "", fragment)).split())


def _meta(page: str, prop: str) -> str:
    m = re.search(rf'<meta property="{re.escape(prop)}" content="([^"]*)"', page)
    return html_mod.unescape(m.group(1)) if m else ""


def read_essay_page(page: str) -> dict:
    """What a card needs from a committed essay page (editorial shell
    markup). Missing pieces come back empty/None."""
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
    dek = re.search(r'<p class="dek">(.*?)</p>', page, re.S)
    by = re.search(r'<p class="by">(.*?)</p>', page, re.S)
    mins = re.search(r"(\d+) min read", _text(by.group(1))) if by else None
    w, h = _meta(page, "og:image:width"), _meta(page, "og:image:height")
    return {
        "headline": _text(h1.group(1)) if h1 else "",
        "dek": _text(dek.group(1)) if dek else "",
        "og_image": _meta(page, "og:image"),
        "og_width": int(w) if w.isdigit() else None,
        "og_height": int(h) if h.isdigit() else None,
        "minutes": int(mins.group(1)) if mins else None,
    }


def _slug_from_url(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def load_essays(index_json: Path = INDEX_JSON, articles_dir: Path = ARTICLES_DIR) -> list[Essay]:
    """Every category "article" entry in blog-index.json, newest first.

    Raises ValueError on an entry without a /articles/ url or a valid date:
    a broken entry should stop the build, not ship a card with href=""."""
    entries = json.loads(index_json.read_text(encoding="utf-8"))
    essays = []
    for e in entries:
        if e.get("category") != "article":
            continue
        url = e.get("url") or ""
        if not url.startswith("/articles/") or url == "/articles/":
            raise ValueError(f"blog-index.json article {e.get('slug')!r} has no /articles/<slug>/ url: {url!r}")
        try:
            published = date.fromisoformat(e.get("date") or "")
        except ValueError:
            raise ValueError(f"blog-index.json article {url} has no valid date: {e.get('date')!r}") from None
        slug = _slug_from_url(url)
        page_path = articles_dir / slug / "index.html"
        if page_path.exists():
            page = read_essay_page(page_path.read_text(encoding="utf-8"))
        else:
            warnings.warn(f"no committed page for {url} ({page_path}); card uses blog-index.json fields")
            page = {}
        essays.append(Essay(
            slug=slug,
            url=url,
            headline=page.get("headline") or _TITLE_SUFFIX_RE.sub("", e.get("title") or "") or slug,
            dek=page.get("dek") or e.get("excerpt") or "",
            published=published,
            og_image=page.get("og_image") or e.get("og_image") or "",
            og_width=page.get("og_width"),
            og_height=page.get("og_height"),
            minutes=page.get("minutes"),
        ))
    essays.sort(key=lambda x: (x.published, x.url), reverse=True)
    return essays


# ── Markup ────────────────────────────────────────────────────


def render_card(essay: Essay, *, lead: bool = False) -> str:
    cls = "gg-ai-card gg-ai-lead" if lead else "gg-ai-card"
    img = ""
    if essay.og_image:
        size = ""
        if essay.og_width and essay.og_height:
            size = f' width="{essay.og_width}" height="{essay.og_height}"'
        loading = 'loading="eager" fetchpriority="high"' if lead else 'loading="lazy"'
        img = (f'\n    <div class="gg-ai-img"><img src="{esc(essay.og_image)}" alt=""{size} '
               f'{loading} decoding="async"></div>')
    meta = f'<time datetime="{essay.published.isoformat()}">{esc(essay.date_display)}</time>'
    if essay.minutes:
        meta += f" &middot; {essay.minutes} min read"
    dek = f'\n      <p class="gg-ai-dek">{esc(essay.dek)}</p>' if essay.dek else ""
    more = '\n      <span class="gg-ai-more" aria-hidden="true">Read the essay <span class="chev">&rsaquo;</span></span>' if lead else ""
    return f"""  <a class="{cls}" href="{esc(essay.url)}">{img}
    <div class="gg-ai-txt">
      <p class="gg-ai-date">{meta}</p>
      <h2 class="gg-ai-title">{esc(essay.headline)}</h2>{dek}{more}
    </div>
  </a>"""


def render_listing(essays: list[Essay]) -> str:
    if not essays:
        return f'<p class="gg-ai-empty">{esc(EMPTY_TEXT)}</p>'
    lead, rest = essays[0], essays[1:]
    out = render_card(lead, lead=True)
    if rest:
        out += '\n<div class="gg-ai-grid">\n' + "\n".join(render_card(e) for e in rest) + "\n</div>"
    return out


LISTING_CSS = """
/* articles listing (generate_articles_index.py) on the shell tokens */
.gg-ai-page{max-width:1200px;box-sizing:content-box;margin:0 auto;padding:0 32px}
.gg-ai-hero{padding:40px 0 32px;box-shadow:inset 0 -1px 0 var(--sand2);margin-bottom:40px}
.gg-ai-hero .dek{margin-bottom:0}
.gg-ai-card{display:block;color:var(--ink);text-decoration:none}
.gg-ai-img{background:var(--sand);aspect-ratio:1200/630;overflow:hidden}
.gg-ai-img img{display:block;width:100%;height:100%;object-fit:cover}
.gg-ai-txt{padding:18px 0 0}
.gg-ai-date{font:500 14px var(--mono);letter-spacing:.02em;color:var(--ink2);margin:0 0 10px}
.gg-ai-title{font:700 26px/1.15 var(--serif);letter-spacing:-.01em;margin:0 0 10px;text-wrap:balance}
.gg-ai-dek{font:italic 400 18px/1.45 var(--serif);color:var(--ink2);margin:0}
.gg-ai-card:hover .gg-ai-title{text-decoration:underline;text-underline-offset:5px;text-decoration-thickness:2px}
.gg-ai-more{display:inline-flex;align-items:center;gap:6px;margin-top:18px;font:700 14px var(--mono);letter-spacing:.05em;text-transform:uppercase;color:var(--teal-ink)}
.gg-ai-more .chev{font-size:17px;line-height:1}
.gg-ai-lead .gg-ai-title{font-size:40px;line-height:1.08}
.gg-ai-lead .gg-ai-dek{font-size:21px}
.gg-ai-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,340px),1fr));gap:48px 32px;margin-top:56px;padding-top:40px;box-shadow:inset 0 1px 0 var(--sand2)}
.gg-ai-empty{font:500 16px var(--mono);color:var(--ink2);padding:32px 0}
@media (min-width:900px){
  .gg-ai-lead{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);column-gap:40px;align-items:center}
  .gg-ai-lead .gg-ai-txt{padding:0}
}
@media (max-width:640px){
  .gg-ai-page{padding:0 16px}
  .gg-ai-hero{padding:22px 0 24px;margin-bottom:28px}
  .gg-ai-title{font-size:24px}
  .gg-ai-lead .gg-ai-title{font-size:30px}
  .gg-ai-lead .gg-ai-dek{font-size:19px}
  .gg-ai-dek{font-size:17px}
  .gg-ai-grid{gap:40px;margin-top:40px;padding-top:32px}
}
"""


def page_meta() -> ArticleMeta:
    """Head metadata for the listing (title, description, og:*, canonical,
    robots), carried over from the pre-shell page unchanged."""
    return ArticleMeta(
        slug="articles",
        canonical_url=f"{SITE_URL}/articles/",
        title=PAGE_TITLE,
        description=PAGE_DESCRIPTION,
        og_title=PAGE_TITLE,
        og_description=OG_DESCRIPTION,
        og_type="website",
        headline=HEADLINE,
        date_published=date(2026, 3, 26),  # unused by the head; required field
        robots="index, follow",
        track_article_events=False,  # a listing, not an article: keep the funnel clean
    )


def render_articles_index(essays: list[Essay]) -> str:
    meta = page_meta()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{render_head(meta, extra_css=LISTING_CSS)}
</head>
<body>
{render_header(meta.nav_active)}

<main class="gg-ai-page">
  <header class="gg-ai-hero">
    <p class="kick-top">{esc(KICKER)}</p>
    <h1>{esc(HEADLINE)}</h1>
    <p class="dek">{esc(DEK)}</p>
  </header>
{render_listing(essays)}
</main>

{render_footer()}
<script>{get_site_header_js()}</script>
{get_consent_banner_html()}
</body>
</html>
"""


def render() -> str:
    return render_articles_index(load_essays())


def main() -> None:
    essays = load_essays()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(render_articles_index(essays), encoding="utf-8")
    print(f"Generated {OUTPUT_PATH} ({len(essays)} essays)")


if __name__ == "__main__":
    main()
