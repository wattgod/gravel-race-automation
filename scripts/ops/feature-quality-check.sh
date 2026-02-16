#!/usr/bin/env bash
# feature-quality-check.sh — Checks generated HTML output for common shortcuts
#
# Scans wordpress/output/ for dead code, missing accessibility,
# broken worker URLs, bypassed email gates, missing JSON-LD,
# missing honeypots, hardcoded race counts, and stale asset hashes.
#
# Usage:
#   bash scripts/ops/feature-quality-check.sh
#   bash scripts/ops/feature-quality-check.sh --output-dir wordpress/output
#
# Exit codes:
#   0 = all checks passed
#   1 = one or more checks failed

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# ── Parse arguments ──
OUTPUT_DIR="$PROJECT_ROOT/wordpress/output"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --output-dir=*)
      OUTPUT_DIR="${1#*=}"
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: $0 [--output-dir DIR]"
      exit 2
      ;;
  esac
done

# Resolve relative paths against project root
if [[ ! "$OUTPUT_DIR" = /* ]]; then
  OUTPUT_DIR="$PROJECT_ROOT/$OUTPUT_DIR"
fi

ERRORS=0
WARNINGS=0

error() { echo "  FAIL: $1"; ((ERRORS++)) || true; }
warn()  { echo "  WARN: $1"; ((WARNINGS++)) || true; }
pass()  { echo "  PASS: $1"; }

# Safe grep -c wrapper: returns 0 instead of failing on no match
count_matches() {
  grep -c "$@" 2>/dev/null || true
}

echo "=== Feature Quality Check ==="
echo "Output dir: $OUTPUT_DIR"
echo ""

if [ ! -d "$OUTPUT_DIR" ]; then
  echo "ERROR: Output directory does not exist: $OUTPUT_DIR"
  echo "Run generators first, then re-run this check."
  exit 1
fi

# Collect all HTML files (top-level .html + subdirectory index.html files)
HTML_FILES=()
while IFS= read -r -d '' f; do
  HTML_FILES+=("$f")
done < <(find "$OUTPUT_DIR" -name "*.html" -print0 2>/dev/null)

if [ ${#HTML_FILES[@]} -eq 0 ]; then
  echo "ERROR: No HTML files found in $OUTPUT_DIR"
  exit 1
fi
echo "Found ${#HTML_FILES[@]} HTML files to check."
echo ""

# Collect all JS files (standalone .js files in output)
JS_FILES=()
while IFS= read -r -d '' f; do
  JS_FILES+=("$f")
done < <(find "$OUTPUT_DIR" -name "*.js" -print0 2>/dev/null)

# ── Check 1: Dead code detection (star hover bug pattern) ──
echo "[1/8] Dead code detection: identical assignments on both branches..."
DEAD_CODE_FOUND=0
for f in "${HTML_FILES[@]}" "${JS_FILES[@]}"; do
  # Pattern: if/else where both branches do the same style assignment
  # Look for patterns like: if(X){...b.style.color=''}else{...b.style.color=''}
  hits=$(grep -noE "if\s*\([^)]*\)\s*\{[^}]*\.style\.[a-zA-Z]+\s*=\s*['\"][^'\"]*['\"][^}]*\}\s*else\s*\{[^}]*\.style\.[a-zA-Z]+\s*=\s*['\"][^'\"]*['\"]" "$f" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    # Check if the two style assignments are identical
    while IFS= read -r hit; do
      first=$(echo "$hit" | grep -oE '\.style\.[a-zA-Z]+\s*=\s*['"'"'"][^'"'"'"]*['"'"'"]' | head -1)
      second=$(echo "$hit" | grep -oE '\.style\.[a-zA-Z]+\s*=\s*['"'"'"][^'"'"'"]*['"'"'"]' | tail -1)
      if [ -n "$first" ] && [ -n "$second" ] && [ "$first" = "$second" ]; then
        error "Dead code in $(basename "$f"): identical assignment on both branches: $first"
        DEAD_CODE_FOUND=1
      fi
    done <<< "$hits"
  fi
done
if [ $DEAD_CODE_FOUND -eq 0 ]; then
  pass "No dead-code if/else patterns found"
fi

# ── Check 2: Missing accessibility on popups ──
echo "[2/8] Popup/overlay accessibility (role=\"dialog\", aria-modal)..."
A11Y_FAIL=0
for f in "${HTML_FILES[@]}"; do
  basename_f=$(basename "$f")
  # Check for exit overlays / modals
  has_overlay=$(count_matches -E "gg-exit-overlay|gg-exit-modal|gg-overlay|gg-modal" "$f")
  if [ "$has_overlay" -gt 0 ]; then
    has_role=$(count_matches 'role="dialog"' "$f")
    has_aria=$(count_matches 'aria-modal="true"' "$f")
    if [ "$has_role" -eq 0 ]; then
      error "$basename_f: overlay/modal present but missing role=\"dialog\""
      A11Y_FAIL=1
    fi
    if [ "$has_aria" -eq 0 ]; then
      error "$basename_f: overlay/modal present but missing aria-modal=\"true\""
      A11Y_FAIL=1
    fi
  fi
done
if [ $A11Y_FAIL -eq 0 ]; then
  pass "All overlays/modals have proper ARIA attributes"
fi

# ── Check 3: Worker URL verification ──
echo "[3/8] Worker URL verification (*.workers.dev reachability)..."
WORKER_FAIL=0
WORKER_URLS=()
for f in "${HTML_FILES[@]}" "${JS_FILES[@]}"; do
  urls=$(grep -oE 'https?://[a-zA-Z0-9._-]+\.workers\.dev[a-zA-Z0-9/._?&=-]*' "$f" 2>/dev/null || true)
  if [ -n "$urls" ]; then
    while IFS= read -r url; do
      # Deduplicate
      already_seen=0
      for seen in "${WORKER_URLS[@]+"${WORKER_URLS[@]}"}"; do
        if [ "$seen" = "$url" ]; then
          already_seen=1
          break
        fi
      done
      if [ $already_seen -eq 0 ]; then
        WORKER_URLS+=("$url")
      fi
    done <<< "$urls"
  fi
done

if [ ${#WORKER_URLS[@]} -eq 0 ]; then
  pass "No workers.dev URLs found (nothing to verify)"
else
  for url in "${WORKER_URLS[@]}"; do
    # Try HEAD first; fall back to GET if HEAD returns 405 (workers often reject HEAD)
    http_code=$(curl -s -o /dev/null -w "%{http_code}" --head --max-time 5 "$url" 2>/dev/null || echo "000")
    if [ "$http_code" = "405" ]; then
      http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "000")
    fi
    # 405 on GET is expected for POST-only intake endpoints — treat as reachable
    if [ "$http_code" = "405" ]; then
      echo "    OK: $url (HTTP 405 — POST-only endpoint, domain resolves)"
    elif [[ "$http_code" =~ ^[45] ]] || [ "$http_code" = "000" ]; then
      error "Worker URL unreachable (HTTP $http_code): $url"
      WORKER_FAIL=1
    else
      echo "    OK: $url (HTTP $http_code)"
    fi
  done
  if [ $WORKER_FAIL -eq 0 ]; then
    pass "All ${#WORKER_URLS[@]} workers.dev URLs reachable"
  fi
fi

# ── Check 4: Email gate enforcement ──
echo "[4/8] Email gate enforcement (results pages must check email)..."
GATE_FAIL=0
for f in "${HTML_FILES[@]}"; do
  basename_f=$(basename "$f")
  has_results=$(count_matches -E "resultSlugs|[?&]results=" "$f")
  if [ "$has_results" -gt 0 ]; then
    has_gate=$(count_matches -E "hasCachedEmail|cachedEmail|emailGate|localStorage.*email|sessionStorage.*email|checkEmail" "$f")
    if [ "$has_gate" -eq 0 ]; then
      error "$basename_f: handles ?results= but has no email gate (hasCachedEmail / localStorage email check)"
      GATE_FAIL=1
    fi
  fi
done
if [ $GATE_FAIL -eq 0 ]; then
  pass "All results pages enforce email gate"
fi

# ── Check 5: JSON-LD on every page ──
echo "[5/8] JSON-LD presence on every page..."
JSONLD_MISSING=0
JSONLD_MISSING_LIST=""
for f in "${HTML_FILES[@]}"; do
  basename_f=$(basename "$f")
  has_jsonld=$(count_matches 'application/ld+json' "$f")
  if [ "$has_jsonld" -eq 0 ]; then
    JSONLD_MISSING_LIST="${JSONLD_MISSING_LIST}    ${basename_f}\n"
    ((JSONLD_MISSING++)) || true
  fi
done
if [ $JSONLD_MISSING -gt 0 ]; then
  error "$JSONLD_MISSING page(s) missing JSON-LD structured data:"
  printf "%b" "$JSONLD_MISSING_LIST" | head -20
  if [ $JSONLD_MISSING -gt 20 ]; then
    echo "    ... and $((JSONLD_MISSING - 20)) more"
  fi
else
  pass "All ${#HTML_FILES[@]} pages have JSON-LD"
fi

# ── Check 6: Honeypot on every form ──
echo "[6/8] Honeypot field on every form..."
HONEYPOT_FAIL=0
for f in "${HTML_FILES[@]}"; do
  basename_f=$(basename "$f")
  form_count=$(count_matches -E '<form[[:space:]>]' "$f")
  if [ "$form_count" -gt 0 ]; then
    honeypot_count=$(count_matches 'name="website"' "$f")
    if [ "$honeypot_count" -lt "$form_count" ]; then
      error "$basename_f: $form_count form(s) but only $honeypot_count honeypot field(s)"
      HONEYPOT_FAIL=1
    fi
  fi
done
if [ $HONEYPOT_FAIL -eq 0 ]; then
  pass "All forms have honeypot fields"
fi

# ── Check 7: No hardcoded race counts ──
echo "[7/8] No hardcoded race counts in meta descriptions..."
HARDCODED_FAIL=0
for f in "${HTML_FILES[@]}"; do
  basename_f=$(basename "$f")
  meta_desc=$(grep -oE '<meta[^>]*name="description"[^>]*content="[^"]*"' "$f" 2>/dev/null || true)
  if [ -n "$meta_desc" ]; then
    if echo "$meta_desc" | grep -qE '\b328\b'; then
      error "$basename_f: meta description contains hardcoded '328' race count"
      HARDCODED_FAIL=1
    fi
  fi
done
if [ $HARDCODED_FAIL -eq 0 ]; then
  pass "No hardcoded '328' race count in meta descriptions"
fi

# ── Check 8: External asset freshness (hash verification) ──
echo "[8/8] External asset hash verification..."
ASSET_DIR="$OUTPUT_DIR/assets"
ASSET_FAIL=0
if [ -d "$ASSET_DIR" ]; then
  for f in "${HTML_FILES[@]}"; do
    basename_f=$(basename "$f")
    # Extract CSS references: href="assets/something.hash.css"
    css_refs=$(grep -oE 'href="assets/[^"]*\.css"' "$f" 2>/dev/null || true)
    if [ -n "$css_refs" ]; then
      while IFS= read -r ref; do
        asset_path="${ref#href=\"}"
        asset_path="${asset_path%\"}"
        full_path="$OUTPUT_DIR/$asset_path"
        if [ ! -f "$full_path" ]; then
          error "$basename_f: references $asset_path but file does not exist"
          ASSET_FAIL=1
        fi
      done <<< "$css_refs"
    fi
    # Extract JS references: src="assets/something.hash.js"
    js_refs=$(grep -oE 'src="assets/[^"]*\.js"' "$f" 2>/dev/null || true)
    if [ -n "$js_refs" ]; then
      while IFS= read -r ref; do
        asset_path="${ref#src=\"}"
        asset_path="${asset_path%\"}"
        full_path="$OUTPUT_DIR/$asset_path"
        if [ ! -f "$full_path" ]; then
          error "$basename_f: references $asset_path but file does not exist"
          ASSET_FAIL=1
        fi
      done <<< "$js_refs"
    fi
  done
  if [ $ASSET_FAIL -eq 0 ]; then
    pass "All asset references resolve to existing files"
  fi
else
  warn "No assets/ directory found — skipping asset hash check"
fi

# ── Summary ──
echo ""
echo "=== Summary ==="
echo "Errors:   $ERRORS"
echo "Warnings: $WARNINGS"
echo "Files:    ${#HTML_FILES[@]} HTML, ${#JS_FILES[@]} JS"
echo ""
if [ $ERRORS -gt 0 ]; then
  echo "FAILED — $ERRORS issue(s) found. Fix before deploying."
  exit 1
fi
echo "PASSED — all 8 checks clean."
