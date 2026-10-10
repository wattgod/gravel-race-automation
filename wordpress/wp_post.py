"""Render an imported WordPress post (scripts/wp_post_import.py) on the editorial shell.

A post lives at its ORIGINAL root URL: gravelgodcycling.com/<slug>/, built to
wordpress/posts/<slug>/index.html (+ img/) and deployed to public_html/<slug>/.
The slug never changes. See docs/article-cadence.md "Imported WordPress posts".

Per post, wordpress/post_sources/ holds:
  <slug>.body.html  converter output: shell sections, word-for-word text, figure markers
  <slug>.json       converter output: live metadata, figures, renditions, comments
  <module>.py       hand-written: ALT, IN_SHORT, infographics; calls render_post()

What this module adds on top of the shell (all opt-in by content, so a post
without pull quotes / galleries / videos / comments gets none of the CSS/JS):
  - images: EssayFigure per <!--GG:FIGURE name--> marker, WebP 1x/@2x + phone;
    GIFs as PlayOnceVideo (muted MP4, + a WebM only when smaller, smallest
    first; plays once when half visible, replay button, the still under
    reduced motion or without JS)
  - <!--GG:GALLERY name--> -> a figure grid
  - pull quotes (converted Click-to-Tweet), the click-to-load YouTube embed
  - comments: approved comments as a static, read-only archive (no form)
  - short posts: Contents only with MIN_CONTENTS_SECTIONS (3)+ sections, and
    at most SHORT_POST_MAX_CLAIMS (2) "In short" claims under SHORT_POST_WORDS (800)
  - `replace={name: SvgFigure|DataTable}`: an infographic takes an image's place;
    the original image stays one click away in a <details> under the figure
  - og:image: the featured image's 1200x630 JPEG crop (<featured>-og.jpg, <=200 KB,
    written by the converter) from the post's own img/ dir; the live (generic)
    og:image only when the post has no featured image. See og_image().
  - `description=`: replaces the live meta/og/JSON-LD description, only when the
    live one is wrong (e.g. Double Day 3 misread "Yield to tonnage")
  - `title=`: the same for the <title>, og:title and JSON-LD headline (the
    title without its " | Gravel God" suffix), only when the live title misstates
    the post (e.g. "Eight Years of Coaching Nate": Nate coached the author).
    Must keep the site's "... | Gravel God" pattern. The h1 and slug never change.
  - `corrections=`: a post's own figures corrected to match its own evidence
    (Matt, 2026-10-09). Each Correction is (exact old text, new text, reason);
    the old text must occur exactly once in the body. A corrected post gets
    CORRECTION_NOTE at the end of the body and CORRECTED_MODIFIED as its
    article:modified_time / dateModified. The word-for-word tests apply the
    same corrections to the snapshot (corrected_baseline), so any other drift
    still fails.
  - `restored=`: content the live post lost and an archived copy still has
    (e.g. Elementor tables whose columns now render empty; Matt, 2026-10-09:
    "1. try"). Each is a shell figure (DataTable) placed by `after=`, with the
    archived values verbatim and the provenance line in a footnote. A restored
    post gets RESTORED_MODIFIED as its modified date. The word-for-word tests
    skip the restored figures by id (restored_ids), so any other drift fails.
  - `dead_youtube=`: {video id: where it sat} for embeds YouTube no longer
    serves (404); the whole click-to-load figure is left out of the page. The
    module keeps the record so a video can be restored.

"In short" rule (Matt, 2026-10-09: "matter of fact in a claude voice"). Every
post module's IN_SHORT follows it; render_post raises on what can be linted
(in_short_problems), the rest is on the writer:
  - Plain, neutral, factual statements of what the post says or argues. Third
    person or impersonal ("The post argues that...", "The author..."). No
    imitation of the author's jokes or slang, no first person, no hype, no "!".
  - Each claim is supported by the post's text (no outside facts, no numbers
    the post doesn't state) and links to the section or figure that supports it.
  - At most IN_SHORT_MAX_WORDS (25) words per claim; 2-4 claims, at most
    SHORT_POST_MAX_CLAIMS (2) under SHORT_POST_WORDS (800) words.
  Example: "The post argues that a dopamine spike above baseline is followed by
  an equal dip below it."
"""
from __future__ import annotations

import dataclasses
import html
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Mapping, NamedTuple, Sequence
from zoneinfo import ZoneInfo

import editorial_shell as es
from editorial_shell import (
    ArticleMeta,
    Claim,
    EssayFigure,
    HeroImage,
    OgImage,
    PhoneCrop,
    Picture,
    PlayOnceVideo,
    render_editorial_page,
)

WORDPRESS = Path(__file__).resolve().parent
POST_SOURCES = WORDPRESS / "post_sources"
POSTS = WORDPRESS / "posts"
SITE = "https://gravelgodcycling.com"
SITE_TZ = ZoneInfo("America/Denver")
GALLERY_MARKER_RE = re.compile(r"<!--GG:GALLERY ([a-z0-9-]+)-->")

# Short-post front matter: a post's opening shouldn't outweigh the post.
# Fewer contents sections than this and the Contents list/bar is left out.
MIN_CONTENTS_SECTIONS = 3
# Under this many words, "In short" holds at most SHORT_POST_MAX_CLAIMS claims
# (keep the strongest); render_post raises otherwise.
SHORT_POST_WORDS = 800
SHORT_POST_MAX_CLAIMS = 2
# "In short" lint (see the module docstring for the full rule).
IN_SHORT_MIN_CLAIMS = 2
IN_SHORT_MAX_CLAIMS = 4
IN_SHORT_MAX_WORDS = 25
FIRST_PERSON_RE = re.compile(r"\b(?:I|me|my|mine|we|us|our|ours)\b", re.I)


# Figure corrections (Matt, 2026-10-09: "Yeah go ahead and fix").
CORRECTED_MODIFIED = "2026-10-09T00:00:00-06:00"
CORRECTION_NOTE = "Some figures in this post were corrected on October 9, 2026."


# Content restored from an archived copy of the post (Matt, 2026-10-09: "1. try").
RESTORED_MODIFIED = "2026-10-09T00:00:00-06:00"


def restored_ids(module) -> set[str]:
    """Ids of a post module's RESTORED figures: additions the word-for-word tests skip."""
    return {f.id for f in getattr(module, "RESTORED", ())}


class Correction(NamedTuple):
    """One factual fix to a post's own text: `old` occurs exactly once in the
    body and becomes `new`; `why` is the evidence (screenshot, arithmetic)."""
    old: str
    new: str
    why: str


def apply_corrections(body: str, corrections: Sequence[Correction]) -> str:
    for c in corrections:
        c = Correction(*c)
        if not c.why.strip() or c.old == c.new:
            raise ValueError(f"correction {c.old[:60]!r}: needs a reason and a change")
        n = body.count(c.old)
        if n != 1:
            raise ValueError(f"correction {c.old[:60]!r} found {n} times in the body, expected once")
        body = body.replace(c.old, c.new, 1)
    return body


def corrected_baseline(text: str, corrections: Sequence[Correction]) -> str:
    """The snapshot text with the same corrections applied, compared word for
    word (whitespace-normalized), so the corrections are the only allowed drift.
    Raises when an old text isn't in the snapshot exactly once."""
    out = " ".join(text.replace("\u200b", " ").split())
    for c in corrections:
        c = Correction(*c)
        old, new = " ".join(c.old.split()), " ".join(c.new.split())
        n = out.count(old)
        if n != 1:
            raise ValueError(f"correction {old[:60]!r} found {n} times in the snapshot, expected once")
        out = out.replace(old, new, 1)
    return out


YT_FIGURE_RE = r'<figure class="gg-yt"><a class="gg-yt-link" [^>]*data-yt="{vid}"[^>]*>.*?</figure>\n?'


def drop_youtube(body: str, dead: Mapping[str, str]) -> str:
    """Leave out each dead click-to-load YouTube figure (exactly one per id)."""
    for vid in dead:
        pat = re.compile(YT_FIGURE_RE.format(vid=re.escape(vid)), re.S)
        n = len(pat.findall(body))
        if n != 1:
            raise ValueError(f"dead_youtube: {vid} found {n} times, expected once")
        body = pat.sub("", body, count=1)
    return body


@dataclass(frozen=True)
class PostSource:
    slug: str
    data: dict
    body: str

    @property
    def url(self) -> str:
        return f"{SITE}/{self.slug}/"


def load(slug: str) -> PostSource:
    data = json.loads((POST_SOURCES / f"{slug}.json").read_text(encoding="utf-8"))
    body = (POST_SOURCES / f"{slug}.body.html").read_text(encoding="utf-8")
    return PostSource(slug, data, body)


def output_path(slug: str) -> Path:
    return POSTS / slug / "index.html"


def write(path: Path, page: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    print(f"wrote {path.relative_to(WORDPRESS.parent)}")


def _local_date(iso: str) -> date:
    return datetime.fromisoformat(iso).astimezone(SITE_TZ).date()


def in_short_problems(claims: Sequence[Claim], words: int) -> list[str]:
    """What breaks the "In short" rule's lintable half (empty list = fine).
    `words` is the post's word count (es.word_count of the body)."""
    out = []
    n = len(claims)
    if words < SHORT_POST_WORDS and n > SHORT_POST_MAX_CLAIMS:
        out.append(f"a {words}-word post gets at most {SHORT_POST_MAX_CLAIMS} claims "
                   f"(under {SHORT_POST_WORDS} words), not {n}; keep the strongest")
    elif not IN_SHORT_MIN_CLAIMS <= n <= IN_SHORT_MAX_CLAIMS:
        out.append(f"{n} claims; write {IN_SHORT_MIN_CLAIMS}-{IN_SHORT_MAX_CLAIMS}")
    for c in claims:
        text = html.unescape(re.sub(r"<[^>]+>", "", c.text_html))
        head = text[:40] + ("..." if len(text) > 40 else "")
        if len(text.split()) > IN_SHORT_MAX_WORDS:
            out.append(f"{head!r}: {len(text.split())} words (max {IN_SHORT_MAX_WORDS})")
        if "!" in text:
            out.append(f"{head!r}: no '!'")
        fp = sorted({m.group(0) for m in FIRST_PERSON_RE.finditer(text)})
        if fp:
            out.append(f"{head!r}: first person {fp}; write it in the third person")
        if not c.href.startswith("#"):
            out.append(f"{head!r}: href {c.href!r} must link to a section or figure on the page")
    return out


# ── Pictures ─────────────────────────────────────────────────


def picture(src: PostSource, name: str, alt: str) -> Picture:
    r = src.data["renditions"][name]
    one, two = r["1x"], r.get("2x")
    phone = None
    if "phone" in r:
        p, p2 = r["phone"], r.get("phone2x")
        phone = PhoneCrop(f"img/{p['file']}", p["width"], p["height"], f"img/{p2['file']}" if p2 else "")
    return Picture(src=f"img/{one['file']}", alt=alt, width=one["width"], height=one["height"],
                   src_2x=f"img/{two['file']}" if two else "", phone=phone)


VIDEO_MIME = {"mp4": "video/mp4", "webm": "video/webm"}


def video_sources(r: Mapping) -> tuple[tuple[str, str], ...]:
    """A GIF's video <source>s, smallest file first: browsers play the first
    source they can, so listing a heavier WebM ahead of the MP4 made readers
    download the heavier one. The converter keeps a WebM only when it is
    smaller; the sort still holds if a committed one is not."""
    kinds = sorted((k for k in VIDEO_MIME if k in r), key=lambda k: (r[k]["bytes"], k != "mp4"))
    return tuple((f"img/{r[k]['file']}", VIDEO_MIME[k]) for k in kinds)


def _figure_for(src: PostSource, spec: dict, alt: str) -> EssayFigure:
    pic = picture(src, spec["name"], alt)
    wide = pic.width >= 1.2 * pic.height
    video = None
    if spec["kind"] == "gif":
        r = src.data["renditions"][spec["name"]]
        video = PlayOnceVideo(
            sources=video_sources(r),
            poster=pic.src, width=pic.width, height=pic.height)
    cap = spec.get("caption_html", "")
    return EssayFigure(pic, video=video, caption_html=cap, width="column" if wide else "inline",
                       id=f"fig-{spec['name']}", marker=spec["name"])


def _original_details(src: PostSource, name: str, alt: str, label: str) -> str:
    pic = es.render_picture(picture(src, name, alt))
    return (f'<details class="gg-original" data-gg-added><summary>{es.esc(label)}</summary>'
            f'<div class="gg-media">{pic}</div></details>')


def render_gallery(src: PostSource, names: Sequence[str], alt: Mapping[str, str]) -> str:
    cols = 2 if len(names) in (2, 4) else 3
    items = "".join(f'<div class="gg-gallery-item">{es.render_picture(picture(src, n, alt[n]))}</div>'
                    for n in names)
    return f'<figure class="gg-gallery" style="--cols:{cols}">{items}</figure>'


# ── HTML infographics ────────────────────────────────────────


@dataclass(frozen=True)
class HtmlFigure:
    """An infographic built from trusted HTML (CSS bars, small inline SVGs in a
    grid) so its labels stay legible from 360 to 680 px, where one scaled SVG
    would not. Same frame as the shell's figures: kicker, h5 title, caption.
    Put data-draw-in on `html`'s root or let draw_in=True add it to the figure.
    Placed by wp_post (marker or after=), before the shell sees the body."""

    id: str
    html: str
    kicker: str = ""
    title: str = ""
    caption_html: str = ""
    draw_in: bool = True
    marker: str = ""
    after: str = ""


def render_html_figure(fig: HtmlFigure) -> str:
    fid = es.esc(fig.id)
    kick = f'\n  <p class="kick">{es.esc(fig.kicker)}</p>' if fig.kicker else ""
    title = f'\n  <h5 id="{fid}-h">{es.esc(fig.title)}</h5>' if fig.title else ""
    label = f' aria-labelledby="{fid}-h"' if fig.title else ""
    cap = f"\n  <figcaption>{fig.caption_html}</figcaption>" if fig.caption_html else ""
    draw = " data-draw-in" if fig.draw_in else ""
    return (f'<figure class="gg-fig gg-htmlfig" id="{fid}"{label}{draw} data-gg-added>{kick}{title}\n'
            f"  {fig.html}{cap}\n</figure>")


def _place_html_figure(body: str, fig: HtmlFigure) -> str:
    block = render_html_figure(fig)
    if bool(fig.marker) == bool(fig.after):
        raise ValueError("HtmlFigure needs exactly one of marker= or after=")
    if fig.marker:
        tag = f"<!--GG:FIGURE {fig.marker}-->"
        if body.count(tag) != 1:
            raise ValueError(f"marker {tag} found {body.count(tag)} times")
        return body.replace(tag, block, 1)
    if body.count(fig.after) != 1:
        raise ValueError(f"after={fig.after[:60]!r} found {body.count(fig.after)} times, expected once")
    end = es._enclosing_block_end(body, body.index(fig.after) + len(fig.after))
    if end is None:
        raise ValueError(f"after={fig.after[:60]!r} is not inside a block")
    return body[:end] + "\n" + block + body[end:]


# ── Comments (read-only archive) ─────────────────────────────


def _comment_paragraphs(content_html: str) -> list[str]:
    text = re.sub(r"<br\s*/?>", "\n", content_html)
    paras = re.split(r"</p>\s*|\n\s*\n", text)
    out = []
    for p in paras:
        plain = html.unescape(re.sub(r"<[^>]+>", "", p)).strip()
        if plain:
            out.append(es.esc(plain).replace("\n", "<br>"))
    return out


def render_comments(comments: Sequence[Mapping]) -> str:
    """Approved comments as a static archive: display name, date, text (all
    escaped; commenter links and emails are never rendered), replies nested,
    no form."""
    if not comments:
        return ""
    by_parent: dict[int, list[Mapping]] = {}
    ids = {c["id"] for c in comments}
    for c in sorted(comments, key=lambda c: c["date"]):
        parent = c.get("parent") or 0
        by_parent.setdefault(parent if parent in ids else 0, []).append(c)

    def items(parent: int) -> str:
        out = []
        for c in by_parent.get(parent, []):
            d = datetime.fromisoformat(c["date"]).date()
            body = "".join(f"<p>{p}</p>" for p in _comment_paragraphs(c["content_html"]))
            kids = items(c["id"])
            kids = f'<ol class="gg-comment-list">{kids}</ol>' if kids else ""
            out.append(
                f'<li class="gg-comment" id="comment-{int(c["id"])}"><p class="gg-comment-meta">'
                f'<strong>{es.esc(c["author"] or "Anonymous")}</strong> &middot; '
                f'<time datetime="{d.isoformat()}">{d:%B} {d.day}, {d.year}</time></p>'
                f'<div class="gg-comment-body">{body}</div>{kids}</li>'
            )
        return "".join(out)

    n = len(comments)
    return (
        f'<section class="gg-comments" id="comments" data-gg-archive aria-labelledby="comments-h">\n'
        f'<h2 id="comments-h" data-no-toc>Comments</h2>\n'
        f'<p class="gg-comments-note">{n} comment{"s" if n != 1 else ""} from the original post. '
        f"Comments are closed.</p>\n"
        f'<ol class="gg-comment-list">{items(0)}</ol>\n</section>'
    )


# ── Page ─────────────────────────────────────────────────────


def og_image(src: PostSource) -> OgImage | None:
    """The featured image's og:image crop (converter: wp_post_import.ensure_og),
    as an absolute URL in the post's own img/ dir; the live og:image (the generic
    logo) only when the post has no featured image or no crop yet."""
    feat = src.data.get("featured")
    og = src.data.get("renditions", {}).get(feat["name"], {}).get("og") if feat else None
    if og:
        return OgImage(f"{src.url}img/{og['file']}", og["width"], og["height"])
    live = src.data["live"].get("og_image") or {}
    return OgImage(live["url"], live.get("width"), live.get("height")) if live.get("url") else None


def article_time_meta(src: PostSource, modified: str | None = None) -> str:
    """article:published_time / article:modified_time, as the live page's head
    has them (the live ISO timestamps, unchanged), except `modified` when the
    post was corrected."""
    live = {**src.data["live"], **({"modified": modified} if modified else {})}
    tags = [f'  <meta property="article:{k}_time" content="{es.esc(live[v])}">'
            for k, v in (("published", "published"), ("modified", "modified")) if live.get(v)]
    return "\n".join(tags)


TITLE_SUFFIX = " | Gravel God"


def _checked_title(title: str | None) -> str | None:
    if title is not None and (not title.endswith(TITLE_SUFFIX) or not title[: -len(TITLE_SUFFIX)].strip()):
        raise ValueError(f"title must look like '... | Gravel God', not {title!r}")
    return title


def article_ld(src: PostSource, description: str | None = None, title: str | None = None,
               modified: str | None = None) -> dict:
    live = src.data["live"]
    ld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": _checked_title(title)[: -len(TITLE_SUFFIX)] if title else live["headline"],
        "description": description or live["description"],
        "datePublished": live["published"],
        "dateModified": modified or live["modified"],
        "author": {"@type": "Person", "name": live.get("author") or "Matti Rowe", "url": SITE},
        "publisher": {"@type": "Organization", "name": "Gravel God", "url": SITE},
        "mainEntityOfPage": src.url,
    }
    if live.get("ld_image"):
        ld["image"] = live["ld_image"]
    return ld


def build_meta(src: PostSource, *, hero: HeroImage | None, kicker: str | None = None, dek: str = "",
               description: str | None = None, title: str | None = None,
               modified: str | None = None) -> ArticleMeta:
    """`description` replaces the live description (meta, og, JSON-LD) when set;
    `title` the live title (<title>, og:title, JSON-LD headline)."""
    live = src.data["live"]
    title = _checked_title(title)
    robots = "index, follow" + (", max-image-preview:large" if "max-image-preview:large" in live.get("robots", "") else "")
    return ArticleMeta(
        slug=src.slug,
        canonical_url=src.url,
        title=title or live["title"],
        description=description or live["description"],
        og_title=title or live.get("og_title") or None,
        og_description=description or live.get("og_description") or None,
        og_image=og_image(src),
        headline=live["headline"],
        date_published=_local_date(live["published"]),
        kicker=kicker if kicker is not None else " · ".join(src.data.get("categories", [])),
        dek=dek,
        byline=live.get("author") or "Gravel God",
        robots=robots,
        hero=hero,
        json_ld=(article_ld(src, description, title, modified),),
    )


def render_post(
    src: PostSource,
    *,
    alt: Mapping[str, str],
    in_short: Sequence[Claim] = (),
    figures: Sequence = (),
    replace: Mapping[str, object] | None = None,
    replace_label: str = "Show the original image",
    after_image: Mapping[str, str] | None = None,
    kicker: str | None = None,
    extra_css: str = "",
    extra_body_end: str = "",
    in_short_on_phone: es.InShortOnPhone = "first",
    description: str | None = None,
    title: str | None = None,
    corrections: Sequence[Correction] = (),
    dead_youtube: Mapping[str, str] | None = None,
    restored: Sequence = (),
) -> str:
    """The full page. `alt` must cover every image (raises otherwise).
    `figures`: extra shell figures (SvgFigure / DataTable / EssayFigure) placed by
    `after=` or by a marker that `after_image` ({marker: image name}) puts right
    after that image. `replace`: {image name: figure}: the figure takes the
    image's place and the image moves into a <details> under it.
    `in_short` must pass in_short_problems (the "In short" rule; empty = none).
    `description`: a corrected meta description (default: the live one).
    `title`: a corrected "... | Gravel God" title (default: the live one).
    `corrections`: Correction(old, new, why) fixes to the post's own figures;
    adds CORRECTION_NOTE and bumps the modified date. `dead_youtube`: {id:
    where it sat} embeds to leave out. `restored`: figures restored from an
    archived copy (placed by after=); bumps the modified date (see the module
    docstring)."""
    data = src.data
    replace = dict(replace or {})
    after_image = dict(after_image or {})
    names = [f["name"] for f in data["figures"]]
    feat = data.get("featured")
    if feat and not feat["also_inline"]:
        names.append(feat["name"])
    missing = [n for n in names if not (alt.get(n) or "").strip()]
    unknown = sorted(set(alt) - set(names))
    if missing or unknown:
        raise ValueError(f"alt text: missing {missing}, unknown {unknown}")
    if in_short:
        problems = in_short_problems(in_short, es.word_count(src.body))
        if problems:
            raise ValueError("in_short: " + "; ".join(problems))

    body = apply_corrections(src.body, corrections)
    if dead_youtube:
        body = drop_youtube(body, dead_youtube)
    if corrections:
        body = body.rstrip() + f'\n<p class="gg-corrected" data-gg-added>{es.esc(CORRECTION_NOTE)}</p>\n'
    for marker, image in after_image.items():
        tag = f"<!--GG:FIGURE {image}-->"
        if body.count(tag) != 1:
            raise ValueError(f"after_image: {tag} found {body.count(tag)} times")
        body = body.replace(tag, f"{tag}\n<!--GG:FIGURE {marker}-->", 1)

    gallery_images = {n for ns in data.get("galleries", {}).values() for n in ns}

    def _gallery(m: re.Match) -> str:
        return render_gallery(src, data["galleries"][m.group(1)], alt)
    body = GALLERY_MARKER_RE.sub(_gallery, body)

    shell_figures: list = []
    html_figures: list[HtmlFigure] = [f for f in figures if isinstance(f, HtmlFigure)]
    for spec in data["figures"]:
        if spec["name"] in gallery_images:
            continue
        if spec["name"] in replace:
            fig = replace.pop(spec["name"])
            details = _original_details(src, spec["name"], alt[spec["name"]], replace_label)
            cap = getattr(fig, "caption_html", "")
            if isinstance(fig, HtmlFigure):
                html_figures.append(dataclasses.replace(fig, marker=spec["name"], after="", caption_html=cap + details))
                continue
            if hasattr(fig, "caption_html"):
                fig = dataclasses.replace(fig, marker=spec["name"], after="", caption_html=cap + details)
            else:  # DataTable: the original goes in its footnote
                fig = dataclasses.replace(fig, marker=spec["name"], after="",
                                          footnote_html=fig.footnote_html + details)
            shell_figures.append(fig)
        else:
            shell_figures.append(_figure_for(src, spec, alt[spec["name"]]))
    if replace:
        raise ValueError(f"replace: no image named {sorted(replace)}")
    shell_figures += [f for f in figures if not isinstance(f, HtmlFigure)]
    ids = [f.id for f in restored]
    if len(set(ids)) != len(ids) or any(not f.after for f in restored):
        raise ValueError(f"restored: figures need distinct ids and after= ({ids})")
    shell_figures += list(restored)
    for hf in html_figures:
        body = _place_html_figure(body, hf)

    hero = None
    if feat and not feat["also_inline"]:  # an inline copy would show the same image twice
        hero = HeroImage.from_picture(picture(src, feat["name"], alt[feat["name"]]), layout="wide")

    comments = render_comments(data.get("comments", []))
    if comments:
        body = body.rstrip() + "\n" + comments + "\n"

    css = []
    js = []
    if 'class="gg-pullquote"' in body:
        css.append(PULLQUOTE_CSS)
    if "gg-gallery" in body:
        css.append(GALLERY_CSS)
    if 'class="gg-yt"' in body:
        css.append(YOUTUBE_CSS)
        js.append(YOUTUBE_JS)
    if comments:
        css.append(COMMENTS_CSS)
    if "gg-sidebar" in body:
        css.append(SIDEBAR_CSS)
    if "gg-original" in body or any("gg-original" in (getattr(f, "caption_html", "") + getattr(f, "footnote_html", ""))
                                    for f in shell_figures):
        css.append(ORIGINAL_CSS)
    if html_figures:
        css.append(HTMLFIG_CSS)
    if 'class="gg-slide"' in body:
        css.append(SLIDES_CSS)
    if 'class="gg-price-table"' in body:
        css.append(PRICE_TABLE_CSS)
    if "gg-cta" in body:
        css.append(CTA_CSS)
    if 'class="gg-corrected"' in body:
        css.append(CORRECTED_CSS)
    if not hero and not shell_figures and "gg-gallery" in body:
        css.insert(0, es.ESSAY_CSS)  # the shell adds it only with figures or a hero picture

    modified = CORRECTED_MODIFIED if corrections else RESTORED_MODIFIED if restored else None
    meta = build_meta(src, hero=hero, kicker=kicker, description=description, title=title, modified=modified)
    sections = len(es.add_heading_ids(body)[1])
    return render_editorial_page(
        meta,
        body,
        in_short=in_short or None,
        in_short_on_phone=in_short_on_phone,
        ladder=True,
        contents=sections >= MIN_CONTENTS_SECTIONS,
        figures=shell_figures,
        extra_css="\n".join(css + ([extra_css] if extra_css else [])),
        extra_head=article_time_meta(src, modified),
        extra_body_end="\n".join(js + ([extra_body_end] if extra_body_end else [])),
    )


# ── CSS / JS ─────────────────────────────────────────────────

PULLQUOTE_CSS = """
/* pull quote (was an Elementor Click-to-Tweet) */
/* Inset from the column on both sides so the italic overhang and the opening
   quote mark sit inside the figure, never flush with the viewport edge on a
   phone; no hanging punctuation (it would push the mark outside the box). */
.article .gg-pullquote{margin:44px 0 40px;padding:0 20px}
.article .gg-pullquote blockquote{margin:0;padding:0;box-shadow:none;font:italic 600 32px/1.22 var(--serif);
  letter-spacing:-.01em;color:var(--ink);text-wrap:balance;hanging-punctuation:none;text-indent:0;
  overflow-wrap:break-word}
.article .gg-pullquote blockquote p{margin:0;font:inherit}
.article .gg-pullquote figcaption{margin-top:14px;font:400 14px/1.5 var(--mono);color:var(--ink3)}
.article .gg-pullquote figcaption::before{content:"\\2014\\00a0"}
@media (max-width:640px){.article .gg-pullquote{padding:0 18px}.article .gg-pullquote blockquote{font-size:26px}}
"""

GALLERY_CSS = """
/* figure grid (was an Elementor gallery) */
.gg-gallery{display:grid;grid-template-columns:repeat(var(--cols,3),minmax(0,1fr));gap:8px;margin:0 0 28px}
.gg-gallery-item img{display:block;width:100%;height:100%;aspect-ratio:1;object-fit:cover}
@media (max-width:640px){.gg-gallery{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""

YOUTUBE_CSS = """
/* click-to-load YouTube: thumbnail + play until clicked, then a youtube-nocookie iframe */
.gg-yt{margin:0 0 28px}
.gg-yt-link{position:relative;display:block;aspect-ratio:16/9;background:var(--hole);overflow:hidden}
.gg-yt-link img{display:block;width:100%;height:100%;object-fit:cover}
.gg-yt-play{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);padding:12px 22px;
  background:var(--ink);color:var(--paper);font:700 14px var(--mono);letter-spacing:.12em;text-transform:uppercase;
  clip-path:var(--chamfer)}
.gg-yt-link:hover .gg-yt-play,.gg-yt-link:focus-visible .gg-yt-play{background:var(--teal-ink)}
.gg-yt-frame{display:block;width:100%;height:auto;aspect-ratio:16/9;border:0}
"""

YOUTUBE_JS = """<script>
  // Click-to-load YouTube: no third-party request until the reader asks for the video.
  (function() {
    document.addEventListener('click', function(e) {
      var a = e.target.closest ? e.target.closest('a.gg-yt-link') : null;
      if (!a) return;
      e.preventDefault();
      var f = document.createElement('iframe');
      var start = parseInt(a.getAttribute('data-start'), 10) || 0;
      f.src = 'https://www.youtube-nocookie.com/embed/' + encodeURIComponent(a.getAttribute('data-yt')) +
        '?autoplay=1' + (start ? '&start=' + start : '');
      f.title = a.getAttribute('aria-label') || 'YouTube video';
      f.allow = 'accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture';
      f.allowFullscreen = true;
      f.className = 'gg-yt-frame';
      a.parentNode.replaceChild(f, a);
      f.focus();
    });
  })();
</script>"""

COMMENTS_CSS = """
/* comments: read-only archive */
.gg-comments{margin:72px 0 0}
.gg-comments h2{font-size:28px;margin:0 0 8px}
.gg-comments-note{font:400 14px/1.5 var(--mono);color:var(--ink3);margin:0 0 24px}
.gg-comment-list{list-style:none;margin:0;padding:0}
.gg-comment{padding:18px 0;border-top:1px solid var(--sand2)}
.gg-comment .gg-comment-list{margin:12px 0 0 20px}
.gg-comment-meta{font:400 14px/1.5 var(--mono);color:var(--ink3);margin:0 0 6px}
.gg-comment-meta strong{color:var(--ink)}
.gg-comment-body p{font-size:18px;margin:0 0 .6em}
"""

SIDEBAR_CSS = """
/* sidebar aside (an Elementor "Sidebar" heading + its text) */
.gg-sidebar h3{font:700 14px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--ink3);margin:0 0 10px}
"""

ORIGINAL_CSS = """
/* the original image under a redrawn infographic */
.gg-original{margin-top:12px}
.gg-original summary{font:400 14px/1.5 var(--mono);color:var(--teal-ink);cursor:pointer}
.gg-original .gg-media{margin-top:12px}
"""

SLIDES_CSS = """
/* slides (was an Elementor carousel): one figure per slide, in order */
.gg-slide{background:var(--sand);padding:18px 22px 14px;margin:0 0 12px}
.gg-slide p{margin:0 0 8px}
.gg-slide figcaption{font:400 14px/1.5 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--ink3)}
.gg-slide + :not(.gg-slide){margin-top:28px}
@media (max-width:640px){.gg-slide{padding:16px 16px 12px}}
"""

PRICE_TABLE_CSS = """
/* price table (was an Elementor price table): a plain definition list */
.gg-price-table{margin:0 0 28px;padding:20px 22px 10px;background:var(--sand);display:flex;flex-direction:column}
.gg-price-table dt{font:700 24px/1.2 var(--serif);color:var(--ink);margin:0 0 4px}
.gg-price-table dd{margin:0 0 10px}
.gg-price-table .gg-price{font:700 28px/1.2 var(--mono);color:var(--ink)}
.gg-price-table .gg-price-period{font-size:14px;font-weight:400;color:var(--ink3)}
.gg-price-table .gg-price-features ul{margin:0;padding-left:1.2em}
.gg-price-table .gg-price-ribbon{order:-1;font:400 14px/1.5 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--ink3)}
"""

CTA_CSS = """
/* call to action (was an Elementor CTA): the sand aside, title + text + plain link */
.gg-cta .gg-cta-title{font:700 24px/1.2 var(--serif);margin:0 0 10px}
.gg-cta .gg-cta-title strong{font-weight:inherit}
.gg-cta .gg-cta-ribbon{font:400 14px/1.5 var(--mono);color:var(--ink3)}
"""

CORRECTED_CSS = """
/* one neutral line at the end of a corrected post */
.article .gg-corrected{margin:40px 0 0;font:400 14px/1.5 var(--mono);color:var(--ink3)}
"""

HTMLFIG_CSS = """
/* HTML infographics (wp_post.HtmlFigure) */
.gg-htmlfig{margin:28px 0 30px;padding:22px 24px 18px}
.gg-htmlfig h5{font:700 24px/1.2 var(--serif);margin:0 0 14px;color:var(--ink)}
.gg-htmlfig .kick{margin-bottom:6px}
@media (max-width:640px){.gg-htmlfig{padding:18px 14px}.gg-htmlfig h5{font-size:21px}}
.gg-htmlfig svg{display:block;width:100%;height:auto;overflow:visible}
.gg-htmlfig svg [data-draw]{transform-box:fill-box}
.gg-htmlfig svg text{font-family:var(--mono)}
"""
