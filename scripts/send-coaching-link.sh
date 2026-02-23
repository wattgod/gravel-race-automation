#!/bin/bash
# Generate a Stripe checkout URL for an accepted coaching athlete.
#
# Usage:
#   ./scripts/send-coaching-link.sh "Sarah K" sarah@example.com mid
#   ./scripts/send-coaching-link.sh "Dan R" dan@example.com min
#   ./scripts/send-coaching-link.sh "Steve A" steve@example.com max
#
# Tiers: min ($199/4wk), mid ($299/4wk), max ($1,200/4wk)
# All tiers include the $99 one-time setup fee.
#
# The returned URL expires in 60 minutes. If the athlete doesn't
# complete checkout, Stripe sends an automatic recovery email.

set -euo pipefail

API_URL="https://athlete-custom-training-plan-pipeline-production.up.railway.app/api/create-coaching-checkout"

# ── Validate args ─────────────────────────────────────────────

if [ $# -lt 3 ]; then
  echo "Usage: $0 NAME EMAIL TIER"
  echo ""
  echo "  NAME   Athlete name (quote if spaces)"
  echo "  EMAIL  Athlete email address"
  echo "  TIER   min | mid | max"
  echo ""
  echo "Examples:"
  echo "  $0 \"Sarah K\" sarah@example.com mid"
  echo "  $0 \"Dan R\" dan@example.com min"
  exit 1
fi

NAME="$1"
EMAIL="$2"
TIER="$3"

# Validate tier
if [[ "$TIER" != "min" && "$TIER" != "mid" && "$TIER" != "max" ]]; then
  echo "Error: tier must be min, mid, or max (got: $TIER)"
  exit 1
fi

# Validate email has @ and .
if [[ "$EMAIL" != *@*.* ]]; then
  echo "Error: invalid email address: $EMAIL"
  exit 1
fi

# ── Pricing display ───────────────────────────────────────────

case "$TIER" in
  min) PRICE="\$199/4wk + \$99 setup" ;;
  mid) PRICE="\$299/4wk + \$99 setup" ;;
  max) PRICE="\$1,200/4wk + \$99 setup" ;;
esac

echo "Creating checkout for:"
echo "  Name:  $NAME"
echo "  Email: $EMAIL"
echo "  Tier:  $TIER ($PRICE)"
echo ""

# ── Call the API ──────────────────────────────────────────────

export _NAME="$NAME" _EMAIL="$EMAIL" _TIER="$TIER"

JSON_BODY=$(python3 -c "import json,os; print(json.dumps({'name': os.environ['_NAME'], 'email': os.environ['_EMAIL'], 'tier': os.environ['_TIER']}))" \
  2>/dev/null) || { echo "Error: failed to build JSON payload"; exit 1; }

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL" \
  -H 'Content-Type: application/json' \
  -d "$JSON_BODY")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" != "200" ]; then
  echo "Error ($HTTP_CODE):"
  echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error','Unknown error'))" 2>/dev/null || echo "$BODY"
  exit 1
fi

CHECKOUT_URL=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['checkout_url'])")

echo "Checkout URL (expires in 60 min):"
echo ""
echo "  $CHECKOUT_URL"
echo ""

# Copy to clipboard on macOS
if command -v pbcopy &>/dev/null; then
  echo -n "$CHECKOUT_URL" | pbcopy
  echo "Copied to clipboard."
fi
