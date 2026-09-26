import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import test from 'node:test';
import worker from '../workers/course-access/worker.js';

const secret = 'test-course-webhook-secret';

function signedRequest(session) {
  const body = JSON.stringify({ type: 'checkout.session.completed', data: { object: session } });
  const timestamp = Math.floor(Date.now() / 1000);
  const signature = createHmac('sha256', secret).update(`${timestamp}.${body}`).digest('hex');
  return new Request('https://course-access.example/webhook', {
    method: 'POST',
    headers: { 'stripe-signature': `t=${timestamp},v1=${signature}` },
    body
  });
}

function mockDb() {
  const users = new Map();
  const enrollments = [];
  return {
    users,
    enrollments,
    prepare(sql) {
      return {
        bind(...args) {
          return {
            async first() {
              if (sql.startsWith('SELECT * FROM users WHERE email')) return users.get(args[0]) ?? null;
              throw new Error(`Unexpected query: ${sql}`);
            },
            async run() {
              if (sql.startsWith('INSERT OR IGNORE INTO users')) {
                users.set(args[0], { id: users.size + 1, email: args[0] });
              } else if (sql.startsWith('INSERT OR IGNORE INTO enrollments')) {
                enrollments.push(args);
              } else {
                throw new Error(`Unexpected query: ${sql}`);
              }
            }
          };
        }
      };
    }
  };
}

test('unrelated Stripe checkout is acknowledged without an enrollment', async () => {
  const db = mockDb();
  const response = await worker.fetch(signedRequest({
    id: 'cs_training_plan',
    customer_email: 'buyer@example.com',
    metadata: { product_type: 'training_plan' },
    success_url: 'https://gravelgodcycling.com/training-plans/success/'
  }), { DB: db, STRIPE_WEBHOOK_SECRET: secret });
  assert.equal(response.status, 200);
  assert.equal((await response.json()).ignored, true);
  assert.equal(db.enrollments.length, 0);
});

test('current $49 Dirt Craft payment link grants access without metadata', async () => {
  const db = mockDb();
  const response = await worker.fetch(signedRequest({
    id: 'cs_dirt_craft',
    payment_link: 'plink_1TvqSNLoaHDbEqSqNE5BwdRl',
    customer_details: { email: 'Buyer@Example.com' },
    amount_total: 4900,
    currency: 'usd',
    metadata: {}
  }), { DB: db, STRIPE_WEBHOOK_SECRET: secret });
  assert.equal(response.status, 200);
  assert.equal((await response.json()).access_granted, true);
  assert.deepEqual(db.enrollments[0], [1, 'dirt-craft', 'cs_dirt_craft', 4900, 'usd']);
});

test('explicit bundle metadata grants only recognized courses', async () => {
  const db = mockDb();
  const response = await worker.fetch(signedRequest({
    id: 'cs_bundle',
    customer_email: 'buyer@example.com',
    metadata: { course_id: 'dirt-craft,gravel-hydration-mastery' },
    amount_total: 5900,
    currency: 'usd'
  }), { DB: db, STRIPE_WEBHOOK_SECRET: secret });
  assert.equal(response.status, 200);
  assert.deepEqual(db.enrollments.map(row => row[1]), ['dirt-craft', 'gravel-hydration-mastery']);
});
