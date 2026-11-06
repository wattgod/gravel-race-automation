#!/usr/bin/env python3
"""Regenerate the pricing constants block in web/training-plans-form.js
(and the two-step intake's step 1, web/training-plans-start.js) from
data/pricing.json — the "generated JS constant for pages" that
docs/specs/goals-2027-funnel-spec.md D18 asks for.

training-plans-form.js is a hand-maintained static file (deployed by SCP,
not by the wordpress/generate_*.py pipeline — see repo CLAUDE.md), so this
script rewrites only the block between the GG_PRICING_CONSTANTS_START/END
markers rather than regenerating the whole file.

Usage:
    python scripts/generate_pricing_js.py            # rewrite the block
    python scripts/generate_pricing_js.py --check     # exit 1 if it's stale
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FORM_JS_PATH = PROJECT_ROOT / "web" / "training-plans-form.js"
# Two-step intake (2026-10-23): step 1 quotes the total before checkout.
# Step 2 shows only the server's price_display, so it carries no block.
START_JS_PATH = PROJECT_ROOT / "web" / "training-plans-start.js"
JS_PATHS = (FORM_JS_PATH, START_JS_PATH)

sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))
from pricing import (  # data/pricing.json (D18)
    MIN_WEEKS,
    PRICE_PER_WEEK,
)

START_MARKER = "  // GG_PRICING_CONSTANTS_START\n"
END_MARKER = "  // GG_PRICING_CONSTANTS_END\n"


def build_block() -> str:
    price_per_week = int(PRICE_PER_WEEK.replace("$", ""))
    return (
        f"  var PRICE_PER_WEEK = {price_per_week};\n"
        f"  var MIN_WEEKS = {MIN_WEEKS};\n"
    )


def render(text: str, path: Path = FORM_JS_PATH) -> str:
    if START_MARKER not in text or END_MARKER not in text:
        raise RuntimeError(
            f"GG_PRICING_CONSTANTS markers not found in {path}"
        )
    before, rest = text.split(START_MARKER, 1)
    _, after = rest.split(END_MARKER, 1)
    return before + START_MARKER + build_block() + END_MARKER + after


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                         help="exit 1 if the file is not up to date, without writing")
    args = parser.parse_args()

    stale = []
    for path in JS_PATHS:
        current = path.read_text()
        updated = render(current, path)
        if current == updated:
            continue
        stale.append(path)
        if not args.check:
            path.write_text(updated)
            print(f"Updated pricing block in {path}")

    if args.check:
        if stale:
            for path in stale:
                print(f"STALE: {path} pricing block does not match data/pricing.json")
            return 1
        print("OK: pricing blocks are up to date")
        return 0
    if not stale:
        print("Pricing blocks already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
