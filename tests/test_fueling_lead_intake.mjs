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

async function runExit(payload, {
  mcStatus = 200, resendStatus = 200, now = '2026-09-29T12:00:00Z', envOverrides = {},
} = {}) {
  const originalFetch = globalThis.fetch;
  const originalError = console.error;
  const requests = [];
  const errors = [];
  globalThis.fetch = async (url, options) => {
    requests.push({ url: String(url), body: JSON.parse(options.body) });
    const status = String(url).includes('mission-control') ? mcStatus : resendStatus;
    return new Response(JSON.stringify({ status: 'ok', id: 'x' }), { status });
  };
  console.error = (...args) => { errors.push(args.map(String).join(' ')); };
  mock.timers.enable({ apis: ['Date'], now: new Date(now) });
  try {
    const response = await worker.fetch(intakeRequest(payload), { ...exitEnv, ...envOverrides });
    const mc = requests.find((r) => r.url.endsWith('/webhooks/subscriber'));
    const alert = requests.find((r) => r.url === 'https://api.resend.com/emails');
    return { response, requests, errors, mc: mc && mc.body, alert: alert && alert.body };
  } finally {
    mock.timers.reset();
    console.error = originalError;
    globalThis.fetch = originalFetch;
  }
}

function nextActions(html) {
  return [...html.matchAll(/<li style="margin:0 0 6px">(.*?)<\/li>/g)].map((m) => m[1]
    .replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&'));
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

test('athlete_review (a coached athlete) never carries lead context to Mission Control', async () => {
  const { response, mc } = await runExit({
    source: 'athlete_review', brand: 'gravelgod',
    name: 'Test Rider B', email: 'test.rider.b@example.com', athlete: 'test-rider-b',
    goal_answers: { outcome_goal: 'Test answer: finish.' },
    race_slug: 'unbound-200', race_name: 'Unbound', offer_variant: 'A', entry_src: 'race',
    goal_type: 'finish', viewed_races: ['Unbound'], guide_chapter: 'Race Selection',
  });
  assert.equal(response.status, 200);
  assert.equal(mc.source, 'athlete_review');
  assert.equal(mc.athlete, 'test-rider-b');
  assert.deepEqual(mc.goal_answers, { outcome_goal: 'Test answer: finish.' });
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

for (const [brand, tag, label, site, social, audience] of [
  ['roadielabs', 'RL', 'Roadie Labs', 'roadielabs.com', 'Roadie Labs social posts', 'riders'],
  ['xcskilabs', 'XC', 'XC Ski Labs', 'xcskilabs.com', 'XC Ski Labs social posts', 'skiers'],
]) {
  test(`athlete_exit uses ${label} alert identity and consent channels`, async () => {
    const { mc, alert } = await runExit(exitPayload(undefined, { brand }));
    assert.equal(mc.brand, brand);
    assert.equal(alert.subject, `[${tag}] Exit survey · Test Rider A · Life got full`);
    assert.equal(alert.from, `${label} <noreply@gravelgodcycling.com>`);
    assert.ok(alert.html.includes(`${label} &middot;`));
    assert.ok(alert.html.includes(
      `channels: ${site}, ${social}, Emails to ${audience} thinking about coaching, `
      + 'My TrainingPeaks coach profile;',
    ));
  });
}

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

test('check-in months count on from today and preseason follows the sport', async () => {
  const month = async (checkin, now, brand = 'gravelgod') => {
    const { alert } = await runExit(exitPayload(
      { exit_reason: 'done', checkin }, { brand },
    ), { now });
    return (alert.html.match(/Check in around ([A-Za-z]+ \d{4})/) || [])[1];
  };
  assert.equal(await month('3m', '2026-09-29T12:00:00Z'), 'December 2026');
  assert.equal(await month('6m', '2026-09-29T12:00:00Z'), 'March 2027');
  assert.equal(await month('3m', '2026-11-30T12:00:00Z'), 'February 2027');
  assert.equal(await month('preseason', '2026-09-29T12:00:00Z'), 'January 2027');
  assert.equal(await month('preseason', '2027-02-10T12:00:00Z'), 'January 2028');
  assert.equal(await month('preseason', '2026-09-29T12:00:00Z', 'xcskilabs'), 'September 2027');
  assert.equal(await month('preseason', '2027-02-10T12:00:00Z', 'xcskilabs'), 'September 2027');
  assert.equal(await month('none', '2026-09-29T12:00:00Z'), undefined);
});

test('no consent line without any text to share, or when they said keep it private', async () => {
  const noQuote = { ...exitFixture.goal_answers };
  delete noQuote.quote;
  delete noQuote.not_for;
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

test('a Resend rejection is logged as an error, and the answers still land', async () => {
  const { response, errors, mc, alert } = await runExit(exitPayload(), { resendStatus: 422 });
  assert.equal(response.status, 200);
  assert.ok(alert, 'the alert was attempted');
  assert.deepEqual(mc.goal_answers, exitFixture.goal_answers);
  assert.ok(errors.some((e) => e.includes('REJECTED by Resend') && e.includes('422')), errors.join('\n'));
});

for (const unset of ['NOTIFICATION_EMAIL', 'RESEND_API_KEY']) {
  test(`with ${unset} unset the exit alert is not sent, and says so`, async () => {
    const { response, errors, requests, mc } = await runExit(exitPayload(), { envOverrides: { [unset]: '' } });
    assert.equal(response.status, 200);
    assert.ok(mc, 'Mission Control (and its backup alert) still gets the answers');
    assert.equal(requests.some((r) => r.url.includes('resend')), false);
    assert.ok(errors.some((e) => e.includes('Athlete exit alert NOT sent')), errors.join('\n'));
  });
}

test('consent covers "who shouldn\'t hire me" on its own', async () => {
  const answers = { exit_reason: 'done', share_as: 'full', not_for: 'Test answer: riders who hate data.',
    connection: 'none' };
  const { alert } = await runExit(exitPayload(answers));
  assert.ok(nextActions(alert.html)[0].startsWith('Consent to share: full name; channels: none ticked; '
    + 'connection: No, just coaching.'));
});

test('an under-18 athlete needs a parent before anything renders', async () => {
  const answers = { ...exitFixture.goal_answers, age_group: 'under_18' };
  const { alert } = await runExit(exitPayload(answers));
  assert.ok(nextActions(alert.html).includes("Under 18: needs a parent's sign-off before anything renders."));
  assert.ok(alert.html.includes('Under 18 (under_18)'));
});

test('age-group sharing without an age group, and no connection answer, are flagged', async () => {
  const answers = { ...exitFixture.goal_answers, share_as: 'age_group' };
  delete answers.age_group;
  delete answers.connection;
  const actions = nextActions((await runExit(exitPayload(answers))).alert.html);
  assert.ok(actions.includes('Ask their age group at approval.'), actions.join('\n'));
  assert.ok(actions.includes('Connection not answered: ask before approval.'), actions.join('\n'));
  assert.ok(actions[0].includes('connection: not answered.'));
});

test('none of the approval flags without consent to share', async () => {
  const answers = { exit_reason: 'fit', share_as: 'age_group' };
  const actions = nextActions((await runExit(exitPayload(answers))).alert.html);
  assert.deepEqual(actions, []);
});

// --- plan_debrief: the race debrief at /race-debrief/ (GG and Roadie) -------

const debriefFixture = JSON.parse(readFileSync(
  new URL('./fixtures/race_debrief_submission.json', import.meta.url), 'utf8',
));
const roadieDebriefFixture = JSON.parse(readFileSync(
  new URL('./fixtures/race_debrief_submission_roadie.json', import.meta.url), 'utf8',
));

function debriefPayload(fixture = debriefFixture, extra = {}) {
  return {
    source: 'plan_debrief', brand: fixture.brand, name: fixture.name, email: fixture.email,
    plan: fixture.plan, goal_answers: fixture.goal_answers, ...extra,
  };
}

test('plan_debrief forwards every answer and the plan to Mission Control', async () => {
  const { response, mc } = await runExit(debriefPayload());
  assert.equal(response.status, 200);
  assert.equal(mc.source, 'plan_debrief');
  assert.equal(mc.brand, 'gravelgod');
  assert.equal(mc.plan, '123456');
  assert.equal('ref' in mc, false);
  assert.deepEqual(mc.goal_answers, debriefFixture.goal_answers);
});

test('a custom plan ref is forwarded as ref', async () => {
  const { mc } = await runExit(debriefPayload(debriefFixture, { plan: '', ref: 'test-ref-0001' }));
  assert.equal(mc.ref, 'test-ref-0001');
  assert.equal('plan' in mc, false);
});

test('a plan or ref that does not match whole is dropped, never forwarded', async () => {
  for (const [plan, ref] of [['12ab34', 'bad'], ['1234567890123', 'has space1'], [' 123456', 'test-ref-0001\n'],
    ['123456\n', 'a'.repeat(33)], [123456.5, { x: 1 }], [['123456'], null]]) {
    const { response, mc } = await runExit(debriefPayload(debriefFixture, { plan, ref }));
    assert.equal(response.status, 200, `${plan} / ${ref}`);
    assert.equal('plan' in mc, false, `plan ${JSON.stringify(plan)}`);
    assert.equal('ref' in mc, false, `ref ${JSON.stringify(ref)}`);
  }
});

test('plan and ref ride only on a debrief', async () => {
  const { mc } = await runExit({ source: 'goal_2027', email: 'goal@example.com', plan: '123456',
    ref: 'test-ref-0001', goal_answers: { outcome_goal: 'x' } });
  assert.equal('plan' in mc, false);
  assert.equal('ref' in mc, false);
});

test('plan_debrief never carries lead context to Mission Control', async () => {
  const { mc } = await runExit(debriefPayload(debriefFixture, {
    race_slug: 'unbound-200', race_name: 'Unbound', offer_variant: 'A', entry_src: 'race',
    goal_type: 'finish', viewed_races: ['Unbound'], guide_chapter: 'Race Selection',
  }));
  assert.equal(mc.race_slug, '');
  assert.equal(mc.race_name, '');
  for (const key of ['offer_variant', 'entry_src', 'goal_type', 'viewed_races', 'guide_chapter']) {
    assert.equal(key in mc, false, key);
  }
});

test('plan_debrief alerts Matti through Resend only, with the plan in the subject', async () => {
  const { requests, alert } = await runExit(debriefPayload());
  assert.deepEqual(requests.map((r) => r.url).sort(), [
    'https://api.resend.com/emails',
    'https://mission-control.example.test/webhooks/subscriber',
  ]);
  assert.equal(alert.subject, '[GG] Race debrief · Test Rider B · plan 123456');
  assert.equal(alert.from, 'Gravel God <noreply@gravelgodcycling.com>');
  assert.deepEqual(alert.to, ['coach@example.com']);
  assert.equal(alert.reply_to, debriefFixture.email);
  assert.ok(alert.html.includes('href="https://www.trainingpeaks.com/training-plans/cycling/tp-123456"'));
});

test('the subject says custom plan, or plan unknown', async () => {
  const custom = await runExit(debriefPayload(debriefFixture, { plan: '', ref: 'test-ref-0001' }));
  assert.equal(custom.alert.subject, '[GG] Race debrief · Test Rider B · custom plan');
  assert.ok(custom.alert.html.includes('custom plan (ref test-ref-0001)'));
  const bare = await runExit(debriefPayload(debriefFixture, { plan: '' }));
  assert.equal(bare.alert.subject, '[GG] Race debrief · Test Rider B · plan unknown');
});

test('the debrief alert carries every answer, and the next actions come first', async () => {
  const { alert } = await runExit(debriefPayload());
  const html = alert.html;
  for (const key of Object.keys(debriefFixture.goal_answers)) {
    assert.ok(html.includes(`>${key}</td>`), `answer ${key} missing from the alert`);
  }
  assert.ok(html.indexOf('NEXT ACTIONS') > 0 && html.indexOf('NEXT ACTIONS') < html.indexOf('<table'));
  assert.deepEqual(nextActions(html), [
    'Consent to share: first name + last initial; channels: gravelgodcycling.com, Gravel God social posts, '
    + "Emails to riders choosing a plan, The plan's TrainingPeaks page; connection: No, only the plan. "
    + 'Next: send the exact wording + render for approval. '
    + 'Ledger entry needs quote_approved_at and render_approved_at before it can render.',
    'Add to the talk-to-a-rider roster for plan 123456 (ask first).',
    'Wants coaching: reply personally. Next race: Test answer: the same race next June.',
  ]);
  assert.ok(html.includes('<b>Recommend:</b> 9/10'));
  assert.ok(html.includes('Finished (finished)'));
  assert.ok(html.includes('ticked: The plan&#39;s TrainingPeaks page') || html.includes("ticked: The plan's TrainingPeaks page"));
});

test('a Roadie debrief is tagged [RL], sent as Roadie Labs, with Roadie channels', async () => {
  const { response, mc, alert } = await runExit(debriefPayload(roadieDebriefFixture));
  assert.equal(response.status, 200);
  assert.equal(mc.brand, 'roadielabs');
  assert.equal(mc.plan, '654321');
  assert.deepEqual(mc.goal_answers, roadieDebriefFixture.goal_answers);
  assert.equal(alert.subject, '[RL] Race debrief · Test Rider C · plan 654321');
  assert.equal(alert.from, 'Roadie Labs <noreply@gravelgodcycling.com>');
  const actions = nextActions(alert.html);
  assert.ok(actions[0].startsWith('Consent to share: full name; channels: roadielabs.com, Roadie Labs social posts, '));
  assert.ok(actions.includes('Wants a plan built around them: reply personally. Next race: Test answer: the same race next June.'));
  assert.equal(alert.html.includes('gravelgodcycling.com,'), false);
});

test('another plan is an ask; a break or not sure is not', async () => {
  const ask = await runExit(debriefPayload(debriefFixture, { goal_answers: { raced: 'dnf', next_want: 'another_plan' } }));
  assert.deepEqual(nextActions(ask.alert.html), ['Asked for another plan.']);
  for (const want of ['break', 'unsure']) {
    const none = await runExit(debriefPayload(debriefFixture, { goal_answers: { raced: 'dns', next_want: want } }));
    assert.deepEqual(nextActions(none.alert.html), []);
    assert.ok(none.alert.html.includes('<b>Recommend:</b> not answered'));
  }
});

test('debrief answers are escaped in the alert', async () => {
  const { alert } = await runExit(debriefPayload(debriefFixture, {
    name: '<b>Test</b> Rider', goal_answers: { raced: 'finished', last_word: '<script>x</script>' } }));
  assert.equal(alert.html.includes('<script>'), false);
  assert.equal(alert.html.includes('<b>Test</b>'), false);
  assert.ok(alert.html.includes('&lt;script&gt;x&lt;/script&gt;'));
});

test('plan_debrief is storage-required: a Mission Control failure is a 503', async () => {
  const { response } = await runExit(debriefPayload(), { mcStatus: 500 });
  assert.equal(response.status, 503);
});

test('a Resend rejection of the debrief alert is logged, and the answers still land', async () => {
  const { response, errors, mc } = await runExit(debriefPayload(), { resendStatus: 422 });
  assert.equal(response.status, 200);
  assert.deepEqual(mc.goal_answers, debriefFixture.goal_answers);
  assert.ok(errors.some((e) => e.includes('Race debrief notification REJECTED by Resend') && e.includes('422')),
    errors.join('\n'));
});

for (const unset of ['NOTIFICATION_EMAIL', 'RESEND_API_KEY']) {
  test(`with ${unset} unset the debrief alert is not sent, and says so`, async () => {
    const { response, errors, requests, mc } = await runExit(debriefPayload(), { envOverrides: { [unset]: '' } });
    assert.equal(response.status, 200);
    assert.ok(mc);
    assert.equal(requests.some((r) => r.url.includes('resend')), false);
    assert.ok(errors.some((e) => e.includes('Race debrief alert NOT sent')), errors.join('\n'));
  });
}

test('a debrief can carry a full form: every answer at 4000 characters', async () => {
  const answers = {};
  for (const [k, v] of Object.entries(debriefFixture.goal_answers)) {
    answers[k] = v.startsWith('Test answer') || v.startsWith('https://') ? 'x'.repeat(4000) : v;
  }
  const { mc } = await runExit(debriefPayload(debriefFixture, { goal_answers: answers }));
  assert.deepEqual(Object.keys(mc.goal_answers), Object.keys(answers));
});

// --- Storage-required sources with no Mission Control URL (Devin on #421) ---

const STORAGE_REQUIRED_BODIES = {
  goal_2027: { source: 'goal_2027', email: 'goal@example.com', goal_answers: { outcome_goal: 'Test answer: x' } },
  athlete_review: { source: 'athlete_review', email: 'review@example.com', goal_answers: { proudest: 'Test answer: x' } },
  athlete_exit: exitPayload(),
  plan_debrief: debriefPayload(),
};

for (const [source, body] of Object.entries(STORAGE_REQUIRED_BODIES)) {
  test(`${source} with MC_WEBHOOK_URL unset is a 503 and sends nothing`, async () => {
    const { response, requests, errors } = await runExit(body, { envOverrides: { MC_WEBHOOK_URL: '' } });
    assert.equal(response.status, 503);
    assert.deepEqual(await response.json(),
      { error: 'Could not store your answers. Nothing was lost — please try again.' });
    assert.deepEqual(requests, [], 'no alert for answers that were never stored');
    assert.ok(errors.some((e) => e.includes(`${source} answers NOT stored: MC_WEBHOOK_URL is unset`)),
      errors.join('\n'));
  });
}

test('a lead capture with MC_WEBHOOK_URL unset still answers 200', async () => {
  const { response } = await runExit({ source: 'exit_intent', email: 'popup@example.com' },
    { envOverrides: { MC_WEBHOOK_URL: '' } });
  assert.equal(response.status, 200);
});

test('every storage-required source is covered above', () => {
  const m = workerSource.match(/const STORAGE_REQUIRED = \[([^\]]*)\]/);
  const listed = m[1].split(',').map((s) => s.trim().replace(/'/g, '')).filter(Boolean);
  assert.deepEqual(listed.sort(), Object.keys(STORAGE_REQUIRED_BODIES).sort());
});
