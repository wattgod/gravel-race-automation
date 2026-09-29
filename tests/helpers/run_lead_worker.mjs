// Runs the lead-intake worker once on the JSON request body read from stdin,
// with every outbound fetch captured instead of sent, and prints what the
// worker answered and what it tried to send. The exit survey chain test
// (mission_control/tests/test_athlete_exit.py) feeds it the body the real page
// posted, then feeds what the worker forwarded into Mission Control.
import { readFileSync } from 'node:fs';

const workerPath = new URL('../../workers/fueling-lead-intake/worker.js', import.meta.url);
const workerSource = readFileSync(workerPath, 'utf8');
const { default: worker } = await import(
  `data:text/javascript;base64,${Buffer.from(workerSource).toString('base64')}`,
);

// stdout carries only the result; the worker's own logging goes to stderr
console.log = console.error;

const body = readFileSync(0, 'utf8');
const sent = [];
globalThis.fetch = async (url, options = {}) => {
  sent.push({ url: String(url), body: options.body ? JSON.parse(options.body) : null });
  return new Response(JSON.stringify({ status: 'ok', id: 'captured' }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
};

const response = await worker.fetch(new Request('https://fueling-lead-intake.example.test', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', Origin: 'https://gravelgodcycling.com' },
  body,
}), {
  ALLOWED_ORIGINS: 'https://gravelgodcycling.com',
  MC_WEBHOOK_URL: 'https://mission-control.example.test',
  MC_WEBHOOK_SECRET: 'test-secret',
  RESEND_API_KEY: 'test-resend-key',
  NOTIFICATION_EMAIL: 'coach@example.com',
});

process.stdout.write(JSON.stringify({ status: response.status, response: await response.json(), sent }));
