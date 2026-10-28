#!/usr/bin/env python3
"""Render complete published Substack articles on the existing editorial shell.

Input is a directory of published-post JSON snapshots with body_html. Source
text and images are preserved; Substack subscription/share controls are removed.
Never import a free-wall teaser as an article. Existing on-site versions win.

Usage: python scripts/import_substack_posts.py /absolute/path/to/snapshots
Then run wordpress/generate_articles_index.py. No network access at render time.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from PIL import Image, ImageOps, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'wordpress'))
from editorial_shell import ArticleMeta, OgImage, render_editorial_page
from article_offers import offer_for_slug, render_offer
from sync_substack_index import LOCAL_VERSIONS

SOURCES = ROOT / 'wordpress/substack_sources'
PAGES = ROOT / 'wordpress/articles'
SITE = 'https://gravelgodcycling.com'
ALLOWED = set('p a h2 h3 h4 em strong b i u s br hr blockquote ul ol li figure figcaption img table thead tbody tr td th sup sub code pre'.split())
CSS = '''
.gg-blog-section img{display:block;max-width:100%;height:auto;margin:24px auto}
.gg-blog-section figure{margin:32px 0}
.gg-blog-section figcaption{font:13px/1.5 var(--mono);color:var(--ink2);margin-top:10px}
.gg-blog-section table{display:block;max-width:100%;overflow:auto}
'''


def original_image(url):
    # Use the publisher's original, rather than copying an email-sized rendition.
    if 'substackcdn.com/image/fetch/' in url:
        suffix = url.split('/')[-1]
        decoded = unquote(suffix)
        if decoded.startswith('https://substack-post-media.s3.amazonaws.com/public/'):
            return decoded
    return url


def image_asset(item):
    url, directory, stem = item
    source = original_image(url)
    # Persist the exact source image once; subsequent runs reuse its renditions.
    digest = hashlib.sha256(source.encode()).hexdigest()[:16]
    destination = directory / f'{digest}.webp'
    if destination.exists():
        with Image.open(destination) as im:
            return url, destination.name, im.size
    request = Request(source, headers={'User-Agent': 'Mozilla/5.0 GravelGod archive import'})
    with urlopen(request, timeout=45) as response:
        data = response.read()
    try:
        decoded = Image.open(io.BytesIO(data))
    except UnidentifiedImageError:
        # HEIC originals are served as WebP by the publisher's own CDN.
        rendition = url.replace('f_auto', 'f_webp')
        if rendition == source:
            raise
        with urlopen(Request(rendition, headers={'User-Agent': 'Mozilla/5.0'}), timeout=45) as response:
            data = response.read()
        decoded = Image.open(io.BytesIO(data))
    with decoded as im:
        im = ImageOps.exif_transpose(im)
        if getattr(im, 'is_animated', False):
            # Preserve animation instead of silently flattening the author's GIF.
            destination = directory / f'{digest}.gif'
            destination.write_bytes(data)
            return url, destination.name, im.size
        im.thumbnail((1600, 2400), Image.Resampling.LANCZOS)
        im.convert('RGB').save(destination, 'WEBP', quality=83)
        return url, destination.name, im.size


def clean_body(raw, slug, title):
    soup = BeautifulSoup(raw, 'html.parser')
    # Platform UI is not article copy. Remove whole widgets before unwrapping.
    for node in list(soup.select('form,button,script,style,svg,input,.subscription-widget-wrap,.subscribe-widget,.button-wrapper')):
        node.decompose()
    for node in list(soup.find_all(True)):
        if node.name is None:
            continue
        if node.name in {'source'}:
            node.decompose()
        elif node.name not in ALLOWED:
            node.unwrap()
    for node in soup.find_all(True):
        attrs = {"id": node["id"]} if node.get("id") else {}
        if node.name == 'a':
            href = node.get('href', '')
            # Never publish recipient-specific newsletter redirect/auth links.
            if 'substack.com/redirect/' in href or 'substack.com/action/' in href:
                node.unwrap()
                continue
            if href.startswith(('https://', 'http://', '/', '#', 'mailto:')):
                attrs['href'] = href
        if node.name == 'img':
            attrs = {k: node[k] for k in ('src', 'alt') if node.get(k)}
            attrs.setdefault('alt', '')
        node.attrs = attrs
    directory = PAGES / slug / 'img'
    directory.mkdir(parents=True, exist_ok=True)
    urls = sorted({im['src'] for im in soup.find_all('img') if im.get('src')})
    with ThreadPoolExecutor(max_workers=4) as pool:
        assets = dict((u, (name, size)) for u, name, size in pool.map(image_asset, [(u, directory, title) for u in urls]))
    for im in soup.find_all('img'):
        if not im.get('src'):
            im.decompose()
            continue
        name, (w, h) = assets[im['src']]
        im['src'] = f'img/{name}'
        im['width'], im['height'] = str(w), str(h)
        im['loading'], im['decoding'] = 'lazy', 'async'
    # Group at h2 boundaries so the shell supplies its established contents rail.
    parts = ['<section class="gg-blog-section">']
    for child in list(soup.contents):
        if getattr(child, 'name', None) == 'h2':
            parts.append('</section><section class="gg-blog-section">')
        parts.append(str(child))
    parts.append('</section>')
    return '\n'.join(parts)


def render(meta, body):
    url = f"{SITE}/articles/{meta['slug']}/"
    ld = {'@context': 'https://schema.org', '@type': 'Article',
          'headline': meta['title'], 'datePublished': meta['date'],
          'author': {'@type': 'Person', 'name': 'Matti Rowe'},
          'mainEntityOfPage': url, 'isBasedOn': meta['source_url']}
    article = ArticleMeta(
        slug=meta['slug'], canonical_url=url, title=meta['title'] + ' | Gravel God',
        headline=meta['title'], description=meta['subtitle'], dek=meta['subtitle'],
        date_published=date.fromisoformat(meta['date']), byline='Matti Rowe',
        og_image=OgImage(url=url+meta['og_image'], width=1200, height=630) if meta.get('og_image') else None,
        json_ld=(ld,),
    )
    return render_editorial_page(article, body, ladder=False, offer_html=render_offer(offer_for_slug(meta["slug"])), extra_css=CSS)


def import_post(post):
    slug = post['slug']
    if slug in LOCAL_VERSIONS or slug == 'coming-soon':
        return None
    if not post.get('is_published') or post.get('free_unlock_required'):
        raise ValueError(f'{slug}: full published body required; refusing teaser')
    raw = post.get('body_html') or ''
    text = BeautifulSoup(raw, 'html.parser').get_text(' ', strip=True)
    if len(text.split()) < max(50, int((post.get('wordcount') or 0)*.6)):
        raise ValueError(f'{slug}: body shorter than publication word count; refusing partial copy')
    body = clean_body(raw, slug, post['title'])
    meta = {'slug': slug, 'title': post['title'].strip(),
            'subtitle': (post.get('subtitle') or '').strip(),
            'date': post['post_date'][:10], 'source_url': post['canonical_url'],
            'source_wordcount': post.get('wordcount'), 'og_image': ''}
    if post.get('cover_image'):
        _, name, _ = image_asset((post['cover_image'], PAGES/slug/'img', slug))
        with Image.open(PAGES/slug/'img'/name) as im:
            crop = ImageOps.fit(im.convert('RGB'), (1200,630), method=Image.Resampling.LANCZOS)
            crop.save(PAGES/slug/'img/og.jpg', 'JPEG', quality=84, optimize=True)
        meta['og_image'] = 'img/og.jpg'
    SOURCES.mkdir(parents=True, exist_ok=True)
    (SOURCES/(slug+'.body.html')).write_text(body+'\n')
    (SOURCES/(slug+'.json')).write_text(json.dumps(meta,indent=2,ensure_ascii=False)+'\n')
    (PAGES/slug/'index.html').write_text(render(meta,body+'\n'))
    return slug


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshots', type=Path, nargs='?')
    args=parser.parse_args()
    if args.snapshots:
        for path in sorted(args.snapshots.glob('*.json')):
            slug=import_post(json.loads(path.read_text()))
            if slug: print(slug, flush=True)
    else:
        for path in sorted(SOURCES.glob('*.json')):
            meta=json.loads(path.read_text())
            (PAGES/meta['slug']/'index.html').write_text(render(meta,path.with_suffix('.body.html').read_text()))


if __name__=='__main__':
    main()
