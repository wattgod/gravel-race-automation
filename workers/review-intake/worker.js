/**
 * Cloudflare Worker: Race Review Intake
 *
 * Receives inline race review submissions from race profile pages.
 * Validates, sends Resend notification to coaching team.
 */

const DISPOSABLE_DOMAINS = [
  '10minutemail.com', 'guerrillamail.com', 'mailinator.com', 'tempmail.com',
  'throwaway.email', 'fakeinbox.com', 'trashmail.com', 'maildrop.cc',
  'yopmail.com', 'temp-mail.org', 'getnada.com', 'mohmal.com'
];

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') return handleCORS(request, env);
    if (request.method !== 'POST') return new Response('Method not allowed', { status: 405 });

    const origin = request.headers.get('Origin');
    const allowedOrigins = (env.ALLOWED_ORIGINS || 'https://gravelgodcycling.com').split(',').map(o => o.trim());
    if (!allowedOrigins.some(allowed => origin?.startsWith(allowed))) {
      return new Response('Forbidden', { status: 403 });
    }

    // Parse JSON — return honest 400 if body is malformed
    let data;
    try {
      data = await request.json();
    } catch (parseError) {
      return jsonResponse({ error: 'Invalid JSON' }, 400, origin);
    }

    // Honeypot
    if (data.website) return jsonResponse({ error: 'Bot detected' }, 400, origin);

    // Sanitize string inputs: truncate to sane lengths
    if (data.email) data.email = String(data.email).substring(0, 254);
    if (data.race_slug) data.race_slug = String(data.race_slug).substring(0, 100);
    if (data.race_name) data.race_name = String(data.race_name).substring(0, 200);
    if (data.best) data.best = String(data.best).substring(0, 500);
    if (data.worst) data.worst = String(data.worst).substring(0, 500);

    const validation = validateReview(data);
    if (!validation.valid) {
      return jsonResponse({ error: validation.error }, 400, origin);
    }

    const reviewId = generateReviewId(data.email, data.race_slug);
    const review = formatReview(data, reviewId);

    // Downstream: notification email. Failures logged, don't affect user response.
    try {
      if (env.RESEND_API_KEY && env.NOTIFICATION_EMAIL) {
        await sendNotificationEmail(env, review);
      }
    } catch (downstreamError) {
      console.error('Downstream error (user unaffected):', downstreamError);
    }

    console.log('Review submitted:', { review_id: reviewId, race: data.race_slug, stars: data.stars });

    return jsonResponse({
      success: true,
      message: 'Review submitted — thank you!'
    }, 200, origin);
  }
};

// --- HTML Escaping ---

function esc(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// --- Validation ---

function validateReview(data) {
  if (!data.email) return { valid: false, error: 'Missing: email' };
  if (!data.race_slug) return { valid: false, error: 'Missing: race slug' };
  if (!data.stars || data.stars < 1 || data.stars > 5) return { valid: false, error: 'Invalid star rating' };

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
    return { valid: false, error: 'Invalid email format' };
  }

  const emailDomain = data.email.split('@')[1].toLowerCase();
  if (DISPOSABLE_DOMAINS.includes(emailDomain)) {
    return { valid: false, error: 'Please use a non-disposable email' };
  }

  return { valid: true };
}

// --- Formatting ---

function generateReviewId(email, raceSlug) {
  const ts = Date.now().toString(36);
  const hash = email.split('').reduce((a, c) => ((a << 5) - a + c.charCodeAt(0)) | 0, 0).toString(36);
  return `rv-${raceSlug.substring(0, 20)}-${hash}-${ts}`;
}

function formatReview(data, reviewId) {
  return {
    review_id: reviewId,
    race_slug: data.race_slug,
    race_name: data.race_name || data.race_slug,
    email: data.email,
    stars: data.stars,
    year_raced: data.year_raced || '',
    would_race_again: data.would_race_again || '',
    finish_position: data.finish_position || '',
    best: (data.best || '').trim(),
    worst: (data.worst || '').trim(),
    submitted_at: new Date().toISOString()
  };
}

// --- Notification Email ---

// Resend: SendGrid's key has been returning 401 account-wide. Sent from
// noreply@ -- the domain's other addresses (e.g. matti@) are accepted by
// Resend but silently never deliver, so noreply@ + a display name is the
// only address confirmed to arrive.
async function sendNotificationEmail(env, review) {
  const stars = '\u2605'.repeat(review.stars) + '\u2606'.repeat(5 - review.stars);

  const html = `
    <h2>${esc(review.race_name)} — ${stars}</h2>
    <table style="border-collapse:collapse;font-family:monospace">
      <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Review ID</td><td>${esc(review.review_id)}</td></tr>
      <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Email</td><td>${esc(review.email)}</td></tr>
      <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Stars</td><td>${review.stars}/5</td></tr>
      <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Year Raced</td><td>${esc(review.year_raced) || '—'}</td></tr>
      <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Would Race Again</td><td>${esc(review.would_race_again) || '—'}</td></tr>
      <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Finish</td><td>${esc(review.finish_position) || '—'}</td></tr>
      <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Best Thing</td><td>${esc(review.best) || '—'}</td></tr>
      <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Worst Thing</td><td>${esc(review.worst) || '—'}</td></tr>
    </table>
    <p style="color:#999;font-size:12px">Submitted: ${esc(review.submitted_at)}</p>
  `;

  try {
    const resp = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.RESEND_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        from: 'Gravel God Reviews <noreply@gravelgodcycling.com>',
        to: [env.NOTIFICATION_EMAIL],
        reply_to: review.email,
        subject: `[GG Review] ${(review.race_name).substring(0, 60)} - ${stars} (${review.stars}/5)`,
        html
      })
    });
    const detail = await resp.text();
    console.log('Review notification (resend):', resp.status, detail.slice(0, 200));
  } catch (error) {
    console.error('Resend notification failed:', error);
  }
}

// --- CORS + Response Helpers ---

function handleCORS(request, env) {
  const origin = request.headers.get('Origin');
  const allowedOrigins = (env.ALLOWED_ORIGINS || 'https://gravelgodcycling.com').split(',').map(o => o.trim());
  const allowOrigin = allowedOrigins.find(a => origin?.startsWith(a)) || '';
  return new Response(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': allowOrigin,
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Max-Age': '86400'
    }
  });
}

function jsonResponse(body, status, origin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': origin || '*'
    }
  });
}
