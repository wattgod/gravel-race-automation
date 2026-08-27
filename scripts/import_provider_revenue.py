#!/usr/bin/env python3
"""Validate or apply reconciled Gravel God provider revenue files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mission_control.services.provider_ingestion import (  # noqa: E402
    ProviderIngestionError,
    apply_bundle,
    build_trainingpeaks_bundle,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate reconciled TrainingPeaks coaching, payout, lifecycle, and "
            "marketplace-control files. Dry-run is the default."
        )
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing the five sanitized provider CSV files",
    )
    parser.add_argument(
        "--observed-at",
        help="ISO-8601 observation timestamp; defaults to current UTC",
    )
    parser.add_argument("--receipt", help="Optional JSON receipt path")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--skip-2026-08-27-controls",
        action="store_true",
        help="Disable the pinned Gravel God baseline controls; intended only for fixtures/tests",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write idempotent rows to the migrated live database",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help="Required with --apply; must equal APPLY_PROVIDER_TRUTH",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size < 1:
        raise ProviderIngestionError("--batch-size must be at least 1")
    if args.apply and args.confirm != "APPLY_PROVIDER_TRUTH":
        raise ProviderIngestionError(
            "--apply requires --confirm APPLY_PROVIDER_TRUTH; no database write was attempted"
        )

    bundle = build_trainingpeaks_bundle(
        args.input_dir,
        observed_at=args.observed_at,
        enforce_2026_08_27_controls=not args.skip_2026_08_27_controls,
    )
    result = apply_bundle(bundle, batch_size=args.batch_size) if args.apply else bundle.summary()
    result["mode"] = "apply" if args.apply else "dry-run"
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.receipt:
        receipt = Path(args.receipt).expanduser().resolve()
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProviderIngestionError as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2) from None
