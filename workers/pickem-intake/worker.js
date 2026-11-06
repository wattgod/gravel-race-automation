/**
 * Cloudflare Worker: Pick'em Intake
 *
 * POST /        Saves one entry per email per game to KV. Resubmitting before
 *               the lock replaces the earlier picks. After the lock: 403.
 *               An opted-in save is also sent to Mission Control (the email
 *               list of record); KV stays the record if that call fails.
 * GET  /export  Every entry for a game (Authorization: Bearer EXPORT_TOKEN),
 *               for scoring, with counts per racing answer and unsynced.
 * POST /resync  Same token: resends opted-in entries Mission Control missed.
 */

const DISPOSABLE_DOMAINS = [
  '10minutemail.com', 'guerrillamail.com', 'mailinator.com', 'tempmail.com',
  'throwaway.email', 'fakeinbox.com', 'trashmail.com', 'maildrop.cc',
  'yopmail.com', 'temp-mail.org', 'getnada.com', 'mohmal.com'
];

// game id -> lock time (race start, UTC) and the racing answers. Must match
// `lock_utc` and `racing` in data/pickem/<game>.json, and each race_slug and
// race_name must match race-data/; tests/test_pickem.py enforces all three.
// An answer with a race means "racing that distance": Mission Control gets
// its race_slug (countdown + debrief). null answers send no race.
const GAMES = {
  'unbound-200-2027': {
    lock: '2027-06-05T11:00:00Z',
    racing: {
      xl: { race_slug: 'unbound-xl', race_name: 'Unbound Gravel XL' },
      '200': { race_slug: 'unbound-200', race_name: 'Unbound 200' },
      '100': { race_slug: 'unbound-100', race_name: 'Unbound Gravel 100' },
      lottery: null,
      no: null
    }
  }
};

const CATEGORIES = ['women', 'men'];
const MAX_NAME = 40;
const MAX_PICK = 80;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === 'GET' && url.pathname === '/export') return handleExport(request, env, url);
    if (request.method === 'POST' && url.pathname === '/resync') return handleResync(request, env, url);
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

    const game = Object.hasOwn(GAMES, data.game) ? GAMES[data.game] : null;
    if (!game) return jsonResponse({ error: 'Unknown game' }, 400, origin);
    const lock = game.lock;
    if (Date.now() >= Date.parse(lock)) {
      return jsonResponse({ error: 'Picks are locked.', locked: true }, 403, origin);
    }

    const entry = cleanEntry(data);
    const validation = validateEntry(entry, game);
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
      racing: entry.racing,
      opt_in: entry.opt_in,
      mc_synced: false,
      submitted_at: now,
      first_submitted_at: previous ? (previous.first_submitted_at || previous.submitted_at) : now
    };

    try {
      await putRecord(env, key, record);
    } catch (kvError) {
      console.error('KV write failed:', kvError);
      return jsonResponse({ error: 'Could not save. Please try again.' }, 500, origin);
    }

    // Saved first, so a Mission Control outage never costs an entry: it
    // stays mc_synced false and POST /resync sends it later.
    if (record.opt_in) await syncRecord(env, key, record);

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
    racing: String(data.racing ?? '').trim().toLowerCase().substring(0, 24),
    picks
  };
}

function validateEntry(entry, game) {
  if (!entry.email) return { valid: false, error: 'Missing: email' };
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(entry.email)) return { valid: false, error: 'Invalid email format' };
  const emailDomain = entry.email.split('@')[1];
  if (DISPOSABLE_DOMAINS.includes(emailDomain)) return { valid: false, error: 'Please use a non-disposable email' };
  if (!entry.display_name) return { valid: false, error: 'Missing: display name' };
  if (entry.display_name.includes('@')) return { valid: false, error: 'Display name cannot be an email' };
  if (!entry.racing || !Object.hasOwn(game.racing, entry.racing)) {
    return { valid: false, error: 'Answer the racing question.' };
  }
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

// --- KV ---

async function putRecord(env, key, record) {
  // The full record rides in metadata when it fits (KV caps metadata at
  // 1024 bytes) so /export reads it from list() without one get per entry.
  const value = JSON.stringify(record);
  // Byte length, not string length: accented names take 2+ bytes each.
  const metadata = new TextEncoder().encode(value).length <= 1000 ? record : { submitted_at: record.submitted_at };
  await env.PICKEM.put(key, value, { metadata });
}

async function listEntries(env, game) {
  const entries = [];
  let cursor;
  do {
    const page = await env.PICKEM.list({ prefix: `entry:${game}:`, cursor });
    for (const k of page.keys) {
      if (k.metadata && k.metadata.picks) {
        entries.push({ key: k.name, record: k.metadata });
        continue;
      }
      const raw = await env.PICKEM.get(k.name);
      if (raw) entries.push({ key: k.name, record: JSON.parse(raw) });
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return entries;
}

// --- Mission Control ---

// Same endpoint, auth and payload style as workers/fueling-lead-intake.
// No name: the leaderboard name is a handle, not what an email should
// greet them by.
async function notifyMissionControl(env, record) {
  if (!env.MC_WEBHOOK_URL) {
    console.error('Mission Control not notified: MC_WEBHOOK_URL is unset');
    return false;
  }
  const race = GAMES[record.game]?.racing?.[record.racing] || null;
  const payload = {
    email: record.email,
    name: '',
    brand: 'gravelgod',
    source: 'pickem',
    game: record.game,
    racing: record.racing
  };
  if (race) {
    payload.race_slug = race.race_slug;
    payload.race_name = race.race_name;
  }
  try {
    const resp = await fetch(`${env.MC_WEBHOOK_URL}/webhooks/subscriber`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${env.MC_WEBHOOK_SECRET || ''}`
      },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(8000)
    });
    console.log('Mission Control notified:', record.game, resp.status);
    if (!resp.ok) console.error('Mission Control returned', resp.status);
    return resp.ok;
  } catch (error) {
    console.error('Mission Control webhook error:', error);
    return false;
  }
}

async function syncRecord(env, key, record) {
  const ok = await notifyMissionControl(env, record);
  if (!ok) return false;
  try {
    await putRecord(env, key, { ...record, mc_synced: true });
  } catch (kvError) {
    // Mission Control has it; a later /resync sends it again, which
    // Mission Control treats as the same contact.
    console.error('KV mc_synced write failed:', kvError);
  }
  return true;
}

// --- Export + resync ---

function authorized(request, env) {
  const auth = request.headers.get('Authorization') || '';
  return Boolean(env.EXPORT_TOKEN) && timingSafeEqual(auth, `Bearer ${env.EXPORT_TOKEN}`);
}

function adminError(error, status) {
  return new Response(JSON.stringify({ error }), {
    status, headers: { 'Content-Type': 'application/json' }
  });
}

function gameParam(url) {
  const game = url.searchParams.get('game') || Object.keys(GAMES)[0];
  return Object.hasOwn(GAMES, game) ? game : null;
}

const unsynced = (e) => e.opt_in && !e.mc_synced;

async function handleExport(request, env, url) {
  if (!authorized(request, env)) return adminError('Unauthorized', 401);
  const game = gameParam(url);
  if (!game) return adminError('Unknown game', 400);
  const entries = (await listEntries(env, game)).map(e => e.record);
  entries.sort((a, b) => a.submitted_at.localeCompare(b.submitted_at));
  const racing_counts = Object.fromEntries(Object.keys(GAMES[game].racing).map(a => [a, 0]));
  for (const e of entries) {
    if (Object.hasOwn(racing_counts, e.racing)) racing_counts[e.racing] += 1;
  }
  return new Response(JSON.stringify({
    game,
    lock_utc: GAMES[game].lock,
    exported_at: new Date().toISOString(),
    count: entries.length,
    opt_in_count: entries.filter(e => e.opt_in).length,
    unsynced_count: entries.filter(unsynced).length,
    racing_counts,
    entries
  }, null, 2), { status: 200, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
}

async function handleResync(request, env, url) {
  if (!authorized(request, env)) return adminError('Unauthorized', 401);
  const game = gameParam(url);
  if (!game) return adminError('Unknown game', 400);
  const pending = (await listEntries(env, game)).filter(e => unsynced(e.record));
  let synced = 0;
  for (const { key, record } of pending) {
    if (await syncRecord(env, key, record)) synced += 1;
  }
  return new Response(JSON.stringify({
    game, tried: pending.length, synced, still_unsynced: pending.length - synced
  }), { status: 200, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
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
