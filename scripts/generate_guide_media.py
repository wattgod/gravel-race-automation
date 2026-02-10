#!/usr/bin/env python3
"""
Generate media assets for the Gravel God Training Guide.

Reads the guide media manifest, generates images via Google AI Studio (Gemini / Nano Banana Pro),
post-processes with Pillow for brand consistency, and outputs web-ready WebP files.

Usage:
    python scripts/generate_guide_media.py                    # Generate all pending
    python scripts/generate_guide_media.py --chapter 3        # Chapter 3 only
    python scripts/generate_guide_media.py --asset ch3-zones  # Single asset
    python scripts/generate_guide_media.py --retry-failed     # Retry failures
    python scripts/generate_guide_media.py --post-process     # Re-run post-processing only
    python scripts/generate_guide_media.py --status           # Status summary
    python scripts/generate_guide_media.py --dry-run          # Show what would be generated
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Paths
GUIDE_DIR = Path(__file__).parent.parent / "guide"
MANIFEST_PATH = GUIDE_DIR / "guide-media-manifest.json"
RAW_DIR = GUIDE_DIR / "media-raw"
OUTPUT_DIR = GUIDE_DIR / "media"

# Ensure directories exist
RAW_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_manifest() -> dict:
    """Load and return the media manifest."""
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def save_manifest(manifest: dict) -> None:
    """Save manifest back to disk."""
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ── Post-Processing ──────────────────────────────────────────


def post_process(asset: dict, raw_path: Path, defaults: dict) -> list[Path]:
    """Post-process a raw image: border, overlay, resize, save WebP.

    Returns list of output file paths.
    """
    from PIL import Image

    sys.path.insert(0, str(Path(__file__).parent))
    from media_templates.base import apply_brand_border, hex_to_rgb

    img = Image.open(raw_path).convert("RGB")

    # Apply data overlay if specified
    pp = asset.get("post_process", {})
    if pp.get("type") == "data_overlay":
        template_name = pp.get("template", "")
        img = apply_data_overlay(img, template_name, asset)

    # Apply brand border
    border_cfg = defaults.get("border", {})
    border_width = border_cfg.get("width", 3)
    border_color = border_cfg.get("color", "#000000")
    img = apply_brand_border(img, width=border_width, color=border_color)

    # Resize and save WebP versions
    quality = defaults.get("quality", 85)
    output_paths = resize_for_web(img, asset.get("resize", {}), asset["id"], quality)

    return output_paths


def apply_data_overlay(img, template_name: str, asset: dict):
    """Route to the appropriate template module for infographic overlays."""
    from PIL import Image

    sys.path.insert(0, str(Path(__file__).parent))

    if template_name == "zone_spectrum":
        from media_templates.zone_spectrum import render
        dims = asset.get("dimensions", {})
        return render(width=dims.get("width", 1200), height=dims.get("height", 600))
    elif template_name == "training_phases":
        from media_templates.training_phases import render
        dims = asset.get("dimensions", {})
        return render(width=dims.get("width", 1600), height=dims.get("height", 500))
    else:
        print(f"  WARNING: Unknown template '{template_name}', skipping overlay")
        return img


def resize_for_web(img, sizes: dict, asset_id: str, quality: int = 85) -> list[Path]:
    """Save 1x + 2x WebP versions of the image. Returns output paths."""
    from PIL import Image

    output_paths = []

    for label, dims in sizes.items():
        if len(dims) != 2:
            continue
        w, h = dims
        resized = img.resize((w, h), Image.LANCZOS)
        out_path = OUTPUT_DIR / f"{asset_id}-{label}.webp"
        resized.save(str(out_path), "WEBP", quality=quality)
        output_paths.append(out_path)
        print(f"  Saved {out_path.name} ({w}x{h}, {out_path.stat().st_size:,} bytes)")

    return output_paths


# ── API Generation ────────────────────────────────────────────


async def generate_nano_banana(asset: dict, defaults: dict) -> Path:
    """Generate an image via Google AI Studio / Gemini Image API.

    Returns path to raw output file.
    """
    import os
    import httpx

    api_key = os.environ.get("GOOGLE_AI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GOOGLE_AI_API_KEY not set. Add it to .env or export it."
        )

    model = asset.get("model", defaults.get("model", "nano-banana-pro"))
    prompt = asset["prompt"]
    dims = asset.get("dimensions", {"width": 1920, "height": 640})

    # Google AI Studio Imagen API endpoint
    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={api_key}"

    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": _aspect_ratio(dims["width"], dims["height"]),
        },
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    # Extract image bytes from response
    predictions = data.get("predictions", [])
    if not predictions:
        raise RuntimeError(f"No predictions returned for {asset['id']}")

    import base64
    img_bytes = base64.b64decode(predictions[0]["bytesBase64Encoded"])

    raw_path = RAW_DIR / f"{asset['id']}.png"
    raw_path.write_bytes(img_bytes)
    print(f"  Generated raw: {raw_path.name} ({len(img_bytes):,} bytes)")

    return raw_path


def _aspect_ratio(w: int, h: int) -> str:
    """Convert dimensions to closest supported aspect ratio string."""
    ratio = w / h
    if ratio >= 2.5:
        return "3:1"
    elif ratio >= 1.7:
        return "16:9"
    elif ratio >= 1.3:
        return "4:3"
    elif ratio >= 0.9:
        return "1:1"
    elif ratio >= 0.7:
        return "3:4"
    else:
        return "9:16"


# ── Batch Generation ─────────────────────────────────────────


async def generate_batch(
    assets: list[dict], defaults: dict, concurrency: int = 3
) -> dict:
    """Generate multiple assets with concurrency control.

    Returns dict of {asset_id: "success"|"error message"}.
    """
    sem = asyncio.Semaphore(concurrency)
    results = {}

    async def _gen(asset):
        async with sem:
            asset_id = asset["id"]
            try:
                print(f"\n→ Generating {asset_id}...")

                # Check for data overlay templates that don't need API
                pp = asset.get("post_process", {})
                if pp.get("type") == "data_overlay" and pp.get("template") in ("zone_spectrum", "training_phases"):
                    # Pure Pillow-generated infographic — no API call needed
                    raw_path = RAW_DIR / f"{asset_id}.png"
                    rendered = apply_data_overlay(None, pp["template"], asset)
                    rendered.save(str(raw_path), "PNG")
                    print(f"  Generated via template: {raw_path.name}")
                else:
                    raw_path = await generate_nano_banana(asset, defaults)

                output_paths = post_process(asset, raw_path, defaults)
                asset["status"] = "complete"
                asset["generated_at"] = datetime.now(timezone.utc).isoformat()
                asset["output_files"] = [p.name for p in output_paths]
                results[asset_id] = "success"
            except Exception as e:
                asset["status"] = "failed"
                asset["error"] = str(e)
                results[asset_id] = f"error: {e}"
                print(f"  FAILED: {e}")

    await asyncio.gather(*[_gen(a) for a in assets])
    return results


# ── Status Report ─────────────────────────────────────────────


def print_status(manifest: dict) -> None:
    """Print a summary of asset generation status."""
    assets = manifest["assets"]
    total = len(assets)
    pending = sum(1 for a in assets if a.get("status") == "pending")
    complete = sum(1 for a in assets if a.get("status") == "complete")
    failed = sum(1 for a in assets if a.get("status") == "failed")

    print(f"\n{'='*50}")
    print(f"GUIDE MEDIA STATUS")
    print(f"{'='*50}")
    print(f"  Total assets:  {total}")
    print(f"  Pending:       {pending}")
    print(f"  Complete:      {complete}")
    print(f"  Failed:        {failed}")

    if failed > 0:
        print(f"\nFailed assets:")
        for a in assets:
            if a.get("status") == "failed":
                print(f"  - {a['id']}: {a.get('error', 'unknown')}")

    # Check output directory
    webp_count = len(list(OUTPUT_DIR.glob("*.webp")))
    raw_count = len(list(RAW_DIR.glob("*")))
    print(f"\nOutput files:")
    print(f"  Raw:   {raw_count} files in {RAW_DIR}")
    print(f"  WebP:  {webp_count} files in {OUTPUT_DIR}")
    print()


# ── CLI ───────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Generate media assets for the Gravel God Training Guide"
    )
    parser.add_argument(
        "--chapter", type=int, help="Generate assets for a specific chapter only"
    )
    parser.add_argument(
        "--asset", type=str, help="Generate a single asset by ID"
    )
    parser.add_argument(
        "--retry-failed", action="store_true", help="Retry failed assets"
    )
    parser.add_argument(
        "--post-process", action="store_true",
        help="Re-run post-processing only (no API calls)"
    )
    parser.add_argument(
        "--status", action="store_true", help="Print status summary"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be generated"
    )
    parser.add_argument(
        "--concurrency", type=int, default=3,
        help="Max concurrent API calls (default: 3)"
    )
    args = parser.parse_args()

    manifest = load_manifest()
    defaults = manifest.get("defaults", {})
    assets = manifest["assets"]

    if args.status:
        print_status(manifest)
        return

    # Filter assets
    if args.asset:
        targets = [a for a in assets if a["id"] == args.asset]
        if not targets:
            print(f"ERROR: Asset '{args.asset}' not found in manifest")
            sys.exit(1)
    elif args.chapter:
        targets = [a for a in assets if a.get("chapter") == args.chapter]
        if not targets:
            print(f"ERROR: No assets found for chapter {args.chapter}")
            sys.exit(1)
    elif args.retry_failed:
        targets = [a for a in assets if a.get("status") == "failed"]
        if not targets:
            print("No failed assets to retry.")
            return
    elif args.post_process:
        targets = [a for a in assets if (RAW_DIR / f"{a['id']}.png").exists()]
        if not targets:
            print("No raw files found for post-processing.")
            return
    else:
        # Default: all pending
        targets = [a for a in assets if a.get("status") == "pending"]
        if not targets:
            print("No pending assets. Use --retry-failed or --status.")
            return

    if args.dry_run:
        print(f"\nWould generate {len(targets)} assets:")
        for a in targets:
            print(f"  - {a['id']} ({a['type']}, {a['placement']})")
        return

    print(f"\nGenerating {len(targets)} assets...")
    start = time.time()

    if args.post_process:
        # Post-process only — no async needed
        for asset in targets:
            raw_path = RAW_DIR / f"{asset['id']}.png"
            if raw_path.exists():
                print(f"\n→ Post-processing {asset['id']}...")
                try:
                    post_process(asset, raw_path, defaults)
                    asset["status"] = "complete"
                    asset["generated_at"] = datetime.now(timezone.utc).isoformat()
                except Exception as e:
                    print(f"  FAILED: {e}")
                    asset["status"] = "failed"
                    asset["error"] = str(e)
    else:
        results = asyncio.run(
            generate_batch(targets, defaults, concurrency=args.concurrency)
        )

    save_manifest(manifest)
    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s")
    print_status(manifest)


if __name__ == "__main__":
    main()
