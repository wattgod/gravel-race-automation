#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Integration tests for the course-access Cloudflare Worker (D1)
#
# Usage:
#   bash tests/test_course_access.sh
#   bash tests/test_course_access.sh https://course-access.your-workers.dev
#
# Pattern: Same as tests/test_worker_intake.sh
# ──────────────────────────────────────────────────────────────

set -euo pipefail

WORKER_URL="${1:-https://course-access.gravelgodcoaching.workers.dev}"
ORIGIN="https://gravelgodcycling.com"
PASS=0
FAIL=0
TOTAL=0

# ── Helpers ──────────────────────────────────────────────────

post() {
  local path="$1"
  local data="$2"
  local origin="${3:-$ORIGIN}"
  curl -s -w "\n%{http_code}" -X POST "${WORKER_URL}${path}" \
    -H "Content-Type: application/json" \
    -H "Origin: $origin" \
    -d "$data"
}

post_auth() {
  local path="$1"
  local data="$2"
  local key="${3:-test-admin-key}"
  curl -s -w "\n%{http_code}" -X POST "${WORKER_URL}${path}" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $key" \
    -d "$data"
}

assert_status() {
  local test_name="$1"
  local expected_status="$2"
  local response="$3"

  TOTAL=$((TOTAL + 1))
  local status body
  status=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')

  if [ "$status" = "$expected_status" ]; then
    PASS=$((PASS + 1))
    printf "  PASS  %-60s [%s]\n" "$test_name" "$status"
  else
    FAIL=$((FAIL + 1))
    printf "  FAIL  %-60s [got %s, expected %s]\n" "$test_name" "$status" "$expected_status"
    printf "        body: %s\n" "$body"
  fi
}

assert_body_contains() {
  local test_name="$1"
  local expected="$2"
  local response="$3"

  TOTAL=$((TOTAL + 1))
  local body
  body=$(echo "$response" | sed '$d')

  if echo "$body" | grep -q "$expected"; then
    PASS=$((PASS + 1))
    printf "  PASS  %-60s [contains '%s']\n" "$test_name" "$expected"
  else
    FAIL=$((FAIL + 1))
    printf "  FAIL  %-60s [missing '%s']\n" "$test_name" "$expected"
    printf "        body: %s\n" "$body"
  fi
}

echo "============================================================"
echo "  Course Access Worker — Integration Tests (D1)"
echo "  URL: $WORKER_URL"
echo "============================================================"
echo ""

# ── 1. CORS Preflight ────────────────────────────────────────

echo "--- CORS Preflight ---"

TOTAL=$((TOTAL + 1))
CORS_R=$(curl -s -w "\n%{http_code}" -X OPTIONS "$WORKER_URL/verify" \
  -H "Origin: $ORIGIN" \
  -H "Access-Control-Request-Method: POST")
CORS_STATUS=$(echo "$CORS_R" | tail -1)
if [ "$CORS_STATUS" = "204" ]; then
  PASS=$((PASS + 1))
  printf "  PASS  %-60s [%s]\n" "OPTIONS returns 204" "$CORS_STATUS"
else
  FAIL=$((FAIL + 1))
  printf "  FAIL  %-60s [got %s, expected 204]\n" "OPTIONS returns 204" "$CORS_STATUS"
fi

echo ""

# ── 2. Protocol-Level Rejections ─────────────────────────────

echo "--- Protocol Rejections ---"

TOTAL=$((TOTAL + 1))
GET_R=$(curl -s -w "\n%{http_code}" -X GET "$WORKER_URL/verify" -H "Origin: $ORIGIN")
GET_STATUS=$(echo "$GET_R" | tail -1)
if [ "$GET_STATUS" = "405" ]; then
  PASS=$((PASS + 1))
  printf "  PASS  %-60s [%s]\n" "GET request rejected" "$GET_STATUS"
else
  FAIL=$((FAIL + 1))
  printf "  FAIL  %-60s [got %s, expected 405]\n" "GET request rejected" "$GET_STATUS"
fi

R=$(post "/verify" '{"email":"test@example.com","course_id":"test"}' "https://evil-site.com")
assert_status "wrong origin rejected" "403" "$R"

R=$(post "/verify" 'not json at all')
assert_status "malformed JSON rejected" "400" "$R"

R=$(post "/verify" '{"email":"test@example.com","course_id":"test","website":"http://spam.com"}')
assert_status "honeypot triggers rejection" "400" "$R"

echo ""

# ── 3. /verify Endpoint ─────────────────────────────────────

echo "--- /verify Endpoint ---"

R=$(post "/verify" '{"email":"test@example.com","course_id":"gravel-hydration-mastery"}')
assert_status "verify valid request returns 200" "200" "$R"
assert_body_contains "verify returns has_access field" "has_access" "$R"

R=$(post "/verify" '{"course_id":"gravel-hydration-mastery"}')
assert_status "verify missing email returns 400" "400" "$R"

R=$(post "/verify" '{"email":"test@example.com"}')
assert_status "verify missing course_id returns 400" "400" "$R"

R=$(post "/verify" '{"email":"not-an-email","course_id":"test"}')
assert_status "verify invalid email format returns 400" "400" "$R"

R=$(post "/verify" '{"email":"test@mailinator.com","course_id":"test"}')
assert_status "verify disposable email rejected" "400" "$R"

R=$(post "/verify" '{"email":"test@example.com","course_id":"../../../etc/passwd"}')
assert_status "verify path traversal in course_id rejected" "400" "$R"

R=$(post "/verify" '{"email":"test@example.com","course_id":"test<script>"}')
assert_status "verify XSS in course_id rejected" "400" "$R"

echo ""

# ── 4. /progress Endpoint ───────────────────────────────────

echo "--- /progress Endpoint ---"

R=$(post "/progress" '{"email":"test@example.com","course_id":"gravel-hydration-mastery","action":"get"}')
# Will return 403 if no access, which is correct behavior
assert_status "progress without access returns 403" "403" "$R"

R=$(post "/progress" '{"email":"test@example.com","course_id":"gravel-hydration-mastery"}')
assert_status "progress missing action returns 400" "400" "$R"

R=$(post "/progress" '{"email":"test@example.com","action":"get"}')
assert_status "progress missing course_id returns 400" "400" "$R"

R=$(post "/progress" '{"course_id":"gravel-hydration-mastery","action":"get"}')
assert_status "progress missing email returns 400" "400" "$R"

R=$(post "/progress" '{"email":"test@example.com","course_id":"gravel-hydration-mastery","action":"invalid"}')
# Will return 403 (no access) before hitting action validation
assert_status "progress invalid action with no access returns 403" "403" "$R"

echo ""

# ── 5. /webhook Endpoint ────────────────────────────────────

echo "--- /webhook Endpoint (Stripe) ---"

# Webhook has no origin check but requires stripe-signature
TOTAL=$((TOTAL + 1))
WH_R=$(curl -s -w "\n%{http_code}" -X POST "${WORKER_URL}/webhook" \
  -H "Content-Type: application/json" \
  -d '{"type":"checkout.session.completed"}')
WH_STATUS=$(echo "$WH_R" | tail -1)
if [ "$WH_STATUS" = "401" ]; then
  PASS=$((PASS + 1))
  printf "  PASS  %-60s [%s]\n" "webhook without signature rejected" "$WH_STATUS"
else
  FAIL=$((FAIL + 1))
  printf "  FAIL  %-60s [got %s, expected 401]\n" "webhook without signature rejected" "$WH_STATUS"
fi

TOTAL=$((TOTAL + 1))
WH_R=$(curl -s -w "\n%{http_code}" -X POST "${WORKER_URL}/webhook" \
  -H "Content-Type: application/json" \
  -H "stripe-signature: t=999999999,v1=fakesigfakesig" \
  -d '{"type":"checkout.session.completed"}')
WH_STATUS=$(echo "$WH_R" | tail -1)
if [ "$WH_STATUS" = "401" ]; then
  PASS=$((PASS + 1))
  printf "  PASS  %-60s [%s]\n" "webhook with invalid signature rejected" "$WH_STATUS"
else
  FAIL=$((FAIL + 1))
  printf "  FAIL  %-60s [got %s, expected 401]\n" "webhook with invalid signature rejected" "$WH_STATUS"
fi

echo ""

# ── 6. /kc Endpoint ──────────────────────────────────────────

echo "--- /kc Endpoint ---"

R=$(post "/kc" '{"email":"test@example.com","course_id":"gravel-hydration-mastery","lesson_id":"lesson-01","question_hash":"abcd1234","selected_index":0,"correct":true}')
assert_status "kc without access returns 403" "403" "$R"

R=$(post "/kc" '{"course_id":"gravel-hydration-mastery","lesson_id":"lesson-01","question_hash":"abcd1234","selected_index":0,"correct":true}')
assert_status "kc missing email returns 400" "400" "$R"

R=$(post "/kc" '{"email":"test@example.com","lesson_id":"lesson-01","question_hash":"abcd1234","selected_index":0,"correct":true}')
assert_status "kc missing course_id returns 400" "400" "$R"

R=$(post "/kc" '{"email":"test@example.com","course_id":"gravel-hydration-mastery","question_hash":"abcd1234","selected_index":0,"correct":true}')
assert_status "kc missing lesson_id returns 400" "400" "$R"

R=$(post "/kc" '{"email":"test@example.com","course_id":"gravel-hydration-mastery","lesson_id":"lesson-01","selected_index":0,"correct":true}')
assert_status "kc missing question_hash returns 400" "400" "$R"

R=$(post "/kc" '{"email":"test@example.com","course_id":"gravel-hydration-mastery","lesson_id":"lesson-01","question_hash":"invalid!","selected_index":0,"correct":true}')
assert_status "kc invalid question_hash format returns 400" "400" "$R"

echo ""

# ── 7. /stats Endpoint ───────────────────────────────────────

echo "--- /stats Endpoint ---"

R=$(post "/stats" '{"email":"test@example.com"}')
# Returns 404 if user not found, or 200 with stats
TOTAL=$((TOTAL + 1))
STATS_STATUS=$(echo "$R" | tail -1)
if [ "$STATS_STATUS" = "200" ] || [ "$STATS_STATUS" = "404" ]; then
  PASS=$((PASS + 1))
  printf "  PASS  %-60s [%s]\n" "stats returns 200 or 404" "$STATS_STATUS"
else
  FAIL=$((FAIL + 1))
  printf "  FAIL  %-60s [got %s, expected 200|404]\n" "stats returns valid response" "$STATS_STATUS"
fi

R=$(post "/stats" '{}')
assert_status "stats missing email returns 400" "400" "$R"

R=$(post "/stats" '{"email":"not-an-email"}')
assert_status "stats invalid email returns 400" "400" "$R"

echo ""

# ── 8. /leaderboard Endpoint ─────────────────────────────────

echo "--- /leaderboard Endpoint ---"

R=$(post "/leaderboard" '{"course_id":"gravel-hydration-mastery"}')
assert_status "leaderboard returns 200" "200" "$R"
assert_body_contains "leaderboard returns leaderboard field" "leaderboard" "$R"

R=$(post "/leaderboard" '{}')
assert_status "leaderboard missing course_id returns 400" "400" "$R"

R=$(post "/leaderboard" '{"course_id":"test<script>"}')
assert_status "leaderboard XSS in course_id rejected" "400" "$R"

echo ""

# ── 9. /admin/* Endpoints ────────────────────────────────────

echo "--- /admin Endpoints ---"

R=$(post_auth "/admin/dashboard" '{}' "wrong-key")
assert_status "admin dashboard wrong key returns 401" "401" "$R"

R=$(post "/admin/dashboard" '{}')
# No auth header, should get 401
assert_status "admin dashboard no auth returns 401" "401" "$R"

R=$(post_auth "/admin/grant" '{}' "wrong-key")
assert_status "admin grant wrong key returns 401" "401" "$R"

echo ""

# ── 10. /unsubscribe Endpoint ────────────────────────────────

echo "--- /unsubscribe Endpoint ---"

TOTAL=$((TOTAL + 1))
UNSUB_R=$(curl -s -w "\n%{http_code}" -X GET "${WORKER_URL}/unsubscribe")
UNSUB_STATUS=$(echo "$UNSUB_R" | tail -1)
if [ "$UNSUB_STATUS" = "400" ]; then
  PASS=$((PASS + 1))
  printf "  PASS  %-60s [%s]\n" "unsubscribe missing params returns 400" "$UNSUB_STATUS"
else
  FAIL=$((FAIL + 1))
  printf "  FAIL  %-60s [got %s, expected 400]\n" "unsubscribe missing params returns 400" "$UNSUB_STATUS"
fi

TOTAL=$((TOTAL + 1))
UNSUB_R=$(curl -s -w "\n%{http_code}" -X GET "${WORKER_URL}/unsubscribe?token=invalidtoken")
UNSUB_STATUS=$(echo "$UNSUB_R" | tail -1)
if [ "$UNSUB_STATUS" = "400" ]; then
  PASS=$((PASS + 1))
  printf "  PASS  %-60s [%s]\n" "unsubscribe missing email returns 400" "$UNSUB_STATUS"
else
  FAIL=$((FAIL + 1))
  printf "  FAIL  %-60s [got %s, expected 400]\n" "unsubscribe missing email returns 400" "$UNSUB_STATUS"
fi

TOTAL=$((TOTAL + 1))
UNSUB_R=$(curl -s -w "\n%{http_code}" -X GET "${WORKER_URL}/unsubscribe?email=test%40example.com&token=invalidtoken")
UNSUB_STATUS=$(echo "$UNSUB_R" | tail -1)
if [ "$UNSUB_STATUS" = "400" ]; then
  PASS=$((PASS + 1))
  printf "  PASS  %-60s [%s]\n" "unsubscribe invalid token returns 400" "$UNSUB_STATUS"
else
  FAIL=$((FAIL + 1))
  printf "  FAIL  %-60s [got %s, expected 400]\n" "unsubscribe invalid token returns 400" "$UNSUB_STATUS"
fi

echo ""

# ── 11. Unknown Routes ───────────────────────────────────────

echo "--- Unknown Routes ---"

R=$(post "/nonexistent" '{"email":"test@example.com"}')
assert_status "unknown path returns 404" "404" "$R"

echo ""

# ── Summary ──────────────────────────────────────────────────

echo "============================================================"
echo "  Results: $PASS/$TOTAL passed, $FAIL failed"
echo "============================================================"

if [ "$FAIL" -gt 0 ]; then
  echo "BLOCKED: Fix failures before deploying."
  exit 1
else
  echo "All tests passed."
  exit 0
fi
