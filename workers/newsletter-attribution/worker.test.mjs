import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import worker from './worker.js';

// Run real SQLite SQL behind the D1 prepared-statement contract.
function database() {
  const sqlite = new DatabaseSync(':memory:');
  sqlite.exec(readFileSync(new URL('./migrations/0001_attribution.sql', import.meta.url), 'utf8'));
  sqlite.exec(readFileSync(new URL('./migrations/0002_rate_limits.sql', import.meta.url), 'utf8'));
  sqlite.exec(readFileSync(new URL('./migrations/0003_click_totals.sql', import.meta.url), 'utf8'));
  return {
    prepare(sql) {
      let params = [];
      return {
        bind(...values) { params = values; return this; },
        async run() { const r = sqlite.prepare(sql).run(...params); return {success:true,meta:{changes:r.changes}}; },
        async first() { return sqlite.prepare(sql).get(...params) || null; },
        async all() { return {results:sqlite.prepare(sql).all(...params)}; },
      };
    },
    async batch(statements) { return Promise.all(statements.map(s => s.run())); },
  };
}
function setup() {
  const env = {DB:database(),INGEST_SECRET:'a'.repeat(48),EMAIL_HASH_KEY:'b'.repeat(48),CAPTURE_ENABLED:'true'};
  const call = (path, body, auth = true, method = body === undefined ? 'GET' : 'POST') => worker.fetch(new Request(`https://newsletter.example${path}`, {
    method,
    headers:{'Content-Type':'application/json', ...(auth ? {Authorization:`Bearer ${env.INGEST_SECRET}`} : {}),Origin:'https://gravelgodcycling.com'},
    ...(body === undefined ? {} : {body:JSON.stringify(body)}),
  }), env);
  return {env,call};
}
const email = 'reader@example.com';
function notification(overrides = {}) {
  return {id:'abc123def456',from:'Substack <no-reply@substack.com>',subject:'New free subscriber to Slow, Mid, 38s!',date:new Date().toISOString(),auth_results:'mx.google.com; dmarc=pass header.from=substack.com',body:`Email: ${email}\nSource: Direct`,...overrides};
}

test('authenticated publisher confirmations are counted once; unauthenticated requests are refused', async () => {
  const {call} = setup();
  assert.equal((await call('/confirm',{messages:[notification()]},false)).status,401);
  assert.equal((await call('/confirm',{messages:[notification()]})).status,200);
  assert.equal((await call('/confirm',{messages:[notification()]})).status,200);
  const report = await (await call('/report')).json();
  assert.equal(report.confirmed,1);
  assert.equal(report.unattributed,1);
});

test('forged senders or failed authentication cannot create subscribers', async () => {
  const {call} = setup();
  await call('/confirm',{messages:[notification({auth_results:'dmarc=fail header.from=substack.com'})]});
  await call('/confirm',{messages:[notification({id:'abc123def457',from:'Attacker <no-reply@evil.example>'})]});
  assert.equal((await (await call('/report')).json()).confirmed,0);
});

test('welcome clicks deduplicate each browser per essay and reject bots/prefetch', async () => {
  const {call} = setup();
  const click = {essay:'sweet-spot',visitor:'ac21b1bc-36c1-4be0-b7d6-d421d83e9131',user_agent:'Mozilla/5.0',purpose:''};
  await call('/click',click);
  await call('/click',click);
  await call('/click',{...click,essay:'unbound'});
  await call('/click',{...click,essay:'kids',purpose:'prefetch'});
  await call('/click',{...click,essay:'kids',user_agent:'Googlebot'});
  const report = await (await call('/report')).json();
  assert.deepEqual(report.essays.map(e=>[e.key,e.readers]),[['sweet-spot',1],['unbound',1],['kids',0]]);
  assert.equal(report.essays[0].clicks,2);
  assert.equal((await call('/click',{...click,essay:'https://evil.example'})).status,400);
});

test('anonymous welcome clicks count as clicks without creating a browser identity',async()=>{
  const {call}=setup();
  await call('/click',{essay:'kids',visitor:'',user_agent:'Mozilla/5.0'});
  const report=await(await call('/report')).json();
  assert.equal(report.essays[2].clicks,1);
  assert.equal(report.essays[2].readers,0);
});

test('test aliases and test browser clicks are excluded by default', async () => {
  const {call} = setup();
  await call('/confirm',{messages:[notification({body:'Email: gravelgodcoaching+newsletter-attribution-test-20261028@gmail.com\nSource: Embed'})]});
  await call('/click',{essay:'kids',visitor:'ac21b1bc-36c1-4be0-b7d6-d421d83e9131',user_agent:'Mozilla/5.0',is_test:true});
  assert.equal((await (await call('/report')).json()).confirmed,0);
  const withTests = await (await call('/report?tests=1')).json();
  assert.equal(withTests.confirmed,1);
  assert.equal(withTests.essays[2].readers,1);
});

test('an accepted website attempt is pending until a verified confirmation; existing subscribers stay unattributed', async () => {
  const {env,call} = setup();
  const body = {email,article:'/sweet-spot-isnt-that-sweet/',website:''};
  const handoff = await call('/capture',body,false);
  assert.equal(handoff.status,200);
  assert.deepEqual(await handoff.json(),{pending:true,continue_url:'https://gravelgodcycling.substack.com/subscribe?email=reader%40example.com'});
  assert.equal((await (await call('/report')).json()).confirmed,0);
  await call('/confirm',{messages:[notification()]});
  const report = await (await call('/report')).json();
  assert.equal(report.confirmed,1);
  assert.equal(report.articles[0].article,body.article);
  await call('/capture',{...body,article:'/articles/something-else/'},false);
  assert.equal((await (await call('/report')).json()).articles[0].article,body.article);
});

test('failed storage and honeypots cannot claim a successful handoff or create an article attribution', async () => {
  const {env,call} = setup();
  const db = env.DB;
  env.DB = {prepare(){throw new Error('Unavailable');}};
  assert.equal((await call('/capture',{email,article:'/articles/essay/',website:''},false)).status,503);
  env.DB = db;
  await call('/confirm',{messages:[notification()]});
  assert.equal((await (await call('/report')).json()).articles.length,0);
  assert.equal((await call('/capture',{email,article:'/articles/essay/',website:'bot'},false)).status,400);
});

test('ordinary HTML forms redirect to the native email-prefilled signup; storage failure still lets the reader subscribe', async () => {
  const {env} = setup();
  const request = () => new Request('https://newsletter.example/capture', {method:'POST',
    headers:{Origin:'https://gravelgodcycling.com','Content-Type':'application/x-www-form-urlencoded'},
    body:new URLSearchParams({email:'reader+test@example.com',article:'/articles/essay/',website:''})});
  const response = await worker.fetch(request(),env);
  assert.equal(response.status,303);
  assert.equal(new URL(response.headers.get('Location')).searchParams.get('email'),'reader+test@example.com');
  env.DB={prepare(){throw new Error('Unavailable');}};
  const fallback = await worker.fetch(request(),env);
  assert.equal(fallback.status,303);
  assert.equal(new URL(fallback.headers.get('Location')).hostname,'gravelgodcycling.substack.com');
});

test('starting export records cannot be presented as newly verified confirmations or credited again',async()=>{
  const {call}=setup();
  await call('/baseline',{subscribers:[{email,confirmed_at:new Date().toISOString(),source:'gravelgodcycling.com'}]});
  await call('/capture',{email,article:'/articles/sweet-spot-training-cycling/',website:''},false);
  await call('/confirm',{messages:[notification()]});
  const report=await(await call('/report')).json();
  assert.equal(report.confirmed,0);
  assert.equal(report.starting_export_in_period,1);
  assert.equal(report.articles.length,0);
  assert.equal(report.historical_website_unattributed,1);
});
