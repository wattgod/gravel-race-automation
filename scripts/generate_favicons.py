#!/usr/bin/env python3
"""
Generate the favicon set from web/gg-logo.svg.

Safari does not reliably use SVG favicons, and until this script existed
favicon.ico 302-redirected to an HTML page — so Safari fell back to a
generic letter-monogram tab icon instead of the real Gravel God mark.

Renders the SVG (glyph fill #3a2e25, already baked into gg-logo.svg) onto a
warm-paper (#f5efe6) square with a little padding, via a headless-Chromium
screenshot (Playwright), then downsamples that master render with Pillow
into the full icon set:

  favicon.ico          16/32/48px, multi-resolution
  favicon-16.png        16x16
  favicon-32.png        32x32
  apple-touch-icon.png 180x180 (flattened onto warm-paper — iOS fills
                        transparency with black otherwise)
  icon-192.png         192x192
  icon-512.png         512x512

Output goes straight into web/ (flat, next to gg-logo.svg itself), where
`scripts/push_wordpress.py --sync-favicons` picks it up and ships it to the
public_html root. The <link> block that references these files is centralized
in `wordpress/brand_tokens.py::get_favicon_head_snippet()`.

Requires: playwright (`pip install playwright && playwright install chromium`),
Pillow. Both are already in requirements.txt.

Usage:
    python3 scripts/generate_favicons.py
    python3 scripts/generate_favicons.py --padding 0.14 --render-px 1024
"""

import argparse
import base64
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SVG_PATH = PROJECT_ROOT / "web" / "gg-logo.svg"
OUT_DIR = PROJECT_ROOT / "web"

WARM_PAPER = "#f5efe6"
GLYPH_VIEWBOX = (1888, 2240)  # width, height — see gg-logo.svg viewBox

ICO_SIZES = (16, 32, 48)
PNG_SIZES = {
    "favicon-16.png": 16,
    "favicon-32.png": 32,
    "apple-touch-icon.png": 180,
    "icon-192.png": 192,
    "icon-512.png": 512,
}


def render_master(render_px: int, padding_frac: float) -> Image.Image:
    """Screenshot the SVG centered on a warm-paper square via headless Chromium."""
    from playwright.sync_api import sync_playwright

    svg_text = SVG_PATH.read_text()
    svg_b64 = base64.b64encode(svg_text.encode("utf-8")).decode("ascii")

    glyph_w, glyph_h = GLYPH_VIEWBOX
    pad = render_px * padding_frac
    avail = render_px - 2 * pad
    scale = min(avail / glyph_w, avail / glyph_h)
    draw_w, draw_h = glyph_w * scale, glyph_h * scale
    left, top = (render_px - draw_w) / 2, (render_px - draw_h) / 2

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  html,body {{ margin:0; padding:0; }}
  .square {{ width:{render_px}px; height:{render_px}px; background:{WARM_PAPER};
             position:relative; overflow:hidden; }}
  .square img {{ position:absolute; left:{left}px; top:{top}px;
                 width:{draw_w}px; height:{draw_h}px; }}
</style></head>
<body><div class="square"><img src="data:image/svg+xml;base64,{svg_b64}"></div></body></html>"""

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "render.html"
        html_path.write_text(html)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(
                viewport={"width": render_px, "height": render_px},
                device_scale_factor=1,
            )
            page.goto(html_path.as_uri())
            el = page.query_selector(".square")
            out_path = Path(tmp) / "master.png"
            el.screenshot(path=str(out_path))
            browser.close()
        return Image.open(out_path).convert("RGBA")


def build_set(master: Image.Image, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    def resized(size: int) -> Image.Image:
        return master.resize((size, size), Image.LANCZOS)

    for name, size in PNG_SIZES.items():
        img = resized(size)
        if name == "apple-touch-icon.png":
            # iOS fills transparency with black — flatten onto warm-paper.
            bg = Image.new("RGB", img.size, WARM_PAPER)
            bg.paste(img, mask=img.split()[3])
            bg.save(out_dir / name)
        else:
            img.save(out_dir / name)
        print(f"  wrote {name} ({size}x{size})")

    ico_path = out_dir / "favicon.ico"
    resized(max(ICO_SIZES)).save(
        ico_path, format="ICO", sizes=[(s, s) for s in ICO_SIZES]
    )
    print(f"  wrote favicon.ico ({'/'.join(str(s) for s in ICO_SIZES)})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-px", type=int, default=1024,
                         help="Master render resolution (default: 1024)")
    parser.add_argument("--padding", type=float, default=0.14,
                         help="Padding fraction on each side (default: 0.14)")
    parser.add_argument("--out-dir", default=str(OUT_DIR),
                         help="Output directory (default: web/)")
    args = parser.parse_args()

    if not SVG_PATH.exists():
        raise SystemExit(f"✗ Not found: {SVG_PATH}")

    print(f"Rendering {SVG_PATH} at {args.render_px}px (padding {args.padding})...")
    master = render_master(args.render_px, args.padding)
    build_set(master, Path(args.out_dir))
    print(f"✓ Favicon set written to {args.out_dir}")


if __name__ == "__main__":
    main()
