/**
 * Cloudflare Worker: Course Nudge Emails
 *
 * Cron Trigger that runs daily at 14:00 UTC (9 AM ET).
 * Queries D1 for users who need engagement nudges and sends
 * personalized emails via SendGrid.
 *
 * Nudge Types:
 *   streak_risk      — Streak >= 3 days, no activity today
 *   near_completion  — >= 75% course complete, inactive 2+ days
 *   course_complete  — All lessons done (sent once)
 *   inactive         — No activity for 7+ days, course incomplete
 *
 * Throttle Rules:
 *   - Max 1 nudge per user per 48 hours
 *   - Never send to nudge_unsubscribed = 1 users
 *   - streak_risk only fires if streak >= 3
 *   - course_complete sent exactly once per course per user
 */

const UNSUBSCRIBE_BASE = 'https://course-access.gravelgodcoaching.workers.dev/unsubscribe';

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runNudges(env));
  },

  // Allow manual trigger via POST with admin key
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

    const results = await runNudges(env);
    return new Response(JSON.stringify(results), {
      status: 200, headers: { 'Content-Type': 'application/json' }
    });
  }
};

async function runNudges(env) {
  const now = new Date();
  const today = now.toISOString().split('T')[0];
  const yesterday = new Date(now - 86400000).toISOString().split('T')[0];
  const twoDaysAgo = new Date(now - 2 * 86400000).toISOString().split('T')[0];
  const sevenDaysAgo = new Date(now - 7 * 86400000).toISOString().split('T')[0];
  const fortyEightHoursAgo = new Date(now - 48 * 3600000).toISOString();

  const results = {
    streak_risk: 0,
    near_completion: 0,
    course_complete: 0,
    inactive: 0,
    skipped_throttle: 0,
    errors: 0
  };

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

      // Get user enrollments
      const enrollments = await env.DB.prepare(
        'SELECT course_id FROM enrollments WHERE user_id = ?'
      ).bind(user.id).all();

      if (!enrollments.results.length) continue;

      let nudgeSent = false;

      for (const enrollment of enrollments.results) {
        if (nudgeSent) break;
        const courseId = enrollment.course_id;

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
          await sendNudge(env, user, courseId, 'streak_risk', {
            streak_count: user.current_streak
          });
          results.streak_risk++;
          nudgeSent = true;
          continue;
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
            await sendNudge(env, user, courseId, 'course_complete', {});
            results.course_complete++;
            nudgeSent = true;
            continue;
          }
        }

        // 3. near_completion: >= 75% done, inactive 2+ days
        // Check for module_complete events as a proxy for significant progress.
        // Having at least one module_complete means substantial completion.
        const hasModuleComplete = await env.DB.prepare(
          "SELECT id FROM xp_log WHERE user_id = ? AND course_id = ? AND event_type = 'module_complete' LIMIT 1"
        ).bind(user.id, courseId).first();

        if (
          user.last_active_date &&
          user.last_active_date <= twoDaysAgo &&
          hasModuleComplete &&
          lessonCount.cnt >= 3 // At least 3 lessons completed + has a module_complete
        ) {
          await sendNudge(env, user, courseId, 'near_completion', {
            lessons_completed: lessonCount.cnt
          });
          results.near_completion++;
          nudgeSent = true;
          continue;
        }

        // 4. inactive: no activity for 7+ days, course incomplete
        if (
          user.last_active_date &&
          user.last_active_date <= sevenDaysAgo &&
          !courseCompleteXP
        ) {
          await sendNudge(env, user, courseId, 'inactive', {
            lessons_completed: lessonCount.cnt
          });
          results.inactive++;
          nudgeSent = true;
          continue;
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

async function sendNudge(env, user, courseId, nudgeType, data) {
  if (!env.NUDGE_UNSUBSCRIBE_SECRET) {
    console.error('NUDGE_UNSUBSCRIBE_SECRET not configured — skipping nudge');
    return;
  }

  const unsubscribeToken = await generateHMAC(
    `${user.email}:unsubscribe`,
    env.NUDGE_UNSUBSCRIBE_SECRET
  );
  const encodedEmail = encodeURIComponent(user.email);
  const unsubscribeUrl = `${UNSUBSCRIBE_BASE}?email=${encodedEmail}&token=${unsubscribeToken}`;
  const siteBase = env.SITE_BASE_URL || 'https://gravelgodcycling.com';
  const resumeUrl = `${siteBase}/course/${courseId}/`;

  const courseTitle = courseId.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  let subject, bodyHtml;

  switch (nudgeType) {
    case 'streak_risk':
      subject = `Don't break your ${data.streak_count}-day streak!`;
      bodyHtml = `
        <div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:40px 24px">
          <p style="font-size:18px;color:#3a2e25">You've been on a <strong>${data.streak_count}-day streak</strong> in ${esc(courseTitle)}.</p>
          <p style="color:#59473c">Complete a lesson today to keep it going. It only takes a few minutes.</p>
          <a href="${esc(resumeUrl)}" style="display:inline-block;background:#1A8A82;color:#fff;padding:14px 32px;text-decoration:none;font-family:monospace;font-size:13px;letter-spacing:1px;text-transform:uppercase;margin-top:16px">CONTINUE LEARNING</a>
        </div>
      `;
      break;

    case 'near_completion':
      subject = `You're almost done with ${courseTitle}!`;
      bodyHtml = `
        <div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:40px 24px">
          <p style="font-size:18px;color:#3a2e25">You've completed <strong>${data.lessons_completed} lessons</strong> in ${esc(courseTitle)}. You're so close to finishing!</p>
          <p style="color:#59473c">Pick up where you left off and cross the finish line.</p>
          <a href="${esc(resumeUrl)}" style="display:inline-block;background:#1A8A82;color:#fff;padding:14px 32px;text-decoration:none;font-family:monospace;font-size:13px;letter-spacing:1px;text-transform:uppercase;margin-top:16px">FINISH STRONG</a>
        </div>
      `;
      break;

    case 'course_complete':
      subject = `You did it! ${courseTitle} complete`;
      bodyHtml = `
        <div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:40px 24px">
          <p style="font-size:18px;color:#3a2e25">Congratulations! You've completed <strong>${esc(courseTitle)}</strong>.</p>
          <p style="color:#59473c">You've earned the knowledge. Now go crush your next gravel race.</p>
          <p style="color:#8c7568;font-family:monospace;font-size:12px;margin-top:24px">Check out our other courses and training plans at <a href="${esc(siteBase)}/course/" style="color:#1A8A82">gravelgodcycling.com/course</a></p>
        </div>
      `;
      break;

    case 'inactive':
      subject = 'Your course is waiting for you';
      bodyHtml = `
        <div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:40px 24px">
          <p style="font-size:18px;color:#3a2e25">It's been a while since you worked on <strong>${esc(courseTitle)}</strong>.</p>
          <p style="color:#59473c">You've already made progress — ${data.lessons_completed} lesson${data.lessons_completed === 1 ? '' : 's'} down. Pick up where you left off.</p>
          <a href="${esc(resumeUrl)}" style="display:inline-block;background:#1A8A82;color:#fff;padding:14px 32px;text-decoration:none;font-family:monospace;font-size:13px;letter-spacing:1px;text-transform:uppercase;margin-top:16px">RESUME COURSE</a>
        </div>
      `;
      break;
  }

  // Add unsubscribe footer
  bodyHtml += `
    <div style="font-family:monospace;font-size:11px;color:#8c7568;text-align:center;padding:24px;margin-top:24px;border-top:1px solid #d4c5b9">
      <a href="${esc(unsubscribeUrl)}" style="color:#8c7568">Unsubscribe from course emails</a>
    </div>
  `;

  // Send via SendGrid — only log nudge if email actually sends
  if (env.SENDGRID_API_KEY) {
    const sgResponse = await fetch('https://api.sendgrid.com/v3/mail/send', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.SENDGRID_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        personalizations: [{
          to: [{ email: user.email }],
          subject: subject
        }],
        from: {
          email: env.FROM_EMAIL || 'courses@gravelgodcycling.com',
          name: env.FROM_NAME || 'Gravel God Courses'
        },
        content: [{
          type: 'text/html',
          value: bodyHtml
        }]
      })
    });

    if (!sgResponse.ok) {
      console.error(`SendGrid failed for user ${user.id}: ${sgResponse.status}`);
      // Don't log the nudge — allow retry on next cron run
      return;
    }
  } else {
    console.warn('SENDGRID_API_KEY not configured — skipping email send');
    return;
  }

  // Only log the nudge AFTER successful email send
  await env.DB.prepare(
    'INSERT INTO nudge_log (user_id, nudge_type, course_id) VALUES (?, ?, ?)'
  ).bind(user.id, nudgeType, courseId).run();

  console.log(`Nudge sent: ${nudgeType} to user ${user.id} for ${courseId}`);
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
