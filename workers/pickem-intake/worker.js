/**
 * Cloudflare Worker: Pick'em Intake
 *
 * POST /        Saves one entry per email per game to KV. Resubmitting before
 *               the lock replaces the earlier picks. After the lock: 403.
 * GET  /export  Every entry for a game (Authorization: Bearer EXPORT_TOKEN),
 *               for scoring and the opt-in list.
 */

const DISPOSABLE_DOMAINS = [
  '10minutemail.com', 'guerrillamail.com', 'mailinator.com', 'tempmail.com',
  'throwaway.email', 'fakeinbox.com', 'trashmail.com', 'maildrop.cc',
  'yopmail.com', 'temp-mail.org', 'getnada.com', 'mohmal.com'
];

// game id -> lock time (race start, UTC). Must match `lock_utc` in
// data/pickem/<game>.json; tests/test_pickem.py enforces it.
const GAMES = {
  'unbound-200-2027': '2027-06-05T11:00:00Z'
};

const CATEGORIES = ['women', 'men'];
const MAX_NAME = 40;
const MAX_PICK = 80;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === 'GET' && url.pathname === '/export') return handleExport(request, env, url);
    if (request.method === 'OPTIONS') return handleCORS(request, env);
    if (request.method !== 'POST') return new Response('Method not allowed', { status: 405 });

    const origin = request.headers.get('Origin');
    const allowedOrigins = (env.ALLOWED_ORIGINS || 'https://gravelgodcycling.com').split(',').map(o => o.trim());
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

    const lock = GAMES[data.game];
    if (!lock) return jsonResponse({ error: 'Unknown game' }, 400, origin);
    if (Date.now() >= Date.parse(lock)) {
      return jsonResponse({ error: 'Picks are locked.', locked: true }, 403, origin);
    }

    const entry = cleanEntry(data);
    const validation = validateEntry(entry);
    if (!validation.valid) return jsonResponse({ error: validation.error }, 400, origin);

    const key = entryKey(data.game, entry.email);
    let previous = null;
    try {
      const raw = await env.PICKEM.get(key);
      previous = raw ? JSON.parse(raw) : null;
    } catch (kvError) {
      console.error('KV read failed:', kvError);
      return jsonResponse({ error: 'Could not save. Please try again.' }, 500, origin);
    }

    const now = new Date().toISOString();
    const record = {
      game: data.game,
      email: entry.email,
      display_name: entry.display_name,
      picks: entry.picks,
      opt_in: entry.opt_in,
      submitted_at: now,
      first_submitted_at: previous ? (previous.first_submitted_at || previous.submitted_at) : now
    };

    try {
      // The full record rides in metadata when it fits (KV caps metadata at
      // 1024 bytes) so /export reads it from list() without one get per entry.
      const value = JSON.stringify(record);
      // Byte length, not string length: accented names take 2+ bytes each.
      const metadata = new TextEncoder().encode(value).length <= 1000 ? record : { submitted_at: now };
      await env.PICKEM.put(key, value, { metadata });
    } catch (kvError) {
      console.error('KV write failed:', kvError);
      return jsonResponse({ error: 'Could not save. Please try again.' }, 500, origin);
    }

    console.log('Pick saved:', { game: data.game, replaced: Boolean(previous) });
    return jsonResponse({ success: true, replaced: Boolean(previous), locks_at: lock }, 200, origin);
  }
};

// --- Validation ---

function cleanEntry(data) {
  const picks = {};
  for (const cat of CATEGORIES) {
    const list = Array.isArray(data.picks?.[cat]) ? data.picks[cat] : [];
    picks[cat] = [0, 1, 2].map(i => String(list[i] ?? '').replace(/\s+/g, ' ').trim().substring(0, MAX_PICK));
  }
  return {
    email: String(data.email ?? '').substring(0, 254).toLowerCase().trim(),
    display_name: String(data.display_name ?? '').replace(/\s+/g, ' ').trim().substring(0, MAX_NAME),
    opt_in: data.opt_in === true,
    picks
  };
}

function validateEntry(entry) {
  if (!entry.email) return { valid: false, error: 'Missing: email' };
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(entry.email)) return { valid: false, error: 'Invalid email format' };
  const emailDomain = entry.email.split('@')[1];
  if (DISPOSABLE_DOMAINS.includes(emailDomain)) return { valid: false, error: 'Please use a non-disposable email' };
  if (!entry.display_name) return { valid: false, error: 'Missing: display name' };
  if (entry.display_name.includes('@')) return { valid: false, error: 'Display name cannot be an email' };
  for (const cat of CATEGORIES) {
    const picks = entry.picks[cat];
    if (picks.some(p => !p)) return { valid: false, error: `Pick 1st, 2nd and 3rd for the ${cat}'s podium.` };
    const keys = picks.map(p => p.toLowerCase());
    if (new Set(keys).size !== keys.length) return { valid: false, error: `Same rider twice in the ${cat}'s podium.` };
  }
  return { valid: true };
}

function entryKey(game, email) {
  return `entry:${game}:${email}`;
}

// --- Export ---

async function handleExport(request, env, url) {
  const auth = request.headers.get('Authorization') || '';
  if (!env.EXPORT_TOKEN || !timingSafeEqual(auth, `Bearer ${env.EXPORT_TOKEN}`)) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401, headers: { 'Content-Type': 'application/json' }
    });
  }
  const game = url.searchParams.get('game') || Object.keys(GAMES)[0];
  if (!GAMES[game]) {
    return new Response(JSON.stringify({ error: 'Unknown game' }), {
      status: 400, headers: { 'Content-Type': 'application/json' }
    });
  }
  const entries = [];
  let cursor;
  do {
    const page = await env.PICKEM.list({ prefix: `entry:${game}:`, cursor });
    for (const k of page.keys) {
      if (k.metadata && k.metadata.picks) {
        entries.push(k.metadata);
        continue;
      }
      const raw = await env.PICKEM.get(k.name);
      if (raw) entries.push(JSON.parse(raw));
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  entries.sort((a, b) => a.submitted_at.localeCompare(b.submitted_at));
  return new Response(JSON.stringify({
    game,
    lock_utc: GAMES[game],
    exported_at: new Date().toISOString(),
    count: entries.length,
    opt_in_count: entries.filter(e => e.opt_in).length,
    entries
  }, null, 2), { status: 200, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
}

function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// --- CORS + Response Helpers ---

function handleCORS(request, env) {
  const origin = request.headers.get('Origin');
  const allowedOrigins = (env.ALLOWED_ORIGINS || 'https://gravelgodcycling.com').split(',').map(o => o.trim());
  const allowOrigin = allowedOrigins.includes(origin) ? origin : '';
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
