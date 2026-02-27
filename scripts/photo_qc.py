#!/usr/bin/env python3
"""
photo_qc.py — Photo quality control pipeline + SEO enhancements.

Layer 1: Automated checks (free, fast) — file integrity, dimensions, size, scoring, dedup
Layer 2: AI vision review (~$3-5) — Claude Sonnet rates relevance, quality, generates alt text
Layer 3: HTML dashboard — contact sheet for human eyeballing
Layer 4: SEO enhancements — apply AI alt text, image sitemap support, JSON-LD image array

Usage:
    python scripts/photo_qc.py --check                          # Layer 1 only
    python scripts/photo_qc.py --check --ai-review              # + Layer 2
    python scripts/photo_qc.py --check --ai-review --report     # + Layer 3
    python scripts/photo_qc.py --apply-seo                      # Layer 4
    python scripts/photo_qc.py --slug unbound-200 --check       # single race
    python scripts/photo_qc.py --check --dry-run                # preview only
    python scripts/photo_qc.py --status                         # coverage report
"""

import argparse
import base64
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

try:
    from PIL import Image, ImageFilter, ImageStat
except ImportError:
    sys.exit("Pillow is required: pip install Pillow")

# ── Paths ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "race-data"
PHOTOS_DIR = PROJECT_ROOT / "race-photos"
REPORTS_DIR = PROJECT_ROOT / "reports"
PROGRESS_FILE = PHOTOS_DIR / "_progress.json"
QC_RESULTS_FILE = PHOTOS_DIR / "_qc_results.json"
QC_PROGRESS_FILE = PHOTOS_DIR / "_qc_progress.json"
TOKENS_PATH = PROJECT_ROOT.parent / "gravel-god-brand" / "tokens" / "tokens.css"
SITE_BASE_URL = "https://gravelgodcycling.com"

# ── Constants ──────────────────────────────────────────────────────────────
EXPECTED_PHOTO_WIDTH = 1200
EXPECTED_PHOTO_HEIGHT = 675
EXPECTED_GIF_WIDTH = 400
EXPECTED_GIF_HEIGHT = 225

PHOTO_MIN_KB = 20
PHOTO_MAX_KB = 500
GIF_MIN_KB = 50
GIF_MAX_KB = 5120  # 5MB — high-motion GIFs can be 3-4MB

GIF_MIN_FRAMES = 10
GIF_MAX_FRAMES = 80  # 3s clip at 8fps = 24 nominal, but allow up to ~10s clips

SCORE_WARN_THRESHOLD = 65
SCORE_FAIL_THRESHOLD = 30

PHASH_DUPLICATE_THRESHOLD = 10  # hamming distance


# ── Perceptual Hash (Pillow-only average hash) ─────────────────────────────
def compute_phash(img: Image.Image) -> int:
    """Compute average perceptual hash — Pillow only, no imagehash dep."""
    small = img.convert("L").resize((8, 8), Image.LANCZOS)
    # Use get_flattened_data if available (Pillow >= 11), else getdata
    if hasattr(small, 'get_flattened_data'):
        pixels = list(small.get_flattened_data())
    else:
        pixels = list(small.getdata())
    avg = sum(pixels) / len(pixels)
    return sum((1 << i) for i, p in enumerate(pixels) if p >= avg)


def hamming_distance(a: int, b: int) -> int:
    """Count differing bits between two hashes."""
    return bin(a ^ b).count('1')


# ── Scoring (reused from youtube_screenshots.py) ──────────────────────────
def score_brightness(img: Image.Image) -> float:
    stat = ImageStat.Stat(img.convert("L"))
    mean = stat.mean[0]
    if mean < 30:
        return mean / 30.0 * 0.3
    if mean > 240:
        return (255 - mean) / 15.0 * 0.3
    if 80 <= mean <= 180:
        return 1.0
    if mean < 80:
        return 0.3 + 0.7 * (mean - 30) / 50.0
    return 0.3 + 0.7 * (240 - mean) / 60.0


def score_contrast(img: Image.Image) -> float:
    stat = ImageStat.Stat(img.convert("L"))
    return min(stat.stddev[0] / 60.0, 1.0)


def score_sharpness(img: Image.Image) -> float:
    gray = img.convert("L")
    laplacian = gray.filter(ImageFilter.Kernel(
        size=(3, 3),
        kernel=[-1, -1, -1, -1, 8, -1, -1, -1, -1],
        scale=1, offset=0,
    ))
    stat = ImageStat.Stat(laplacian)
    return min(stat.var[0] / 1500.0, 1.0)


def score_nature_color(img: Image.Image) -> float:
    rgb = img.convert("RGB")
    stat = ImageStat.Stat(rgb)
    r, g, b = stat.mean
    score = 0.0
    if g > r and g > b:
        score += 0.5
    if r > b and 60 < r < 200:
        score += 0.3
    if b > r and b > g:
        score -= 0.2
    spread = max(r, g, b) - min(r, g, b)
    if spread < 20:
        score -= 0.3
    return max(0.0, min(1.0, score + 0.3))


def score_composition(img: Image.Image) -> float:
    w, h = img.size
    top_third = img.crop((0, 0, w, h // 3)).convert("L")
    bottom_third = img.crop((0, 2 * h // 3, w, h)).convert("L")
    top_mean = ImageStat.Stat(top_third).mean[0]
    bottom_mean = ImageStat.Stat(bottom_third).mean[0]
    score = 1.0
    if top_mean > 200 and bottom_mean < 100:
        score -= 0.4
    if top_mean < 60 and bottom_mean < 60:
        score -= 0.3
    if abs(top_mean - bottom_mean) < 10:
        score -= 0.2
    return max(0.0, score)


def score_frame(img: Image.Image) -> float:
    """Composite quality score 0-100."""
    return (
        score_brightness(img) * 20 +
        score_contrast(img) * 20 +
        score_sharpness(img) * 25 +
        score_nature_color(img) * 20 +
        score_composition(img) * 15
    )


# ── Layer 1: Automated Checks ─────────────────────────────────────────────
def check_photo(filepath: Path) -> dict:
    """Run all automated checks on a single photo (JPG). Returns check result dict."""
    result = {
        "file": str(filepath.relative_to(PHOTOS_DIR)),
        "type": "photo",
        "checks": {},
        "status": "pass",
    }
    checks = result["checks"]

    # File exists + readable
    if not filepath.exists():
        checks["exists"] = {"pass": False, "msg": "File not found"}
        result["status"] = "fail"
        return result
    checks["exists"] = {"pass": True}

    # File size
    size_kb = filepath.stat().st_size / 1024
    checks["file_size_kb"] = {"value": round(size_kb, 1)}
    if size_kb < PHOTO_MIN_KB:
        checks["file_size_kb"]["pass"] = False
        checks["file_size_kb"]["msg"] = f"Too small ({size_kb:.0f}KB < {PHOTO_MIN_KB}KB)"
    elif size_kb > PHOTO_MAX_KB:
        checks["file_size_kb"]["pass"] = False
        checks["file_size_kb"]["msg"] = f"Too large ({size_kb:.0f}KB > {PHOTO_MAX_KB}KB)"
    else:
        checks["file_size_kb"]["pass"] = True

    # Pillow can open
    try:
        img = Image.open(filepath)
        img.load()
        checks["readable"] = {"pass": True}
    except Exception as e:
        checks["readable"] = {"pass": False, "msg": f"Cannot open: {e}"}
        result["status"] = "fail"
        return result

    # Dimensions
    w, h = img.size
    checks["dimensions"] = {"value": f"{w}x{h}"}
    if w == EXPECTED_PHOTO_WIDTH and h == EXPECTED_PHOTO_HEIGHT:
        checks["dimensions"]["pass"] = True
    else:
        checks["dimensions"]["pass"] = False
        checks["dimensions"]["msg"] = f"Expected {EXPECTED_PHOTO_WIDTH}x{EXPECTED_PHOTO_HEIGHT}"

    # Quality score
    quality = round(score_frame(img), 1)
    checks["quality_score"] = {"value": quality}
    if quality < SCORE_FAIL_THRESHOLD:
        checks["quality_score"]["pass"] = False
        checks["quality_score"]["msg"] = f"Below fail threshold ({SCORE_FAIL_THRESHOLD})"
    elif quality < SCORE_WARN_THRESHOLD:
        checks["quality_score"]["pass"] = True
        checks["quality_score"]["msg"] = f"Below warn threshold ({SCORE_WARN_THRESHOLD})"
    else:
        checks["quality_score"]["pass"] = True

    # Perceptual hash (stored for dedup comparison later)
    phash = compute_phash(img)
    result["phash"] = phash

    # Determine overall status
    any_fail = any(not c.get("pass", True) for c in checks.values())
    any_warn = any(
        c.get("pass") and c.get("msg") and "warn" in c.get("msg", "").lower()
        for c in checks.values()
    )
    if any_fail:
        result["status"] = "fail"
    elif any_warn or (quality < SCORE_WARN_THRESHOLD):
        result["status"] = "warn"

    return result


def check_gif(filepath: Path) -> dict:
    """Run all automated checks on a single GIF. Returns check result dict."""
    result = {
        "file": str(filepath.relative_to(PHOTOS_DIR)),
        "type": "gif",
        "checks": {},
        "status": "pass",
    }
    checks = result["checks"]

    # File exists
    if not filepath.exists():
        checks["exists"] = {"pass": False, "msg": "File not found"}
        result["status"] = "fail"
        return result
    checks["exists"] = {"pass": True}

    # File size
    size_kb = filepath.stat().st_size / 1024
    checks["file_size_kb"] = {"value": round(size_kb, 1)}
    if size_kb < GIF_MIN_KB:
        checks["file_size_kb"]["pass"] = False
        checks["file_size_kb"]["msg"] = f"Too small ({size_kb:.0f}KB < {GIF_MIN_KB}KB)"
    elif size_kb > GIF_MAX_KB:
        checks["file_size_kb"]["pass"] = False
        checks["file_size_kb"]["msg"] = f"Too large ({size_kb:.0f}KB > {GIF_MAX_KB}KB)"
    else:
        checks["file_size_kb"]["pass"] = True

    # Pillow can open
    try:
        img = Image.open(filepath)
        checks["readable"] = {"pass": True}
    except Exception as e:
        checks["readable"] = {"pass": False, "msg": f"Cannot open: {e}"}
        result["status"] = "fail"
        return result

    # Dimensions — width must match, height varies with source aspect ratio
    w, h = img.size
    checks["dimensions"] = {"value": f"{w}x{h}"}
    width_ok = abs(w - EXPECTED_GIF_WIDTH) <= 2
    if width_ok:
        checks["dimensions"]["pass"] = True
    else:
        checks["dimensions"]["pass"] = False
        checks["dimensions"]["msg"] = f"Expected width ~{EXPECTED_GIF_WIDTH}, got {w}"

    # Frame count
    try:
        n_frames = getattr(img, 'n_frames', 1)
        checks["frame_count"] = {"value": n_frames}
        if n_frames < GIF_MIN_FRAMES:
            checks["frame_count"]["pass"] = False
            checks["frame_count"]["msg"] = f"Too few frames ({n_frames} < {GIF_MIN_FRAMES})"
        elif n_frames > GIF_MAX_FRAMES:
            checks["frame_count"]["pass"] = False
            checks["frame_count"]["msg"] = f"Too many frames ({n_frames} > {GIF_MAX_FRAMES})"
        else:
            checks["frame_count"]["pass"] = True
    except Exception:
        checks["frame_count"] = {"pass": True, "value": "unknown"}

    # Determine overall status
    any_fail = any(not c.get("pass", True) for c in checks.values())
    if any_fail:
        result["status"] = "fail"

    return result


def check_json_disk_parity(slug: str, race_photos: list, slug_dir: Path) -> list:
    """Check that race JSON photo entries match files on disk."""
    errors = []

    # Files in JSON
    json_files = set()
    for p in race_photos:
        if p.get("file"):
            json_files.add(p["file"])

    # Files on disk
    disk_files = set()
    if slug_dir.exists():
        for f in slug_dir.iterdir():
            if f.is_file() and f.suffix in (".jpg", ".gif"):
                disk_files.add(f.name)

    # Orphans: on disk but not in JSON
    orphans = disk_files - json_files
    for f in sorted(orphans):
        errors.append({"type": "orphan", "file": f, "msg": f"On disk but not in race JSON"})

    # Missing: in JSON but not on disk
    missing = json_files - disk_files
    for f in sorted(missing):
        errors.append({"type": "missing", "file": f, "msg": f"In race JSON but not on disk"})

    return errors


def find_duplicates(photo_results: list) -> list:
    """Find perceptual hash duplicates across photos. Returns list of duplicate pairs."""
    duplicates = []
    hashes = [(r["file"], r["phash"]) for r in photo_results if "phash" in r]

    for i in range(len(hashes)):
        for j in range(i + 1, len(hashes)):
            dist = hamming_distance(hashes[i][1], hashes[j][1])
            if dist <= PHASH_DUPLICATE_THRESHOLD:
                duplicates.append({
                    "file_a": hashes[i][0],
                    "file_b": hashes[j][0],
                    "hamming_distance": dist,
                })

    return duplicates


def run_layer1(slugs: list[str] = None, dry_run: bool = False) -> dict:
    """Run Layer 1 automated checks on all races (or specified slugs).

    Returns QC results dict ready to write to _qc_results.json.
    """
    results = {
        "checked_at": date.today().isoformat(),
        "races": {},
        "summary": {"total_photos": 0, "total_gifs": 0, "total_races": 0,
                     "pass": 0, "warn": 0, "fail": 0},
    }

    # Load progress to know which races have photos
    progress = {}
    if PROGRESS_FILE.exists():
        try:
            progress = json.loads(PROGRESS_FILE.read_text())
        except json.JSONDecodeError:
            pass

    # Determine which races to check
    if slugs:
        races_to_check = slugs
    else:
        races_to_check = sorted(progress.keys())

    if dry_run:
        print(f"[DRY RUN] Would check {len(races_to_check)} races")
        for slug in races_to_check[:10]:
            print(f"  - {slug}")
        if len(races_to_check) > 10:
            print(f"  ... and {len(races_to_check) - 10} more")
        return results

    for slug in races_to_check:
        slug_dir = PHOTOS_DIR / slug
        race_result = {"photos": [], "gifs": [], "parity_errors": [], "duplicates": []}

        # Load race JSON for parity check
        race_json_path = DATA_DIR / f"{slug}.json"
        race_photos = []
        if race_json_path.exists():
            try:
                data = json.loads(race_json_path.read_text())
                race_photos = data.get("race", data).get("photos", [])
            except json.JSONDecodeError:
                pass

        # Check each photo file
        if slug_dir.exists():
            for f in sorted(slug_dir.iterdir()):
                if f.suffix == ".jpg":
                    r = check_photo(f)
                    race_result["photos"].append(r)
                    results["summary"]["total_photos"] += 1
                elif f.suffix == ".gif":
                    r = check_gif(f)
                    race_result["gifs"].append(r)
                    results["summary"]["total_gifs"] += 1

        # JSON/disk parity
        parity = check_json_disk_parity(slug, race_photos, slug_dir)
        race_result["parity_errors"] = parity

        # Perceptual hash duplicates (within this race)
        race_result["duplicates"] = find_duplicates(race_result["photos"])

        # Race-level status
        all_statuses = [r["status"] for r in race_result["photos"] + race_result["gifs"]]
        if parity:
            all_statuses.append("fail")
        if race_result["duplicates"]:
            all_statuses.append("warn")

        if "fail" in all_statuses:
            race_result["status"] = "fail"
            results["summary"]["fail"] += 1
        elif "warn" in all_statuses:
            race_result["status"] = "warn"
            results["summary"]["warn"] += 1
        else:
            race_result["status"] = "pass"
            results["summary"]["pass"] += 1

        results["races"][slug] = race_result
        results["summary"]["total_races"] += 1

    return results


# ── Layer 2: AI Vision Review ─────────────────────────────────────────────
def encode_image_base64(filepath: Path, max_size: int = 1024) -> str:
    """Resize image and encode as base64 for API calls."""
    img = Image.open(filepath)
    # Resize to max dimension
    w, h = img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    # Convert to JPEG bytes
    import io
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def build_vision_prompt(slug: str, photo_files: list[str]) -> str:
    """Build prompt for Claude vision review of race photos."""
    display_name = slug.replace("-", " ").title()
    return f"""You are reviewing photos extracted from YouTube race videos for {display_name}, a gravel cycling race.

For each photo (numbered 1-{len(photo_files)}), rate:

1. **Relevance** (1-5): How well does it show gravel racing, course terrain, or race atmosphere?
2. **Quality** (1-5): Is it sharp, well-composed, and visually interesting?
3. **Issues**: List any problems: text_overlay, watermark, letterboxing, blur, dark, interview, crowd_only, bike_shop, indoor, screen_recording
4. **Description**: One sentence describing what's visible — include terrain type, landscape features, activity, and location keywords. Write it as alt text suitable for SEO.
5. **Keywords**: 3-5 SEO terms visible in the image (e.g., "rocky descent", "Kansas prairie", "peloton", "gravel road", "mountain pass")

Return ONLY valid JSON:
{{
  "photos": [
    {{
      "index": 1,
      "relevance": 4,
      "quality": 5,
      "issues": [],
      "description": "Riders climbing loose gravel through Kansas Flint Hills at golden hour",
      "keywords": ["gravel climb", "Kansas Flint Hills", "golden hour", "peloton"]
    }}
  ]
}}"""


def run_layer2(slugs: list[str] = None, dry_run: bool = False) -> dict:
    """Run Layer 2 AI vision review. Returns per-race AI results."""
    sys.path.insert(0, str(Path(__file__).parent))
    from youtube_enrich import parse_json_response

    # Load existing QC progress
    qc_progress = {}
    if QC_PROGRESS_FILE.exists():
        try:
            qc_progress = json.loads(QC_PROGRESS_FILE.read_text())
        except json.JSONDecodeError:
            pass

    # Load progress to find races with photos
    progress = {}
    if PROGRESS_FILE.exists():
        try:
            progress = json.loads(PROGRESS_FILE.read_text())
        except json.JSONDecodeError:
            pass

    races_to_review = slugs if slugs else sorted(progress.keys())
    ai_results = {}
    reviewed = 0
    skipped = 0

    for slug in races_to_review:
        # Skip if already reviewed (resume support)
        if slug in qc_progress and not dry_run:
            skipped += 1
            ai_results[slug] = qc_progress[slug]
            continue

        slug_dir = PHOTOS_DIR / slug
        if not slug_dir.exists():
            continue

        # Collect JPG photos (not GIFs — those don't need alt text)
        photo_files = sorted(f for f in slug_dir.iterdir() if f.suffix == ".jpg")
        if not photo_files:
            continue

        if dry_run:
            print(f"  [DRY RUN] Would review {len(photo_files)} photos for {slug}")
            continue

        print(f"  Reviewing {slug} ({len(photo_files)} photos)...", end=" ", flush=True)

        # Build multimodal API call
        try:
            from youtube_enrich import call_api_vision
            prompt = build_vision_prompt(slug, [f.name for f in photo_files])

            # Encode photos
            images = []
            for pf in photo_files:
                b64 = encode_image_base64(pf)
                images.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": b64,
                    }
                })

            response = call_api_vision(prompt, images)
            parsed = parse_json_response(response)

            ai_results[slug] = {
                "reviewed_at": date.today().isoformat(),
                "photos": parsed.get("photos", []),
            }

            # Save progress incrementally
            qc_progress[slug] = ai_results[slug]
            PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
            QC_PROGRESS_FILE.write_text(json.dumps(qc_progress, indent=2) + "\n")

            reviewed += 1
            print("OK")
            time.sleep(1)  # Rate limit courtesy

        except Exception as e:
            print(f"ERROR: {e}")
            continue

    print(f"\nAI review: {reviewed} reviewed, {skipped} skipped (cached)")
    return ai_results


# ── Layer 3: HTML Dashboard ───────────────────────────────────────────────
def read_brand_tokens() -> dict:
    """Read brand tokens from tokens.css for dashboard styling."""
    tokens = {}
    if TOKENS_PATH.exists():
        css = TOKENS_PATH.read_text()
        import re
        for match in re.finditer(r'(--gg-[\w-]+)\s*:\s*([^;]+);', css):
            tokens[match.group(1)] = match.group(2).strip()
    return tokens


def render_qc_dashboard(qc_results: dict, ai_results: dict = None) -> str:
    """Render self-contained HTML QC dashboard."""
    tokens = read_brand_tokens()

    # Fallback colors if tokens not available
    bg = tokens.get("--gg-color-warm-paper", "#f5efe6")
    text_color = tokens.get("--gg-color-dark-brown", "#3a2e25")
    primary = tokens.get("--gg-color-primary-brown", "#59473c")
    teal = tokens.get("--gg-color-teal", "#1A8A82")
    gold = tokens.get("--gg-color-gold", "#B7950B")
    font_data = tokens.get("--gg-font-data", "'Sometype Mono', monospace")
    font_editorial = tokens.get("--gg-font-editorial", "'Source Serif 4', serif")

    summary = qc_results.get("summary", {})
    races = qc_results.get("races", {})

    # Sort worst-scoring races first
    sorted_races = sorted(
        races.items(),
        key=lambda x: (
            {"fail": 0, "warn": 1, "pass": 2}.get(x[1].get("status", "pass"), 2),
            x[0],
        )
    )

    # Build race sections
    race_sections = []
    for slug, race_data in sorted_races:
        status = race_data.get("status", "pass")
        status_color = {"pass": "#2d8a4e", "warn": gold, "fail": "#c0392b"}.get(status, "#666")
        border_color = {"pass": "#2d8a4e", "warn": gold, "fail": "#c0392b"}.get(status, "#ccc")

        # Photo thumbnails
        photo_html = ""
        for p in race_data.get("photos", []):
            filepath = PHOTOS_DIR / p["file"]
            if filepath.exists():
                q_score = p.get("checks", {}).get("quality_score", {}).get("value", "?")
                p_status = p.get("status", "pass")
                p_border = {"pass": "#2d8a4e", "warn": gold, "fail": "#c0392b"}.get(p_status, "#ccc")
                # AI data for this photo
                ai_desc = ""
                if ai_results and slug in ai_results:
                    idx = race_data["photos"].index(p)
                    ai_photos = ai_results[slug].get("photos", [])
                    if idx < len(ai_photos):
                        ai = ai_photos[idx]
                        ai_desc = f'<div class="ai-data">R:{ai.get("relevance","?")}/5 Q:{ai.get("quality","?")}/5<br>{ai.get("description","")}</div>'

                photo_html += f'''
                <div class="photo-card" style="border-color:{p_border}">
                    <img src="file://{filepath}" alt="{p['file']}" loading="lazy">
                    <div class="photo-meta">Score: {q_score} | {p["file"]}</div>
                    {ai_desc}
                </div>'''

        # GIF thumbnails
        gif_html = ""
        for g in race_data.get("gifs", []):
            filepath = PHOTOS_DIR / g["file"]
            if filepath.exists():
                g_status = g.get("status", "pass")
                g_border = {"pass": "#2d8a4e", "warn": gold, "fail": "#c0392b"}.get(g_status, "#ccc")
                frames = g.get("checks", {}).get("frame_count", {}).get("value", "?")
                size = g.get("checks", {}).get("file_size_kb", {}).get("value", "?")
                gif_html += f'''
                <div class="gif-card" style="border-color:{g_border}">
                    <img src="file://{filepath}" alt="{g['file']}" loading="lazy">
                    <div class="photo-meta">{frames}f | {size}KB | {g["file"]}</div>
                </div>'''

        # Parity errors
        parity_html = ""
        for pe in race_data.get("parity_errors", []):
            parity_html += f'<div class="parity-error">{pe["type"].upper()}: {pe["file"]} — {pe["msg"]}</div>'

        # Duplicates
        dup_html = ""
        for d in race_data.get("duplicates", []):
            dup_html += f'<div class="dup-warn">DUPLICATE: {d["file_a"]} ↔ {d["file_b"]} (hamming={d["hamming_distance"]})</div>'

        n_photos = len(race_data.get("photos", []))
        n_gifs = len(race_data.get("gifs", []))

        race_sections.append(f'''
        <details class="race-section" {"open" if status == "fail" else ""}>
            <summary>
                <span class="status-badge" style="background:{status_color}">{status.upper()}</span>
                <span class="race-name">{slug}</span>
                <span class="race-counts">{n_photos} photos, {n_gifs} GIFs</span>
            </summary>
            <div class="race-content">
                <div class="photo-grid">{photo_html}</div>
                <div class="gif-grid">{gif_html}</div>
                {parity_html}
                {dup_html}
            </div>
        </details>''')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Photo QC Report — {qc_results.get("checked_at", "")}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:{bg}; color:{text_color}; font-family:{font_data}; padding:20px; }}
h1 {{ font-family:{font_editorial}; font-size:28px; margin-bottom:16px; }}
.summary-bar {{ display:flex; gap:16px; margin-bottom:24px; padding:12px; border:3px solid {primary}; }}
.summary-stat {{ text-align:center; }}
.summary-stat .num {{ font-size:24px; font-weight:bold; }}
.summary-stat .label {{ font-size:11px; text-transform:uppercase; letter-spacing:1px; }}
.race-section {{ margin-bottom:8px; border:2px solid #ccc; }}
.race-section summary {{ padding:8px 12px; cursor:pointer; display:flex; align-items:center; gap:8px; }}
.race-section[open] summary {{ border-bottom:2px solid #ccc; }}
.status-badge {{ display:inline-block; padding:2px 8px; color:white; font-size:11px; font-weight:bold; letter-spacing:1px; }}
.race-name {{ font-weight:bold; }}
.race-counts {{ margin-left:auto; font-size:12px; color:#888; }}
.race-content {{ padding:12px; }}
.photo-grid, .gif-grid {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:8px; }}
.photo-card, .gif-card {{ border:3px solid #ccc; overflow:hidden; }}
.photo-card img {{ width:200px; height:auto; display:block; }}
.gif-card img {{ width:200px; height:auto; display:block; }}
.photo-meta {{ padding:4px 6px; font-size:10px; background:rgba(0,0,0,0.05); }}
.ai-data {{ padding:4px 6px; font-size:10px; color:{teal}; }}
.parity-error {{ padding:4px 8px; background:#fce4ec; color:#c0392b; font-size:12px; margin:4px 0; }}
.dup-warn {{ padding:4px 8px; background:#fff8e1; color:{gold}; font-size:12px; margin:4px 0; }}
</style>
</head>
<body>
<h1>Photo QC Report</h1>
<p>Generated: {qc_results.get("checked_at", "")} | Pipeline: photo_qc.py</p>

<div class="summary-bar">
    <div class="summary-stat"><div class="num">{summary.get("total_races", 0)}</div><div class="label">Races</div></div>
    <div class="summary-stat"><div class="num">{summary.get("total_photos", 0)}</div><div class="label">Photos</div></div>
    <div class="summary-stat"><div class="num">{summary.get("total_gifs", 0)}</div><div class="label">GIFs</div></div>
    <div class="summary-stat"><div class="num" style="color:#2d8a4e">{summary.get("pass", 0)}</div><div class="label">Pass</div></div>
    <div class="summary-stat"><div class="num" style="color:{gold}">{summary.get("warn", 0)}</div><div class="label">Warn</div></div>
    <div class="summary-stat"><div class="num" style="color:#c0392b">{summary.get("fail", 0)}</div><div class="label">Fail</div></div>
</div>

{"".join(race_sections)}

</body>
</html>'''


# ── Layer 4: SEO Enhancements ─────────────────────────────────────────────
def apply_seo_alt_text(ai_results: dict, dry_run: bool = False) -> int:
    """Update race JSON alt text from AI-generated descriptions. Returns count updated."""
    updated = 0

    for slug, ai_data in ai_results.items():
        race_json_path = DATA_DIR / f"{slug}.json"
        if not race_json_path.exists():
            continue

        try:
            data = json.loads(race_json_path.read_text())
        except json.JSONDecodeError:
            continue

        race = data.get("race", data)
        photos = race.get("photos", [])
        ai_photos = ai_data.get("photos", [])

        if not photos or not ai_photos:
            continue

        changed = False
        photo_idx = 0
        for p in photos:
            if p.get("type", "").startswith("video-") and photo_idx < len(ai_photos):
                ai = ai_photos[photo_idx]
                new_alt = ai.get("description", "")
                if new_alt and new_alt != p.get("alt", ""):
                    display_name = slug.replace("-", " ").title()
                    # Build SEO-rich alt text
                    location = race.get("vitals", {}).get("location", "")
                    alt_parts = [new_alt]
                    # Add race name if not already in description
                    race_name = race.get("display_name") or race.get("name", display_name)
                    if race_name.lower() not in new_alt.lower():
                        alt_parts.append(race_name)
                    if location and location.lower() not in new_alt.lower():
                        alt_parts.append(location)
                    p["alt"] = " - ".join(alt_parts)

                    # Store AI quality data
                    p["ai_relevance"] = ai.get("relevance")
                    p["ai_quality"] = ai.get("quality")
                    p["ai_keywords"] = ai.get("keywords", [])
                    changed = True
                photo_idx += 1

        if changed and not dry_run:
            race_json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            updated += 1
            print(f"  Updated alt text: {slug}")
        elif changed:
            print(f"  [DRY RUN] Would update: {slug}")

    return updated


# ── Status Report ─────────────────────────────────────────────────────────
def print_status():
    """Print photo coverage and QC status report."""
    progress = {}
    if PROGRESS_FILE.exists():
        try:
            progress = json.loads(PROGRESS_FILE.read_text())
        except json.JSONDecodeError:
            pass

    qc_results = {}
    if QC_RESULTS_FILE.exists():
        try:
            qc_results = json.loads(QC_RESULTS_FILE.read_text())
        except json.JSONDecodeError:
            pass

    qc_progress = {}
    if QC_PROGRESS_FILE.exists():
        try:
            qc_progress = json.loads(QC_PROGRESS_FILE.read_text())
        except json.JSONDecodeError:
            pass

    total_photos = 0
    total_gifs = 0
    for slug, p in progress.items():
        total_photos += p.get("photos", 0)
        gifs = p.get("gifs", p.get("gif", 0))
        if isinstance(gifs, bool):
            gifs = 1 if gifs else 0
        total_gifs += gifs

    summary = qc_results.get("summary", {})

    print(f"\n{'=' * 55}")
    print(f"Photo QC Status")
    print(f"{'=' * 55}")
    print(f"Races with photos:     {len(progress)}")
    print(f"Total photos on disk:  {total_photos}")
    print(f"Total GIFs on disk:    {total_gifs}")
    print(f"{'─' * 55}")

    if summary:
        print(f"Last QC check:         {qc_results.get('checked_at', 'never')}")
        print(f"Races checked:         {summary.get('total_races', 0)}")
        print(f"Photos checked:        {summary.get('total_photos', 0)}")
        print(f"GIFs checked:          {summary.get('total_gifs', 0)}")
        print(f"  Pass:                {summary.get('pass', 0)}")
        print(f"  Warn:                {summary.get('warn', 0)}")
        print(f"  Fail:                {summary.get('fail', 0)}")
    else:
        print(f"QC checks:             not yet run")

    print(f"{'─' * 55}")
    print(f"AI reviews completed:  {len(qc_progress)}")
    print(f"AI reviews remaining:  {max(0, len(progress) - len(qc_progress))}")
    print(f"{'=' * 55}")


# ── CLI ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Photo quality control pipeline + SEO enhancements.")
    parser.add_argument("--check", action="store_true",
                        help="Run Layer 1 automated checks")
    parser.add_argument("--ai-review", action="store_true",
                        help="Run Layer 2 AI vision review (requires ANTHROPIC_API_KEY)")
    parser.add_argument("--report", action="store_true",
                        help="Generate Layer 3 HTML dashboard")
    parser.add_argument("--apply-seo", action="store_true",
                        help="Apply Layer 4 SEO enhancements from AI review data")
    parser.add_argument("--slug", nargs="+",
                        help="Specific race slug(s) to check")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without writing")
    parser.add_argument("--status", action="store_true",
                        help="Print coverage report and exit")
    args = parser.parse_args()

    if args.status:
        print_status()
        return 0

    if not any([args.check, args.ai_review, args.report, args.apply_seo]):
        parser.error("Provide --check, --ai-review, --report, --apply-seo, or --status")

    # Layer 1: Automated checks
    qc_results = {}
    if args.check:
        print(f"\n{'=' * 55}")
        print(f"Layer 1: Automated Checks")
        print(f"{'=' * 55}")
        qc_results = run_layer1(slugs=args.slug, dry_run=args.dry_run)

        if not args.dry_run:
            # Save results
            PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
            # Strip phash from saved results (not JSON-serializable as-is for large ints)
            save_results = json.loads(json.dumps(qc_results, default=str))
            QC_RESULTS_FILE.write_text(json.dumps(save_results, indent=2) + "\n")
            print(f"\nResults saved: {QC_RESULTS_FILE}")

        s = qc_results.get("summary", {})
        print(f"\nSummary: {s.get('total_races', 0)} races | "
              f"{s.get('total_photos', 0)} photos | {s.get('total_gifs', 0)} GIFs")
        print(f"  Pass: {s.get('pass', 0)} | Warn: {s.get('warn', 0)} | Fail: {s.get('fail', 0)}")

    # Layer 2: AI vision review
    ai_results = {}
    if args.ai_review:
        print(f"\n{'=' * 55}")
        print(f"Layer 2: AI Vision Review")
        print(f"{'=' * 55}")
        ai_results = run_layer2(slugs=args.slug, dry_run=args.dry_run)

    # Layer 3: HTML dashboard
    if args.report:
        print(f"\n{'=' * 55}")
        print(f"Layer 3: HTML Dashboard")
        print(f"{'=' * 55}")

        # Load QC results if not from this run
        if not qc_results and QC_RESULTS_FILE.exists():
            qc_results = json.loads(QC_RESULTS_FILE.read_text())

        # Load AI results if not from this run
        if not ai_results and QC_PROGRESS_FILE.exists():
            ai_results = json.loads(QC_PROGRESS_FILE.read_text())

        if not qc_results:
            print("ERROR: No QC results found. Run --check first.")
            return 1

        html = render_qc_dashboard(qc_results, ai_results)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORTS_DIR / f"photo-qc-{date.today().isoformat()}.html"
        report_path.write_text(html)
        print(f"Dashboard: {report_path}")

    # Layer 4: SEO enhancements
    if args.apply_seo:
        print(f"\n{'=' * 55}")
        print(f"Layer 4: SEO Enhancements")
        print(f"{'=' * 55}")

        # Load AI results
        if not ai_results and QC_PROGRESS_FILE.exists():
            try:
                ai_results = json.loads(QC_PROGRESS_FILE.read_text())
            except json.JSONDecodeError:
                pass

        if not ai_results:
            print("ERROR: No AI review data found. Run --ai-review first.")
            return 1

        # Apply alt text updates
        count = apply_seo_alt_text(ai_results, dry_run=args.dry_run)
        print(f"\nUpdated alt text in {count} race files")

    return 0


if __name__ == "__main__":
    sys.exit(main())
