// Private aggregate reporting. Raw email addresses never enter persistent storage.
const ESSAYS = [
  {key:'sweet-spot',title:"Sweet Spot Isn't that Sweet",url:'https://gravelgodcycling.substack.com/p/sweet-spot-isnt-that-sweet'},
  {key:'unbound',title:'Unbound Two Hun..I Mean Five Point Four Miles',url:'https://gravelgodcycling.substack.com/p/unbound-two-huni-mean-five-point'},
  {key:'kids',title:'I Lied - Having Kids Makes You Slow',url:'https://gravelgodcycling.substack.com/p/i-lied-having-kids-makes-you-slow'},
];
const encoder = new TextEncoder();
const now = () => Math.floor(Date.now()/1000);
const json = (data,status=200) => Response.json(data,{status,headers:{'Cache-Control':'no-store','X-Robots-Tag':'noindex'}});

async function hash(value, secret) {
  const key = await crypto.subtle.importKey('raw',encoder.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']);
  return Array.from(new Uint8Array(await crypto.subtle.sign('HMAC',key,encoder.encode(value))),b=>b.toString(16).padStart(2,'0')).join('');
}
async function authenticated(request, env) {
  if (!env.INGEST_SECRET || env.INGEST_SECRET.length < 32) return false;
  // Compare fixed-size digests, with no early-return based on a shared prefix.
  const actual = await hash(request.headers.get('Authorization') || '',env.INGEST_SECRET);
  const expected = await hash(`Bearer ${env.INGEST_SECRET}`,env.INGEST_SECRET);
  let difference = 0;
  for(let i=0;i<expected.length;i++) difference |= actual.charCodeAt(i)^expected.charCodeAt(i);
  return difference === 0;
}
function isTest(email) {
  return email === 'gravelgodcoaching@gmail.com' || /^gravelgodcoaching\+newsletter-[^@]+@gmail\.com$/.test(email);
}
function emailAddress(value) {
  const address = String(value || '').trim().toLowerCase();
  return address.length <= 254 && /^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/.test(address) ? address : null;
}
function verifiedNotification(message) {
  if (!/^(?:Substack\s*<)?no-reply@substack\.com>?$/i.test(String(message.from || '').trim())) return null;
  if (!/^New (?:free|paid) subscriber to Slow, Mid, 38s!$/.test(message.subject || '')) return null;
  if (!/^mx\.google\.com\s*;/i.test(message.auth_results || '')) return null;
  const auth = message.auth_results || '';
  if (!/\bdmarc=pass\b[^;]*\bheader\.from=substack\.com(?:\s|;|$)/i.test(auth)
      && !/\bdkim=pass\b[^;]*\bheader\.i=@(?:[a-z0-9-]+\.)?substack\.com(?:\s|;|$)/i.test(auth)) return null;
  if (!/^[a-f0-9]{8,40}$/i.test(message.id || '')) return null;
  const confirmedAt = Math.floor(Date.parse(message.date)/1000);
  if (!Number.isFinite(confirmedAt) || confirmedAt > now()+300 || confirmedAt < now()-86400*366) return null;
  const match = String(message.body || '').slice(0,18000).match(/\bEmail:\s*([^\s<>]+@[^\s<>]+)/i);
  const email = emailAddress(match?.[1]);
  return email ? {email,confirmedAt} : null;
}
async function attribute(db, emailHash) {
  // Existing subscribers and attempts after confirmation must never be credited.
  await db.prepare(`UPDATE subscribers SET article = (
    SELECT article FROM attempts WHERE email_hash = subscribers.email_hash
      AND accepted = 1 AND attempted_at <= subscribers.confirmed_at
      AND attempted_at >= subscribers.confirmed_at - 2592000
  ) WHERE email_hash = ? AND source = 'notification' AND article IS NULL`).bind(emailHash).run();
}
async function confirmations(data, env) {
  if (!Array.isArray(data.messages) || data.messages.length > 100) return json({error:'Invalid message batch'},400);
  let accepted = 0, rejected = 0;
  for(const message of data.messages) {
    const verified = verifiedNotification(message);
    if (!verified) { rejected++; continue; }
    const emailHash = await hash(verified.email,env.EMAIL_HASH_KEY);
    // INSERT OR IGNORE and a unique email identity make overlapping bridge runs safe.
    await env.DB.batch([
      env.DB.prepare('INSERT OR IGNORE INTO receipts(message_id,received_at) VALUES(?,?)').bind(message.id,now()),
      env.DB.prepare('INSERT OR IGNORE INTO subscribers(email_hash,confirmed_at,source,is_test) VALUES(?,?,?,?)')
        .bind(emailHash,verified.confirmedAt,'notification',Number(isTest(verified.email))),
    ]);
    await attribute(env.DB,emailHash);
    accepted++;
  }
  await env.DB.prepare('INSERT OR REPLACE INTO health(key,value) VALUES(?,?)').bind('last_sync',String(now())).run();
  await env.DB.prepare('INSERT OR REPLACE INTO health(key,value) VALUES(?,?)').bind('sync_rejected',String(rejected)).run();
  return json({accepted,rejected});
}
async function baseline(data,env) {
  if (!Array.isArray(data.subscribers) || data.subscribers.length > 500) return json({error:'Invalid baseline'},400);
  for(const row of data.subscribers) {
    const email = emailAddress(row.email);
    const confirmedAt = Math.floor(Date.parse(row.confirmed_at)/1000);
    if (!email || !Number.isFinite(confirmedAt) || confirmedAt > now()) return json({error:'Invalid baseline row'},400);
    const emailHash = await hash(email,env.EMAIL_HASH_KEY);
    await env.DB.prepare('INSERT OR IGNORE INTO subscribers(email_hash,confirmed_at,source,is_test) VALUES(?,?,?,?)')
      .bind(emailHash,confirmedAt,row.source === 'gravelgodcycling.com' ? 'historical_website' : 'historical_other',Number(isTest(email))).run();
  }
  return json({imported:data.subscribers.length});
}
async function click(data,env) {
  if (!ESSAYS.some(e=>e.key === data.essay) || (data.visitor && !/^[a-f0-9-]{36}$/i.test(data.visitor))) return json({error:'Invalid click'},400);
  if (/bot|crawler|spider|preview|scanner|proofpoint|barracuda|mimecast|safelinks|headless/i.test(data.user_agent || '')
      || /prefetch|prerender|preview/i.test(data.purpose || '') || !(data.user_agent || '').trim()) return json({recorded:false});
  await env.DB.prepare('INSERT INTO click_totals(essay,day,is_test) VALUES(?,?,?) ON CONFLICT(essay,day,is_test) DO UPDATE SET clicks=clicks+1')
    .bind(data.essay,Math.floor(now()/86400)*86400,Number(data.is_test === true)).run();
  if (!data.visitor) return json({recorded:true});
  const visitorHash = await hash(data.visitor,env.EMAIL_HASH_KEY);
  // One reader browser per essay in each UTC month. No raw IP or UA is stored.
  const month = new Date().toISOString().slice(0,7);
  await env.DB.prepare('INSERT OR IGNORE INTO clicks(essay,visitor_hash,clicked_at,is_test) VALUES(?,?,?,?)')
    .bind(data.essay,`${month}:${visitorHash}`,now(),Number(data.is_test === true)).run();
  return json({recorded:true});
}
async function report(url,env) {
  const days = Math.max(1,Math.min(366,Number(url.searchParams.get('days')) || 30));
  const tests = url.searchParams.get('tests') === '1';
  const since = Math.floor(now()/86400)*86400-(days-1)*86400;
  const predicate = tests ? '1=1' : 'is_test=0';
  const total = await env.DB.prepare(`SELECT COUNT(*) AS confirmed, SUM(CASE WHEN article IS NULL THEN 1 ELSE 0 END) AS unattributed FROM subscribers WHERE confirmed_at >= ? AND ${predicate}`).bind(since).first();
  const articles = await env.DB.prepare(`SELECT article,COUNT(*) AS confirmed FROM subscribers WHERE confirmed_at >= ? AND article IS NOT NULL AND ${predicate} GROUP BY article ORDER BY confirmed DESC,article`).bind(since).all();
  const clicks = await env.DB.prepare(`SELECT essay,COUNT(DISTINCT substr(visitor_hash,9)) AS readers FROM clicks WHERE clicked_at >= ? AND ${predicate} GROUP BY essay`).bind(since).all();
  const clickTotals = await env.DB.prepare(`SELECT essay,SUM(clicks) AS clicks FROM click_totals WHERE day >= ? AND ${predicate} GROUP BY essay`).bind(since).all();
  const health = await env.DB.prepare('SELECT value FROM health WHERE key = ?').bind('last_sync').first();
  const rejected = await env.DB.prepare('SELECT value FROM health WHERE key = ?').bind('sync_rejected').first();
  const historical = await env.DB.prepare(`SELECT COUNT(*) AS n FROM subscribers WHERE source='historical_website' AND ${predicate}`).first();
  return json({days,include_tests:tests,confirmed:total.confirmed || 0,unattributed:total.unattributed || 0,
    articles:articles.results,essays:ESSAYS.map(e=>({...e,readers:clicks.results.find(c=>c.essay === e.key)?.readers || 0,clicks:clickTotals.results.find(c=>c.essay === e.key)?.clicks || 0})),
    historical_website_unattributed:historical.n,last_sync:health ? Number(health.value) : null,sync_rejected:rejected ? Number(rejected.value) : 0,
    goals:{monthly_income_usd:3000,monthly_confirmed_subscribers:100},
    click_definition:'Clicks exclude known bots and prefetch. Distinct browsers are measured only with analytics consent; one reader may use multiple browsers. Undetected scanners may remain. These are not delivered-email click rates.'});
}
async function boundedBody(request, limit) {
  if (Number(request.headers.get('Content-Length')) > limit) throw new RangeError('Body too large');
  if (!request.body) return '';
  const reader = request.body.getReader();
  const decoder = new TextDecoder();
  let length = 0, text = '';
  while (true) {
    const {done,value} = await reader.read();
    if (done) break;
    length += value.byteLength;
    if (length > limit) { await reader.cancel(); throw new RangeError('Body too large'); }
    text += decoder.decode(value,{stream:true});
  }
  return text + decoder.decode();
}
async function capture(request,env) {
  const origin = request.headers.get('Origin');
  const isForm = request.headers.get('Content-Type')?.startsWith('application/x-www-form-urlencoded');
  const origins = ['https://gravelgodcycling.com','https://www.gravelgodcycling.com'];
  if (env.ALLOW_LOCAL_TEST === 'true') origins.push('http://127.0.0.1:42087');
  const respond = (body,status=200) => {
    if (isForm && body.continue_url) return new Response(null,{status:303,headers:{Location:body.continue_url,'Cache-Control':'no-store','Referrer-Policy':'no-referrer'}});
    return Response.json(body,{status,headers:{'Access-Control-Allow-Origin':origin,'Vary':'Origin','Cache-Control':'no-store'}});
  };
  if (!origins.includes(origin)) return json({error:'Forbidden'},403);
  if (request.method === 'OPTIONS') return new Response(null,{status:204,headers:{'Access-Control-Allow-Origin':origin,'Access-Control-Allow-Methods':'POST','Access-Control-Allow-Headers':'Content-Type','Vary':'Origin'}});
  if (request.method !== 'POST') return respond({error:'Method not allowed'},405);
  if (env.CAPTURE_ENABLED !== 'true') return respond({error:'Use the Substack signup below.'},503);
  let data;
  try {
    const raw = await boundedBody(request,4096);
    data = isForm ? Object.fromEntries(new URLSearchParams(raw)) : JSON.parse(raw);
  }
  catch { return respond({error:'Invalid submission'},400); }
  const email = emailAddress(data?.email);
  const article = String(data?.article || '');
  if (!email || data.website) return respond({error:'Invalid submission'},400);
  const destination = new URL('https://gravelgodcycling.substack.com/subscribe');
  destination.searchParams.set('email',email);
  if (!/^\/(?:articles\/)?[a-z0-9-]{1,160}\/$/.test(article)) {
    return respond({pending:false,continue_url:destination.href,error:'Missing article'},400);
  }
  try {
  const emailHash = await hash(email,env.EMAIL_HASH_KEY);
  const ip = request.headers.get('CF-Connecting-IP') || 'local';
  const bucket = await hash(`${Math.floor(now()/3600)}:${ip}`,env.EMAIL_HASH_KEY);
  await env.DB.prepare('DELETE FROM rate_buckets WHERE created_at < ?').bind(now()-86400).run();
  await env.DB.prepare('INSERT INTO rate_buckets(bucket,created_at) VALUES(?,?) ON CONFLICT(bucket) DO UPDATE SET requests=requests+1').bind(bucket,now()).run();
  const rate = await env.DB.prepare('SELECT requests FROM rate_buckets WHERE bucket=?').bind(bucket).first();
  if (rate.requests > 10) return respond({pending:false,continue_url:destination.href,error:'Attribution rate limited'},429);
  const existing = await env.DB.prepare('SELECT email_hash FROM subscribers WHERE email_hash=?').bind(emailHash).first();
  if (!existing) {
    await env.DB.prepare('INSERT INTO attempts(email_hash,article,attempted_at,accepted,is_test) VALUES(?,?,?,0,?) ON CONFLICT(email_hash) DO UPDATE SET article=excluded.article,attempted_at=excluded.attempted_at,accepted=0')
      .bind(emailHash,article,now(),Number(isTest(email))).run();
  }
  if (!existing) {
    await env.DB.prepare('UPDATE attempts SET accepted=1 WHERE email_hash=?').bind(emailHash).run();
    await attribute(env.DB,emailHash);
  }
  // Only a pending handoff. Substack's own form owns consent and subscription.
  return respond({pending:true,continue_url:destination.href});
  } catch {
    console.error(JSON.stringify({event:'newsletter_capture_failed'}));
    return respond({pending:false,continue_url:destination.href,error:'Attribution unavailable'},503);
  }
}
export default {
  async fetch(request,env) {
    const url = new URL(request.url);
    if (url.pathname === '/health') return json({ok:true});
    if (url.pathname === '/capture') {
      try { return await capture(request,env); }
      catch { return json({error:'Please use the Substack signup below.'},503); }
    }
    if (!await authenticated(request,env)) return json({error:'Unauthorized'},401);
    try {
      if (url.pathname === '/report' && request.method === 'GET') return await report(url,env);
      if (request.method !== 'POST') return json({error:'Method not allowed'},405);
      const body = await boundedBody(request,2000000);
      let data;
      try { data = JSON.parse(body); } catch { return json({error:'Invalid JSON'},400); }
      if (!data || typeof data !== 'object') return json({error:'Invalid payload'},400);
      if (url.pathname === '/confirm') return await confirmations(data,env);
      if (url.pathname === '/baseline') return await baseline(data,env);
      if (url.pathname === '/click') return await click(data,env);
      return json({error:'Not found'},404);
    } catch {
      // Do not log bodies, email addresses, authorization headers or provider tokens.
      console.error(JSON.stringify({event:'newsletter_attribution_failed',path:url.pathname}));
      return json({error:'Attribution unavailable'},503);
    }
  },
};
