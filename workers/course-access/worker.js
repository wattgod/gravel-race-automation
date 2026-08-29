/**
 * Cloudflare Worker: Course Access (D1-backed)
 *
 * Handles course purchase verification, Stripe webhook processing,
 * lesson progress tracking, gamification (XP/streaks/levels),
 * knowledge check recording, leaderboard, admin dashboard, and
 * nudge email unsubscribe.
 *
 * Endpoints:
 *   POST /verify         — Check if email has access to a course
 *   POST /webhook        — Stripe webhook receiver (checkout.session.completed)
 *   POST /progress       — Save/retrieve lesson progress (awards XP + streak)
 *   POST /kc             — Record knowledge check answer, award XP
 *   POST /stats          — Return user stats (XP, streak, level, leaderboard rank)
 *   POST /leaderboard    — Top 10 XP users for a course
 *   POST /activation     — Case-bound coaching activation read/submissions
 *   POST /admin/dashboard — Aggregate stats (requires ADMIN_API_KEY)
 *   POST /admin/grant    — Manually grant course access (requires ADMIN_API_KEY)
 *   GET  /unsubscribe    — Unsubscribe from nudge emails (HMAC token in URL)
 *   OPTIONS              — CORS preflight
 */

const DISPOSABLE_DOMAINS = [
  '10minutemail.com', 'guerrillamail.com', 'mailinator.com', 'tempmail.com',
  'throwaway.email', 'fakeinbox.com', 'trashmail.com', 'maildrop.cc',
  'yopmail.com', 'temp-mail.org', 'getnada.com', 'mohmal.com'
];

const COURSE_ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,98}[a-z0-9]$/;
const LESSON_ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,98}[a-z0-9]$/;
const QUESTION_HASH_PATTERN = /^[a-f0-9]{8}$/;
const CASE_ID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const ATHLETE_KEY_PATTERN = /^[a-z0-9][a-z0-9:_-]{2,127}$/;
const SLUG_PATTERN = /^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$/;
const ACCESS_TOKEN_PATTERN = /^[A-Za-z0-9_-]{43}$/;
const COACHING_COURSE_ID = 'coaching-start';

// ── XP Constants ──────────────────────────────────────────────
const XP_LESSON_COMPLETE = 10;
const XP_KC_CORRECT = 5;
const XP_MODULE_COMPLETE = 25;
const XP_COURSE_COMPLETE = 100;

const LEVELS = [
  { level: 1, xp: 0,   name: 'Gravel Curious' },
  { level: 2, xp: 50,  name: 'Dirt Dabbler' },
  { level: 3, xp: 150, name: 'Gravel Grinder' },
  { level: 4, xp: 300, name: 'Dust Demon' },
  { level: 5, xp: 500, name: 'Gravel God' },
];

function getLevelInfo(totalXP) {
  let current = LEVELS[0];
  for (const lvl of LEVELS) {
    if (totalXP >= lvl.xp) current = lvl;
  }
  const nextIdx = LEVELS.findIndex(l => l.level === current.level + 1);
  const next = nextIdx >= 0 ? LEVELS[nextIdx] : null;
  return {
    level: current.level,
    name: current.name,
    xp_to_next: next ? next.xp - totalXP : 0,
    next_level_xp: next ? next.xp : null,
    next_level_name: next ? next.name : null
  };
}

export default {
  async fetch(request, env, ctx) {
    if (request.method === 'OPTIONS') return handleCORS(request, env);

    const url = new URL(request.url);
    const path = url.pathname;

    // Stripe webhook — does NOT check Origin (Stripe sends from its own servers)
    if (request.method === 'POST' && path === '/webhook') {
      return handleWebhook(request, env);
    }

    // Unsubscribe — GET with HMAC token
    if (request.method === 'GET' && path === '/unsubscribe') {
      return handleUnsubscribe(url, env);
    }

    // All other POST endpoints require origin check
    if (request.method !== 'POST') return new Response('Method not allowed', { status: 405 });

    const origin = request.headers.get('Origin');
    const allowedOrigins = (env.ALLOWED_ORIGINS || 'https://gravelgodcycling.com').split(',').map(o => o.trim());

    // Admin endpoints use Authorization header instead of Origin
    if (path.startsWith('/admin/')) {
      return handleAdmin(request, path, env);
    }

    if (!allowedOrigins.includes(origin)) {
      return new Response('Forbidden', { status: 403 });
    }

    let data;
    try {
      data = await request.json();
    } catch (parseError) {
      return jsonResponse({ error: 'Invalid JSON' }, 400, origin);
    }

    // Honeypot
    if (data.website) return jsonResponse({ error: 'Bot detected' }, 400, origin);

    if (path === '/verify') return handleVerify(data, env, origin);
    if (path === '/activation') return handleActivation(data, env, origin);
    if (path === '/progress') return handleProgress(data, env, origin, ctx);
    if (path === '/kc') return handleKC(data, env, origin);
    if (path === '/stats') return handleStats(data, env, origin);
    if (path === '/leaderboard') return handleLeaderboard(data, env, origin);

    return jsonResponse({ error: 'Not found' }, 404, origin);
  },

  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(runCourseCanary(env));
  },
};

async function runCourseCanary(env) {
  const columns = await env.DB.prepare('PRAGMA table_info(enrollments)').all();
  const names = new Set((columns.results || []).map(row => row.name));
  const required = [
    'case_id', 'athlete_key', 'brand', 'tier',
    'access_token_hash', 'access_token_expires_at',
  ];
  const missing = required.filter(name => !names.has(name));
  if (missing.length) {
    console.error(JSON.stringify({
      message: 'coaching_course_daily_canary',
      status: 'failed',
      check: 'd1_case_binding_schema',
      missing,
    }));
    throw new Error('Course D1 case-binding schema is incomplete');
  }
  if (!env.COACHING_PIPELINE_URL || !env.COACHING_PROGRESS_SECRET) {
    throw new Error('Course progress bridge is not configured');
  }
  const response = await fetch(
    `${env.COACHING_PIPELINE_URL.replace(/\/$/, '')}/api/coaching-course-progress`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Coaching-Course-Secret': env.COACHING_PROGRESS_SECRET,
      },
      body: '{}',
    }
  );
  let result = {};
  try {
    result = await response.json();
  } catch (_error) {
    result = {};
  }
  if (response.status !== 400 || result.error !== 'Valid case_id is required') {
    console.error(JSON.stringify({
      message: 'coaching_course_daily_canary',
      status: 'failed',
      check: 'authenticated_progress_bridge',
      http_status: response.status,
    }));
    throw new Error('Course progress bridge canary failed');
  }
  const activationResponse = await fetch(
    `${env.COACHING_PIPELINE_URL.replace(/\/$/, '')}/api/coaching-activation`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Coaching-Course-Secret': env.COACHING_PROGRESS_SECRET,
      },
      body: '{}',
    }
  );
  let activationResult = {};
  try {
    activationResult = await activationResponse.json();
  } catch (_error) {
    activationResult = {};
  }
  if (activationResponse.status !== 400 ||
      activationResult.error !== 'Valid case_id is required') {
    console.error(JSON.stringify({
      message: 'coaching_course_daily_canary',
      status: 'failed',
      check: 'authenticated_activation_bridge',
      http_status: activationResponse.status,
    }));
    throw new Error('Coaching activation bridge canary failed');
  }
  const receipt = {
    message: 'coaching_course_daily_canary',
    status: 'ok',
    checks: [
      'd1_case_binding_schema',
      'authenticated_progress_bridge',
      'authenticated_activation_bridge',
    ],
  };
  console.log(JSON.stringify(receipt));
  return receipt;
}

// ── Email + User Helpers ──────────────────────────────────────

async function emailHash(email) {
  const encoder = new TextEncoder();
  const hashBuffer = await crypto.subtle.digest('SHA-256', encoder.encode(email));
  return Array.from(new Uint8Array(hashBuffer)).map(b => b.toString(16).padStart(2, '0')).join('').substring(0, 12);
}

async function sha256Hex(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest))
    .map(byte => byte.toString(16).padStart(2, '0')).join('');
}

function generateAccessToken() {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function getActivationEnrollment(data, env) {
  const courseId = String(data.course_id || '').substring(0, 100);
  const accessToken = String(data.access_token || '').trim();
  if (courseId !== COACHING_COURSE_ID || !ACCESS_TOKEN_PATTERN.test(accessToken)) {
    return null;
  }
  const tokenHash = await sha256Hex(accessToken);
  return env.DB.prepare(`
    SELECT id, user_id, course_id, case_id, athlete_key, brand, tier,
           preferred_name, goal_label, access_token_expires_at
    FROM enrollments
    WHERE course_id = ? AND access_token_hash = ?
      AND access_token_expires_at > ?
  `).bind(courseId, tokenHash, new Date().toISOString()).first();
}

function validateEmail(email) {
  if (!email) return { email: null, error: 'Missing: email' };
  email = String(email).substring(0, 254).toLowerCase().trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return { email: null, error: 'Invalid email format' };
  const domain = email.split('@')[1].toLowerCase();
  if (DISPOSABLE_DOMAINS.includes(domain)) return { email: null, error: 'Disposable email addresses are not allowed' };
  return { email, error: null };
}

async function getOrCreateUser(env, email) {
  const hash = await emailHash(email);
  let user = await env.DB.prepare('SELECT * FROM users WHERE email = ?').bind(email).first();
  if (!user) {
    await env.DB.prepare(
      'INSERT OR IGNORE INTO users (email, email_hash) VALUES (?, ?)'
    ).bind(email, hash).run();
    user = await env.DB.prepare('SELECT * FROM users WHERE email = ?').bind(email).first();
  }
  return user;
}

// ── Streak Logic ──────────────────────────────────────────────

function todayUTC() {
  return new Date().toISOString().split('T')[0];
}

function yesterdayUTC() {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().split('T')[0];
}

async function recordActivity(env, userId) {
  const today = todayUTC();

  // Insert today into streak_history (ignore if exists)
  await env.DB.prepare(
    'INSERT OR IGNORE INTO streak_history (user_id, active_date) VALUES (?, ?)'
  ).bind(userId, today).run();

  // Get current user data
  const user = await env.DB.prepare('SELECT * FROM users WHERE id = ?').bind(userId).first();
  const lastActive = user.last_active_date;
  const yesterday = yesterdayUTC();

  let newStreak;
  if (lastActive === today) {
    // Already active today, no change
    newStreak = user.current_streak;
  } else if (lastActive === yesterday) {
    // Consecutive day — increment streak
    newStreak = user.current_streak + 1;
  } else {
    // Gap > 1 day — reset to 1
    newStreak = 1;
  }

  const longestStreak = Math.max(newStreak, user.longest_streak);

  await env.DB.prepare(
    'UPDATE users SET last_active_date = ?, current_streak = ?, longest_streak = ? WHERE id = ?'
  ).bind(today, newStreak, longestStreak, userId).run();

  return { current_streak: newStreak, longest_streak: longestStreak };
}

// ── XP Logic ──────────────────────────────────────────────────

async function awardXP(env, userId, courseId, eventType, xpAmount, referenceId) {
  await env.DB.prepare(
    'INSERT INTO xp_log (user_id, course_id, event_type, xp_amount, reference_id) VALUES (?, ?, ?, ?, ?)'
  ).bind(userId, courseId, eventType, xpAmount, referenceId || null).run();

  await env.DB.prepare(
    'UPDATE users SET total_xp = total_xp + ? WHERE id = ?'
  ).bind(xpAmount, userId).run();

  const user = await env.DB.prepare('SELECT total_xp FROM users WHERE id = ?').bind(userId).first();
  return user.total_xp;
}

// ── Verify Endpoint ───────────────────────────────────────────

async function handleVerify(data, env, origin) {
  if (data.course_id === COACHING_COURSE_ID) {
    const enrollment = await getActivationEnrollment(data, env);
    return jsonResponse({
      has_access: Boolean(enrollment),
      course_id: COACHING_COURSE_ID,
      access_expires_at: enrollment ? enrollment.access_token_expires_at : null,
      personalization: enrollment ? {
        preferred_name: enrollment.preferred_name || null,
        goal_label: enrollment.goal_label || null,
      } : null,
    }, 200, origin);
  }
  const { email, error: emailError } = validateEmail(data.email);
  if (!email) return jsonResponse({ error: emailError }, 400, origin);
  if (!data.course_id) return jsonResponse({ error: 'Missing: course_id' }, 400, origin);

  const courseId = String(data.course_id).substring(0, 100);
  if (!COURSE_ID_PATTERN.test(courseId)) {
    return jsonResponse({ error: 'Invalid course_id format' }, 400, origin);
  }

  const user = await env.DB.prepare('SELECT id FROM users WHERE email = ?').bind(email).first();
  if (!user) {
    return jsonResponse({ has_access: false, course_id: courseId }, 200, origin);
  }

  const enrollment = await env.DB.prepare(
    'SELECT id, preferred_name, goal_label FROM enrollments WHERE user_id = ? AND course_id = ?'
  ).bind(user.id, courseId).first();

  return jsonResponse({
    has_access: !!enrollment,
    course_id: courseId,
    personalization: enrollment ? {
      preferred_name: enrollment.preferred_name || null,
      goal_label: enrollment.goal_label || null,
    } : null,
  }, 200, origin);
}

// ── Coaching Activation Endpoint ─────────────────────────────

async function handleActivation(data, env, origin) {
  const enrollment = await getActivationEnrollment(data, env);
  if (!enrollment || !enrollment.case_id || !enrollment.athlete_key) {
    return jsonResponse({ error: 'Invalid or expired activation link' }, 403, origin);
  }
  if (!env.COACHING_PIPELINE_URL || !env.COACHING_PROGRESS_SECRET) {
    return jsonResponse({ error: 'Coaching activation is not configured' }, 503, origin);
  }
  const upstreamPayload = {
    case_id: enrollment.case_id,
    athlete_key: enrollment.athlete_key,
    action: data.action,
  };
  if (data.event_id !== undefined) upstreamPayload.event_id = data.event_id;
  if (data.payload !== undefined) upstreamPayload.payload = data.payload;
  try {
    const response = await fetch(
      `${env.COACHING_PIPELINE_URL.replace(/\/$/, '')}/api/coaching-activation`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Coaching-Course-Secret': env.COACHING_PROGRESS_SECRET,
        },
        body: JSON.stringify(upstreamPayload),
      }
    );
    const result = await response.json();
    return jsonResponse(result, response.status, origin);
  } catch (_error) {
    console.error(JSON.stringify({
      message: 'coaching_activation_proxy_failed',
      status: 'network_or_json_error',
      enrollment_id: enrollment.id,
    }));
    return jsonResponse({ error: 'Coaching activation is temporarily unavailable' }, 502, origin);
  }
}

// ── Progress Endpoint ─────────────────────────────────────────

async function handleProgress(data, env, origin, ctx) {
  const { email, error: emailError } = validateEmail(data.email);
  if (!email) return jsonResponse({ error: emailError }, 400, origin);
  if (!data.course_id) return jsonResponse({ error: 'Missing: course_id' }, 400, origin);
  if (!data.action) return jsonResponse({ error: 'Missing: action' }, 400, origin);

  const courseId = String(data.course_id).substring(0, 100);
  if (!COURSE_ID_PATTERN.test(courseId)) {
    return jsonResponse({ error: 'Invalid course_id format' }, 400, origin);
  }

  // Verify access
  const user = await env.DB.prepare('SELECT id FROM users WHERE email = ?').bind(email).first();
  if (!user) return jsonResponse({ error: 'No access to this course' }, 403, origin);

  const enrollment = await env.DB.prepare(
    'SELECT id, case_id, athlete_key FROM enrollments WHERE user_id = ? AND course_id = ?'
  ).bind(user.id, courseId).first();
  if (!enrollment) return jsonResponse({ error: 'No access to this course' }, 403, origin);

  if (data.action === 'get') {
    const lessons = await env.DB.prepare(
      'SELECT lesson_id FROM lesson_progress WHERE user_id = ? AND course_id = ?'
    ).bind(user.id, courseId).all();

    const completedLessons = lessons.results.map(r => r.lesson_id);
    const totalLessons = data.total_lessons || 0;

    const userRow = await env.DB.prepare('SELECT * FROM users WHERE id = ?').bind(user.id).first();

    return jsonResponse({
      completed_lessons: completedLessons,
      last_active: userRow.last_active_date,
      pct_complete: totalLessons > 0 ? Math.round((completedLessons.length / totalLessons) * 100) : 0,
      total_xp: userRow.total_xp,
      current_streak: userRow.current_streak,
      level: getLevelInfo(userRow.total_xp)
    }, 200, origin);
  }

  if (data.action === 'complete') {
    if (!data.lesson_id) return jsonResponse({ error: 'Missing: lesson_id' }, 400, origin);
    const lessonId = String(data.lesson_id).substring(0, 100);
    if (!LESSON_ID_PATTERN.test(lessonId)) {
      return jsonResponse({ error: 'Invalid lesson_id format' }, 400, origin);
    }

    // Insert lesson progress (ignore if already completed)
    const insertResult = await env.DB.prepare(
      'INSERT OR IGNORE INTO lesson_progress (user_id, course_id, lesson_id) VALUES (?, ?, ?)'
    ).bind(user.id, courseId, lessonId).run();

    let xpAwarded = 0;
    const xpEvents = [];

    // Only award XP if this is a new completion
    if (insertResult.meta.changes > 0) {
      // Award lesson complete XP
      const totalXP = await awardXP(env, user.id, courseId, 'lesson_complete', XP_LESSON_COMPLETE, lessonId);
      xpAwarded += XP_LESSON_COMPLETE;
      xpEvents.push({ type: 'lesson_complete', xp: XP_LESSON_COMPLETE });

      // Check for module completion bonus
      // Validate: module_lesson_ids must have >= 2 lessons (a single-lesson "module"
      // would be trivially gameable), and all IDs must match LESSON_ID_PATTERN
      if (data.module_lesson_ids && Array.isArray(data.module_lesson_ids) && data.module_lesson_ids.length >= 2) {
        const validIds = data.module_lesson_ids.filter(id =>
          typeof id === 'string' && LESSON_ID_PATTERN.test(id)
        );
        if (validIds.length === data.module_lesson_ids.length && validIds.length <= 20) {
          const placeholders = validIds.map(() => '?').join(',');
          const moduleProgress = await env.DB.prepare(
            `SELECT COUNT(*) as cnt FROM lesson_progress WHERE user_id = ? AND course_id = ? AND lesson_id IN (${placeholders})`
          ).bind(user.id, courseId, ...validIds).first();

          // Only award if ALL listed lessons are actually completed
          if (moduleProgress.cnt === validIds.length) {
            // Check we haven't already awarded module_complete for this exact set
            const moduleRef = validIds.sort().join(',');
            const existingModule = await env.DB.prepare(
              "SELECT id FROM xp_log WHERE user_id = ? AND course_id = ? AND event_type = 'module_complete' AND reference_id = ?"
            ).bind(user.id, courseId, moduleRef).first();

            if (!existingModule) {
              await awardXP(env, user.id, courseId, 'module_complete', XP_MODULE_COMPLETE, moduleRef);
              xpAwarded += XP_MODULE_COMPLETE;
              xpEvents.push({ type: 'module_complete', xp: XP_MODULE_COMPLETE });
            }
          }
        }
      }

      // Check for course completion bonus
      // Don't trust total_lessons from client — use server count
      // Require at minimum 2 lessons and that total_lessons matches server count
      const serverLessonCount = await env.DB.prepare(
        'SELECT COUNT(*) as cnt FROM lesson_progress WHERE user_id = ? AND course_id = ?'
      ).bind(user.id, courseId).first();
      const clientTotal = parseInt(data.total_lessons, 10) || 0;

      // Course completion: client says there are N lessons AND server confirms N completed
      // Guard: require at least 4 lessons to count as a real course
      if (clientTotal >= 4 && serverLessonCount.cnt >= clientTotal) {
        // Check we haven't already awarded course_complete XP
        const existing = await env.DB.prepare(
          "SELECT id FROM xp_log WHERE user_id = ? AND course_id = ? AND event_type = 'course_complete'"
        ).bind(user.id, courseId).first();

        if (!existing) {
          await awardXP(env, user.id, courseId, 'course_complete', XP_COURSE_COMPLETE, courseId);
          xpAwarded += XP_COURSE_COMPLETE;
          xpEvents.push({ type: 'course_complete', xp: XP_COURSE_COMPLETE });
        }
      }

      // Record activity for streak
      await recordActivity(env, user.id);
    }

    // Return updated state
    const lessons = await env.DB.prepare(
      'SELECT lesson_id FROM lesson_progress WHERE user_id = ? AND course_id = ?'
    ).bind(user.id, courseId).all();
    const completedLessons = lessons.results.map(r => r.lesson_id);
    const totalLessons = data.total_lessons || 0;
    const userRow = await env.DB.prepare('SELECT * FROM users WHERE id = ?').bind(user.id).first();

    if (insertResult.meta.changes > 0 && enrollment.case_id && enrollment.athlete_key &&
        env.COACHING_PIPELINE_URL && env.COACHING_PROGRESS_SECRET && ctx) {
      const progressEvent = syncCoachingProgress(env, {
        case_id: enrollment.case_id,
        athlete_key: enrollment.athlete_key,
        course_id: courseId,
        lesson_id: lessonId,
        completed_lessons: completedLessons.length,
        total_lessons: Number(totalLessons) || 0,
        pct_complete: totalLessons > 0
          ? Math.min(100, Math.round((completedLessons.length / totalLessons) * 100))
          : 0,
        event_id: `course:${enrollment.id}:${courseId}:${lessonId}`,
      });
      ctx.waitUntil(progressEvent);
    }

    return jsonResponse({
      completed_lessons: completedLessons,
      last_active: userRow.last_active_date,
      pct_complete: totalLessons > 0 ? Math.round((completedLessons.length / totalLessons) * 100) : 0,
      xp_awarded: xpAwarded,
      xp_events: xpEvents,
      total_xp: userRow.total_xp,
      current_streak: userRow.current_streak,
      level: getLevelInfo(userRow.total_xp)
    }, 200, origin);
  }

  return jsonResponse({ error: 'Invalid action (get|complete)' }, 400, origin);
}

async function syncCoachingProgress(env, payload) {
  try {
    const response = await fetch(`${env.COACHING_PIPELINE_URL.replace(/\/$/, '')}/api/coaching-course-progress`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Coaching-Course-Secret': env.COACHING_PROGRESS_SECRET,
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      console.error(JSON.stringify({
        message: 'coaching_course_progress_sync_failed',
        status: response.status,
        course_id: payload.course_id,
        event_id: payload.event_id,
      }));
    }
  } catch (error) {
    console.error(JSON.stringify({
      message: 'coaching_course_progress_sync_failed',
      status: 'network_error',
      course_id: payload.course_id,
      event_id: payload.event_id,
    }));
  }
}

// ── Knowledge Check Endpoint ──────────────────────────────────

async function handleKC(data, env, origin) {
  const { email, error: emailError } = validateEmail(data.email);
  if (!email) return jsonResponse({ error: emailError }, 400, origin);
  if (!data.course_id) return jsonResponse({ error: 'Missing: course_id' }, 400, origin);
  if (!data.lesson_id) return jsonResponse({ error: 'Missing: lesson_id' }, 400, origin);
  if (!data.question_hash) return jsonResponse({ error: 'Missing: question_hash' }, 400, origin);
  if (data.selected_index === undefined) return jsonResponse({ error: 'Missing: selected_index' }, 400, origin);
  if (data.correct === undefined) return jsonResponse({ error: 'Missing: correct' }, 400, origin);

  const courseId = String(data.course_id).substring(0, 100);
  if (!COURSE_ID_PATTERN.test(courseId)) {
    return jsonResponse({ error: 'Invalid course_id format' }, 400, origin);
  }
  const lessonId = String(data.lesson_id).substring(0, 100);
  if (!LESSON_ID_PATTERN.test(lessonId)) {
    return jsonResponse({ error: 'Invalid lesson_id format' }, 400, origin);
  }
  const questionHash = String(data.question_hash).substring(0, 8);
  if (!QUESTION_HASH_PATTERN.test(questionHash)) {
    return jsonResponse({ error: 'Invalid question_hash format' }, 400, origin);
  }

  const user = await env.DB.prepare('SELECT id FROM users WHERE email = ?').bind(email).first();
  if (!user) return jsonResponse({ error: 'No access' }, 403, origin);

  const enrollment = await env.DB.prepare(
    'SELECT id FROM enrollments WHERE user_id = ? AND course_id = ?'
  ).bind(user.id, courseId).first();
  if (!enrollment) return jsonResponse({ error: 'No access to this course' }, 403, origin);

  const correct = data.correct ? 1 : 0;
  const selectedIndex = parseInt(data.selected_index, 10);

  // Insert answer (ignore if already answered)
  const insertResult = await env.DB.prepare(
    'INSERT OR IGNORE INTO knowledge_check_answers (user_id, course_id, lesson_id, question_hash, selected_index, correct) VALUES (?, ?, ?, ?, ?, ?)'
  ).bind(user.id, courseId, lessonId, questionHash, selectedIndex, correct).run();

  let xpAwarded = 0;
  if (insertResult.meta.changes > 0 && correct) {
    await awardXP(env, user.id, courseId, 'kc_correct', XP_KC_CORRECT, questionHash);
    xpAwarded = XP_KC_CORRECT;
  }

  // Record activity for streak
  if (insertResult.meta.changes > 0) {
    await recordActivity(env, user.id);
  }

  const userRow = await env.DB.prepare('SELECT total_xp, current_streak FROM users WHERE id = ?').bind(user.id).first();

  return jsonResponse({
    recorded: true,
    correct: !!correct,
    xp_awarded: xpAwarded,
    total_xp: userRow.total_xp,
    current_streak: userRow.current_streak,
    level: getLevelInfo(userRow.total_xp)
  }, 200, origin);
}

// ── Stats Endpoint ────────────────────────────────────────────

async function handleStats(data, env, origin) {
  const { email, error: emailError } = validateEmail(data.email);
  if (!email) return jsonResponse({ error: emailError }, 400, origin);

  const user = await env.DB.prepare('SELECT * FROM users WHERE email = ?').bind(email).first();
  if (!user) return jsonResponse({ error: 'User not found' }, 404, origin);

  let leaderboardRank = null;
  if (data.course_id) {
    const courseId = String(data.course_id).substring(0, 100);
    // Rank among users enrolled in this course
    const rank = await env.DB.prepare(`
      SELECT COUNT(*) + 1 as rank FROM users u
      JOIN enrollments e ON e.user_id = u.id
      WHERE e.course_id = ? AND u.total_xp > ?
    `).bind(courseId, user.total_xp).first();
    leaderboardRank = rank.rank;
  }

  return jsonResponse({
    total_xp: user.total_xp,
    current_streak: user.current_streak,
    longest_streak: user.longest_streak,
    last_active_date: user.last_active_date,
    level: getLevelInfo(user.total_xp),
    leaderboard_rank: leaderboardRank
  }, 200, origin);
}

// ── Leaderboard Endpoint ──────────────────────────────────────

async function handleLeaderboard(data, env, origin) {
  if (!data.course_id) return jsonResponse({ error: 'Missing: course_id' }, 400, origin);

  const courseId = String(data.course_id).substring(0, 100);
  if (!COURSE_ID_PATTERN.test(courseId)) {
    return jsonResponse({ error: 'Invalid course_id format' }, 400, origin);
  }

  const leaders = await env.DB.prepare(`
    SELECT u.email_hash, u.total_xp, u.current_streak,
           (SELECT COUNT(*) FROM lesson_progress lp WHERE lp.user_id = u.id AND lp.course_id = ?) as lessons_completed
    FROM users u
    JOIN enrollments e ON e.user_id = u.id
    WHERE e.course_id = ?
    ORDER BY u.total_xp DESC
    LIMIT 10
  `).bind(courseId, courseId).all();

  const leaderboard = leaders.results.map((row, i) => ({
    rank: i + 1,
    user_hash: row.email_hash,
    total_xp: row.total_xp,
    current_streak: row.current_streak,
    lessons_completed: row.lessons_completed,
    level: getLevelInfo(row.total_xp)
  }));

  return jsonResponse({ course_id: courseId, leaderboard }, 200, origin);
}

// ── Admin Endpoints ───────────────────────────────────────────

async function handleAdmin(request, path, env) {
  const authHeader = request.headers.get('Authorization') || '';
  const token = authHeader.replace('Bearer ', '').trim();
  const origin = request.headers.get('Origin') || '';
  const allowedOrigins = (env.ALLOWED_ORIGINS || 'https://gravelgodcycling.com').split(',').map(o => o.trim());
  const corsOrigin = allowedOrigins.includes(origin) ? origin : allowedOrigins[0];

  const dashboardAuthorized = Boolean(
    env.ADMIN_API_KEY && await timingSafeSecretEqual(token, env.ADMIN_API_KEY)
  );
  const grantAuthorized = ['/admin/grant', '/admin/canary'].includes(path) && Boolean(
    env.COURSE_ACCESS_GRANT_KEY &&
    await timingSafeSecretEqual(token, env.COURSE_ACCESS_GRANT_KEY)
  );
  if (!dashboardAuthorized && !grantAuthorized) {
    return jsonResponse({ error: 'Unauthorized' }, 401, corsOrigin);
  }

  let data;
  try {
    data = await request.json();
  } catch (e) {
    data = {};
  }

  if (path === '/admin/dashboard') return handleAdminDashboard(data, env, corsOrigin);
  if (path === '/admin/grant') return handleAdminGrant(data, env, corsOrigin);
  if (path === '/admin/canary') {
    try {
      return jsonResponse(await runCourseCanary(env), 200, corsOrigin);
    } catch (_error) {
      return jsonResponse({ error: 'Course canary failed' }, 503, corsOrigin);
    }
  }

  return jsonResponse({ error: 'Not found' }, 404, corsOrigin);
}

async function handleAdminDashboard(data, env, origin) {
  const now = new Date();
  const today = todayUTC();
  const d7 = new Date(now - 7 * 86400000).toISOString().split('T')[0];
  const d30 = new Date(now - 30 * 86400000).toISOString().split('T')[0];

  // Revenue
  const totalEnrollments = await env.DB.prepare('SELECT COUNT(*) as cnt FROM enrollments').first();
  const totalRevenue = await env.DB.prepare('SELECT COALESCE(SUM(amount_cents), 0) as total FROM enrollments').first();
  const recentPurchases = await env.DB.prepare(
    'SELECT e.course_id, u.email, e.amount_cents, e.currency, e.purchased_at FROM enrollments e JOIN users u ON u.id = e.user_id WHERE e.purchased_at >= ? ORDER BY e.purchased_at DESC LIMIT 20'
  ).bind(d7).all();
  const revenueByCourse = await env.DB.prepare(
    'SELECT course_id, COUNT(*) as enrollments, COALESCE(SUM(amount_cents), 0) as revenue FROM enrollments GROUP BY course_id'
  ).all();

  // Engagement
  const active24h = await env.DB.prepare(
    'SELECT COUNT(DISTINCT user_id) as cnt FROM streak_history WHERE active_date = ?'
  ).bind(today).first();
  const active7d = await env.DB.prepare(
    'SELECT COUNT(DISTINCT user_id) as cnt FROM streak_history WHERE active_date >= ?'
  ).bind(d7).first();
  const active30d = await env.DB.prepare(
    'SELECT COUNT(DISTINCT user_id) as cnt FROM streak_history WHERE active_date >= ?'
  ).bind(d30).first();

  // Streaks
  const activeStreaks = await env.DB.prepare(
    "SELECT email_hash, current_streak, longest_streak FROM users WHERE current_streak > 0 AND last_active_date >= ? ORDER BY current_streak DESC LIMIT 20"
  ).bind(new Date(now - 2 * 86400000).toISOString().split('T')[0]).all();

  // Course health
  const courseHealth = await env.DB.prepare(`
    SELECT
      e.course_id,
      COUNT(DISTINCT e.user_id) as enrolled,
      COUNT(DISTINCT lp.user_id) as started,
      (SELECT COUNT(DISTINCT lp2.user_id) FROM lesson_progress lp2
       JOIN enrollments e2 ON e2.user_id = lp2.user_id AND e2.course_id = lp2.course_id
       JOIN xp_log xl ON xl.user_id = lp2.user_id AND xl.course_id = lp2.course_id AND xl.event_type = 'course_complete'
       WHERE lp2.course_id = e.course_id) as completed
    FROM enrollments e
    LEFT JOIN lesson_progress lp ON lp.user_id = e.user_id AND lp.course_id = e.course_id
    GROUP BY e.course_id
  `).all();

  // KC accuracy
  const kcAccuracy = await env.DB.prepare(`
    SELECT course_id, lesson_id, question_hash,
           COUNT(*) as attempts,
           SUM(correct) as correct_count,
           ROUND(CAST(SUM(correct) AS FLOAT) / COUNT(*) * 100, 1) as accuracy_pct
    FROM knowledge_check_answers
    GROUP BY course_id, lesson_id, question_hash
    ORDER BY accuracy_pct ASC
  `).all();

  // Nudge stats
  const nudgeStats = await env.DB.prepare(`
    SELECT nudge_type, COUNT(*) as sent FROM nudge_log GROUP BY nudge_type
  `).all();

  return jsonResponse({
    generated_at: now.toISOString(),
    revenue: {
      total_enrollments: totalEnrollments.cnt,
      total_revenue_cents: totalRevenue.total,
      by_course: revenueByCourse.results,
      recent_purchases: recentPurchases.results
    },
    engagement: {
      active_24h: active24h.cnt,
      active_7d: active7d.cnt,
      active_30d: active30d.cnt
    },
    streaks: {
      active_streaks: activeStreaks.results
    },
    course_health: courseHealth.results,
    knowledge_checks: kcAccuracy.results,
    nudges: nudgeStats.results
  }, 200, origin);
}

async function handleAdminGrant(data, env, origin) {
  if (!data.email) return jsonResponse({ error: 'Missing: email' }, 400, origin);
  if (!data.course_id) return jsonResponse({ error: 'Missing: course_id' }, 400, origin);

  const { email, error: emailError } = validateEmail(data.email);
  if (!email) return jsonResponse({ error: emailError }, 400, origin);
  const courseId = String(data.course_id).substring(0, 100);
  if (!COURSE_ID_PATTERN.test(courseId)) {
    return jsonResponse({ error: 'Invalid course_id format' }, 400, origin);
  }
  const caseId = String(data.case_id || '').trim();
  const athleteKey = String(data.athlete_key || '').trim().toLowerCase();
  const brand = String(data.brand || '').trim().toLowerCase();
  const tier = String(data.tier || '').trim().toLowerCase();
  const preferredName = String(data.preferred_name || '').trim().substring(0, 80);
  const goalLabel = String(data.goal_label || '').trim().substring(0, 160);
  const hasCaseBinding = Boolean(caseId || athleteKey);
  if (hasCaseBinding && (!CASE_ID_PATTERN.test(caseId) || !ATHLETE_KEY_PATTERN.test(athleteKey))) {
    return jsonResponse({ error: 'Valid case_id and athlete_key are required together' }, 400, origin);
  }
  if ((brand && !SLUG_PATTERN.test(brand)) || (tier && !SLUG_PATTERN.test(tier))) {
    return jsonResponse({ error: 'Invalid brand or tier format' }, 400, origin);
  }
  if (courseId === COACHING_COURSE_ID && !hasCaseBinding) {
    return jsonResponse({ error: 'Coaching activation access must be case-bound' }, 400, origin);
  }

  let accessToken = null;
  let accessTokenHash = null;
  let accessTokenExpiresAt = null;
  if (courseId === COACHING_COURSE_ID) {
    accessToken = generateAccessToken();
    accessTokenHash = await sha256Hex(accessToken);
    accessTokenExpiresAt = new Date(Date.now() + 365 * 86400000).toISOString();
  }

  const user = await getOrCreateUser(env, email);

  await env.DB.prepare(`
    INSERT INTO enrollments
      (user_id, course_id, stripe_session_id, amount_cents, currency, case_id,
       athlete_key, brand, tier, preferred_name, goal_label,
       access_token_hash, access_token_expires_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(user_id, course_id) DO UPDATE SET
      case_id = COALESCE(excluded.case_id, enrollments.case_id),
      athlete_key = COALESCE(excluded.athlete_key, enrollments.athlete_key),
      brand = COALESCE(excluded.brand, enrollments.brand),
      tier = COALESCE(excluded.tier, enrollments.tier),
      preferred_name = COALESCE(excluded.preferred_name, enrollments.preferred_name),
      goal_label = COALESCE(excluded.goal_label, enrollments.goal_label),
      access_token_hash = COALESCE(excluded.access_token_hash, enrollments.access_token_hash),
      access_token_expires_at = COALESCE(excluded.access_token_expires_at, enrollments.access_token_expires_at)
  `).bind(
    user.id, courseId, data.stripe_session_id || 'manual_grant',
    data.amount_cents || 0, data.currency || 'usd',
    caseId || null, athleteKey || null, brand || null, tier || null,
    preferredName || null, goalLabel || null,
    accessTokenHash, accessTokenExpiresAt
  ).run();

  return jsonResponse({
    granted: true,
    email: email,
    course_id: courseId,
    case_bound: hasCaseBinding,
    case_id: caseId || null,
    access_token: accessToken,
    access_token_expires_at: accessTokenExpiresAt,
  }, 200, origin);
}

// ── Unsubscribe Endpoint ──────────────────────────────────────

async function handleUnsubscribe(url, env) {
  const token = url.searchParams.get('token');
  const emailParam = url.searchParams.get('email');
  if (!token || !emailParam) {
    return new Response(
      '<html><body style="font-family:monospace;text-align:center;padding:60px"><h1>Invalid link</h1><p>Missing required parameters.</p></body></html>',
      { status: 400, headers: { 'Content-Type': 'text/html' } }
    );
  }

  const email = decodeURIComponent(emailParam).toLowerCase().trim();

  if (!env.NUDGE_UNSUBSCRIBE_SECRET) {
    console.error('NUDGE_UNSUBSCRIBE_SECRET not configured');
    return new Response(
      '<html><body style="font-family:monospace;text-align:center;padding:60px"><h1>Server error</h1><p>Unsubscribe is temporarily unavailable.</p></body></html>',
      { status: 500, headers: { 'Content-Type': 'text/html' } }
    );
  }

  // O(1) verification: compute expected HMAC for this email, compare to token
  const expectedToken = await generateHMAC(
    `${email}:unsubscribe`,
    env.NUDGE_UNSUBSCRIBE_SECRET
  );

  if (!timingSafeEqual(token, expectedToken)) {
    return new Response(
      '<html><body style="font-family:monospace;text-align:center;padding:60px"><h1>Invalid or expired link</h1><p>This unsubscribe link is no longer valid.</p></body></html>',
      { status: 400, headers: { 'Content-Type': 'text/html' } }
    );
  }

  // Token is valid — find and update user
  const user = await env.DB.prepare(
    'SELECT id FROM users WHERE email = ?'
  ).bind(email).first();

  if (!user) {
    return new Response(
      '<html><body style="font-family:monospace;text-align:center;padding:60px"><h1>Not found</h1><p>No account found for this email address.</p></body></html>',
      { status: 404, headers: { 'Content-Type': 'text/html' } }
    );
  }

  await env.DB.prepare(
    'UPDATE users SET nudge_unsubscribed = 1 WHERE id = ?'
  ).bind(user.id).run();

  return new Response(
    '<html><body style="font-family:monospace;text-align:center;padding:60px"><h1>Unsubscribed</h1><p>You will no longer receive nudge emails from Gravel God Courses.</p></body></html>',
    { status: 200, headers: { 'Content-Type': 'text/html' } }
  );
}

// ── Stripe Webhook Endpoint ─────────────────────────────────

async function handleWebhook(request, env) {
  const signature = request.headers.get('stripe-signature');
  if (!signature) {
    return new Response(JSON.stringify({ error: 'Missing stripe-signature header' }), {
      status: 401, headers: { 'Content-Type': 'application/json' }
    });
  }

  const body = await request.text();

  const isValid = await verifyStripeSignature(body, signature, env.STRIPE_WEBHOOK_SECRET);
  if (!isValid) {
    return new Response(JSON.stringify({ error: 'Invalid signature' }), {
      status: 401, headers: { 'Content-Type': 'application/json' }
    });
  }

  let event;
  try {
    event = JSON.parse(body);
  } catch (e) {
    return new Response(JSON.stringify({ error: 'Invalid JSON' }), {
      status: 400, headers: { 'Content-Type': 'application/json' }
    });
  }

  if (event.type !== 'checkout.session.completed') {
    return new Response(JSON.stringify({ received: true }), {
      status: 200, headers: { 'Content-Type': 'application/json' }
    });
  }

  const session = event.data.object;
  const email = (session.customer_details?.email || session.customer_email || '').toLowerCase().trim();

  if (!email) {
    console.error('Webhook: No email in checkout session', session.id);
    return new Response(JSON.stringify({ error: 'No email in session' }), {
      status: 400, headers: { 'Content-Type': 'application/json' }
    });
  }

  const courseId = session.metadata?.course_id || extractCourseIdFromSession(session);
  if (!courseId) {
    console.error('Webhook: No course_id found', session.id);
    return new Response(JSON.stringify({ error: 'No course_id in session' }), {
      status: 400, headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const user = await getOrCreateUser(env, email);

    // Bundles use a comma-separated course_id list ("course-a,course-b") —
    // grant one enrollment per course.
    const courseIds = courseId.split(',').map(c => c.trim()).filter(Boolean);
    for (const cid of courseIds) {
      await env.DB.prepare(
        'INSERT OR IGNORE INTO enrollments (user_id, course_id, stripe_session_id, amount_cents, currency) VALUES (?, ?, ?, ?, ?)'
      ).bind(
        user.id,
        cid,
        session.id,
        session.amount_total || 0,
        session.currency || 'usd'
      ).run();
    }

    console.log('Access granted:', { email, courseIds, session_id: session.id });
  } catch (dbError) {
    console.error('D1 write failed:', dbError);
    return new Response(JSON.stringify({ error: 'Storage error' }), {
      status: 500, headers: { 'Content-Type': 'application/json' }
    });
  }

  // Send confirmation email (non-blocking)
  try {
    if (env.SENDGRID_API_KEY && env.NOTIFICATION_EMAIL) {
      await sendPurchaseNotification(env, email, courseId, session);
    }
  } catch (downstreamError) {
    console.error('Notification error (user unaffected):', downstreamError);
  }

  return new Response(JSON.stringify({ received: true, access_granted: true }), {
    status: 200, headers: { 'Content-Type': 'application/json' }
  });
}

// ── Stripe Signature Verification ───────────────────────────

async function verifyStripeSignature(payload, header, secret) {
  if (!secret) return false;

  const parts = {};
  header.split(',').forEach(item => {
    const [key, value] = item.split('=');
    parts[key] = value;
  });

  const timestamp = parts['t'];
  const sig = parts['v1'];
  if (!timestamp || !sig) return false;

  const age = Math.floor(Date.now() / 1000) - parseInt(timestamp, 10);
  if (age > 300) return false;

  const signedPayload = `${timestamp}.${payload}`;
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw', encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
  );

  const signatureBuffer = await crypto.subtle.sign('HMAC', key, encoder.encode(signedPayload));
  const expectedSig = Array.from(new Uint8Array(signatureBuffer))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');

  return timingSafeEqual(sig, expectedSig);
}

// ── HMAC helper (for unsubscribe tokens) ────────────────────

async function generateHMAC(message, secret) {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw', encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
  );
  const sig = await crypto.subtle.sign('HMAC', key, encoder.encode(message));
  return Array.from(new Uint8Array(sig)).map(b => b.toString(16).padStart(2, '0')).join('');
}

function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}

async function timingSafeSecretEqual(a, b) {
  const [left, right] = await Promise.all([
    crypto.subtle.digest('SHA-256', new TextEncoder().encode(String(a || ''))),
    crypto.subtle.digest('SHA-256', new TextEncoder().encode(String(b || ''))),
  ]);
  return crypto.subtle.timingSafeEqual(left, right);
}

function extractCourseIdFromSession(session) {
  const successUrl = session.success_url || '';
  const match = successUrl.match(/\/course\/([a-z0-9-]+)\//);
  return match ? match[1] : null;
}

// ── Notification Email ──────────────────────────────────────

async function sendPurchaseNotification(env, email, courseId, session) {
  const amount = session.amount_total
    ? `$${(session.amount_total / 100).toFixed(2)} ${(session.currency || 'usd').toUpperCase()}`
    : '—';

  const resp = await fetch('https://api.sendgrid.com/v3/mail/send', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.SENDGRID_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      personalizations: [{
        to: [{ email: env.NOTIFICATION_EMAIL }],
        subject: `[GG Course] New purchase: ${esc(courseId)} — ${esc(email)}`
      }],
      from: { email: 'courses@gravelgodcycling.com', name: 'Gravel God Courses' },
      reply_to: { email: email },
      content: [{
        type: 'text/html',
        value: `
          <h2>New Course Purchase</h2>
          <table style="border-collapse:collapse;font-family:monospace">
            <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Course</td><td>${esc(courseId)}</td></tr>
            <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Email</td><td>${esc(email)}</td></tr>
            <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Amount</td><td>${esc(amount)}</td></tr>
            <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Session ID</td><td>${esc(session.id)}</td></tr>
            <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Time</td><td>${new Date().toISOString()}</td></tr>
          </table>
        `
      }]
    })
  });

  console.log('SendGrid purchase notification:', resp.status);
}

// ── Helpers ─────────────────────────────────────────────────

function esc(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function handleCORS(request, env) {
  const origin = request.headers.get('Origin');
  const allowedOrigins = (env.ALLOWED_ORIGINS || 'https://gravelgodcycling.com').split(',').map(o => o.trim());
  const allowOrigin = allowedOrigins.includes(origin) ? origin : '';
  return new Response(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': allowOrigin,
      'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
      'Access-Control-Max-Age': '86400'
    }
  });
}

function jsonResponse(body, status, origin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': origin || ''
    }
  });
}
