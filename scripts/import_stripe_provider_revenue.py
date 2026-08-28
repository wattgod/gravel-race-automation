#!/usr/bin/env python3
"""Validate or apply a privacy-safe standalone Stripe reconciliation receipt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mission_control.services.provider_ingestion import (
    ProviderIngestionError,
)
from mission_control.services.stripe_provider_ingestion import (
    apply_stripe_bundle,
    build_stripe_bundle,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and normalize one authenticated, PII-safe Stripe provider "
            "receipt. Dry-run is the default."
        )
    )
    parser.add_argument(
        "--receipt-file", required=True, help="Sanitized Stripe JSON receipt"
    )
    parser.add_argument(
        "--output-receipt", help="Optional dry-run/apply JSON receipt path"
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--skip-2026-08-27-controls",
        action="store_true",
        help="Disable the pinned live baseline; intended only for fixtures or a reviewed rollover",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write idempotent rows to the migrated Mission Control database",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help="Required with --apply; must equal APPLY_STRIPE_PROVIDER_TRUTH",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size < 1:
        raise ProviderIngestionError("--batch-size must be at least 1")
    if args.apply and args.confirm != "APPLY_STRIPE_PROVIDER_TRUTH":
        raise ProviderIngestionError(
            "--apply requires --confirm APPLY_STRIPE_PROVIDER_TRUTH; "
            "no database write was attempted"
        )
    bundle = build_stripe_bundle(
        args.receipt_file,
        enforce_2026_08_27_controls=not args.skip_2026_08_27_controls,
    )
    result = (
        apply_stripe_bundle(bundle, batch_size=args.batch_size)
        if args.apply
        else bundle.summary()
    )
    result["mode"] = "apply" if args.apply else "dry-run"
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output_receipt:
        output = Path(args.output_receipt).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProviderIngestionError as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2) from None
