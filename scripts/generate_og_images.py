#!/usr/bin/env python3
"""
Generate Open Graph share cards for race profile pages -> og/{slug}.jpg.

The card is the race page's hero, at share-card scale: tier / series kicker,
race name, location + date, the editorial verdict, and the Lab Score. Every
value comes from generate_neo_brutalist.load_race_data — the same normalizer
that renders /race/{slug}/ — so the card can't disagree with the page. (The
Feb-2026 cards computed their own score and were never regenerated: Unbound
200's card said 80/100 while its page said 96.)

Visual system: scripts/og_brand.py (2026 brand — paper ground, GG mark).

Usage:
    python scripts/generate_og_images.py unbound-200
    python scripts/generate_og_images.py --all
    python scripts/generate_og_images.py --all --output-dir wordpress/output/og
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

import og_brand as og  # noqa: E402
from generate_neo_brutalist import (  # noqa: E402
    DISCIPLINE_LABELS, REMOVED_FABRICATED_SLUGS, load_race_data,
)

SCORE_COL_W = 250
LEFT_W = og.W - 2 * og.MARGIN - SCORE_COL_W - 64
CONTENT_TOP = 176
CONTENT_BOTTOM = og.H - 44

_YEAR_FIRST = re.compile(r"^(\d{4}):\s*([A-Z][a-z]+\.?\s+\d{1,2})\b")
_MONTH_FIRST = re.compile(r"^([A-Z][a-z]+\.?\s+\d{1,2}),\s*(\d{4})\b")


def short_date(date_specific: str) -> str:
    """'2027: June 5; final route pending' -> 'June 5, 2027'. Anything that
    isn't a concrete date (TBD, DROPPED, CANCELLED...) returns '' so the card
    shows location only rather than a status sentence cut in half."""
    ds = (date_specific or "").strip()
    m = _YEAR_FIRST.match(ds)
    if m:
        return f"{m.group(2)}, {m.group(1)}"
    m = _MONTH_FIRST.match(ds)
    if m:
        return f"{m.group(1)}, {m.group(2)}"
    return ""


def verdict_of(rd: dict) -> str:
    """Same precedence as generate_neo_brutalist.build_hero."""
    return (
        rd.get("final_verdict", {}).get("one_liner", "").strip()
        or rd.get("biased_opinion", {}).get("summary", "").strip()
        or rd.get("biased_opinion", {}).get("bottom_line", "").strip()
        or rd.get("final_verdict", {}).get("should_you_race", "").strip()
    )


def _fit_one_line(draw, text: str, font, max_w: int, tracking: int = 0) -> str:
    if og.tracked_w(draw, text, font, tracking) <= max_w:
        return text
    while text and og.tracked_w(draw, text + "…", font, tracking) > max_w:
        text = text[:-1]
    return text.rstrip(" ,·") + "…"


def _clamp_lines(draw, text: str, font, max_w: int, max_lines: int) -> list[str]:
    """Wrap; if it overflows, end the last kept line on a word + ellipsis."""
    try:
        return og.wrap(draw, text, font, max_w, max_lines)
    except og.OGCardError:
        lines = og.wrap(draw, text, font, max_w, 99)[:max_lines]
        last = lines[-1].split()
        while last and og.text_w(draw, " ".join(last) + "…", font) > max_w:
            last.pop()
        lines[-1] = " ".join(last).rstrip(",;:—-") + "…"
        return lines


def generate_og_image(rd: dict, output_path: Path) -> Path:
    img, draw = og.new_card()

    # ── Kicker: TIER n · DISCIPLINE · SERIES (as the page hero) ──
    parts = [(rd["tier_label"], og.SEC_BROWN)]
    discipline = rd.get("discipline", "gravel")
    if discipline != "gravel":
        parts.append((DISCIPLINE_LABELS.get(discipline, discipline.upper()), og.DARK_BROWN))
    series = rd.get("series") or {}
    if series.get("id") and series.get("name"):
        parts.append((f"{series['name']} SERIES", og.TEAL))
    kicker_font = og.mono(18, bold=True)
    while len(parts) > 1 and og.tracked_w(
            draw, " · ".join(p[0].upper() for p in parts), kicker_font, 4) + 28 > LEFT_W:
        parts.pop()  # drop series first, then discipline, never the tier
    og.kicker(draw, (og.MARGIN, CONTENT_TOP), parts, size=18)

    # ── Vitals + verdict, sized so the whole stack fits ──
    vitals = rd.get("vitals", {})
    vit_font = og.mono(19, bold=True)
    loc = vitals.get("location", "").upper()
    # A race between editions says so (the page's "taking a break" strip)
    # instead of showing a date.
    brk = (rd.get("taking_a_break") or {}).get("label", "")
    date = (brk or short_date(vitals.get("date_specific", ""))).upper()
    # The date stays whole; a long location gives way first.
    date_part = f" · {date}" if (loc and date) else date
    loc = _fit_one_line(draw, loc, vit_font,
                        LEFT_W - og.tracked_w(draw, date_part, vit_font, 2) - 2,
                        tracking=2) if loc else ""
    vit = loc + date_part
    verdict = verdict_of(rd)

    # Layouts, largest type first: A/B keep the name at display size, C/D
    # shrink it for long two-line names. Take the first that shows the whole
    # verdict without shrinking the name below C; failing that, the one that
    # shows the most verdict at the largest name (the verdict then ends in an
    # ellipsis). The name always outranks the verdict at thumbnail size.
    combos = {"A": ((84, 76), 30, 2), "B": ((84, 76), 27, 3),
              "C": ((68, 60), 27, 3), "D": ((56, 50), 24, 3)}
    fits = {}
    for key, (name_sizes, v_size, v_lines) in combos.items():
        try:
            name_font, name_lines = og.fit_headline(draw, rd["name"], LEFT_W,
                                                    sizes=name_sizes, max_lines=2)
        except og.OGCardError:
            continue
        v_font = og.serif(v_size, 400)
        v_wrapped = _clamp_lines(draw, verdict, v_font, LEFT_W, v_lines) if verdict else []
        name_lh = round(name_font.size * 1.08)
        height = (36 + len(name_lines) * name_lh + 18 + (30 if vit else 0)
                  + ((26 + 28 + len(v_wrapped) * round(v_size * 1.38)) if v_wrapped else 0))
        if CONTENT_TOP + height <= CONTENT_BOTTOM:
            whole = not (v_wrapped and v_wrapped[-1].endswith("…"))
            fits[key] = ((name_font, name_lines, name_lh, v_font, v_wrapped), whole)
    layout = next((fits[k][0] for k in "ABC" if k in fits and fits[k][1]), None)
    layout = layout or next((fits[k][0] for k in "BCAD" if k in fits), None)
    if layout is None:
        raise og.OGCardError(f"{rd.get('slug')}: content does not fit the card")
    name_font, name_lines, name_lh, v_font, v_wrapped = layout

    y = CONTENT_TOP + 36
    for line in name_lines:
        draw.text((og.MARGIN, y), line, font=name_font, fill=og.DARK_BROWN)
        y += name_lh
    y += 18
    if vit:
        og.draw_tracked(draw, (og.MARGIN, y), vit, vit_font, og.SEC_BROWN, 2)
        y += 30
    if v_wrapped:
        y += 26
        og.draw_tracked(draw, (og.MARGIN, y), "VERDICT", og.mono(16, bold=True), og.GOLD, 4)
        y += 28
        for line in v_wrapped:
            draw.text((og.MARGIN, y), line, font=v_font, fill=og.DARK_BROWN)
            y += round(v_font.size * 1.38)

    # ── Lab Score column ──
    col_x = og.W - og.MARGIN - SCORE_COL_W
    draw.rectangle([col_x - 32, CONTENT_TOP + 4, col_x - 31, CONTENT_BOTTOM - 8], fill=og.TAN)
    score = str(rd["overall_score"])
    s_font = og.serif(168, 700)
    l, t, r, b = draw.textbbox((0, 0), score, font=s_font)
    sx = col_x + (SCORE_COL_W - (r - l)) // 2 - l
    draw.text((sx, CONTENT_TOP + 40 - t), score, font=s_font, fill=og.GOLD)
    lab_font = og.mono(18, bold=True)
    lw = og.tracked_w(draw, "LAB SCORE", lab_font, 4)
    og.draw_tracked(draw, (col_x + (SCORE_COL_W - lw) // 2, CONTENT_TOP + 40 + (b - t) + 22),
                    "LAB SCORE", lab_font, og.SEC_BROWN, 4)

    return og.save(img, output_path)


def main():
    parser = argparse.ArgumentParser(description="Generate OG images for gravel race profiles")
    parser.add_argument("slug", nargs="?", help="Race slug (e.g., unbound-200)")
    parser.add_argument("--all", action="store_true", help="Generate for all races")
    parser.add_argument("--data-dir", type=Path, help="Race data directory")
    parser.add_argument("--output-dir", type=Path, help="Output directory for images")
    args = parser.parse_args()

    if not args.slug and not args.all:
        parser.error("Provide a race slug or --all")

    data_dir = args.data_dir or og.REPO_ROOT / "race-data"
    if not data_dir.exists():
        print(f"ERROR: Data directory not found: {data_dir}")
        sys.exit(1)
    output_dir = args.output_dir or og.REPO_ROOT / "wordpress" / "output" / "og"

    slugs = ([f.stem for f in sorted(data_dir.glob("*.json"))
              if f.stem not in REMOVED_FABRICATED_SLUGS]
             if args.all else [args.slug])
    total, errors = len(slugs), 0

    for i, slug in enumerate(slugs, 1):
        data_file = data_dir / f"{slug}.json"
        if not data_file.exists():
            print(f"  SKIP: {slug} (no data file)")
            errors += 1
            continue
        try:
            rd = load_race_data(data_file)
            rd.setdefault("slug", slug)
            generate_og_image(rd, output_dir / f"{slug}.jpg")
            if args.all and i % 50 == 0:
                print(f"  [{i}/{total}] Generated {slug}.jpg")
        except Exception as e:
            print(f"  ERROR: {slug}: {e}")
            errors += 1

    print(f"\nDone. {total - errors}/{total} images generated in {output_dir}/")
    if errors:
        print(f"  {errors} errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
