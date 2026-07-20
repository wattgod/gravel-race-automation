import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const workerPath = new URL('../workers/fueling-lead-intake/worker.js', import.meta.url);
const workerSource = readFileSync(workerPath, 'utf8');
const { default: worker } = await import(
  `data:text/javascript;base64,${Buffer.from(workerSource).toString('base64')}`,
);

const env = {
  ALLOWED_ORIGINS: 'https://gravelgodcycling.com',
};

function intakeRequest(payload) {
  return new Request('https://fueling-lead-intake.example.test', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Origin: 'https://gravelgodcycling.com',
    },
    body: JSON.stringify({ website: '', ...payload }),
  });
}

test('accepts bikepacking_guide and forwards guide_chapter to Mission Control', async () => {
  const originalFetch = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (url, options) => {
    requests.push({ url, options });
    return new Response(null, { status: 204 });
  };

  try {
    const response = await worker.fetch(intakeRequest({
      email: 'bikepacking-guide@example.com',
      source: 'bikepacking_guide',
      guide_chapter: 'Fueling for multi-day rides',
    }), {
      ...env,
      MC_WEBHOOK_URL: 'https://mission-control.example.test',
      MC_WEBHOOK_SECRET: 'test-secret',
    });

    assert.equal(response.status, 200);
    assert.equal(requests.length, 1);
    assert.equal(requests[0].url, 'https://mission-control.example.test/webhooks/subscriber');
    assert.deepEqual(JSON.parse(requests[0].options.body), {
      email: 'bikepacking-guide@example.com',
      name: '',
      brand: 'gravelgod',
      source: 'bikepacking_guide',
      race_slug: '',
      race_name: '',
      guide_chapter: 'Fueling for multi-day rides',
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('continues to reject an unknown source', async () => {
  const response = await worker.fetch(intakeRequest({
    email: 'unknown-source@example.com',
    source: 'totally_unknown',
  }), env);

  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), { error: 'Unknown source' });
});
