/**
 * Cloudflare Worker: Training Plan Request Handler
 * 
 * Receives form submissions, validates, infers blindspots, sends notification
 */

const DISPOSABLE_DOMAINS = [
  '10minutemail.com', 'guerrillamail.com', 'mailinator.com', 'tempmail.com',
  'throwaway.email', 'fakeinbox.com', 'trashmail.com', 'maildrop.cc',
  'yopmail.com', 'temp-mail.org', 'getnada.com', 'mohmal.com'
];

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') return handleCORS(request, env);
    if (request.method !== 'POST') return new Response('Method not allowed', { status: 405 });

    const origin = request.headers.get('Origin');
    const allowedOrigins = (env.ALLOWED_ORIGINS || 'https://wattgod.github.io').split(',').map(o => o.trim());
    if (!allowedOrigins.some(allowed => origin?.startsWith(allowed))) {
      return new Response('Forbidden', { status: 403 });
    }

    try {
      const data = await request.json();
      
      const validation = validateSubmission(data);
      if (!validation.valid) {
        return jsonResponse({ error: validation.error }, 400, origin);
      }

      const requestId = generateRequestId(data.email, data.race_slug);
      const trainingRequest = formatTrainingRequest(data, requestId);

      if (env.SENDGRID_API_KEY && env.NOTIFICATION_EMAIL) {
        await sendNotificationEmail(env, trainingRequest);
      }

      if (env.GITHUB_TOKEN) {
        await triggerGitHubAction(env.GITHUB_TOKEN, trainingRequest);
      }

      console.log('Training plan request:', { request_id: requestId, race: data.race_name, email: data.email });

      return jsonResponse({
        success: true,
        message: `Got it! I'll build your ${data.race_name || 'training'} plan and send it to ${data.email} within 24 hours (usually same day).`,
        request_id: requestId
      }, 200, origin);

    } catch (error) {
      console.error('Worker error:', error);
      return jsonResponse({ error: 'Invalid request' }, 400, origin);
    }
  }
};

function validateSubmission(data) {
  const required = [
    'name', 'email', 'sex', 'age', 'weight', 'height_ft', 'height_in',
    'years_cycling', 'sleep_quality', 'stress_level',
    'race_date', 'race_goal', 'longest_ride',
    'hours_per_week', 'trainer_access',
    'strength_current', 'strength_want'
  ];
  
  for (const field of required) {
    if (!data[field]) {
      return { valid: false, error: `Missing: ${field.replace(/_/g, ' ')}` };
    }
  }

  // Email validation
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
    return { valid: false, error: 'Invalid email format' };
  }

  const emailDomain = data.email.split('@')[1].toLowerCase();
  if (DISPOSABLE_DOMAINS.includes(emailDomain)) {
    return { valid: false, error: 'Please use a non-disposable email' };
  }

  if (data.website) return { valid: false, error: 'Bot detected' };

  // Date validation
  const raceDate = new Date(data.race_date);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  
  if (raceDate < today) {
    return { valid: false, error: 'Race date is in the past' };
  }

  const weeksUntil = Math.floor((raceDate - today) / (7 * 24 * 60 * 60 * 1000));
  if (weeksUntil < 4) {
    return { valid: false, error: 'Race must be at least 4 weeks away' };
  }

  // Check day selections
  const longDays = Array.isArray(data.long_ride_days) ? data.long_ride_days : (data.long_ride_days ? [data.long_ride_days] : []);
  const intervalDays = Array.isArray(data.interval_days) ? data.interval_days : (data.interval_days ? [data.interval_days] : []);
  
  if (longDays.length === 0) {
    return { valid: false, error: 'Select at least one long ride day' };
  }
  if (intervalDays.length === 0) {
    return { valid: false, error: 'Select at least one interval day' };
  }

  return { valid: true };
}

function generateRequestId(email, raceSlug) {
  const base = email.split('@')[0].toLowerCase().replace(/[^a-z0-9]/g, '-').substring(0, 15);
  const race = (raceSlug || 'custom').substring(0, 10);
  return `tp-${race}-${base}-${Date.now().toString(36)}`;
}

function inferBlindspots(data) {
  const blindspots = [];
  
  if (data.sleep_quality === 'poor' || data.sleep_quality === 'fair') {
    blindspots.push({ code: 'RECOVERY_DEFICIT', label: 'Recovery Deficit', desc: 'Sleep quality may limit adaptation' });
  }
  
  if (data.stress_level === 'high' || data.stress_level === 'very_high') {
    blindspots.push({ code: 'LIFE_STRESS', label: 'Life Stress Overload', desc: 'High stress affects training capacity' });
  }
  
  if (data.strength_current === 'none' || data.strength_current === 'occasional') {
    blindspots.push({ code: 'MOVEMENT_GAP', label: 'Movement Quality Gap', desc: 'Limited strength foundation' });
  }
  
  if (data.injuries && data.injuries.trim().length > 0) {
    blindspots.push({ code: 'INJURY_MGMT', label: 'Injury Management', desc: 'Existing limitations to work around' });
  }
  
  if (data.strength_equipment === 'minimal' || data.strength_equipment === 'none') {
    blindspots.push({ code: 'EQUIPMENT_LIMITED', label: 'Equipment Limitations', desc: 'Minimal strength equipment' });
  }
  
  if (data.hours_per_week === '3-5' || data.hours_per_week === '5-7') {
    blindspots.push({ code: 'TIME_CRUNCHED', label: 'Time-Crunched', desc: 'Limited weekly training hours' });
  }
  
  const age = parseInt(data.age);
  if (age >= 45) {
    blindspots.push({ code: 'MASTERS', label: 'Masters Recovery', desc: 'Age 45+ requires recovery adjustments' });
  }
  
  if (data.trainer_access === 'no') {
    blindspots.push({ code: 'OUTDOOR_ONLY', label: 'Outdoor Only', desc: 'No indoor training option' });
  }
  
  return blindspots;
}

function calculateCategory(ftp, weight, sex) {
  if (!ftp || !weight) return null;
  
  const weightKg = weight * 0.453592;
  const wpkg = ftp / weightKg;
  
  const categories = sex === 'female' ? [
    { min: 4.3, cat: 'Pro/Cat 1' }, { min: 3.6, cat: 'Cat 2' }, { min: 3.2, cat: 'Cat 3' },
    { min: 2.8, cat: 'Cat 4' }, { min: 2.2, cat: 'Cat 5' }, { min: 0, cat: 'Recreational' }
  ] : [
    { min: 5.0, cat: 'Pro/Cat 1' }, { min: 4.2, cat: 'Cat 2' }, { min: 3.7, cat: 'Cat 3' },
    { min: 3.2, cat: 'Cat 4' }, { min: 2.5, cat: 'Cat 5' }, { min: 0, cat: 'Recreational' }
  ];
  
  const category = categories.find(c => wpkg >= c.min);
  return { wpkg: wpkg.toFixed(2), category: category?.cat || 'Unknown' };
}

function formatTrainingRequest(data, requestId) {
  const raceDate = new Date(data.race_date);
  const today = new Date();
  const weeksUntil = Math.floor((raceDate - today) / (7 * 24 * 60 * 60 * 1000));

  const heightInches = (parseInt(data.height_ft) * 12) + parseInt(data.height_in);
  const heightCm = Math.round(heightInches * 2.54);
  const weightKg = Math.round(parseInt(data.weight) * 0.453592);

  const blindspots = inferBlindspots(data);
  const powerMetrics = calculateCategory(data.ftp ? parseInt(data.ftp) : null, parseInt(data.weight), data.sex);

  const longDays = Array.isArray(data.long_ride_days) ? data.long_ride_days : (data.long_ride_days ? [data.long_ride_days] : []);
  const intervalDays = Array.isArray(data.interval_days) ? data.interval_days : (data.interval_days ? [data.interval_days] : []);
  const offDays = Array.isArray(data.off_days) ? data.off_days : (data.off_days ? [data.off_days] : []);

  return {
    request_id: requestId,
    timestamp: new Date().toISOString(),
    
    athlete: {
      name: data.name,
      email: data.email,
      sex: data.sex,
      age: parseInt(data.age),
      weight_lbs: parseInt(data.weight),
      weight_kg: weightKg,
      height_ft: parseInt(data.height_ft),
      height_in: parseInt(data.height_in),
      height_cm: heightCm,
      years_cycling: data.years_cycling,
      sleep_quality: data.sleep_quality,
      stress_level: data.stress_level
    },
    
    race: {
      slug: data.race_slug || 'custom',
      name: data.race_name || 'Custom Race',
      date: data.race_date,
      distance: data.race_distance || 'unknown',
      goal: data.race_goal,
      weeks_until: weeksUntil
    },
    
    fitness: {
      longest_recent_ride: data.longest_ride,
      ftp: data.ftp ? parseInt(data.ftp) : null,
      hr_max: data.hr_max ? parseInt(data.hr_max) : null,
      hr_threshold: data.hr_threshold ? parseInt(data.hr_threshold) : null,
      hr_resting: data.hr_resting ? parseInt(data.hr_resting) : null,
      watts_per_kg: powerMetrics?.wpkg || null,
      estimated_category: powerMetrics?.category || null
    },
    
    schedule: {
      hours_per_week: data.hours_per_week,
      trainer_access: data.trainer_access,
      long_ride_days: longDays,
      interval_days: intervalDays,
      off_days: offDays
    },
    
    strength: {
      current: data.strength_current,
      want_in_plan: data.strength_want,
      equipment: data.strength_equipment || null
    },
    
    blindspots: blindspots,
    
    notes: {
      injuries: data.injuries || null,
      additional: data.notes || null
    }
  };
}

async function sendNotificationEmail(env, req) {
  const emailBody = formatEmailBody(req);
  
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
          subject: `🏁 ${req.race.name}: ${req.athlete.name} (${req.race.goal}) - ${req.race.weeks_until}wks`
        }],
        from: { email: 'gravelgodcoaching@gmail.com', name: 'Gravel God Coaching' },
        reply_to: { email: req.athlete.email, name: req.athlete.name },
        content: [{ type: 'text/html', value: emailBody }]
      })
    });
    const sgStatus = sgResponse.status;
    const sgBody = await sgResponse.text();
    console.log('SendGrid response:', sgStatus, sgBody);
  } catch (error) {
    console.error('Email error:', error);
  }
}

function formatEmailBody(req) {
  const longDays = req.schedule.long_ride_days.join(', ') || 'None';
  const intervalDays = req.schedule.interval_days.join(', ') || 'None';
  const offDays = req.schedule.off_days.length > 0 ? req.schedule.off_days.join(', ') : 'None required';
  
  const blindspotHtml = req.blindspots.length > 0 
    ? `<h2>⚠️ Blindspots Detected</h2><div class="blindspots">${req.blindspots.map(b => `<div class="blindspot"><strong>${b.label}</strong> — ${b.desc}</div>`).join('')}</div>`
    : '';
  
  const powerHtml = req.fitness.watts_per_kg 
    ? `<div class="power-box"><span class="power-value">${req.fitness.watts_per_kg} W/kg</span><span class="power-cat">${req.fitness.estimated_category}</span></div>`
    : '';

  return `
<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: 'Courier New', monospace; background: #f5f5dc; padding: 20px; margin: 0; }
    .card { background: white; border: 3px solid #2c2c2c; padding: 24px; max-width: 680px; margin: 0 auto; }
    h1 { font-size: 18px; border-bottom: 3px solid #2c2c2c; padding-bottom: 8px; margin-top: 0; }
    h2 { font-size: 12px; color: #7d695d; margin-top: 20px; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.1em; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
    .row { display: flex; margin: 4px 0; font-size: 13px; }
    .label { width: 130px; color: #7d695d; flex-shrink: 0; }
    .value { font-weight: 600; color: #2c2c2c; }
    .highlight { background: #4ecdc4; padding: 2px 8px; color: #2c2c2c; }
    .goal-tag { display: inline-block; background: #F4D03F; padding: 3px 10px; font-weight: 700; text-transform: uppercase; font-size: 11px; }
    .notes-box { background: #f5f5dc; padding: 10px; margin-top: 6px; font-size: 12px; border-left: 3px solid #4ecdc4; }
    .footer { margin-top: 20px; padding-top: 12px; border-top: 2px solid #2c2c2c; font-size: 11px; color: #7d695d; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
    .metrics { background: #f9f9f9; padding: 10px; margin-top: 6px; display: flex; gap: 16px; flex-wrap: wrap; }
    .metric { display: inline-block; }
    .metric-value { font-weight: 700; color: #2c2c2c; font-size: 14px; }
    .metric-label { font-size: 10px; color: #7d695d; }
    .power-box { background: #2c2c2c; color: white; padding: 12px 16px; margin-top: 8px; display: flex; justify-content: space-between; align-items: center; }
    .power-value { font-size: 20px; font-weight: 700; color: #4ecdc4; }
    .power-cat { font-size: 12px; color: #a89074; }
    .blindspots { background: #fff3cd; border: 2px solid #ffc107; padding: 12px; margin-top: 8px; }
    .blindspot { margin: 6px 0; font-size: 12px; }
    .days-list { font-size: 12px; background: #f5f5dc; padding: 6px 10px; display: inline-block; margin-top: 4px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>🏁 Training Plan Request</h1>
    <p style="margin: 0 0 12px 0; font-size: 12px;"><strong>ID:</strong> ${req.request_id}</p>
    
    <h2>Athlete</h2>
    <div class="grid">
      <div>
        <div class="row"><span class="label">Name:</span><span class="value">${req.athlete.name}</span></div>
        <div class="row"><span class="label">Email:</span><span class="value">${req.athlete.email}</span></div>
        <div class="row"><span class="label">Sex / Age:</span><span class="value">${req.athlete.sex} / ${req.athlete.age}</span></div>
      </div>
      <div>
        <div class="row"><span class="label">Height:</span><span class="value">${req.athlete.height_ft}'${req.athlete.height_in}" (${req.athlete.height_cm}cm)</span></div>
        <div class="row"><span class="label">Weight:</span><span class="value">${req.athlete.weight_lbs}lbs (${req.athlete.weight_kg}kg)</span></div>
        <div class="row"><span class="label">Experience:</span><span class="value">${req.athlete.years_cycling}</span></div>
      </div>
    </div>
    <div class="row" style="margin-top: 8px;"><span class="label">Sleep:</span><span class="value">${req.athlete.sleep_quality}</span></div>
    <div class="row"><span class="label">Stress:</span><span class="value">${req.athlete.stress_level}</span></div>
    
    <h2>Race</h2>
    <div class="row"><span class="label">Race:</span><span class="value"><span class="highlight">${req.race.name}</span></span></div>
    <div class="row"><span class="label">Date:</span><span class="value">${req.race.date} <strong>(${req.race.weeks_until} weeks)</strong></span></div>
    <div class="row"><span class="label">Distance:</span><span class="value">${req.race.distance}</span></div>
    <div class="row"><span class="label">Goal:</span><span class="value"><span class="goal-tag">${req.race.goal}</span></span></div>
    
    <h2>Fitness</h2>
    <div class="row"><span class="label">Longest Ride:</span><span class="value">${req.fitness.longest_recent_ride} (last 4 wks)</span></div>
    <div class="metrics">
      <span class="metric"><span class="metric-value">${req.fitness.ftp || '—'}</span> <span class="metric-label">FTP</span></span>
      <span class="metric"><span class="metric-value">${req.fitness.hr_max || '—'}</span> <span class="metric-label">Max HR</span></span>
      <span class="metric"><span class="metric-value">${req.fitness.hr_threshold || '—'}</span> <span class="metric-label">LTHR</span></span>
      <span class="metric"><span class="metric-value">${req.fitness.hr_resting || '—'}</span> <span class="metric-label">Rest HR</span></span>
    </div>
    ${powerHtml}
    
    <h2>Schedule</h2>
    <div class="row"><span class="label">Hours/Week:</span><span class="value">${req.schedule.hours_per_week}</span></div>
    <div class="row"><span class="label">Trainer:</span><span class="value">${req.schedule.trainer_access}</span></div>
    <div class="row"><span class="label">Long Rides:</span></div>
    <div class="days-list">${longDays}</div>
    <div class="row"><span class="label">Intervals:</span></div>
    <div class="days-list">${intervalDays}</div>
    <div class="row"><span class="label">Off Days:</span></div>
    <div class="days-list">${offDays}</div>
    
    <h2>Strength</h2>
    <div class="row"><span class="label">Current:</span><span class="value">${req.strength.current}</span></div>
    <div class="row"><span class="label">Include:</span><span class="value">${req.strength.want_in_plan}</span></div>
    <div class="row"><span class="label">Equipment:</span><span class="value">${req.strength.equipment || 'Not specified'}</span></div>
    
    ${blindspotHtml}
    
    ${req.notes.injuries ? `<h2>Injuries/Limitations</h2><div class="notes-box">${req.notes.injuries}</div>` : ''}
    ${req.notes.additional ? `<h2>Additional Notes</h2><div class="notes-box">${req.notes.additional}</div>` : ''}
    
    <div class="footer">
      <p>↩️ Reply to contact ${req.athlete.name} directly</p>
      <p>Submitted: ${req.timestamp}</p>
    </div>
  </div>
</body>
</html>`;
}

async function triggerGitHubAction(token, request) {
  try {
    await fetch('https://api.github.com/repos/wattgod/training-plans-component/dispatches', {
      method: 'POST',
      headers: {
        'Accept': 'application/vnd.github.v3+json',
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        'User-Agent': 'Gravel-God-Training-Plans'
      },
      body: JSON.stringify({ event_type: 'training-plan-request', client_payload: request })
    });
  } catch (error) {
    console.error('GitHub trigger error:', error);
  }
}

function handleCORS(request, env) {
  const origin = request.headers.get('Origin');
  const allowedOrigins = (env.ALLOWED_ORIGINS || 'https://wattgod.github.io').split(',').map(o => o.trim());
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
