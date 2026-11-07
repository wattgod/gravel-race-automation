#!/usr/bin/env python3
"""Write the v6.7 character redraws (render_character_art_v67.py --work DIR) into the site sources.

    python3 scripts/apply_character_art_v67.py --work DIR [--only posts__slug ...]

Substack articles (wordpress/articles/<slug>/): img/<stem>-v67.webp at the old image's exact size,
the body's src switched in wordpress/substack_sources/<slug>.body.html, a new og image
(img/og-v67.jpg) when the cover was redrawn, old files deleted, pages re-rendered with
scripts/import_substack_posts.py. Re-importing from Substack snapshots would bring the old art back.

Imported WordPress posts (wordpress/posts/<slug>/): <name>-v67 renditions (1x/@2x/phone/og) via
wp_post_import.still_renditions/og_rendition, renditions + figure kind updated in post_sources/<slug>.json,
the ALT entry rewritten in the post module, old files deleted, the post re-rendered.

New file names because /articles/ and post img/ folders are served with a long cache.
"""
from __future__ import annotations

import argparse, ast, io, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'wordpress'))
WP = ROOT / 'wordpress'
SPECS = ROOT / 'data' / 'character-art-v67' / 'specs'
SITE = 'https://gravelgodcycling.com'
TAG = 'v67'

from PIL import Image, ImageOps  # noqa: E402


def _rm(p: Path):
    if p.exists():
        subprocess.run(['git', 'rm', '-q', '--cached', '--ignore-unmatch', str(p)], cwd=ROOT)
        p.unlink()


def cover_of(slug: str) -> str | None:
    """Which body image the article's og.jpg was cropped from (og = fit(cover, 1200x630))."""
    d = WP / 'articles' / slug / 'img'
    og = d / 'og.jpg'
    if not og.exists():
        return None
    from PIL import ImageChops, ImageStat
    o = Image.open(og).convert('L').resize((120, 63))
    best, name = 1e9, None
    for f in d.iterdir():
        if f.suffix not in ('.webp', '.gif') or TAG in f.stem:
            continue
        with Image.open(f) as im:
            im.seek(0)
            c = ImageOps.fit(im.convert('L'), (120, 63))
        err = ImageStat.Stat(ImageChops.difference(c, o)).mean[0]
        if err < best:
            best, name = err, f.name
    return name if best < 12 else None


def apply_article(slug: str, spec: dict, work: Path, stem: str) -> int:
    d = WP / 'articles' / slug / 'img'
    body_p = WP / 'substack_sources' / f'{slug}.body.html'
    meta_p = WP / 'substack_sources' / f'{slug}.json'
    body = body_p.read_text()
    meta = json.loads(meta_p.read_text())
    cover = cover_of(slug)
    n = 0
    for e in spec['images']:
        if e.get('verdict') != 'replace':
            continue
        png = work / stem / (Path(e['file']).stem + '.png')
        old = WP / 'articles' / slug / e['file']
        new_name = f'{Path(e["file"]).stem}-{TAG}.webp'
        with Image.open(png) as im:
            if old.exists():
                with Image.open(old) as o:
                    size = o.size
            else:
                size = tuple(e['size'])
            im.convert('RGB').resize(size, Image.LANCZOS).save(d / new_name, 'WEBP', quality=83, method=6)
            if cover and Path(e['file']).name == cover:
                ImageOps.fit(im.convert('RGB'), (1200, 630), Image.LANCZOS).save(d / f'og-{TAG}.jpg', 'JPEG',
                                                                                 quality=84, optimize=True)
                meta['og_image'] = f'img/og-{TAG}.jpg'
                _rm(d / 'og.jpg')
        body = body.replace(f'src="{e["file"]}"', f'src="img/{new_name}"')
        _rm(old)
        n += 1
    body_p.write_text(body)
    meta_p.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + '\n')
    return n


def set_alt(module: Path, key: str, alt: str):
    src = module.read_text()
    tree = ast.parse(src)
    ns = {}                                   # module-level string constants, for keys like f"{_P}-3"
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
            ns[node.targets[0].id] = node.value.value

    def keyval(k):
        try:
            return eval(compile(ast.Expression(k), '<alt-key>', 'eval'), {'__builtins__': {}}, dict(ns))
        except Exception:
            return None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', '') == 'ALT' for t in node.targets):
            for k, v in zip(node.value.keys, node.value.values):
                if k is not None and keyval(k) == key:
                    lines = src.splitlines(keepends=True)
                    # col_offset is in UTF-8 bytes
                    pre = lines[v.lineno - 1].encode()[:v.col_offset].decode()
                    start = sum(len(l) for l in lines[:v.lineno - 1]) + len(pre)
                    pre_e = lines[v.end_lineno - 1].encode()[:v.end_col_offset].decode()
                    end = sum(len(l) for l in lines[:v.end_lineno - 1]) + len(pre_e)
                    module.write_text(src[:start] + json.dumps(alt, ensure_ascii=False) + src[end:])
                    return True
    return False


def post_module(slug: str) -> Path:
    for p in (WP / 'post_sources').glob('*.py'):
        if re.search(rf'^SLUG = "{re.escape(slug)}"', p.read_text(), re.M):
            return p
    raise FileNotFoundError(slug)


def apply_post(slug: str, spec: dict, work: Path, stem: str) -> int:
    import wp_post_import as wpi
    d = WP / 'posts' / slug / 'img'
    jp = WP / 'post_sources' / f'{slug}.json'
    data = json.loads(jp.read_text())
    mod = post_module(slug)
    feat = (data.get('featured') or {}).get('name')
    n = 0
    for e in spec['images']:
        if e.get('verdict') != 'replace':
            continue
        name = e['name']
        png = work / stem / (Path(e['file']).stem + '.png')
        r = data['renditions'][name]
        old_files = [v['file'] for v in r.values() if isinstance(v, dict) and 'file' in v]
        new = wpi.still_renditions(png, d, f'{name}-{TAG}', force=True)
        if name == feat:
            new['og'] = wpi.og_rendition(png, d, f'{name}-{TAG}', force=True)
        prev = dict(r); r.clear()           # keep the key order so the json diff stays small
        for k, v in prev.items():
            if k in new:
                r[k] = new[k]
            elif k not in ('1x', '2x', 'phone', 'phone2x', 'mp4', 'webm', 'og'):
                r[k] = v
        for k, v in new.items():
            r.setdefault(k, v)
        if name == feat:
            data['featured']['kind'] = 'still'
        for f in data.get('figures', []):
            if f['name'] == name and f.get('kind') == 'gif':
                f['kind'] = 'still'     # the redraw is a still; the old GIF's videos go
        for f in old_files:
            if f not in {v['file'] for v in r.values() if isinstance(v, dict) and 'file' in v}:
                _rm(d / f)
        if e.get('alt') and not set_alt(mod, name, e['alt']):
            print(f'  ! {slug}: no ALT entry for {name}')
        n += 1
    jp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n')
    return n


def apply(work: Path, only=None):
    total = 0
    touched_articles, touched_posts = False, []
    for p in sorted(SPECS.glob('*.json')):
        if only and p.stem not in only:
            continue
        spec = json.loads(p.read_text())
        if not any(e.get('verdict') == 'replace' for e in spec['images']):
            continue
        if spec['collection'] == 'articles':
            total += apply_article(spec['slug'], spec, work, p.stem); touched_articles = True
        else:
            total += apply_post(spec['slug'], spec, work, p.stem); touched_posts.append(spec['slug'])
    if touched_articles:
        subprocess.run([sys.executable, 'scripts/import_substack_posts.py'], cwd=ROOT, check=True)
    for slug in touched_posts:
        subprocess.run([sys.executable, str(post_module(slug))], cwd=ROOT, check=True)
    if touched_articles or touched_posts:     # the listing shows each page's og image
        subprocess.run([sys.executable, 'wordpress/generate_articles_index.py'], cwd=ROOT, check=True)
    print(f'applied {total} images')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True)
    ap.add_argument('--only', nargs='*')
    a = ap.parse_args()
    apply(Path(a.work), a.only)
