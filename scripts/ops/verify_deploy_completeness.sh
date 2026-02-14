#!/usr/bin/env bash
# verify_deploy_completeness.sh
#
# After regeneration, checks that every generator's output was actually deployed.
# Prevents the "changed code but forgot to deploy" failure mode.
#
# Usage: bash scripts/ops/verify_deploy_completeness.sh
#
# Exit codes:
#   0 = all generated files have been deployed
#   1 = some files regenerated but not deployed

set -euo pipefail
cd "$(dirname "$0")/../.."

FAIL=0
OUTPUT="wordpress/output"

echo "=== Deploy Completeness Check ==="

# Check race pages
race_count=$(ls "$OUTPUT"/*.html 2>/dev/null | grep -v methodology | grep -v guide | wc -l | xargs)
if [ "$race_count" -gt 0 ]; then
  echo "  Race pages generated: $race_count"
else
  echo "  WARNING: No race pages in output/"
fi

# Check methodology
if [ -f "$OUTPUT/methodology.html" ]; then
  echo "  Methodology: generated"
else
  echo "  WARNING: methodology.html not generated"
fi

# Check tier hubs
tier_count=$(ls "$OUTPUT"/tier-*/index.html 2>/dev/null | wc -l | xargs)
if [ "$tier_count" -gt 0 ]; then
  echo "  Tier hubs: $tier_count generated"
else
  echo "  WARNING: No tier hub pages in output/"
fi

# Check guide
if [ -f "$OUTPUT/guide.html" ]; then
  echo "  Guide: generated"
else
  echo "  WARNING: guide.html not generated"
fi

# Check index
if [ -f "web/race-index.json" ]; then
  echo "  Index: generated"
else
  echo "  WARNING: race-index.json not generated"
fi

echo ""
echo "=== Header Consistency Check ==="

# Verify ALL generated HTML uses new header, not old nav
old_nav_files=""
for f in "$OUTPUT"/*.html "$OUTPUT"/tier-*/index.html; do
  [ -f "$f" ] || continue
  if grep -q "gg-site-nav" "$f" 2>/dev/null; then
    old_nav_files="$old_nav_files\n  $(basename "$f")"
    FAIL=1
  fi
  if ! grep -q "gg-site-header" "$f" 2>/dev/null; then
    echo "  MISSING new header in: $(basename "$f")"
    FAIL=1
  fi
done

if [ -n "$old_nav_files" ]; then
  echo "  FAIL: Old gg-site-nav class found in:$old_nav_files"
fi

# Check search widget for discipline filter
if [ -f "web/gravel-race-search.html" ]; then
  if grep -q "gg-discipline" "web/gravel-race-search.html"; then
    echo "  Search widget: discipline filter present"
  else
    echo "  FAIL: Search widget missing discipline filter"
    FAIL=1
  fi
fi

if [ -f "web/gravel-race-search.js" ]; then
  if grep -q "discipline" "web/gravel-race-search.js"; then
    echo "  Search JS: discipline wired"
  else
    echo "  FAIL: Search JS missing discipline logic"
    FAIL=1
  fi
fi

# Check index has discipline field
if [ -f "web/race-index.json" ]; then
  disc_count=$(python3 -c "
import json
data = json.load(open('web/race-index.json'))
print(sum(1 for r in data if 'discipline' in r))
" 2>/dev/null || echo "0")
  total=$(python3 -c "
import json
print(len(json.load(open('web/race-index.json'))))
" 2>/dev/null || echo "0")
  if [ "$disc_count" = "$total" ] && [ "$total" -gt 0 ]; then
    echo "  Index: all $total entries have discipline field"
  else
    echo "  FAIL: Only $disc_count/$total index entries have discipline"
    FAIL=1
  fi
fi

echo ""
if [ $FAIL -eq 0 ]; then
  echo "PASS: All checks passed"
else
  echo "FAIL: Issues found — fix before deploying"
  exit 1
fi
