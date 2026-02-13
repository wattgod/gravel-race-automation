(function() {
  const DATA_URL = '/wp-content/uploads/race-index.json';
  const TIER_PAGE_SIZE = 20;

  let allRaces = [];
  let currentSort = 'score';
  let displayMode = 'tiers'; // 'tiers' or 'match'
  let matchScores = {};      // slug → match pct
  let tierVisibleCounts = { 1: TIER_PAGE_SIZE, 2: TIER_PAGE_SIZE, 3: TIER_PAGE_SIZE, 4: TIER_PAGE_SIZE };
  let tierCollapsed = { 1: false, 2: false, 3: true, 4: true };

  // Near Me state
  let userLat = null;
  let userLng = null;
  let nearMeRadius = 0; // 0 = off, otherwise miles
  let raceDistances = {}; // slug → distance in miles

  // Compare state
  let compareSlugs = [];    // Array of slug strings, max 4
  let compareMode = false;  // true when showing compare panel

  var COMPARE_COLORS = [
    { stroke: '#59473c', fill: 'rgba(89,71,60,0.15)' },
    { stroke: '#178079', fill: 'rgba(23,128,121,0.15)' },
    { stroke: '#9a7e0a', fill: 'rgba(154,126,10,0.15)' },
    { stroke: '#766a5e', fill: 'rgba(118,106,94,0.15)' }
  ];

  // Map state
  let mapInstance = null;
  let mapMarkers = [];
  let viewMode = 'list'; // 'list' or 'map'
  let leafletLoaded = false;

  const TIER_NAMES = { 1: 'Elite', 2: 'Contender', 3: 'Solid', 4: 'Roster' };
  const TIER_DESCS = {
    1: 'The definitive gravel events. World-class fields, iconic courses, bucket-list status.',
    2: 'Established races with strong reputations and competitive fields. The next tier of must-do events.',
    3: 'Regional favorites and emerging races. Strong local scenes, genuine gravel character.',
    4: 'Up-and-coming races and local grinders. Grassroots gravel — small fields, raw vibes.'
  };
  const US_REGIONS = new Set(['West', 'Midwest', 'South', 'Northeast']);
  const TIER_COLORS_MAP = { 1: '#59473c', 2: '#7d695d', 3: '#766a5e', 4: '#5e6868' };

  const SLIDERS = [
    { key: 'distance',      label: 'Distance',      low: 'Quick Spin',       high: 'Ultra Endurance', mapping: [{ field: 'length', weight: 1.0 }] },
    { key: 'technicality',  label: 'Technicality',   low: 'Smooth Gravel',    high: 'Single Track',    mapping: [{ field: 'technicality', weight: 1.0 }] },
    { key: 'climbing',      label: 'Climbing',       low: 'Flat is Fast',     high: 'Mountain Goat',   mapping: [{ field: 'elevation', weight: 1.0 }] },
    { key: 'adventure',     label: 'Adventure',      low: 'Close to Town',    high: 'Deep Backcountry',mapping: [{ field: 'adventure', weight: 0.6 }, { field: 'logistics', weight: 0.4 }] },
    { key: 'competition',   label: 'Competition',    low: 'Just Finish',      high: 'Pro Field',       mapping: [{ field: 'field_depth', weight: 0.6 }, { field: 'race_quality', weight: 0.4 }] },
    { key: 'prestige',      label: 'Prestige',       low: 'Hidden Gem',       high: 'Bucket List',     mapping: [{ field: 'prestige', weight: 1.0 }] },
    { key: 'budget',        label: 'Budget',         low: 'All-In',           high: 'Budget Friendly', mapping: [{ field: 'value', weight: 0.6 }, { field: 'expenses', weight: 0.4, invert: true }] }
  ];

  function noResultsHtml() {
    return '<div class="gg-no-results">No races match your filters.' +
      '<div class="gg-no-results-suggestions">Try removing a filter, selecting a different region, or choosing &ldquo;Any&rdquo; for month.<br>' +
      '<button class="gg-no-results-reset" onclick="document.querySelectorAll(\'#gg-race-search select\').forEach(function(s){s.selectedIndex=0});' +
      'document.querySelectorAll(\'#gg-race-search .gg-slider-input\').forEach(function(s){s.value=3});' +
      'window.dispatchEvent(new Event(\'gg-reset-filters\'));">Reset All Filters</button></div></div>';
  }

  // ── Haversine distance (miles) ──
  function haversineMi(lat1, lng1, lat2, lng2) {
    var R = 3959; // Earth radius in miles
    var dLat = (lat2 - lat1) * Math.PI / 180;
    var dLng = (lng2 - lng1) * Math.PI / 180;
    var a = Math.sin(dLat/2) * Math.sin(dLat/2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLng/2) * Math.sin(dLng/2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  function computeDistances() {
    raceDistances = {};
    if (userLat === null) return;
    allRaces.forEach(function(r) {
      if (r.lat != null && r.lng != null) {
        raceDistances[r.slug] = Math.round(haversineMi(userLat, userLng, r.lat, r.lng));
      }
    });
  }

  // ── Init ──
  function fetchWithRetry(url, attempts, delay) {
    return fetch(url).then(function(r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }).catch(function(err) {
      if (attempts <= 1) throw err;
      return new Promise(function(resolve) {
        setTimeout(function() { resolve(fetchWithRetry(url, attempts - 1, delay * 2)); }, delay);
      });
    });
  }

  function init() {
    buildSliders();
    fetchWithRetry(DATA_URL, 3, 1000)
      .then(function(data) {
        allRaces = data;
        populateFilterOptions();
        loadFromURL();
        // Validate compare slugs against loaded data
        var validSlugs = {};
        allRaces.forEach(function(r) { validSlugs[r.slug] = true; });
        compareSlugs = compareSlugs.filter(function(s) { return validSlugs[s]; });
        if (compareSlugs.length < 2) compareMode = false;
        render();
        bindEvents();
      })
      .catch(function(err) {
        document.getElementById('gg-tier-container').innerHTML =
          '<div class="gg-no-results">Unable to load race data. Please refresh the page or try again later.</div>';
        console.error('Race index load failed after retries:', err);
      });
  }

  // ── Questionnaire sliders ──
  function buildSliders() {
    var grid = document.getElementById('gg-slider-grid');
    grid.innerHTML = SLIDERS.map(function(s) { return '\
      <div class="gg-slider-row">\
        <span class="gg-slider-label">' + s.label + '</span>\
        <input type="range" min="1" max="5" value="3" id="gg-q-' + s.key + '" aria-label="' + s.label + ': ' + s.low + ' to ' + s.high + '">\
        <div class="gg-slider-endpoints">\
          <span>' + s.low + '</span>\
          <span>' + s.high + '</span>\
        </div>\
      </div>';
    }).join('');
  }

  function getSliderValues() {
    var vals = {};
    SLIDERS.forEach(function(s) {
      vals[s.key] = parseInt(document.getElementById('gg-q-' + s.key).value);
    });
    return vals;
  }

  function computeMatchScore(race, sliderVals) {
    if (!race.scores) return 0;
    var weightedSqDiff = 0;
    var totalWeight = 0;
    SLIDERS.forEach(function(s) {
      var userVal = sliderVals[s.key];
      s.mapping.forEach(function(m) {
        var raceVal = race.scores[m.field] || 1;
        if (m.invert) raceVal = 6 - raceVal;
        var diff = userVal - raceVal;
        weightedSqDiff += m.weight * diff * diff;
        totalWeight += m.weight;
      });
    });
    var maxPossible = totalWeight * 16;
    return Math.round((1 - weightedSqDiff / maxPossible) * 100);
  }

  // ── Match mode ──
  function runMatch() {
    var vals = getSliderValues();
    matchScores = {};
    allRaces.forEach(function(r) {
      matchScores[r.slug] = computeMatchScore(r, vals);
    });
    displayMode = 'match';
    document.getElementById('gg-btn-reset').style.display = '';
    render();
    saveToURL();
  }
  window.runMatch = runMatch;

  function resetMatch() {
    displayMode = 'tiers';
    matchScores = {};
    document.getElementById('gg-btn-reset').style.display = 'none';
    tierVisibleCounts = { 1: TIER_PAGE_SIZE, 2: TIER_PAGE_SIZE, 3: TIER_PAGE_SIZE, 4: TIER_PAGE_SIZE };
    render();
    saveToURL();
  }
  window.resetMatch = resetMatch;

  // ── Questionnaire toggle ──
  function toggleQuestionnaire() {
    var body = document.getElementById('gg-q-body');
    var toggle = document.getElementById('gg-q-toggle');
    body.classList.toggle('collapsed');
    toggle.classList.toggle('collapsed');
  }
  window.toggleQuestionnaire = toggleQuestionnaire;

  // ── Near Me ──
  function activateNearMe() {
    var btn = document.getElementById('gg-nearme-btn');
    if (!btn) return;

    if (userLat !== null) {
      // Already have location — toggle off
      userLat = null;
      userLng = null;
      nearMeRadius = 0;
      raceDistances = {};
      btn.classList.remove('active');
      btn.textContent = 'NEAR ME';
      var radiusSel = document.getElementById('gg-nearme-radius');
      if (radiusSel) radiusSel.style.display = 'none';
      currentSort = 'score';
      updateSortButtons();
      render();
      saveToURL();
      return;
    }

    if (!navigator.geolocation) {
      btn.textContent = 'NOT SUPPORTED';
      btn.disabled = true;
      return;
    }

    btn.textContent = 'LOCATING...';
    btn.disabled = true;

    navigator.geolocation.getCurrentPosition(
      function(pos) {
        userLat = pos.coords.latitude;
        userLng = pos.coords.longitude;
        nearMeRadius = 500; // default radius
        computeDistances();
        btn.classList.add('active');
        btn.textContent = 'NEAR ME ✓';
        btn.disabled = false;
        var radiusSel = document.getElementById('gg-nearme-radius');
        if (radiusSel) {
          radiusSel.style.display = '';
          radiusSel.value = '500';
        }
        currentSort = 'nearby';
        updateSortButtons();
        render();
        saveToURL();
      },
      function(err) {
        btn.textContent = 'DENIED';
        btn.disabled = false;
        setTimeout(function() {
          btn.textContent = 'NEAR ME';
        }, 2000);
        console.warn('Geolocation denied:', err.message);
      },
      { timeout: 10000, maximumAge: 300000 }
    );
  }
  window.activateNearMe = activateNearMe;

  function onRadiusChange() {
    var sel = document.getElementById('gg-nearme-radius');
    nearMeRadius = parseInt(sel.value) || 0;
    render();
    saveToURL();
  }
  window.onRadiusChange = onRadiusChange;

  function updateSortButtons() {
    document.querySelectorAll('.gg-sort-btn').forEach(function(b) {
      b.classList.toggle('active', b.dataset.sort === currentSort);
    });
  }

  // ── Map ──
  function loadLeaflet(callback) {
    if (leafletLoaded) { callback(); return; }
    var css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    document.head.appendChild(css);
    var js = document.createElement('script');
    js.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    js.onload = function() { leafletLoaded = true; callback(); };
    document.head.appendChild(js);
  }

  function initMap() {
    if (mapInstance) return;
    var container = document.getElementById('gg-map-container');
    if (!container) return;
    mapInstance = L.map(container, { scrollWheelZoom: true, zoomControl: true }).setView([30, 0], 2);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18
    }).addTo(mapInstance);
  }

  function updateMapMarkers() {
    if (!mapInstance) return;
    mapMarkers.forEach(function(m) { mapInstance.removeLayer(m); });
    mapMarkers = [];
    var filtered = sortRaces(filterRaces());
    filtered.forEach(function(race) {
      if (race.lat == null || race.lng == null) return;
      var tierColor = TIER_COLORS_MAP[race.tier] || '#5e6868';
      var marker = L.circleMarker([race.lat, race.lng], {
        radius: race.tier === 1 ? 8 : race.tier === 2 ? 7 : 6,
        fillColor: tierColor,
        color: '#1a1613',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.85
      });
      var popupHtml = '<div class="gg-map-popup">' +
        '<p class="gg-popup-name">' +
          (race.has_profile
            ? '<a href="' + race.profile_url + '">' + race.name + '</a>'
            : race.name) +
        '</p>' +
        '<p class="gg-popup-meta">' + (race.location || '') +
          (race.month ? ' &middot; ' + race.month : '') + '</p>' +
        '<p class="gg-popup-stats">' +
          (race.overall_score ? '<span class="gg-popup-score">' + race.overall_score + '</span>' : '') +
          (race.distance_mi ? race.distance_mi + ' mi' : '') +
          (race.distance_mi && race.elevation_ft ? ' &middot; ' : '') +
          (race.elevation_ft ? Number(race.elevation_ft).toLocaleString() + ' ft' : '') +
        '</p>' +
        (userLat !== null && raceDistances[race.slug] !== undefined
          ? '<p class="gg-popup-meta">' + raceDistances[race.slug].toLocaleString() + ' mi away</p>'
          : '') +
        (race.rwgps_id
          ? '<p class="gg-popup-route"><a href="https://ridewithgps.com/routes/' + race.rwgps_id + '" target="_blank" rel="noopener">View Route &#x2197;</a></p>'
          : '') +
      '</div>';
      marker.bindPopup(popupHtml, { maxWidth: 280 });
      marker.addTo(mapInstance);
      mapMarkers.push(marker);
    });
  }

  // ── Calendar ──
  var MONTH_NAMES = ['January','February','March','April','May','June',
                     'July','August','September','October','November','December'];

  function renderCalendar() {
    var calContainer = document.getElementById('gg-calendar-container');
    if (!calContainer) return;
    var filtered = sortRaces(filterRaces());
    var byMonth = {};
    MONTH_NAMES.forEach(function(m) { byMonth[m] = []; });
    filtered.forEach(function(r) {
      if (r.month && byMonth[r.month]) byMonth[r.month].push(r);
    });
    var noMonth = filtered.filter(function(r) { return !r.month; });
    var currentMonth = MONTH_NAMES[new Date().getMonth()];
    var html = '';
    MONTH_NAMES.forEach(function(m) {
      var races = byMonth[m];
      if (races.length === 0) return;
      var isCurrent = (m === currentMonth);
      html += '<div class="gg-cal-month' + (isCurrent ? ' gg-cal-now' : '') + '" id="gg-cal-' + m.toLowerCase() + '">' +
        '<div class="gg-cal-month-header">' +
          '<span>' + m.toUpperCase() + '</span>' +
          '<span class="gg-cal-month-count">' + races.length + ' race' + (races.length !== 1 ? 's' : '') + '</span>' +
        '</div>';
      races.forEach(function(r) {
        var nameTag = r.has_profile
          ? '<a class="gg-cal-name" href="' + r.profile_url + '">' + r.name + '</a>'
          : '<span class="gg-cal-name">' + r.name + '</span>';
        var distBadge = '';
        if (userLat !== null && raceDistances[r.slug] !== undefined) {
          distBadge = ' <span class="gg-distance-badge">' + raceDistances[r.slug].toLocaleString() + ' mi</span>';
        }
        html += '<div class="gg-cal-race">' +
          '<span class="gg-tier-badge gg-tier-' + r.tier + '">T' + r.tier + '</span>' +
          '<div class="gg-cal-info">' + nameTag + '<div class="gg-cal-loc">' + (r.location || '') +
            (r.distance_mi ? ' &middot; ' + r.distance_mi + ' mi' : '') + distBadge + '</div></div>' +
          (r.overall_score ? '<span class="gg-cal-score">' + r.overall_score + '</span>' : '') +
        '</div>';
      });
      html += '</div>';
    });
    if (noMonth.length > 0) {
      html += '<div class="gg-cal-month"><div class="gg-cal-month-header"><span>DATE TBD</span>' +
        '<span class="gg-cal-month-count">' + noMonth.length + ' race' + (noMonth.length !== 1 ? 's' : '') + '</span></div>';
      noMonth.forEach(function(r) {
        var nameTag = r.has_profile
          ? '<a class="gg-cal-name" href="' + r.profile_url + '">' + r.name + '</a>'
          : '<span class="gg-cal-name">' + r.name + '</span>';
        html += '<div class="gg-cal-race">' +
          '<span class="gg-tier-badge gg-tier-' + r.tier + '">T' + r.tier + '</span>' +
          '<div class="gg-cal-info">' + nameTag + '<div class="gg-cal-loc">' + (r.location || '') + '</div></div>' +
          (r.overall_score ? '<span class="gg-cal-score">' + r.overall_score + '</span>' : '') +
        '</div>';
      });
      html += '</div>';
    }
    if (!html) html = noResultsHtml();
    calContainer.setAttribute('role', 'region');
    calContainer.setAttribute('aria-label', 'Race calendar by month');
    calContainer.innerHTML = html;
    // Scroll to current month
    var curEl = document.getElementById('gg-cal-' + currentMonth.toLowerCase());
    if (curEl) curEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function toggleView(mode) {
    viewMode = mode;
    document.querySelectorAll('.gg-view-btn').forEach(function(b) {
      b.classList.toggle('active', b.dataset.view === mode);
    });
    var mapContainer = document.getElementById('gg-map-container');
    var tierContainer = document.getElementById('gg-tier-container');
    var calContainer = document.getElementById('gg-calendar-container');
    mapContainer.classList.remove('visible');
    tierContainer.style.display = 'none';
    if (calContainer) calContainer.style.display = 'none';
    if (mode === 'map') {
      mapContainer.classList.add('visible');
      loadLeaflet(function() {
        initMap();
        updateMapMarkers();
        setTimeout(function() { mapInstance.invalidateSize(); }, 100);
      });
    } else if (mode === 'calendar') {
      if (calContainer) { calContainer.style.display = ''; renderCalendar(); }
    } else {
      tierContainer.style.display = '';
    }
  }
  window.toggleView = toggleView;

  // ── URL state ──
  function loadFromURL() {
    var params = new URLSearchParams(window.location.search);
    if (params.get('q')) document.getElementById('gg-search').value = params.get('q');
    if (params.get('tier')) document.getElementById('gg-tier').value = params.get('tier');
    if (params.get('region')) document.getElementById('gg-region').value = params.get('region');
    if (params.get('distance')) document.getElementById('gg-distance').value = params.get('distance');
    if (params.get('month')) document.getElementById('gg-month').value = params.get('month');
    if (params.get('profile')) document.getElementById('gg-profile').value = params.get('profile');
    if (params.get('sort')) currentSort = params.get('sort');

    // Restore match mode from URL
    if (params.get('match') === '1') {
      SLIDERS.forEach(function(s) {
        var val = params.get('q_' + s.key);
        if (val) document.getElementById('gg-q-' + s.key).value = val;
      });
      displayMode = 'match';
      document.getElementById('gg-btn-reset').style.display = '';
    }

    // Restore near me from URL (triggers geolocation)
    if (params.get('nearme') === '1') {
      var r = parseInt(params.get('radius'));
      if (r) nearMeRadius = r;
      // Auto-trigger geolocation
      setTimeout(function() { activateNearMe(); }, 100);
    }

    // Restore compare state from URL
    var cmpParam = params.get('compare');
    if (cmpParam) compareSlugs = cmpParam.split(',').filter(Boolean);
    if (params.get('cmp') === '1' && compareSlugs.length >= 2) compareMode = true;

    // Restore view mode from URL
    var urlView = params.get('view');
    if (urlView === 'map' || urlView === 'calendar') {
      setTimeout(function() { toggleView(urlView); }, 150);
    }
  }

  function saveToURL() {
    var f = getFilters();
    var params = new URLSearchParams();
    if (f.search) params.set('q', f.search);
    if (f.tier) params.set('tier', f.tier);
    if (f.region) params.set('region', f.region);
    if (f.distance) params.set('distance', f.distance);
    if (f.month) params.set('month', f.month);
    if (f.profile) params.set('profile', f.profile);
    if (currentSort !== 'score') params.set('sort', currentSort);

    if (displayMode === 'match') {
      params.set('match', '1');
      SLIDERS.forEach(function(s) {
        var val = document.getElementById('gg-q-' + s.key).value;
        if (val !== '3') params.set('q_' + s.key, val);
      });
    }

    if (userLat !== null) {
      params.set('nearme', '1');
      if (nearMeRadius && nearMeRadius !== 500) params.set('radius', nearMeRadius);
    }

    if (viewMode && viewMode !== 'list') params.set('view', viewMode);

    if (compareSlugs.length > 0) params.set('compare', compareSlugs.join(','));
    if (compareMode) params.set('cmp', '1');

    var newURL = params.toString()
      ? window.location.pathname + '?' + params.toString()
      : window.location.pathname;
    window.history.replaceState({}, '', newURL);
  }

  // ── Filter helpers ──
  function countByFilter(filterKey, filterValue) {
    return allRaces.filter(function(r) {
      if (filterKey === 'tier') return r.tier == filterValue;
      if (filterKey === 'region') return r.region === filterValue;
      if (filterKey === 'month') return r.month === filterValue;
      if (filterKey === 'profile') {
        if (filterValue === 'yes') return r.has_profile;
        if (filterValue === 'no') return !r.has_profile;
      }
      if (filterKey === 'distance') {
        var parts = filterValue.split('-').map(Number);
        var d = r.distance_mi || 0;
        return d >= parts[0] && d <= parts[1];
      }
      return true;
    }).length;
  }

  function populateFilterOptions() {
    var tierSel = document.getElementById('gg-tier');
    tierSel.innerHTML = '<option value="">All Tiers</option>';
    [1, 2, 3, 4].forEach(function(t) {
      var count = countByFilter('tier', t);
      var opt = document.createElement('option');
      opt.value = t; opt.textContent = 'Tier ' + t + ' (' + count + ')';
      tierSel.appendChild(opt);
    });

    var regions = [];
    var seen = {};
    allRaces.forEach(function(r) {
      if (r.region && !seen[r.region]) { seen[r.region] = true; regions.push(r.region); }
    });
    regions.sort();
    var regionSel = document.getElementById('gg-region');
    regionSel.innerHTML = '<option value="">All Regions</option>';
    // Add "International" meta-region (all non-US regions)
    var intlCount = allRaces.filter(function(r) { return r.region && !US_REGIONS.has(r.region); }).length;
    if (intlCount > 0) {
      var intlOpt = document.createElement('option');
      intlOpt.value = 'International'; intlOpt.textContent = 'International (' + intlCount + ')';
      regionSel.appendChild(intlOpt);
    }
    regions.forEach(function(r) {
      var count = countByFilter('region', r);
      var opt = document.createElement('option');
      opt.value = r; opt.textContent = r + ' (' + count + ')';
      regionSel.appendChild(opt);
    });

    var distSel = document.getElementById('gg-distance');
    distSel.innerHTML = '<option value="">Any Distance</option>';
    [['0-50', 'Under 50 mi'], ['50-100', '50-100 mi'], ['100-200', '100-200 mi'], ['200-999', '200+ mi']].forEach(function(pair) {
      var count = countByFilter('distance', pair[0]);
      var opt = document.createElement('option');
      opt.value = pair[0]; opt.textContent = pair[1] + ' (' + count + ')';
      distSel.appendChild(opt);
    });

    var months = ['January','February','March','April','May','June',
                  'July','August','September','October','November','December'];
    var monthSel = document.getElementById('gg-month');
    monthSel.innerHTML = '<option value="">Any Month</option>';
    months.forEach(function(m) {
      var count = countByFilter('month', m);
      if (count > 0) {
        var opt = document.createElement('option');
        opt.value = m; opt.textContent = m + ' (' + count + ')';
        monthSel.appendChild(opt);
      }
    });

    var profSel = document.getElementById('gg-profile');
    profSel.innerHTML = '<option value="">All</option>';
    var withProfile = countByFilter('profile', 'yes');
    var noProfile = countByFilter('profile', 'no');
    profSel.innerHTML += '<option value="yes">Has Profile (' + withProfile + ')</option>';
    profSel.innerHTML += '<option value="no">No Profile (' + noProfile + ')</option>';
  }

  function getFilters() {
    var search = document.getElementById('gg-search').value.toLowerCase();
    var tier = document.getElementById('gg-tier').value;
    var region = document.getElementById('gg-region').value;
    var distance = document.getElementById('gg-distance').value;
    var month = document.getElementById('gg-month').value;
    var profile = document.getElementById('gg-profile').value;
    return { search: search, tier: tier, region: region, distance: distance, month: month, profile: profile };
  }

  function filterRaces() {
    var f = getFilters();
    return allRaces.filter(function(r) {
      if (f.search && !r.name.toLowerCase().includes(f.search) &&
          !(r.location || '').toLowerCase().includes(f.search)) return false;
      if (f.tier && r.tier != f.tier) return false;
      if (f.region === 'International' && (!r.region || US_REGIONS.has(r.region))) return false;
      if (f.region && f.region !== 'International' && r.region !== f.region) return false;
      if (f.month && r.month !== f.month) return false;
      if (f.profile === 'yes' && !r.has_profile) return false;
      if (f.profile === 'no' && r.has_profile) return false;
      if (f.distance) {
        var parts = f.distance.split('-').map(Number);
        var d = r.distance_mi || 0;
        if (d < parts[0] || d > parts[1]) return false;
      }
      // Near Me radius filter
      if (userLat !== null && nearMeRadius > 0) {
        var dist = raceDistances[r.slug];
        if (dist === undefined || dist > nearMeRadius) return false;
      }
      return true;
    });
  }

  function sortRaces(races) {
    var sorted = races.slice();
    switch(currentSort) {
      case 'score':
        sorted.sort(function(a, b) { return (b.overall_score || 0) - (a.overall_score || 0); });
        break;
      case 'name':
        sorted.sort(function(a, b) { return a.name.localeCompare(b.name); });
        break;
      case 'distance':
        sorted.sort(function(a, b) { return (b.distance_mi || 0) - (a.distance_mi || 0); });
        break;
      case 'nearby':
        sorted.sort(function(a, b) { return (raceDistances[a.slug] || 99999) - (raceDistances[b.slug] || 99999); });
        break;
    }
    return sorted;
  }

  // ── Score / rendering helpers ──
  function scoreColor(score) {
    if (score >= 85) return '#3a2e25';
    if (score >= 75) return '#59473c';
    if (score >= 65) return '#7d695d';
    return '#5e6868';
  }

  var SCORE_LABELS = {
    logistics: 'Logistics', length: 'Length', technicality: 'Technicality',
    elevation: 'Elevation', climate: 'Climate', altitude: 'Altitude',
    adventure: 'Adventure', prestige: 'Prestige', race_quality: 'Race Quality',
    experience: 'Experience', community: 'Community', field_depth: 'Field Depth',
    value: 'Value', expenses: 'Expenses'
  };

  function renderScoreBreakdown(scores) {
    if (!scores || Object.keys(scores).length < 7) return '';
    var rows = Object.entries(SCORE_LABELS).map(function(pair) {
      var key = pair[0], label = pair[1];
      var val = scores[key] || 0;
      var dots = Array.from({length: 5}, function(_, i) {
        return '<span class="gg-score-dot' + (i < val ? ' filled' : '') + '"></span>';
      }).join('');
      return '<div class="gg-score-row"><span class="gg-score-row-label">' + label + '</span><span class="gg-score-row-dots">' + dots + '</span></div>';
    }).join('');
    return '<div class="gg-score-breakdown"><div class="gg-score-grid">' + rows + '</div></div>';
  }

  function radarPoints(scores, vars, cx, cy, r) {
    var n = vars.length;
    return vars.map(function(v, i) {
      var val = (scores[v] || 1) / 5;
      var angle = (Math.PI * 2 * i / n) - Math.PI / 2;
      return [cx + r * val * Math.cos(angle), cy + r * val * Math.sin(angle)];
    });
  }

  function renderMiniRadar(scores) {
    if (!scores || Object.keys(scores).length < 7) return '';
    var vars = ['length','technicality','elevation','climate','altitude','logistics','adventure'];
    var cx = 40, cy = 40, r = 30;
    var n = vars.length;
    var points = radarPoints(scores, vars, cx, cy, r);
    var poly = points.map(function(p) { return p.join(','); }).join(' ');
    var grid = [0.2, 0.4, 0.6, 0.8, 1.0].map(function(s) {
      var gp = Array.from({length: n}, function(_, i) {
        var angle = (Math.PI * 2 * i / n) - Math.PI / 2;
        return [cx + r * s * Math.cos(angle), cy + r * s * Math.sin(angle)];
      });
      return '<polygon points="' + gp.map(function(p){return p.join(',');}).join(' ') + '" fill="none" stroke="#d4c5b9" stroke-width="0.5"/>';
    }).join('');
    return '<svg class="gg-radar" width="80" height="80" viewBox="0 0 80 80">' +
      grid +
      '<polygon points="' + poly + '" fill="rgba(26,138,130,0.12)" stroke="#3a2e25" stroke-width="1.5"/>' +
    '</svg>';
  }

  function renderCard(race) {
    var nameTag = race.has_profile
      ? '<a class="gg-card-name" href="' + race.profile_url + '">' + race.name + '</a>'
      : '<span class="gg-card-name no-link">' + race.name + '</span>';

    var breakdown = renderScoreBreakdown(race.scores);
    var scoreBar = race.overall_score
      ? '<div class="gg-score-bar" onclick="this.nextElementSibling&&this.nextElementSibling.classList.toggle(\'open\')" title="Click for score breakdown">' +
          '<div class="gg-score-track">' +
            '<div class="gg-score-fill" style="width:' + race.overall_score + '%;background:' + scoreColor(race.overall_score) + '"></div>' +
          '</div>' +
          '<span class="gg-score-num">' + race.overall_score + '</span>' +
        '</div>' + breakdown
      : '';

    var radar = renderMiniRadar(race.scores);

    var matchBadge = (displayMode === 'match' && matchScores[race.slug] !== undefined)
      ? '<span class="gg-match-badge">' + matchScores[race.slug] + '% match</span>'
      : '';

    var distBadge = '';
    if (userLat !== null && raceDistances[race.slug] !== undefined) {
      distBadge = '<span class="gg-distance-badge">' + raceDistances[race.slug].toLocaleString() + ' mi away</span>';
    }

    var compareCheck = '<label class="gg-compare-check" title="Add to compare">' +
      '<input type="checkbox" data-slug="' + race.slug + '" onchange="toggleCompare(this.dataset.slug,this.checked)"' +
        (compareSlugs.indexOf(race.slug) !== -1 ? ' checked' : '') + '>' +
      '<span class="gg-compare-check-box"></span>' +
    '</label>';

    return '<div class="gg-card">' +
      '<div class="gg-card-header">' +
        compareCheck +
        nameTag +
        '<div style="display:flex;gap:6px;align-items:center">' +
          matchBadge +
          distBadge +
          '<span class="gg-tier-badge gg-tier-' + race.tier + '">TIER ' + race.tier + '</span>' +
        '</div>' +
      '</div>' +
      '<div class="gg-card-meta">' + (race.location || 'Location TBD') + (race.month ? ' &middot; ' + race.month : '') + '</div>' +
      '<div class="gg-card-stats">' +
        (race.distance_mi ? '<div class="gg-stat"><span class="gg-stat-val">' + race.distance_mi + '</span><span class="gg-stat-label">Miles</span></div>' : '') +
        (race.elevation_ft ? '<div class="gg-stat"><span class="gg-stat-val">' + Number(race.elevation_ft).toLocaleString() + '</span><span class="gg-stat-label">Ft Elev</span></div>' : '') +
      '</div>' +
      scoreBar +
      radar +
      (race.tagline ? '<div class="gg-card-tagline">' + race.tagline + '</div>' : '') +
    '</div>';
  }

  // ── Tier grouping ──
  function groupByTier(races) {
    var groups = { 1: [], 2: [], 3: [], 4: [] };
    races.forEach(function(r) {
      var t = r.tier || 4;
      if (groups[t]) groups[t].push(r);
    });
    return groups;
  }

  function renderTierSections(filtered) {
    var groups = groupByTier(filtered);
    var container = document.getElementById('gg-tier-container');
    var html = '';

    [1, 2, 3, 4].forEach(function(t) {
      var races = groups[t];
      if (races.length === 0) return;

      var collapsed = tierCollapsed[t];
      var visible = races.slice(0, tierVisibleCounts[t]);
      var remaining = races.length - visible.length;

      html += '<div class="gg-tier-section">' +
        '<button class="gg-tier-section-header tier-' + t + '" onclick="toggleTier(' + t + ')" aria-expanded="' + (!collapsed) + '" aria-controls="gg-tier-body-' + t + '">' +
          '<div class="gg-tier-section-title">' +
            '<span class="gg-tier-badge gg-tier-' + t + '">TIER ' + t + '</span>' +
            '<h3><a href="/race/tier-' + t + '/" onclick="event.stopPropagation()" class="gg-tier-name-link">' + TIER_NAMES[t] + '</a></h3>' +
            '<span class="gg-tier-section-count">' + races.length + ' race' + (races.length !== 1 ? 's' : '') + '</span>' +
          '</div>' +
          '<p class="gg-tier-section-desc">' + TIER_DESCS[t] + '</p>' +
          '<span class="gg-tier-section-chevron' + (collapsed ? ' collapsed' : '') + '">▾</span>' +
        '</button>' +
        '<div class="gg-tier-section-body' + (collapsed ? ' collapsed' : '') + '" id="gg-tier-body-' + t + '">' +
          '<div class="gg-grid">' + visible.map(renderCard).join('') + '</div>' +
          (remaining > 0 ? '<button class="gg-load-more" onclick="loadMoreTier(' + t + ')">Show ' + Math.min(remaining, TIER_PAGE_SIZE) + ' more of ' + remaining + ' remaining</button>' : '') +
        '</div>' +
      '</div>';
    });

    if (!html) {
      html = noResultsHtml();
    }
    container.innerHTML = html;
  }

  function renderMatchResults(filtered) {
    var sorted = filtered.slice().sort(function(a, b) { return (matchScores[b.slug] || 0) - (matchScores[a.slug] || 0); });
    var container = document.getElementById('gg-tier-container');

    var html = '<div class="gg-match-banner">' +
      '<span>Showing results ranked by match score</span>' +
      '<button onclick="resetMatch()">Back to Tiers</button>' +
    '</div>';

    if (sorted.length > 0) {
      html += '<div class="gg-grid">' + sorted.map(renderCard).join('') + '</div>';
    } else {
      html += noResultsHtml();
    }
    container.innerHTML = html;
  }

  function toggleTier(t) {
    tierCollapsed[t] = !tierCollapsed[t];
    render(false);
  }
  window.toggleTier = toggleTier;

  function loadMoreTier(t) {
    tierVisibleCounts[t] += TIER_PAGE_SIZE;
    render(false);
  }
  window.loadMoreTier = loadMoreTier;

  // ── Active filter pills ──
  function renderActivePills() {
    var f = getFilters();
    var container = document.getElementById('gg-active-filters');
    var pills = [];

    var distLabels = { '0-50': 'Under 50 mi', '50-100': '50-100 mi', '100-200': '100-200 mi', '200-999': '200+ mi' };
    var filterLabels = {
      search: f.search ? '"' + f.search + '"' : null,
      tier: f.tier ? 'Tier ' + f.tier : null,
      region: f.region || null,
      distance: f.distance ? distLabels[f.distance] : null,
      month: f.month || null,
      profile: f.profile ? (f.profile === 'yes' ? 'Has Profile' : 'No Profile') : null
    };

    // Add near me pill
    if (userLat !== null) {
      pills.push('<span class="gg-filter-pill">Near Me (' + nearMeRadius + ' mi)<button onclick="activateNearMe()">×</button></span>');
    }

    Object.entries(filterLabels).forEach(function(pair) {
      var key = pair[0], label = pair[1];
      if (label) {
        var inputId = key === 'search' ? 'gg-search' : 'gg-' + key;
        pills.push('<span class="gg-filter-pill">' + label + '<button onclick="document.getElementById(\'' + inputId + '\').value=\'\';document.getElementById(\'' + inputId + '\').dispatchEvent(new Event(\'change\'))">×</button></span>');
      }
    });

    if (pills.length > 1) {
      pills.push('<button class="gg-clear-all" onclick="clearAllFilters()">Clear all</button>');
    }

    container.innerHTML = pills.join('');
  }

  // ── Compare functions ──
  function toggleCompare(slug, checked) {
    if (checked && compareSlugs.indexOf(slug) === -1) {
      if (compareSlugs.length >= 4) {
        updateCompareCheckboxes();
        return;
      }
      compareSlugs.push(slug);
    } else if (!checked) {
      compareSlugs = compareSlugs.filter(function(s) { return s !== slug; });
    }
    if (compareMode && compareSlugs.length < 2) {
      compareMode = false;
      render();
      return;
    }
    updateCompareBar();
    updateCompareCheckboxes();
    saveToURL();
  }
  window.toggleCompare = toggleCompare;

  function clearCompare() {
    compareSlugs = [];
    compareMode = false;
    updateCompareBar();
    render();
  }
  window.clearCompare = clearCompare;

  function showCompare() {
    if (compareSlugs.length < 2) return;
    compareMode = true;
    render();
  }
  window.showCompare = showCompare;

  function exitCompare() {
    compareMode = false;
    render();
  }
  window.exitCompare = exitCompare;

  function updateCompareBar() {
    var bar = document.getElementById('gg-compare-bar');
    var pills = document.getElementById('gg-compare-pills');
    var btn = document.getElementById('gg-btn-compare');
    if (!bar) return;
    if (compareSlugs.length === 0) {
      bar.style.display = 'none';
      return;
    }
    bar.style.display = '';
    var slugSet = {};
    allRaces.forEach(function(r) { slugSet[r.slug] = r.name; });
    pills.innerHTML = compareSlugs.map(function(slug) {
      var name = slugSet[slug] || slug;
      return '<span class="gg-filter-pill">' + name + '<button onclick="toggleCompare(\'' + slug + '\',false)">\u00d7</button></span>';
    }).join('');
    btn.disabled = compareSlugs.length < 2;
    btn.textContent = 'COMPARE (' + compareSlugs.length + ')';
  }

  function updateCompareCheckboxes() {
    document.querySelectorAll('#gg-race-search input[data-slug]').forEach(function(cb) {
      cb.checked = compareSlugs.indexOf(cb.dataset.slug) !== -1;
    });
  }

  // ── Compare panel ──
  function renderComparePanel() {
    var slugMap = {};
    allRaces.forEach(function(r) { slugMap[r.slug] = r; });
    var races = compareSlugs.map(function(s) { return slugMap[s]; }).filter(Boolean);
    if (races.length < 2) { compareMode = false; return; }

    var container = document.getElementById('gg-tier-container');
    var radarVars = ['length','technicality','elevation','climate','altitude','logistics','adventure'];

    // Banner
    var html = '<div class="gg-compare-banner">' +
      '<span>COMPARING ' + races.length + ' RACES</span>' +
      '<button onclick="exitCompare()">Back to Results</button>' +
    '</div>';

    // Table
    html += '<div class="gg-compare-table-wrap"><table class="gg-compare-table">';

    // Header row: race names
    html += '<thead><tr><th class="gg-compare-label-col"></th>';
    races.forEach(function(r, i) {
      html += '<th style="border-left:3px solid ' + COMPARE_COLORS[i].stroke + '">' +
        (r.has_profile ? '<a href="' + r.profile_url + '">' + r.name + '</a>' : r.name) +
      '</th>';
    });
    html += '</tr></thead><tbody>';

    // Tier row
    html += '<tr><td class="gg-compare-label-col">TIER</td>';
    races.forEach(function(r) {
      html += '<td><span class="gg-tier-badge gg-tier-' + r.tier + '">TIER ' + r.tier + '</span> ' + TIER_NAMES[r.tier] + '</td>';
    });
    html += '</tr>';

    // Score row with best highlight
    var scores = races.map(function(r) { return r.overall_score || 0; });
    var maxScore = Math.max.apply(null, scores);
    html += '<tr><td class="gg-compare-label-col">SCORE</td>';
    races.forEach(function(r) {
      var s = r.overall_score || 0;
      var best = s === maxScore && maxScore > 0 ? ' gg-compare-best' : '';
      html += '<td class="' + best + '"><span class="gg-compare-score-num">' + s + '</span>' +
        '<div class="gg-score-track"><div class="gg-score-fill" style="width:' + s + '%;background:' + scoreColor(s) + '"></div></div></td>';
    });
    html += '</tr>';

    // Vitals section header
    html += '<tr class="gg-compare-section-row"><td colspan="' + (races.length + 1) + '">VITALS</td></tr>';

    // Location
    html += '<tr><td class="gg-compare-label-col">LOCATION</td>';
    races.forEach(function(r) { html += '<td>' + (r.location || 'TBD') + '</td>'; });
    html += '</tr>';

    // Month
    html += '<tr><td class="gg-compare-label-col">MONTH</td>';
    races.forEach(function(r) { html += '<td>' + (r.month || 'TBD') + '</td>'; });
    html += '</tr>';

    // Distance (best = longest)
    var dists = races.map(function(r) { return r.distance_mi || 0; });
    var maxDist = Math.max.apply(null, dists);
    html += '<tr><td class="gg-compare-label-col">DISTANCE</td>';
    races.forEach(function(r) {
      var d = r.distance_mi || 0;
      var best = d === maxDist && maxDist > 0 ? ' gg-compare-best' : '';
      html += '<td class="' + best + '">' + (d ? d + ' mi' : '\u2014') + '</td>';
    });
    html += '</tr>';

    // Elevation (best = highest)
    var elevs = races.map(function(r) { return r.elevation_ft || 0; });
    var maxElev = Math.max.apply(null, elevs);
    html += '<tr><td class="gg-compare-label-col">ELEVATION</td>';
    races.forEach(function(r) {
      var e = r.elevation_ft || 0;
      var best = e === maxElev && maxElev > 0 ? ' gg-compare-best' : '';
      html += '<td class="' + best + '">' + (e ? Number(e).toLocaleString() + ' ft' : '\u2014') + '</td>';
    });
    html += '</tr>';

    // Radar chart section
    html += '<tr class="gg-compare-section-row"><td colspan="' + (races.length + 1) + '">RADAR</td></tr>';
    html += '<tr><td colspan="' + (races.length + 1) + '" class="gg-compare-radar-cell">';

    // Overlaid radar SVG
    var rCx = 100, rCy = 100, rR = 80;
    var n = radarVars.length;
    var svgContent = '';
    // Grid rings
    [0.2, 0.4, 0.6, 0.8, 1.0].forEach(function(s) {
      var gp = Array.from({length: n}, function(_, i) {
        var angle = (Math.PI * 2 * i / n) - Math.PI / 2;
        return [rCx + rR * s * Math.cos(angle), rCy + rR * s * Math.sin(angle)];
      });
      svgContent += '<polygon points="' + gp.map(function(p){return p.join(',');}).join(' ') + '" fill="none" stroke="#d4c5b9" stroke-width="0.5"/>';
    });
    // Axis lines
    Array.from({length: n}, function(_, i) {
      var angle = (Math.PI * 2 * i / n) - Math.PI / 2;
      svgContent += '<line x1="' + rCx + '" y1="' + rCy + '" x2="' + (rCx + rR * Math.cos(angle)) + '" y2="' + (rCy + rR * Math.sin(angle)) + '" stroke="#d4c5b9" stroke-width="0.5"/>';
    });
    // Axis labels
    var radarLabels = ['LEN','TECH','ELEV','CLIM','ALT','LOG','ADV'];
    Array.from({length: n}, function(_, i) {
      var angle = (Math.PI * 2 * i / n) - Math.PI / 2;
      var lx = rCx + (rR + 14) * Math.cos(angle);
      var ly = rCy + (rR + 14) * Math.sin(angle);
      svgContent += '<text x="' + lx + '" y="' + ly + '" text-anchor="middle" dominant-baseline="central" font-size="8" font-family="Sometype Mono,monospace" fill="#7d695d">' + radarLabels[i] + '</text>';
    });
    // One polygon per race
    races.forEach(function(r, idx) {
      if (!r.scores) return;
      var pts = radarPoints(r.scores, radarVars, rCx, rCy, rR);
      var poly = pts.map(function(p) { return p.join(','); }).join(' ');
      var c = COMPARE_COLORS[idx];
      svgContent += '<polygon points="' + poly + '" fill="' + c.fill + '" stroke="' + c.stroke + '" stroke-width="2"/>';
    });
    html += '<svg class="gg-compare-radar" width="200" height="200" viewBox="0 0 200 200">' + svgContent + '</svg>';

    // Legend
    html += '<div class="gg-compare-legend">';
    races.forEach(function(r, idx) {
      html += '<span class="gg-compare-legend-item"><span class="gg-compare-legend-swatch" style="background:' + COMPARE_COLORS[idx].stroke + '"></span>' + r.name + '</span>';
    });
    html += '</div>';
    html += '</td></tr>';

    // Scores section header
    html += '<tr class="gg-compare-section-row"><td colspan="' + (races.length + 1) + '">SCORES</td></tr>';

    // 14 score dimension rows
    Object.entries(SCORE_LABELS).forEach(function(pair) {
      var key = pair[0], label = pair[1];
      var vals = races.map(function(r) { return (r.scores && r.scores[key]) || 0; });
      var maxVal = Math.max.apply(null, vals);
      html += '<tr><td class="gg-compare-label-col">' + label.toUpperCase() + '</td>';
      races.forEach(function(r, idx) {
        var v = (r.scores && r.scores[key]) || 0;
        var best = v === maxVal && maxVal > 0 ? ' gg-compare-best' : '';
        var dots = Array.from({length: 5}, function(_, i) {
          var cls = i < v ? (best ? 'gg-compare-dot-best' : 'gg-compare-dot-filled') : 'gg-compare-dot-empty';
          return '<span class="' + cls + '"></span>';
        }).join('');
        html += '<td class="' + best + '"><span class="gg-compare-dots">' + dots + '</span></td>';
      });
      html += '</tr>';
    });

    // View links row
    html += '<tr><td class="gg-compare-label-col"></td>';
    races.forEach(function(r) {
      html += '<td>' + (r.has_profile ? '<a href="' + r.profile_url + '" class="gg-compare-view-link">View Profile \u2197</a>' : '') + '</td>';
    });
    html += '</tr>';

    html += '</tbody></table></div>';
    container.innerHTML = html;
  }

  function clearAllFilters() {
    document.getElementById('gg-search').value = '';
    document.getElementById('gg-tier').value = '';
    document.getElementById('gg-region').value = '';
    document.getElementById('gg-distance').value = '';
    document.getElementById('gg-month').value = '';
    document.getElementById('gg-profile').value = '';
    // Also clear near me
    if (userLat !== null) activateNearMe();
    render();
  }
  window.clearAllFilters = clearAllFilters;

  // ── Main render ──
  function render(resetPages) {
    if (resetPages !== false) {
      tierVisibleCounts = { 1: TIER_PAGE_SIZE, 2: TIER_PAGE_SIZE, 3: TIER_PAGE_SIZE, 4: TIER_PAGE_SIZE };
    }

    var filtered = sortRaces(filterRaces());

    // If match mode was loaded from URL but scores not yet computed, compute now
    if (displayMode === 'match' && Object.keys(matchScores).length === 0) {
      var vals = getSliderValues();
      allRaces.forEach(function(r) {
        matchScores[r.slug] = computeMatchScore(r, vals);
      });
    }

    document.getElementById('gg-count').textContent =
      filtered.length + ' race' + (filtered.length !== 1 ? 's' : '') + ' found';

    if (compareMode && compareSlugs.length >= 2) {
      renderComparePanel();
      renderActivePills();
      updateCompareBar();
      saveToURL();
      return;
    }

    if (displayMode === 'match') {
      renderMatchResults(filtered);
    } else {
      renderTierSections(filtered);
    }

    renderActivePills();
    updateCompareCheckboxes();
    updateCompareBar();
    if (viewMode === 'map' && mapInstance) { updateMapMarkers(); }
    if (viewMode === 'calendar') { renderCalendar(); }
    saveToURL();
  }

  // ── Event binding ──
  function bindEvents() {
    var searchTimer = null;
    function debouncedRender() {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(render, 200);
    }
    // Text search: debounce to avoid DOM thrashing on every keystroke
    document.getElementById('gg-search').addEventListener('input', debouncedRender);
    // Dropdowns: render immediately on change (single event per selection)
    ['gg-tier','gg-region','gg-distance','gg-month','gg-profile'].forEach(function(id) {
      document.getElementById(id).addEventListener('change', render);
    });

    window.addEventListener('gg-reset-filters', function() {
      displayMode = 'tiers';
      matchScores = {};
      nearMeRadius = 0;
      compareSlugs = [];
      compareMode = false;
      tierVisibleCounts = { 1: TIER_PAGE_SIZE, 2: TIER_PAGE_SIZE, 3: TIER_PAGE_SIZE, 4: TIER_PAGE_SIZE };
      render();
    });

    document.querySelectorAll('.gg-sort-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        currentSort = btn.dataset.sort;
        updateSortButtons();
        render();
      });
      if (btn.dataset.sort === currentSort) {
        updateSortButtons();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
