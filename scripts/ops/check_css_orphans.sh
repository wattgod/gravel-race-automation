#!/usr/bin/env bash
# check_css_orphans.sh
#
# Checks that no generator Python files reference CSS classes that were
# replaced during the header migration. Prevents orphaned CSS from
# accumulating in generators.
#
# Usage: bash scripts/ops/check_css_orphans.sh
#
# Exit codes:
#   0 = no orphaned classes found
#   1 = old CSS classes still referenced

set -euo pipefail
cd "$(dirname "$0")/../.."

FAIL=0

echo "=== CSS Orphan Check ==="

# Old classes that should no longer exist in any generator
OLD_CLASSES=(
  "gg-site-nav"
  "gg-site-nav-inner"
  "gg-site-nav-brand"
  "gg-site-nav-link"
  "gg-hub-nav"
  "gg-hub-nav-brand"
  "gg-hub-nav-links"
)

for cls in "${OLD_CLASSES[@]}"; do
  hits=$(grep -rn "$cls" wordpress/generate_*.py 2>/dev/null || true)
  if [ -n "$hits" ]; then
    echo "  FAIL: Old class '$cls' found:"
    echo "$hits" | sed 's/^/    /'
    FAIL=1
  fi
done

# Also check generated output HTML
for cls in "${OLD_CLASSES[@]}"; do
  hits=$(grep -rn "$cls" wordpress/output/*.html wordpress/output/tier-*/index.html 2>/dev/null | head -5 || true)
  if [ -n "$hits" ]; then
    echo "  FAIL: Old class '$cls' in generated output:"
    echo "$hits" | sed 's/^/    /'
    FAIL=1
  fi
done

echo ""
if [ $FAIL -eq 0 ]; then
  echo "PASS: No orphaned CSS classes found"
else
  echo "FAIL: Orphaned CSS classes detected — clean up before deploying"
  exit 1
fi
