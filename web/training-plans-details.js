/* Two-step questionnaire, step 2: /training-plans/details/?t=<token> (2026-10-23).
 *
 * The customer has paid on step 1. This page asks the rest of the questions
 * the plan needs, autosaves a draft (localStorage + server), and submits the
 * finished answers to the pipeline, which then builds the plan.
 *
 * `fields` sent to the server is exactly what the full questionnaire sends to
 * /create-checkout today: built with the same FIELD_MAP, mapToWorkerFormat
 * and identifyBlindspots. Those blocks (and the attribution helpers) are
 * verbatim copies from web/training-plans-form.js; tests/test_plan_intake_pages.py
 * fails if they drift.
 */
(function() {
  if (window.__ggPlanDetailsLoaded) return;
  window.__ggPlanDetailsLoaded = true;

  var BRAND_CFG = window.__TP_FORM_CONFIG || {};
  var FORM_SOURCE = 'gravelgodcycling.com/training-plans/details';
  var GA_ATTRIBUTION_TIMEOUT_MS = 500;

  var API_BASE = 'https://athlete-custom-training-plan-pipeline-production.up.railway.app/api';
  var root = document.getElementById('gg-plan-details');
  var form = document.getElementById('gg-training-form');
  if (!root || !form) return;
  var messageEl = document.getElementById('gg-pd-message');
  var saveStatusEl = document.getElementById('gg-pd-save-status');
  var racesContainer = document.getElementById('races-container');
  var addRaceBtn = document.getElementById('add-race-btn');
  var pages = Array.prototype.slice.call(form.querySelectorAll('.gg-pd-page'));
  var progressFill = document.getElementById('gg-pd-progress-fill');
  var progressLabel = document.getElementById('gg-pd-progress-label');
  var backBtn = document.getElementById('gg-pd-back');
  var nextBtn = document.getElementById('gg-pd-next');
  var submitBtn = document.getElementById('gg-pd-submit');
  var DELIVERY_HOURS = root.getAttribute('data-delivery-hours') || '24';

  // mapToWorkerFormat (verbatim below) reads these. Step 2 never sends a
  // slug: the server keeps the A-race (and its slug) from step 1.
  var prefilledRaceSlug = null;
  var prefilledRaceName = null;

  var MAX_EXTRA_RACES = 9;
  var extraRaceCount = 0;
  var currentPage = 0;
  var intake = null;
  var token = '';
  var formStarted = false;
  var submitting = false;
  var done = false;
  var draftTimer = null;
  var draftDirty = false;
  var lastDraftBody = '';
  var STORAGE_PREFIX = 'gg_tp_details_';
  var TOKEN_SESSION_KEY = 'gg_tp_details_token';
  var DRAFT_DEBOUNCE_MS = 2000;

  // ---- Attribution + GA4 (verbatim from web/training-plans-form.js) ----
  var FORM_VERSION = '2026-10-23-two-step-2';

  var CHECKOUT_PENDING_KEY = 'gg_tp_checkout_pending';
  var IS_CHECKOUT_RETURN = false;
  try {
    IS_CHECKOUT_RETURN = sessionStorage.getItem(CHECKOUT_PENDING_KEY) === '1';
    sessionStorage.removeItem(CHECKOUT_PENDING_KEY);
  } catch (e) {}

  var ENTRY_SURFACE_KEY = 'gg_tp_entry_surface';
  var ENTRY_SURFACE_RE = /^[a-z_]{1,32}$/;
  function resolveEntrySurface() {
    var fromUrl = '';
    try { fromUrl = new URLSearchParams(window.location.search).get('src') || ''; } catch (e) {}
    if (ENTRY_SURFACE_RE.test(fromUrl)) {
      try { sessionStorage.setItem(ENTRY_SURFACE_KEY, fromUrl); } catch (e) {}
      return fromUrl;
    }
    // Only a genuine bounce back from Stripe reuses the stored surface —
    // a later, unrelated visit with no ?src= and no checkout in flight
    // must not silently inherit an old attribution just for sharing a tab.
    if (IS_CHECKOUT_RETURN) {
      try {
        var stored = sessionStorage.getItem(ENTRY_SURFACE_KEY) || '';
        if (ENTRY_SURFACE_RE.test(stored)) return stored;
      } catch (e) {}
    }
    var ref = document.referrer || '';
    if (!ref) return 'direct';
    var refOrigin = '';
    try { refOrigin = new URL(ref).origin; } catch (e) { return 'external'; }
    if (refOrigin !== window.location.origin) return 'external';
    if (/\/race\/[^/]+\/training-plan\//.test(ref)) return 'race_plan_page_untagged';
    if (/\/race\//.test(ref)) return 'race_profile_untagged';
    return 'internal_other';
  }
  var ENTRY_SURFACE = resolveEntrySurface();

  var OFFER_VARIANT_KEY = 'gg_tp_offer_variant';
  var OFFER_VARIANT_RE = /^[ABC]$/;
  function resolveOfferVariant() {
    var fromUrl = '';
    try { fromUrl = new URLSearchParams(window.location.search).get('offer_variant') || ''; } catch (e) {}
    if (OFFER_VARIANT_RE.test(fromUrl)) {
      try { sessionStorage.setItem(OFFER_VARIANT_KEY, fromUrl); } catch (e) {}
      return fromUrl;
    }
    if (!IS_CHECKOUT_RETURN) { return ''; }
    try {
      var stored = sessionStorage.getItem(OFFER_VARIANT_KEY) || '';
      if (OFFER_VARIANT_RE.test(stored)) return stored;
    } catch (e) {}
    return '';
  }
  var OFFER_VARIANT = resolveOfferVariant();

  var ENTRY_SRC_KEY = 'gg_tp_entry_src';
  var ENTRY_SRC_RE = /^[a-z_]{1,24}$/;
  function resolveEntrySrc() {
    var fromUrl = '';
    try { fromUrl = new URLSearchParams(window.location.search).get('entry_src') || ''; } catch (e) {}
    if (ENTRY_SRC_RE.test(fromUrl)) {
      try { sessionStorage.setItem(ENTRY_SRC_KEY, fromUrl); } catch (e) {}
      return fromUrl;
    }
    if (!IS_CHECKOUT_RETURN) { return ''; }
    try {
      var stored = sessionStorage.getItem(ENTRY_SRC_KEY) || '';
      if (ENTRY_SRC_RE.test(stored)) return stored;
    } catch (e) {}
    return '';
  }
  var ENTRY_SRC = resolveEntrySrc();

  function track(event, params) {
    var payload = { entry_surface: ENTRY_SURFACE, form_version: FORM_VERSION };
    if (OFFER_VARIANT) { payload.offer_variant = OFFER_VARIANT; }
    if (ENTRY_SRC) { payload.entry_src = ENTRY_SRC; }
    if (params) { for (var k in params) payload[k] = params[k]; }
    if (typeof gtag === 'function') {
      gtag('event', event, payload);
    } else if (window.dataLayer) {
      var obj = { event: event };
      for (var k2 in payload) obj[k2] = payload[k2];
      window.dataLayer.push(obj);
    }
  }

  // ---- Field mapping (verbatim from web/training-plans-form.js) ----
  var FIELD_MAP = {
    heightFeet: 'height_ft',
    heightInches: 'height_in',
    yearsCycling: 'years_cycling',
    typicalSleep: 'sleep_quality',
    stressLevel: 'stress_level',
    recentRideDuration: 'longest_ride',
    weeklyHours: 'hours_per_week',
    trainerType: 'trainer_access',
    currentStrength: 'strength_current',
    includeStrength: 'strength_want',
    strengthEquipment: 'strength_equipment',
    additionalNotes: 'notes',
    _honeypot: 'website',
    maxHr: 'hr_max',
    lthr: 'hr_threshold',
    restingHr: 'hr_resting',
    longRideDays: 'long_ride_days',
    intervalDays: 'interval_days',
    daysOff: 'off_days',
    travelDates: 'travel_dates'
  };

  function mapToWorkerFormat(data) {
    var mapped = {};
    for (var key in data) {
      if (!data.hasOwnProperty(key)) continue;
      var newKey = FIELD_MAP[key] || key;
      mapped[newKey] = data[key];
    }

    // Flatten A-race (or first race) for worker validation
    var races = data.races || [];
    var aRace = races.find(function(r) { return r.priority === 'A'; }) || races[0];
    if (aRace) {
      mapped.race_name = aRace.name;
      mapped.race_date = aRace.date;
      mapped.race_distance = aRace.distance || '';
      mapped.race_goal = aRace.goal || '';
      // Carry the slug ONLY if the A-race is still the one we prefilled from
      // ?race= (the customer didn't swap it). The backend resolves the target
      // race by this ID exactly; a stale slug would point at the wrong race.
      if (prefilledRaceSlug && aRace.name === prefilledRaceName) {
        mapped.race_slug = prefilledRaceSlug;
      }
    }

    // Keep full races array for reference
    mapped.races = races;

    return mapped;
  }

  function identifyBlindspots(data) {
    var bs = [];
    if (data.typicalSleep === 'poor' || data.typicalSleep === 'fair')
      bs.push('Sleep deficit may limit recovery');
    if (data.stressLevel === 'high' || data.stressLevel === 'very-high')
      bs.push('High life stress may require reduced training load');
    if (data.injuries) bs.push('Injury/limitation considerations noted');
    var aRace = (data.races || []).find(function(r) { return r.priority === 'A'; });
    if (aRace && parseInt(aRace.distance) >= 100 && data.recentRideDuration === '<2hrs')
      bs.push('Significant endurance gap for A-race distance');
    if (data.weeklyHours === '3-5' && aRace && parseInt(aRace.distance) >= 100)
      bs.push('Limited hours for long-distance A-race');
    if (data.travelDuringPlan === 'multi' || data.travelDuringPlan === 'frequent')
      bs.push('Frequent travel will disrupt training consistency');
    if (data.priorPlanExperience === 'none')
      bs.push('First structured plan - may need onboarding guidance');
    return bs;
  }

  // ---- Views ----
  function showView(name) {
    var views = root.querySelectorAll('[data-view]');
    for (var i = 0; i < views.length; i++) {
      views[i].hidden = views[i].getAttribute('data-view') !== name;
    }
    window.scrollTo(0, 0);
  }

  function showDone(building) {
    done = true;
    var line = document.getElementById('gg-pd-done-line');
    if (line) {
      if (!building) {
        line.textContent = '';
      } else if (new URLSearchParams(window.location.search).get('delivery') === 'endure' ||
                 (intake && intake.delivery === 'endure')) {
        line.textContent = 'It\u2019ll be ready within ' + DELIVERY_HOURS + ' hours.';
      } else {
        line.textContent = 'It\u2019ll be in your TrainingPeaks within ' + DELIVERY_HOURS + ' hours.';
      }
    }
    try { localStorage.removeItem(STORAGE_PREFIX + token); } catch (e) {}
    showView('done');
  }

  function showMessage(text) {
    messageEl.textContent = text;
    messageEl.style.display = 'block';
  }

  function hideMessage() {
    messageEl.style.display = 'none';
    messageEl.textContent = '';
  }

  // ---- Token (a bearer link: kept out of the address bar after reading) ----
  function readToken() {
    var params = new URLSearchParams(window.location.search);
    var t = params.get('t') || '';
    if (t) {
      try { sessionStorage.setItem(TOKEN_SESSION_KEY, t); } catch (e) {}
      try {
        var scrubbedUrl = new URL(window.location.href);
        scrubbedUrl.searchParams.delete('t');
        window.history.replaceState(null, '', scrubbedUrl.pathname + scrubbedUrl.search + scrubbedUrl.hash);
      } catch (e) {}
    } else {
      try { t = sessionStorage.getItem(TOKEN_SESSION_KEY) || ''; } catch (e) {}
    }
    return /^[A-Za-z0-9_.-]{6,200}$/.test(t) ? t : '';
  }

  // ---- Races page: A-race fixed from step 1, B/C races addable ----
  function createRaceEntry(index) {
    var entry = document.createElement('div');
    entry.className = 'gg-race-entry';
    entry.dataset.raceIndex = index;
    entry.innerHTML =
      '<div class="gg-race-entry-header">' +
        '<span class="gg-race-number"></span>' +
        '<button type="button" class="gg-remove-race">Remove</button>' +
      '</div>' +
      '<div class="gg-race-fields">' +
        '<div class="gg-form-group">' +
          '<label>Race Name <span class="required">*</span></label>' +
          '<input type="text" name="race_' + index + '_name" required placeholder="e.g., Mid South">' +
        '</div>' +
        '<div class="gg-form-group">' +
          '<label>Date <span class="required">*</span></label>' +
          '<input type="date" name="race_' + index + '_date" required>' +
        '</div>' +
        '<div class="gg-form-group">' +
          '<label>Distance</label>' +
          '<select name="race_' + index + '_distance">' +
            '<option value="">Select</option>' +
            '<option value="50">~50 mi</option>' +
            '<option value="75">~75 mi</option>' +
            '<option value="100">~100 mi</option>' +
            '<option value="130">~130 mi</option>' +
            '<option value="150">~150 mi</option>' +
            '<option value="200">200+ mi</option>' +
          '</select>' +
        '</div>' +
        '<div class="gg-form-group">' +
          '<label>Goal</label>' +
          '<select name="race_' + index + '_goal">' +
            '<option value="">Select</option>' +
            '<option value="survive">Survive</option>' +
            '<option value="finish-strong">Finish Strong</option>' +
            '<option value="compete">Compete</option>' +
            '<option value="podium">Podium</option>' +
          '</select>' +
        '</div>' +
        '<div class="gg-form-group">' +
          '<label>Priority <span class="required">*</span></label>' +
          '<select name="race_' + index + '_priority" required>' +
            '<option value="">Select</option>' +
            '<option value="B">B - Important</option>' +
            '<option value="C">C - Training</option>' +
          '</select>' +
        '</div>' +
      '</div>';
    return entry;
  }

  function addRace() {
    if (extraRaceCount >= MAX_EXTRA_RACES) return null;
    var entry = createRaceEntry(extraRaceCount);
    racesContainer.appendChild(entry);
    extraRaceCount++;
    renumberRaces();
    return entry;
  }

  function renumberRaces() {
    var entries = racesContainer.querySelectorAll('.gg-race-entry');
    extraRaceCount = entries.length;
    entries.forEach(function(entry, i) {
      entry.dataset.raceIndex = i;
      entry.querySelector('.gg-race-number').textContent = 'Race ' + (i + 2);
      entry.querySelectorAll('input, select').forEach(function(field) {
        field.name = field.name.replace(/race_\d+_/, 'race_' + i + '_');
      });
    });
    if (extraRaceCount >= MAX_EXTRA_RACES) {
      addRaceBtn.disabled = true;
      addRaceBtn.textContent = 'Maximum ' + (MAX_EXTRA_RACES + 1) + ' races';
    } else {
      addRaceBtn.disabled = false;
      addRaceBtn.textContent = '+ Add a B or C race';
    }
  }

  racesContainer.addEventListener('click', function(e) {
    var btn = e.target.closest('.gg-remove-race');
    if (!btn) return;
    var entry = btn.closest('.gg-race-entry');
    if (entry) { entry.remove(); renumberRaces(); queueDraft(); }
  });
  addRaceBtn.addEventListener('click', function() { addRace(); });

  function fieldValue(name) {
    var el = form.querySelector('[name="' + name + '"]');
    return el ? el.value : '';
  }

  function getRaces() {
    var races = [];
    if (intake && intake.race_name && intake.race_date) {
      races.push({
        name: intake.race_name, date: intake.race_date,
        distance: fieldValue('race_a_distance'),
        goal: fieldValue('race_a_goal'),
        priority: 'A'
      });
    }
    racesContainer.querySelectorAll('.gg-race-entry').forEach(function(entry, i) {
      var name = fieldValue('race_' + i + '_name');
      var date = fieldValue('race_' + i + '_date');
      if (name && date) {
        races.push({
          name: name, date: date,
          distance: fieldValue('race_' + i + '_distance'),
          goal: fieldValue('race_' + i + '_goal'),
          priority: fieldValue('race_' + i + '_priority')
        });
      }
    });
    return races;
  }

  // ---- Conditional fields (same rules as the full form) ----
  var sexSelect = form.querySelector('select[name="sex"]');
  var cycleRow = document.getElementById('cycle-row');
  var travelSelect = form.querySelector('[name="travelDuringPlan"]');
  var travelDatesGroup = document.getElementById('travelDatesGroup');
  var powerFields = document.getElementById('powerFields');
  var hrFields = document.getElementById('hrFields');
  var ftpInput = document.getElementById('ftpInput');
  var weightInput = form.querySelector('input[name="weight"]');
  var pwCalc = document.getElementById('pwCalc');
  var wkgValue = document.getElementById('wkgValue');
  var catValue = document.getElementById('catValue');

  function syncConditional() {
    if (sexSelect && cycleRow) {
      cycleRow.style.display = sexSelect.value === 'female' ? '' : 'none';
    }
    if (travelSelect && travelDatesGroup) {
      var tv = travelSelect.value;
      travelDatesGroup.style.display = (tv && tv !== 'none') ? '' : 'none';
    }
    var metric = form.querySelector('input[name="powerOrHr"]:checked');
    var mv = metric ? metric.value : '';
    if (powerFields) powerFields.style.display = (mv === 'power' || mv === 'both') ? '' : 'none';
    if (hrFields) hrFields.style.display = (mv === 'hr' || mv === 'both') ? '' : 'none';
    calculateWkg();
  }

  function calculateWkg() {
    var ftp = parseFloat(ftpInput ? ftpInput.value : '');
    var weightLbs = parseFloat(weightInput ? weightInput.value : '');
    var sex = sexSelect ? sexSelect.value : '';
    if (ftp && weightLbs) {
      var weightKg = weightLbs * 0.453592;
      var wkg = (ftp / weightKg).toFixed(2);
      wkgValue.textContent = wkg;
      var w = parseFloat(wkg);
      var category;
      if (sex === 'female') {
        if (w >= 4.5) category = 'Elite';
        else if (w >= 3.8) category = 'Cat 1-2';
        else if (w >= 3.2) category = 'Cat 3';
        else if (w >= 2.6) category = 'Cat 4';
        else category = 'Cat 5';
      } else {
        if (w >= 5.0) category = 'Elite';
        else if (w >= 4.2) category = 'Cat 1-2';
        else if (w >= 3.5) category = 'Cat 3';
        else if (w >= 2.9) category = 'Cat 4';
        else category = 'Cat 5';
      }
      catValue.textContent = category;
      pwCalc.style.display = 'block';
    } else {
      pwCalc.style.display = 'none';
    }
  }

  function setupFlexibleToggle(groupId) {
    var group = document.getElementById(groupId);
    if (!group) return;
    var checkboxes = group.querySelectorAll('input[type="checkbox"]');
    var flexibleCb = group.querySelector('input[value="Flexible"]');
    checkboxes.forEach(function(cb) {
      cb.addEventListener('change', function() {
        if (this.value === 'Flexible' && this.checked) {
          checkboxes.forEach(function(other) { if (other !== cb) other.checked = false; });
        } else if (this.value !== 'Flexible' && this.checked && flexibleCb) {
          flexibleCb.checked = false;
        }
      });
    });
  }
  setupFlexibleToggle('longRideDays');
  setupFlexibleToggle('intervalDays');

  function getCheckboxValues(name) {
    var checked = form.querySelectorAll('input[name="' + name + '"]:checked');
    return Array.from(checked).map(function(cb) { return cb.value; });
  }

  // ---- Build `fields`: the same shape the full form sends today ----
  function buildFields() {
    var formData = new FormData(form);
    var data = Object.fromEntries(formData.entries());

    // Remove individual race fields (we use the races array)
    Object.keys(data).forEach(function(key) {
      if (key.startsWith('race_')) delete data[key];
    });
    data.races = getRaces();
    data.longRideDays = getCheckboxValues('longRideDays');
    data.intervalDays = getCheckboxValues('intervalDays');
    data.daysOff = getCheckboxValues('daysOff');

    if (ftpInput && ftpInput.value && weightInput && weightInput.value) {
      var wKg = parseFloat(weightInput.value) * 0.453592;
      data.pwRatio = (parseFloat(ftpInput.value) / wKg).toFixed(2);
      data.estimatedCategory = catValue ? catValue.textContent : '';
    }

    // Compute blindspots BEFORE mapping (uses camelCase field names)
    data.blindspots = identifyBlindspots(data);
    data._source = FORM_SOURCE;

    return mapToWorkerFormat(data);
  }

  // Raw snapshot of the inputs, used only to restore the form later.
  function snapshotForm() {
    var snap = {};
    new FormData(form).forEach(function(val, key) {
      if (key === '_honeypot') return;
      if (snap[key] !== undefined) {
        if (!Array.isArray(snap[key])) snap[key] = [snap[key]];
        snap[key].push(val);
      } else {
        snap[key] = val;
      }
    });
    snap._savedAt = Date.now();
    snap._page = currentPage;
    return snap;
  }

  function applySnapshot(snap) {
    if (!snap) return;
    var maxRaceIdx = -1;
    Object.keys(snap).forEach(function(key) {
      var m = key.match(/^race_(\d+)_/);
      if (m && parseInt(m[1], 10) > maxRaceIdx) maxRaceIdx = parseInt(m[1], 10);
    });
    while (extraRaceCount <= maxRaceIdx && extraRaceCount < MAX_EXTRA_RACES) addRace();
    // Checkbox groups: a snapshot lists every checked box, so clear first.
    ['longRideDays', 'intervalDays', 'daysOff'].forEach(function(name) {
      if (snap[name] === undefined) return;
      form.querySelectorAll('input[name="' + name + '"]').forEach(function(cb) { cb.checked = false; });
    });
    Object.keys(snap).forEach(function(key) {
      if (key.charAt(0) === '_') return;
      setField(key, snap[key]);
    });
  }

  function setField(key, val) {
    if (val === null || val === undefined) return;
    if (Array.isArray(val)) {
      val.forEach(function(v) {
        var cb = form.querySelector('input[name="' + key + '"][value="' + cssEscape(v) + '"]');
        if (cb) cb.checked = true;
      });
      return;
    }
    var el = form.querySelector('[name="' + key + '"]');
    if (!el) return;
    if (el.type === 'radio' || el.type === 'checkbox') {
      var opt = form.querySelector('input[name="' + key + '"][value="' + cssEscape(val) + '"]');
      if (opt) opt.checked = true;
    } else {
      el.value = val;
    }
  }

  function cssEscape(v) {
    return String(v).replace(/["\\]/g, '\\$&');
  }

  // A server draft without a snapshot (fields only): map it back onto the form.
  function applyDraftFields(fields) {
    if (!fields) return;
    var reverse = {};
    for (var k in FIELD_MAP) reverse[FIELD_MAP[k]] = k;
    var skip = { races: 1, race_name: 1, race_date: 1, race_slug: 1, race_distance: 1, race_goal: 1,
      blindspots: 1, pwRatio: 1, estimatedCategory: 1, website: 1, name: 1, email: 1 };
    Object.keys(fields).forEach(function(key) {
      if (skip[key] || key.charAt(0) === '_') return;
      var formKey = reverse[key] || key;
      setField(formKey, fields[key]);
    });
    if (fields.race_distance) setField('race_a_distance', fields.race_distance);
    if (fields.race_goal) setField('race_a_goal', fields.race_goal);
    (fields.races || []).forEach(function(r) {
      if (!r || r.priority === 'A' || !r.name || !r.date) return;
      var entry = addRace();
      if (!entry) return;
      var i = extraRaceCount - 1;
      setField('race_' + i + '_name', r.name);
      setField('race_' + i + '_date', r.date);
      setField('race_' + i + '_distance', r.distance || '');
      setField('race_' + i + '_goal', r.goal || '');
      setField('race_' + i + '_priority', r.priority || '');
    });
  }

  // ---- Autosave: localStorage now, server draft debounced ----
  function saveLocal() {
    if (!token || done) return;
    try { localStorage.setItem(STORAGE_PREFIX + token, JSON.stringify(snapshotForm())); } catch (e) {}
  }

  function setSaveStatus(text) {
    if (saveStatusEl) saveStatusEl.textContent = text;
  }

  function queueDraft() {
    draftDirty = true;
    saveLocal();
    clearTimeout(draftTimer);
    draftTimer = setTimeout(sendDraft, DRAFT_DEBOUNCE_MS);
  }

  function sendDraft() {
    clearTimeout(draftTimer);
    if (!token || done || submitting || !draftDirty || !intake) return Promise.resolve();
    var fields = buildFields();
    fields._form = snapshotForm();
    var body = JSON.stringify({ fields: fields, submit: false });
    if (body === lastDraftBody) { draftDirty = false; return Promise.resolve(); }
    draftDirty = false;
    setSaveStatus('Saving\u2026');
    return fetch(API_BASE + '/intake-details/' + encodeURIComponent(token), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body,
      keepalive: body.length < 60000
    }).then(function(response) {
      if (response.status === 409) { showDone(false); return; }
      if (!response.ok) throw new Error('draft ' + response.status);
      lastDraftBody = body;
      setSaveStatus('Saved');
    }).catch(function() {
      draftDirty = true;
      setSaveStatus('Saved on this device');
    });
  }

  // ---- Pages ----
  function pageFields(index) {
    return Array.prototype.slice.call(pages[index].querySelectorAll('input, select, textarea'));
  }

  // A field inside a hidden conditional block (cycle, travel, power/HR) is
  // not validated, the same as the full form.
  function hiddenByConditional(f) {
    var el = f;
    while (el && el !== form) {
      if (el.style && el.style.display === 'none') return true;
      el = el.parentElement;
    }
    return false;
  }

  function firstInvalid(index) {
    var fields = pageFields(index);
    for (var i = 0; i < fields.length; i++) {
      if (hiddenByConditional(fields[i])) continue;
      if (!fields[i].checkValidity()) return fields[i];
    }
    return null;
  }

  function pageValid(index) {
    var bad = firstInvalid(index);
    if (bad) { bad.reportValidity(); return false; }
    return true;
  }

  function goToPage(index, opts) {
    if (index < 0 || index >= pages.length) return;
    currentPage = index;
    pages.forEach(function(p, i) { p.hidden = i !== index; });
    var pct = Math.round(((index + 1) / pages.length) * 100);
    if (progressFill) progressFill.style.width = pct + '%';
    if (progressLabel) {
      progressLabel.textContent = 'Step ' + (index + 1) + ' of ' + pages.length + ': ' +
        (pages[index].getAttribute('data-title') || '');
    }
    backBtn.hidden = index === 0;
    nextBtn.hidden = index === pages.length - 1;
    submitBtn.hidden = index !== pages.length - 1;
    hideMessage();
    if (!opts || !opts.silent) {
      track('tp_step2_page', { page: index + 1, page_name: pages[index].getAttribute('data-title') || '' });
      draftDirty = true;
      saveLocal();
      sendDraft();
      var top = document.getElementById('gg-pd-progress');
      if (top) top.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  backBtn.addEventListener('click', function() { goToPage(currentPage - 1); });
  nextBtn.addEventListener('click', function() {
    if (!pageValid(currentPage)) {
      track('tp_form_error', { error: 'page_invalid', step: 2, page: currentPage + 1 });
      return;
    }
    goToPage(currentPage + 1);
  });

  form.addEventListener('focusin', function() {
    if (formStarted) return;
    formStarted = true;
    track('tp_step2_start', {});
  });
  form.addEventListener('change', function() { syncConditional(); queueDraft(); });
  form.addEventListener('input', function() { calculateWkg(); queueDraft(); });
  document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'hidden') { saveLocal(); sendDraft(); }
  });

  // ---- Final submit ----
  form.addEventListener('submit', async function(e) {
    e.preventDefault();
    if (submitting || done) return;
    for (var i = 0; i < pages.length; i++) {
      var bad = firstInvalid(i);
      if (bad) {
        if (i !== currentPage) goToPage(i, { silent: true });
        bad.reportValidity();
        track('tp_form_error', { error: 'page_invalid', step: 2, page: i + 1 });
        return;
      }
    }
    submitting = true;
    clearTimeout(draftTimer);
    saveLocal();
    submitBtn.disabled = true;
    submitBtn.textContent = 'Sending\u2026';
    hideMessage();

    var fields = buildFields();
    var races = fields.races || [];
    track('tp_step2_submit', {
      races_count: races.length,
      has_power: !!(ftpInput && ftpInput.value)
    });

    var ok = false;
    var errorText = '';
    try {
      var response = await fetch(API_BASE + '/intake-details/' + encodeURIComponent(token), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fields: fields, submit: true })
      });
      var result = {};
      try { result = await response.json(); } catch (parseError) {}
      if (response.ok && (result.status === 'building' || result.status === 'received')) ok = true;
      else if (response.status === 409 && result.status === 'already_complete') ok = true;
      else errorText = result.error || '';
    } catch (err) {
      errorText = '';
    }

    if (ok) {
      showDone(true);
      return;
    }
    submitting = false;
    submitBtn.disabled = false;
    submitBtn.textContent = submitBtn.getAttribute('data-label') || 'SEND MY ANSWERS';
    showMessage((errorText ? errorText + ' ' : '') +
      'Your answers are saved on this device. Try again, or reply to your receipt email and I\u2019ll sort it out.');
    track('tp_form_error', { error: errorText || 'submit_failed', step: 2 });
  });

  // ---- Load ----
  function fillHeader() {
    var hello = document.getElementById('gg-pd-hello');
    var raceLine = document.getElementById('gg-pd-race-line');
    var aName = document.getElementById('gg-pd-a-name');
    var aDate = document.getElementById('gg-pd-a-date');
    var paidNote = document.getElementById('gg-pd-paid-note');
    var first = (intake.first_name || '').trim();
    if (hello) hello.textContent = first ? 'Thanks, ' + first + '. You\u2019re paid up.' : 'Thanks. You\u2019re paid up.';
    if (paidNote && intake.paid === false) {
      hello.textContent = first ? 'Thanks, ' + first + '.' : 'Thanks.';
      paidNote.hidden = false;
    }
    if (raceLine) {
      var bits = [];
      if (intake.race_name) bits.push(intake.race_name);
      if (intake.race_date) bits.push(intake.race_date);
      if (intake.weeks) bits.push(intake.weeks + ' weeks');
      if (intake.price_display) bits.push(intake.price_display);
      raceLine.textContent = bits.join(' \u00b7 ');
    }
    if (aName) aName.textContent = intake.race_name || '';
    if (aDate) aDate.textContent = intake.race_date || '';
  }

  function loadLocal() {
    try {
      var saved = JSON.parse(localStorage.getItem(STORAGE_PREFIX + token) || 'null');
      if (!saved || !saved._savedAt) return null;
      if (Date.now() - saved._savedAt > 30 * 24 * 60 * 60 * 1000) {
        localStorage.removeItem(STORAGE_PREFIX + token);
        return null;
      }
      return saved;
    } catch (e) { return null; }
  }

  function start() {
    token = readToken();
    if (!token) {
      track('tp_step2_view', { status: 'no_token' });
      showView('invalid');
      return;
    }
    fetch(API_BASE + '/intake-details/' + encodeURIComponent(token), { headers: { 'Accept': 'application/json' } })
      .then(function(response) {
        if (response.status === 404) { return { _status: 404 }; }
        if (!response.ok) { return { _status: response.status }; }
        return response.json();
      })
      .then(function(data) {
        if (data._status === 404) {
          track('tp_step2_view', { status: 'not_found' });
          showView('invalid');
          return;
        }
        if (data._status) {
          track('tp_step2_view', { status: 'error' });
          showView('error');
          return;
        }
        intake = data;
        if (data.status === 'complete') {
          track('tp_step2_view', { status: 'complete' });
          showDone(false);
          return;
        }
        track('tp_step2_view', { status: 'awaiting', paid: !!data.paid });
        fillHeader();
        var draft = data.draft || {};
        var serverSnap = draft._form || null;
        if (serverSnap) applySnapshot(serverSnap);
        else applyDraftFields(draft);
        var local = loadLocal();
        if (local && (!serverSnap || (local._savedAt || 0) >= (serverSnap._savedAt || 0))) {
          applySnapshot(local);
        }
        syncConditional();
        lastDraftBody = '';
        showView('form');
        var resume = (local && local._page) || (serverSnap && serverSnap._page) || 0;
        goToPage(Math.min(Math.max(parseInt(resume, 10) || 0, 0), pages.length - 1), { silent: true });
        track('tp_step2_page', { page: currentPage + 1, page_name: pages[currentPage].getAttribute('data-title') || '' });
      })
      .catch(function() {
        track('tp_step2_view', { status: 'error' });
        showView('error');
      });
  }

  renumberRaces();
  start();
})();
