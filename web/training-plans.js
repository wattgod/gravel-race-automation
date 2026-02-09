(function() {
  // ---- FAQ Accordion ----
  document.querySelectorAll('.tp-faq-q').forEach(function(q) {
    q.addEventListener('click', function() {
      var item = this.parentElement;
      var wasOpen = item.classList.contains('open');
      // Close all
      document.querySelectorAll('.tp-faq-item').forEach(function(i) {
        i.classList.remove('open');
      });
      if (!wasOpen) item.classList.add('open');
    });
  });

  // ---- Smooth scroll for anchor links ----
  document.querySelectorAll('.tp-landing a[href^="#"]').forEach(function(link) {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      var target = document.querySelector(this.getAttribute('href'));
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // ---- Sticky CTA smooth scroll ----
  var stickyCta = document.querySelector('.tp-sticky-cta a');
  if (stickyCta) {
    stickyCta.addEventListener('click', function(e) {
      e.preventDefault();
      var target = document.querySelector(this.getAttribute('href'));
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  }

  // ---- Rotating Reality Checks ----
  var realityChecks = [
    "You downloaded a 12-week plan from the internet. It assumed you had 15 hours a week and zero injuries. How'd that go?",
    "Your buddy's training plan worked great. For your buddy. You're not your buddy.",
    "A 50-year-old with 5 hours needs fundamentally different training than a 28-year-old with 15. Different hours demand different science.",
    "You know what a generic plan does at mile 80 of Unbound? Nothing. Because it doesn't know you're at Unbound.",
    "Every training plan is a bet. Most plans are betting you're a 25-year-old with unlimited time and perfect recovery. Are you?",
    "The plan said 'tempo ride, 2 hours.' You had 45 minutes before school pickup. So you skipped it. Then you skipped Tuesday too.",
    "Your FTP is 230. Your plan was written for someone with an FTP of 300. You've been training in the wrong zones for 8 weeks.",
    "You have a smart trainer collecting dust. You have a race in 16 weeks. You have no plan. You have excuses. Pick one to fix.",
    "Nutrition plan: 'eat 60g carbs per hour.' At what elevation? In what heat? For what distance? Details matter. Vague advice kills races.",
    "Your strength training is whatever YouTube recommended this week. Your left hip flexor has an opinion about that.",
    "Rest days aren't lazy. They're where adaptation happens. Your plan should know which ones are strategic and which ones are panic.",
    "You're training for a 100-mile gravel race with a plan designed for 40km road crits. The specificity isn't there.",
    "Three hours a week can build you for a gravel century. But not with a plan that wastes two of them on junk miles.",
    "You told your last plan about your bad knee. It gave you plyometrics in week 3.",
    "Heat kills more gravel races than fitness. If your plan doesn't have an acclimatization protocol, it's not a plan. It's a wish.",
    "You tapered for 3 weeks because 'that's what the article said.' You lost fitness. Race day felt flat. Taper length is individual.",
    "Your race starts at 7,000 feet. Your plan was written at sea level. That's a different sport and nobody told you.",
    "Training without power zones is like cooking without measurements. You can do it. It's just worse.",
    "You finished your last race. You also bonked at mile 60, walked two climbs, and questioned your life choices. 'Finished' is a low bar.",
    "Somewhere right now, someone is doing their third 'base phase' of the year because they keep restarting the same generic plan.",
    "Your plan says 'G-Spot, 2 hours.' At what cadence? In what position? After how much fatigue? Those dimensions change the workout entirely. Most plans don't even know they exist.",
    "Mile 80 of your race, you'll be grinding at 55rpm in the drops on tired legs. Your training plan should have prepared you for that exact scenario. Did it?"
  ];

  var quoteEl = document.getElementById('tp-quote-text');
  if (quoteEl) {
    // Shuffle using Fisher-Yates
    for (var qi = realityChecks.length - 1; qi > 0; qi--) {
      var qj = Math.floor(Math.random() * (qi + 1));
      var tmp = realityChecks[qi]; realityChecks[qi] = realityChecks[qj]; realityChecks[qj] = tmp;
    }
    var quoteIndex = 0;
    quoteEl.textContent = realityChecks[0];

    setInterval(function() {
      quoteEl.style.opacity = '0';
      setTimeout(function() {
        quoteIndex = (quoteIndex + 1) % realityChecks.length;
        quoteEl.textContent = realityChecks[quoteIndex];
        quoteEl.style.opacity = '1';
      }, 400);
    }, 8000);
  }

  // ---- Tab Switching ----
  document.querySelectorAll('.tp-tab-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var tab = this.dataset.tab;
      this.closest('.tp-tabs').querySelectorAll('.tp-tab-btn').forEach(function(b) {
        b.classList.remove('active');
      });
      this.classList.add('active');
      this.closest('.tp-tabs').querySelectorAll('.tp-tab-panel').forEach(function(p) {
        p.classList.remove('active');
      });
      document.getElementById('tab-' + tab).classList.add('active');
    });
  });

  // ---- Sample Week Clickable Blocks ----
  var sampleDetail = document.getElementById('tp-sample-detail');

  var zoneColors = {
    z1: '#e8e8e8',
    z2: '#F5E5D3',
    z3: '#c9b8a3',
    z4: '#59473C',
    z5: '#222',
    z6: '#000'
  };

  function buildWorkoutViz(structureJSON, meta) {
    var blocks = JSON.parse(structureJSON);
    var vizHTML = '<div class="tp-workout-viz">';
    blocks.forEach(function(b) {
      var heightPx = Math.round(b.h * 0.95);
      var bg = zoneColors[b.z] || '#ccc';
      var border = b.z === 'z2' ? '#59473C' : '#000';
      vizHTML += '<div class="tp-viz-block tp-viz-' + b.z + '" style="flex-basis:' + b.w + '%;height:' + heightPx + 'px;background:' + bg + ';border:2px solid ' + border + ';">';
      if (b.l) vizHTML += '<span class="tp-viz-label">' + b.l + '</span>';
      vizHTML += '</div>';
    });
    vizHTML += '</div>';
    if (meta) {
      var parts = meta.split(' | ');
      vizHTML += '<div class="tp-viz-meta">';
      parts.forEach(function(p) { vizHTML += '<span>' + p + '</span>'; });
      vizHTML += '</div>';
    }
    return vizHTML;
  }

  document.querySelectorAll('.tp-sample-block[data-detail]').forEach(function(block) {
    block.addEventListener('click', function() {
      var wasActive = this.classList.contains('active');
      document.querySelectorAll('.tp-sample-block').forEach(function(b) {
        b.classList.remove('active');
      });
      if (wasActive) {
        sampleDetail.style.display = 'none';
      } else {
        this.classList.add('active');
        var html = '';
        if (this.dataset.structure) {
          html += buildWorkoutViz(this.dataset.structure, this.dataset.meta || '');
        }
        html += '<div>' + this.dataset.detail + '</div>';
        sampleDetail.innerHTML = html;
        sampleDetail.style.display = 'block';
      }
    });
  });

  // ---- Flip Cards (touch support) ----
  document.querySelectorAll('.tp-flip-card').forEach(function(card) {
    card.addEventListener('click', function() {
      this.classList.toggle('flipped');
    });
  });

  // ---- FORM LOGIC (from training-plan-form-full.html) ----

  var WORKER_URL = 'https://training-plan-intake.gravelgodcoaching.workers.dev';
  var form = document.getElementById('gg-training-form');
  var messageEl = document.getElementById('gg-form-message');
  var submitBtn = form.querySelector('.gg-submit-btn');
  var racesContainer = document.getElementById('races-container');
  var addRaceBtn = document.getElementById('add-race-btn');

  var raceCount = 0;
  var MAX_RACES = 10;

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

  // Power/HR toggle
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

  // W/kg calculation
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

  // Show menstrual cycle fields when sex = female
  var cycleRow = document.getElementById('cycle-row');
  if (sexSelect && cycleRow) {
    sexSelect.addEventListener('change', function() {
      cycleRow.style.display = this.value === 'female' ? 'flex' : 'none';
    });
  }

  // Flexible checkbox logic
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

  // Form submission
  form.addEventListener('submit', async function(e) {
    e.preventDefault();
    var races = getRaces();
    if (races.length === 0) {
      messageEl.className = 'gg-form-message error';
      messageEl.textContent = 'Please add at least one race.';
      messageEl.style.display = 'block';
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting...';
    messageEl.style.display = 'none';

    var formData = new FormData(form);
    var data = Object.fromEntries(formData.entries());

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

    data.blindspots = identifyBlindspots(data);
    data._source = 'gravelgodcycling.com/training-plans';

    try {
      var response = await fetch(WORKER_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      var result = await response.json();
      if (result.success) {
        messageEl.className = 'gg-form-message success';
        messageEl.textContent = result.message;
        form.reset();
        racesContainer.innerHTML = '';
        raceCount = 0;
        addRace();
        powerFields.style.display = 'none';
        hrFields.style.display = 'none';
        pwCalc.style.display = 'none';
      } else {
        throw new Error(result.error || 'Submission failed');
      }
    } catch (error) {
      messageEl.className = 'gg-form-message error';
      messageEl.textContent = error.message || 'Something went wrong. Please try again.';
    }

    messageEl.style.display = 'block';
    submitBtn.disabled = false;
    submitBtn.textContent = 'Submit & Build My Plan';
    messageEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });
})();
