"""review-intake Worker: a review is stored before the form is told it arrived.

Runs the real worker.js under Node with an in-memory KV and a stubbed Resend.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "workers" / "review-intake" / "worker.js"
WRANGLER = ROOT / "workers" / "review-intake" / "wrangler.toml"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

HARNESS = r"""
import worker from './worker.mjs';
const scenario = JSON.parse(process.argv[2]);
const store = new Map();
const kv = {
  async put(k, v, opts) {
    if (scenario.kvFails) throw new Error('kv down');
    store.set(k, { v, meta: opts && opts.metadata });
  },
};
const sent = [];
globalThis.fetch = async (url, init) => {
  sent.push(JSON.parse(init.body));
  return { ok: !scenario.resendFails, status: scenario.resendFails ? 500 : 200, text: async () => '' };
};
const env = {
  ALLOWED_ORIGINS: 'https://gravelgodcycling.com,https://roadielabs.com',
  RESEND_API_KEY: 'k', NOTIFICATION_EMAIL: 'n@example.com',
};
if (!scenario.noBinding) env.RACE_REVIEWS = kv;
const req = new Request('https://w.example/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', Origin: scenario.origin },
  body: JSON.stringify({ email: 'rider@example.com', race_slug: 'unbound-200', race_name: 'Unbound', stars: 4 }),
});
const origLog = console.log; const origErr = console.error;
console.log = () => {}; console.error = () => {};
const resp = await worker.fetch(req, env);
console.log = origLog; console.error = origErr;
const body = await resp.json();
const records = [...store.values()].map(r => ({ data: JSON.parse(r.v), meta: r.meta }));
console.log(JSON.stringify({ status: resp.status, body, records, sent }));
"""


def run(tmp_path, **scenario):
    scenario.setdefault("origin", "https://gravelgodcycling.com")
    shutil.copy(WORKER, tmp_path / "worker.mjs")
    (tmp_path / "harness.mjs").write_text(HARNESS)
    out = subprocess.run(
        ["node", str(tmp_path / "harness.mjs"), json.dumps(scenario)],
        capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_stores_then_notifies(tmp_path):
    r = run(tmp_path)
    assert r["status"] == 200 and r["body"]["success"] is True
    assert len(r["records"]) == 1
    assert r["records"][0]["meta"]["notified"] is True
    assert r["records"][0]["data"]["brand"] == "gravelgod"
    assert r["sent"][0]["from"].endswith("<noreply@gravelgodcycling.com>")


def test_store_failure_is_an_error_not_a_thank_you(tmp_path):
    r = run(tmp_path, kvFails=True)
    assert r["status"] == 503
    assert "success" not in r["body"]
    assert r["sent"] == []


def test_missing_binding_is_an_error(tmp_path):
    r = run(tmp_path, noBinding=True)
    assert r["status"] == 503


def test_email_failure_keeps_the_stored_review_and_retries(tmp_path):
    r = run(tmp_path, resendFails=True)
    assert r["status"] == 200
    assert r["records"][0]["meta"]["notified"] is False
    assert len(r["sent"]) == 2


def test_roadie_origin_uses_roadie_sender(tmp_path):
    r = run(tmp_path, origin="https://roadielabs.com")
    assert r["records"][0]["data"]["brand"] == "roadielabs"
    assert r["sent"][0]["from"] == "Roadie Labs Reviews <noreply@roadielabs.com>"
    assert r["sent"][0]["subject"].startswith("[RL Review]")


def test_wrangler_binds_kv_and_allows_both_brands():
    toml = WRANGLER.read_text()
    assert 'binding = "RACE_REVIEWS"' in toml
    assert "https://gravelgodcycling.com" in toml
    assert "https://roadielabs.com" in toml
