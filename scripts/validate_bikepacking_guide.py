#!/usr/bin/env python3
"""Validate the WS-G bikepacking guide contract before generation or review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONTENT = PROJECT_ROOT / "guide" / "bikepacking-guide-content.json"
DEFAULT_SCHEMA = PROJECT_ROOT / "guide" / "bikepacking-guide-content.schema.json"

R1_BANNED = (
    "when i raced",
    "my tour divide",
    "i finished the",
    "i've raced",
    "my time on the divide",
)
R2_BANNED = (
    "12-week ultra",
    "12 week ultra",
    "twelve-week ultra",
    "twelve week ultra",
)
R4_BANNED = (
    "sleep deprivation",
    "sleep-deprived",
    "ride through the night",
    "skip sleep",
    "train on no sleep",
    "without sleep",
    "all-nighter",
)


def _path(error) -> str:
    parts = [str(part) for part in error.absolute_path]
    return ".".join(parts) if parts else "<root>"


def _customer_copy(value, *, in_sources: bool = False):
    """Yield customer-visible strings while excluding the R5 audit sidecar."""
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _customer_copy(child, in_sources=in_sources or key == "sources")
    elif isinstance(value, list):
        for child in value:
            yield from _customer_copy(child, in_sources=in_sources)
    elif isinstance(value, str) and not in_sources:
        yield value


def validate_content(content_path: Path = DEFAULT_CONTENT,
                     schema_path: Path = DEFAULT_SCHEMA) -> list[str]:
    """Return all schema and WS-G semantic errors."""
    data = json.loads(content_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = [
        f"{_path(error)}: {error.message}"
        for error in sorted(
            Draft202012Validator(schema).iter_errors(data),
            key=lambda error: list(error.absolute_path),
        )
    ]

    chapters = data.get("chapters", [])
    numbers = [chapter.get("number") for chapter in chapters]
    if numbers != list(range(1, 9)):
        errors.append(f"chapters: numbers must be ordered 1-8, got {numbers}")

    ids = [chapter.get("id") for chapter in chapters]
    if len(ids) != len(set(ids)):
        errors.append("chapters: chapter ids must be unique")

    for chapter in chapters:
        number = chapter.get("number")
        expected_gated = isinstance(number, int) and number >= 4
        if chapter.get("gated") is not expected_gated:
            errors.append(
                f"chapter {number}: gated must be {expected_gated} "
                "(chapters 1-3 free; chapters 4-8 gated)"
            )
        for section in chapter.get("sections", []):
            for block in section.get("blocks", []):
                if block.get("type") != "data_table":
                    continue
                width = len(block.get("headers", []))
                for row_index, row in enumerate(block.get("rows", []), 1):
                    if len(row) != width:
                        errors.append(
                            f"{section.get('id')}: data_table row {row_index} "
                            f"has {len(row)} cells; expected {width}"
                        )

    copy = "\n".join(_customer_copy(data)).lower()
    for rule, phrases in (("R1", R1_BANNED), ("R2", R2_BANNED), ("R4", R4_BANNED)):
        for phrase in phrases:
            if phrase in copy:
                errors.append(f"{rule}: banned phrase in customer copy: {phrase!r}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", type=Path, default=DEFAULT_CONTENT)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()

    try:
        errors = validate_content(args.content, args.schema)
    except (OSError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"{len(errors)} bikepacking guide validation error(s)")
        return 1

    print("PASS: bikepacking guide schema and WS-G content guards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
