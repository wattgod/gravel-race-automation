"""Contract checks for case-bound coaching course access and progress."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "workers" / "course-access" / "worker.js"
SCHEMA = ROOT / "workers" / "course-access" / "schema.sql"
MIGRATION = (
    ROOT / "workers" / "course-access" / "migrations" /
    "0001_case_bound_onboarding.sql"
)


def test_case_binding_is_persisted_for_manual_grants():
    source = WORKER.read_text()
    assert "case_id, athlete_key, brand, tier" in source
    assert "Valid case_id and athlete_key are required together" in source
    assert "idx_enrollments_case_course" in SCHEMA.read_text()
    migration = MIGRATION.read_text()
    assert "ALTER TABLE enrollments ADD COLUMN case_id TEXT" in migration
    assert "ALTER TABLE enrollments ADD COLUMN athlete_key TEXT" in migration
    personalization_migration = (
        ROOT / "workers" / "course-access" / "migrations" /
        "0002_safe_personalization.sql"
    ).read_text()
    assert "ALTER TABLE enrollments ADD COLUMN preferred_name TEXT" in personalization_migration
    assert "ALTER TABLE enrollments ADD COLUMN goal_label TEXT" in personalization_migration


def test_new_lesson_progress_syncs_without_email_or_health_data():
    source = WORKER.read_text()
    sync_body = source.split("async function syncCoachingProgress", 1)[1]
    assert "X-Coaching-Course-Secret" in sync_body
    assert "ctx.waitUntil(progressEvent)" in source
    assert "case_id: enrollment.case_id" in source
    assert "athlete_key: enrollment.athlete_key" in source
    assert "email:" not in sync_body.split("//", 1)[0]
    assert "health" not in sync_body.split("//", 1)[0].lower()


def test_progress_event_is_stable_for_safe_retry():
    source = WORKER.read_text()
    assert "event_id: `course:${enrollment.id}:${courseId}:${lessonId}`" in source


def test_verify_returns_only_safe_course_personalization():
    source = WORKER.read_text()
    verify = source.split("async function handleVerify", 1)[1].split(
        "// ── Progress Endpoint", 1)[0]
    assert "preferred_name" in verify
    assert "goal_label" in verify
    assert "health" not in verify.lower()
    assert "questionnaire" not in verify.lower()


def test_daily_canary_is_no_write_and_checks_both_boundaries():
    source = WORKER.read_text()
    config = (ROOT / "workers" / "course-access" / "wrangler.toml").read_text()
    canary = source.split("async function runCourseCanary", 1)[1].split(
        "// ── Email + User Helpers", 1)[0]
    assert "async scheduled(" in source
    assert "runCourseCanary(env)" in source
    assert "PRAGMA table_info(enrollments)" in canary
    assert "/api/coaching-course-progress" in canary
    assert "/api/coaching-activation" in canary
    assert "Valid case_id is required" in canary
    assert "authenticated_activation_bridge" in canary
    assert "'/admin/canary'" in source
    assert "INSERT" not in canary
    assert "UPDATE" not in canary
    assert 'crons = ["23 14 * * *"]' in config


def test_coaching_activation_uses_case_bound_expiring_token_not_email():
    source = WORKER.read_text()
    migration = (
        ROOT / "workers" / "course-access" / "migrations" /
        "0003_activation_access_tokens.sql"
    ).read_text()
    verify = source.split("async function handleVerify", 1)[1].split(
        "// ── Coaching Activation Endpoint", 1)[0]
    activation = source.split("async function handleActivation", 1)[1].split(
        "// ── Progress Endpoint", 1)[0]
    assert "getActivationEnrollment(data, env)" in verify
    assert "data.course_id === COACHING_COURSE_ID" in verify
    assert "email" not in verify.split("if (data.course_id", 1)[1].split("}\n", 1)[0]
    assert "access_token_hash" in source
    assert "access_token_expires_at > ?" in source
    assert "case_id: enrollment.case_id" in activation
    assert "athlete_key: enrollment.athlete_key" in activation
    assert "email" not in activation.lower()
    assert "ALTER TABLE enrollments ADD COLUMN access_token_hash TEXT" in migration
    assert "idx_enrollments_access_token" in migration


def test_coaching_grant_returns_raw_token_once_and_stores_only_hash():
    source = WORKER.read_text()
    grant = source.split("async function handleAdminGrant", 1)[1].split(
        "// ── Unsubscribe Endpoint", 1)[0]
    assert "generateAccessToken()" in grant
    assert "sha256Hex(accessToken)" in grant
    assert "access_token: accessToken" in grant
    insert = grant.split("INSERT INTO enrollments", 1)[1].split(".run()", 1)[0]
    assert "access_token_hash" in insert
    assert "access_token," not in insert
    assert "Coaching activation access must be case-bound" in grant


def test_coaching_grant_rejects_cross_account_case_rebinding_cleanly():
    source = WORKER.read_text()
    grant = source.split("async function handleAdminGrant", 1)[1].split(
        "// ── Unsubscribe Endpoint", 1)[0]
    guard = grant.split("let accessToken = null", 1)[0]
    assert "WHERE e.case_id = ? AND e.course_id = ?" in guard
    assert "existingCaseEnrollment.email !== email" in guard
    assert "Coaching activation case is already bound to another account" in guard
    assert "}, 409, origin)" in guard
