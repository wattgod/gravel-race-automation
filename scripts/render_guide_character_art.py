#!/usr/bin/env python3
"""Render the Gravel Handbook chapter scenes from the Gravel God character rig (v6.2-v6.7 look).

Matti, 2026-11-01: "6.2-6.7 is where we're at. Redo all images on website with wrong version of
character." These scenes replace the painted image-generator art that used to sit in guide/art/.

    python3 scripts/render_guide_character_art.py                # all nine -> guide/art/
    python3 scripts/render_guide_character_art.py --only 08-post-race --out /tmp/x

Needs a checkout of wattgod/gravel-god-character (default ~/gravel-god-character, or
$GG_CHARACTER_RIG pointing at its rig/ folder) plus rsvg-convert and Pillow. No paid image calls.

Framing: chapter art is 3:2 but the page crops it to 21:9 at 38% from the top on wide screens,
so the character stays inside rows ~14%..78%. The cover is 16:9, cropped to 2:1 on wide screens
and 4:3 (from 30% across) on phones, with the title box over its lower left, so he rides on the right.
"""
import argparse, io, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RIG = Path(os.environ.get('GG_CHARACTER_RIG', Path.home() / 'gravel-god-character' / 'rig'))
if not (RIG / 'gg_rig3d.py').is_file():
    sys.exit(f'Character rig not found at {RIG}. Clone wattgod/gravel-god-character or set GG_CHARACTER_RIG.')
sys.path.insert(0, str(RIG))
_cwd = os.getcwd(); os.chdir(RIG)
from gg_common import _fontconfig                     # noqa: E402
_fontconfig()
import gg_character                                    # noqa: E402
gg_character.set_outfit('street')
from gg_character import DEFS, CHARACTER_VERSION       # noqa: E402
from gg_rig3d import Bike, RideBody                    # noqa: E402
from gg_poses import RIDE_POSES                        # noqa: E402
from gg_offbike import StandBody, OFFBIKE_POSES        # noqa: E402
import gg_scene                                        # noqa: E402
from gg_scene import World, Path as Road, Sign, Cone, Tree, place_bike_on_path, follow_cam, compose  # noqa: E402
os.chdir(_cwd)
from PIL import Image                                  # noqa: E402

# Chapter 6 (mental toughness) rides under a storm sky; colours only, the character is untouched.
STORM = dict(sky_top='#7f7c79', sky_hz='#cbc2b2', sun='none', sun_ring='none',
             hill_far='#a9a294', hill_mid='#b6ad9b', hill_near='#c2b7a1', haze='#d9d0bf',
             ground='#d6cab0', ground_lt='#e0d6c0', ground_dk='#c6b896')


def world(profile=None, seed=2, trees=(), start=(-34.0, 0.0)):
    """A straight gravel road along +x. trees: (arc length, sideways offset) pairs; + offset is the
    far side of the road from the camera, so they stand behind him."""
    env = World(Road([('straight', 70)], start=start), profile=profile, disc=18, seed=seed)
    for i, (s, off) in enumerate(trees):
        env.add(Tree(env.path.at(s, off), h=3.4 + (i % 3) * 0.3, seed=i + seed * 10))
    env.scatter_rocks(n=16, seed=seed)
    return env


def facing(psi):
    """Sign yaw so its face points at a camera at heading psi (0 = his right side, 90 = in front)."""
    return psi - 90


def ride(name, face, s=34.0, profile=None, props=(), trees=(), crank=-35, seed=2):
    env = world(profile, seed=seed, trees=trees)
    bk = place_bike_on_path(env, s, speed=7)
    bk.update(crank=crank)
    bike = Bike(**bk)
    pose = dict(RIDE_POSES[name]['pose']); pose['face'] = face
    body = RideBody(bike, pose)
    body.face = face
    for p in props:
        env.add(p(env))
    return env, [bike], [body], [bk], body.hip


def stand(pose_name, face, bike=True, props=(), trees=(), seed=3):
    env = world(seed=seed, start=(-34.0, -2.6), trees=trees)
    b = OFFBIKE_POSES[pose_name]['build'](0.0)[0][0]
    P = dict(b.P); P['face'] = face
    body = StandBody(P)
    bikes = [Bike(x=-0.35, y=1.35, roll=10, crank=-60)] if bike else []   # on his left, away from the camera
    for p in props:
        env.add(p(env))
    return env, bikes, [body], [], body.hip


# slug -> (builder, camera heading relative to the road, elevation, px per metre, hip position on canvas)
SCENES = {
    '00-cover': (lambda: ride('attack', 'grin', trees=((44, 9), (47, 11))), 52, 5, 380, (0.62, 0.50)),
    '01-what-is-gravel': (lambda: ride('point', 'grin', props=(
        lambda e: Sign(e.path.at(33.3, 3.3), facing(40) - 10, lines=('PAVEMENT', 'ENDS'), post=1.25),)), 40, 5, 420, (0.40, 0.44)),
    '02-race-selection': (lambda: stand('phone', 'thinking', trees=((40, 9),), props=(
        lambda e: Sign((-2.8, 1.6), facing(40) + 10, lines=('UNBOUND', 'MID SOUTH', 'SBT GRVL'), post=1.25),)), 40, 7, 400, (0.46, 0.46)),
    '03-training-fundamentals': (lambda: ride('seated_climb', 'focused', trees=((25, 10), (44, 12)),
                                              profile=[('rollers', 20, 60, 0.4, 14)]), 30, 6, 420, (0.50, 0.44)),
    '04-workout-execution': (lambda: ride('standing_climb', 'grimace', crank=-80, seed=7, trees=((46, 10),),
                                          profile=[('climb', 20, 60, 0.10)]), 18, 3, 420, (0.48, 0.42)),
    '05-nutrition': (lambda: stand('eat', 'content', props=(
        lambda e: Sign((-2.6, 1.8), facing(35) + 10, lines=('AID', 'STATION', 'MILE 62'), post=1.25),
        lambda e: Cone((3.0, -1.2)),)), 35, 7, 400, (0.46, 0.46)),
    '06-mental': (lambda: ride('drops', 'focused', seed=5), 40, 4, 420, (0.48, 0.44)),
    '07-race-week': (lambda: stand('sit', 'content', trees=((38, 9),)), 40, 9, 420, (0.46, 0.58)),
    '08-post-race': (lambda: ride('no_hands', 'laugh', props=(
        lambda e: Sign(e.path.at(32.8, 3.1), facing(48) - 10, lines=('FINISH',), post=1.25),
        lambda e: Cone(e.path.at(37.5, 2.5)), lambda e: Cone(e.path.at(40.5, 2.5)))), 48, 5, 400, (0.48, 0.47)),
}


def render(slug, out_dir):
    build, rel, elev, k, pos = SCENES[slug]
    W, H = (1920, 1080) if slug == '00-cover' else (1920, 1280)
    saved = dict(gg_scene.PAL)
    if slug == '06-mental':
        gg_scene.PAL.update(STORM)
    try:
        os.chdir(RIG)
        env, bikes, bodies, bike_kws, hip = build()
        yaw = bike_kws[0]['yaw'] if bike_kws else 0.0
        cam = follow_cam(hip, (pos[0] * W, pos[1] * H), yaw + rel, elev, k)
        inner = compose(cam, W, H, env, bikes=bikes, bodies=bodies, focus=(hip[0], hip[1]), bike_kws=bike_kws,
                        keep_clear=(hip, 0.42 * k))
    finally:
        os.chdir(_cwd); gg_scene.PAL.clear(); gg_scene.PAL.update(saved)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
           f'<defs>{DEFS}</defs>{inner}</svg>')
    png = subprocess.run(['rsvg-convert', '-w', str(W), '-h', str(H)], input=svg.encode(), capture_output=True,
                         check=True, cwd=RIG).stdout
    im = Image.open(io.BytesIO(png)).convert('RGB')
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / f'gg-art-v67-{slug}'
    im.save(f'{base}-2x.webp', quality=86, method=6)
    im.resize((W // 2, H // 2), Image.LANCZOS).save(f'{base}-1x.webp', quality=86, method=6)
    print(f'{base}-{{1x,2x}}.webp')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(ROOT / 'guide' / 'art'))
    ap.add_argument('--only', nargs='*', choices=sorted(SCENES))
    a = ap.parse_args()
    print(f'rig {CHARACTER_VERSION}')
    for slug in a.only or SCENES:
        render(slug, Path(a.out))


if __name__ == '__main__':
    main()
