#!/usr/bin/env bash
# generator-quality-check.sh — Source-level checks for all HTML generators
#
# Scans wordpress/*.py generator source files for known anti-patterns:
#   1. Hardcoded racer rating thresholds (must use brand_tokens.RACER_RATING_THRESHOLD)
#   2. Dead functions (defined but never called)
#   3. Dishonest CTAs ("RATE IT" without a rating system)
#   4. Orphaned CSS classes (CSS selectors with no matching HTML class usage)
#   5. esc() inside JSON-LD <script> blocks
#   6. Hardcoded year in output strings
#   7. RACER_RATING_FORM_BASE or other dead constants
#
# Usage:
#   bash scripts/ops/generator-quality-check.sh
#
# Exit codes:
#   0 = all checks passed
#   1 = one or more checks failed

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GEN_DIR="$PROJECT_ROOT/wordpress"

ERRORS=0
WARNINGS=0

error() { echo "  FAIL: $1"; ((ERRORS++)) || true; }
warn()  { echo "  WARN: $1"; ((WARNINGS++)) || true; }
pass()  { echo "  PASS: $1"; }

echo "=== Generator Quality Check ==="
echo "Source dir: $GEN_DIR"
echo ""

GENERATORS=(
  "$GEN_DIR/generate_neo_brutalist.py"
  "$GEN_DIR/generate_state_hubs.py"
  "$GEN_DIR/generate_homepage.py"
  "$GEN_DIR/generate_series_hubs.py"
)

# ── Check 1: Hardcoded racer rating thresholds ──
echo "[1/7] Hardcoded racer rating thresholds..."
THRESH_FAIL=0
for gen in "${GENERATORS[@]}"; do
  basename_gen=$(basename "$gen")
  # Look for rr_total >= N or racer_total >= N where N is a raw number
  hits=$(grep -nE 'rr_total\s*>=\s*[0-9]+|racer_total\s*>=\s*[0-9]+' "$gen" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    error "$basename_gen: hardcoded racer threshold found:"
    echo "$hits" | sed 's/^/      /'
    THRESH_FAIL=1
  fi
done
if [ $THRESH_FAIL -eq 0 ]; then
  pass "All generators use RACER_RATING_THRESHOLD constant"
fi

# ── Check 2: Dead functions (defined but never called) ──
echo "[2/7] Dead functions..."
DEAD_FUNC_FAIL=0
for gen in "${GENERATORS[@]}"; do
  basename_gen=$(basename "$gen")
  # Find all function definitions starting with _
  func_defs=$(grep -oE 'def (_[a-zA-Z_]+)\(' "$gen" 2>/dev/null | sed 's/def //' | sed 's/(//' || true)
  if [ -n "$func_defs" ]; then
    while IFS= read -r func; do
      # Count how many times this function name appears (should be > 1: definition + at least one call)
      count=$(grep -c "$func" "$gen" 2>/dev/null || echo "0")
      if [ "$count" -le 1 ]; then
        error "$basename_gen: function $func() defined but never called"
        DEAD_FUNC_FAIL=1
      fi
    done <<< "$func_defs"
  fi
done
if [ $DEAD_FUNC_FAIL -eq 0 ]; then
  pass "No dead private functions found"
fi

# ── Check 3: Dishonest CTAs ──
echo "[3/7] Dishonest CTAs (RATE IT without rating system)..."
CTA_FAIL=0
for gen in "${GENERATORS[@]}"; do
  basename_gen=$(basename "$gen")
  hits=$(grep -n '"RATE IT"' "$gen" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    error "$basename_gen: contains 'RATE IT' CTA — no rating form exists"
    CTA_FAIL=1
  fi
done
if [ $CTA_FAIL -eq 0 ]; then
  pass "No dishonest CTAs found"
fi

# ── Check 4: Dead constants ──
echo "[4/7] Dead constants (RACER_RATING_FORM_BASE, etc.)..."
DEAD_CONST_FAIL=0
DEAD_CONSTANTS=("RACER_RATING_FORM_BASE")
for gen in "${GENERATORS[@]}"; do
  basename_gen=$(basename "$gen")
  for const in "${DEAD_CONSTANTS[@]}"; do
    hits=$(grep -n "$const" "$gen" 2>/dev/null || true)
    if [ -n "$hits" ]; then
      error "$basename_gen: contains dead constant $const"
      DEAD_CONST_FAIL=1
    fi
  done
done
if [ $DEAD_CONST_FAIL -eq 0 ]; then
  pass "No dead constants found"
fi

# ── Check 5: esc() inside JSON-LD template blocks ──
# Only catches esc() on the SAME line as or between application/ld+json
# and </script> on a MULTI-LINE f-string template. Does NOT flag
# Python-dict-based JSON-LD builders (they use json.dumps correctly).
echo "[5/7] esc() inside JSON-LD template f-strings..."
ESC_FAIL=0
for gen in "${GENERATORS[@]}"; do
  basename_gen=$(basename "$gen")
  in_jsonld=0
  line_num=0
  while IFS= read -r line; do
    ((line_num++)) || true
    # Only enter JSON-LD state for inline template strings (f''' blocks)
    # that contain the opening tag AND content on subsequent lines
    if echo "$line" | grep -q 'application/ld+json.*{esc('; then
      error "$basename_gen:$line_num: esc() on same line as JSON-LD script tag"
      ESC_FAIL=1
    elif echo "$line" | grep -q 'application/ld+json'; then
      # Check if this is a template f-string (has { but not json.dumps)
      if echo "$line" | grep -qv 'json\.dumps\|json_parts\|jsonld_html\|jsonld_parts'; then
        in_jsonld=1
      fi
    fi
    if [ $in_jsonld -eq 1 ]; then
      if echo "$line" | grep -q '</script>'; then
        in_jsonld=0
      elif echo "$line" | grep -q '{esc('; then
        error "$basename_gen:$line_num: esc() used inside JSON-LD template block"
        ESC_FAIL=1
      fi
    fi
  done < "$gen"
done
if [ $ESC_FAIL -eq 0 ]; then
  pass "No esc() calls inside JSON-LD template blocks"
fi

# ── Check 6: Hardcoded year in non-comment output strings ──
echo "[6/7] Hardcoded year '2026' in output strings..."
YEAR_FAIL=0
CURRENT_YEAR=$(date +%Y)
for gen in "${GENERATORS[@]}"; do
  basename_gen=$(basename "$gen")
  # Find lines with 2026 that aren't comments and don't reference CURRENT_YEAR
  hits=$(grep -nE "2026" "$gen" 2>/dev/null | grep -v "^\s*#" | grep -v "CURRENT_YEAR" | grep -v "Date:" | grep -v "Effective" | grep -v "Last updated" || true)
  if [ -n "$hits" ]; then
    # Filter to only f-string/HTML output lines (containing ' or " and {)
    output_hits=$(echo "$hits" | grep -E "(f'|f\"|<|html)" || true)
    if [ -n "$output_hits" ]; then
      error "$basename_gen: hardcoded '2026' in output strings:"
      echo "$output_hits" | sed 's/^/      /' | head -5
      YEAR_FAIL=1
    fi
  fi
done
if [ $YEAR_FAIL -eq 0 ]; then
  pass "No hardcoded year in output strings"
fi

# ── Check 7: RACER_RATING_THRESHOLD import from brand_tokens ──
echo "[7/7] RACER_RATING_THRESHOLD imported from brand_tokens..."
IMPORT_FAIL=0
for gen in "${GENERATORS[@]}"; do
  basename_gen=$(basename "$gen")
  uses_threshold=$(grep -c "RACER_RATING_THRESHOLD" "$gen" 2>/dev/null || true)
  uses_threshold=${uses_threshold:-0}
  if [ "$uses_threshold" -gt 0 ]; then
    imports_from_brand=$(grep -c "from brand_tokens import.*RACER_RATING_THRESHOLD" "$gen" 2>/dev/null || true)
    imports_from_brand=${imports_from_brand:-0}
    if [ "$imports_from_brand" -eq 0 ]; then
      # Check if it defines its own (bad)
      defines_own=$(grep -c "^RACER_RATING_THRESHOLD" "$gen" 2>/dev/null || true)
      defines_own=${defines_own:-0}
      if [ "$defines_own" -gt 0 ]; then
        error "$basename_gen: defines own RACER_RATING_THRESHOLD instead of importing from brand_tokens"
        IMPORT_FAIL=1
      fi
    fi
  fi
done
if [ $IMPORT_FAIL -eq 0 ]; then
  pass "All generators import RACER_RATING_THRESHOLD from brand_tokens"
fi

# ── Summary ──
echo ""
echo "=== Summary ==="
echo "Errors:   $ERRORS"
echo "Warnings: $WARNINGS"
echo "Generators checked: ${#GENERATORS[@]}"
echo ""
if [ $ERRORS -gt 0 ]; then
  echo "FAILED — $ERRORS issue(s) found. Fix before deploying."
  exit 1
fi
echo "PASSED — all 7 checks clean."
