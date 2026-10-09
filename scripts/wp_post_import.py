#!/usr/bin/env python3
"""Import a WordPress (Elementor) blog post into the editorial shell, at its SAME root URL.

    python3 scripts/wp_post_import.py 3504            # convert + images + scaffold
    python3 scripts/wp_post_import.py 3504 --no-images
    python3 scripts/wp_post_import.py 3504 --aside Sidebar

Inputs (outside the repo; see docs/article-cadence.md "Imported WordPress posts"):
  --inventory   inventory.json from the 2026-10-09 WP audit (one record per post:
                slug, images with full-size URLs, comments, categories)
  --snapshots   snapshots/<id>.html: the post's rendered Elementor content (the
                word-for-word baseline) and <id>.txt (its visible text)
  --cache       downloaded live HTML and original images (default ~/.cache/gg-wp-import)

Outputs (in the repo):
  wordpress/post_sources/<slug>.body.html   the body: shell sections, word-for-word text,
                                            <!--GG:FIGURE name--> markers for images
  wordpress/post_sources/<slug>.json        live metadata + figures + comments (generated)
  wordpress/post_sources/<module>.py        scaffolded once, then hand-edited: alt text,
                                            "In short", infographics (never overwritten)
  wordpress/posts/<slug>/img/               optimized images (WebP 1x/@2x/phone; GIFs as
                                            MP4 + WebM + WebP poster)
  <specs>/pilot/<slug>/images.json          per-image manifest (with --manifest-dir)

Rules the converter holds:
- Body text is the snapshot's text, word for word (tests/test_wp_post_import.py diffs
  the rendered page against <id>.txt). Nothing is rewritten; markup is only mapped.
- Metadata comes from the LIVE page's <head> (title, description, canonical, OG,
  article:published_time), never the REST API (aioseo canonicals are wrong for some posts).
- Headings: the highest level used becomes h2 (a contents entry), the next h3, so
  h5/h6-only posts get a working Contents. Heading text is unchanged.
- Widgets: text-editor -> paragraphs/lists/quotes; heading -> h2/h3; image -> figure
  marker; blockquote (Click-to-Tweet) -> pull quote; image-gallery/gallery -> figure grid;
  video (YouTube) and YouTube iframes -> click-to-load embed (no third-party JS until
  clicked); divider -> <hr>; icon-list -> <ul>; spacer/share-buttons -> dropped. Any
  other widget raises, so nothing is silently lost.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
WORDPRESS = ROOT / "wordpress"
POST_SOURCES = WORDPRESS / "post_sources"
POSTS_OUT = WORDPRESS / "posts"
SITE = "https://gravelgodcycling.com"
SITE_TZ = ZoneInfo("America/Denver")
DEFAULT_CACHE = Path.home() / ".cache" / "gg-wp-import"
DEFAULT_SPECS = Path.home() / "specs" / "gg-wp-posts-2026-10-09"
UA = "Mozilla/5.0 (GravelGod wp_post_import)"

# Image renditions. The reading column is 680 CSS px, so a 1600w 1x already
# covers DPR 2.3; @2x is only written when the source really has 2x pixels.
ONE_X = 1600
PHONE_W = 660
GIF_MAX_W = 1280
WEBP_QUALITY = 80

DROP_WIDGETS = ("share-buttons.", "posts.", "spacer.")
KNOWN_WIDGETS = ("text-editor.", "heading.", "image.", "blockquote.", "image-gallery.", "gallery.",
                 "video.", "divider.", "icon-list.")


# ── Mini DOM ──────────────────────────────────────────────────

VOID = {"br", "img", "hr", "meta", "link", "input", "source", "wbr", "col", "area", "embed", "track"}


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["Node | str"] = field(default_factory=list)

    def get(self, name: str, default: str = "") -> str:
        return self.attrs.get(name) or default

    @property
    def classes(self) -> set[str]:
        return set(self.get("class").split())

    def iter(self):
        yield self
        for c in self.children:
            if isinstance(c, Node):
                yield from c.iter()

    def find_all(self, pred) -> list["Node"]:
        return [n for n in self.iter() if pred(n)]

    def text(self) -> str:
        out = []
        for c in self.children:
            if isinstance(c, str):
                out.append(c)
            elif c.tag == "br":
                out.append(" ")
            elif c.tag not in ("script", "style", "noscript"):
                out.append(c.text())
        return "".join(out)


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v or "") for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, {k: (v or "") for k, v in attrs}))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse_html(text: str) -> Node:
    b = _TreeBuilder()
    b.feed(text)
    b.close()
    return b.root


# ── Helpers ───────────────────────────────────────────────────


def esc_text(s: str) -> str:
    return html.escape(s, quote=False)


def esc_attr(s: str) -> str:
    return html.escape(s, quote=True)


def name_from_url(url: str) -> str:
    """Stable figure name from an upload URL: 'Ut-på-baeretur-1.png' -> 'ut-pa-baeretur-1'."""
    stem = urllib.parse.unquote(url.split("?")[0].rsplit("/", 1)[-1]).rsplit(".", 1)[0]
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")


def original_upload_url(url: str) -> str:
    """Strip WordPress size suffixes: x-1024x576.png -> x.png (the -scaled variant stays)."""
    u = url.split("?")[0]
    return re.sub(r"-\d+x\d+(\.\w+)$", r"\1", u)


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", urllib.parse.unquote(s))


def youtube_id(url: str) -> tuple[str, int] | None:
    """(video id, start seconds) for a YouTube watch/short/embed URL."""
    p = urllib.parse.urlparse(html.unescape(url))
    host = p.netloc.lower().removeprefix("www.").removeprefix("m.")
    q = urllib.parse.parse_qs(p.query)
    vid = None
    if host == "youtu.be":
        vid = p.path.strip("/").split("/")[0]
    elif host in ("youtube.com", "youtube-nocookie.com"):
        if p.path == "/watch":
            vid = (q.get("v") or [None])[0]
        else:
            m = re.match(r"/(?:embed|shorts|v)/([^/?#]+)", p.path)
            vid = m.group(1) if m else None
    if not vid or not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", vid):
        return None
    t = (q.get("t") or q.get("start") or ["0"])[0]
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s?)?", t or "0")
    start = 0
    if m:
        h, mi, s = (int(x) if x else 0 for x in m.groups())
        start = h * 3600 + mi * 60 + s
    return vid, start


def render_youtube(vid: str, start: int, title: str = "") -> str:
    """Click-to-load YouTube: a link with the video's thumbnail. The shared post JS
    swaps in a youtube-nocookie iframe on click; without JS it opens YouTube."""
    watch = f"https://www.youtube.com/watch?v={vid}" + (f"&t={start}s" if start else "")
    label = f"Play video{': ' + title if title else ''} (loads YouTube)"
    return (
        f'<figure class="gg-yt"><a class="gg-yt-link" href="{esc_attr(watch)}" data-yt="{esc_attr(vid)}" '
        f'data-start="{start}" aria-label="{esc_attr(label)}">'
        f'<img src="https://i.ytimg.com/vi/{esc_attr(vid)}/hqdefault.jpg" alt="" width="480" height="360" '
        f'loading="lazy" decoding="async"><span class="gg-yt-play" data-gg-chrome aria-hidden="true">Play</span>'
        f"</a></figure>"
    )


# ── Converter ─────────────────────────────────────────────────

INLINE_KEEP = {"a", "strong", "em", "sup", "sub", "code", "br", "s", "del", "mark", "small", "abbr"}
INLINE_RENAME = {"b": "strong", "i": "em"}
BLOCKS = {"p", "ul", "ol", "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "pre",
          "table", "thead", "tbody", "tr", "td", "th", "figure", "figcaption", "div", "section",
          "dl", "dt", "dd"}
HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")


@dataclass
class FigureSpec:
    name: str
    url: str  # full-size upload URL (download source)
    kind: str  # "still" | "gif"
    width: int
    height: int
    caption_html: str = ""
    link: str = ""
    inventory_class: str = ""
    inventory_alt: str = ""
    section: str = ""

    def to_json(self) -> dict:
        return dict(self.__dict__)


@dataclass
class Converted:
    body_html: str
    figures: list[FigureSpec]
    galleries: dict[str, list[str]]
    heading_map: dict[str, str]
    headings: list[tuple[str, str]]  # (level after mapping, text)


class ElementorConverter:
    def __init__(self, images_by_url: dict[str, dict] | None = None, asides: tuple[str, ...] = ()) -> None:
        self.images_by_url = images_by_url or {}
        self.asides = set(asides)
        self.figures: list[FigureSpec] = []
        self.galleries: dict[str, list[str]] = {}
        self.heading_map: dict[str, str] = {}
        self._names: set[str] = set()
        self._ids: set[str] = set()
        self._pq = 0

    # -- entry --
    def convert(self, content_html: str) -> Converted:
        root = parse_html(content_html)
        widgets = self._widgets(root)
        self.heading_map = self._heading_map(widgets)
        blocks: list[tuple[str, str]] = []  # (kind, html); kind "h2" starts a section
        i = 0
        while i < len(widgets):
            w = widgets[i]
            wt = w.get("data-widget_type")
            if wt.startswith("heading.") and self._heading_text(w) in self.asides:
                nxt = widgets[i + 1] if i + 1 < len(widgets) else None
                if not nxt or not nxt.get("data-widget_type").startswith("text-editor."):
                    raise ValueError(f"aside {self._heading_text(w)!r} must be followed by a text widget")
                inner = "\n".join(h for _, h in self._text_editor(nxt, in_aside=True))
                hid = "aside-" + re.sub(r"[^a-z0-9]+", "-", self._heading_text(w).lower()).strip("-")
                head = self._heading_widget(w, force="h3")[0][1]
                blocks.append(("block", f'<aside class="gg-case-study gg-sidebar" id="{hid}">\n{head}\n{inner}\n</aside>'))
                i += 2
                continue
            blocks += self._widget(w)
            i += 1
        body, headings = self._sections(blocks)
        return Converted(body, self.figures, self.galleries, self.heading_map, headings)

    def _widgets(self, root: Node) -> list[Node]:
        out: list[Node] = []

        def walk(n: Node) -> None:
            for c in n.children:
                if not isinstance(c, Node):
                    continue
                if c.get("data-widget_type"):
                    out.append(c)
                else:
                    walk(c)
        walk(root)
        for w in out:
            wt = w.get("data-widget_type")
            if not wt.startswith(KNOWN_WIDGETS + DROP_WIDGETS):
                raise NotImplementedError(f"Elementor widget {wt!r} has no mapping yet (add one in wp_post_import.py)")
        return out

    def _heading_text(self, w: Node) -> str:
        hs = w.find_all(lambda n: n.tag in HEADINGS)
        return re.sub(r"\s+", " ", hs[0].text()).strip() if hs else ""

    def _heading_map(self, widgets: list[Node]) -> dict[str, str]:
        levels = set()
        for w in widgets:
            wt = w.get("data-widget_type")
            if wt.startswith(DROP_WIDGETS):
                continue
            if wt.startswith("heading.") and self._heading_text(w) in self.asides:
                continue
            for h in w.find_all(lambda n: n.tag in HEADINGS):
                if h.text().strip():
                    levels.add(int(h.tag[1]))
        ordered = sorted(levels)
        return {f"h{lv}": ("h2" if k == 0 else "h3" if k == 1 else "h4") for k, lv in enumerate(ordered)}

    # -- widgets --
    def _widget(self, w: Node) -> list[tuple[str, str]]:
        wt = w.get("data-widget_type")
        if wt.startswith(DROP_WIDGETS):
            return []
        if wt.startswith("text-editor."):
            return self._text_editor(w)
        if wt.startswith("heading."):
            return self._heading_widget(w)
        if wt.startswith("image."):
            return self._image_widget(w)
        if wt.startswith("blockquote."):
            return [("block", self._pullquote(w))]
        if wt.startswith(("image-gallery.", "gallery.")):
            return [("block", self._gallery(w))]
        if wt.startswith("video."):
            return [("block", self._video(w))]
        if wt.startswith("divider."):
            return [("block", "<hr>")]
        if wt.startswith("icon-list."):
            items = [self._inline_children(li).strip() for li in w.find_all(lambda n: n.tag == "li")]
            return [("block", "<ul>\n" + "\n".join(f"<li>{t}</li>" for t in items if t) + "\n</ul>")]
        raise NotImplementedError(wt)

    def _heading_widget(self, w: Node, force: str | None = None) -> list[tuple[str, str]]:
        hs = w.find_all(lambda n: n.tag in HEADINGS)
        if not hs or not hs[0].text().strip():
            return []
        lvl = force or self.heading_map[hs[0].tag]
        return [(lvl, f"<{lvl}>{self._heading_inner(hs[0])}</{lvl}>")]

    def _heading_inner(self, h: Node) -> str:
        """Heading text with its markup; bold is dropped (headings are bold already)."""
        return re.sub(r"</?strong>", "", self._inline_children(h)).strip()

    def _container(self, w: Node) -> Node:
        c = w.find_all(lambda n: "elementor-widget-container" in n.classes)
        return c[0] if c else w

    def _text_editor(self, w: Node, in_aside: bool = False) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        self._blocks_of(self._container(w), out, in_aside)
        return out

    def _blocks_of(self, parent: Node, out: list[tuple[str, str]], in_aside: bool) -> None:
        run: list[Node | str] = []

        def flush() -> None:
            if run:
                inner = "".join(self._inline(x) for x in run)
                if inner.strip():
                    out.append(("block", f"<p>{inner.strip()}</p>"))
                run.clear()

        for c in parent.children:
            if isinstance(c, str) or (c.tag not in BLOCKS and c.tag not in ("img", "iframe")):
                if isinstance(c, Node) and c.tag in ("script", "style", "noscript"):
                    continue
                if isinstance(c, Node) and (c.find_all(lambda n: n.tag in BLOCKS) or c.find_all(lambda n: n.tag == "img")):
                    flush()
                    self._blocks_of(c, out, in_aside)  # a span/a wrapping blocks: unwrap
                    continue
                run.append(c)
                continue
            flush()
            out.extend(self._block(c, in_aside))
        flush()

    def _block(self, n: Node, in_aside: bool) -> list[tuple[str, str]]:
        t = n.tag
        if t in ("div", "section"):
            out: list[tuple[str, str]] = []
            self._blocks_of(n, out, in_aside)
            return out
        if t == "img":
            return self._image_marker(n)
        if t == "iframe":
            yt = youtube_id(n.get("src") or n.get("data-src"))
            if not yt:
                raise NotImplementedError(f"iframe {n.get('src')!r} has no mapping")
            return [("block", render_youtube(*yt, title=n.get("title")))]
        if t in HEADINGS:
            if not n.text().strip():
                return []
            lvl = "h3" if in_aside else self.heading_map[t]
            return [(lvl, f"<{lvl}>{self._heading_inner(n)}</{lvl}>")]
        if t == "hr":
            return [("block", "<hr>")]
        if t == "p":
            figs: list[tuple[str, str]] = []
            for x in n.find_all(lambda x: x.tag in ("img", "iframe")):
                figs += self._block(x, in_aside)  # images/embeds go after the paragraph
            inner = self._inline_children(n).strip()
            para = [("block", f"<p{self._label_id(inner)}>{inner}</p>")] if inner and _visible(inner) else []
            return para + figs
        if t in ("ul", "ol"):
            items = []
            for li in n.children:
                if isinstance(li, Node) and li.tag == "li":
                    items.append(f"<li>{self._li(li, in_aside)}</li>")
            attrs = ""
            if t == "ol" and n.get("start"):
                attrs = f' start="{esc_attr(n.get("start"))}"'
            return [("block", f"<{t}{attrs}>\n" + "\n".join(items) + f"\n</{t}>")]
        if t == "blockquote":
            out = []
            self._blocks_of(n, out, in_aside)
            inner = "\n".join(h for _, h in out)
            return [("block", f"<blockquote>\n{inner}\n</blockquote>")]
        if t == "pre":
            return [("block", f"<pre>{esc_text(n.text())}</pre>")]
        if t in ("table", "thead", "tbody", "tr", "td", "th", "dl", "dt", "dd", "figure", "figcaption", "li"):
            return [("block", self._passthrough(n))]
        raise NotImplementedError(t)

    def _label_id(self, inner: str) -> str:
        """A bold-only paragraph ("<strong>What I hated about today</strong>") is a
        pseudo-heading: give it an id so "In short" can link to it."""
        m = re.fullmatch(r"<strong>([^<]{1,80})</strong>", inner)
        if not m:
            return ""
        base = re.sub(r"[^a-z0-9]+", "-", html.unescape(m.group(1)).lower()).strip("-")[:60]
        if not base:
            return ""
        sid, k = base, 2
        while sid in self._ids:
            sid, k = f"{base}-{k}", k + 1
        self._ids.add(sid)
        return f' id="{sid}"'

    def _li(self, li: Node, in_aside: bool) -> str:
        if any(isinstance(c, Node) and c.tag in ("ul", "ol", "p") for c in li.children):
            parts = []
            for c in li.children:
                if isinstance(c, Node) and c.tag in ("ul", "ol"):
                    parts.append(self._block(c, in_aside)[0][1])
                elif isinstance(c, Node) and c.tag == "p":
                    parts.append(self._inline_children(c))
                else:
                    parts.append(self._inline(c))
            return "".join(parts).strip()
        return self._inline_children(li).strip()

    def _passthrough(self, n: Node) -> str:
        inner = "".join(self._passthrough(c) if isinstance(c, Node) and c.tag in BLOCKS else self._inline(c)
                        for c in n.children)
        span = ""
        for a in ("colspan", "rowspan"):
            if n.get(a):
                span += f' {a}="{esc_attr(n.get(a))}"'
        return f"<{n.tag}{span}>{inner}</{n.tag}>"

    def _inline_children(self, n: Node) -> str:
        return "".join(self._inline(c) for c in n.children)

    def _inline(self, c: Node | str) -> str:
        if isinstance(c, str):
            return esc_text(c)
        t = INLINE_RENAME.get(c.tag, c.tag)
        if t in ("script", "style", "noscript", "img", "iframe"):
            return ""
        if t == "br":
            return "<br>"
        inner = self._inline_children(c)
        if t == "a":
            href = c.get("href")
            if not href:
                return inner
            attrs = f' href="{esc_attr(href)}"'
            if c.get("target") == "_blank":
                attrs += ' target="_blank" rel="noopener"'
            return f"<a{attrs}>{inner}</a>"
        if t in INLINE_KEEP:
            return f"<{t}>{inner}</{t}>" if inner else ""
        if t in HEADINGS or t in BLOCKS:  # block inside inline context (e.g. <p> in <h6>)
            return inner
        return inner  # span, font, u, ...: unwrap, keep the text

    # -- images --
    def _lookup(self, src: str) -> dict:
        key = _nfc(original_upload_url(src))
        for cand in (key, re.sub(r"(\.\w+)$", r"-scaled\1", key), key.replace("-scaled.", ".")):
            if cand in self.images_by_url:
                return self.images_by_url[cand]
        return {}

    def _unique(self, name: str) -> str:
        base, k = name, 2
        while name in self._names:
            name = f"{base}-{k}"
            k += 1
        self._names.add(name)
        return name

    def _spec(self, src: str, width: str = "", height: str = "", link: str = "", caption_html: str = "") -> FigureSpec:
        inv = self._lookup(src)
        full = inv.get("full_url") or original_upload_url(src)
        ext = full.rsplit(".", 1)[-1].lower()
        spec = FigureSpec(
            name=self._unique(name_from_url(full)),
            url=full,
            kind="gif" if ext == "gif" else "still",
            width=int(inv.get("width") or width or 0),
            height=int(inv.get("height") or height or 0),
            caption_html=caption_html,
            link=link if link and "/wp-content/uploads/" not in link else "",
            inventory_class=inv.get("class_", ""),
            inventory_alt=inv.get("alt", ""),
        )
        return spec

    def _image_marker(self, img: Node, caption_html: str = "", link: str = "") -> list[tuple[str, str]]:
        src = img.get("data-src") or img.get("src")
        if not src or src.startswith("data:"):
            return []
        spec = self._spec(src, img.get("width"), img.get("height"), link, caption_html)
        self.figures.append(spec)
        return [("block", f"<!--GG:FIGURE {spec.name}-->")]

    def _image_widget(self, w: Node) -> list[tuple[str, str]]:
        imgs = w.find_all(lambda n: n.tag == "img")
        if not imgs:
            return []
        caps = w.find_all(lambda n: n.tag == "figcaption")
        cap = self._inline_children(caps[0]).strip() if caps else ""
        links = w.find_all(lambda n: n.tag == "a" and n.get("href"))
        return self._image_marker(imgs[0], cap, links[0].get("href") if links else "")

    def _gallery(self, w: Node) -> str:
        names = []
        for n in w.iter():
            src = ""
            if n.tag == "img":
                src = n.get("data-src") or n.get("src")
            elif n.get("data-thumbnail"):
                src = n.get("data-thumbnail")
            if src and not src.startswith("data:"):
                spec = self._spec(src)
                self.figures.append(spec)
                names.append(spec.name)
        gname = self._unique("gallery-" + (names[0] if names else "empty"))
        self.galleries[gname] = names
        return f"<!--GG:GALLERY {gname}-->"

    # -- other widgets --
    def _pullquote(self, w: Node) -> str:
        self._pq += 1
        content = w.find_all(lambda n: "elementor-blockquote__content" in n.classes)
        cite = w.find_all(lambda n: "elementor-blockquote__author" in n.classes)
        body = self._inline_children(content[0]).strip() if content else self._inline_children(w).strip()
        cap = f"\n  <figcaption>{self._inline_children(cite[0]).strip()}</figcaption>" if cite and cite[0].text().strip() else ""
        return (f'<figure class="gg-pullquote" id="pull-quote-{self._pq}">\n'
                f"  <blockquote><p>{body}</p></blockquote>{cap}\n</figure>")

    def _video(self, w: Node) -> str:
        try:
            settings = json.loads(html.unescape(w.get("data-settings") or "{}"))
        except json.JSONDecodeError:
            settings = {}
        url = settings.get("youtube_url") or ""
        yt = youtube_id(url)
        if not yt:
            raise NotImplementedError(f"video widget without a YouTube URL: {settings}")
        start = int(settings.get("start") or yt[1] or 0)
        return render_youtube(yt[0], start)

    # -- sections --
    def _sections(self, blocks: list[tuple[str, str]]) -> tuple[str, list[tuple[str, str]]]:
        sections: list[list[str]] = [[]]
        headings = []
        for kind, h in blocks:
            if kind == "h2" and sections[-1]:
                sections.append([])
            if kind in ("h2", "h3", "h4"):
                headings.append((kind, re.sub(r"<[^>]+>", "", html.unescape(h))))
            sections[-1].append(h)
        out = []
        for s in sections:
            if s:
                out.append('<section class="gg-blog-section">\n' + "\n".join(s) + "\n</section>")
        return "\n".join(out) + "\n", headings


def _visible(fragment: str) -> bool:
    return bool(re.sub(r"<[^>]+>|\s|&nbsp;|\xa0", "", fragment))


# ── Visible text (the word-for-word proof) ───────────────────


class _TextOf(HTMLParser):
    """Visible text, block-separated. Skips script/style/template, elements carrying
    data-gg-added / data-gg-chrome / data-gg-archive, the shell's .slot blocks
    ("In short", ladder) and any element whose id is in skip_ids."""

    BLOCK_END = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "figcaption",
                 "section", "aside", "figure", "tr", "td", "th", "pre", "ul", "ol"}

    def __init__(self, skip_ids: set[str]) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_ids = skip_ids
        self.stack: list[tuple[str, bool]] = []
        self.skip = 0
        self.out: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in VOID:
            if tag == "br" and not self.skip:
                self.out.append(" ")
            return
        cls = set((a.get("class") or "").split())
        sk = (tag in ("script", "style", "template", "noscript", "svg", "button")
              or any(k in a for k in ("data-gg-added", "data-gg-chrome", "data-gg-archive"))
              or "slot" in cls or (a.get("id") in self.skip_ids))
        self.stack.append((tag, sk))
        if sk:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for _, sk in self.stack[i:]:
                    if sk:
                        self.skip -= 1
                del self.stack[i:]
                break
        if not self.skip and tag in self.BLOCK_END:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def visible_text(fragment: str, skip_ids: set[str] | frozenset[str] = frozenset()) -> str:
    p = _TextOf(set(skip_ids))
    p.feed(fragment)
    p.close()
    return "".join(p.out)


def words(text: str) -> list[str]:
    """Whitespace-separated tokens; NBSP and zero-width spaces count as whitespace."""
    return text.replace("​", " ").split()


def article_of(page_html: str) -> str:
    m = re.search(r'<article class="article" id="article">(.*)</article>', page_html, re.S)
    if not m:
        raise ValueError("no <article> in page")
    return m.group(1)


def text_diff(baseline_txt: str, page_html: str, skip_ids: set[str] | frozenset[str] = frozenset()) -> list[str]:
    """Unified diff (one word per line) of the snapshot text vs the page's article text.
    Empty list = word for word."""
    import difflib
    a = words(baseline_txt)
    b = words(visible_text(article_of(page_html), skip_ids))
    if a == b:
        return []
    return list(difflib.unified_diff(a, b, "snapshot", "page", lineterm="", n=3))


# ── Live metadata ─────────────────────────────────────────────


class _HeadParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.canonical = ""
        self.title = ""
        self._in_title = False
        self._in_ld = False
        self.ld: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "meta":
            key = a.get("property") or a.get("name")
            if key and key not in self.meta:
                self.meta[key] = a.get("content", "")
        elif tag == "link" and a.get("rel") == "canonical" and not self.canonical:
            self.canonical = a.get("href", "")
        elif tag == "title" and not self.title:
            self._in_title = True
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._in_ld = True
            self.ld.append("")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "script":
            self._in_ld = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_ld:
            self.ld[-1] += data


def extract_live_meta(page_html: str) -> dict:
    """Title, description, canonical, OG, dates, headline and author from a live WP page."""
    p = _HeadParser()
    p.feed(page_html)
    m = p.meta
    posting: dict = {}
    authors: dict[str, str] = {}
    for block in p.ld:
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        for node in data.get("@graph", [data]) if isinstance(data, dict) else []:
            types = node.get("@type")
            types = types if isinstance(types, list) else [types]
            if "BlogPosting" in types or "Article" in types:
                posting = node
            if "Person" in types and node.get("@id"):
                authors[node["@id"]] = node.get("name", "")
    author = posting.get("author") or {}
    author_name = author.get("name") or authors.get(author.get("@id", ""), "")
    image = posting.get("image") or {}
    if isinstance(image, list):
        image = image[0] if image else {}
    if isinstance(image, str):
        image = {"url": image}
    og_w, og_h = m.get("og:image:width", ""), m.get("og:image:height", "")
    return {
        "title": html.unescape(p.title.strip()),
        "description": m.get("description", ""),
        "canonical": p.canonical,
        "robots": m.get("robots", ""),
        "og_title": m.get("og:title", ""),
        "og_description": m.get("og:description", ""),
        "og_type": m.get("og:type", "article"),
        "og_url": m.get("og:url", ""),
        "og_image": {"url": m.get("og:image", ""), "width": int(og_w) if og_w.isdigit() else None,
                     "height": int(og_h) if og_h.isdigit() else None},
        "published": m.get("article:published_time", ""),
        "modified": m.get("article:modified_time", ""),
        "headline": html.unescape(posting.get("headline", "")),
        "author": author_name,
        "ld_image": image.get("url", ""),
    }


def local_date(iso: str) -> str:
    """'2022-04-23T01:08:59+00:00' -> '2022-04-22' (the site's own timezone)."""
    return datetime.fromisoformat(iso).astimezone(SITE_TZ).date().isoformat()


# ── Fetching + images ─────────────────────────────────────────


def fetch(url: str, dest: Path, *, refresh: bool = False) -> Path:
    if dest.exists() and not refresh:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    q = urllib.parse.quote(url, safe=":/%?&=#")
    req = urllib.request.Request(q, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        dest.write_bytes(r.read())
    return dest


def fetch_comments(post_id: int, cache: Path) -> list[dict]:
    """Approved comments (the public REST endpoint only returns approved ones)."""
    dest = cache / "comments" / f"{post_id}.json"
    fetch(f"{SITE}/wp-json/wp/v2/comments?post={post_id}&per_page=100&orderby=date&order=asc", dest)
    out = []
    for c in json.loads(dest.read_text()):
        out.append({"id": c["id"], "parent": c.get("parent", 0), "author": c.get("author_name", ""),
                    "date": c.get("date", ""), "content_html": c.get("content", {}).get("rendered", "")})
    return out


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _webp(im, w: int, dest: Path) -> dict:
    from PIL import Image
    h = round(im.height * w / im.width)
    out = im if w == im.width else im.resize((w, h), Image.LANCZOS)
    out.save(dest, "WEBP", quality=WEBP_QUALITY, method=6)
    return {"file": dest.name, "width": w, "height": h, "bytes": dest.stat().st_size}


def still_renditions(src: Path, out_dir: Path, name: str, *, force: bool = False) -> dict:
    """x.webp (1x, <=1600w), x@2x.webp (only if the source has 2x pixels),
    x-m.webp + x-m@2x.webp (phone, 660w / 1320w; same framing: these are memes,
    and reframing would cut their captions)."""
    from PIL import Image
    out_dir.mkdir(parents=True, exist_ok=True)
    im = Image.open(src)
    im.seek(0)
    im = im.convert("RGBA") if im.mode in ("P", "LA", "RGBA") else im.convert("RGB")
    if im.mode == "RGBA" and im.getextrema()[3][0] == 255:
        im = im.convert("RGB")
    w = im.width
    files = {}
    one = min(ONE_X, w)
    plan = {"1x": (one, f"{name}.webp"), "phone": (min(PHONE_W, w), f"{name}-m.webp")}
    if w >= 2 * one and one == ONE_X:
        plan["2x"] = (min(2 * ONE_X, w), f"{name}@2x.webp")
    if w >= 2 * PHONE_W:
        plan["phone2x"] = (2 * PHONE_W, f"{name}-m@2x.webp")
    for key, (tw, fn) in plan.items():
        dest = out_dir / fn
        if dest.exists() and not force:
            from PIL import Image as _I
            with _I.open(dest) as d:
                files[key] = {"file": fn, "width": d.width, "height": d.height, "bytes": dest.stat().st_size}
            continue
        files[key] = _webp(im, tw, dest)
    return files


def gif_renditions(src: Path, out_dir: Path, name: str, *, force: bool = False) -> dict:
    """GIF -> muted MP4 (H.264) + WebM (VP9), a WebP poster (the frame 90% of the
    way through, usually the payoff) and still renditions of that frame for no-JS/reduced motion."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required for GIFs")
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height,nb_read_frames", "-of", "json", str(src)],
                           check=True, capture_output=True, text=True)
    info = json.loads(probe.stdout)["streams"][0]
    frames = int(info.get("nb_read_frames") or 1)
    w = int(info["width"])
    tw = min(GIF_MAX_W, w) // 2 * 2
    scale = f"scale={tw}:-2:flags=lanczos"
    mp4, webm = out_dir / f"{name}.mp4", out_dir / f"{name}.webm"
    if force or not mp4.exists():
        _run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", scale, "-an", "-c:v", "libx264",
              "-pix_fmt", "yuv420p", "-crf", "26", "-preset", "slow", "-movflags", "+faststart", str(mp4)])
    if force or not webm.exists():
        _run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", scale, "-an", "-c:v", "libvpx-vp9",
              "-b:v", "0", "-crf", "38", "-row-mt", "1", str(webm)])
    frame = out_dir.parent / f".{name}-frame.png"
    pick = int(0.9 * (frames - 1))
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", f"select=eq(n\\,{pick})", "-frames:v", "1",
          "-fps_mode", "passthrough", str(frame)])
    stills = still_renditions(frame, out_dir, name, force=force)
    frame.unlink()
    files = dict(stills)
    files["mp4"] = {"file": mp4.name, "bytes": mp4.stat().st_size}
    files["webm"] = {"file": webm.name, "bytes": webm.stat().st_size}
    return files


# ── Scaffold ─────────────────────────────────────────────────


def module_name(slug: str) -> str:
    m = re.sub(r"[^a-z0-9]+", "_", slug.lower()).strip("_")
    return m if not m[0].isdigit() else f"post_{m}"


SCAFFOLD = '''"""Imported WordPress post: {url}

Generated by scripts/wp_post_import.py {post_id}; the body ({slug}.body.html) and
metadata ({slug}.json) are regenerated by the converter, this file is not.
Hand-edit ALT (one entry per image, written from what the image shows),
IN_SHORT (drafts restate the post's own words) and any infographics.

Regenerate: python3 wordpress/post_sources/{module}.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from editorial_shell import Claim  # noqa: E402,F401
import wp_post  # noqa: E402

SLUG = "{slug}"
SOURCE = wp_post.load(SLUG)
OUTPUT_PATH = wp_post.output_path(SLUG)

ALT = {{
{alts}
}}

IN_SHORT: tuple = ()


def render() -> str:
    return wp_post.render_post(SOURCE, alt=ALT, in_short=IN_SHORT)


def main() -> None:
    wp_post.write(OUTPUT_PATH, render())


if __name__ == "__main__":
    main()
'''


# ── CLI ──────────────────────────────────────────────────────


def section_of(body: str, marker: str) -> str:
    """The text of the last h2 before a marker ("Intro" if none)."""
    i = body.find(marker)
    hs = re.findall(r"<h2>(.*?)</h2>", body[:i], re.S) if i >= 0 else []
    return html.unescape(re.sub(r"<[^>]+>", "", hs[-1])) if hs else "Intro"


def import_post(record: dict, snapshot_html: str, live_html: str, *, comments: list[dict] | None = None,
                asides: tuple[str, ...] = ()) -> tuple[Converted, dict]:
    """Pure conversion (no network, no files): returns the body and the JSON data."""
    images = {_nfc(i["full_url"]): i for i in record.get("images", [])}
    images.update({_nfc(original_upload_url(i["url"])): i for i in record.get("images", [])})
    conv = ElementorConverter(images, asides=asides).convert(snapshot_html)
    live = extract_live_meta(live_html)
    for f in conv.figures:
        f.section = section_of(conv.body_html, f"<!--GG:FIGURE {f.name}-->")
        if f.name in {n for ns in conv.galleries.values() for n in ns}:
            g = next(k for k, ns in conv.galleries.items() if f.name in ns)
            f.section = section_of(conv.body_html, f"<!--GG:GALLERY {g}-->")
    feat = record.get("featured_image") or {}
    featured = None
    if feat.get("url"):
        inline = next((f for f in conv.figures if _nfc(f.url) == _nfc(feat["url"])), None)
        featured = {"name": inline.name if inline else name_from_url(feat["url"]), "url": feat["url"],
                    "width": feat.get("width"), "height": feat.get("height"), "also_inline": bool(inline),
                    "kind": "gif" if feat["url"].lower().endswith(".gif") else "still"}
    data = {
        "id": record["id"],
        "slug": record["slug"],
        "source_url": record["url"],
        "categories": record.get("categories", []),
        "series": record.get("series", ""),
        "live": live,
        "heading_map": conv.heading_map,
        "featured": featured,
        "figures": [f.to_json() for f in conv.figures],
        "galleries": conv.galleries,
        "comments": comments or [],
    }
    return conv, data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("post_id", type=int)
    ap.add_argument("--inventory", type=Path, default=DEFAULT_SPECS / "inventory.json")
    ap.add_argument("--snapshots", type=Path, default=DEFAULT_SPECS / "snapshots")
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--manifest-dir", type=Path, default=None,
                    help="write <dir>/<slug>/images.json (default: <specs>/pilot)")
    ap.add_argument("--aside", action="append", default=[],
                    help="heading text that, with the text widget after it, becomes a sidebar aside")
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--force-images", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="re-download the live page")
    args = ap.parse_args(argv)

    record = next((r for r in json.loads(args.inventory.read_text()) if r["id"] == args.post_id), None)
    if not record:
        print(f"post {args.post_id} not in {args.inventory}", file=sys.stderr)
        return 1
    slug = record["slug"]
    snapshot = (args.snapshots / f"{args.post_id}.html").read_text(encoding="utf-8")
    live_html = fetch(record["url"], args.cache / "live" / f"{slug}.html", refresh=args.refresh).read_text(encoding="utf-8")
    comments = fetch_comments(args.post_id, args.cache) if record.get("comment_count") else []
    conv, data = import_post(record, snapshot, live_html, comments=comments, asides=tuple(args.aside))
    data["import"] = {"asides": list(args.aside)}

    live = data["live"]
    want = f"{SITE}/{slug}/"
    if live["canonical"] != want:
        print(f"WARNING: live canonical {live['canonical']!r} is not {want!r}; the page will use {want!r}",
              file=sys.stderr)

    out_img = POSTS_OUT / slug / "img"
    if not args.no_images:
        todo = [(f["name"], f["url"], f["kind"]) for f in data["figures"]]
        if data["featured"] and not data["featured"]["also_inline"]:
            todo.append((data["featured"]["name"], data["featured"]["url"], data["featured"]["kind"]))
        renditions = {}
        seen: dict[str, str] = {}  # sha1 of the original -> figure name
        for name, url, kind in todo:
            src = fetch(url, args.cache / "img" / slug / urllib.parse.unquote(url.rsplit("/", 1)[-1]))
            digest = hashlib.sha1(src.read_bytes()).hexdigest()
            feat = data["featured"]
            if feat and name == feat["name"] and not feat["also_inline"] and digest in seen:
                # The featured image is a byte-identical copy of an inline image: no hero.
                feat.update(also_inline=True, name=seen[digest])
                continue
            seen.setdefault(digest, name)
            renditions[name] = (gif_renditions if kind == "gif" else still_renditions)(
                src, out_img, name, force=args.force_images)
            renditions[name]["source_bytes"] = src.stat().st_size
        data["renditions"] = renditions
    else:
        old = POST_SOURCES / f"{slug}.json"
        if old.exists():
            prev = json.loads(old.read_text())
            data["renditions"] = prev.get("renditions", {})
            if data["featured"] and (prev.get("featured") or {}).get("url") == data["featured"]["url"]:
                data["featured"] = prev["featured"]  # keeps the byte-identical-copy decision

    POST_SOURCES.mkdir(parents=True, exist_ok=True)
    (POST_SOURCES / f"{slug}.body.html").write_text(conv.body_html, encoding="utf-8")
    (POST_SOURCES / f"{slug}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    mod = POST_SOURCES / f"{module_name(slug)}.py"
    if not mod.exists():
        names = [f["name"] for f in data["figures"]]
        if data["featured"] and not data["featured"]["also_inline"]:
            names.append(data["featured"]["name"])
        alts = "\n".join(f'    "{n}": "",' for n in names)
        mod.write_text(SCAFFOLD.format(url=record["url"], post_id=args.post_id, slug=slug,
                                       module=mod.stem, alts=alts), encoding="utf-8")
        print(f"scaffolded {mod.relative_to(ROOT)}: write ALT + IN_SHORT, then run it")

    manifest_dir = args.manifest_dir or (args.inventory.parent / "pilot")
    write_manifest(manifest_dir / slug / "images.json", data, record)
    print(f"wrote {POST_SOURCES.relative_to(ROOT)}/{slug}.body.html (+ .json); "
          f"{len(data['figures'])} figures, headings {conv.heading_map}")
    return 0


MANIFEST_KEEP = ("what", "recommendation", "reclassified_as", "notes", "alt")


def write_manifest(path: Path, data: dict, record: dict) -> None:
    """Per-image facts from the import, merged with the hand-written fields
    (what / recommendation / notes) of an existing manifest."""
    old = {}
    opportunities = []
    if path.exists():
        prev = json.loads(path.read_text())
        old = {i["name"]: i for i in prev.get("images", [])}
        opportunities = prev.get("infographic_opportunities", [])
    rows = []
    entries = list(data["figures"])
    if data["featured"] and not data["featured"]["also_inline"]:
        entries.append({**data["featured"], "section": "Hero (featured image)", "inventory_class": "",
                        "inventory_alt": ""})
    for f in entries:
        r = {"name": f["name"], "source_url": f["url"], "kind": f["kind"], "section": f["section"],
             "inventory_class": f.get("inventory_class", ""), "inventory_alt": f.get("inventory_alt", ""),
             "width": f.get("width"), "height": f.get("height"),
             "renditions": data.get("renditions", {}).get(f["name"], {})}
        for k in MANIFEST_KEEP:
            if k in old.get(f["name"], {}):
                r[k] = old[f["name"]][k]
        rows.append(r)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"post_id": data["id"], "slug": data["slug"], "url": data["source_url"],
                                "images": rows, "infographic_opportunities": opportunities},
                               indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
