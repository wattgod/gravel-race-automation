#!/usr/bin/env bash
#
# Integration tests for fueling-lead-intake Cloudflare Worker.
# Tests all 6 valid sources AND all rejection paths.
#
# Usage:
#   bash tests/test_worker_intake.sh
#   bash tests/test_worker_intake.sh https://custom-worker-url.workers.dev
#
# Exit code 0 = all tests pass. Non-zero = at least one failure.
# Run this AFTER every deploy. No exceptions.

set -euo pipefail

WORKER_URL="${1:-https://fueling-lead-intake.gravelgodcoaching.workers.dev}"
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
  local body
  local status
  status=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')

  if [ "$status" = "$expected_status" ]; then
    PASS=$((PASS + 1))
    printf "  PASS  %-55s [%s]\n" "$test_name" "$status"
  else
    FAIL=$((FAIL + 1))
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
  local body
  local status
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
echo "=== fueling-lead-intake Worker Integration Tests ==="
echo "Target: $WORKER_URL"
echo ""

# ============================================================
# SECTION 1: Happy path — all 6 sources should return 200
# ============================================================
echo "--- Happy Path (expect 200) ---"

R=$(post '{"email":"test-exit@example.com","source":"exit_intent","website":""}')
assert_status "exit_intent: email only" "200" "$R"

R=$(post '{"email":"test-rp@example.com","source":"race_profile","race_slug":"unbound","race_name":"Unbound Gravel","website":""}')
assert_status "race_profile: email + race" "200" "$R"

R=$(post '{"email":"test-pk@example.com","source":"prep_kit_gate","race_slug":"steamboat","race_name":"Steamboat Gravel","website":""}')
assert_status "prep_kit_gate: email + race" "200" "$R"

R=$(post '{"email":"test-quiz@example.com","source":"race_quiz","race_slug":"big-sugar","race_name":"Big Sugar","website":""}')
assert_status "race_quiz: email + race" "200" "$R"

R=$(post '{"email":"test-qs@example.com","source":"quiz_shared","race_slug":"gravel-worlds","race_name":"Gravel Worlds","website":""}')
assert_status "quiz_shared: email + race" "200" "$R"

R=$(post '{"email":"test-fuel@example.com","weight_lbs":"175","race_slug":"unbound","race_name":"Unbound Gravel","target_hours":"10","website":""}')
assert_status "fueling_calculator: full payload" "200" "$R"

echo ""

# ============================================================
# SECTION 2: Rejection paths — validation errors return 400
# ============================================================
echo "--- Rejection Paths (expect 400) ---"

R=$(post '{"source":"exit_intent","website":""}')
assert_status_and_body "missing email" "400" "Missing: email" "$R"

R=$(post '{"email":"not-an-email","source":"exit_intent","website":""}')
assert_status_and_body "invalid email format" "400" "Invalid email" "$R"

R=$(post '{"email":"test@mailinator.com","source":"exit_intent","website":""}')
assert_status_and_body "disposable email domain" "400" "non-disposable" "$R"

R=$(post '{"email":"test@example.com","source":"exit_intent","website":"gotcha"}')
assert_status_and_body "honeypot triggered" "400" "Bot detected" "$R"

R=$(post '{"email":"test@example.com","source":"totally_unknown","website":""}')
assert_status_and_body "unknown source" "400" "Unknown source" "$R"

R=$(post '{"email":"test@example.com","website":""}')
assert_status_and_body "no source, no weight (undetectable)" "400" "Unknown source" "$R"

R=$(post '{"email":"test@example.com","weight_lbs":"175","website":""}')
assert_status_and_body "fueling_calculator: missing race_slug" "400" "Missing: race slug" "$R"

R=$(post '{"email":"test@example.com","weight_lbs":"50","race_slug":"test","website":""}')
assert_status_and_body "fueling_calculator: weight too low" "400" "Weight must be" "$R"

R=$(post '{"email":"test@example.com","weight_lbs":"500","race_slug":"test","website":""}')
assert_status_and_body "fueling_calculator: weight too high" "400" "Weight must be" "$R"

R=$(post '{"email":"test@example.com","weight_lbs":"abc","race_slug":"test","website":""}')
assert_status_and_body "fueling_calculator: weight NaN" "400" "Weight must be" "$R"

echo ""

# ============================================================
# SECTION 3: Protocol-level rejections
# ============================================================
echo "--- Protocol Rejections ---"

# Wrong method
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

# Wrong origin
R=$(post '{"email":"test@example.com","source":"exit_intent","website":""}' "https://evil-site.com")
assert_status "wrong origin rejected" "403" "$R"

# Malformed JSON
TOTAL=$((TOTAL + 1))
BAD_R=$(curl -s -w "\n%{http_code}" -X POST "$WORKER_URL" \
  -H "Content-Type: application/json" \
  -H "Origin: $ORIGIN" \
  -d 'this is not json')
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

# CORS preflight
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
# SECTION 4: Security — HTML injection attempt
# ============================================================
echo "--- Security ---"

R=$(post '{"email":"xss@example.com","source":"race_profile","race_slug":"<script>alert(1)</script>","race_name":"<img src=x onerror=alert(1)>","website":""}')
assert_status "HTML in fields still accepted (escaped server-side)" "200" "$R"

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
