import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const workerPath = new URL('../workers/course-nudge/worker.js', import.meta.url);
const workerSource = readFileSync(workerPath, 'utf8');
const {
  default: worker,
  runNudges,
  sendNudge,
  courseTitleFor,
  spelledOut,
  buildNudgeCopy,
  cadenceEligible,
  daysSinceDateOnly,
  daysSinceDatetime,
  isDryRun,
} = await import(
  `data:text/javascript;base64,${Buffer.from(workerSource).toString('base64')}`,
);

// Captured once at load time. runNudges() calls `new Date()` internally a
// few milliseconds later, well under the 1-day floor() resolution these
// helpers use, so day-count math stays exact regardless of when the suite
// actually runs.
const NOW = new Date();

function daysAgoDateOnly(n) {
  return new Date(NOW.getTime() - n * 86400000).toISOString().split('T')[0];
}

function daysAgoDatetime(n) {
  return new Date(NOW.getTime() - n * 86400000).toISOString().replace('T', ' ').slice(0, 19);
}

// ── Mock D1 ──────────────────────────────────────────────────
// Matches each prepared statement against the first handler whose pattern is
// a substring of the SQL text, then calls it with the bound args. A query
// with no matching handler throws (rather than silently returning empty) so
// a test can't pass by accident on a query it never actually accounted for.

function makeMockDB(handlers) {
  function findHandler(sql) {
    for (const [pattern, fn] of handlers) {
      if (sql.includes(pattern)) return fn;
    }
    throw new Error(`Unmocked D1 query in test: ${sql}`);
  }

  return {
    prepare(sql) {
      let boundArgs = [];
      const stmt = {
        bind(...args) {
          boundArgs = args;
          return stmt;
        },
        async all() {
          const r = findHandler(sql)(boundArgs, sql);
          return { results: r || [] };
        },
        async first() {
          const r = findHandler(sql)(boundArgs, sql);
          return r === undefined ? null : r;
        },
        async run() {
          findHandler(sql)(boundArgs, sql);
          return { success: true };
        },
      };
      return stmt;
    },
  };
}

// A DB that throws on any query at all — proves a code path never touches D1.
function makeUntouchableDB() {
  return {
    prepare(sql) {
      throw new Error(`D1 should not have been queried, but got: ${sql}`);
    },
  };
}

const baseEnv = {
  SITE_BASE_URL: 'https://gravelgodcycling.com',
  NUDGE_UNSUBSCRIBE_SECRET: 'test-secret',
  RESEND_API_KEY: 'test-key',
};

// ── Copy / number formatting ────────────────────────────────

test('courseTitleFor: uses the known display title for dirt-craft', () => {
  assert.equal(courseTitleFor('dirt-craft'), 'Dirt Craft');
});

test('courseTitleFor: falls back to a title-cased slug for unknown courses', () => {
  assert.equal(courseTitleFor('bike-fit-basics'), 'Bike Fit Basics');
});

test('spelledOut: spells 1-10, falls back to digits above 10', () => {
  assert.equal(spelledOut(1), 'One');
  assert.equal(spelledOut(5), 'Five');
  assert.equal(spelledOut(10), 'Ten');
  assert.equal(spelledOut(11), '11');
  assert.equal(spelledOut(21), '21');
});

test('buildNudgeCopy: never_started has no numbers, no exclamation marks', () => {
  const copy = buildNudgeCopy('never_started', 'Dirt Craft', 'https://x/course/dirt-craft/', 'https://x', {});
  assert.equal(copy.subject, 'Dirt Craft is still sitting there');
  assert.match(copy.bodyMain, /You bought <strong>Dirt Craft<\/strong> and haven't opened lesson one\./);
  assert.match(copy.bodyMain, /It's short\./);
  assert.doesNotMatch(copy.subject + copy.bodyMain, /!/);
  assert.doesNotMatch(copy.bodyMain, /Congratulations/);
});

test('buildNudgeCopy: inactive uses digits mid-sentence (not sentence-start words)', () => {
  const copy = buildNudgeCopy('inactive', 'Dirt Craft', 'https://x/course/dirt-craft/', 'https://x', { lessons_completed: 5 });
  assert.equal(copy.subject, 'Dirt Craft, lesson 6');
  assert.match(copy.bodyMain, /You stopped at lesson 5\./);
});

test('buildNudgeCopy: streak_risk subject and spelled-out body count', () => {
  const copy = buildNudgeCopy('streak_risk', 'Dirt Craft', 'https://x/course/dirt-craft/', 'https://x', { streak_count: 5 });
  assert.equal(copy.subject, 'day 6, or day 1 again');
  assert.match(copy.bodyMain, /Five days of Dirt Craft in a row\./);
  assert.match(copy.bodyMain, /One lesson today keeps it\./);
});

test('buildNudgeCopy: near_completion spells the count at sentence start', () => {
  const copy = buildNudgeCopy('near_completion', 'Dirt Craft', 'https://x/course/dirt-craft/', 'https://x', { lessons_completed: 3 });
  assert.equal(copy.subject, "you're 3 lessons in");
  assert.match(copy.bodyMain, /Three lessons into Dirt Craft, then it went quiet\./);
});

test('buildNudgeCopy: course_complete has no button, links to /course/, no exclamation marks', () => {
  const copy = buildNudgeCopy('course_complete', 'Dirt Craft', 'https://x/course/dirt-craft/', 'https://x', {});
  assert.equal(copy.subject, 'Dirt Craft: done');
  assert.match(copy.bodyMain, /You finished <strong>Dirt Craft<\/strong>\./);
  assert.match(copy.bodyMain, /The only test left is on a bike\./);
  assert.match(copy.bodyMain, /href="https:\/\/x\/course\/"/);
  assert.doesNotMatch(copy.bodyMain, /style="display:inline-block;background:#178079/); // no button styling
  assert.doesNotMatch(copy.subject + copy.bodyMain, /!/);
});

// ── Cadence decisions ────────────────────────────────────────

test('cadenceEligible: first send only after 7 days silent', () => {
  assert.equal(cadenceEligible(0, 6), false);
  assert.equal(cadenceEligible(0, 7), true);
  assert.equal(cadenceEligible(0, 30), true);
});

test('cadenceEligible: second send only after 21 days silent', () => {
  assert.equal(cadenceEligible(1, 7), false);
  assert.equal(cadenceEligible(1, 20), false);
  assert.equal(cadenceEligible(1, 21), true);
});

test('cadenceEligible: never a third send', () => {
  assert.equal(cadenceEligible(2, 100), false);
  assert.equal(cadenceEligible(3, 1000), false);
});

test('daysSinceDateOnly / daysSinceDatetime compute whole days', () => {
  assert.equal(daysSinceDateOnly(daysAgoDateOnly(10), NOW), 10);
  assert.equal(daysSinceDatetime(daysAgoDatetime(21), NOW), 21);
});

test('daysSinceDateOnly / daysSinceDatetime fail closed (never cadence-eligible) on missing or malformed input', () => {
  // -Infinity, not Infinity: malformed data must never look "very silent"
  // and trigger an immediate send.
  assert.equal(daysSinceDateOnly(null, NOW), -Infinity);
  assert.equal(daysSinceDateOnly('not-a-date', NOW), -Infinity);
  assert.equal(daysSinceDatetime(null, NOW), -Infinity);
  assert.equal(daysSinceDatetime('not-a-date', NOW), -Infinity);
  assert.equal(cadenceEligible(0, daysSinceDateOnly('not-a-date', NOW)), false);
});

test('isDryRun: env var or query param', () => {
  assert.equal(isDryRun({ DRY_RUN: 'true' }, new URL('https://x/')), true);
  assert.equal(isDryRun({}, new URL('https://x/?dry_run=1')), true);
  assert.equal(isDryRun({}, new URL('https://x/?dry_run=true')), true);
  assert.equal(isDryRun({}, new URL('https://x/')), false);
});

// ── runNudges with a mocked DB ───────────────────────────────

test('runNudges: never_started fires at day 7, not before, dry-run does not write', async () => {
  const insertedNudges = [];
  const user = { id: 1, email: 'a@example.com', current_streak: 0, last_active_date: null };

  function makeDB(daysSincePurchase) {
    return makeMockDB([
      ['FROM users WHERE nudge_unsubscribed', () => [user]],
      ['sent_at > ?', () => null], // no recent nudge, throttle open
      ['FROM enrollments WHERE user_id', () => [{ course_id: 'dirt-craft', purchased_at: daysAgoDatetime(daysSincePurchase) }]],
      ['FROM lesson_progress WHERE user_id = ? AND course_id = ?', () => ({ cnt: 0 })],
      ["event_type = 'course_complete'", () => null],
      ["event_type = 'module_complete'", () => null],
      ['nudge_type = ?', () => ({ cnt: 0 })], // never sent before
      ['INSERT INTO nudge_log', (args) => insertedNudges.push(args)],
    ]);
  }

  const resultsBefore = await runNudges({ ...baseEnv, DB: makeDB(6) }, { dryRun: true });
  assert.equal(resultsBefore.never_started, 0);

  const resultsAt7 = await runNudges({ ...baseEnv, DB: makeDB(7) }, { dryRun: true });
  assert.equal(resultsAt7.never_started, 1);
  assert.equal(resultsAt7.would_send.length, 1);
  assert.equal(resultsAt7.would_send[0].nudge_type, 'never_started');
  assert.equal(resultsAt7.would_send[0].email, 'a@example.com');
  assert.equal(resultsAt7.would_send[0].subject, 'Dirt Craft is still sitting there');
  assert.equal(insertedNudges.length, 0); // dry-run never writes
});

test('runNudges: never_started is capped at two sends total (day 7, day 21, then never)', async () => {
  function makeDB(daysSincePurchase, priorSentCount) {
    return makeMockDB([
      ['FROM users WHERE nudge_unsubscribed', () => [{ id: 1, email: 'a@example.com', current_streak: 0, last_active_date: null }]],
      ['sent_at > ?', () => null],
      ['FROM enrollments WHERE user_id', () => [{ course_id: 'dirt-craft', purchased_at: daysAgoDatetime(daysSincePurchase) }]],
      ['FROM lesson_progress WHERE user_id = ? AND course_id = ?', () => ({ cnt: 0 })],
      ["event_type = 'course_complete'", () => null],
      ["event_type = 'module_complete'", () => null],
      ['nudge_type = ?', () => ({ cnt: priorSentCount })],
    ]);
  }

  // One already sent (the day-7 one); day 15 is too soon for the second.
  const tooSoon = await runNudges({ ...baseEnv, DB: makeDB(15, 1) }, { dryRun: true });
  assert.equal(tooSoon.never_started, 0);

  // Day 21: second send fires.
  const secondSend = await runNudges({ ...baseEnv, DB: makeDB(21, 1) }, { dryRun: true });
  assert.equal(secondSend.never_started, 1);

  // Two already sent: never again, no matter how much time passes.
  const capped = await runNudges({ ...baseEnv, DB: makeDB(365, 2) }, { dryRun: true });
  assert.equal(capped.never_started, 0);
});

test('runNudges: inactive requires at least one lesson done and reports lesson count copy', async () => {
  const db = makeMockDB([
    ['FROM users WHERE nudge_unsubscribed', () => [{ id: 2, email: 'b@example.com', current_streak: 0, last_active_date: daysAgoDateOnly(10) }]],
    ['sent_at > ?', () => null],
    ['FROM enrollments WHERE user_id', () => [{ course_id: 'dirt-craft', purchased_at: daysAgoDatetime(30) }]],
    ['FROM lesson_progress WHERE user_id = ? AND course_id = ?', () => ({ cnt: 5 })],
    ["event_type = 'course_complete'", () => null],
    ["event_type = 'module_complete'", () => null],
    ['nudge_type = ?', () => ({ cnt: 0 })],
  ]);

  const results = await runNudges({ ...baseEnv, DB: db }, { dryRun: true });
  assert.equal(results.inactive, 1);
  assert.equal(results.would_send[0].subject, 'Dirt Craft, lesson 6');
});

test('runNudges: the global 48h throttle blocks every type, even when a type-specific cadence would allow it', async () => {
  const db = makeMockDB([
    ['FROM users WHERE nudge_unsubscribed', () => [{ id: 3, email: 'c@example.com', current_streak: 5, last_active_date: daysAgoDateOnly(1) }]],
    ['sent_at > ?', () => ({ id: 999 })], // recent nudge within 48h
  ]);

  const results = await runNudges({ ...baseEnv, DB: db }, { dryRun: true });
  assert.equal(results.skipped_throttle, 1);
  assert.equal(results.streak_risk, 0);
  assert.equal(results.would_send.length, 0);
});

test('runNudges: streak_risk fires before never_started/inactive checks, in dry-run', async () => {
  const db = makeMockDB([
    ['FROM users WHERE nudge_unsubscribed', () => [{ id: 4, email: 'd@example.com', current_streak: 4, last_active_date: daysAgoDateOnly(1) }]],
    ['sent_at > ?', () => null],
    ['FROM enrollments WHERE user_id', () => [{ course_id: 'dirt-craft', purchased_at: daysAgoDatetime(60) }]],
    ['FROM lesson_progress WHERE user_id = ? AND course_id = ?', () => ({ cnt: 8 })],
  ]);

  const results = await runNudges({ ...baseEnv, DB: db }, { dryRun: true });
  assert.equal(results.streak_risk, 1);
  assert.equal(results.would_send[0].subject, 'day 5, or day 1 again');
});

// ── Cron entrypoint honors DRY_RUN ──────────────────────────

test('scheduled(): DRY_RUN=true env var stops the cron path from sending or writing, not just the fetch path', async () => {
  const originalFetch = globalThis.fetch;
  let fetchCalled = false;
  globalThis.fetch = async () => { fetchCalled = true; return new Response(null, { status: 200 }); };

  const db = makeMockDB([
    ['FROM users WHERE nudge_unsubscribed', () => [{ id: 5, email: 'e@example.com', current_streak: 5, last_active_date: daysAgoDateOnly(1) }]],
    ['sent_at > ?', () => null],
    ['FROM enrollments WHERE user_id', () => [{ course_id: 'dirt-craft', purchased_at: daysAgoDatetime(60) }]],
    ['FROM lesson_progress WHERE user_id = ? AND course_id = ?', () => ({ cnt: 8 })],
    // No handler for INSERT INTO nudge_log: a real send would hit the
    // "unmocked query" throw below and fail this test.
  ]);

  let capturedPromise = null;
  const ctx = { waitUntil: (p) => { capturedPromise = p; } };

  try {
    await worker.scheduled({}, { ...baseEnv, DB: db, DRY_RUN: 'true' }, ctx);
    await capturedPromise;
    assert.equal(fetchCalled, false); // never called Resend
  } finally {
    globalThis.fetch = originalFetch;
  }
});

// ── NUDGE_UNSUBSCRIBE_SECRET fails closed ───────────────────

test('sendNudge: sends nothing and writes nothing when NUDGE_UNSUBSCRIBE_SECRET is unset', async () => {
  const originalFetch = globalThis.fetch;
  let fetchCalled = false;
  globalThis.fetch = async () => { fetchCalled = true; return new Response(null, { status: 200 }); };

  const envWithoutSecret = { ...baseEnv, DB: makeUntouchableDB() };
  delete envWithoutSecret.NUDGE_UNSUBSCRIBE_SECRET;

  const copy = buildNudgeCopy('never_started', 'Dirt Craft', 'https://x/course/dirt-craft/', 'https://x', {});

  try {
    const sent = await sendNudge(envWithoutSecret, { id: 6, email: 'f@example.com' }, 'dirt-craft', 'never_started', copy);
    assert.equal(sent, false);
    assert.equal(fetchCalled, false); // Resend never called
    // makeUntouchableDB() would have thrown if sendNudge tried to write
    // nudge_log, so reaching this line proves it didn't.
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('sendNudge: dry-run copy building does not require NUDGE_UNSUBSCRIBE_SECRET at all', async () => {
  // maybeSendNudge's dry-run branch never calls sendNudge, so it never
  // touches the secret — exercised indirectly via runNudges above with
  // baseEnv (which does set the secret); this test confirms buildNudgeCopy
  // itself has no dependency on it.
  const copy = buildNudgeCopy('never_started', 'Dirt Craft', 'https://x/course/dirt-craft/', 'https://x', {});
  assert.equal(copy.subject, 'Dirt Craft is still sitting there');
});
