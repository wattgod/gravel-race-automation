#!/usr/bin/env python3
"""WordPress Page Weight Audit — analyze CSS/JS/HTML size for key pages.

Usage:
    python scripts/audit_page_weight.py             # Terminal report
    python scripts/audit_page_weight.py --json      # JSON output for CI
    python scripts/audit_page_weight.py --verbose   # Show individual asset URLs

Thresholds (configurable via constants):
    - >15 external CSS files → WARN (AIOSEO bloat)
    - >500KB total HTML → WARN
    - >10 external JS files → WARN
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

SITE_URL = "https://gravelgodcycling.com"

# Pages to audit
PAGES = {
    "Homepage": "/",
    "Search Widget": "/gravel-races/",
    "Race: Unbound 200": "/race/unbound-200/",
    "Race: Mid South": "/race/mid-south/",
    "Race: Belgian Waffle Ride": "/race/belgian-waffle-ride/",
    "Prep Kit: Unbound 200": "/race/unbound-200/prep-kit/",
    "About": "/about/",
    "Methodology": "/race/methodology/",
}

# Thresholds
MAX_CSS_FILES = 15
MAX_JS_FILES = 10
MAX_HTML_KB = 500


class AssetCounter(HTMLParser):
    """Parse HTML to count external CSS, JS, inline CSS/JS, and images."""

    def __init__(self):
        super().__init__()
        self.css_files = []
        self.js_files = []
        self.inline_css_size = 0
        self.inline_js_size = 0
        self.image_count = 0
        self._in_style = False
        self._in_script = False
        self._current_data = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if tag == "link" and attr_dict.get("rel") == "stylesheet":
            href = attr_dict.get("href", "")
            if href:
                self.css_files.append(href)
        elif tag == "script":
            src = attr_dict.get("src", "")
            if src:
                self.js_files.append(src)
            else:
                self._in_script = True
                self._current_data = []
        elif tag == "style":
            self._in_style = True
            self._current_data = []
        elif tag == "img":
            self.image_count += 1

    def handle_endtag(self, tag):
        if tag == "style" and self._in_style:
            self._in_style = False
            content = "".join(self._current_data)
            self.inline_css_size += len(content.encode("utf-8"))
        elif tag == "script" and self._in_script:
            self._in_script = False
            content = "".join(self._current_data)
            self.inline_js_size += len(content.encode("utf-8"))

    def handle_data(self, data):
        if self._in_style or self._in_script:
            self._current_data.append(data)


def fmt_kb(n: int) -> str:
    """Format bytes as KB."""
    return f"{n / 1024:.1f}KB"


def audit_page(name: str, path: str, verbose: bool = False) -> dict:
    """Fetch a page and analyze its weight."""
    url = urljoin(SITE_URL, path)
    try:
        resp = requests.get(url, timeout=30, headers={
            "User-Agent": "GravelGod-Audit/1.0"
        })
        resp.raise_for_status()
    except Exception as e:
        return {"name": name, "path": path, "error": str(e)}

    html = resp.text
    html_size = len(html.encode("utf-8"))

    parser = AssetCounter()
    parser.feed(html)

    warnings = []
    if len(parser.css_files) > MAX_CSS_FILES:
        warnings.append(f"CSS files: {len(parser.css_files)} (max {MAX_CSS_FILES})")
    if len(parser.js_files) > MAX_JS_FILES:
        warnings.append(f"JS files: {len(parser.js_files)} (max {MAX_JS_FILES})")
    if html_size > MAX_HTML_KB * 1024:
        warnings.append(f"HTML size: {fmt_kb(html_size)} (max {MAX_HTML_KB}KB)")

    result = {
        "name": name,
        "path": path,
        "html_size": html_size,
        "css_files": len(parser.css_files),
        "js_files": len(parser.js_files),
        "inline_css_size": parser.inline_css_size,
        "inline_js_size": parser.inline_js_size,
        "image_count": parser.image_count,
        "warnings": warnings,
    }

    if verbose:
        result["css_urls"] = parser.css_files
        result["js_urls"] = parser.js_files

    return result


def print_report(results: list[dict], verbose: bool = False):
    """Print formatted terminal report."""
    print(f"\n{'=' * 70}")
    print(f"  WORDPRESS PAGE WEIGHT AUDIT")
    print(f"{'=' * 70}\n")

    total_warnings = 0
    for r in results:
        if "error" in r:
            print(f"  {r['name']}: ERROR — {r['error']}\n")
            continue

        status = "WARN" if r["warnings"] else "OK"
        total_warnings += len(r["warnings"])

        print(f"  {r['name']} ({r['path']})")
        print(f"    HTML: {fmt_kb(r['html_size'])}  |  "
              f"CSS: {r['css_files']} files + {fmt_kb(r['inline_css_size'])} inline  |  "
              f"JS: {r['js_files']} files + {fmt_kb(r['inline_js_size'])} inline  |  "
              f"Images: {r['image_count']}  |  [{status}]")

        for w in r["warnings"]:
            print(f"    \u26a0  {w}")

        if verbose and r.get("css_urls"):
            print(f"    CSS assets:")
            for url in r["css_urls"]:
                short = url.split("?")[0][-60:]
                print(f"      {short}")

        if verbose and r.get("js_urls"):
            print(f"    JS assets:")
            for url in r["js_urls"]:
                short = url.split("?")[0][-60:]
                print(f"      {short}")

        print()

    print(f"{'─' * 70}")
    print(f"  Total pages: {len(results)}  |  Warnings: {total_warnings}")
    if total_warnings:
        print(f"  Thresholds: CSS>{MAX_CSS_FILES} files, JS>{MAX_JS_FILES} files, HTML>{MAX_HTML_KB}KB")
    print(f"{'─' * 70}\n")


def main():
    parser = argparse.ArgumentParser(description="WordPress Page Weight Audit")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", action="store_true", help="Show individual asset URLs")
    args = parser.parse_args()

    results = []
    for name, path in PAGES.items():
        results.append(audit_page(name, path, verbose=args.verbose))

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results, verbose=args.verbose)

    # Exit 1 if any warnings
    has_warnings = any(r.get("warnings") for r in results)
    sys.exit(1 if has_warnings else 0)


if __name__ == "__main__":
    main()
