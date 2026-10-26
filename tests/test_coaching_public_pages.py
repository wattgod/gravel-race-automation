"""Execute the deployed Worker handlers with controlled public HTTP responses."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / 'workers/coaching-intake/worker.js'


def test_authenticated_public_probe_fails_closed_and_bounds_its_fetches():
    script = r'''
import { timingSafeEqual } from 'node:crypto';
crypto.subtle.timingSafeEqual = (a, b) => timingSafeEqual(Buffer.from(a), Buffer.from(b));
const worker = (await import(WORKER_URL)).default;
const { probePublicPages } = await import(PAGES_URL);
const assert = (await import('node:assert/strict')).default;
const env = {COACHING_CANARY_SECRET: 'test-only'};
const req = (method='POST', secret='test-only') => new Request(
  'https://edge.example/__pages?url=http://127.0.0.1',
  {method, headers:{'X-Coaching-Canary-Secret': secret}});
let calls = [];
const good = '<html>coaching_intake_submission_id coaching-intake ' + 'x'.repeat(500) + '</html>';
globalThis.fetch = async (url, init) => {
  calls.push(url);
  assert.equal(init.redirect, 'manual');
  assert.equal(init.cache, 'no-store');
  assert.ok(init.signal instanceof AbortSignal);
  return new Response(good, {headers:{'Content-Type':'text/html'}});
};
for (const [request, bindings, expected] of [
  [req('GET'), env, 405], [req('POST','wrong'), env, 401],
  [req('POST',''), env, 401], [req(), {}, 503],
]) {
  assert.equal((await worker.fetch(request, bindings)).status, expected);
  assert.equal(calls.length, 0);
}
const response = await worker.fetch(req(), env);
assert.equal(response.status, 200);
assert.equal(response.headers.get('Cache-Control'), 'no-store');
assert.equal(response.headers.get('Access-Control-Allow-Origin'), null);
const result = await response.json();
assert.equal(result.status, 'ok');
assert.equal(result.schema, 'coaching_public_pages/v1');
assert.ok(!Number.isNaN(Date.parse(result.generated_at)));
const expected = ['gravelgodcycling.com', 'roadielabs.com', 'xcskilabs.com'].flatMap(
  host => ['/coaching/','/coaching/apply/','/coaching/welcome/'].map(path => `https://${host}${path}`));
assert.deepEqual(calls, expected);
assert.equal(result.pages.length, 9);
assert.ok(result.pages.every(page => page.ok && page.status === 200));
assert.ok(!JSON.stringify(result).includes('<html>'));
for (const [makeResponse, reason] of [
  [() => new Response('holding', {status:202}), 'http_status'],
  [() => new Response('', {status:302, headers:{Location:'http://127.0.0.1'}}), 'http_status'],
  [() => new Response('tiny', {headers:{'Content-Type':'text/html'}}), 'short_body'],
  [() => new Response(good, {headers:{'Content-Type':'text/plain'}}), 'not_html'],
  [() => new Response(good + 'sgcaptcha', {headers:{'Content-Type':'text/html'}}), 'challenge'],
  [() => new Response('x'.repeat(2_000_001)), 'body_too_large'],
  [() => { throw new Error('private-provider-detail'); }, 'fetch_failed'],
]) {
  const failed = await probePublicPages(async () => makeResponse());
  assert.equal(failed.status, 'failed');
  assert.equal(failed.pages.length, 9);
  assert.ok(failed.pages.every(page => !page.ok && page.error === reason));
  assert.ok(!JSON.stringify(failed).includes('private-provider-detail'));
}
const absentForm = await probePublicPages(async () => new Response('x'.repeat(600), {headers:{'Content-Type':'text/html'}}));
assert.equal(absentForm.pages.filter(page => page.error === 'intake_contract_missing').length, 3);
assert.equal(absentForm.status, 'failed');
const legacy = 'action="https://formsubmit.co/test" name="_next" value="https://xcskilabs.com/coaching/apply/?submitted=true" name="email" id="submitBtn" ' + 'x'.repeat(500);
const mixed = await probePublicPages(async () => new Response(legacy, {headers:{'Content-Type':'text/html'}}));
assert.equal(mixed.pages.find(page => page.url === 'https://xcskilabs.com/coaching/apply/').ok, true);
assert.equal(mixed.pages.find(page => page.url === 'https://roadielabs.com/coaching/apply/').ok, false);
console.log('public page contracts passed');
'''.replace('WORKER_URL', json.dumps(WORKER.as_uri())).replace(
        'PAGES_URL', json.dumps(WORKER.with_name('public-pages.js').as_uri()))
    result = subprocess.run(['node', '--input-type=module', '-e', script],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
