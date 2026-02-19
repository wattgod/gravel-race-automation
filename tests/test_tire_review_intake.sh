#!/usr/bin/env bash
#
# Integration tests for tire-review-intake Cloudflare Worker.
# Tests happy paths, rejection paths, protocol, dedup, and security.
#
# Usage:
#   bash tests/test_tire_review_intake.sh
#   bash tests/test_tire_review_intake.sh https://custom-worker-url.workers.dev
#
# Exit code 0 = all tests pass. Non-zero = at least one failure.
# Run this AFTER every deploy. No exceptions.

set -euo pipefail

WORKER_URL="${1:-https://tire-review-intake.gravelgodcoaching.workers.dev}"
ORIGIN="https://gravelgodcycling.com"
RUN_ID=$(date +%s)
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
echo "=== tire-review-intake Worker Integration Tests ==="
echo "Target: $WORKER_URL"
echo "Run ID: $RUN_ID (test emails use test-tire-*-${RUN_ID}@example.com)"
echo ""

# ============================================================
# SECTION 1: Happy paths (expect 200)
# ============================================================
echo "--- Happy Paths (expect 200) ---"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test Tire\",\"email\":\"test-tire-full-${RUN_ID}@example.com\",\"stars\":5,\"width_ridden\":40,\"pressure_psi\":28,\"conditions\":[\"dry\",\"mixed\"],\"race_used_at\":\"Unbound 200\",\"would_recommend\":\"yes\",\"review_text\":\"Great tire for testing.\",\"website\":\"\"}")
assert_status "full review (all fields)" "200" "$R"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test Tire\",\"email\":\"test-tire-minimal-${RUN_ID}@example.com\",\"stars\":4,\"website\":\"\"}")
assert_status "minimal review (required fields only)" "200" "$R"

echo ""

# ============================================================
# SECTION 2: Rejection paths (expect 400)
# ============================================================
echo "--- Rejection Paths (expect 400) ---"

R=$(post "{\"tire_name\":\"Test\",\"email\":\"test-tire-notid-${RUN_ID}@example.com\",\"stars\":4,\"website\":\"\"}")
assert_status_and_body "missing tire_id" "400" "Missing: tire_id" "$R"

R=$(post "{\"tire_id\":\"has spaces\",\"tire_name\":\"Test\",\"email\":\"test-tire-badid1-${RUN_ID}@example.com\",\"stars\":4,\"website\":\"\"}")
assert_status_and_body "invalid tire_id (spaces)" "400" "Invalid tire_id format" "$R"

R=$(post "{\"tire_id\":\"x\",\"tire_name\":\"Test\",\"email\":\"test-tire-badid2-${RUN_ID}@example.com\",\"stars\":4,\"website\":\"\"}")
assert_status_and_body "invalid tire_id (single char)" "400" "Invalid tire_id format" "$R"

R=$(post "{\"tire_id\":\"../etc/passwd\",\"tire_name\":\"Test\",\"email\":\"test-tire-badid3-${RUN_ID}@example.com\",\"stars\":4,\"website\":\"\"}")
assert_status_and_body "invalid tire_id (path traversal)" "400" "Invalid tire_id format" "$R"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"email\":\"test-tire-noname-${RUN_ID}@example.com\",\"stars\":4,\"website\":\"\"}")
assert_status_and_body "missing tire_name" "400" "Missing: tire_name" "$R"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test\",\"stars\":4,\"website\":\"\"}")
assert_status_and_body "missing email" "400" "Missing: email" "$R"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test\",\"email\":\"not-an-email\",\"stars\":4,\"website\":\"\"}")
assert_status_and_body "invalid email format" "400" "Invalid email" "$R"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test\",\"email\":\"test@mailinator.com\",\"stars\":4,\"website\":\"\"}")
assert_status_and_body "disposable email (mailinator)" "400" "non-disposable" "$R"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test\",\"email\":\"test-tire-nostar-${RUN_ID}@example.com\",\"website\":\"\"}")
assert_status_and_body "missing stars" "400" "Invalid star" "$R"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test\",\"email\":\"test-tire-star0-${RUN_ID}@example.com\",\"stars\":0,\"website\":\"\"}")
assert_status_and_body "stars = 0" "400" "Invalid star" "$R"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test\",\"email\":\"test-tire-star6-${RUN_ID}@example.com\",\"stars\":6,\"website\":\"\"}")
assert_status_and_body "stars = 6" "400" "Invalid star" "$R"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test\",\"email\":\"test-tire-starhalf-${RUN_ID}@example.com\",\"stars\":3.5,\"website\":\"\"}")
assert_status_and_body "stars = 3.5 (float)" "400" "Invalid star" "$R"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test\",\"email\":\"test-tire-wid20-${RUN_ID}@example.com\",\"stars\":4,\"width_ridden\":20,\"website\":\"\"}")
assert_status_and_body "width_ridden = 20 (below 25)" "400" "Invalid width_ridden" "$R"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test\",\"email\":\"test-tire-wid65-${RUN_ID}@example.com\",\"stars\":4,\"width_ridden\":65,\"website\":\"\"}")
assert_status_and_body "width_ridden = 65 (above 60)" "400" "Invalid width_ridden" "$R"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test\",\"email\":\"test-tire-psi10-${RUN_ID}@example.com\",\"stars\":4,\"pressure_psi\":10,\"website\":\"\"}")
assert_status_and_body "pressure_psi = 10 (below 15)" "400" "Invalid pressure_psi" "$R"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test\",\"email\":\"test-tire-psi70-${RUN_ID}@example.com\",\"stars\":4,\"pressure_psi\":70,\"website\":\"\"}")
assert_status_and_body "pressure_psi = 70 (above 60)" "400" "Invalid pressure_psi" "$R"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test\",\"email\":\"test-tire-badcond-${RUN_ID}@example.com\",\"stars\":4,\"conditions\":[\"snow\"],\"website\":\"\"}")
assert_status_and_body "conditions = [snow] (invalid)" "400" "Invalid conditions" "$R"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test\",\"email\":\"test-tire-condstr-${RUN_ID}@example.com\",\"stars\":4,\"conditions\":\"dry\",\"website\":\"\"}")
assert_status_and_body "conditions = string (not array)" "400" "Invalid conditions" "$R"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test\",\"email\":\"test-tire-rec-${RUN_ID}@example.com\",\"stars\":4,\"would_recommend\":\"maybe\",\"website\":\"\"}")
assert_status_and_body "would_recommend = maybe (invalid)" "400" "Invalid would_recommend" "$R"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test\",\"email\":\"test-tire-bot-${RUN_ID}@example.com\",\"stars\":4,\"website\":\"gotcha\"}")
assert_status_and_body "honeypot triggered" "400" "Bot detected" "$R"

echo ""

# ============================================================
# SECTION 3: Protocol rejections
# ============================================================
echo "--- Protocol Rejections ---"

# GET request
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
R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test\",\"email\":\"test-tire-origin-${RUN_ID}@example.com\",\"stars\":4,\"website\":\"\"}" "https://evil-site.com")
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
# SECTION 4: Dedup (expect 409)
# ============================================================
echo "--- Dedup (expect 409) ---"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"Test Tire\",\"email\":\"test-tire-full-${RUN_ID}@example.com\",\"stars\":3,\"website\":\"\"}")
assert_status_and_body "resubmit same email+tire" "409" "already reviewed" "$R"

echo ""

# ============================================================
# SECTION 5: Security
# ============================================================
echo "--- Security ---"

R=$(post "{\"tire_id\":\"zzz-test-tire\",\"tire_name\":\"<script>alert(1)</script>\",\"email\":\"test-tire-xss-${RUN_ID}@example.com\",\"stars\":5,\"review_text\":\"<img src=x onerror=alert(1)>\",\"website\":\"\"}")
assert_status "HTML injection in fields (escaped server-side)" "200" "$R"

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
