/**
 * Cloudflare Worker: Tire Review Intake
 *
 * Receives tire review submissions from per-tire pages.
 * Validates, writes to KV, sends SendGrid notification.
 */

const DISPOSABLE_DOMAINS = [
  '10minutemail.com', 'guerrillamail.com', 'mailinator.com', 'tempmail.com',
  'throwaway.email', 'fakeinbox.com', 'trashmail.com', 'maildrop.cc',
  'yopmail.com', 'temp-mail.org', 'getnada.com', 'mohmal.com'
];

const VALID_CONDITIONS = ['dry', 'mixed', 'wet', 'mud'];

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
    if (data.tire_id) data.tire_id = String(data.tire_id).substring(0, 100);
    if (data.tire_name) data.tire_name = String(data.tire_name).substring(0, 200);
    if (data.email) data.email = String(data.email).substring(0, 254);
    if (data.race_used_at) data.race_used_at = String(data.race_used_at).substring(0, 100);
    if (data.review_text) data.review_text = String(data.review_text).substring(0, 500);

    const validation = validateReview(data);
    if (!validation.valid) {
      return jsonResponse({ error: validation.error }, 400, origin);
    }

    const reviewId = generateReviewId(data.email, data.tire_id);
    const review = formatReview(data, reviewId);
    const kvKey = `${data.tire_id}:${reviewId}`;

    // Write to KV
    try {
      await env.TIRE_REVIEWS.put(kvKey, JSON.stringify(review), {
        metadata: {
          tire_id: data.tire_id,
          stars: data.stars,
          submitted_at: review.submitted_at,
        }
      });
    } catch (kvError) {
      console.error('KV write failed:', kvError);
      return jsonResponse({ error: 'Storage error' }, 500, origin);
    }

    // Notification email. Failures logged, don't affect user response.
    try {
      if (env.SENDGRID_API_KEY && env.NOTIFICATION_EMAIL) {
        await sendNotificationEmail(env, review);
      }
    } catch (downstreamError) {
      console.error('Downstream error (user unaffected):', downstreamError);
    }

    console.log('Tire review submitted:', { review_id: reviewId, tire: data.tire_id, stars: data.stars });

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
  if (!data.tire_id) return { valid: false, error: 'Missing: tire_id' };
  if (!data.tire_name) return { valid: false, error: 'Missing: tire_name' };
  if (!data.email) return { valid: false, error: 'Missing: email' };
  if (!data.stars || !Number.isInteger(data.stars) || data.stars < 1 || data.stars > 5) {
    return { valid: false, error: 'Invalid star rating (1-5)' };
  }

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
    return { valid: false, error: 'Invalid email format' };
  }

  const emailDomain = data.email.split('@')[1].toLowerCase();
  if (DISPOSABLE_DOMAINS.includes(emailDomain)) {
    return { valid: false, error: 'Please use a non-disposable email' };
  }

  // Optional field validation
  if (data.width_ridden != null) {
    const w = Number(data.width_ridden);
    if (!Number.isInteger(w) || w <= 0) {
      return { valid: false, error: 'Invalid width_ridden' };
    }
  }

  if (data.pressure_psi != null) {
    const p = Number(data.pressure_psi);
    if (!Number.isInteger(p) || p < 15 || p > 60) {
      return { valid: false, error: 'Invalid pressure_psi (15-60)' };
    }
  }

  if (data.conditions != null) {
    if (!Array.isArray(data.conditions) || !data.conditions.every(c => VALID_CONDITIONS.includes(c))) {
      return { valid: false, error: 'Invalid conditions' };
    }
  }

  if (data.would_recommend != null && !['yes', 'no'].includes(data.would_recommend)) {
    return { valid: false, error: 'Invalid would_recommend (yes/no)' };
  }

  return { valid: true };
}

// --- Formatting ---

function generateReviewId(email, tireId) {
  const ts = Date.now().toString(36);
  const hash = email.split('').reduce((a, c) => ((a << 5) - a + c.charCodeAt(0)) | 0, 0).toString(36);
  return `tr-${tireId.substring(0, 20)}-${hash}-${ts}`;
}

function formatReview(data, reviewId) {
  return {
    review_id: reviewId,
    tire_id: data.tire_id,
    tire_name: data.tire_name,
    email: data.email,
    stars: data.stars,
    width_ridden: data.width_ridden || null,
    pressure_psi: data.pressure_psi || null,
    conditions: data.conditions || [],
    race_used_at: (data.race_used_at || '').trim() || null,
    would_recommend: data.would_recommend || null,
    review_text: (data.review_text || '').trim() || null,
    submitted_at: new Date().toISOString()
  };
}

// --- Notification Email ---

async function sendNotificationEmail(env, review) {
  const stars = '\u2605'.repeat(review.stars) + '\u2606'.repeat(5 - review.stars);
  const conditions = review.conditions.length ? review.conditions.join(', ') : '—';

  const resp = await fetch('https://api.sendgrid.com/v3/mail/send', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.SENDGRID_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      personalizations: [{
        to: [{ email: env.NOTIFICATION_EMAIL }],
        subject: `[GG Tire Review] ${(review.tire_name).substring(0, 60)} - ${stars} (${review.stars}/5)`
      }],
      from: { email: 'reviews@gravelgodcycling.com', name: 'Gravel God Tire Reviews' },
      reply_to: { email: review.email },
      content: [{
        type: 'text/html',
        value: `
          <h2>${esc(review.tire_name)} — ${stars}</h2>
          <table style="border-collapse:collapse;font-family:monospace">
            <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Review ID</td><td>${esc(review.review_id)}</td></tr>
            <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Email</td><td>${esc(review.email)}</td></tr>
            <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Stars</td><td>${review.stars}/5</td></tr>
            <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Width Ridden</td><td>${review.width_ridden ? review.width_ridden + 'mm' : '—'}</td></tr>
            <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Pressure</td><td>${review.pressure_psi ? review.pressure_psi + ' psi' : '—'}</td></tr>
            <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Conditions</td><td>${esc(conditions)}</td></tr>
            <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Race Used At</td><td>${esc(review.race_used_at) || '—'}</td></tr>
            <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Recommend?</td><td>${esc(review.would_recommend) || '—'}</td></tr>
            <tr><td style="padding:4px 12px 4px 0;font-weight:bold">Review Text</td><td>${esc(review.review_text) || '—'}</td></tr>
          </table>
          <p style="color:#999;font-size:12px">Submitted: ${esc(review.submitted_at)}</p>
        `
      }]
    })
  });

  console.log('SendGrid notification:', resp.status);
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
