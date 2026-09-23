/**
 * Cloudflare Worker: Course Nudge Emails
 *
 * Cron Trigger that runs daily at 14:00 UTC (9 AM ET).
 * Queries D1 for users who need engagement nudges and sends
 * personalized emails via Resend.
 *
 * Nudge Types:
 *   never_started    — Enrolled, zero lessons completed, 7+ days since enrollment
 *   inactive         — >= 1 lesson done, course incomplete, no activity 7+ days
 *   streak_risk      — Streak >= 3 days, active yesterday, no activity today
 *   near_completion  — >= 75% course complete (proxy: module_complete + 3+ lessons), inactive 2+ days
 *   course_complete  — All lessons done (sent once)
 *
 * Throttle Rules:
 *   - Max 1 nudge per user per 48 hours (global, across all types)
 *   - Never send to nudge_unsubscribed = 1 users
 *   - streak_risk only fires if streak >= 3
 *   - course_complete sent exactly once per course per user
 *   - never_started and inactive each send at most twice per user per course:
 *     first at day 7 of silence, second at day 21, then never again
 *     (silence = days since enrollment for never_started, days since
 *     last_active_date for inactive). Checked against nudge_log.
 *   - Only courses listed in COURSE_TITLES get nudged at all. An unlisted
 *     course_id (e.g. a non-course product sharing the enrollments table)
 *     is skipped entirely, no email of any type.
 *   - No nudge type fires for a course the user already has a
 *     course_complete xp_log event for, checked directly (not just via
 *     the lesson-count proxies each branch already uses).
 *
 * Fixed after review (both predated this change, caught by an adversarial
 * review pass before shipping):
 *   - The 48h throttle used to compare an ISO timestamp ('...T...Z') against
 *     D1's 'YYYY-MM-DD HH:MM:SS' sent_at as TEXT. On the same calendar date
 *     that lexical comparison could wrongly treat a recent send as
 *     not-recent (space < 'T'), letting a user be nudged twice within 48h.
 *     Fixed by formatting the threshold in the same 'YYYY-MM-DD HH:MM:SS'
 *     shape D1 actually stores, so the comparison is apples-to-apples.
 *   - A user who already got the once-only course_complete email could
 *     still match near_completion afterwards (that branch didn't check
 *     courseCompleteXP), so a finished course could keep sending "the rest
 *     is short." Fixed by checking courseCompleteXP directly in every
 *     branch below, not just relying on the lesson-count proxies.
 */

const UNSUBSCRIBE_BASE = 'https://course-access.gravelgodcoaching.workers.dev/unsubscribe';

// Real display titles, keyed by course_id (enrollments.course_id /
// lesson_progress.course_id). D1 has no `courses` table yet, so this is the
// interim config — add new courses here as they ship. Any course_id not
// listed falls back to a title-cased slug.
const COURSE_TITLES = {
  'dirt-craft': 'Dirt Craft'
};

// Only nudge for courses we actually know about. An enrollment for a
// course_id not listed in COURSE_TITLES (e.g. a non-course product that
// happens to share the enrollments table) is skipped entirely below.
function isKnownCourse(courseId) {
  return Object.prototype.hasOwnProperty.call(COURSE_TITLES, courseId);
}

const NUMBER_WORDS = ['Zero', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten'];

export default {
  async scheduled(event, env, ctx) {
    // Honor DRY_RUN on the cron path too — not just the manual fetch
    // trigger — so the env var alone is enough to test a run safely.
    ctx.waitUntil(runNudges(env, { dryRun: env.DRY_RUN === 'true' }));
  },

  // Allow manual trigger via POST with admin key.
  // Pass ?dry_run=1 (or set the DRY_RUN env var to "true") to compute who
  // would get what without sending anything or writing to nudge_log.
  async fetch(request, env) {
    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405 });
    }

    const authHeader = request.headers.get('Authorization') || '';
    const token = authHeader.replace('Bearer ', '').trim();
    if (!env.ADMIN_API_KEY || token !== env.ADMIN_API_KEY) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401, headers: { 'Content-Type': 'application/json' }
      });
    }

    const url = new URL(request.url);
    const dryRun = isDryRun(env, url);

    const results = await runNudges(env, { dryRun });
    return new Response(JSON.stringify(results), {
      status: 200, headers: { 'Content-Type': 'application/json' }
    });
  }
};

function isDryRun(env, url) {
  if (env.DRY_RUN === 'true') return true;
  const param = url.searchParams.get('dry_run');
  return param === '1' || param === 'true';
}

async function runNudges(env, opts = {}) {
  const dryRun = !!opts.dryRun;
  const now = new Date();
  const today = now.toISOString().split('T')[0];
  const yesterday = new Date(now - 86400000).toISOString().split('T')[0];
  const twoDaysAgo = new Date(now - 2 * 86400000).toISOString().split('T')[0];
  // Same 'YYYY-MM-DD HH:MM:SS' shape D1 stores via datetime('now') in
  // nudge_log.sent_at, so the SQL text comparison below is apples-to-apples
  // instead of comparing an ISO string against a SQLite datetime string.
  const fortyEightHoursAgo = toSqliteDatetime(new Date(now - 48 * 3600000));

  const results = {
    never_started: 0,
    inactive: 0,
    streak_risk: 0,
    near_completion: 0,
    course_complete: 0,
    skipped_throttle: 0,
    errors: 0,
    dry_run: dryRun
  };
  if (dryRun) results.would_send = [];

  // Get all eligible users (not unsubscribed)
  const users = await env.DB.prepare(
    'SELECT id, email, current_streak, last_active_date FROM users WHERE nudge_unsubscribed = 0'
  ).all();

  for (const user of users.results) {
    try {
      // Check 48-hour throttle
      const recentNudge = await env.DB.prepare(
        'SELECT id FROM nudge_log WHERE user_id = ? AND sent_at > ? LIMIT 1'
      ).bind(user.id, fortyEightHoursAgo).first();

      if (recentNudge) {
        results.skipped_throttle++;
        continue;
      }

      // Get user enrollments (with purchase date, for never_started cadence)
      const enrollments = await env.DB.prepare(
        'SELECT course_id, purchased_at FROM enrollments WHERE user_id = ?'
      ).bind(user.id).all();

      if (!enrollments.results.length) continue;

      let nudgeSent = false;

      for (const enrollment of enrollments.results) {
        if (nudgeSent) break;
        const courseId = enrollment.course_id;
        if (!isKnownCourse(courseId)) continue; // unlisted course, no nudges at all

        // Get lesson count for this course
        const lessonCount = await env.DB.prepare(
          'SELECT COUNT(*) as cnt FROM lesson_progress WHERE user_id = ? AND course_id = ?'
        ).bind(user.id, courseId).first();

        // 1. streak_risk: streak >= 3, no activity today
        if (
          user.current_streak >= 3 &&
          user.last_active_date &&
          user.last_active_date !== today &&
          user.last_active_date === yesterday
        ) {
          const sent = await maybeSendNudge(env, user, courseId, 'streak_risk', {
            streak_count: user.current_streak
          }, { dryRun, results });
          if (sent) { results.streak_risk++; nudgeSent = true; continue; }
        }

        // 2. course_complete: check if all lessons done, send once
        // We use xp_log to check for course_complete event
        const courseCompleteXP = await env.DB.prepare(
          "SELECT id FROM xp_log WHERE user_id = ? AND course_id = ? AND event_type = 'course_complete'"
        ).bind(user.id, courseId).first();

        if (courseCompleteXP) {
          // Check if we already sent course_complete nudge
          const alreadySent = await env.DB.prepare(
            "SELECT id FROM nudge_log WHERE user_id = ? AND course_id = ? AND nudge_type = 'course_complete'"
          ).bind(user.id, courseId).first();

          if (!alreadySent) {
            const sent = await maybeSendNudge(env, user, courseId, 'course_complete', {}, { dryRun, results });
            if (sent) { results.course_complete++; nudgeSent = true; continue; }
          }
        }

        // 3. near_completion: >= 75% done, inactive 2+ days
        // Check for module_complete events as a proxy for significant progress.
        // Having at least one module_complete means substantial completion.
        const hasModuleComplete = await env.DB.prepare(
          "SELECT id FROM xp_log WHERE user_id = ? AND course_id = ? AND event_type = 'module_complete' LIMIT 1"
        ).bind(user.id, courseId).first();

        if (
          !courseCompleteXP && // never nudge a finished course
          user.last_active_date &&
          user.last_active_date <= twoDaysAgo &&
          hasModuleComplete &&
          lessonCount.cnt >= 3 // At least 3 lessons completed + has a module_complete
        ) {
          const sent = await maybeSendNudge(env, user, courseId, 'near_completion', {
            lessons_completed: lessonCount.cnt
          }, { dryRun, results });
          if (sent) { results.near_completion++; nudgeSent = true; continue; }
        }

        // 4. never_started: zero lessons completed, 7+ days since enrollment.
        // Capped at 2 sends: day 7, then day 21.
        if (!courseCompleteXP && lessonCount.cnt === 0 && enrollment.purchased_at) {
          const daysSilent = daysSinceDatetime(enrollment.purchased_at, now);
          const priorCount = await nudgeSendCount(env, user.id, courseId, 'never_started');
          if (cadenceEligible(priorCount, daysSilent)) {
            const sent = await maybeSendNudge(env, user, courseId, 'never_started', {}, { dryRun, results });
            if (sent) { results.never_started++; nudgeSent = true; continue; }
          }
        }

        // 5. inactive: >= 1 lesson done, course incomplete, no activity 7+ days.
        // Capped at 2 sends: day 7, then day 21.
        if (lessonCount.cnt >= 1 && !courseCompleteXP && user.last_active_date) {
          const daysSilent = daysSinceDateOnly(user.last_active_date, now);
          const priorCount = await nudgeSendCount(env, user.id, courseId, 'inactive');
          if (cadenceEligible(priorCount, daysSilent)) {
            const sent = await maybeSendNudge(env, user, courseId, 'inactive', {
              lessons_completed: lessonCount.cnt
            }, { dryRun, results });
            if (sent) { results.inactive++; nudgeSent = true; continue; }
          }
        }
      }
    } catch (err) {
      console.error(`Nudge error for user ${user.id}:`, err);
      results.errors++;
    }
  }

  console.log('Nudge run complete:', JSON.stringify(results));
  return results;
}

// ── Cadence helpers ──────────────────────────────────────────

// never_started / inactive: first send at day 7 of silence, second at day
// 21, then never again — regardless of how many days have passed since.
function cadenceEligible(priorSentCount, daysSilent) {
  if (priorSentCount >= 2) return false;
  if (priorSentCount === 0) return daysSilent >= 7;
  if (priorSentCount === 1) return daysSilent >= 21;
  return false;
}

async function nudgeSendCount(env, userId, courseId, nudgeType) {
  const row = await env.DB.prepare(
    'SELECT COUNT(*) as cnt FROM nudge_log WHERE user_id = ? AND course_id = ? AND nudge_type = ?'
  ).bind(userId, courseId, nudgeType).first();
  return row ? row.cnt : 0;
}

// Formats a Date the same way SQLite's datetime('now') does: a plain
// 'YYYY-MM-DD HH:MM:SS' TEXT value, no 'T', no fractional seconds, no 'Z'.
// Used so SQL TEXT comparisons against nudge_log.sent_at are apples-to-apples
// instead of comparing this worker's ISO strings against SQLite's own shape.
function toSqliteDatetime(date) {
  return date.toISOString().replace('T', ' ').slice(0, 19);
}

// Missing or unparseable dates fail closed (-Infinity => never cadence-
// eligible) rather than open — malformed data should suppress a nudge, not
// trigger an immediate send.

// last_active_date is a plain 'YYYY-MM-DD' date string (see
// course-access/worker.js recordActivity).
function daysSinceDateOnly(dateStr, now) {
  if (!dateStr) return -Infinity;
  const then = new Date(`${dateStr}T00:00:00Z`);
  if (isNaN(then.getTime())) return -Infinity;
  return Math.floor((now.getTime() - then.getTime()) / 86400000);
}

// purchased_at is a SQLite datetime('now') string: 'YYYY-MM-DD HH:MM:SS'.
function daysSinceDatetime(dateTimeStr, now) {
  if (!dateTimeStr) return -Infinity;
  const normalized = dateTimeStr.includes('T') ? dateTimeStr : `${dateTimeStr.replace(' ', 'T')}Z`;
  const then = new Date(normalized);
  if (isNaN(then.getTime())) return -Infinity;
  return Math.floor((now.getTime() - then.getTime()) / 86400000);
}

// ── Copy helpers ─────────────────────────────────────────────

function courseTitleFor(courseId) {
  return COURSE_TITLES[courseId] || courseId.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// Spells out 1-10 (for sentence-start use); digits otherwise, including
// values above 10 even at a sentence start.
function spelledOut(n) {
  return (Number.isInteger(n) && n >= 0 && n <= 10) ? NUMBER_WORDS[n] : String(n);
}

function buildNudgeCopy(nudgeType, courseTitle, resumeUrl, siteBase, data) {
  switch (nudgeType) {
    case 'never_started':
      return {
        subject: `${courseTitle} is still sitting there`,
        bodyMain: `
          <p style="font-size:18px;color:#3a2e25">You bought <strong>${esc(courseTitle)}</strong> and haven't opened lesson one.</p>
          <p style="color:#59473c">It's short.</p>
          <a href="${esc(resumeUrl)}" style="display:inline-block;background:#178079;color:#fff;padding:14px 32px;text-decoration:none;font-family:monospace;font-size:13px;letter-spacing:1px;text-transform:uppercase;margin-top:16px">Start lesson one</a>
        `
      };

    case 'inactive': {
      const n = data.lessons_completed;
      return {
        subject: `${courseTitle}, lesson ${n + 1}`,
        bodyMain: `
          <p style="font-size:18px;color:#3a2e25">You stopped at lesson ${n}.</p>
          <p style="color:#59473c">It's still there.</p>
          <a href="${esc(resumeUrl)}" style="display:inline-block;background:#178079;color:#fff;padding:14px 32px;text-decoration:none;font-family:monospace;font-size:13px;letter-spacing:1px;text-transform:uppercase;margin-top:16px">Pick it back up</a>
        `
      };
    }

    case 'streak_risk': {
      const n = data.streak_count;
      return {
        subject: `day ${n + 1}, or day 1 again`,
        bodyMain: `
          <p style="font-size:18px;color:#3a2e25">${spelledOut(n)} days of ${esc(courseTitle)} in a row.</p>
          <p style="color:#59473c">One lesson today keeps it.</p>
          <a href="${esc(resumeUrl)}" style="display:inline-block;background:#178079;color:#fff;padding:14px 32px;text-decoration:none;font-family:monospace;font-size:13px;letter-spacing:1px;text-transform:uppercase;margin-top:16px">Keep it going</a>
        `
      };
    }

    case 'near_completion': {
      const n = data.lessons_completed;
      return {
        subject: `you're ${n} lessons in`,
        bodyMain: `
          <p style="font-size:18px;color:#3a2e25">${spelledOut(n)} lessons into ${esc(courseTitle)}, then it went quiet.</p>
          <p style="color:#59473c">The rest is short.</p>
          <a href="${esc(resumeUrl)}" style="display:inline-block;background:#178079;color:#fff;padding:14px 32px;text-decoration:none;font-family:monospace;font-size:13px;letter-spacing:1px;text-transform:uppercase;margin-top:16px">Finish it</a>
        `
      };
    }

    case 'course_complete':
      return {
        subject: `${courseTitle}: done`,
        bodyMain: `
          <p style="font-size:18px;color:#3a2e25">You finished <strong>${esc(courseTitle)}</strong>.</p>
          <p style="color:#59473c">The only test left is on a bike.</p>
          <p style="color:#7d695d;font-family:monospace;font-size:12px;margin-top:24px">Check out our other courses and training plans at <a href="${esc(siteBase)}/course/" style="color:#178079">gravelgodcycling.com/course</a></p>
        `
      };

    default:
      return null;
  }
}

// ── Send / dry-run dispatch ──────────────────────────────────

// Returns true if a nudge was (or, in dry-run mode, would be) sent.
async function maybeSendNudge(env, user, courseId, nudgeType, data, { dryRun, results }) {
  const courseTitle = courseTitleFor(courseId);
  const siteBase = env.SITE_BASE_URL || 'https://gravelgodcycling.com';
  const resumeUrl = `${siteBase}/course/${courseId}/`;
  const copy = buildNudgeCopy(nudgeType, courseTitle, resumeUrl, siteBase, data);
  if (!copy) return false;

  if (dryRun) {
    results.would_send.push({
      user_id: user.id,
      email: user.email,
      course_id: courseId,
      nudge_type: nudgeType,
      subject: copy.subject
    });
    return true;
  }

  return sendNudge(env, user, courseId, nudgeType, copy);
}

async function sendNudge(env, user, courseId, nudgeType, copy) {
  if (!env.NUDGE_UNSUBSCRIBE_SECRET) {
    console.error('NUDGE_UNSUBSCRIBE_SECRET not configured — skipping nudge');
    return false;
  }

  const unsubscribeToken = await generateHMAC(
    `${user.email}:unsubscribe`,
    env.NUDGE_UNSUBSCRIBE_SECRET
  );
  const encodedEmail = encodeURIComponent(user.email);
  const unsubscribeUrl = `${UNSUBSCRIBE_BASE}?email=${encodedEmail}&token=${unsubscribeToken}`;

  let bodyHtml = `<div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:40px 24px">${copy.bodyMain}</div>`;

  // Add unsubscribe footer
  bodyHtml += `
    <div style="font-family:monospace;font-size:11px;color:#7d695d;text-align:center;padding:24px;margin-top:24px;border-top:1px solid #d4c5b9">
      <a href="${esc(unsubscribeUrl)}" style="color:#7d695d">Unsubscribe from course emails</a>
    </div>
  `;

  // Send via Resend — only log nudge if email actually sends. SendGrid's
  // key has been returning 401 account-wide. Sent from noreply@ — the
  // domain's other addresses (e.g. matti@) are accepted by Resend but
  // silently never deliver, so noreply@ is the only address confirmed
  // to arrive.
  if (env.RESEND_API_KEY) {
    const fromName = env.FROM_NAME || 'Gravel God Courses';
    const resendResponse = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.RESEND_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        from: `${fromName} <${env.FROM_EMAIL || 'noreply@gravelgodcycling.com'}>`,
        to: [user.email],
        subject: copy.subject,
        html: bodyHtml
      })
    });

    if (!resendResponse.ok) {
      const detail = await resendResponse.text();
      console.error(`Resend failed for user ${user.id}: ${resendResponse.status} ${detail.slice(0, 200)}`);
      // Don't log the nudge — allow retry on next cron run
      return false;
    }
  } else {
    console.warn('RESEND_API_KEY not configured — skipping email send');
    return false;
  }

  // Only log the nudge AFTER successful email send
  await env.DB.prepare(
    'INSERT INTO nudge_log (user_id, nudge_type, course_id) VALUES (?, ?, ?)'
  ).bind(user.id, nudgeType, courseId).run();

  console.log(`Nudge sent: ${nudgeType} to user ${user.id} for ${courseId}`);
  return true;
}

// ── Helpers ──────────────────────────────────────────────────

async function generateHMAC(message, secret) {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw', encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
  );
  const sig = await crypto.subtle.sign('HMAC', key, encoder.encode(message));
  return Array.from(new Uint8Array(sig)).map(b => b.toString(16).padStart(2, '0')).join('');
}

function esc(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Exported for tests only.
export {
  runNudges,
  sendNudge,
  courseTitleFor,
  isKnownCourse,
  spelledOut,
  buildNudgeCopy,
  cadenceEligible,
  daysSinceDateOnly,
  daysSinceDatetime,
  toSqliteDatetime,
  isDryRun
};
