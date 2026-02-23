#!/usr/bin/env python3
"""Extract inline CSS from gravel-race-search.html into an external cacheable file.

Reads the search widget HTML, extracts the single <style> block, writes it to
a content-hashed CSS file (gg-search.{hash}.css), and replaces the inline
<style> with a <link rel="stylesheet"> tag.

This reduces the HTML payload from ~198KB to ~63KB and makes the CSS
browser-cacheable on subsequent page loads.

Usage:
    python scripts/extract_widget_css.py           # Extract and rewrite
    python scripts/extract_widget_css.py --dry-run  # Show what would change
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WIDGET_HTML = PROJECT_ROOT / "web" / "gravel-race-search.html"
CSS_OUTPUT_DIR = PROJECT_ROOT / "web"


def extract_css(html_content: str):
    """Extract the <style>...</style> block from the widget HTML.

    Returns (css_content, html_before_style, html_after_style) or raises ValueError.
    """
    # Match the single <style> block (non-greedy)
    match = re.search(
        r'([ \t]*)<style>\n(.*?)\n[ \t]*</style>',
        html_content,
        re.DOTALL,
    )
    if not match:
        raise ValueError("No <style> block found in widget HTML")

    indent = match.group(1)
    css_content = match.group(2)
    start = match.start()
    end = match.end()

    html_before = html_content[:start]
    html_after = html_content[end:]

    return css_content, html_before, html_after, indent


def main():
    parser = argparse.ArgumentParser(description="Extract widget CSS to external file")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing")
    args = parser.parse_args()

    if not WIDGET_HTML.exists():
        print(f"✗ Widget HTML not found: {WIDGET_HTML}")
        return 1

    html_content = WIDGET_HTML.read_text()
    original_size = len(html_content.encode("utf-8"))

    try:
        css_content, html_before, html_after, indent = extract_css(html_content)
    except ValueError as e:
        print(f"✗ {e}")
        return 1

    css_size = len(css_content.encode("utf-8"))

    # Compute content hash for cache-busted filename
    css_hash = hashlib.md5(css_content.encode()).hexdigest()[:8]
    css_filename = f"gg-search.{css_hash}.css"
    css_path = CSS_OUTPUT_DIR / css_filename

    # Build the <link> replacement
    # The widget is served from /wp-content/uploads/ on WordPress
    link_tag = f'{indent}<link rel="stylesheet" href="/wp-content/uploads/{css_filename}">'

    # Reconstruct the HTML with the <link> tag instead of inline <style>
    new_html = html_before + link_tag + html_after
    new_size = len(new_html.encode("utf-8"))

    print(f"CSS extraction summary:")
    print(f"  Original HTML: {original_size:,} bytes")
    print(f"  Extracted CSS: {css_size:,} bytes ({css_filename})")
    print(f"  New HTML:      {new_size:,} bytes")
    print(f"  Reduction:     {original_size - new_size:,} bytes ({(original_size - new_size) / original_size * 100:.0f}%)")

    if args.dry_run:
        print(f"\n  [dry run] Would write: {css_path}")
        print(f"  [dry run] Would rewrite: {WIDGET_HTML}")
        return 0

    # Remove old gg-search.*.css files
    for old in CSS_OUTPUT_DIR.glob("gg-search.*.css"):
        old.unlink()
        print(f"  Removed old: {old.name}")

    # Write the CSS file
    css_path.write_text(css_content + "\n")
    print(f"  ✓ Wrote CSS: {css_path}")

    # Rewrite the HTML
    WIDGET_HTML.write_text(new_html)
    print(f"  ✓ Rewrote HTML: {WIDGET_HTML}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
