#!/usr/bin/env bash
#
# Integration tests for review-intake Cloudflare Worker.
# Tests happy path, all rejection paths, protocol checks, security.
#
# Usage:
#   bash tests/test_worker_review.sh
#   bash tests/test_worker_review.sh https://custom-worker-url.workers.dev
#
# Exit code 0 = all tests pass. Non-zero = at least one failure.
# Run AFTER every deploy. No exceptions.

set -euo pipefail

WORKER_URL="${1:-https://review-intake.gravelgodcoaching.workers.dev}"
ORIGIN="https://gravelgodcycling.com"
PASS=0
FAIL=0
TOTAL=0

# --- Helpers ---

post() {
  local data="$1"
  local origin="${2:-$ORIGIN}"
  curl -s -w "\n%{http_code}" -X POST "$WORKER_URL" \
    -H "Content-Type: application/json" \
    -H "Origin: $origin" \
    -d "$data"
}

assert_status() {
  local test_name="$1"
  local expected_status="$2"
  local response="$3"

  TOTAL=$((TOTAL + 1))
  local status
  status=$(echo "$response" | tail -1)

  if [ "$status" = "$expected_status" ]; then
    PASS=$((PASS + 1))
    printf "  PASS  %-55s [%s]\n" "$test_name" "$status"
  else
    FAIL=$((FAIL + 1))
    local body
    body=$(echo "$response" | sed '$d')
    printf "  FAIL  %-55s [got %s, expected %s]\n" "$test_name" "$status" "$expected_status"
    printf "        body: %s\n" "$body"
  fi
}

assert_status_and_body() {
  local test_name="$1"
  local expected_status="$2"
  local expected_body_fragment="$3"
  local response="$4"

  TOTAL=$((TOTAL + 1))
  local status
  local body
  status=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')

  if [ "$status" = "$expected_status" ] && echo "$body" | grep -q "$expected_body_fragment"; then
    PASS=$((PASS + 1))
    printf "  PASS  %-55s [%s, contains '%s']\n" "$test_name" "$status" "$expected_body_fragment"
  else
    FAIL=$((FAIL + 1))
    printf "  FAIL  %-55s [got %s, expected %s with '%s']\n" "$test_name" "$status" "$expected_status" "$expected_body_fragment"
    printf "        body: %s\n" "$body"
  fi
}

echo ""
echo "=== review-intake Worker Integration Tests ==="
echo "Target: $WORKER_URL"
echo ""

# ============================================================
# SECTION 1: Happy path
# ============================================================
echo "--- Happy Path (expect 200) ---"

R=$(post '{"email":"test-review@example.com","race_slug":"unbound-gravel","race_name":"Unbound Gravel","stars":4,"year_raced":"2025","would_race_again":"yes","finish_position":"top half","best":"Amazing gravel roads","worst":"Wind in section 3","website":""}')
assert_status "full review submission" "200" "$R"

R=$(post '{"email":"test-min@example.com","race_slug":"big-sugar","stars":3,"website":""}')
assert_status "minimal review (required fields only)" "200" "$R"

echo ""

# ============================================================
# SECTION 2: Rejection paths
# ============================================================
echo "--- Rejection Paths (expect 400) ---"

R=$(post '{"race_slug":"unbound","stars":4,"website":""}')
assert_status_and_body "missing email" "400" "Missing: email" "$R"

R=$(post '{"email":"test@example.com","stars":4,"website":""}')
assert_status_and_body "missing race_slug" "400" "Missing: race slug" "$R"

R=$(post '{"email":"test@example.com","race_slug":"unbound","website":""}')
assert_status_and_body "missing stars" "400" "Invalid star" "$R"

R=$(post '{"email":"test@example.com","race_slug":"unbound","stars":0,"website":""}')
assert_status_and_body "stars too low (0)" "400" "Invalid star" "$R"

R=$(post '{"email":"test@example.com","race_slug":"unbound","stars":6,"website":""}')
assert_status_and_body "stars too high (6)" "400" "Invalid star" "$R"

R=$(post '{"email":"not-an-email","race_slug":"unbound","stars":3,"website":""}')
assert_status_and_body "invalid email format" "400" "Invalid email" "$R"

R=$(post '{"email":"test@mailinator.com","race_slug":"unbound","stars":3,"website":""}')
assert_status_and_body "disposable email" "400" "non-disposable" "$R"

R=$(post '{"email":"test@example.com","race_slug":"unbound","stars":3,"website":"gotcha"}')
assert_status_and_body "honeypot triggered" "400" "Bot detected" "$R"

echo ""

# ============================================================
# SECTION 3: Protocol-level rejections
# ============================================================
echo "--- Protocol Rejections ---"

TOTAL=$((TOTAL + 1))
METHOD_R=$(curl -s -w "\n%{http_code}" -X GET "$WORKER_URL" -H "Origin: $ORIGIN")
METHOD_STATUS=$(echo "$METHOD_R" | tail -1)
if [ "$METHOD_STATUS" = "405" ]; then
  PASS=$((PASS + 1))
  printf "  PASS  %-55s [%s]\n" "GET request rejected" "$METHOD_STATUS"
else
  FAIL=$((FAIL + 1))
  printf "  FAIL  %-55s [got %s, expected 405]\n" "GET request rejected" "$METHOD_STATUS"
fi

R=$(post '{"email":"test@example.com","race_slug":"unbound","stars":3,"website":""}' "https://evil-site.com")
assert_status "wrong origin rejected" "403" "$R"

TOTAL=$((TOTAL + 1))
BAD_R=$(curl -s -w "\n%{http_code}" -X POST "$WORKER_URL" \
  -H "Content-Type: application/json" \
  -H "Origin: $ORIGIN" \
  -d 'not json at all')
BAD_STATUS=$(echo "$BAD_R" | tail -1)
BAD_BODY=$(echo "$BAD_R" | sed '$d')
if [ "$BAD_STATUS" = "400" ] && echo "$BAD_BODY" | grep -q "Invalid JSON"; then
  PASS=$((PASS + 1))
  printf "  PASS  %-55s [%s]\n" "malformed JSON rejected" "$BAD_STATUS"
else
  FAIL=$((FAIL + 1))
  printf "  FAIL  %-55s [got %s, expected 400 with 'Invalid JSON']\n" "malformed JSON rejected" "$BAD_STATUS"
  printf "        body: %s\n" "$BAD_BODY"
fi

TOTAL=$((TOTAL + 1))
CORS_R=$(curl -s -w "\n%{http_code}" -X OPTIONS "$WORKER_URL" \
  -H "Origin: $ORIGIN" \
  -H "Access-Control-Request-Method: POST")
CORS_STATUS=$(echo "$CORS_R" | tail -1)
if [ "$CORS_STATUS" = "204" ]; then
  PASS=$((PASS + 1))
  printf "  PASS  %-55s [%s]\n" "CORS preflight returns 204" "$CORS_STATUS"
else
  FAIL=$((FAIL + 1))
  printf "  FAIL  %-55s [got %s, expected 204]\n" "CORS preflight returns 204" "$CORS_STATUS"
fi

echo ""

# ============================================================
# SECTION 4: Security
# ============================================================
echo "--- Security ---"

R=$(post '{"email":"xss@example.com","race_slug":"<script>alert(1)</script>","race_name":"<img src=x onerror=alert(1)>","stars":5,"best":"<b>bold</b>","worst":"<script>steal()</script>","website":""}')
assert_status "HTML in fields accepted (escaped server-side)" "200" "$R"

echo ""

# ============================================================
# Summary
# ============================================================
echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
  echo "BLOCKED: Fix failures before deploying."
  exit 1
else
  echo "All tests passed."
  exit 0
fi
