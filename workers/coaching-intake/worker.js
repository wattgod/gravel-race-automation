/**
 * Brand-aware coaching intake edge.
 *
 * Browser -> this Worker -> authenticated Railway onboarding case endpoint.
 * A form submission creates FIT_REVIEW only. Fit approval, evidence
 * verification, and payment handoff are separate authenticated backend steps;
 * checkout is never created from an untrusted browser flag.
 */

const BRAND_BY_HOST = {
  'gravelgodcycling.com': 'gravelgod',
  'www.gravelgodcycling.com': 'gravelgod',
  'roadielabs.com': 'roadielabs',
  'www.roadielabs.com': 'roadielabs',
  'xcskilabs.com': 'xcskilabs',
  'www.xcskilabs.com': 'xcskilabs',
};

const VALID_TIERS = new Set(['min', 'mid', 'max']);
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === '/__canary') {
      return handleCanary(request, env);
    }
    const origin = request.headers.get('Origin') || '';
    const brand = brandFromOrigin(origin);

    if (request.method === 'OPTIONS') {
      return brand
        ? new Response(null, { status: 204, headers: corsHeaders(origin) })
        : new Response('Forbidden', { status: 403 });
    }
    if (request.method !== 'POST') {
      return jsonResponse({ error: 'Method not allowed' }, 405, origin);
    }
    if (!brand) {
      return jsonResponse({ error: 'Forbidden' }, 403, origin);
    }
    if (!env.PIPELINE_URL || !env.COACHING_INTAKE_SECRET) {
      console.error(JSON.stringify({
        message: 'coaching_intake_configuration_missing',
      }));
      return jsonResponse({ error: 'Intake is temporarily unavailable' }, 503, origin);
    }

    let data;
    try {
      data = await request.json();
    } catch (_) {
      return jsonResponse({ error: 'Invalid request' }, 400, origin);
    }

    const name = String(data.name || '').trim();
    const email = String(data.email || '').trim().toLowerCase();
    const tier = String(data.tier || '').trim().toLowerCase();
    if (data.website) return jsonResponse({ error: 'Submission blocked' }, 400, origin);
    if (!name) return jsonResponse({ error: 'Name is required' }, 400, origin);
    if (!EMAIL_RE.test(email)) {
      return jsonResponse({ error: 'Valid email is required' }, 400, origin);
    }
    if (!VALID_TIERS.has(tier)) {
      return jsonResponse({ error: 'Select a coaching tier' }, 400, origin);
    }

    const requestedSubmissionId = String(data.submission_id || '').trim();
    const submissionId = UUID_RE.test(requestedSubmissionId)
      ? requestedSubmissionId
      : crypto.randomUUID();
    const questionnaire = { ...data };
    delete questionnaire.website;
    delete questionnaire.submission_id;

    let backend;
    try {
      backend = await fetch(`${env.PIPELINE_URL.replace(/\/$/, '')}/api/coaching-intakes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Coaching-Intake-Secret': env.COACHING_INTAKE_SECRET,
        },
        body: JSON.stringify({
          submission_id: submissionId,
          brand,
          tier,
          name,
          email,
          questionnaire,
        }),
      });
    } catch (error) {
      console.error(JSON.stringify({
        message: 'coaching_intake_backend_unavailable', brand,
      }));
      return jsonResponse({ error: 'Could not submit. Please try again.' }, 502, origin);
    }

    let result = {};
    try {
      result = await backend.json();
    } catch (_) {
      result = {};
    }
    if (!backend.ok) {
      console.error(JSON.stringify({
        message: 'coaching_intake_backend_rejected',
        brand,
        status: backend.status,
      }));
      return jsonResponse(
        { error: result.error || 'Could not submit. Please try again.' },
        backend.status >= 500 ? 502 : backend.status,
        origin,
      );
    }

    return jsonResponse({
      success: true,
      case_id: result.case_id || submissionId,
      state: result.state || 'FIT_REVIEW',
      receipt_sent: Boolean(result.receipt_sent),
      duplicate: Boolean(result.duplicate),
    }, backend.status === 200 ? 200 : 201, origin);
  },
};

async function handleCanary(request, env) {
  if (request.method !== 'POST') {
    return jsonResponse({ error: 'Method not allowed' }, 405, '');
  }
  if (!env.PIPELINE_URL || !env.COACHING_INTAKE_SECRET ||
      !env.COACHING_CANARY_SECRET) {
    console.error(JSON.stringify({
      message: 'coaching_canary_configuration_missing',
    }));
    return jsonResponse({ error: 'Canary is not configured' }, 503, '');
  }
  const supplied = request.headers.get('X-Coaching-Canary-Secret') || '';
  if (!(await secretsMatch(supplied, env.COACHING_CANARY_SECRET))) {
    return jsonResponse({ error: 'Unauthorized' }, 401, '');
  }

  let backend;
  try {
    backend = await fetch(
      `${env.PIPELINE_URL.replace(/\/$/, '')}/api/coaching-canary`,
      {
        method: 'POST',
        headers: {
          'X-Coaching-Intake-Secret': env.COACHING_INTAKE_SECRET,
        },
      },
    );
  } catch (_) {
    console.error(JSON.stringify({
      message: 'coaching_canary_backend_unavailable',
    }));
    return jsonResponse({
      schema: 'coaching_edge_canary/v1',
      status: 'failed',
      edge_reachable: true,
      error: 'Backend unavailable',
    }, 502, '');
  }

  let result = {};
  try {
    // The canary response is a bounded internal JSON contract, not an
    // arbitrary upstream payload.
    result = await backend.json();
  } catch (_) {
    result = { status: 'failed', error: 'Invalid backend response' };
  }
  const response = {
    ...result,
    schema: 'coaching_edge_canary/v1',
    edge_reachable: true,
    backend_status: backend.status,
  };
  const status = backend.ok && result.status === 'ok' ? 200 : 503;
  const log = {
    message: 'coaching_edge_canary',
    status: response.status || 'failed',
    backend_status: backend.status,
  };
  if (status === 200) console.log(JSON.stringify(log));
  else console.error(JSON.stringify(log));
  return jsonResponse(response, status, '');
}

async function secretsMatch(provided, expected) {
  const encoder = new TextEncoder();
  const [providedHash, expectedHash] = await Promise.all([
    crypto.subtle.digest('SHA-256', encoder.encode(provided)),
    crypto.subtle.digest('SHA-256', encoder.encode(expected)),
  ]);
  return crypto.subtle.timingSafeEqual(providedHash, expectedHash);
}

function brandFromOrigin(origin) {
  try {
    return BRAND_BY_HOST[new URL(origin).hostname.toLowerCase()] || '';
  } catch (_) {
    return '';
  }
}

function corsHeaders(origin) {
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Vary': 'Origin',
    'X-Content-Type-Options': 'nosniff',
  };
}

function jsonResponse(body, status, origin) {
  const headers = {
    'Content-Type': 'application/json',
    'X-Content-Type-Options': 'nosniff',
  };
  if (brandFromOrigin(origin)) Object.assign(headers, corsHeaders(origin));
  return new Response(JSON.stringify(body), {
    status,
    headers,
  });
}
