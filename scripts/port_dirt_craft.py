#!/usr/bin/env python3
"""One-off port: dirt-craft-course/data → data/courses/dirt-craft/.

Normalizes block schemas to the conventions generate_guide.py renders:
  - accordion: panels/{title,content}/{title,content_blocks} → items[]
  - data_table: columns→headers, title→caption
  - L03 calculator: adds calculator_id, outputs→output_fields
  - race_slug inputs: race_search → optional plain text (ignored by compute)
  - L08 string select options → {value,label} objects
  - inserts image blocks (course-local "src" paths) per placement map

Safe to re-run — regenerates everything from the source repo.
"""
import json
import shutil
from pathlib import Path

SRC = Path("/Users/mattirowe/Documents/GravelGod/dirt-craft-course/data")
DST = Path(__file__).resolve().parent.parent / "data" / "courses" / "dirt-craft"
ILLUSTRATIONS = SRC / "illustrations"
ASSET_URL_BASE = "/course/dirt-craft/assets"

# ── Image placement: lesson file → [(insert_after_original_index, filename, alt, caption)]
IMAGE_PLAN = {
    "01-letting-go.json": [
        (1, "L01_death_grip_vs_weighted_drop_v2.webp",
         "Side-by-side comparison: a rigid rider with a death grip and locked elbows versus a relaxed rider in the weighted drop position with heavy feet and quiet hands",
         "Same road, same speed. The difference is where the weight lives."),
        (3, "L01_hands_light_grip.webp",
         "Close-up of hands resting lightly on gravel handlebar tops, fingers wrapped loosely with minimal grip pressure",
         "Grip pressure at a 3 out of 10 — holding a bag of chips you don't want to crush."),
        (10, "L01_washboard_road.webp",
         "Washboard gravel road with shallow rhythmic corrugations stretching into the distance",
         "Washboard: the surface that punishes rigidity."),
    ],
    "02-your-body-is-the-suspension.json": [
        (1, "L02_rigid_vs_hinged_v2.webp",
         "Comparison of a rigid rider transmitting a bump through a locked body versus a hinged rider absorbing the same bump through bent hips and elbows",
         "Rigid transmits. Hinged absorbs."),
        (6, "L02_hip_hinge_side.webp",
         "Side view of a gravel rider hinged at the hips with a flat back, low torso, and bent elbows over rough terrain",
         "The Hip Hinge: stable lower body, floating upper body."),
    ],
    "03-where-traction-lives.json": [
        (1, "L03_tire_contact_patch.webp",
         "Diagram of a gravel tire contact patch growing larger as pressure drops, showing more rubber on the ground at lower PSI",
         "Lower pressure, bigger contact patch, more traction."),
        (6, "L03_four_surfaces.webp",
         "Four gravel surface types side by side: hardpack, loose over hard, chunky embedded rock, and sand",
         "Four surfaces, four different pressure windows."),
    ],
    "04-the-quiet-eye.json": [
        (1, "L04_look_ahead.webp",
         "Gravel rider looking far up the road, gaze fixed 3 to 5 seconds ahead instead of at the front wheel",
         "Central vision lives 3-5 seconds up the road."),
        (5, "L04_scanning_hierarchy.webp",
         "Visual scanning hierarchy diagram: central vision focused far ahead while peripheral vision covers the near surface",
         "The Quiet Eye hierarchy: far focus, wide gaze."),
    ],
    "05-braking-that-builds-confidence.json": [
        (2, "L05_two_finger_brake_v2.webp",
         "Close-up of a two-finger braking position on the hoods, index and middle finger covering the lever with a relaxed grip",
         "Two fingers on the lever, two keeping the bar."),
        (3, "L05_speed_scrub_descent.webp",
         "Rider scrubbing speed on a straight section of gravel descent before the corner, bike upright and weight back",
         "All braking happens before the corner, not in it."),
        (8, "L05_brake_position_wide.webp",
         "Braking body position on gravel: hips pushed back, heels dropped, arms long, weight low behind the saddle",
         "The braking position: hips back, heels down, arms long."),
    ],
    "06-cornering-without-clenching.json": [
        (1, "L06_outside_foot_corner.webp",
         "Gravel rider cornering with the outside pedal dropped to six o'clock and weighted, bike leaned beneath an upright body",
         "Outside foot heavy, inside hand light, bike leaning beneath you."),
        (3, "L06_line_selection.webp",
         "Overhead view of corner line options through a loose gravel corner, highlighting the smoothest packed line over the geometric apex",
         "Surface first, geometry second: ride the packed line, not the apex."),
    ],
    "07-climbing-without-spinning-out.json": [
        (1, "L07_standing_vs_seated_v2.webp",
         "Comparison of standing and seated climbing on loose gravel showing how standing shifts weight off the rear tire",
         "Standing unloads the rear tire exactly when it needs weight most."),
        (6, "L07_seated_climb.webp",
         "Seated climbing position on a loose gravel grade: weight back on the saddle, torso low, elbows bent",
         "The seated climbing ready position keeps the drive wheel planted."),
    ],
    "08-reading-surfaces-at-speed.json": [
        (2, "L08_surface_transition.webp",
         "Gravel road transitioning abruptly from smooth hardpack to loose chunky rock, seen from the rider's perspective",
         "Transitions are where surface reading pays off — pre-adjust before the change."),
    ],
    "09-descending-as-play.json": [
        (1, "L09_four_positions.webp",
         "Four descending body positions from hoods upright through hoods low and drops to a full drops tuck",
         "The Position Ladder: every rung down buys free speed."),
        (4, "L09_drops_descent.webp",
         "Gravel rider descending in the drops with bent elbows, low torso, and heels down on a fast gravel road",
         "The drops: more brake leverage, lower center of mass, better control."),
    ],
    "10-pack-dynamics-and-pacing.json": [
        (2, "L10_drafting_gap.webp",
         "Two gravel riders drafting with a visible gap between wheels on a smooth gravel road",
         "The draft is free speed — if the gap matches the surface."),
        (7, "L10_surface_adjusted_gap.webp",
         "Diagram of drafting gaps lengthening as the surface degrades from smooth gravel to loose and chunky rock",
         "Surface-adjusted gaps: smoother surface, tighter wheel."),
    ],
    "11-when-things-break.json": [
        (1, "L11_repair_kit_v2.webp",
         "Field repair kit laid out on the ground: tire plugs, spare tube, quick link, CO2, tire levers, and multi-tool",
         "The minimum kit for 40+ mile events — audited the week before every race."),
        (4, "L11_tire_plug_v2.webp",
         "Hands inserting a tire plug into a punctured tubeless gravel tire with the wheel still on the bike",
         "Tire plug repair: find it, plug it, spin it — target under 3 minutes."),
    ],
    "12-the-final-hour.json": [
        (2, "L12_fatigue_rider.webp",
         "Fatigued gravel racer late in a long race with degraded form: creeping death grip, rising shoulders, locked elbows",
         "Hour five: fatigue strips skills in reverse order of acquisition."),
        (7, "L12_body_scan_v2.webp",
         "Head-to-toe body scan checkpoints on a rider: jaw, shoulders, elbows, hands, hips, and heels marked for the fatigue reset",
         "The 10-second full body scan — jaw to heels, top to bottom."),
    ],
}

COURSE_JSON = {
    "id": "dirt-craft",
    "title": "Dirt Craft",
    "subtitle": "Stop fighting the bike. Start riding it.",
    "description": (
        "The skills, numbers, and instincts that separate riders who race gravel "
        "from riders who survive it. 12 lessons built around deliberate practice "
        "drills, sensation targets, and the emotional journey from fear to flow — "
        "plus a stack of 12 named tools you can deploy on any surface, at any speed."
    ),
    "price_usd": 29,
    "stripe_payment_link": "https://buy.stripe.com/xxx",
    "stripe_price_id": "price_xxx",
    "instructor": {
        "name": "Matti Rowe",
        "title": "Head Coach, Gravel God Cycling",
        "bio": (
            "USAC Level 2 coach, 15+ years of endurance coaching experience. A "
            "reformed roadie who was genuinely terrible at bike handling — rigid "
            "arms, death grip, braking in corners — and rebuilt his riding through "
            "years of deliberate skill practice. Has guided athletes through Unbound "
            "200, BWR, SBT GRVL, and dozens of other premier gravel events. "
            "Specializes in turning slow, boring, repetitive drills into invisible "
            "race-day instinct."
        ),
    },
    "what_youll_learn": [
        "Break the death-grip cycle and let the bike move beneath you",
        "Find your personal tire pressure and traction envelope on any surface",
        "Brake, corner, and climb on loose terrain with specific, repeatable technique",
        "Read surfaces at speed and pre-adjust before transitions",
        "Descend gravel as play, not survival — using body position for free speed",
        "Maintain technique under deep fatigue with the 20-minute reset protocol",
    ],
    "modules": [
        {
            "id": "trust-the-bike",
            "title": "Trust the Bike",
            "tagline": "The bike knows what to do. Your job is to stop preventing it.",
            "lessons": [
                {"id": "letting-go", "title": "Letting Go", "file": "lessons/01-letting-go.json"},
                {"id": "your-body-is-the-suspension", "title": "Your Body Is the Suspension", "file": "lessons/02-your-body-is-the-suspension.json"},
                {"id": "where-traction-lives", "title": "Where Traction Actually Lives", "file": "lessons/03-where-traction-lives.json"},
                {"id": "the-quiet-eye", "title": "The Quiet Eye", "file": "lessons/04-the-quiet-eye.json"},
                {"id": "trust-stack-check", "title": "Module 1: Stack Check", "file": "lessons/m1-stack-check.json"},
            ],
        },
        {
            "id": "control-the-inputs",
            "title": "Control the Inputs",
            "tagline": "Replace fear with specific, repeatable technique.",
            "lessons": [
                {"id": "braking-that-builds-confidence", "title": "Braking That Builds Confidence", "file": "lessons/05-braking-that-builds-confidence.json"},
                {"id": "cornering-without-clenching", "title": "Cornering Without Clenching", "file": "lessons/06-cornering-without-clenching.json"},
                {"id": "climbing-without-spinning-out", "title": "Climbing Without Spinning Out", "file": "lessons/07-climbing-without-spinning-out.json"},
                {"id": "reading-surfaces-at-speed", "title": "Reading Surfaces at Speed", "file": "lessons/08-reading-surfaces-at-speed.json"},
                {"id": "control-stack-check", "title": "Module 2: Stack Check", "file": "lessons/m2-stack-check.json"},
            ],
        },
        {
            "id": "find-the-speed",
            "title": "Find the Speed",
            "tagline": "Speed is the byproduct of skill meeting terrain.",
            "lessons": [
                {"id": "descending-as-play", "title": "Descending as Play, Not Survival", "file": "lessons/09-descending-as-play.json"},
                {"id": "pack-dynamics-and-pacing", "title": "Pack Dynamics & Pacing by Terrain", "file": "lessons/10-pack-dynamics-and-pacing.json"},
                {"id": "when-things-break", "title": "When Things Break", "file": "lessons/11-when-things-break.json"},
                {"id": "speed-stack-check", "title": "Module 3: Stack Check", "file": "lessons/m3-stack-check.json"},
            ],
        },
        {
            "id": "ride-in-flow",
            "title": "Ride in Flow",
            "tagline": "If you just ride for watts, you cap your enjoyment. If you get good at riding your bike, your enjoyment is endless.",
            "lessons": [
                {"id": "the-final-hour", "title": "The Final Hour and Beyond", "file": "lessons/12-the-final-hour.json"},
                {"id": "flow-stack-check", "title": "Module 4: Stack Check", "file": "lessons/m4-stack-check.json"},
            ],
        },
    ],
    "meta_description": (
        "Master gravel bike handling in 12 drill-based lessons — from death grip "
        "to flow. Tire pressure, cornering, braking, descending. Field drills included."
    ),
    "og_image": "course-dirt-craft-og.png",
    "status": "active",
}


def normalize_accordion(block):
    """Convert the three dirt-craft accordion shapes into items[]."""
    if "panels" in block:
        items = [{"title": p["title"], "content": p["content"]} for p in block["panels"]]
    elif "content_blocks" in block:
        items = [{"title": block.get("title", "Details"),
                  "blocks": [normalize_block(b) for b in block["content_blocks"]]}]
    else:
        items = [{"title": block.get("title", "Details"), "content": block.get("content", "")}]
    return {"type": "accordion", "items": items}


def normalize_data_table(block):
    out = dict(block)
    if "columns" in out:
        out["headers"] = out.pop("columns")
    if "title" in out and "caption" not in out:
        out["caption"] = out.pop("title")
    out.pop("title", None)
    return out


def normalize_select_options(options):
    """String options → {value,label} objects."""
    norm = []
    for opt in options:
        if isinstance(opt, dict):
            norm.append(opt)
        else:
            norm.append({"value": opt, "label": str(opt).replace("_", " ").title()})
    return norm


def normalize_calculator(block):
    out = dict(block)
    # L03 baseline calculator: no id, "outputs" instead of "output_fields"
    if "calculator_id" not in out:
        out["calculator_id"] = "pressure-window-baseline"
    if "outputs" in out and "output_fields" not in out:
        out["output_fields"] = out.pop("outputs")
    out.pop("outputs", None)

    inputs = []
    for inp in out.get("inputs", []):
        inp = dict(inp)
        # race_search → optional plain text, ignored by compute
        if inp.get("type") == "race_search":
            inp["type"] = "text"
            inp["optional"] = True
            inp["placeholder"] = "e.g. Unbound 200 — for your notes only"
            inp["help"] = ("Optional note field. The calculation uses the manual "
                           "inputs below — enter gradient/altitude/surface yourself.")
            inp.pop("race_fields", None)
            inp.pop("required", None)
        if inp.get("type") == "select" and "options" in inp:
            inp["options"] = normalize_select_options(inp["options"])
        # L03 inputs carry "default" but no placeholder
        if inp.get("type", "number") == "number" and "placeholder" not in inp and "default" in inp:
            inp["placeholder"] = str(inp["default"])
        inputs.append(inp)
    out["inputs"] = inputs
    return out


def normalize_block(block):
    t = block.get("type")
    if t == "accordion":
        return normalize_accordion(block)
    if t == "data_table":
        return normalize_data_table(block)
    if t == "calculator":
        return normalize_calculator(block)
    return block


def port_lesson(src_path: Path, dst_path: Path):
    data = json.loads(src_path.read_text(encoding="utf-8"))
    blocks = [normalize_block(b) for b in data.get("blocks", [])]

    # Insert image blocks (descending index keeps original positions valid)
    plan = IMAGE_PLAN.get(src_path.name, [])
    for after_idx, fname, alt, caption in sorted(plan, key=lambda p: -p[0]):
        img_block = {
            "type": "image",
            "src": f"{ASSET_URL_BASE}/{fname}",
            "alt": alt,
            "caption": caption,
        }
        blocks.insert(after_idx + 1, img_block)

    data["blocks"] = blocks
    dst_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return [p[1] for p in plan]


def main():
    lessons_dst = DST / "lessons"
    assets_dst = DST / "assets"
    lessons_dst.mkdir(parents=True, exist_ok=True)
    assets_dst.mkdir(parents=True, exist_ok=True)

    (DST / "course.json").write_text(
        json.dumps(COURSE_JSON, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {DST / 'course.json'}")

    used_images = []
    for src_path in sorted((SRC / "lessons").glob("*.json")):
        dst_path = lessons_dst / src_path.name
        used_images += port_lesson(src_path, dst_path)
        print(f"  lessons/{src_path.name}")

    for fname in sorted(set(used_images)):
        src_img = ILLUSTRATIONS / fname
        if not src_img.exists():
            raise SystemExit(f"MISSING ILLUSTRATION: {src_img}")
        shutil.copy2(src_img, assets_dst / fname)
    print(f"Copied {len(set(used_images))} illustrations → {assets_dst}")

    md = COURSE_JSON["meta_description"]
    print(f"meta_description length: {len(md)} chars {'OK' if len(md) < 160 else 'TOO LONG'}")


if __name__ == "__main__":
    main()
