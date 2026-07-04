#!/usr/bin/env python3
"""Social Engine — database-driven post candidates + neo-brutalist cards.

Phase 1 of docs/specs/social-engine.md: generates the day's post candidates
(countdown window-entries, score reveals) with per-brand text and 1080x1350
Instagram cards rendered from brand tokens. No posting — output goes to
data/social-queue/ (+ cards) for the publish/approval layers (Phase 3).

The automation boundary: everything generated here is DATA in brand voice —
facts dominate, templates carry the tone. Opinion content never comes from
this script.

Usage:
    python3 scripts/social_engine.py --countdown             # today's window entries
    python3 scripts/social_engine.py --card unbound-200      # render one card
    python3 scripts/social_engine.py --score-reveal scratch-ankle-gravel
    python3 scripts/social_engine.py --preview N             # N sample cards → ~/Downloads
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

GRAVEL_ROOT = Path(__file__).resolve().parent.parent
ROAD_ROOT = GRAVEL_ROOT.parent / "road-race-automation"
QUEUE_DIR = GRAVEL_ROOT / "data" / "social-queue"
CARD_DIR = GRAVEL_ROOT / "data" / "social-cards"

sys.path.insert(0, str(GRAVEL_ROOT / "scripts"))
from generate_race_dates import parse_date_specific  # noqa: E402

# Brand palettes — mirrors tokens.css (never invent hex; these are the
# documented brand values). GG warm paper / brown / teal; RL newsprint mono.
BRANDS = {
    "gravel": {
        "root": GRAVEL_ROOT, "site": "https://gravelgodcycling.com",
        "label": "GRAVEL GOD CYCLING", "rating_key": "gravel_god_rating",
        "bg": "#f5efe6", "ink": "#59473c", "accent": "#1A8A82",
        "chip_bg": "#59473c", "chip_ink": "#f5efe6",
        "tier_names": {1: "TIER 1", 2: "TIER 2", 3: "TIER 3", 4: "TIER 4"},
        "utm": "utm_source=social&utm_medium=organic&utm_campaign=db_posts",
    },
    "road": {
        "root": ROAD_ROOT, "site": "https://roadielabs.com",
        "label": "ROADIE LABS", "rating_key": "fondo_rating",
        "bg": "#f5f5f0", "ink": "#1a1a1a", "accent": "#1a1a1a",
        "chip_bg": "#1a1a1a", "chip_ink": "#f5f5f0",
        "tier_names": {1: "ELITE", 2: "CONTENDER", 3: "RISING", 4: "LOCAL"},
        "utm": "utm_source=social&utm_medium=organic&utm_campaign=db_posts",
    },
}

W, H = 1080, 1350  # IG portrait


def _font(mono: bool, size: int) -> ImageFont.FreeTypeFont:
    """System stand-ins for brand fonts (see spec: swap TTFs before launch)."""
    candidates = (
        ["/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
         "/System/Library/Fonts/Supplemental/Courier New.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"]
        if mono else
        ["/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
         "/System/Library/Fonts/Supplemental/Georgia.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"])
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def load_race(slug: str, brand: str) -> dict | None:
    p = BRANDS[brand]["root"] / "race-data" / f"{slug}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())["race"]
    rating = d.get(BRANDS[brand]["rating_key"]) or {}
    vitals = d.get("vitals") or {}
    iso = parse_date_specific(vitals.get("date_specific"))
    return {
        "slug": slug, "name": d.get("name", slug),
        "score": rating.get("overall_score"), "tier": rating.get("tier"),
        "date_iso": iso,
        "weeks_out": round((date.fromisoformat(iso) - date.today()).days / 7, 1) if iso else None,
        "distance": vitals.get("distance_mi"), "elevation": vitals.get("elevation_ft"),
        "location": vitals.get("location", ""),
    }


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def render_card(race: dict, brand: str, kind: str = "countdown") -> Path:
    """1080x1350 neo-brutalist card: thick border, big score, tier chip,
    countdown line. No border-radius, no shadows — per brand rules."""
    b = BRANDS[brand]
    img = Image.new("RGB", (W, H), b["bg"])
    d = ImageDraw.Draw(img)
    ink, margin = b["ink"], 56

    # frame (3px double border = neo-brutalist)
    for off in (0, 10):
        d.rectangle([margin - off if off else margin, margin - off if off else margin,
                     W - margin + off if off else W - margin,
                     H - margin + off if off else H - margin],
                    outline=ink, width=4)

    # header label
    d.text((margin + 40, margin + 36), b["label"], font=_font(True, 34), fill=ink)
    d.line([margin + 40, margin + 96, W - margin - 40, margin + 96], fill=ink, width=3)

    # race name (serif, wrapped)
    name_font = _font(False, 88)
    y = margin + 150
    for line in _wrap(d, race["name"].upper(), name_font, W - 2 * margin - 80)[:3]:
        d.text((margin + 40, y), line, font=name_font, fill=ink)
        y += 100

    # giant score
    score = race.get("score")
    if score is not None:
        d.text((margin + 40, y + 40), str(score), font=_font(False, 330), fill=ink)
        quip = race.get("quip")
        if quip:
            qf = _font(False, 44)
            qy = y + 400
            for line in _wrap(d, f"\u201c{quip}\u201d", qf, W - 2 * margin - 100)[:4]:
                d.text((margin + 50, qy), line, font=qf, fill=ink)
                qy += 56
        else:
            d.text((margin + 60, y + 380), "/ 100 · SAME RULER AS EVERY RACE WE RATE",
                   font=_font(True, 26), fill=ink)

    # tier chip
    tier = race.get("tier")
    if tier:
        chip = f' {b["tier_names"].get(tier, f"TIER {tier}")} '
        cf = _font(True, 40)
        cw = d.textlength(chip, font=cf)
        cx, cy = W - margin - 40 - cw - 24, margin + 150
        d.rectangle([cx, cy, cx + cw + 24, cy + 64], fill=b["chip_bg"])
        d.text((cx + 12, cy + 10), chip, font=cf, fill=b["chip_ink"])

    # countdown / footer band
    band_y = H - margin - 220
    d.line([margin + 40, band_y, W - margin - 40, band_y], fill=ink, width=3)
    if kind == "countdown" and race.get("weeks_out") is not None:
        big = f"{race['weeks_out']:.0f} WEEKS OUT"
        sub = ("THE FULL TRAINING WINDOW IS OPEN" if race["weeks_out"] >= 12
               else "SHORT RUNWAY. STRUCTURE WHAT'S LEFT.")
    else:
        big = f"SCORED {score}/100"
        sub = "EVERY RACE. SAME 15 CRITERIA. IN PUBLIC."
    d.text((margin + 40, band_y + 28), big, font=_font(True, 64), fill=b["accent"])
    d.text((margin + 40, band_y + 116), sub, font=_font(True, 28), fill=ink)
    d.text((margin + 40, H - margin - 60),
           b["site"].replace("https://", "") + "  ·  the full profile is free",
           font=_font(True, 26), fill=ink)

    CARD_DIR.mkdir(parents=True, exist_ok=True)
    out = CARD_DIR / f"{date.today().isoformat()}-{brand}-{race['slug']}-{kind}.png"
    img.save(out)
    return out


def post_text(race: dict, brand: str, kind: str) -> dict:
    """Per-platform text in brand voice. Facts dominate; templates carry tone."""
    b = BRANDS[brand]
    url = f"{b['site']}/race/{race['slug']}/?{b['utm']}"
    w = race.get("weeks_out")
    if brand == "gravel":
        if kind == "countdown":
            x = (f"{race['name']} is {w:.0f} weeks out. That's the full training "
                 f"window — the weeks you can't get back later. We scored it "
                 f"{race['score']}/100. Course, pacing, where the day actually "
                 f"gets decided: {url}")
            ig = (f"{race['name']}: {w:.0f} weeks out.\n\nThe base-building window "
                  f"is open — it's the one part of race prep you can't cram later. "
                  f"We scored this one {race['score']}/100 on the same fifteen "
                  f"criteria as every race in the database, in public, including "
                  f"the insulting scores.\n\nFull profile free — link in bio.")
        else:
            x = (f"We gave {race['name']} a {race['score']}/100. Not an insult — "
                 f"a ruler. Every race, same fifteen criteria, in public: {url}")
            ig = (f"{race['name']}: {race['score']}/100.\n\nA rating system is "
                  f"only useful if it's willing to be rude. Same ruler for every "
                  f"race in the database — the 97s and the 36s alike.\n\n"
                  f"Full breakdown free — link in bio.")
    else:
        if kind == "countdown":
            x = (f"{race['name']}: {w:.0f} weeks out. The full training window. "
                 f"Scored {race['score']}/100 on the published 15-criteria "
                 f"rubric. Profile: {url}")
            ig = (f"{race['name']} — {w:.0f} weeks out.\n\nBase does not "
                  f"compress. The weeks lost to waiting come off the front of "
                  f"a plan, and the front is where the aerobic volume lives.\n\n"
                  f"Scored {race['score']}/100. Rubric public. Link in bio.")
        else:
            x = (f"{race['name']}: {race['score']}/100. Same ruler as every "
                 f"race we rate. The rubric is public: {url}")
            ig = (f"{race['name']}: {race['score']}/100.\n\nA database where "
                  f"everything scores 85 is a brochure. Rubric public — check "
                  f"our work. Link in bio.")
    return {"x": x, "instagram_caption": ig, "substack_note": x}


def countdown_candidates(window: tuple[float, float] = (15.5, 16.49)) -> list[dict]:
    """Races entering the 16-week window today-ish, both brands."""
    out = []
    for brand, b in BRANDS.items():
        dates = json.loads((b["root"] / "web" / "race-dates.json").read_text())
        for slug, iso in dates.items():
            wk = (date.fromisoformat(iso) - date.today()).days / 7
            if window[0] <= wk <= window[1]:
                race = load_race(slug, brand)
                if race and race.get("score"):
                    race["brand"] = brand
                    out.append(race)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--countdown", action="store_true")
    ap.add_argument("--card", metavar="SLUG")
    ap.add_argument("--score-reveal", metavar="SLUG")
    ap.add_argument("--brand", choices=["gravel", "road"], default="gravel")
    ap.add_argument("--preview", type=int, metavar="N", help="render N sample cards to ~/Downloads")
    args = ap.parse_args()

    if args.preview:
        import random
        prev = Path.home() / "Downloads" / "social-cards-preview"
        prev.mkdir(parents=True, exist_ok=True)
        for brand in BRANDS:
            slugs = [p.stem for p in (BRANDS[brand]["root"] / "race-data").glob("*.json")]
            random.shuffle(slugs)
            done = 0
            for slug in slugs:
                r = load_race(slug, brand)
                if r and r.get("score") and r.get("weeks_out") and r["weeks_out"] > 0:
                    card = render_card(r, brand, "countdown" if done % 2 == 0 else "score")
                    dest = prev / card.name
                    dest.write_bytes(card.read_bytes())
                    print(f"  {dest}")
                    done += 1
                    if done >= args.preview:
                        break
        return 0

    if args.card or args.score_reveal:
        slug = args.card or args.score_reveal
        kind = "countdown" if args.card else "score"
        race = load_race(slug, args.brand)
        if not race:
            print(f"no race {slug!r} in {args.brand}")
            return 1
        card = render_card(race, args.brand, kind)
        texts = post_text(race, args.brand, kind)
        print(f"card:  {card}")
        print(f"x:     {texts['x']}")
        return 0

    if args.countdown:
        cands = countdown_candidates()
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        queue = []
        for race in cands:
            card = render_card(race, race["brand"], "countdown")
            queue.append({"kind": "countdown", "brand": race["brand"],
                          "slug": race["slug"], "race": race["name"],
                          "card": str(card),
                          "text": post_text(race, race["brand"], "countdown"),
                          "auto_publish": True})
        qf = QUEUE_DIR / f"{date.today().isoformat()}.json"
        qf.write_text(json.dumps(queue, indent=1))
        print(f"{len(queue)} candidate(s) → {qf}")
        for q in queue:
            print(f"  [{q['brand']}] {q['race']} — {q['card']}")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
