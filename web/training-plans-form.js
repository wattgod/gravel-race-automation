(function() {
  var API_URL = 'https://athlete-custom-training-plan-pipeline-production.up.railway.app/api/create-checkout';
  var form = document.getElementById('gg-training-form');
  var messageEl = document.getElementById('gg-form-message');
  var submitBtn = form.querySelector('.gg-submit-btn');
  var racesContainer = document.getElementById('races-container');
  var addRaceBtn = document.getElementById('add-race-btn');

  var raceCount = 0;
  var MAX_RACES = 10;
  var formStarted = false;
  var formSubmitted = false;
  var sectionsSeen = {};
  var STORAGE_KEY = 'gg_training_form';

  // ---- Pricing constants (must match server) ----
  var PRICE_PER_WEEK = 15;
  var PRICE_CAP = 249;
  var MIN_WEEKS = 4;

  function computePrice(raceDateStr) {
    if (!raceDateStr) return null;
    var raceDate = new Date(raceDateStr + 'T00:00:00');
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var days = Math.ceil((raceDate - today) / (1000 * 60 * 60 * 24));
    var weeks = Math.max(MIN_WEEKS, Math.ceil(days / 7));
    var price = Math.min(weeks * PRICE_PER_WEEK, PRICE_CAP);
    return { weeks: weeks, price: price };
  }

  function updatePriceDisplay() {
    var races = getRaces();
    var aRace = races.find(function(r) { return r.priority === 'A'; }) || races[0];
    if (aRace && aRace.date) {
      var pricing = computePrice(aRace.date);
      if (pricing) {
        submitBtn.textContent = 'Submit & Pay — $' + pricing.price;
        return;
      }
    }
    submitBtn.textContent = 'Submit & Pay';
  }

  // ---- GA4 Analytics Helper ----
  function track(event, params) {
    if (typeof gtag === 'function') {
      gtag('event', event, params || {});
    } else if (window.dataLayer) {
      var obj = { event: event };
      if (params) { for (var k in params) obj[k] = params[k]; }
      window.dataLayer.push(obj);
    }
  }

  track('tp_page_view', { page: 'questionnaire' });

  // ---- localStorage persistence ----
  function saveForm() {
    try {
      var formData = new FormData(form);
      var data = {};
      formData.forEach(function(val, key) {
        if (key === '_honeypot') return;
        if (data[key] !== undefined) {
          if (!Array.isArray(data[key])) data[key] = [data[key]];
          data[key].push(val);
        } else {
          data[key] = val;
        }
      });
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch(e) {}
  }

  function restoreForm() {
    try {
      var saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (!saved) return;
      for (var key in saved) {
        if (key.startsWith('race_')) continue;
        var val = saved[key];
        if (Array.isArray(val)) {
          val.forEach(function(v) {
            var cb = form.querySelector('input[name="' + key + '"][value="' + v + '"]');
            if (cb) cb.checked = true;
          });
        } else {
          var el = form.querySelector('[name="' + key + '"]');
          if (!el) continue;
          if (el.type === 'radio') {
            var radio = form.querySelector('input[name="' + key + '"][value="' + val + '"]');
            if (radio) radio.checked = true;
          } else {
            el.value = val;
          }
        }
      }
      // Trigger conditional fields
      var powerOrHr = form.querySelector('input[name="powerOrHr"]:checked');
      if (powerOrHr) powerOrHr.dispatchEvent(new Event('change', { bubbles: true }));
      if (sexSelect) sexSelect.dispatchEvent(new Event('change'));
      calculateWkg();
    } catch(e) {}
  }

  function clearSaved() {
    try { localStorage.removeItem(STORAGE_KEY); } catch(e) {}
  }

  // ---- Field name mapping (camelCase form → snake_case worker) ----
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
    daysOff: 'off_days'
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
    }

    // Keep full races array for reference
    mapped.races = races;

    return mapped;
  }

  // ---- Race Entries ----
  function createRaceEntry(index) {
    var entry = document.createElement('div');
    entry.className = 'gg-race-entry';
    entry.dataset.raceIndex = index;
    entry.innerHTML =
      '<div class="gg-race-entry-header">' +
        '<span class="gg-race-number">Race ' + (index + 1) + '</span>' +
        '<button type="button" class="gg-remove-race" onclick="removeRace(' + index + ')">Remove</button>' +
      '</div>' +
      '<div class="gg-race-fields">' +
        '<div class="gg-form-group">' +
          '<label>Race Name <span class="required">*</span></label>' +
          '<input type="text" name="race_' + index + '_name" required placeholder="e.g., Unbound 200">' +
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
            '<option value="A">A - Main Goal</option>' +
            '<option value="B">B - Important</option>' +
            '<option value="C">C - Training</option>' +
          '</select>' +
        '</div>' +
      '</div>';
    return entry;
  }

  function addRace() {
    if (raceCount >= MAX_RACES) return;
    racesContainer.appendChild(createRaceEntry(raceCount));
    raceCount++;
    updateAddButton();
  }

  window.removeRace = function(index) {
    var entry = racesContainer.querySelector('[data-race-index="' + index + '"]');
    if (entry) { entry.remove(); renumberRaces(); }
  };

  function renumberRaces() {
    var entries = racesContainer.querySelectorAll('.gg-race-entry');
    raceCount = entries.length;
    entries.forEach(function(entry, i) {
      entry.dataset.raceIndex = i;
      entry.querySelector('.gg-race-number').textContent = 'Race ' + (i + 1);
      entry.querySelector('.gg-remove-race').setAttribute('onclick', 'removeRace(' + i + ')');
      entry.querySelectorAll('input, select').forEach(function(field) {
        field.name = field.name.replace(/race_\d+_/, 'race_' + i + '_');
      });
    });
    updateAddButton();
  }

  function updateAddButton() {
    if (raceCount >= MAX_RACES) {
      addRaceBtn.disabled = true;
      addRaceBtn.textContent = 'Maximum ' + MAX_RACES + ' races';
    } else {
      addRaceBtn.disabled = false;
      addRaceBtn.textContent = '+ Add Race';
    }
  }

  addRace(); // First race by default
  addRaceBtn.addEventListener('click', addRace);

  // ---- Update price when race fields change ----
  racesContainer.addEventListener('change', updatePriceDisplay);
  racesContainer.addEventListener('input', function() {
    clearTimeout(racesContainer._priceTimeout);
    racesContainer._priceTimeout = setTimeout(updatePriceDisplay, 500);
  });

  // ---- Power/HR toggle ----
  var powerHrRadios = document.querySelectorAll('input[name="powerOrHr"]');
  var powerFields = document.getElementById('powerFields');
  var hrFields = document.getElementById('hrFields');

  powerHrRadios.forEach(function(radio) {
    radio.addEventListener('change', function() {
      var val = this.value;
      powerFields.style.display = (val === 'power' || val === 'both') ? 'block' : 'none';
      hrFields.style.display = (val === 'hr' || val === 'both') ? 'block' : 'none';
    });
  });

  // ---- W/kg calculation ----
  var ftpInput = document.getElementById('ftpInput');
  var weightInput = document.querySelector('input[name="weight"]');
  var sexSelect = document.querySelector('select[name="sex"]');
  var pwCalc = document.getElementById('pwCalc');
  var wkgValue = document.getElementById('wkgValue');
  var catValue = document.getElementById('catValue');

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

  if (ftpInput) ftpInput.addEventListener('input', calculateWkg);
  if (weightInput) weightInput.addEventListener('input', calculateWkg);
  if (sexSelect) sexSelect.addEventListener('change', calculateWkg);

  // ---- Menstrual cycle fields (sex = female) ----
  var cycleRow = document.getElementById('cycle-row');
  if (sexSelect && cycleRow) {
    sexSelect.addEventListener('change', function() {
      cycleRow.style.display = this.value === 'female' ? 'flex' : 'none';
    });
  }

  // ---- Flexible checkbox logic ----
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

  function getRaces() {
    var races = [];
    racesContainer.querySelectorAll('.gg-race-entry').forEach(function(entry, i) {
      var name = form.querySelector('input[name="race_' + i + '_name"]');
      var date = form.querySelector('input[name="race_' + i + '_date"]');
      var distance = form.querySelector('select[name="race_' + i + '_distance"]');
      var goal = form.querySelector('select[name="race_' + i + '_goal"]');
      var priority = form.querySelector('select[name="race_' + i + '_priority"]');
      if (name && name.value && date && date.value) {
        races.push({
          name: name.value, date: date.value,
          distance: distance ? distance.value : '',
          goal: goal ? goal.value : '',
          priority: priority ? priority.value : ''
        });
      }
    });
    return races;
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

  // ---- Form section progress tracking ----
  form.addEventListener('focusin', function(e) {
    if (!formStarted) {
      formStarted = true;
      track('tp_form_start', {});
    }
    var section = e.target.closest('.gg-form-section');
    if (section) {
      var num = section.querySelector('.gg-section-number');
      var sectionId = num ? num.textContent.trim() : '?';
      if (!sectionsSeen[sectionId]) {
        sectionsSeen[sectionId] = true;
        track('tp_form_section', { section: sectionId });
      }
    }
  });

  // ---- Auto-save on change ----
  form.addEventListener('change', saveForm);
  form.addEventListener('input', function() {
    clearTimeout(form._saveTimeout);
    form._saveTimeout = setTimeout(saveForm, 1000);
  });

  // ---- Abandonment tracking ----
  window.addEventListener('beforeunload', function() {
    if (formStarted && !formSubmitted) {
      track('tp_form_abandon', {
        sections_reached: Object.keys(sectionsSeen).length,
        last_section: Object.keys(sectionsSeen).pop() || '0'
      });
      // Beacon for reliability
      if (navigator.sendBeacon && typeof gtag === 'function') {
        navigator.sendBeacon('https://www.google-analytics.com/collect', '');
      }
    }
  });

  // ---- Restore saved form data ----
  restoreForm();
  updatePriceDisplay(); // Show price from restored race dates

  // ---- Form submission → Stripe Checkout ----
  form.addEventListener('submit', async function(e) {
    e.preventDefault();
    var races = getRaces();
    if (races.length === 0) {
      messageEl.className = 'gg-form-message error';
      messageEl.textContent = 'Please add at least one race.';
      messageEl.style.display = 'block';
      track('tp_form_error', { error: 'no_races' });
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Preparing checkout...';
    messageEl.style.display = 'none';

    // Build data object with camelCase field names
    var formData = new FormData(form);
    var data = Object.fromEntries(formData.entries());

    // Remove individual race fields (we use the races array)
    Object.keys(data).forEach(function(key) {
      if (key.startsWith('race_')) delete data[key];
    });
    data.races = races;
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
    data._source = 'gravelgodcycling.com/training-plans/questionnaire';

    // Map to worker format (camelCase → snake_case)
    var workerData = mapToWorkerFormat(data);

    try {
      var response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(workerData)
      });
      var result = await response.json();

      if (result.checkout_url) {
        // Success — redirect to Stripe Checkout
        formSubmitted = true;
        clearSaved();
        var aRace = races.find(function(r) { return r.priority === 'A'; }) || races[0];
        var pricing = aRace ? computePrice(aRace.date) : null;
        track('tp_form_submit', {
          races_count: races.length,
          has_power: !!(ftpInput && ftpInput.value),
          sections_completed: Object.keys(sectionsSeen).length,
          price: pricing ? pricing.price : 0,
          weeks: pricing ? pricing.weeks : 0
        });
        window.location.href = result.checkout_url;
        return; // Don't re-enable button — page is navigating away
      } else {
        throw new Error(result.error || 'Failed to create checkout session');
      }
    } catch (error) {
      messageEl.className = 'gg-form-message error';
      messageEl.textContent = error.message || 'Something went wrong. Please try again.';
      track('tp_form_error', { error: error.message || 'unknown' });
      messageEl.style.display = 'block';
      submitBtn.disabled = false;
      updatePriceDisplay();
      messageEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });
})();
