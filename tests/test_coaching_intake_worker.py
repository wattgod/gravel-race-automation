"""Contract checks for the shared coaching-intake edge Worker."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "workers" / "coaching-intake" / "worker.js"
WRANGLER = ROOT / "workers" / "coaching-intake" / "wrangler.jsonc"


def test_worker_javascript_parses():
    result = subprocess.run(
        ["node", "--check", str(WORKER)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_worker_routes_all_brands_without_trusting_form_brand():
    source = WORKER.read_text()
    assert "'gravelgodcycling.com': 'gravelgod'" in source
    assert "'roadielabs.com': 'roadielabs'" in source
    assert "'xcskilabs.com': 'xcskilabs'" in source
    assert "brandFromOrigin(origin)" in source
    assert "data.brand" not in source


def test_worker_has_honeypot_and_real_backend_submission():
    source = WORKER.read_text()
    assert "data.website" in source
    assert "/api/coaching-intakes" in source
    assert "X-Coaching-Intake-Secret" in source
    assert "Could not submit. Please try again." in source


def test_worker_does_not_create_checkout_from_browser_submission():
    source = WORKER.read_text()
    assert "create-coaching-checkout" not in source
    assert "FIT_REVIEW" in source


def test_worker_preserves_client_submission_receipt_for_safe_retry():
    source = WORKER.read_text()
    assert "UUID_RE.test(requestedSubmissionId)" in source
    assert "submission_id: submissionId" in source
    assert "delete questionnaire.submission_id" in source
    assert "duplicate: Boolean(result.duplicate)" in source
    assert "backend.status === 200 ? 200 : 201" in source


def test_worker_does_not_reflect_cors_for_unknown_origins():
    source = WORKER.read_text()
    assert "if (brandFromOrigin(origin)) Object.assign(headers, corsHeaders(origin));" in source


def test_worker_secret_is_not_committed():
    config = WRANGLER.read_text()
    assert '"COACHING_INTAKE_SECRET"' not in config
    assert '"COACHING_CANARY_SECRET"' not in config
    assert '"compatibility_date": "2026-08-25"' in config
    assert '"compatibility_flags": ["nodejs_compat"]' in config
    assert '"observability"' in config


def test_worker_has_authenticated_edge_to_backend_canary():
    source = WORKER.read_text()
    assert "url.pathname === '/__canary'" in source
    assert "request.method !== 'POST'" in source
    assert 'X-Coaching-Canary-Secret' in source
    assert 'COACHING_CANARY_SECRET' in source
    assert '/api/coaching-canary' in source
    assert 'X-Coaching-Intake-Secret' in source
    assert 'crypto.subtle.timingSafeEqual' in source
    assert "side_effects" not in source  # backend owns the safety claim


def test_worker_uses_structured_error_logs():
    source = WORKER.read_text()
    assert "console.error('Coaching" not in source
    assert 'console.error(JSON.stringify({' in source
