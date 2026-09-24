(function() {
  if (window.__ggSeasonPlanFormLoaded) return;
  window.__ggSeasonPlanFormLoaded = true;

  var API_BASE = 'https://athlete-custom-training-plan-pipeline-production.up.railway.app/api';
  var API_URL = API_BASE + '/create-checkout';
  // Mission Control's own public URL (docs/handoffs/2026-09-22-season-review-
  // and-goals-funnel.md) — the read-only prefill route lives there, not on
  // the checkout server.
  var MC_BASE = 'https://athlete-profiles-production.up.railway.app';

  var form = document.getElementById('gg-season-form');
  if (!form) return;
  var messageEl = document.getElementById('gg-season-message');
  var submitBtn = form.querySelector('.gg-apply-submit-btn');
  var racesContainer = document.getElementById('season-races-container');
  var addRaceBtn = document.getElementById('season-add-race-btn');

  var raceCount = 0;
  var MAX_RACES = 20;
  var formStarted = false;

  /* ---- URL params (?t=<poster_token>, and the same attribution params
     every other GG questionnaire reads) ---- */
  var TOKEN = (function() {
    var v = '';
    try { v = new URLSearchParams(window.location.search).get('t') || ''; } catch (e) {}
    // Plain $ is correct and sufficient here — unlike Python's re module,
    // JS regex $ (no /m flag) has no "matches before a trailing newline"
    // quirk, so it doesn't need Python's \Z workaround (which isn't even
    // valid JS regex syntax — \Z matches a literal "Z", silently breaking
    // every token match, caught by re-screenshotting after this fix).
    return /^[A-Za-z0-9_-]{16,64}$/.test(v) ? v : '';
  })();
  // sol review round 2: ?t= is a bearer credential (unlocks name/email/
  // goal/race/habits for a valid token) that would otherwise sit in the
  // visible URL for the rest of this visit — browser history, anything
  // screenshotted or copy-pasted, and this page's own later GA4 events,
  // which read window.location. Scrubbed from the URL bar (not from the
  // one initial page load itself, which the browser has already sent to
  // the server) the instant it's read, before the prefill fetch or
  // anything else runs. Never throws if the History API is unavailable.
  if (TOKEN && window.history && window.history.replaceState) {
    try {
      var scrubbedUrl = new URL(window.location.href);
      scrubbedUrl.searchParams.delete('t');
      window.history.replaceState(null, '', scrubbedUrl.pathname + scrubbedUrl.search);
    } catch (e) {}
  }
  var OFFER_VARIANT = (function() {
    var v = '';
    try { v = new URLSearchParams(window.location.search).get('offer_variant') || ''; } catch (e) {}
    return /^[ABC]$/.test(v) ? v : '';
  })();
  var ENTRY_SRC = (function() {
    var v = '';
    try { v = new URLSearchParams(window.location.search).get('entry_src') || ''; } catch (e) {}
    return /^[a-z_]{1,24}$/.test(v) ? v : '';
  })();
  var RACE_SLUG = (function() {
    var v = '';
    try { v = new URLSearchParams(window.location.search).get('race') || ''; } catch (e) {}
    return /^[a-z0-9-]{1,80}$/.test(v) ? v : '';
  })();

  /* ---- GA4 (user actions only — never on page load / auto-play) ---- */
  function ga4(name, params) {
    try {
      if (typeof gtag === 'function') { gtag('event', name, params || {}); }
    } catch (e) {}
  }
  var startedTracked = false;
  function trackStart() {
    if (startedTracked) return;
    startedTracked = true;
    ga4('season_form_start', { offer_variant: OFFER_VARIANT, entry_src: ENTRY_SRC });
  }
  form.addEventListener('focusin', trackStart, { once: true });
  form.addEventListener('click', trackStart, { once: true });

  /* ---- Prefill from a returning /goals/ lead (D9) ----
     Read-only display ("already on file") for name/email/goal/A-race;
     the form works blank with no token. Never blocks the form on failure. */
  function showPrefillField(id, labelText, value) {
    var el = document.getElementById(id);
    if (!el || !value) return;
    el.hidden = false;
    var val = el.querySelector('[data-prefill-value]');
    if (val) { val.textContent = value; }
  }

  if (TOKEN) {
    fetch(MC_BASE + '/api/season-plan/prefill/' + encodeURIComponent(TOKEN), {
      headers: { 'Accept': 'application/json' }
    }).then(function(r) { return r.ok ? r.json() : null; }).then(function(data) {
      if (!data) return;
      var nameInput = form.querySelector('[name="name"]');
      var emailInput = form.querySelector('[name="email"]');
      // sol review round 2 NIT: don't clobber anything the visitor already
      // typed while this fetch was still in flight.
      if (data.name && nameInput && !nameInput.value) { nameInput.value = data.name; }
      if (data.email && emailInput && !emailInput.value) { emailInput.value = data.email; }
      showPrefillField('gg-sp-goal-onfile', 'Goal', data.goal);
      showPrefillField('gg-sp-habits-onfile', 'Habits', data.habits);
      if (data.a_race_name) {
        // Fill the already-present, still-empty first row (added at load
        // before this fetch resolved) rather than adding a second one.
        var firstEntry = racesContainer.querySelector('.gg-sp-race-entry');
        var nameField = firstEntry && firstEntry.querySelector('[name$="_name"]');
        var raceEntry = (nameField && !nameField.value) ? firstEntry : addRace();
        raceEntry.querySelector('[name$="_name"]').value = data.a_race_name;
        if (data.a_race_date) { raceEntry.querySelector('[name$="_date"]').value = data.a_race_date; }
        raceEntry.querySelector('[name$="_priority"]').value = 'A';
      }
    }).catch(function() { /* prefill is a convenience, never a blocker */ });
  }

  /* ---- Races: add/remove rows, at least one A race required ---- */
  function addRace() {
    // Cap on rows actually on the page, not a monotonic counter — sol
    // review: raceCount never decremented on remove, so adding and
    // removing rows permanently ate into the 20-row limit.
    if (racesContainer.children.length >= MAX_RACES) return null;
    var index = raceCount++;
    var entry = document.createElement('div');
    entry.className = 'gg-sp-race-entry';
    entry.dataset.raceIndex = index;

    var header = document.createElement('div');
    header.className = 'gg-sp-race-entry-header';
    var label = document.createElement('span');
    label.className = 'gg-sp-race-number';
    label.textContent = 'Race ' + (index + 1);
    header.appendChild(label);
    var removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'gg-sp-remove-race';
    removeBtn.textContent = 'Remove';
    removeBtn.addEventListener('click', function() { entry.remove(); });
    header.appendChild(removeBtn);
    entry.appendChild(header);

    var fields = document.createElement('div');
    fields.className = 'gg-sp-race-fields';

    var nameGroup = document.createElement('div');
    nameGroup.className = 'gg-apply-group';
    var nameLabel = document.createElement('label');
    nameLabel.className = 'gg-apply-label';
    nameLabel.textContent = 'Race name';
    var nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.name = 'race_' + index + '_name';
    nameInput.required = true;
    nameInput.placeholder = 'e.g., Unbound 200';
    nameGroup.appendChild(nameLabel);
    nameGroup.appendChild(nameInput);
    fields.appendChild(nameGroup);

    var dateGroup = document.createElement('div');
    dateGroup.className = 'gg-apply-group';
    var dateLabel = document.createElement('label');
    dateLabel.className = 'gg-apply-label';
    dateLabel.textContent = 'Date';
    var dateInput = document.createElement('input');
    dateInput.type = 'date';
    dateInput.name = 'race_' + index + '_date';
    dateInput.required = true;
    dateGroup.appendChild(dateLabel);
    dateGroup.appendChild(dateInput);
    fields.appendChild(dateGroup);

    var priorityGroup = document.createElement('div');
    priorityGroup.className = 'gg-apply-group';
    var priorityLabel = document.createElement('label');
    priorityLabel.className = 'gg-apply-label';
    priorityLabel.textContent = 'Priority';
    var prioritySelect = document.createElement('select');
    prioritySelect.name = 'race_' + index + '_priority';
    prioritySelect.required = true;
    ['A', 'B', 'C'].forEach(function(p) {
      var opt = document.createElement('option');
      opt.value = p;
      opt.textContent = p + (p === 'A' ? ' — the one that matters most' : '');
      prioritySelect.appendChild(opt);
    });
    priorityGroup.appendChild(priorityLabel);
    priorityGroup.appendChild(prioritySelect);
    fields.appendChild(priorityGroup);

    entry.appendChild(fields);
    racesContainer.appendChild(entry);
    return entry;
  }

  function getRaces() {
    var entries = racesContainer.querySelectorAll('.gg-sp-race-entry');
    var races = [];
    entries.forEach(function(entry) {
      var name = entry.querySelector('[name$="_name"]').value.trim();
      var date = entry.querySelector('[name$="_date"]').value;
      var priority = entry.querySelector('[name$="_priority"]').value;
      if (name && date) { races.push({ name: name, date: date, priority: priority }); }
    });
    return races;
  }

  if (addRaceBtn) {
    addRaceBtn.addEventListener('click', function() { addRace(); });
  }
  if (racesContainer && racesContainer.children.length === 0) { addRace(); }

  /* ---- Checkbox helper (off days) ---- */
  function getCheckboxValues(name) {
    var boxes = form.querySelectorAll('input[name="' + name + '"]:checked');
    var values = [];
    boxes.forEach(function(b) { values.push(b.value); });
    return values;
  }

  /* ---- Submit -> create-checkout, product: "season_plan" ---- */
  form.addEventListener('submit', function(e) {
    e.preventDefault();

    // Honeypot: a filled hidden field means a bot. Fail silently, no error
    // message a bot's script could branch on.
    var honeypot = form.querySelector('[name="website"]');
    if (honeypot && honeypot.value) { return; }

    var races = getRaces();
    if (races.length === 0) {
      messageEl.className = 'gg-apply-message error';
      messageEl.textContent = 'Add at least one race.';
      messageEl.hidden = false;
      return;
    }
    if (!races.some(function(r) { return r.priority === 'A'; })) {
      messageEl.className = 'gg-apply-message error';
      messageEl.textContent = 'Mark one race as your A — the one that matters most.';
      messageEl.hidden = false;
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Preparing checkout...';
    messageEl.hidden = true;

    var formData = new FormData(form);
    var payload = {
      product: 'season_plan',
      name: (formData.get('name') || '').toString().trim(),
      email: (formData.get('email') || '').toString().trim(),
      races: races,
      hours_per_week: formData.get('hours_per_week') || '',
      off_days: getCheckboxValues('off_days'),
      has_power_meter: formData.get('has_power_meter') || '',
      has_hr_monitor: formData.get('has_hr_monitor') || '',
      has_trainer: formData.get('has_trainer') || '',
      notes: (formData.get('notes') || '').toString().trim(),
      strength_want: formData.get('strength_want') || '',
      strength_equipment: (formData.get('strength_equipment') || '').toString().trim(),
      tp_email: (formData.get('tp_email') || '').toString().trim(),
      entry_surface: 'season_plan_page'
    };
    if (OFFER_VARIANT) { payload.offer_variant = OFFER_VARIANT; }
    if (ENTRY_SRC) { payload.entry_src = ENTRY_SRC; }
    if (RACE_SLUG) { payload.race_slug = RACE_SLUG; }

    ga4('begin_checkout', {
      currency: 'USD',
      value: __SEASON_PLAN_PRICE_CENTS_DOLLARS__,
      items: [{ item_name: 'Season Plan', item_category: 'season_plan', price: __SEASON_PLAN_PRICE_CENTS_DOLLARS__ }]
    });

    fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function(response) { return response.json(); }).then(function(result) {
      if (result.checkout_url) {
        ga4('season_form_submit', { races_count: races.length });
        window.location.href = result.checkout_url;
        return;
      }
      submitBtn.disabled = false;
      submitBtn.textContent = 'Submit & Pay — ' + __SEASON_PLAN_PRICE_DISPLAY__;
      messageEl.className = 'gg-apply-message error';
      messageEl.textContent = result.error || 'Something went wrong. Please try again.';
      messageEl.hidden = false;
    }).catch(function() {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Submit & Pay — ' + __SEASON_PLAN_PRICE_DISPLAY__;
      messageEl.className = 'gg-apply-message error';
      messageEl.textContent = 'Could not reach checkout. Please try again.';
      messageEl.hidden = false;
    });
  });
})();
