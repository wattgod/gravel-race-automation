#!/usr/bin/env python3
"""
Generate Open Graph share cards for race profile pages -> og/{slug}.jpg.

Topo race card (scripts/og_topo.py): tier · location, race name, the
editorial verdict, and the Lab Score tag. Every value comes from
generate_neo_brutalist.load_race_data — the same normalizer that renders
/race/{slug}/ — so the card can't disagree with the page. (The Feb-2026
cards computed their own score and were never regenerated: Unbound 200's
card said 80 while its page said 96.)

The race card stays in the critic's register: no plan/coaching pitch inside
the rating, only the brand strip naming all three pillars (same rule as
generate_neo_brutalist.build_hero).

Usage:
    python scripts/generate_og_images.py unbound-200
    python scripts/generate_og_images.py --all
    python scripts/generate_og_images.py --all --output-dir wordpress/output/og
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

import og_topo  # noqa: E402
from generate_neo_brutalist import REMOVED_FABRICATED_SLUGS, load_race_data  # noqa: E402


def verdict_of(rd: dict) -> str:
    """Same precedence as generate_neo_brutalist.build_hero."""
    return (
        rd.get("final_verdict", {}).get("one_liner", "").strip()
        or rd.get("biased_opinion", {}).get("summary", "").strip()
        or rd.get("biased_opinion", {}).get("bottom_line", "").strip()
        or rd.get("final_verdict", {}).get("should_you_race", "").strip()
    )


def race_card_html(rd: dict) -> str:
    return og_topo.race_card(
        key=rd["slug"],
        tier_label=rd["tier_label"],
        location=rd.get("vitals", {}).get("location", ""),
        name=rd["name"],
        verdict=verdict_of(rd),
        score=rd["overall_score"],
    )


def generate_og_image(rd: dict, output_path: Path, renderer: "og_topo.Renderer") -> Path:
    return renderer.render(race_card_html(rd), Path(output_path).with_suffix(".jpg"))


def main():
    parser = argparse.ArgumentParser(description="Generate OG images for gravel race profiles")
    parser.add_argument("slug", nargs="?", help="Race slug (e.g., unbound-200)")
    parser.add_argument("--all", action="store_true", help="Generate for all races")
    parser.add_argument("--data-dir", type=Path, help="Race data directory")
    parser.add_argument("--output-dir", type=Path, help="Output directory for images")
    args = parser.parse_args()

    if not args.slug and not args.all:
        parser.error("Provide a race slug or --all")

    data_dir = args.data_dir or og_topo.REPO_ROOT / "race-data"
    if not data_dir.exists():
        print(f"ERROR: Data directory not found: {data_dir}")
        sys.exit(1)
    output_dir = args.output_dir or og_topo.OG_OUTPUT_DIR

    slugs = ([f.stem for f in sorted(data_dir.glob("*.json"))
              if f.stem not in REMOVED_FABRICATED_SLUGS]
             if args.all else [args.slug])
    total, errors = len(slugs), 0

    with og_topo.Renderer() as renderer:
        for i, slug in enumerate(slugs, 1):
            data_file = data_dir / f"{slug}.json"
            if not data_file.exists():
                print(f"  SKIP: {slug} (no data file)")
                errors += 1
                continue
            try:
                rd = load_race_data(data_file)
                rd.setdefault("slug", slug)
                generate_og_image(rd, output_dir / f"{slug}.jpg", renderer)
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
