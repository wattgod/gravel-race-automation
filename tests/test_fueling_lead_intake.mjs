import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test, { mock } from 'node:test';

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

// --- athlete_exit: the exit survey at /coaching/exit/ ---------------------

const exitFixture = JSON.parse(readFileSync(
  new URL('./fixtures/exit_survey_submission.json', import.meta.url), 'utf8',
));

const exitEnv = {
  ...env,
  MC_WEBHOOK_URL: 'https://mission-control.example.test',
  MC_WEBHOOK_SECRET: 'test-secret',
  RESEND_API_KEY: 'test-resend-key',
  NOTIFICATION_EMAIL: 'coach@example.com',
};

async function runExit(payload, { mcStatus = 200, now = '2026-09-29T12:00:00Z' } = {}) {
  const originalFetch = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (url, options) => {
    requests.push({ url: String(url), body: JSON.parse(options.body) });
    const status = String(url).includes('mission-control') ? mcStatus : 200;
    return new Response(JSON.stringify({ status: 'ok', id: 'x' }), { status });
  };
  mock.timers.enable({ apis: ['Date'], now: new Date(now) });
  try {
    const response = await worker.fetch(intakeRequest(payload), exitEnv);
    const mc = requests.find((r) => r.url.endsWith('/webhooks/subscriber'));
    const alert = requests.find((r) => r.url === 'https://api.resend.com/emails');
    return { response, requests, mc: mc && mc.body, alert: alert && alert.body };
  } finally {
    mock.timers.reset();
    globalThis.fetch = originalFetch;
  }
}

function exitPayload(answers = exitFixture.goal_answers, extra = {}) {
  return {
    source: 'athlete_exit', brand: 'gravelgod',
    name: exitFixture.name, email: exitFixture.email, athlete: exitFixture.athlete,
    goal_answers: answers, ...extra,
  };
}

test('athlete_exit forwards every answer and the athlete tag to Mission Control', async () => {
  const { response, mc } = await runExit(exitPayload());
  assert.equal(response.status, 200);
  assert.equal(mc.source, 'athlete_exit');
  assert.equal(mc.athlete, 'test-rider-a');
  assert.deepEqual(mc.goal_answers, exitFixture.goal_answers);
});

test('athlete_exit never carries lead context to Mission Control', async () => {
  const { mc } = await runExit(exitPayload(exitFixture.goal_answers, {
    race_slug: 'unbound-200', race_name: 'Unbound', offer_variant: 'A', entry_src: 'race',
    goal_type: 'finish', viewed_races: ['Unbound'], guide_chapter: 'Race Selection',
  }));
  assert.equal(mc.race_slug, '');
  assert.equal(mc.race_name, '');
  for (const key of ['offer_variant', 'entry_src', 'goal_type', 'viewed_races', 'guide_chapter']) {
    assert.equal(key in mc, false, key);
  }
});

test('athlete_exit alerts Matti through Resend only, never a marketing list', async () => {
  const { requests, alert } = await runExit(exitPayload());
  assert.deepEqual(requests.map((r) => r.url).sort(), [
    'https://api.resend.com/emails',
    'https://mission-control.example.test/webhooks/subscriber',
  ]);
  assert.equal(alert.subject, '[GG] Exit survey · Test Rider A · Life got full');
  assert.equal(alert.from, 'Gravel God <noreply@gravelgodcycling.com>');
  assert.deepEqual(alert.to, ['coach@example.com']);
  assert.equal(alert.reply_to, exitFixture.email);
});

test('the alert carries every answer, and the next actions come first', async () => {
  const { alert } = await runExit(exitPayload());
  const html = alert.html;
  for (const key of Object.keys(exitFixture.goal_answers)) {
    assert.ok(html.includes(`>${key}</td>`), `answer ${key} missing from the alert`);
  }
  const next = html.indexOf('NEXT ACTIONS');
  assert.ok(next > 0 && next < html.indexOf('<table'));
  assert.ok(html.includes(
    'Consent to share: first name + last initial; channels: gravelgodcycling.com, '
    + 'Gravel God social posts, Emails to riders thinking about coaching, My TrainingPeaks coach profile; '
    + "connection: We're friends or ride together. Next: send the exact wording + render for approval. "
    + 'Ledger entry needs quote_approved_at and render_approved_at before it can render.',
  ), html);
  assert.ok(html.includes('Add to the talk-to-an-athlete roster (ask first).'));
  assert.ok(html.includes('Check in around March 2027 (In about six months).'));
  assert.ok(html.includes('Asked for: A summary of my zones and latest tests; Notes for training on my own; '
    + 'Confirmation that billing has stopped; Help with my TrainingPeaks account.'));
  assert.ok(html.includes('<b>Recommend:</b> 8/10'));
  assert.ok(html.includes('test-rider-a'));
});

test('check-in months count on from today', async () => {
  const month = async (checkin, now) => {
    const { alert } = await runExit(exitPayload({ exit_reason: 'done', checkin }), { now });
    return (alert.html.match(/Check in around ([A-Za-z]+ \d{4})/) || [])[1];
  };
  assert.equal(await month('3m', '2026-09-29T12:00:00Z'), 'December 2026');
  assert.equal(await month('6m', '2026-09-29T12:00:00Z'), 'March 2027');
  assert.equal(await month('3m', '2026-11-30T12:00:00Z'), 'February 2027');
  assert.equal(await month('preseason', '2026-09-29T12:00:00Z'), 'January 2027');
  assert.equal(await month('preseason', '2027-02-10T12:00:00Z'), 'January 2028');
  assert.equal(await month('none', '2026-09-29T12:00:00Z'), undefined);
});

test('no consent line without a quote, or when they said keep it private', async () => {
  const noQuote = { ...exitFixture.goal_answers };
  delete noQuote.quote;
  for (const answers of [noQuote, { ...exitFixture.goal_answers, share_as: 'private' }]) {
    const { alert } = await runExit(exitPayload(answers));
    assert.equal(alert.html.includes('Consent to share'), false);
  }
});

test('reference yes reads yes; no answers asked for means no actions', async () => {
  const { alert } = await runExit(exitPayload({ exit_reason: 'fit', reference: 'yes', checkin: 'none' }));
  assert.ok(alert.html.includes('Add to the talk-to-an-athlete roster (yes).'));
  const bare = await runExit(exitPayload({ exit_reason: 'fit', reference: 'no' }));
  assert.ok(bare.alert.html.includes('NEXT ACTIONS</p>\n    <p style="margin:0 0 16px">None.</p>'));
  assert.ok(bare.alert.html.includes('<b>Recommend:</b> not answered'));
  assert.equal(bare.alert.subject, '[GG] Exit survey · Test Rider A · The coaching wasn\'t the right fit');
});

test('answers are escaped in the alert', async () => {
  const { alert } = await runExit(exitPayload({ exit_reason: 'other', last_word: '<script>x</script>' }));
  assert.equal(alert.html.includes('<script>'), false);
  assert.ok(alert.html.includes('&lt;script&gt;x&lt;/script&gt;'));
});

test('athlete_exit is storage-required: a Mission Control failure is a 503', async () => {
  const { response } = await runExit(exitPayload(), { mcStatus: 500 });
  assert.equal(response.status, 503);
});

test('the exit popup source is untouched and still separate', async () => {
  const { response, requests } = await runExit({ source: 'exit_intent', email: 'popup@example.com' });
  assert.equal(response.status, 200);
  assert.equal(requests.some((r) => r.url.includes('resend')), false);
});
