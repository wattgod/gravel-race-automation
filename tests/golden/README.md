# Golden Files

Reference outputs that represent known-good quality standards.

## Purpose

Golden files serve as:
1. **Quality benchmarks** - Compare new outputs against these
2. **Regression tests** - Ensure quality doesn't degrade
3. **Examples** - Show what good output looks like

## Adding Golden Files

When you have a race output that:
- Passes all quality gates
- Has been manually reviewed
- Represents the target quality standard

Copy it here:
- `{race-folder}-raw.md` - Research dump
- `{race-folder}-brief.md` - Race brief
- `{race-folder}.json` - Final JSON

## Usage

Tests in `test_quality_gates.py` compare new outputs against golden files to ensure quality standards are maintained.

