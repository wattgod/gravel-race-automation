#!/usr/bin/env python3
"""Redraw every article/post image that shows an old version of the Gravel God character with the
v6.2-v6.7 character rig (wattgod/gravel-god-character, rig/).

Matti, 2026-11-01: "6.2-6.7 is where we're at. Redo all images on website with wrong version of
character." The old versions are the fedora-and-beard cartoon sticker, the painted image-generator
mustache character and the v7 bearded artwork. Each image has one spec row in
data/character-art-v67/specs/<collection>__<slug>.json (collection = articles | posts):

    {"file": "img/x.webp",              # the image as the page uses it (posts: the 1x file)
     "name": "x",                       # posts only: the figure name (renditions key)
     "verdict": "replace" | "keep",     # keep = no old character in it (photo, chart, other art)
     "joke": "...",                     # its words, verbatim (bubbles, captions, signs)
     "mode": "composite" | "rebuild" | "scene",
     "erase": "shiftmap" | "telea" | "#rrggbb",   # composite: how the old cartoon is removed
     "figs": [{"box": [x0, y0, x1, y1], # where he stands, in 1x pixels (hat to feet)
               "erase_box": [...],      # optional: the old cartoon's box if it differs
               "mask": "box" | "grabcut",       # box (default): erase the whole box
               "pose": "arms_crossed", "ride": null, "face": "smile", "psi": 80, "elev": 6,
               "crop": "full" | "bust" | "head", "fit": "height" | "width" | "contain",
               "scale": 1.0, "dx": 0, "dy": 0, "anchor": "bottom" | "top" | "center"}],
     "bg": {"type": "flat", "color": "#f5efe6"} | {"type": "chalk"} | {"type": "original"},
     "scene": {...},                    # mode=scene: a gg_scene gravel road (see render_scene)
     "insets": [{"src": [x0, y0, x1, y1], "box": [...]}],   # pieces of the original kept (TV, chart)
     "shapes": [{"type": "rect" | "line" | "ellipse", "box": [...], "fill": "#hex", "outline": null, "width": 0}],
     "texts": [{"type": "bubble" | "caption" | "meme", "text": "...", "box": [...], "tail": [x, y],
                "size": 40, "font": "serif" | "mono", "weight": 700, "color": "#1a1613",
                "align": "center", "fill": "#ffffff", "stroke": null}],
     "alt": "...",                      # posts: the new alt text
     "match": "exact" | "closest", "note": "what the rig could not reproduce"}

    python3 scripts/render_character_art_v67.py --work /tmp/v67            # render every spec
    python3 scripts/render_character_art_v67.py --work /tmp/v67 --only posts__does-beer-make-you-slow
    python3 scripts/render_character_art_v67.py --work /tmp/v67 --apply    # + write site files

Originals are read from git at BASE (before this redraw), so re-renders are reproducible after the
old files are deleted. Needs the rig checkout (~/gravel-god-character or $GG_CHARACTER_RIG),
rsvg-convert, Pillow, numpy and opencv-contrib (cv2.xphoto) for removing old cartoons from photos.
No paid image calls.
"""
from __future__ import annotations

import argparse, io, json, os, re, subprocess, sys, textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / 'data' / 'character-art-v67' / 'specs'
WP = ROOT / 'wordpress'
BASE = 'd8950bb9'           # the commit before the redraw: originals come from here
TAG = 'v67'
RIG = Path(os.environ.get('GG_CHARACTER_RIG', Path.home() / 'gravel-god-character' / 'rig'))
FONTS = RIG / 'fonts'

import numpy as np                                              # noqa: E402
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps  # noqa: E402

_rig = None


def rig():
    """Import the rig lazily (it chdirs for its assets)."""
    global _rig
    if _rig is None:
        if not (RIG / 'gg_rig3d.py').is_file():
            sys.exit(f'Character rig not found at {RIG}. Clone wattgod/gravel-god-character or set GG_CHARACTER_RIG.')
        sys.path.insert(0, str(RIG))
        cwd = os.getcwd(); os.chdir(RIG)
        try:
            from gg_common import _fontconfig
            _fontconfig()
            import gg_character
            gg_character.set_outfit('street')
            import gg_rig3d, gg_rig3d_math, gg_poses, gg_offbike, gg_head_art, gg_scene
        finally:
            os.chdir(cwd)
        _rig = dict(character=gg_character, rig3d=gg_rig3d, math=gg_rig3d_math, poses=gg_poses,
                    offbike=gg_offbike, head=gg_head_art, scene=gg_scene)
    return _rig


def svg_png(svg: str, W: int, H: int) -> Image.Image:
    png = subprocess.run(['rsvg-convert', '-w', str(W), '-h', str(H)], input=svg.encode(),
                         capture_output=True, check=True, cwd=RIG).stdout
    return Image.open(io.BytesIO(png)).convert('RGBA')


# ── the character ──────────────────────────────────────────────────────────

_fig_cache: dict = {}


def _drop_collar(im: Image.Image) -> Image.Image:
    """Head crop: remove the tee (pale, grey-ish regions touching the bottom edge) so a head can
    sit on a photo's own neck/jersey without a white shelf. Eye whites never touch the bottom."""
    a = np.array(im)
    rgb = a[:, :, :3].astype(np.int16); al = a[:, :, 3]
    sat = rgb.max(axis=2) - rgb.min(axis=2)
    pale = ((sat < 40) & (rgb.max(axis=2) > 90) & (al > 0)).astype(np.uint8)
    import cv2
    n, lab = cv2.connectedComponents(pale, connectivity=8)
    H = a.shape[0]
    bottom = set(np.unique(lab[H - 3:H][pale[H - 3:H] > 0]).tolist()) - {0}
    if bottom:
        m = np.isin(lab, list(bottom))
        m = cv2.dilate(m.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        a[:, :, 3][m] = 0
    return Image.fromarray(a)


def figure(pose='arms_crossed', face=None, psi=80, elev=6, ride=None, crop='full', k=900, **_):
    """The rig character, transparent and tightly cropped. crop: full | bust | head."""
    key = (pose, face, psi, elev, ride, crop, k)
    if key in _fig_cache:
        return _fig_cache[key].copy()
    r = rig()
    Bike, RideBody, draw_scene = r['rig3d'].Bike, r['rig3d'].RideBody, r['rig3d'].draw_scene
    W, H = 2400, 2600
    if ride:
        bike = Bike(wheel=20, crank=-35)
        p = dict(r['poses'].RIDE_POSES[ride]['pose'])
        if face: p['face'] = face
        bodies, bikes = [RideBody(bike, p)], [bike]
    else:
        bodies, bikes = r['offbike'].OFFBIKE_POSES[pose]['build'](0.0)
    if face:
        bodies[0].face = face
    hs = r['head'].HEAD_SCALE
    kk = k * {'head': 2.6, 'bust': 1.8}.get(crop, 1.0)
    cam = r['math'].Cam(psi, 0, 0, kk, elev_deg=elev)
    if crop in ('head', 'bust'):
        hd = bodies[0].head
        px, py = cam.P((hd[0], hd[1], hd[2] + 0.1 * (hs - 1.0)))
        cam.ox, cam.oy = W / 2 - px, H * 0.32 - py
    else:
        ref = bodies[0].hip
        px, py = cam.P((ref[0], ref[1], 0.0))
        cam.ox, cam.oy = W / 2 - px, H * 0.93 - py
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
           f'<defs>{r["character"].DEFS}</defs>{draw_scene(cam, bikes, bodies, shadow=False)}</svg>')
    im = svg_png(svg, W, H)
    if crop in ('head', 'bust'):
        hd = bodies[0].head
        _, ny = cam.P((hd[0], hd[1], hd[2] - (0.13 * hs if crop == 'head' else 0.42)))
        im = im.crop((0, 0, W, min(H, int(ny))))
        if crop == 'head':
            im = _drop_collar(im)
    im = im.crop(im.getbbox())
    _fig_cache[key] = im
    return im.copy()


def place(img: Image.Image, fig: Image.Image, box, fit='height', anchor='bottom', scale=1.0, dx=0.0, dy=0.0,
          shadow=True) -> Image.Image:
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    fw, fh = fig.size
    s = {'height': bh / fh, 'width': bw / fw}.get(fit, min(bw / fw, bh / fh)) * scale
    f = fig.resize((max(1, round(fw * s)), max(1, round(fh * s))), Image.LANCZOS)
    px = (x0 + x1) / 2 + dx * bw - f.size[0] / 2
    py = {'bottom': y1 - f.size[1], 'top': y0}.get(anchor, (y0 + y1) / 2 - f.size[1] / 2) + dy * bh
    out = img.convert('RGBA')
    if shadow:   # a soft contact shadow so he sits in the picture rather than on it
        a = f.getchannel('A').point(lambda v: int(v * 0.28))
        sh = Image.new('RGBA', f.size, (0, 0, 0, 0)); sh.putalpha(a)
        sh = sh.filter(ImageFilter.GaussianBlur(max(2, f.size[1] // 90)))
        _over(out, sh, int(px + f.size[0] * 0.015), int(py + f.size[1] * 0.008))
    _over(out, f, int(px), int(py))
    return out


def _over(dst: Image.Image, src: Image.Image, x: int, y: int):
    """alpha_composite that clips at the canvas edge (he may stand partly out of frame)."""
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(dst.size[0], x + src.size[0]), min(dst.size[1], y + src.size[1])
    if x1 <= x0 or y1 <= y0:
        return
    dst.alpha_composite(src.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


# ── removing the old cartoon ─────────────────────────────────────────────────

def old_mask(img: Image.Image, box, mode='grabcut', pad=6) -> np.ndarray:
    import cv2
    a = np.array(img.convert('RGB'))[:, :, ::-1].copy()
    H, W = a.shape[:2]
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    m = np.zeros((H, W), np.uint8)
    if mode == 'box':
        m[y0:y1, x0:x1] = 1
    else:
        gm = np.zeros((H, W), np.uint8)
        bgm = np.zeros((1, 65), np.float64); fgm = np.zeros((1, 65), np.float64)
        rx0, ry0 = max(0, x0 - 2), max(0, y0 - 2)
        rect = (rx0, ry0, max(2, min(W - 1, x1 + 2) - rx0), max(2, min(H - 1, y1 + 2) - ry0))
        try:
            cv2.grabCut(a, gm, rect, bgm, fgm, 5, cv2.GC_INIT_WITH_RECT)
            m = np.where((gm == cv2.GC_FGD) | (gm == cv2.GC_PR_FGD), 1, 0).astype(np.uint8)
        except cv2.error:
            m[y0:y1, x0:x1] = 1
        if m.sum() < 0.15 * max(1, (x1 - x0) * (y1 - y0)):     # grabcut found nothing: use the box
            m[:] = 0; m[y0:y1, x0:x1] = 1
    if pad:
        m = cv2.dilate(m, np.ones((pad * 2 + 1, pad * 2 + 1), np.uint8))
    return m


def clone_fill(a: np.ndarray, m: np.ndarray) -> np.ndarray:
    """Fill each hole with real texture from beside it: the neighbouring patch (left/right/up/down,
    whichever matches the hole's surroundings best and holds no hole), feathered in, so grass stays
    grass and chalk stays chalk."""
    import cv2
    H, W = m.shape
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    out = a.copy()
    for i in range(1, n):
        x, y, w, h = (int(v) for v in stats[i, :4])
        hole = (lab[y:y + h, x:x + w] == i)
        g = max(4, min(w, h) // 8)
        P = cv2.copyMakeBorder(out, g, g, g, g, cv2.BORDER_REPLICATE).astype(np.float32)
        PM = cv2.copyMakeBorder(m, g, g, g, g, cv2.BORDER_REPLICATE)
        ring = P[y:y + h + 2 * g, x:x + w + 2 * g]
        rmask = PM[y:y + h + 2 * g, x:x + w + 2 * g] == 0
        if not rmask.any():
            rmask[:] = True
        best, pick = 1e18, None
        for fx, fy in ((-1, 0), (1, 0), (-1.3, 0), (1.3, 0), (-1.7, 0), (1.7, 0), (-2.2, 0), (2.2, 0),
                       (0, -1), (0, 1), (0, -1.4), (0, 1.4), (-1, -1), (1, -1), (-1, 1), (1, 1)):
            sx, sy = int(x + fx * w), int(y + fy * h)
            if sx < 0 or sy < 0 or sx + w > W or sy + h > H or m[sy:sy + h, sx:sx + w].any():
                continue
            cand = P[sy:sy + h + 2 * g, sx:sx + w + 2 * g]
            err = float(np.abs(cand - ring)[rmask].mean()) * (1 + 0.08 * (abs(fx) + abs(fy)))
            if err < best:
                best, pick = err, (sx, sy)
        if pick is None:          # nowhere clean to copy from: smooth fill
            out = cv2.inpaint(out, (lab == i).astype(np.uint8) * 255, 9, cv2.INPAINT_TELEA)
            continue
        sx, sy = pick
        patch = out[sy:sy + h, sx:sx + w].astype(np.float32)
        alpha = cv2.dilate(hole.astype(np.uint8), np.ones((2 * g + 1, 2 * g + 1), np.uint8)).astype(np.float32)
        alpha = cv2.GaussianBlur(alpha, (0, 0), g / 2)
        alpha = np.maximum(alpha, hole.astype(np.float32))[:, :, None]
        reg = out[y:y + h, x:x + w].astype(np.float32)
        # pull the patch's colour toward the hole's surroundings
        ring_mean = ring[rmask].mean(axis=0)
        cand_ring = P[sy:sy + h + 2 * g, sx:sx + w + 2 * g][rmask].mean(axis=0)
        patch = np.clip(patch + (ring_mean - cand_ring), 0, 255)
        out[y:y + h, x:x + w] = (patch * alpha + reg * (1 - alpha)).astype(np.uint8)
        m = m.copy(); m[lab == i] = 0      # filled: later holes may copy from here
    return out


def erase(img: Image.Image, masks, method='clone') -> Image.Image:
    import cv2
    a = np.array(img.convert('RGB'))[:, :, ::-1].copy()
    m = np.zeros(a.shape[:2], np.uint8)
    for mm in masks:
        m |= mm
    if not m.any():
        return img.convert('RGB')
    if method.startswith('#'):
        c = tuple(int(method[i:i + 2], 16) for i in (1, 3, 5))
        a[m > 0] = c[::-1]
    elif method == 'clone':
        a = clone_fill(a, m)
    elif method == 'telea':
        a = cv2.inpaint(a, m * 255, max(3, int(min(a.shape[:2]) * 0.01)), cv2.INPAINT_TELEA)
    else:
        dst = np.zeros_like(a)
        cv2.xphoto.inpaint(a, (1 - m) * 255, dst, cv2.xphoto.INPAINT_SHIFTMAP)
        a = dst
    return Image.fromarray(a[:, :, ::-1])


# ── words ──────────────────────────────────────────────────────────────────

INK, PAPER = '#1a1613', '#f5efe6'


def font(kind='serif', size=40, weight=700):
    if kind == 'mono':
        return ImageFont.truetype(str(FONTS / 'SometypeMono.ttf'), size)
    f = ImageFont.truetype(str(FONTS / ('SourceSerif4-Italic.ttf' if kind == 'italic' else 'SourceSerif4.ttf')), size)
    try:
        f.set_variation_by_axes([weight, min(60, max(8, size // 3))])
    except Exception:
        pass
    return f


def wrap_fit(d, text, box_w, box_h, kind, weight, size, min_size=10, spacing=1.15):
    """Largest size <= `size` at which `text` wraps inside box_w x box_h. Keeps the author's line
    breaks; wraps long lines on spaces."""
    s = size
    while s >= min_size:
        f = font(kind, s, weight)
        lines = []
        for para in text.split('\n'):
            words, cur = para.split(' '), ''
            for w in words:
                t = (cur + ' ' + w).strip()
                if d.textlength(t, font=f) <= box_w or not cur:
                    cur = t
                else:
                    lines.append(cur); cur = w
            lines.append(cur)
        lh = s * spacing
        if max(d.textlength(l, font=f) for l in lines) <= box_w and lh * len(lines) <= box_h:
            return f, lines, lh
        s -= max(1, s // 20)
    f = font(kind, min_size, weight)
    return f, text.split('\n'), min_size * spacing


def draw_text_block(d, box, text, kind='serif', weight=600, size=48, color=INK, align='center',
                    stroke=None, stroke_w=0, valign='center'):
    x0, y0, x1, y1 = box
    f, lines, lh = wrap_fit(d, text, x1 - x0, y1 - y0, kind, weight, size)
    th = lh * len(lines)
    y = {'top': y0, 'bottom': y1 - th}.get(valign, (y0 + y1) / 2 - th / 2)
    for ln in lines:
        w = d.textlength(ln, font=f)
        x = {'left': x0, 'right': x1 - w}.get(align, (x0 + x1) / 2 - w / 2)
        d.text((x, y + (lh - f.size) / 2), ln, font=f, fill=color,
               stroke_width=stroke_w, stroke_fill=stroke)
        y += lh


def bubble(img: Image.Image, t: dict, sc: float) -> Image.Image:
    """A speech bubble (ellipse, ink outline) with a tail to `tail`, or a thought bubble."""
    x0, y0, x1, y1 = (v * sc for v in t['box'])
    out = img.convert('RGBA'); d = ImageDraw.Draw(out)
    lw = max(2, round(min(x1 - x0, y1 - y0) * 0.022))
    fill = t.get('fill', '#ffffff'); edge = t.get('edge', INK)
    if t.get('tail'):
        tx, ty = (v * sc for v in t['tail'])
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if t.get('thought'):
            for i, f in enumerate((0.35, 0.62, 0.85)):
                r = (1 - f) * min(x1 - x0, y1 - y0) * 0.12 + lw
                px, py = cx + (tx - cx) * f, cy + (ty - cy) * f
                d.ellipse((px - r, py - r, px + r, py + r), fill=fill, outline=edge, width=lw)
        else:
            ang = np.arctan2(ty - cy, tx - cx); half = 0.13
            rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
            pts = [(cx + rx * 0.82 * np.cos(ang + s), cy + ry * 0.82 * np.sin(ang + s)) for s in (-half, half)]
            d.polygon([pts[0], (tx, ty), pts[1]], fill=fill, outline=edge, width=lw)
    if t.get('shape') == 'rect':
        d.rounded_rectangle((x0, y0, x1, y1), radius=(y1 - y0) * 0.22, fill=fill, outline=edge, width=lw)
    else:
        d.ellipse((x0, y0, x1, y1), fill=fill, outline=edge, width=lw)
    if t.get('tail') and not t.get('thought'):   # clean the seam where the tail joins
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = (x1 - x0) / 2 - lw * 1.5, (y1 - y0) / 2 - lw * 1.5
        if t.get('shape') != 'rect':
            d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=fill)
    ix, iy = (x1 - x0) * (0.16 if t.get('shape') != 'rect' else 0.07), (y1 - y0) * (0.2 if t.get('shape') != 'rect' else 0.12)
    draw_text_block(d, (x0 + ix, y0 + iy, x1 - ix, y1 - iy), t['text'], t.get('font', 'serif'),
                    t.get('weight', 600), round(t.get('size', 40) * sc), t.get('color', INK))
    return out


def caption(img: Image.Image, t: dict, sc: float) -> Image.Image:
    out = img.convert('RGBA'); d = ImageDraw.Draw(out)
    box = [v * sc for v in t['box']]
    if t.get('fill'):
        pad = round(t.get('pad', 10) * sc)
        d.rectangle((box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad), fill=t['fill'])
    stroke = t.get('stroke')
    draw_text_block(d, box, t['text'], t.get('font', 'serif'), t.get('weight', 700), round(t.get('size', 48) * sc),
                    t.get('color', INK), t.get('align', 'center'), stroke,
                    max(1, round(t.get('size', 48) * sc * 0.07)) if stroke else 0, t.get('valign', 'center'))
    return out


def meme(img: Image.Image, t: dict, sc: float) -> Image.Image:
    """Top/bottom meme lines in the brand serif, black weight, white with ink outline."""
    W, H = img.size
    for key, box in (('top', (0.04, 0.02, 0.96, 0.24)), ('bottom', (0.04, 0.76, 0.96, 0.98))):
        if t.get(key):
            img = caption(img, {'text': t[key].upper(), 'box': [box[0] * W / sc, box[1] * H / sc, box[2] * W / sc, box[3] * H / sc],
                                'weight': 900, 'size': t.get('size', 72), 'color': '#ffffff', 'stroke': INK,
                                'valign': 'top' if key == 'top' else 'bottom'}, sc)
    return img


def draw_shapes(img, shapes, sc):
    """Plain flat shapes in brand colours: panels, divider lines, a ground strip."""
    if not shapes:
        return img
    out = img.convert('RGBA'); d = ImageDraw.Draw(out)
    for sh in shapes:
        b = [v * sc for v in sh['box']]
        w = round(sh.get('width', 0) * sc)
        if sh.get('type') == 'line':
            d.line(b, fill=sh.get('fill', INK), width=max(1, w))
        elif sh.get('type') == 'ellipse':
            d.ellipse(b, fill=sh.get('fill'), outline=sh.get('outline'), width=w)
        else:
            d.rectangle(b, fill=sh.get('fill'), outline=sh.get('outline'), width=w)
    return out


def draw_texts(img, texts, sc):
    for t in texts or ():
        kind = t.get('type', 'bubble')
        img = {'bubble': bubble, 'caption': caption, 'meme': meme}[kind](img, t, sc)
    return img


# ── backgrounds ────────────────────────────────────────────────────────────

def chalkboard(W, H, seed=3):
    rng = np.random.default_rng(seed)
    base = np.full((H, W, 3), (38, 40, 39), np.float32)
    n = rng.normal(0, 1, (H // 8 + 1, W // 8 + 1)).astype(np.float32)
    n = np.array(Image.fromarray(((n - n.min()) / (np.ptp(n) + 1e-6) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32)
    base += (n[:, :, None] - 128) * 0.09
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))


def background(bg: dict, W: int, H: int) -> Image.Image:
    t = bg.get('type', 'flat')
    if t == 'chalk':
        return chalkboard(W, H)
    if t == 'gradient':
        a = np.array([int(bg['top'][i:i + 2], 16) for i in (1, 3, 5)], np.float32)
        b = np.array([int(bg['bottom'][i:i + 2], 16) for i in (1, 3, 5)], np.float32)
        y = np.linspace(0, 1, H)[:, None, None]
        return Image.fromarray(np.broadcast_to(a + (b - a) * y, (H, W, 3)).astype(np.uint8))
    return Image.new('RGB', (W, H), bg.get('color', PAPER))


SCENE_PAL = {
    'storm': dict(sky_top='#7f7c79', sky_hz='#cbc2b2', sun='none', sun_ring='none', hill_far='#a9a294',
                  hill_mid='#b6ad9b', hill_near='#c2b7a1', haze='#d9d0bf', ground='#d6cab0', ground_lt='#e0d6c0',
                  ground_dk='#c6b896'),
    'dusk': dict(sky_top='#d98b5f', sky_hz='#f3c98b', sun='#f6e3a1', sun_ring='#e9a35b', hill_far='#c9967a',
                 hill_mid='#b98a6d', hill_near='#a87f63', haze='#f0c9a0'),
    'night': dict(sky_top='#1f2a3a', sky_hz='#4a5568', sun='#e8e4d0', sun_ring='#9aa3b0', hill_far='#36404f',
                  hill_mid='#2f3846', hill_near='#29313d', haze='#556070', ground='#6b6a63', ground_lt='#78766d',
                  ground_dk='#5d5c56', road='#8a877d', road_edge='#6f6c63', rut='#7d7a70', verge='#5f6058'),
    'snow': dict(sky_top='#c9d4dd', sky_hz='#eef2f4', sun='#f7f4ea', sun_ring='#dfe6ea', hill_far='#dfe6ea',
                 hill_mid='#e8edf0', hill_near='#f1f4f6', haze='#f4f6f7', ground='#f3f5f6', ground_lt='#fafbfb',
                 ground_dk='#e3e8eb', road='#e9edf0', road_edge='#cfd8de', rut='#dde3e7', verge='#e6ebee',
                 tuft='#c9d1d6', tuft_dk='#b7c0c6', canopy=('#6f8577', '#62786a', '#7b9182')),
    'green': dict(hill_far='#c9cfb0', hill_mid='#b9c49b', hill_near='#a9b788', ground='#cdd3ae', ground_lt='#d9dfbd',
                  ground_dk='#bcc39b', verge='#b9c28f', tuft='#8f9a62', tuft_dk='#7b8652'),
}


def render_scene(sc_spec: dict, W: int, H: int) -> Image.Image:
    """A gravel road scene with him in it (the guide renderer's recipe). Keys: pose|ride, face,
    rel (camera heading vs the road), elev, k (px per metre at this W), pos (hip at fraction of
    the frame), profile, trees [[s, off]...], signs [{s, off, lines, turn}], cones, palette, seed."""
    r = rig(); gs = r['scene']
    Bike, RideBody = r['rig3d'].Bike, r['rig3d'].RideBody
    cwd = os.getcwd(); saved = dict(gs.PAL)
    try:
        os.chdir(RIG)
        gs.PAL.update(SCENE_PAL.get(sc_spec.get('palette', ''), {}))
        start = (-34.0, 0.0) if sc_spec.get('ride') else (-34.0, -2.6)
        env = gs.World(gs.Path([('straight', 70)], start=start), profile=sc_spec.get('profile'), disc=18,
                       seed=sc_spec.get('seed', 2))
        for i, (s, off) in enumerate(sc_spec.get('trees', [])):
            env.add(gs.Tree(env.path.at(s, off), h=3.4 + (i % 3) * 0.3, seed=i + 20))
        env.scatter_rocks(n=16, seed=sc_spec.get('seed', 2))
        rel, elev = sc_spec.get('rel', 40), sc_spec.get('elev', 5)
        k = sc_spec.get('k', 420) * W / 1920
        face = sc_spec.get('face')
        if sc_spec.get('ride'):
            bk = gs.place_bike_on_path(env, 34.0, speed=7); bk.update(crank=sc_spec.get('crank', -35))
            bike = Bike(**bk)
            p = dict(r['poses'].RIDE_POSES[sc_spec['ride']]['pose'])
            if face: p['face'] = face
            body = RideBody(bike, p)
            if face: body.face = face
            bikes, bodies, kws = [bike], [body], [bk]
        else:
            b = r['offbike'].OFFBIKE_POSES[sc_spec.get('pose', 'stand')]['build'](0.0)
            body = b[0][0]
            if face: body.face = face
            bikes = list(b[1]) or ([Bike(x=-0.35, y=1.35, roll=10, crank=-60)] if sc_spec.get('bike', True) else [])
            bodies, kws = [body], []
        for sg in sc_spec.get('signs', []):
            xy = env.path.at(sg['s'], sg['off']) if 's' in sg else tuple(sg['xy'])
            env.add(gs.Sign(xy, rel - 90 + sg.get('turn', 0), lines=tuple(sg['lines']), post=sg.get('post', 1.25)))
        for c in sc_spec.get('cones', []):
            env.add(gs.Cone(env.path.at(*c)))
        hip = body.hip
        yaw = kws[0]['yaw'] if kws else 0.0
        pos = sc_spec.get('pos', (0.5, 0.45))
        cam = gs.follow_cam(hip, (pos[0] * W, pos[1] * H), yaw + rel, elev, k)
        inner = gs.compose(cam, W, H, env, bikes=bikes, bodies=bodies, focus=(hip[0], hip[1]), bike_kws=kws,
                           keep_clear=(hip, 0.42 * k))
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
               f'<defs>{r["character"].DEFS}</defs>{inner}</svg>')
        return svg_png(svg, W, H).convert('RGB')
    finally:
        os.chdir(cwd); gs.PAL.clear(); gs.PAL.update(saved)


# ── one image ──────────────────────────────────────────────────────────────

def git_bytes(path: str) -> bytes | None:
    p = subprocess.run(['git', 'show', f'{BASE}:{path}'], cwd=ROOT, capture_output=True)
    return p.stdout if p.returncode == 0 else None


def original(collection: str, slug: str, file: str):
    """(image at the best resolution kept, 1x size). Posts keep an @2x for wide images."""
    rel = f'wordpress/{collection}/{slug}/{file}'
    one = git_bytes(rel)
    if one is None:
        raise FileNotFoundError(rel)
    im1 = Image.open(io.BytesIO(one)); im1.seek(0)
    size1 = im1.size
    best = im1
    if True:   # posts and hand-built articles keep an @2x for wide images
        two = git_bytes(re.sub(r'\.webp$', '@2x.webp', rel))
        if two:
            best = Image.open(io.BytesIO(two))
    best.seek(0)
    return best.convert('RGB'), size1


def render_one(collection: str, slug: str, e: dict) -> Image.Image:
    src, (w1, h1) = original(collection, slug, e['file'])
    W, H = src.size
    sc = W / w1
    mode = e.get('mode', 'composite')
    if mode == 'scene':
        img = render_scene(e['scene'], W, H).convert('RGBA')
    elif mode == 'rebuild':
        img = background(e.get('bg', {}), W, H).convert('RGBA')
    else:
        masks = [old_mask(src, [v * sc for v in (f.get('erase_box') or f['box'])], f.get('mask', 'box'),
                          round(f.get('pad', 6) * sc))
                 for f in e.get('figs', []) if not f.get('no_erase')]
        for b in e.get('erase_extra', []):
            masks.append(old_mask(src, [v * sc for v in b], 'box', 0))
        img = erase(src, masks, e.get('erase', 'clone')).convert('RGBA')
    for ins in e.get('insets', []):          # keep a piece of the original (a TV, a chart, a sign)
        piece = src.crop([v * sc for v in ins['src']])
        bx = [v * sc for v in ins['box']]
        img.paste(piece.resize((round(bx[2] - bx[0]), round(bx[3] - bx[1])), Image.LANCZOS), (round(bx[0]), round(bx[1])))
    img = draw_shapes(img, e.get('shapes'), sc)
    for f in e.get('figs', []):
        if f.get('only_erase'):
            continue
        fig = figure(**f)
        img = place(img, fig, [v * sc for v in f['box']], f.get('fit', 'height'), f.get('anchor', 'bottom'),
                    f.get('scale', 1.0), f.get('dx', 0), f.get('dy', 0), f.get('shadow', mode != 'rebuild' or True))
    img = draw_texts(img, e.get('texts'), sc)
    return img.convert('RGB')


def load_specs(only=None):
    for p in sorted(SPECS.glob('*.json')):
        if only and p.stem not in only:
            continue
        yield p.stem, json.loads(p.read_text())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--work', required=True, help='folder for full-size PNG renders')
    ap.add_argument('--only', nargs='*', help='spec stems, e.g. posts__does-beer-make-you-slow')
    ap.add_argument('--file', nargs='*', help='only these image files')
    ap.add_argument('--apply', action='store_true', help='also write the site files (see apply_v67_art.py)')
    a = ap.parse_args()
    work = Path(a.work)
    for stem, spec in load_specs(a.only):
        coll, slug = spec['collection'], spec['slug']
        for e in spec['images']:
            if e.get('verdict') != 'replace':
                continue
            if a.file and e['file'] not in a.file and Path(e['file']).name not in a.file:
                continue
            out = work / stem / (Path(e['file']).stem + '.png')
            out.parent.mkdir(parents=True, exist_ok=True)
            render_one(coll, slug, e).save(out)
            print(out, flush=True)
    if a.apply:
        sys.path.insert(0, str(ROOT / 'scripts'))
        import apply_character_art_v67
        apply_character_art_v67.apply(work, a.only)


if __name__ == '__main__':
    main()
