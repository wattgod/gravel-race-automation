#!/usr/bin/env python3
"""Regenerate the pricing constants block in web/training-plans-form.js
from data/pricing.json — the "generated JS constant for pages" that
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

sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))
from pricing import (  # data/pricing.json (D18)
    MIN_WEEKS,
    PRICE_CAP,
    PRICE_PER_WEEK,
)

START_MARKER = "  // GG_PRICING_CONSTANTS_START\n"
END_MARKER = "  // GG_PRICING_CONSTANTS_END\n"


def build_block() -> str:
    price_per_week = int(PRICE_PER_WEEK.replace("$", ""))
    price_cap = int(PRICE_CAP.replace("$", ""))
    return (
        f"  var PRICE_PER_WEEK = {price_per_week};\n"
        f"  var PRICE_CAP = {price_cap};\n"
        f"  var MIN_WEEKS = {MIN_WEEKS};\n"
    )


def render(text: str) -> str:
    if START_MARKER not in text or END_MARKER not in text:
        raise RuntimeError(
            f"GG_PRICING_CONSTANTS markers not found in {FORM_JS_PATH}"
        )
    before, rest = text.split(START_MARKER, 1)
    _, after = rest.split(END_MARKER, 1)
    return before + START_MARKER + build_block() + END_MARKER + after


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                         help="exit 1 if the file is not up to date, without writing")
    args = parser.parse_args()

    current = FORM_JS_PATH.read_text()
    updated = render(current)

    if args.check:
        if current != updated:
            print(f"STALE: {FORM_JS_PATH} pricing block does not match data/pricing.json")
            return 1
        print("OK: pricing block is up to date")
        return 0

    if current != updated:
        FORM_JS_PATH.write_text(updated)
        print(f"Updated pricing block in {FORM_JS_PATH}")
    else:
        print("Pricing block already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
