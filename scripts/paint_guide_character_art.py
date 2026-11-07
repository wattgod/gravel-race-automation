#!/usr/bin/env python3
"""Repaint the Gravel Handbook chapter art with the locked v6.7 character (paid image calls).

Matti, 2026-11-06: "Can we make the flat v6.7 redraws less flat with richer detail? I want a consistent
character" -> "Yes, paint them". Each scene starts from the painted original that was live before #534
(rooms, props, crowds, light). His head is covered with a grey box first, so the image model has to
draw it from the rig's head cards instead of keeping the old face (a plain "replace him" edit kept it).

    python3 scripts/paint_guide_character_art.py --plan                      # refs + prompts, no calls
    python3 scripts/paint_guide_character_art.py --only 02-race-selection    # one paid call (~$0.15)
    python3 scripts/paint_guide_character_art.py --finish 02-race-selection=3  # take try 3 -> guide/art/

Needs a checkout of wattgod/gravel-god-character (default ~/gravel-god-character, or $GG_CHARACTER_RIG
pointing at its rig/ folder) with `python3 refpack.py` run once, and $REPLICATE_API_TOKEN in the
environment. Every call goes through that repo's spend ledger and $40 cap (gen_head_art.run), and lands in
rig/assets/head_art/raw/guide-v67p-<slug>-<try>.png. Check each try against docs/CHARACTER.md before
--finish: his face matches the head cards, teal-stripe socks, slim build, and any stud the model put in
his (visible) right ear is marked in STUDS so --finish paints it out.
"""
import argparse, io, math, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RIG = Path(os.environ.get('GG_CHARACTER_RIG', Path.home() / 'gravel-god-character' / 'rig'))
REFPACK = RIG / 'out' / 'refpack'
RAW = RIG / 'assets' / 'head_art' / 'raw'          # gitignored in the character repo
BIKE_SHEET = RIG.parent / 'docs' / 'img' / 'gravel-god-bike.png'
BASE_REF = '199fca509b12086f625f8cc3abc217a15a52591e'   # last main commit with the painted originals
OUT = ROOT / 'guide' / 'art'

EDIT = (
    "Image 1 is a finished illustration in which the main man's head is hidden under a flat grey box. Paint "
    "his head in place of the box. It is the head of the fixed cartoon character in images 2 and 3: copy his "
    "face shape, eyebrows, eyes, nose, skin tone, hair and mustache exactly from images 2 and 3, painted in "
    "image 1's style and light. {head} Join the head naturally to his neck and shoulders, at the size that "
    "fits his body, a little large for cartoon proportions. Clean-shaven apart from a big dark-brown "
    "handlebar mustache with tips that curl up; glossy slicked-back longer dark-brown hair, no parting, no "
    "fringe, a slight outward flick at the nape. Earring: a small diamond stud in his LEFT earlobe only; his "
    "right ear has no earring, so if only his right ear shows, draw no earring at all. His body and clothes "
    "match image 4: a slim cyclist with narrow shoulders, skinny bare arms and thin ripped legs, never "
    "bulky; plain white crew-neck tee with no logo; tight denim jorts with a frayed hem at mid-thigh; tall "
    "white socks with a teal stripe; brown shoes with gum soles. His bike is the bike in image 5: matte black "
    "carbon gravel bike with gold-flake and teal pinstripe accents, no cables, knobby tyres, two black "
    "bottles, no bags. Keep everything else in image 1 exactly as it is: the setting, every prop, every "
    "other person, his pose, the composition, the camera, the light and the colours. No grey box left, no "
    "text, no logos, no watermark, no border.")

# slug -> (expression of the head cards, body card, how his head sits, head box as fractions x0, y0, x1, y1)
SCENES = {
    '00-cover': ('grin', 'street_ride_cruise_psi045_eye',
                 'Three-quarter view facing the right of the picture, looking ahead along the road, grinning.',
                 (0.335, 0.03, 0.44, 0.22)),
    '01-what-is-gravel': ('smile', 'street_ride_cruise_psi045_eye',
                          'Three-quarter view facing the right, drinking from the white paper cup at his mouth. '
                          'He is the only man with a mustache.', (0.44, 0.105, 0.525, 0.23)),
    '02-race-selection': ('thinking', 'street_body_psi045_eye',
                          'Three-quarter view facing the right, looking down at the maps, chin resting on his '
                          'hand, thinking.', (0.33, 0.055, 0.455, 0.235)),
    '03-training-fundamentals': ('focused', 'street_ride_cruise_psi045_eye',
                                 'Three-quarter view facing the right, looking ahead at the screen, focused.',
                                 (0.365, 0.045, 0.485, 0.205)),
    '04-workout-execution': ('focused', 'street_ride_standing_climb_psi045_eye',
                             'Three-quarter view facing the right, head down, looking up the climb, focused '
                             'and working hard.', (0.54, 0.0, 0.67, 0.20)),
    '05-nutrition': ('smile', 'street_body_psi045_eye',
                     'Three-quarter view facing the right toward the volunteer, smiling, mid-bite of a banana.',
                     (0.43, 0.03, 0.53, 0.18)),
    '06-mental': ('focused', 'street_ride_drops_psi045_eye',
                  'Three-quarter view facing the right, eyes on the road ahead, focused, hair blown by the wind.',
                  (0.355, 0.115, 0.45, 0.25)),
    '07-race-week': ('smile', 'street_body_psi090_eye',
                     'He lies on his back, head on the cushion and hands behind his head, seen from the side, '
                     'face turned up, relaxed and smiling.', (0.20, 0.405, 0.325, 0.54)),
    '08-post-race': ('grin', 'street_body_psi045_eye',
                     'Three-quarter view facing the right, grinning, tired and happy, a little mud on his face.',
                     (0.325, 0.17, 0.44, 0.33)),
}
AR = {'00-cover': '16:9'}
SIZE = {'00-cover': (1920, 1080)}
PAD = 0.01                      # grey box margin around the head box, as a fraction of the image
# Studs the model painted in his right ear, per chosen try: (x, y, radius), as fractions of the image width/height.
STUDS = {
    '02-race-selection': [(0.364, 0.176, 0.0035)],
    '03-training-fundamentals': [(0.414, 0.1485, 0.0032)],
    '04-workout-execution': [(0.5815, 0.1035, 0.0025)],
    '05-nutrition': [(0.450, 0.1325, 0.002)],
    '08-post-race': [(0.356, 0.279, 0.0035)],
}


def card(stem):
    p = REFPACK / stem.split('_')[1] / f'{stem}_white.png'
    if not p.is_file():
        sys.exit(f'Missing reference card {p}. Run `python3 refpack.py` in {RIG}.')
    return p


def base(slug, tmp):
    """The pre-#534 painting with his head under a flat grey box."""
    from PIL import Image, ImageDraw
    p = tmp / f'masked-{slug}.png'
    webp = subprocess.run(['git', 'show', f'{BASE_REF}:guide/art/gg-art-{slug}-2x.webp'], cwd=ROOT,
                          capture_output=True, check=True).stdout
    im = Image.open(io.BytesIO(webp)).convert('RGB')
    x0, y0, x1, y1 = SCENES[slug][3]
    w, h = im.size
    ImageDraw.Draw(im).rectangle([max(0, x0 - PAD) * w, max(0, y0 - PAD) * h, min(1, x1 + PAD) * w,
                                  min(1, y1 + PAD) * h], fill='#808080')
    im.save(p)
    return p


def plan(slug, tmp):
    face, body, head, _ = SCENES[slug]
    refs = [base(slug, tmp), card(f'street_head_{face}_psi045_eye'), card(f'street_head_{face}_psi090_eye'),
            card(body), BIKE_SHEET]
    return refs, EDIT.format(head=head)


def remove_right_ear_studs(im, slug):
    """Every scene shows his RIGHT ear, which has no stud, and the model paints one there anyway. Fill each
    stud marked in STUDS with the skin around it. (fix_studs.py's blob search missed lavender studs and took
    his teeth in 07, so the studs are marked by hand per try.)"""
    from PIL import Image, ImageDraw, ImageFilter
    w, h = im.size
    for fx, fy, fr in STUDS.get(slug, ()):
        cx, cy, r = fx * w, fy * h, fr * w
        ring = [im.getpixel((int(cx + 1.8 * r * math.cos(t / 16 * math.pi)), int(cy + 1.8 * r * math.sin(t / 16 * math.pi))))
                for t in range(32)]
        med = tuple(sorted(c[i] for c in ring)[len(ring) // 2] for i in range(3))
        ImageDraw.Draw(im).ellipse([cx - 1.25 * r, cy - 1.25 * r, cx + 1.25 * r, cy + 1.25 * r], fill=med)
        box = tuple(int(v) for v in (cx - 2.2 * r, cy - 2.2 * r, cx + 2.2 * r, cy + 2.2 * r))
        mask = Image.new('L', (box[2] - box[0], box[3] - box[1]), 0)
        ImageDraw.Draw(mask).ellipse([0.4 * r, 0.4 * r, 4.0 * r, 4.0 * r], fill=255)
        im.paste(im.crop(box).filter(ImageFilter.GaussianBlur(r * 0.5)), box[:2], mask.filter(ImageFilter.GaussianBlur(r * 0.4)))
    return len(STUDS.get(slug, ()))


def finish(slug, n):
    from PIL import Image
    src = RAW / f'guide-v67p-{slug}-{n}.png'
    W, H = SIZE.get(slug, (1920, 1280))
    im = Image.open(src).convert('RGB')
    print(f'{slug}: studs removed from his right ear: {remove_right_ear_studs(im, slug)}')
    r = max(W / im.width, H / im.height)                     # cover-fit, then centre-crop to the exact size
    im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((x, y, x + W, y + H))
    OUT.mkdir(parents=True, exist_ok=True)
    b = OUT / f'gg-art-v67-{slug}'
    im.save(f'{b}-2x.webp', quality=86, method=6)
    im.resize((W // 2, H // 2), Image.LANCZOS).save(f'{b}-1x.webp', quality=86, method=6)
    print(f'{b}-{{1x,2x}}.webp  <- {src.name}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', nargs='*', choices=sorted(SCENES))
    ap.add_argument('--plan', action='store_true', help='print refs and prompts; no paid calls')
    ap.add_argument('--finish', nargs='*', metavar='SLUG=TRY', help='copy chosen tries into guide/art/')
    a = ap.parse_args()
    if a.finish:
        for s in a.finish:
            slug, n = s.split('=')
            finish(slug, n)
        return
    tmp = RAW / 'guide-base'
    tmp.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(RIG))
    for slug in a.only or SCENES:
        refs, prompt = plan(slug, tmp)
        if a.plan:
            print(f'\n== {slug}\n' + '\n'.join(f'  image {i + 1}: {r}' for i, r in enumerate(refs)) + f'\n  {prompt}')
            continue
        import gen_head_art
        n = 1 + sum(1 for _ in RAW.glob(f'guide-v67p-{slug}-*.png'))
        gen_head_art.run(prompt, [str(r) for r in refs], res='2K', ar=AR.get(slug, '3:2'), tag=f'guide-v67p-{slug}-{n}')


if __name__ == '__main__':
    main()
