/**
 * Cloudflare Worker: Lead Intake (All Email Capture Points)
 *
 * Multi-brand: serves gravelgodcycling.com (default), roadielabs.com, and
 * xcskilabs.com. The page sends `brand`; absent → gravelgod. Brand is
 * tagged on the Mission Control payload and the notification email
 * subject/sender so road leads are distinguishable in the shared inbox.
 *
 * Handles 16 capture sources:
 *   - exit_intent:        email only (race profile exit popup)
 *   - race_profile:       email + race context (prep kit CTA)
 *   - prep_kit_gate:      email + race context (content unlock)
 *   - race_quiz:          email + race context (quiz results gate)
 *   - quiz_shared:        email + race context (shared quiz results)
 *   - tire_guide:         email + race context (tire setup CTA)
 *   - race_review:        email + race context + stars/review data (race profile review form)
 *   - state_hub:          email + state slug (state hub page subscribe)
 *   - date_reminder:      email + race slug + race date (race date reminder)
 *   - race_plan_ladder:   email + race context + tier (plan-ladder "notify me" form)
 *   - training_guide:     email + optional guide_chapter (guide end-of-chapter capture)
 *   - bikepacking_guide:  email + optional guide_chapter (bikepacking guide capture)
 *   - race_watch:         email + race context (race watch/reminder capture)
 *   - gravel_tv_subscribe: legacy Gravel TV subscriber source (retained during migration)
 *   - gravel_weekly_subscribe: Gravel Weekly publication signup
 *   - fueling_calculator: email + weight + race + fueling data (detected by weight_lbs, no source field)
 *
 * Transactional sources (not leads, never marketed to):
 *   - athlete_review:     a coached athlete's season review (goal_answers + athlete tag)
 *   - athlete_exit:       a leaving athlete's exit survey (goal_answers + athlete tag).
 *                         Not exit_intent, which is the race-page exit popup above.
 *
 * Notification emails fire for fueling_calculator (contains actionable athlete data),
 * athlete_review and athlete_exit.
 * Mission Control's database is the lead list of record — nothing else reads a marketing
 * contacts list, so this worker does not maintain one.
 */

const DISPOSABLE_DOMAINS = [
  '10minutemail.com', 'guerrillamail.com', 'mailinator.com', 'tempmail.com',
  'throwaway.email', 'fakeinbox.com', 'trashmail.com', 'maildrop.cc',
  'yopmail.com', 'temp-mail.org', 'getnada.com', 'mohmal.com'
];

const KNOWN_SOURCES = ['exit_intent', 'race_profile', 'prep_kit_gate', 'race_quiz', 'quiz_shared', 'tire_guide', 'race_review', 'state_hub', 'date_reminder', 'race_plan_ladder', 'training_guide', 'bikepacking_guide', 'race_watch', 'gravel_tv_subscribe', 'gravel_weekly_subscribe', 'goal_2027', 'athlete_review', 'athlete_exit'];

// Sources whose questionnaire answers ride along as goal_answers.
const ANSWER_SOURCES = ['goal_2027', 'athlete_review', 'athlete_exit'];

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') return handleCORS(request, env);
    if (request.method !== 'POST') return new Response('Method not allowed', { status: 405 });

    const origin = request.headers.get('Origin');
    const allowedOrigins = (env.ALLOWED_ORIGINS || 'https://gravelgodcycling.com').split(',').map(o => o.trim());
    if (!origin || !allowedOrigins.includes(origin)) {
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

    // 2027 goal questionnaire: the answers ARE the deliverable (they make the
    // poster and the coach's read), so unlike every other source this one
    // forwards a body. Capped hard — a lead payload is not a document store.
    if (ANSWER_SOURCES.includes(source)) {
      data.goal_answers = sanitizeAnswers(data.goal_answers);
      data.offer_variant = ['A', 'B', 'C'].includes(String(data.offer_variant))
        ? String(data.offer_variant)
        : '';
      // Which surface sent this visitor to /goals/ — 'home' (poster wall CTA)
      // or 'race' (race-page goal strip, generate_neo_brutalist.py
      // build_goal_card). race_slug (above) already carries which race page.
      data.entry_src = /^[a-z_]{1,24}$/.test(String(data.entry_src || ''))
        ? String(data.entry_src)
        : '';
      // Which goal the visitor tapped on the race-page goal card
      // (generate_neo_brutalist.py build_goal_card) before landing here —
      // fixed set only, same discipline as entry_src above.
      data.goal_type = /^(finish|beat_time|race_it|same|bigger)$/.test(String(data.goal_type || ''))
        ? String(data.goal_type)
        : '';
    }
    // A leaving athlete is not a lead: none of the lead context rides along.
    // Mission Control's countdown/debrief jobs enroll anyone whose stored
    // record carries a race_slug, so a stray ?race= on the exit link must
    // never reach it.
    if (source === 'athlete_exit') {
      for (const key of ['race_slug', 'race_name', 'guide_chapter', 'offer_variant',
        'entry_src', 'goal_type', 'viewed_races']) {
        delete data[key];
      }
    }
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
    // Nor is a coached athlete's season review a lead (the same reasoning as
    // the exit above): a ?race= on their review link must never reach
    // Mission Control's countdown/debrief jobs.
    if (source === 'athlete_review') {
      for (const key of ['race_slug', 'race_name', 'guide_chapter', 'offer_variant',
        'entry_src', 'goal_type', 'viewed_races']) {
        delete data[key];
      }
    }

    // Validate based on source
    const validation = validateBySource(source, data);
    if (!validation.valid) {
      return jsonResponse({ error: validation.error }, 400, origin);
    }

    // Downstream work: Mission Control, webhook, notification email
    // Failures here are logged but don't affect the user response
    // (mcResultPromise is declared here, at function scope, not inside the
    // try block below — it's read again after that block ends, and `let`
    // is block-scoped: a sol review caught a ReferenceError crashing every
    // accepted request when it was declared inside the try.)
    let mcResultPromise = null;
    try {
      const promises = [];

      // Notify Mission Control for sequence enrollment (all sources)
      if (env.MC_WEBHOOK_URL) {
        mcResultPromise = notifyMissionControl(env, data, source);
        promises.push(mcResultPromise);
      }

      // A coached athlete just filed their season review: tell Matti now, in
      // his inbox. FormSubmit mail is filtered to a label and skips the inbox,
      // which is how the old path went unseen.
      if (source === 'athlete_review' && env.NOTIFICATION_EMAIL) {
        promises.push(sendAthleteReviewEmail(env, data));
      }
      // A coached athlete is leaving: Matti hears now, with what to do next
      // at the top. Mission Control sends a short backup alert too, so one
      // failing never means none. Nothing here touches a marketing list.
      if (source === 'athlete_exit') {
        if (env.NOTIFICATION_EMAIL && env.RESEND_API_KEY) {
          promises.push(sendAthleteExitEmail(env, data));
        } else {
          // Mission Control's backup alert still goes; say why this one didn't.
          console.error('Athlete exit alert NOT sent: NOTIFICATION_EMAIL or RESEND_API_KEY is unset');
        }
      }

      // Notification email only for fueling_calculator (has actionable athlete data)
      if (source === 'fueling_calculator') {
        const leadId = generateLeadId(data.email, data.race_slug);
        const lead = formatFuelingLead(data, leadId);

        if (env.COACHING_WEBHOOK_URL) {
          promises.push(sendToWebhook(env.COACHING_WEBHOOK_URL, lead));
        }
        if (env.RESEND_API_KEY && env.NOTIFICATION_EMAIL) {
          promises.push(sendNotificationEmail(env, lead));
        }
      }

      const settled = await Promise.allSettled(promises);
      if (STORAGE_REQUIRED.includes(source) && settled.some(r => r.status === 'rejected')) {
        // the caller keeps the athlete's draft and shows an honest error
        return jsonResponse(
          { error: 'Could not store your answers. Nothing was lost — please try again.' },
          503, origin,
        );
      }
    } catch (downstreamError) {
      console.error('Downstream error (user unaffected):', downstreamError);
      if (STORAGE_REQUIRED.includes(source)) {
        return jsonResponse(
          { error: 'Could not store your answers. Nothing was lost — please try again.' },
          503, origin,
        );
      }
    }

    console.log('Lead captured:', { source, email: data.email, race_slug: data.race_slug || '' });

    const responseBody = { success: true, message: 'Your personalized plan is ready' };
    if (mcResultPromise) {
      const mcResult = await mcResultPromise.catch(() => ({}));
      if (mcResult && mcResult.poster_token) { responseBody.poster_token = mcResult.poster_token; }
    }
    return jsonResponse(responseBody, 200, origin);
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

  // training_guide and bikepacking_guide (guide captures): email only, required
  // above for all sources. guide_chapter is optional context, already
  // truncated to 80 chars before validation runs.

  return { valid: true };
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

// --- Notification Email (athlete season review) ---

// Resend first: SendGrid's key has been returning 401, and a season review
// that nobody is told about is the whole failure mode this replaced.
async function sendAthleteReviewEmail(env, data) {
  const answers = data.goal_answers || {};
  const who = esc(data.name || data.email);
  const rows = Object.entries(answers)
    .map(([k, v]) => `<tr><td style="padding:4px 12px 4px 0;font-family:monospace;color:#7d695d;vertical-align:top">${esc(k)}</td><td style="padding:4px 0">${esc(v)}</td></tr>`)
    .join('');
  const html = `<div style="font-family:Georgia,serif;max-width:640px">
    <p style="font-family:monospace;letter-spacing:.14em;color:#178079">ATHLETE SEASON REVIEW</p>
    <h2 style="margin:0 0 4px">${who}</h2>
    <p style="color:#7d695d;margin:0 0 16px">${esc(data.athlete || 'no athlete tag')} &middot; ${esc(data.email)}</p>
    <table style="border-collapse:collapse;font-size:15px">${rows}</table>
    <p style="font-family:monospace;font-size:12px;color:#7d695d;margin-top:20px">File it: python3 scripts/file_athlete_review.py --email ${esc(data.email)}</p>
  </div>`;

  const subject = `[GG] Season review: ${(data.name || data.email).substring(0, 60)}`;

  if (env.RESEND_API_KEY) {
    try {
      const resp = await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.RESEND_API_KEY}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          from: 'Gravel God <noreply@gravelgodcycling.com>',
          to: [env.NOTIFICATION_EMAIL],
          reply_to: data.email,
          subject,
          html
        })
      });
      const detail = await resp.text();
      console.log('Athlete review notification (resend):', resp.status, detail.slice(0, 200));
      if (resp.ok) return;
    } catch (error) {
      console.error('Resend notification failed:', error);
    }
  }

  if (!env.SENDGRID_API_KEY) return;
  try {
    const resp = await fetch('https://api.sendgrid.com/v3/mail/send', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.SENDGRID_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        personalizations: [{ to: [{ email: env.NOTIFICATION_EMAIL }], subject }],
        from: brandSender(data.brand || 'gravelgod'),
        reply_to: { email: data.email },
        content: [{ type: 'text/html', value: html }]
      })
    });
    console.log('Athlete review notification (sendgrid):', resp.status);
  } catch (error) {
    console.error('Athlete review notification failed:', error);
  }
}

// --- Notification Email (athlete exit survey) ---

// Option labels as the exit form shows them (wordpress/season_review_variants.py
// EXIT). tests/test_exit_survey.py fails if the two drift apart.
const EXIT_OPTION_LABELS = {
  exit_reason: {
    done: 'I got what I came for',
    time: 'Life got full',
    cost: 'Cost',
    health: 'Injury or health',
    break: 'A break from structured training',
    diy: 'Coaching myself from here',
    elsewhere: 'Moving to another coach, team or app',
    fit: "The coaching wasn't the right fit",
    progress: "I wasn't seeing the progress I wanted",
    other: 'Something else',
  },
  share_as: {
    full: 'Yes, with my full name',
    initial: 'Yes, first name and last initial',
    age_group: 'Yes, first name and age group',
    private: 'No, keep it between us',
  },
  connection: {
    none: 'No, just coaching',
    comped: 'You coached me free or at a discount',
    friend: "We're friends or ride together",
    work: "We've worked together",
    family: "We're family",
  },
  age_group: {
    under_18: 'Under 18',
    '18_29': '18–29',
    '30_39': '30–39',
    '40_49': '40–49',
    '50_59': '50–59',
    '60_plus': '60+',
  },
  reference: { yes: 'Yes', ask: 'Ask me first each time', no: 'No' },
  come_back: { yes: 'Probably', maybe: 'Maybe', no: 'Probably not' },
  checkin: {
    none: 'No thanks',
    '3m': 'In about three months',
    '6m': 'In about six months',
    preseason: 'Before next season',
  },
};
const EXIT_CHANNEL_LABELS = {
  where_site: 'gravelgodcycling.com',
  where_social: 'Gravel God social posts',
  where_email: 'Emails to riders thinking about coaching',
  where_tp: 'My TrainingPeaks coach profile',
};
const EXIT_NEED_LABELS = {
  need_zones: 'A summary of my zones and latest tests',
  need_notes: 'Notes for training on my own',
  need_billing: 'Confirmation that billing has stopped',
  need_tp: 'Help with my TrainingPeaks account',
};
// The receipts spec's identity tiers (docs/specs/receipts-social-proof-2026.md
// §5.3). "private" is not a sharing tier: that athlete appears in the count only.
const EXIT_SHARE_TIERS = {
  full: 'full name',
  initial: 'first name + last initial',
  age_group: 'first name + age group',
};

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
  'August', 'September', 'October', 'November', 'December'];

function monthsFrom(now, n) {
  const total = now.getUTCFullYear() * 12 + now.getUTCMonth() + n;
  return `${MONTHS[total % 12]} ${Math.floor(total / 12)}`;
}

// "Before next season": the gravel build starts over the winter, so the
// January after this one. The others count on from today.
function checkinMonth(code, now) {
  if (code === '3m') return monthsFrom(now, 3);
  if (code === '6m') return monthsFrom(now, 6);
  if (code === 'preseason') return `January ${now.getUTCFullYear() + 1}`;
  return '';
}

function exitLabel(field, value) {
  return (EXIT_OPTION_LABELS[field] || {})[value] || '';
}

// What Matti has to do, derived from the answers. Plain text; escaped where
// it is rendered. Mission Control's backup alert builds the same list
// (mission_control/services/athlete_exit.py next_actions); a test holds the
// two to the same output.
function exitNextActions(answers, now) {
  const actions = [];
  const tier = EXIT_SHARE_TIERS[answers.share_as];
  // "Can I share what you wrote above?" covers both texts.
  const consented = !!(tier && (answers.quote || answers.not_for));
  if (consented) {
    const channels = Object.keys(EXIT_CHANNEL_LABELS)
      .filter((k) => answers[k] === 'yes')
      .map((k) => EXIT_CHANNEL_LABELS[k]);
    const connection = exitLabel('connection', answers.connection) || 'not answered';
    actions.push(
      `Consent to share: ${tier}; channels: ${channels.join(', ') || 'none ticked'}; `
      + `connection: ${connection}. Next: send the exact wording + render for approval. `
      + 'Ledger entry needs quote_approved_at and render_approved_at before it can render.',
    );
  }
  if (answers.age_group === 'under_18') {
    actions.push("Under 18: needs a parent's sign-off before anything renders.");
  }
  if (consented && answers.share_as === 'age_group' && !exitLabel('age_group', answers.age_group)) {
    actions.push('Ask their age group at approval.');
  }
  if (consented && !exitLabel('connection', answers.connection)) {
    actions.push('Connection not answered: ask before approval.');
  }
  if (answers.reference === 'yes' || answers.reference === 'ask') {
    actions.push(`Add to the talk-to-an-athlete roster (${answers.reference === 'yes' ? 'yes' : 'ask first'}).`);
  }
  if (answers.checkin && answers.checkin !== 'none') {
    const month = checkinMonth(answers.checkin, now);
    if (month) {
      actions.push(`Check in around ${month} (${exitLabel('checkin', answers.checkin)}).`);
    }
  }
  const needs = Object.keys(EXIT_NEED_LABELS)
    .filter((k) => answers[k] === 'yes')
    .map((k) => EXIT_NEED_LABELS[k]);
  if (needs.length) actions.push(`Asked for: ${needs.join('; ')}.`);
  return actions;
}

function exitAnswerDisplay(key, value) {
  if (EXIT_OPTION_LABELS[key]) return exitLabel(key, value) ? `${exitLabel(key, value)} (${value})` : value;
  const tick = EXIT_CHANNEL_LABELS[key] || EXIT_NEED_LABELS[key];
  if (tick && value === 'yes') return `ticked: ${tick}`;
  return value;
}

// Resend only, from noreply@ (matti@ is accepted and never arrives). No
// marketing contact is created or updated for an exit, here or anywhere.
async function sendAthleteExitEmail(env, data) {
  const answers = data.goal_answers || {};
  const reason = exitLabel('exit_reason', answers.exit_reason) || 'no reason given';
  const actions = exitNextActions(answers, new Date());
  const who = esc(data.name || data.email);
  const actionsHtml = actions.length
    ? `<ul style="margin:0 0 16px;padding-left:20px">${actions.map((a) => `<li style="margin:0 0 6px">${esc(a)}</li>`).join('')}</ul>`
    : '<p style="margin:0 0 16px">None.</p>';
  const recommend = answers.recommend !== undefined ? `${esc(answers.recommend)}/10` : 'not answered';
  const rows = Object.entries(answers)
    .map(([k, v]) => `<tr><td style="padding:4px 12px 4px 0;font-family:monospace;color:#7d695d;vertical-align:top">${esc(k)}</td><td style="padding:4px 0">${esc(exitAnswerDisplay(k, v))}</td></tr>`)
    .join('');
  const html = `<div style="font-family:Georgia,serif;max-width:640px">
    <p style="font-family:monospace;letter-spacing:.14em;color:#178079">ATHLETE EXIT SURVEY</p>
    <h2 style="margin:0 0 4px">${who}</h2>
    <p style="color:#7d695d;margin:0 0 16px">${esc(data.athlete || 'no athlete tag')} &middot; ${esc(data.email)} &middot; ${esc(reason)}</p>
    <p style="font-family:monospace;letter-spacing:.14em;margin:0 0 6px">NEXT ACTIONS</p>
    ${actionsHtml}
    <p style="margin:0 0 16px"><b>Recommend:</b> ${recommend}</p>
    <table style="border-collapse:collapse;font-size:15px">${rows}</table>
  </div>`;

  const subject = `[GG] Exit survey · ${(data.name || data.email).substring(0, 60)} · ${reason}`;

  try {
    const resp = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.RESEND_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        from: 'Gravel God <noreply@gravelgodcycling.com>',
        to: [env.NOTIFICATION_EMAIL],
        reply_to: data.email,
        subject,
        html
      })
    });
    const detail = await resp.text();
    if (resp.ok) {
      console.log('Athlete exit notification (resend):', resp.status, detail.slice(0, 200));
    } else {
      console.error('Athlete exit notification REJECTED by Resend:', resp.status, detail.slice(0, 200));
    }
  } catch (error) {
    console.error('Athlete exit notification failed:', error);
  }
}

// --- Notification Email (fueling_calculator only) ---

// Resend: SendGrid's key has been returning 401 account-wide. Sent from
// noreply@ — the domain's other addresses (e.g. matti@) are accepted by
// Resend but silently never deliver, so noreply@ + a display name is the
// only address confirmed to arrive.
async function sendNotificationEmail(env, lead) {
  const emailBody = formatEmailBody(lead);
  const subject = `[${brandLabel(lead.brand)}] Fueling Lead: ${(lead.race_name || lead.race_slug).substring(0, 60)} - ${lead.email}`;

  try {
    const resp = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.RESEND_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        from: `${brandSender(lead.brand).name} <noreply@gravelgodcycling.com>`,
        to: [env.NOTIFICATION_EMAIL],
        reply_to: lead.email,
        subject,
        html: emailBody
      })
    });
    const detail = await resp.text();
    console.log('Fueling lead notification (resend):', resp.status, detail.slice(0, 200));
  } catch (error) {
    console.error('Resend notification failed:', error);
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

// --- Goal questionnaire answers ---

// Keep at most MAX_ANSWER_KEYS short answers, each truncated, with a total
// budget so one pasted essay can't blow up every downstream store.
const MAX_ANSWER_KEYS = 64;
const MAX_ANSWER_LEN = 4000;
// Room for the exit survey's eight free-text answers at MAX_ANSWER_LEN each
// (32000) plus its choices, so a full-length form is never cut. Mission
// Control's _MAX_GOAL_ANSWERS_TOTAL must match.
const MAX_ANSWERS_TOTAL = 40000;

function sanitizeAnswers(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
  const out = {};
  let budget = MAX_ANSWERS_TOTAL;
  for (const [key, value] of Object.entries(raw)) {
    if (Object.keys(out).length >= MAX_ANSWER_KEYS) break;
    if (!/^[a-z0-9_]{1,40}$/.test(key)) continue;
    if (typeof value !== 'string' && typeof value !== 'number') continue;
    const text = String(value).trim().substring(0, MAX_ANSWER_LEN);
    if (!text) continue;
    if (text.length > budget) continue;
    budget -= text.length;
    out[key] = text;
  }
  return out;
}

// --- Mission Control Webhook ---

// Sources whose answers are the deliverable. For these, Mission Control
// refusing the payload is a failure the visitor must hear about — otherwise
// the page shows a poster, wipes the saved draft, and the answers exist
// nowhere.
const STORAGE_REQUIRED = ['goal_2027', 'athlete_review', 'athlete_exit'];

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
    if (data.goal_answers && Object.keys(data.goal_answers).length) {
      payload.goal_answers = data.goal_answers;
    }
    if (data.offer_variant) payload.offer_variant = data.offer_variant;
    if (data.entry_src) payload.entry_src = data.entry_src;
    if (data.goal_type) payload.goal_type = data.goal_type;
    // Which athlete this belongs to. Without it a coached athlete's review
    // arrives unattributed and the filing script has to guess.
    if (data.athlete) payload.athlete = String(data.athlete).substring(0, 80);
    if (Array.isArray(data.viewed_races) && data.viewed_races.length) {
      payload.viewed_races = data.viewed_races;
    }

    const resp = await fetch(`${env.MC_WEBHOOK_URL}/webhooks/subscriber`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${env.MC_WEBHOOK_SECRET || ''}`,
      },
      body: JSON.stringify(payload),
    });

    console.log('Mission Control notified:', data.email, source, resp.status);
    if (!resp.ok && STORAGE_REQUIRED.includes(source)) {
      throw new Error(`Mission Control returned ${resp.status}`);
    }
    // For goal_2027 (D9), Mission Control hands back this lead's
    // poster_token so the caller can pass it on to the browser — the
    // Season Plan CTA needs it to link to /season-plan/?t=<token>.
    if (resp.ok && (source === 'goal_2027' || source === 'athlete_review')) {
      try {
        const body = await resp.json();
        if (body && body.poster_token) { return { poster_token: body.poster_token }; }
      } catch (parseErr) { /* not fatal — the CTA just falls back to blank */ }
    }
  } catch (error) {
    console.error('Mission Control webhook error:', error);
    if (STORAGE_REQUIRED.includes(source)) { throw error; }
  }
  return {};
}

// --- CORS + Response Helpers ---

function handleCORS(request, env) {
  const origin = request.headers.get('Origin');
  const allowedOrigins = (env.ALLOWED_ORIGINS || 'https://gravelgodcycling.com').split(',').map(o => o.trim());
  const isAllowed = !!origin && allowedOrigins.includes(origin);

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
