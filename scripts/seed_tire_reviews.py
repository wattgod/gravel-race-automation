#!/usr/bin/env python3
"""
Seed realistic community reviews for popular tires.

Writes directly to per-tire JSON files (bypasses the worker).
Review IDs prefixed with 'seed-' for identification.
Idempotent: skips tires that already have seed reviews unless --force.

Usage:
    python scripts/seed_tire_reviews.py              # seed all 10
    python scripts/seed_tire_reviews.py --dry-run     # preview
    python scripts/seed_tire_reviews.py --force        # re-seed even if seeds exist
    python scripts/seed_tire_reviews.py --tire specialized-pathfinder-pro
"""

import argparse
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TIRE_DIR = PROJECT_ROOT / "data" / "tires"

# ── Tire configs: id → (name, widths) ────────────────────────

SEED_TIRES = {
    "panaracer-gravelking-sk": {
        "name": "Panaracer GravelKing SK",
        "widths": [35, 38, 40, 43, 50],
    },
    "specialized-pathfinder-pro": {
        "name": "Specialized Pathfinder Pro",
        "widths": [38, 42, 47],
    },
    "continental-terra-trail": {
        "name": "Continental Terra Trail",
        "widths": [35, 40, 45],
    },
    "donnelly-mso": {
        "name": "Donnelly X'Plor MSO",
        "widths": [36, 40, 50],
    },
    "vittoria-terreno-mix": {
        "name": "Vittoria Terreno Mix",
        "widths": [38, 40, 45],
    },
    "teravail-cannonball": {
        "name": "Teravail Cannonball",
        "widths": [38, 42, 47],
    },
    "pirelli-cinturato-gravel-m": {
        "name": "Pirelli Cinturato Gravel M",
        "widths": [35, 40, 45, 50],
    },
    "goodyear-connector": {
        "name": "Goodyear Connector",
        "widths": [35, 40, 45, 50],
    },
    "schwalbe-g-one-rs": {
        "name": "Schwalbe G-One RS",
        "widths": [35, 40, 45],
    },
    "vittoria-terreno-dry": {
        "name": "Vittoria Terreno Dry",
        "widths": [38, 40, 45],
    },
}

# ── Review content pools ─────────────────────────────────────

RACE_NAMES = [
    "Unbound 200", "Mid South", "Belgian Waffle Ride", "SBT GRVL",
    "Dirty Kanza", "Gravel Worlds", "Big Sugar", "Steamboat Gravel",
    "Barry-Roubaix", "The Rift", "BWR Kansas", "Crusher in the Tushar",
    "Gravel Locos", "DK XL", "Rooted Vermont",
]

VALID_CONDITIONS = ["dry", "mixed", "wet", "mud"]

# Per-tire review templates: 5 reviews each (2x 5-star, 2x 4-star, 1x 3-star)
# Each review: (stars, conditions, would_recommend, review_text, race_index)
REVIEW_TEMPLATES = {
    "panaracer-gravelking-sk": [
        (5, ["dry", "mixed"], "yes",
         "Ran these for 3,000 miles across Kansas gravel. The SK tread rolls fast on hardpack and still corners well on loose stuff. Best value in gravel tires.",
         0),
        (5, ["mixed", "wet"], "yes",
         "Used the 43mm at Mid South in the slop. Surprisingly good grip for a semi-knob tire. Would not be my first choice for pure mud but they got me through.",
         1),
        (4, ["dry"], "yes",
         "Fast rolling and affordable. Ran 40mm at SBT GRVL with no issues. Sidewalls are a bit thin though — had one close call on sharp rock.",
         3),
        (4, ["mixed"], "yes",
         "Solid all-around gravel tire. Not the best at anything but good at everything. My go-to recommendation for riders on a budget.",
         4),
        (3, ["wet", "mud"], "no",
         "Fine in dry conditions but the knobs pack with mud fast. Lost traction multiple times at Barry-Roubaix when the rain came. Switched to something more aggressive after that.",
         8),
    ],
    "specialized-pathfinder-pro": [
        (5, ["dry", "mixed"], "yes",
         "The fastest gravel tire I have ridden. Center tread rolls like a road tire on pavement sections and the side knobs hook up on corners. Ran 42mm at Unbound and saved watts all day.",
         0),
        (5, ["mixed"], "yes",
         "Perfect for mixed surface racing. Ran these front and rear at BWR and they handled everything from tarmac to chunky gravel to single track. Highly recommend.",
         2),
        (4, ["dry"], "yes",
         "Great tire but the 38mm runs narrow. I would go 42mm minimum for most gravel racing. Rolling resistance is genuinely impressive though.",
         3),
        (4, ["mixed", "wet"], "yes",
         "Used at SBT GRVL in the 47mm. Good grip on the descents and fast enough on the climbs. A bit pricey compared to alternatives but the performance justifies it.",
         3),
        (3, ["wet", "mud"], "no",
         "Not the tire for a wet race. The center tread is too slick when things get muddy. Fine for dry conditions but I blew through a mud section at Gravel Worlds and nearly crashed.",
         5),
    ],
    "continental-terra-trail": [
        (5, ["mixed", "wet"], "yes",
         "The ShieldWall casing is legit. Ran these at Dirty Kanza through flint rock and zero flats. Grip in the wet is top-tier for a gravel tire. My desert island tire.",
         4),
        (5, ["dry", "mixed"], "yes",
         "Bombproof puncture protection and still rolls reasonably fast. Used 40mm at BWR California and they handled everything. Confidence-inspiring on descents.",
         2),
        (4, ["mixed"], "yes",
         "Great all-around tire with excellent durability. A touch heavy compared to competitors but the flat protection is worth the trade. Two seasons and counting on one set.",
         3),
        (4, ["dry"], "yes",
         "Solid choice for rocky courses. The 45mm is a great option for longer gravel events where flats end your day. Not the fastest roller but that is not what you buy these for.",
         7),
        (3, ["wet", "mud"], "yes",
         "Good tire but struggles in deep mud. The tread pattern does not clear well. For mixed or dry conditions it is excellent though. Would use again on appropriate courses.",
         1),
    ],
    "donnelly-mso": [
        (5, ["mixed"], "yes",
         "Classic gravel tire for a reason. The 40mm MSO is the perfect balance of speed and grip. Ran it at the original Dirty Kanza and it is still my go-to for unpredictable conditions.",
         4),
        (5, ["dry", "mixed"], "yes",
         "One of the OG gravel tires and still competitive. Great cornering knobs with a fast center. Used 50mm at Gravel Worlds for extra cushion and loved them.",
         5),
        (4, ["wet"], "yes",
         "Surprisingly good in the wet for a file-center tire. The side knobs hook up well on loose corners. Not the cheapest option but quality construction.",
         6),
        (4, ["dry"], "yes",
         "Fast and predictable. Ran 36mm at a shorter gravel race and they felt planted. Would go wider for anything with real off-road sections though.",
         8),
        (3, ["mud"], "no",
         "Love these in dry to mixed but they are not mud tires. Center section gets slippery fast in real mud. Learned this at Mid South the hard way.",
         1),
    ],
    "vittoria-terreno-mix": [
        (5, ["mixed", "wet"], "yes",
         "The Graphene compound is noticeably grippier than competitors. Ran 40mm at Big Sugar through sand and wet leaves. Cornered with confidence the whole race.",
         6),
        (5, ["mixed"], "yes",
         "Best all-conditions gravel tire I have tried. The tread pattern works on everything from hardpack to loose over hard. 45mm is the sweet spot for longer events.",
         0),
        (4, ["dry", "mixed"], "yes",
         "Fast tire with good grip. Ran these at SBT GRVL in the 38mm. Rolling resistance is competitive with faster options while offering much more traction.",
         3),
        (4, ["wet"], "yes",
         "Impressive wet grip. Used at Steamboat Gravel in rainy conditions and felt secure on every descent. Slightly heavier than the Terreno Dry but worth it for mixed conditions.",
         7),
        (3, ["dry"], "yes",
         "Good tire but a bit heavy for pure speed. On a dry hardpack course you are giving up watts to faster rolling options. Best suited for mixed conditions as the name suggests.",
         2),
    ],
    "teravail-cannonball": [
        (5, ["dry", "mixed"], "yes",
         "Light, fast, and durable. The 42mm Cannonball is my race day tire for any course that is not pure mud. Ran them at Unbound and they rolled beautifully on the flint hills.",
         0),
        (5, ["mixed"], "yes",
         "Excellent all-rounder. The tread rolls fast on pavement sections and still grips on loose gravel. Used 47mm at the Rift and they were perfect for the volcanic terrain.",
         9),
        (4, ["dry"], "yes",
         "Very fast rolling gravel tire. The light casing makes it a bit vulnerable on sharp rock but the speed trade is worth it for most courses. Great for racing.",
         3),
        (4, ["mixed", "wet"], "yes",
         "Solid grip in mixed conditions. Ran 38mm at BWR and they handled the varied terrain well. Would go wider for rougher courses but the 38 is great for fast gravel.",
         2),
        (3, ["wet", "mud"], "no",
         "Not enough tread for real mud. The low-profile knobs pack up quickly. Great dry tire but know its limits. Switched to something more aggressive for my muddier races.",
         5),
    ],
    "pirelli-cinturato-gravel-m": [
        (5, ["mixed", "wet"], "yes",
         "The M compound is incredible in wet conditions. Best grip I have experienced on wet gravel. Ran 45mm at Mid South and they kept me upright when others were sliding out.",
         1),
        (5, ["mixed"], "yes",
         "Top-tier gravel tire. The knob pattern sheds mud better than most and the rolling resistance is competitive. 40mm at Crusher was perfect for the rocky climbs.",
         11),
        (4, ["dry", "mixed"], "yes",
         "Great all-around tire with Italian engineering that shows. A bit pricier than alternatives but the grip and durability justify the cost. Two seasons on one set.",
         0),
        (4, ["wet", "mud"], "yes",
         "Handles mud better than most gravel tires. Not a true mud tire but the M tread clears well. Used 50mm at Gravel Locos in sloppy conditions and they performed.",
         12),
        (3, ["dry"], "yes",
         "Good tire but not the fastest on pure hardpack. The aggressive tread costs you a few watts compared to faster options. Best in mixed to wet conditions where the grip pays off.",
         3),
    ],
    "goodyear-connector": [
        (5, ["dry", "mixed"], "yes",
         "Underrated tire. The Connector rolls fast and grips well for the price. Ran 40mm at Barry-Roubaix and they handled the Michigan gravel perfectly. Great value.",
         8),
        (5, ["mixed"], "yes",
         "Solid all-conditions tire from Goodyear. The compound is durable and the tread works on varied terrain. 45mm at Gravel Worlds was a great setup.",
         5),
        (4, ["dry"], "yes",
         "Fast and affordable. Not the lightest tire but the rolling resistance is competitive. Good option for riders who want performance without the premium price tag.",
         3),
        (4, ["mixed", "wet"], "yes",
         "Good grip in mixed conditions. The center tread rolls well and the side knobs hook up on corners. Used 50mm at DK and appreciated the extra volume on rough roads.",
         13),
        (3, ["wet", "mud"], "no",
         "Fine in mixed but struggles in real mud. The tread does not clear well and you lose traction fast. Stick to dry or mixed courses with these.",
         1),
    ],
    "schwalbe-g-one-rs": [
        (5, ["dry"], "yes",
         "Fastest gravel tire I have tested. The micro-knob center rolls like a road tire. Ran 40mm at BWR and set a PR. If your course is mostly dry this is the tire.",
         2),
        (5, ["dry", "mixed"], "yes",
         "Incredible rolling speed with enough grip for hardpack gravel. The Addix compound is durable too. 45mm at SBT GRVL was lightning fast on the climbs.",
         3),
        (4, ["mixed"], "yes",
         "Very fast tire. The grip is adequate for mixed conditions but not confidence-inspiring on loose stuff. Best on courses with significant pavement or hardpack sections.",
         0),
        (4, ["dry"], "yes",
         "Great speed tire. The 35mm is basically a road tire that can handle some gravel. I use them for gravel fondos with mostly paved approaches. Light and fast.",
         7),
        (3, ["wet"], "no",
         "Too slick for wet conditions. The minimal tread that makes it fast on dry surfaces becomes a liability in the rain. Learned this at a wet Rooted Vermont.",
         14),
    ],
    "vittoria-terreno-dry": [
        (5, ["dry"], "yes",
         "Built for dry gravel and it shows. The Graphene compound rolls fast and the tread pattern grips on hardpack. 40mm at Unbound in perfect conditions was chef's kiss.",
         0),
        (5, ["dry", "mixed"], "yes",
         "My go-to for dry gravel races. Faster than the Terreno Mix with plenty of grip for hardpack and loose-over-hard. Ran 45mm at Big Sugar and loved them.",
         6),
        (4, ["dry"], "yes",
         "Fast and grippy in dry conditions. The low-profile tread rolls well on pavement sections too. Not as versatile as the Mix but that is not its job.",
         3),
        (4, ["mixed"], "yes",
         "Good dry tire that handles some mixed terrain. I ran 38mm at BWR California and they were fine on the varied surfaces. Would not choose these if rain was forecast though.",
         2),
        (3, ["wet"], "no",
         "Name says it all — these are dry tires. Tried them at a wet Steamboat Gravel and spent most of the race sliding. Know your conditions and choose accordingly.",
         7),
    ],
}


def generate_reviews(tire_id: str) -> list:
    """Generate 5 seed reviews for a tire."""
    config = SEED_TIRES[tire_id]
    templates = REVIEW_TEMPLATES[tire_id]
    reviews = []

    # Fixed seed per tire for reproducibility
    rng = random.Random(hash(tire_id) & 0xFFFFFFFF)

    # Base date: spread reviews over the past 30 days
    base_date = datetime(2026, 2, 15, 10, 0, 0)

    for n, (stars, conditions, recommend, text, race_idx) in enumerate(templates, 1):
        width = rng.choice(config["widths"])
        pressure = rng.randint(22, 35)
        race = RACE_NAMES[race_idx] if race_idx < len(RACE_NAMES) else RACE_NAMES[0]
        submitted = base_date - timedelta(days=rng.randint(1, 30), hours=rng.randint(0, 23))

        reviews.append({
            "review_id": f"seed-{tire_id}-{n}",
            "tire_id": tire_id,
            "tire_name": config["name"],
            "stars": stars,
            "width_ridden": width,
            "pressure_psi": pressure,
            "conditions": conditions,
            "race_used_at": race,
            "would_recommend": recommend,
            "review_text": text,
            "submitted_at": submitted.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "approved": True,
        })

    return reviews


def has_seed_reviews(tire_data: dict) -> bool:
    """Check if tire already has seed-prefixed reviews."""
    for r in tire_data.get("community_reviews", []):
        if isinstance(r.get("review_id"), str) and r["review_id"].startswith("seed-"):
            return True
    return False


def remove_seed_reviews(tire_data: dict) -> int:
    """Remove existing seed reviews, return count removed."""
    original = tire_data.get("community_reviews", [])
    filtered = [r for r in original if not (isinstance(r.get("review_id"), str) and r["review_id"].startswith("seed-"))]
    removed = len(original) - len(filtered)
    tire_data["community_reviews"] = filtered
    return removed


def seed_tire(tire_id: str, force: bool = False, dry_run: bool = False) -> str:
    """Seed reviews for a single tire. Returns status message."""
    tire_path = TIRE_DIR / f"{tire_id}.json"
    if not tire_path.exists():
        return f"  SKIP  {tire_id}: file not found at {tire_path}"

    tire_data = json.loads(tire_path.read_text(encoding="utf-8"))

    if has_seed_reviews(tire_data) and not force:
        count = sum(1 for r in tire_data.get("community_reviews", [])
                    if isinstance(r.get("review_id"), str) and r["review_id"].startswith("seed-"))
        return f"  SKIP  {tire_id}: already has {count} seed reviews (use --force to replace)"

    if dry_run:
        reviews = generate_reviews(tire_id)
        stars = [r["stars"] for r in reviews]
        avg = sum(stars) / len(stars)
        return f"  DRY   {tire_id}: would add 5 reviews (avg {avg:.1f} stars)"

    # Remove existing seed reviews if --force
    if force:
        removed = remove_seed_reviews(tire_data)
        if removed:
            print(f"  DEL   {tire_id}: removed {removed} existing seed reviews")

    # Generate and append
    reviews = generate_reviews(tire_id)
    if "community_reviews" not in tire_data:
        tire_data["community_reviews"] = []
    tire_data["community_reviews"].extend(reviews)

    # Sort by submitted_at descending (newest first)
    tire_data["community_reviews"].sort(
        key=lambda r: r.get("submitted_at", ""), reverse=True
    )

    # Write — match sync_tire_reviews.py format exactly
    with open(tire_path, "w", encoding="utf-8") as f:
        json.dump(tire_data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    stars = [r["stars"] for r in reviews]
    avg = sum(stars) / len(stars)
    return f"  SEED  {tire_id}: added 5 reviews (avg {avg:.1f} stars, total now {len(tire_data['community_reviews'])})"


def main():
    parser = argparse.ArgumentParser(description="Seed realistic tire reviews.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--force", action="store_true", help="Re-seed even if seeds exist")
    parser.add_argument("--tire", type=str, help="Seed a single tire by ID")
    args = parser.parse_args()

    print("\n=== Seed Tire Reviews ===")
    if args.dry_run:
        print("Mode: DRY RUN (no files will be modified)\n")
    elif args.force:
        print("Mode: FORCE (replacing existing seed reviews)\n")
    else:
        print("Mode: Normal (skipping tires with existing seeds)\n")

    tire_ids = [args.tire] if args.tire else list(SEED_TIRES.keys())

    for tire_id in tire_ids:
        if tire_id not in SEED_TIRES:
            print(f"  ERROR {tire_id}: not in seed list")
            continue
        result = seed_tire(tire_id, force=args.force, dry_run=args.dry_run)
        print(result)

    print(f"\nDone. {len(tire_ids)} tires processed.")


if __name__ == "__main__":
    main()
