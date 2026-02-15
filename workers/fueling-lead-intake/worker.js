/**
 * Cloudflare Worker: Lead Intake (All Email Capture Points)
 *
 * Handles 6 capture sources from gravelgodcycling.com:
 *   - exit_intent:        email only (race profile exit popup)
 *   - race_profile:       email + race context (prep kit CTA)
 *   - prep_kit_gate:      email + race context (content unlock)
 *   - race_quiz:          email + race context (quiz results gate)
 *   - quiz_shared:        email + race context (shared quiz results)
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

const KNOWN_SOURCES = ['exit_intent', 'race_profile', 'prep_kit_gate', 'race_quiz', 'quiz_shared'];

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') return handleCORS(request, env);
    if (request.method !== 'POST') return new Response('Method not allowed', { status: 405 });

    const origin = request.headers.get('Origin');
    const allowedOrigins = (env.ALLOWED_ORIGINS || 'https://gravelgodcycling.com').split(',').map(o => o.trim());
    if (!allowedOrigins.some(allowed => origin?.startsWith(allowed))) {
      return new Response('Forbidden', { status: 403 });
    }

    try {
      const data = await request.json();

      // Honeypot check (all forms include this)
      if (data.website) {
        return jsonResponse({ error: 'Bot detected' }, 400, origin);
      }

      // Detect source: fueling_calculator has weight_lbs but no source field
      const source = data.source || (data.weight_lbs ? 'fueling_calculator' : null);

      if (!source || (source !== 'fueling_calculator' && !KNOWN_SOURCES.includes(source))) {
        return jsonResponse({ error: 'Unknown source' }, 400, origin);
      }

      // Validate based on source
      const validation = validateBySource(source, data);
      if (!validation.valid) {
        return jsonResponse({ error: validation.error }, 400, origin);
      }

      const promises = [];

      // Upsert to SendGrid Marketing Contacts (all sources)
      if (env.SENDGRID_API_KEY && env.SG_LIST_ID) {
        promises.push(upsertMarketingContact(env, data, source));
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

      console.log('Lead captured:', { source, email: data.email, race_slug: data.race_slug || '' });

      return jsonResponse({ success: true, message: 'Your personalized plan is ready' }, 200, origin);

    } catch (error) {
      console.error('Worker error:', error);
      // Return 200 to frontend — user already sees success UI
      return jsonResponse({ success: true }, 200, origin);
    }
  }
};

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
          subject: `⛽ Fueling Lead: ${lead.race_name || lead.race_slug} — ${lead.email}`
        }],
        from: { email: 'leads@gravelgodcycling.com', name: 'Gravel God Fueling' },
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
  const ftp = lead.athlete.ftp ? `${lead.athlete.ftp}W` : '—';
  const height = lead.athlete.height_ft
    ? `${lead.athlete.height_ft}'${lead.athlete.height_in || 0}"`
    : '—';
  const rate = lead.fueling.personalized_rate
    ? `${lead.fueling.personalized_rate}g/hr`
    : '—';
  const total = lead.fueling.total_carbs
    ? `${lead.fueling.total_carbs}g`
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
    <p style="margin: 0 0 10px; font-size: 12px;"><strong>ID:</strong> ${lead.lead_id}</p>

    <h2>Contact</h2>
    <div class="row"><span class="label">Email:</span><span class="value">${lead.email}</span></div>
    <div class="row"><span class="label">Race:</span><span class="value"><span class="highlight">${lead.race_name || lead.race_slug}</span></span></div>

    <h2>Athlete</h2>
    <div class="row"><span class="label">Weight:</span><span class="value">${lead.athlete.weight_lbs}lbs (${lead.athlete.weight_kg}kg)</span></div>
    <div class="row"><span class="label">Height:</span><span class="value">${height}</span></div>
    <div class="row"><span class="label">Age:</span><span class="value">${lead.athlete.age || '—'}</span></div>
    <div class="row"><span class="label">FTP:</span><span class="value">${ftp}</span></div>

    <h2>Fueling Results</h2>
    <div class="row"><span class="label">Target Hours:</span><span class="value">${lead.fueling.target_hours || '—'}</span></div>
    <div class="row"><span class="label">Carb Rate:</span><span class="value">${rate}</span></div>
    <div class="row"><span class="label">Total Carbs:</span><span class="value">${total}</span></div>

    <h2>Hydration</h2>
    <div class="row"><span class="label">Fluid Target:</span><span class="value">${lead.fueling.fluid_target_ml_hr ? lead.fueling.fluid_target_ml_hr + ' ml/hr' : '—'}</span></div>
    <div class="row"><span class="label">Sodium:</span><span class="value">${lead.fueling.sodium_mg_hr ? lead.fueling.sodium_mg_hr + ' mg/hr' : '—'}</span></div>
    <div class="row"><span class="label">Climate:</span><span class="value">${lead.fueling.climate_heat || '—'}</span></div>
    <div class="row"><span class="label">Sweat:</span><span class="value">${lead.fueling.sweat_tendency || '—'}</span></div>
    <div class="row"><span class="label">Fuel Format:</span><span class="value">${lead.fueling.fuel_format || '—'}</span></div>
    <div class="row"><span class="label">Cramping:</span><span class="value">${lead.fueling.cramp_history || '—'}</span></div>

    <div class="footer">
      <p>Source: Prep Kit fueling calculator</p>
      <p>Submitted: ${lead.timestamp}</p>
    </div>
  </div>
</body>
</html>`;
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
