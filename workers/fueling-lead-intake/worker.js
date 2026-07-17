/**
 * Cloudflare Worker: Lead Intake (All Email Capture Points)
 *
 * Multi-brand: serves gravelgodcycling.com (default), roadielabs.com, and
 * xcskilabs.com. The page sends `brand`; absent → gravelgod. Brand is
 * tagged on the SendGrid contact (env.SG_FIELD_BRAND), the Mission Control
 * payload, and the notification email subject/sender so road leads are
 * distinguishable in the shared list/inbox.
 *
 * Handles 10 capture sources:
 *   - exit_intent:        email only (race profile exit popup)
 *   - race_profile:       email + race context (prep kit CTA)
 *   - prep_kit_gate:      email + race context (content unlock)
 *   - race_quiz:          email + race context (quiz results gate)
 *   - quiz_shared:        email + race context (shared quiz results)
 *   - tire_guide:         email + race context (tire setup card CTA)
 *   - race_review:        email + race context + stars/review data (race profile review form)
 *   - state_hub:          email + state slug (state hub page subscribe)
 *   - date_reminder:      email + race slug + race date (race date reminder)
 *   - race_plan_ladder:   email + race context + tier (plan-ladder "notify me" form)
 *   - training_guide:     email + optional guide_chapter (guide end-of-chapter capture)
 *   - fueling_calculator: email + weight + race + fueling data (detected by weight_lbs, no source field)
 *
 * Every valid submission upserts the contact into SendGrid Marketing Contacts.
 * Notification emails only fire for fueling_calculator (contains actionable athlete data).
 */

const DISPOSABLE_DOMAINS = [
  '10minutemail.com', 'guerrillamail.com', 'mailinator.com', 'tempmail.com',
  'throwaway.email', 'fakeinbox.com', 'trashmail.com', 'maildrop.cc',
  'yopmail.com', 'temp-mail.org', 'getnada.com', 'mohmal.com'
];

const KNOWN_SOURCES = ['exit_intent', 'race_profile', 'prep_kit_gate', 'race_quiz', 'quiz_shared', 'tire_guide', 'race_review', 'state_hub', 'date_reminder', 'race_plan_ladder', 'training_guide'];

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

    // Honeypot check (all forms include this)
    if (data.website) {
      return jsonResponse({ error: 'Bot detected' }, 400, origin);
    }

    // Brand routing (multi-brand intake). Defaults to gravelgod for back-compat
    // with the gravel pages that don't send a brand field.
    const brand = (String(data.brand || 'gravelgod')).toLowerCase();
    data.brand = brand;

    // Detect source: fueling_calculator has weight_lbs but no source field
    const source = data.source || (data.weight_lbs ? 'fueling_calculator' : null);

    if (!source || (source !== 'fueling_calculator' && !KNOWN_SOURCES.includes(source))) {
      return jsonResponse({ error: 'Unknown source' }, 400, origin);
    }

    // Sanitize string inputs: truncate to sane lengths
    if (data.email) data.email = String(data.email).substring(0, 254);
    if (data.race_slug) data.race_slug = String(data.race_slug).substring(0, 100);
    if (data.race_name) data.race_name = String(data.race_name).substring(0, 200);
    if (data.guide_chapter) data.guide_chapter = String(data.guide_chapter).substring(0, 80);
    // Trail context (docs/specs/friend-first-sequences.md §4.2-4.3) — the
    // browser's localStorage breadcrumb of recently viewed races, forwarded
    // by any capture form so welcome-sequence branching works regardless of
    // where the visitor actually converts.
    if (Array.isArray(data.viewed_races)) {
      data.viewed_races = data.viewed_races
        .filter((r) => typeof r === 'string' && r)
        .slice(0, 5)
        .map((r) => r.substring(0, 60));
    } else {
      delete data.viewed_races;
    }

    // Validate based on source
    const validation = validateBySource(source, data);
    if (!validation.valid) {
      return jsonResponse({ error: validation.error }, 400, origin);
    }

    // Downstream work: SendGrid, webhook, notification email
    // Failures here are logged but don't affect the user response
    try {
      const promises = [];

      // Upsert to SendGrid Marketing Contacts (all sources)
      if (env.SENDGRID_API_KEY && env.SG_LIST_ID) {
        promises.push(upsertMarketingContact(env, data, source));
      }

      // Notify Mission Control for sequence enrollment (all sources)
      if (env.MC_WEBHOOK_URL) {
        promises.push(notifyMissionControl(env, data, source));
      }

      // Notification email only for fueling_calculator (has actionable athlete data)
      if (source === 'fueling_calculator') {
        const leadId = generateLeadId(data.email, data.race_slug);
        const lead = formatFuelingLead(data, leadId);

        if (env.COACHING_WEBHOOK_URL) {
          promises.push(sendToWebhook(env.COACHING_WEBHOOK_URL, lead));
        }
        if (env.SENDGRID_API_KEY && env.NOTIFICATION_EMAIL) {
          promises.push(sendNotificationEmail(env, lead));
        }
      }

      await Promise.allSettled(promises);
    } catch (downstreamError) {
      console.error('Downstream error (user unaffected):', downstreamError);
    }

    console.log('Lead captured:', { source, email: data.email, race_slug: data.race_slug || '' });

    return jsonResponse({ success: true, message: 'Your personalized plan is ready' }, 200, origin);
  }
};

// --- Brand helpers (multi-brand intake) ---

const BRAND_LABELS = { gravelgod: 'Gravel God', roadielabs: 'Roadie Labs', xcskilabs: 'XC Ski Labs' };
const BRAND_SENDERS = {
  gravelgod: { email: 'leads@gravelgodcycling.com', name: 'Gravel God Fueling' },
  roadielabs: { email: 'leads@gravelgodcycling.com', name: 'Roadie Labs Fueling' },
  xcskilabs: { email: 'leads@gravelgodcycling.com', name: 'XC Ski Labs Leads' },
};
function brandLabel(brand) { return BRAND_LABELS[brand] || 'Gravel God'; }
function brandSender(brand) { return BRAND_SENDERS[brand] || BRAND_SENDERS.gravelgod; }

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

function validateBySource(source, data) {
  // Email required for all sources
  if (!data.email) return { valid: false, error: 'Missing: email' };
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
    return { valid: false, error: 'Invalid email format' };
  }
  const emailDomain = data.email.split('@')[1].toLowerCase();
  if (DISPOSABLE_DOMAINS.includes(emailDomain)) {
    return { valid: false, error: 'Please use a non-disposable email' };
  }

  // Fueling calculator has additional requirements
  if (source === 'fueling_calculator') {
    if (!data.weight_lbs) return { valid: false, error: 'Missing: weight' };
    if (!data.race_slug) return { valid: false, error: 'Missing: race slug' };
    const weight = parseFloat(data.weight_lbs);
    if (isNaN(weight) || weight < 80 || weight > 400) {
      return { valid: false, error: 'Weight must be between 80-400 lbs' };
    }
  }

  // training_guide (guide end-of-chapter capture): email only, required
  // above for all sources. guide_chapter is optional context, already
  // truncated to 80 chars before validation runs.

  return { valid: true };
}

// --- SendGrid Marketing Contacts ---

async function upsertMarketingContact(env, data, source) {
  try {
    const customFields = {};
    if (env.SG_FIELD_LATEST_SOURCE) customFields[env.SG_FIELD_LATEST_SOURCE] = source;
    if (env.SG_FIELD_RACE_SLUG && data.race_slug) customFields[env.SG_FIELD_RACE_SLUG] = data.race_slug;
    if (env.SG_FIELD_RACE_NAME && data.race_name) customFields[env.SG_FIELD_RACE_NAME] = data.race_name;
    if (env.SG_FIELD_HAS_FUELING) customFields[env.SG_FIELD_HAS_FUELING] = source === 'fueling_calculator' ? 'yes' : 'no';
    if (env.SG_FIELD_BRAND && data.brand) customFields[env.SG_FIELD_BRAND] = data.brand;

    const contact = { email: data.email };
    if (Object.keys(customFields).length > 0) {
      contact.custom_fields = customFields;
    }

    const body = {
      list_ids: [env.SG_LIST_ID],
      contacts: [contact]
    };

    const resp = await fetch('https://api.sendgrid.com/v3/marketing/contacts', {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${env.SENDGRID_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    });

    console.log('SendGrid Marketing upsert:', resp.status, 'email:', data.email, 'source:', source);
  } catch (error) {
    console.error('SendGrid Marketing error:', error);
  }
}

// --- Fueling Calculator Lead Formatting ---

function generateLeadId(email, raceSlug) {
  const base = email.split('@')[0].toLowerCase().replace(/[^a-z0-9]/g, '-').substring(0, 15);
  const race = (raceSlug || 'unknown').substring(0, 15);
  return `fuel-${race}-${base}-${Date.now().toString(36)}`;
}

function formatFuelingLead(data, leadId) {
  const weightLbs = parseFloat(data.weight_lbs);
  const weightKg = Math.round(weightLbs * 0.453592);

  return {
    lead_id: leadId,
    timestamp: new Date().toISOString(),
    source: 'prep-kit-fueling-calculator',
    brand: data.brand || 'gravelgod',
    email: data.email,
    race_slug: data.race_slug,
    race_name: data.race_name || '',
    athlete: {
      weight_lbs: weightLbs,
      weight_kg: weightKg,
      height_ft: data.height_ft || null,
      height_in: data.height_in || null,
      age: data.age ? parseInt(data.age) : null,
      ftp: data.ftp ? parseFloat(data.ftp) : null,
    },
    fueling: {
      target_hours: data.target_hours ? parseFloat(data.target_hours) : null,
      personalized_rate: data.personalized_rate || null,
      total_carbs: data.total_carbs || null,
      fluid_target_ml_hr: data.fluid_target_ml_hr || null,
      sodium_mg_hr: data.sodium_mg_hr || null,
      sweat_tendency: data.sweat_tendency || null,
      fuel_format: data.fuel_format || null,
      cramp_history: data.cramp_history || null,
      climate_heat: data.climate_heat || null,
    }
  };
}

// --- Webhook ---

async function sendToWebhook(webhookUrl, lead) {
  try {
    await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(lead)
    });
  } catch (error) {
    console.error('Webhook error:', error);
  }
}

// --- Notification Email (fueling_calculator only) ---

async function sendNotificationEmail(env, lead) {
  const emailBody = formatEmailBody(lead);

  try {
    const sgResponse = await fetch('https://api.sendgrid.com/v3/mail/send', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.SENDGRID_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        personalizations: [{
          to: [{ email: env.NOTIFICATION_EMAIL }],
          subject: `[${brandLabel(lead.brand)}] Fueling Lead: ${(lead.race_name || lead.race_slug).substring(0, 60)} - ${lead.email}`
        }],
        from: brandSender(lead.brand),
        reply_to: { email: lead.email },
        content: [{ type: 'text/html', value: emailBody }]
      })
    });
    console.log('SendGrid notification:', sgResponse.status);
  } catch (error) {
    console.error('Email error:', error);
  }
}

function formatEmailBody(lead) {
  const ftp = lead.athlete.ftp ? `${esc(lead.athlete.ftp)}W` : '—';
  const height = lead.athlete.height_ft
    ? `${esc(lead.athlete.height_ft)}'${esc(lead.athlete.height_in || 0)}"`
    : '—';
  const rate = lead.fueling.personalized_rate
    ? `${esc(lead.fueling.personalized_rate)}g/hr`
    : '—';
  const total = lead.fueling.total_carbs
    ? `${esc(lead.fueling.total_carbs)}g`
    : '—';

  return `
<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: 'Courier New', monospace; background: #f5f5dc; padding: 20px; margin: 0; }
    .card { background: white; border: 3px solid #2c2c2c; padding: 24px; max-width: 580px; margin: 0 auto; }
    h1 { font-size: 16px; border-bottom: 3px solid #2c2c2c; padding-bottom: 8px; margin-top: 0; }
    h2 { font-size: 11px; color: #7d695d; margin-top: 16px; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.1em; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
    .row { display: flex; margin: 3px 0; font-size: 13px; }
    .label { width: 120px; color: #7d695d; flex-shrink: 0; }
    .value { font-weight: 600; color: #2c2c2c; }
    .highlight { background: #4ecdc4; padding: 2px 8px; color: #2c2c2c; font-weight: 700; }
    .footer { margin-top: 16px; padding-top: 10px; border-top: 2px solid #2c2c2c; font-size: 11px; color: #7d695d; }
  </style>
</head>
<body>
  <div class="card">
    <h1>&#9981; Fueling Calculator Lead</h1>
    <p style="margin: 0 0 10px; font-size: 12px;"><strong>ID:</strong> ${esc(lead.lead_id)}</p>

    <h2>Contact</h2>
    <div class="row"><span class="label">Email:</span><span class="value">${esc(lead.email)}</span></div>
    <div class="row"><span class="label">Race:</span><span class="value"><span class="highlight">${esc(lead.race_name || lead.race_slug)}</span></span></div>

    <h2>Athlete</h2>
    <div class="row"><span class="label">Weight:</span><span class="value">${esc(lead.athlete.weight_lbs)}lbs (${esc(lead.athlete.weight_kg)}kg)</span></div>
    <div class="row"><span class="label">Height:</span><span class="value">${height}</span></div>
    <div class="row"><span class="label">Age:</span><span class="value">${esc(lead.athlete.age) || '—'}</span></div>
    <div class="row"><span class="label">FTP:</span><span class="value">${ftp}</span></div>

    <h2>Fueling Results</h2>
    <div class="row"><span class="label">Target Hours:</span><span class="value">${esc(lead.fueling.target_hours) || '—'}</span></div>
    <div class="row"><span class="label">Carb Rate:</span><span class="value">${rate}</span></div>
    <div class="row"><span class="label">Total Carbs:</span><span class="value">${total}</span></div>

    <h2>Hydration</h2>
    <div class="row"><span class="label">Fluid Target:</span><span class="value">${lead.fueling.fluid_target_ml_hr ? esc(lead.fueling.fluid_target_ml_hr) + ' ml/hr' : '—'}</span></div>
    <div class="row"><span class="label">Sodium:</span><span class="value">${lead.fueling.sodium_mg_hr ? esc(lead.fueling.sodium_mg_hr) + ' mg/hr' : '—'}</span></div>
    <div class="row"><span class="label">Climate:</span><span class="value">${esc(lead.fueling.climate_heat) || '—'}</span></div>
    <div class="row"><span class="label">Sweat:</span><span class="value">${esc(lead.fueling.sweat_tendency) || '—'}</span></div>
    <div class="row"><span class="label">Fuel Format:</span><span class="value">${esc(lead.fueling.fuel_format) || '—'}</span></div>
    <div class="row"><span class="label">Cramping:</span><span class="value">${esc(lead.fueling.cramp_history) || '—'}</span></div>

    <div class="footer">
      <p>Brand: ${esc(brandLabel(lead.brand))}</p>
      <p>Source: Prep Kit fueling calculator</p>
      <p>Submitted: ${esc(lead.timestamp)}</p>
    </div>
  </div>
</body>
</html>`;
}

// --- Mission Control Webhook ---

async function notifyMissionControl(env, data, source) {
  try {
    const payload = {
      email: data.email,
      name: data.name || '',
      brand: data.brand || 'gravelgod',
      source: source,
      race_slug: data.race_slug || '',
      race_name: data.race_name || '',
    };
    if (data.guide_chapter) payload.guide_chapter = data.guide_chapter;
    if (Array.isArray(data.viewed_races) && data.viewed_races.length) {
      payload.viewed_races = data.viewed_races;
    }

    await fetch(`${env.MC_WEBHOOK_URL}/webhooks/subscriber`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${env.MC_WEBHOOK_SECRET || ''}`,
      },
      body: JSON.stringify(payload),
    });

    console.log('Mission Control notified:', data.email, source);
  } catch (error) {
    console.error('Mission Control webhook error:', error);
  }
}

// --- CORS + Response Helpers ---

function handleCORS(request, env) {
  const origin = request.headers.get('Origin');
  const allowedOrigins = (env.ALLOWED_ORIGINS || 'https://gravelgodcycling.com').split(',').map(o => o.trim());
  const isAllowed = allowedOrigins.some(allowed => origin?.startsWith(allowed));

  return new Response(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': isAllowed ? origin : '',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Max-Age': '86400'
    }
  });
}

function jsonResponse(data, status, origin) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': origin || '*' }
  });
}
