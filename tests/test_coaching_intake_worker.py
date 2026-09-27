"""Contract checks for the shared coaching-intake edge Worker."""

import json
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


def test_worker_forwards_only_consent_gated_valid_ga4_attribution():
    source = WORKER.read_text()
    assert "data.analytics_consent === 'granted'" in source
    assert "GA4_CLIENT_ID_RE.test(requestedGa4ClientId)" in source
    assert "GA4_SESSION_ID_RE.test(requestedGa4SessionId)" in source
    assert "ga4_client_id: ga4ClientId" in source
    assert "ga4_session_id: ga4SessionId" in source
    assert "delete questionnaire.ga4_client_id" in source
    assert "delete questionnaire.ga4_session_id" in source


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


def test_worker_forwards_free_text_answers_verbatim_to_backend():
    """Run the Worker and capture the backend body: a questionnaire answer
    the Worker has never heard of (normal_week) must reach Railway unchanged.
    """
    answer = "Mon off.\nTue 2x20 on the trainer.\nSat group ride, 4 hours."
    script = f"""
const worker = (await import({json.dumps(WORKER.as_uri())})).default;
let forwarded = null;
globalThis.fetch = async (url, init) => {{
  forwarded = {{ url, body: JSON.parse(init.body) }};
  return new Response(JSON.stringify({{ case_id: 'c', state: 'FIT_REVIEW' }}),
                      {{ status: 201 }});
}};
const request = new Request('https://coaching-intake.example.workers.dev/', {{
  method: 'POST',
  headers: {{ 'Origin': 'https://gravelgodcycling.com',
             'Content-Type': 'application/json' }},
  body: JSON.stringify({{ name: 'A Rider', email: 'a@example.com', tier: 'mid',
                         normal_week: {json.dumps(answer)} }}),
}});
const response = await worker.fetch(request, {{
  PIPELINE_URL: 'https://pipeline.example', COACHING_INTAKE_SECRET: 's' }});
process.stdout.write(JSON.stringify({{ status: response.status, forwarded }}));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["status"] == 201
    assert out["forwarded"]["url"] == "https://pipeline.example/api/coaching-intakes"
    assert out["forwarded"]["body"]["brand"] == "gravelgod"
    assert out["forwarded"]["body"]["questionnaire"]["normal_week"] == answer
