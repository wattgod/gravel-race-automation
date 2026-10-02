#!/usr/bin/env python3
"""Generate the Gravel God homepage OG image (1200x630) -> og/homepage.jpg.

This is also the site-wide fallback card for pages without their own, so it
carries the whole business, not one page's pitch: the homepage ladder —
pick a race, get a plan, get coached (scripts/og_topo.py ladder card).
Numbers come from the same sources the site renders (compute_stats for the
race count, pricing.py for the plan price), so the card can't drift the way
the Feb-2026 hardcoded one did ("328 races / 14 dimensions").
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

import og_topo  # noqa: E402
from generate_homepage import compute_stats, load_race_index  # noqa: E402
from pricing import PRICE_PER_WEEK  # noqa: E402


def ladder_rows(stats: dict) -> list[tuple[str, str, str]]:
    return [
        ("01", "Pick a race.", f"{stats['race_count']} RATED"),
        ("02", "Get a plan.", f"{PRICE_PER_WEEK} A WEEK"),
        ("03", "Get coached.", "A HUMAN IN YOUR CORNER"),
    ]


def generate(output_dir: Path | None = None, renderer=None) -> Path:
    stats = compute_stats(load_race_index())
    out = (output_dir or og_topo.OG_OUTPUT_DIR) / "homepage.jpg"
    html = og_topo.ladder_card(key="homepage", rows=ladder_rows(stats))
    if renderer is None:
        with og_topo.Renderer() as r:
            path = r.render(html, out)
    else:
        path = renderer.render(html, out)
    print(f"Generated {path} ({path.stat().st_size:,} bytes) — {stats['race_count']} races")
    return path


if __name__ == "__main__":
    generate()
