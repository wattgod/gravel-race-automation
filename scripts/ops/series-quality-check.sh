#!/usr/bin/env bash
# series-quality-check.sh — Validates series hub page quality
#
# Run after regenerating series hub pages to catch known shortcuts.
# Encodes lessons from LESSONS_LEARNED.md Shortcuts #20-26.
#
# Usage: bash scripts/ops/series-quality-check.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUTPUT_DIR="$PROJECT_ROOT/wordpress/output/race/series"
GENERATOR="$PROJECT_ROOT/wordpress/generate_series_hubs.py"

ERRORS=0
WARNINGS=0

error() { echo "  ERROR: $1"; ((ERRORS++)); }
warn()  { echo "  WARN:  $1"; ((WARNINGS++)); }

echo "=== Series Hub Quality Check ==="
echo ""

# ── Check 1: Generator source has no hardcoded year ──
echo "[1/7] Checking generator for hardcoded year..."
YEAR_HITS=$(grep -n "2026" "$GENERATOR" | grep -v "^.*#" | grep -v "CURRENT_YEAR" || true)
if [ -n "$YEAR_HITS" ]; then
    error "Hardcoded '2026' found in generator (non-comment lines):"
    echo "$YEAR_HITS" | while read -r line; do echo "    $line"; done
else
    echo "  OK: No hardcoded year in generator source"
fi

# ── Check 2: No esc() inside JSON-LD blocks ──
echo "[2/7] Checking for esc() in JSON-LD blocks..."
IN_JSONLD=0
ESC_IN_JSONLD=0
while IFS= read -r line; do
    if echo "$line" | grep -q "application/ld+json"; then
        IN_JSONLD=1
    elif [ $IN_JSONLD -eq 1 ] && echo "$line" | grep -q "</script>"; then
        IN_JSONLD=0
    elif [ $IN_JSONLD -eq 1 ] && echo "$line" | grep -q '{esc('; then
        error "esc() used inside JSON-LD template: $line"
        ESC_IN_JSONLD=1
    fi
done < "$GENERATOR"
if [ $ESC_IN_JSONLD -eq 0 ]; then
    echo "  OK: No esc() in JSON-LD blocks"
fi

# ── Check 3: _build_faq_pairs exists (DRY check) ──
echo "[3/7] Checking FAQ DRY compliance..."
if ! grep -q "def _build_faq_pairs(" "$GENERATOR"; then
    error "Missing _build_faq_pairs() — FAQ logic is likely duplicated"
else
    FAQ_CALLS=$(grep -c "_build_faq_pairs(" "$GENERATOR" || true)
    if [ "$FAQ_CALLS" -lt 3 ]; then
        error "Expected _build_faq_pairs to be called by both FAQ builders (found $FAQ_CALLS refs)"
    else
        echo "  OK: FAQ logic uses shared _build_faq_pairs()"
    fi
fi

# ── Check 4: All generated pages have valid JSON-LD ──
echo "[4/7] Validating JSON-LD in generated pages..."
if [ ! -d "$OUTPUT_DIR" ]; then
    error "Output directory $OUTPUT_DIR does not exist — run generator first"
else
    for html_file in "$OUTPUT_DIR"/*/index.html; do
        slug=$(basename "$(dirname "$html_file")")
        # Extract JSON-LD blocks and validate
        python3 -c "
import json, sys
html = open('$html_file').read()
start_tag = '<script type=\"application/ld+json\">'
end_tag = '</script>'
pos = 0
block_num = 0
while True:
    start = html.find(start_tag, pos)
    if start == -1: break
    cs = start + len(start_tag)
    end = html.find(end_tag, cs)
    if end == -1: break
    block = html[cs:end].strip()
    try:
        parsed = json.loads(block)
        if '&#' in block or '&amp;' in block:
            print(f'ENTITY: block {block_num} has HTML entities')
            sys.exit(1)
    except json.JSONDecodeError as e:
        print(f'INVALID: block {block_num}: {e}')
        sys.exit(1)
    block_num += 1
    pos = end + len(end_tag)
if block_num == 0:
    print('NO_BLOCKS')
    sys.exit(1)
print(f'OK:{block_num}')
" 2>&1
        result=$?
        if [ $result -ne 0 ]; then
            error "JSON-LD validation failed for $slug"
        else
            echo "  OK: $slug JSON-LD valid"
        fi
    done
fi

# ── Check 5: FAQ HTML/JSON-LD parity ──
echo "[5/7] Checking FAQ HTML/JSON-LD question parity..."
for html_file in "$OUTPUT_DIR"/*/index.html; do
    slug=$(basename "$(dirname "$html_file")")
    python3 -c "
import json
html = open('$html_file').read()
# Count HTML FAQ questions
faq_start = html.find('class=\"gg-series-faq\"')
if faq_start == -1:
    # No FAQ section — that's OK for series with no data
    exit(0)
html_count = html[faq_start:].count('<summary>')

# Count JSON-LD FAQ questions
start_tag = '<script type=\"application/ld+json\">'
end_tag = '</script>'
pos = 0
jsonld_count = 0
while True:
    start = html.find(start_tag, pos)
    if start == -1: break
    cs = start + len(start_tag)
    end = html.find(end_tag, cs)
    if end == -1: break
    block = html[cs:end].strip()
    try:
        parsed = json.loads(block)
        if parsed.get('@type') == 'FAQPage':
            jsonld_count = len(parsed.get('mainEntity', []))
            break
    except json.JSONDecodeError:
        pass
    pos = end + len(end_tag)

if html_count > 0 and jsonld_count > 0 and html_count != jsonld_count:
    print(f'MISMATCH: HTML={html_count} JSON-LD={jsonld_count}')
    exit(1)
print(f'OK: {html_count} questions')
" 2>&1
    result=$?
    if [ $result -ne 0 ]; then
        error "FAQ parity failed for $slug"
    else
        echo "  OK: $slug FAQ parity"
    fi
done

# ── Check 6: Named constants (no raw magic numbers in key spots) ──
echo "[6/7] Checking for magic numbers in generator..."
MAGIC_HITS=$(grep -nE '\[:([0-9]+)\]|<= ?[0-9]{2,}|> ?[0-9]{2,}' "$GENERATOR" | \
    grep -v "CURRENT_YEAR\|MAX_\|TIMELINE_\|MATRIX_\|BAR_CHART_\|MAP_LABEL_\|# \|def \|MONTH_ORDER\|RADAR_\|POLYGON_\|US_OUTLINE\|viewBox\|vw=\|vh=" | \
    grep -vE '^\s*#' || true)
if [ -n "$MAGIC_HITS" ]; then
    warn "Potential magic numbers found (review manually):"
    # Use process substitution to avoid pipefail issues
    while IFS= read -r line; do echo "    $line"; done <<< "$(echo "$MAGIC_HITS" | head -5)"
else
    echo "  OK: No obvious magic numbers"
fi

# ── Check 7: All 5 series pages exist ──
echo "[7/7] Checking all series pages exist..."
EXPECTED_SLUGS="belgian-waffle-ride grasshopper-adventure-series gravel-earth-series grinduro life-time-grand-prix"
for slug in $EXPECTED_SLUGS; do
    if [ ! -f "$OUTPUT_DIR/$slug/index.html" ]; then
        error "Missing page: $slug/index.html"
    fi
done
echo "  OK: All 5 series pages exist"

# ── Summary ──
echo ""
echo "=== Summary ==="
echo "Errors:   $ERRORS"
echo "Warnings: $WARNINGS"
if [ $ERRORS -gt 0 ]; then
    echo "FAILED — fix errors before deploying"
    exit 1
fi
echo "PASSED"
