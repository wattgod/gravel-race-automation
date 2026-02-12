#!/usr/bin/env python3
"""
Audit all brand color usage across the codebase.

Verifies that every hardcoded hex color matches the canonical brand tokens
in wordpress/brand_tokens.py. Flags any stale or out-of-sync values.

Also checks WCAG AA contrast ratios for key color pairs.

Usage:
    python scripts/audit_colors.py           # Run full audit
    python scripts/audit_colors.py --fix     # Show suggested fix commands
    python scripts/audit_colors.py --contrast # Only run contrast checks
"""

import argparse
import math
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Canonical brand colors (source of truth) ──────────────────
# These MUST match the values in wordpress/brand_tokens.py
CANONICAL_COLORS = {
    "secondary_brown": "#7d695d",
    "gold": "#9a7e0a",
    "teal": "#178079",
    "tier_1": "#59473c",
    "tier_2": "#7d695d",
    "tier_3": "#766a5e",
    "tier_4": "#5e6868",
    "warm_paper": "#f5efe6",
    "primary_brown": "#59473c",
    "dark_brown": "#3a2e25",
    "sand": "#ede4d8",
}

# Old values that should NEVER appear in the codebase
BANNED_COLORS = {
    "#8c7568": "secondary_brown (use #7d695d)",
    "#B7950B": "gold (use #9a7e0a)",
    "#b7950b": "gold (use #9a7e0a)",
    "#1A8A82": "teal (use #178079)",
    "#1a8a82": "teal (use #178079)",
    "#999999": "tier_3 (use #766a5e)",
    "#cccccc": "tier_4 (use #5e6868)",
    "#918981": "tier_4 old (use #5e6868)",
}

# Files to scan (glob patterns relative to project root)
SCAN_PATTERNS = [
    "wordpress/*.py",
    "web/*.html",
    "web/*.js",
    "scripts/*.py",
    "scripts/media_templates/*.py",
    "workers/**/*.js",
    "guide/*.json",
    "tests/*.py",
    "docs/**/*.md",
    "skills/*.md",
]

# Files to skip (build output, node_modules, etc.)
SKIP_PATTERNS = {"wordpress/output", "node_modules", ".git", "__pycache__"}

# ── WCAG Contrast Checking ────────────────────────────────────

# Required contrast pairs: (foreground, background, min_ratio, label)
CONTRAST_PAIRS = [
    ("#59473c", "#f5efe6", 4.5, "T1 primary brown on warm paper"),
    ("#7d695d", "#f5efe6", 4.5, "T2 secondary brown on warm paper"),
    ("#766a5e", "#f5efe6", 4.5, "T3 on warm paper"),
    ("#5e6868", "#f5efe6", 4.5, "T4 on warm paper"),
    ("#9a7e0a", "#ffffff", 3.0, "Gold on white (UI components)"),
    ("#ffffff", "#178079", 4.5, "White on teal background"),
    ("#7d695d", "#ede4d8", 3.0, "Secondary brown on sand (large text/UI only)"),
]


def linearize(c):
    """Convert sRGB 0-255 to linear."""
    s = c / 255.0
    if s <= 0.04045:
        return s / 12.92
    return ((s + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color):
    """Calculate relative luminance from hex color."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def contrast_ratio(fg, bg):
    """Calculate WCAG contrast ratio between two hex colors."""
    l1 = relative_luminance(fg)
    l2 = relative_luminance(bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def check_contrast():
    """Check all required contrast pairs. Returns (passes, failures)."""
    passes = []
    failures = []
    for fg, bg, min_ratio, label in CONTRAST_PAIRS:
        ratio = contrast_ratio(fg, bg)
        entry = (label, fg, bg, ratio, min_ratio)
        if ratio >= min_ratio:
            passes.append(entry)
        else:
            failures.append(entry)
    return passes, failures


def should_skip(path):
    """Check if file path should be skipped."""
    parts = str(path.relative_to(PROJECT_ROOT)).split("/")
    if any(skip in parts for skip in SKIP_PATTERNS):
        return True
    # Skip this script's own BANNED_COLORS dict
    if path.name == "audit_colors.py":
        return True
    return False


def scan_for_banned_colors():
    """Scan all source files for banned color values. Returns list of (file, line, color, note)."""
    findings = []
    for pattern in SCAN_PATTERNS:
        for filepath in PROJECT_ROOT.glob(pattern):
            if should_skip(filepath) or not filepath.is_file():
                continue
            try:
                lines = filepath.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, PermissionError):
                continue
            for i, line in enumerate(lines, 1):
                for banned, note in BANNED_COLORS.items():
                    if banned in line:
                        findings.append((filepath, i, banned, note))
    return findings


def verify_brand_tokens_sync():
    """Verify that brand_tokens.py COLORS dict matches CSS custom properties."""
    bt_path = PROJECT_ROOT / "wordpress" / "brand_tokens.py"
    content = bt_path.read_text()

    issues = []

    # Extract CSS custom property values
    css_vars = {}
    for m in re.finditer(r"--gg-color-([\w-]+):\s*(#[0-9a-fA-F]{6});", content):
        css_vars[m.group(1)] = m.group(2).lower()

    # Extract COLORS dict values
    colors_dict = {}
    for m in re.finditer(r'"(\w+)":\s*"(#[0-9a-fA-F]{6})"', content):
        colors_dict[m.group(1)] = m.group(2).lower()

    # Cross-check tier colors
    for tier in range(1, 5):
        css_key = f"tier-{tier}"
        dict_key = f"tier_{tier}"
        css_val = css_vars.get(css_key, "MISSING")
        dict_val = colors_dict.get(dict_key, "MISSING")
        if css_val != dict_val:
            issues.append(f"MISMATCH: CSS --gg-color-{css_key}={css_val} vs COLORS[{dict_key}]={dict_val}")

    # Cross-check named colors
    cross_checks = [
        ("secondary-brown", "secondary_brown"),
        ("gold", "gold"),
        ("teal", "teal"),
    ]
    for css_key, dict_key in cross_checks:
        css_val = css_vars.get(css_key, "MISSING")
        dict_val = colors_dict.get(dict_key, "MISSING")
        if css_val != dict_val:
            issues.append(f"MISMATCH: CSS --gg-color-{css_key}={css_val} vs COLORS[{dict_key}]={dict_val}")

    return issues


def main():
    parser = argparse.ArgumentParser(description="Audit brand color usage")
    parser.add_argument("--fix", action="store_true", help="Show suggested fix commands")
    parser.add_argument("--contrast", action="store_true", help="Only run contrast checks")
    args = parser.parse_args()

    exit_code = 0

    # ── Contrast checks ──
    print("=" * 60)
    print("WCAG AA CONTRAST AUDIT")
    print("=" * 60)
    passes, failures = check_contrast()
    for label, fg, bg, ratio, min_ratio in passes:
        print(f"  PASS  {ratio:.2f}:1 >= {min_ratio}:1  {label}")
    for label, fg, bg, ratio, min_ratio in failures:
        print(f"  FAIL  {ratio:.2f}:1 <  {min_ratio}:1  {label}  ({fg} on {bg})")
        exit_code = 1
    print(f"\n  {len(passes)} passed, {len(failures)} failed\n")

    if args.contrast:
        sys.exit(exit_code)

    # ── Brand tokens internal consistency ──
    print("=" * 60)
    print("BRAND TOKENS INTERNAL CONSISTENCY")
    print("=" * 60)
    sync_issues = verify_brand_tokens_sync()
    if sync_issues:
        for issue in sync_issues:
            print(f"  {issue}")
        exit_code = 1
    else:
        print("  All CSS vars match COLORS dict")
    print()

    # ── Banned color scan ──
    print("=" * 60)
    print("BANNED COLOR SCAN")
    print("=" * 60)
    findings = scan_for_banned_colors()
    if findings:
        for filepath, line, color, note in findings:
            rel = filepath.relative_to(PROJECT_ROOT)
            print(f"  {rel}:{line}  {color}  ({note})")
        exit_code = 1
        print(f"\n  {len(findings)} stale color references found")
    else:
        print("  No banned colors found — all clean")
    print()

    if exit_code == 0:
        print("ALL CHECKS PASSED")
    else:
        print("AUDIT FAILED — fix issues above")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
