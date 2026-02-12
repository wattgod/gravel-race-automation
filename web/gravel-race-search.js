(function() {
  const DATA_URL = '/wp-content/uploads/race-index.json';
  const TIER_PAGE_SIZE = 20;

  let allRaces = [];
  let currentSort = 'score';
  let displayMode = 'tiers'; // 'tiers' or 'match'
  let matchScores = {};      // slug → match pct
  let tierVisibleCounts = { 1: TIER_PAGE_SIZE, 2: TIER_PAGE_SIZE, 3: TIER_PAGE_SIZE, 4: TIER_PAGE_SIZE };
  let tierCollapsed = { 1: false, 2: false, 3: true, 4: true };

  const TIER_NAMES = { 1: 'Elite', 2: 'Contender', 3: 'Solid', 4: 'Roster' };
  const TIER_DESCS = {
    1: 'The definitive gravel events. World-class fields, iconic courses, bucket-list status.',
    2: 'Established races with strong reputations and competitive fields. The next tier of must-do events.',
    3: 'Regional favorites and emerging races. Strong local scenes, genuine gravel character.',
    4: 'Up-and-coming races and local grinders. Grassroots gravel — small fields, raw vibes.'
  };
  const US_REGIONS = new Set(['West', 'Midwest', 'South', 'Northeast']);

  const SLIDERS = [
    { key: 'distance',      label: 'Distance',      low: 'Quick Spin',       high: 'Ultra Endurance', mapping: [{ field: 'length', weight: 1.0 }] },
    { key: 'technicality',  label: 'Technicality',   low: 'Smooth Gravel',    high: 'Single Track',    mapping: [{ field: 'technicality', weight: 1.0 }] },
    { key: 'climbing',      label: 'Climbing',       low: 'Flat is Fast',     high: 'Mountain Goat',   mapping: [{ field: 'elevation', weight: 1.0 }] },
    { key: 'adventure',     label: 'Adventure',      low: 'Close to Town',    high: 'Deep Backcountry',mapping: [{ field: 'adventure', weight: 0.6 }, { field: 'logistics', weight: 0.4 }] },
    { key: 'competition',   label: 'Competition',    low: 'Just Finish',      high: 'Pro Field',       mapping: [{ field: 'field_depth', weight: 0.6 }, { field: 'race_quality', weight: 0.4 }] },
    { key: 'prestige',      label: 'Prestige',       low: 'Hidden Gem',       high: 'Bucket List',     mapping: [{ field: 'prestige', weight: 1.0 }] },
    { key: 'budget',        label: 'Budget',         low: 'All-In',           high: 'Budget Friendly', mapping: [{ field: 'value', weight: 0.6 }, { field: 'expenses', weight: 0.4, invert: true }] }
  ];

  // ── Init ──
  function init() {
    buildSliders();
    fetch(DATA_URL)
      .then(r => r.json())
      .then(data => {
        allRaces = data;
        populateFilterOptions();
        loadFromURL();
        render();
        bindEvents();
      })
      .catch(err => {
        document.getElementById('gg-tier-container').innerHTML =
          '<div class="gg-no-results">Failed to load race data. Check console.</div>';
        console.error('Race index load error:', err);
      });
  }

  // ── Questionnaire sliders ──
  function buildSliders() {
    const grid = document.getElementById('gg-slider-grid');
    grid.innerHTML = SLIDERS.map(s => `
      <div class="gg-slider-row">
        <span class="gg-slider-label">${s.label}</span>
        <input type="range" min="1" max="5" value="3" id="gg-q-${s.key}">
        <div class="gg-slider-endpoints">
          <span>${s.low}</span>
          <span>${s.high}</span>
        </div>
      </div>
    `).join('');
  }

  function getSliderValues() {
    const vals = {};
    SLIDERS.forEach(s => {
      vals[s.key] = parseInt(document.getElementById('gg-q-' + s.key).value);
    });
    return vals;
  }

  function computeMatchScore(race, sliderVals) {
    if (!race.scores) return 0;
    let weightedSqDiff = 0;
    let totalWeight = 0;
    SLIDERS.forEach(s => {
      const userVal = sliderVals[s.key];
      s.mapping.forEach(m => {
        let raceVal = race.scores[m.field] || 1;
        if (m.invert) raceVal = 6 - raceVal;
        const diff = userVal - raceVal;
        weightedSqDiff += m.weight * diff * diff;
        totalWeight += m.weight;
      });
    });
    const maxPossible = totalWeight * 16; // max squared diff per dimension = (5-1)^2 = 16
    return Math.round((1 - weightedSqDiff / maxPossible) * 100);
  }

  // ── Match mode ──
  function runMatch() {
    const vals = getSliderValues();
    matchScores = {};
    allRaces.forEach(r => {
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
    const body = document.getElementById('gg-q-body');
    const toggle = document.getElementById('gg-q-toggle');
    body.classList.toggle('collapsed');
    toggle.classList.toggle('collapsed');
  }
  window.toggleQuestionnaire = toggleQuestionnaire;

  // ── URL state ──
  function loadFromURL() {
    const params = new URLSearchParams(window.location.search);
    if (params.get('q')) document.getElementById('gg-search').value = params.get('q');
    if (params.get('tier')) document.getElementById('gg-tier').value = params.get('tier');
    if (params.get('region')) document.getElementById('gg-region').value = params.get('region');
    if (params.get('distance')) document.getElementById('gg-distance').value = params.get('distance');
    if (params.get('month')) document.getElementById('gg-month').value = params.get('month');
    if (params.get('profile')) document.getElementById('gg-profile').value = params.get('profile');
    if (params.get('sort')) currentSort = params.get('sort');

    // Restore match mode from URL
    if (params.get('match') === '1') {
      SLIDERS.forEach(s => {
        const val = params.get('q_' + s.key);
        if (val) document.getElementById('gg-q-' + s.key).value = val;
      });
      // Defer runMatch until data is loaded — handled via displayMode check after data loads
      displayMode = 'match';
      document.getElementById('gg-btn-reset').style.display = '';
    }
  }

  function saveToURL() {
    const f = getFilters();
    const params = new URLSearchParams();
    if (f.search) params.set('q', f.search);
    if (f.tier) params.set('tier', f.tier);
    if (f.region) params.set('region', f.region);
    if (f.distance) params.set('distance', f.distance);
    if (f.month) params.set('month', f.month);
    if (f.profile) params.set('profile', f.profile);
    if (currentSort !== 'score') params.set('sort', currentSort);

    if (displayMode === 'match') {
      params.set('match', '1');
      SLIDERS.forEach(s => {
        const val = document.getElementById('gg-q-' + s.key).value;
        if (val !== '3') params.set('q_' + s.key, val);
      });
    }

    const newURL = params.toString()
      ? `${window.location.pathname}?${params.toString()}`
      : window.location.pathname;
    window.history.replaceState({}, '', newURL);
  }

  // ── Filter helpers ──
  function countByFilter(filterKey, filterValue) {
    return allRaces.filter(r => {
      if (filterKey === 'tier') return r.tier == filterValue;
      if (filterKey === 'region') return r.region === filterValue;
      if (filterKey === 'month') return r.month === filterValue;
      if (filterKey === 'profile') {
        if (filterValue === 'yes') return r.has_profile;
        if (filterValue === 'no') return !r.has_profile;
      }
      if (filterKey === 'distance') {
        const [min, max] = filterValue.split('-').map(Number);
        const d = r.distance_mi || 0;
        return d >= min && d <= max;
      }
      return true;
    }).length;
  }

  function populateFilterOptions() {
    const tierSel = document.getElementById('gg-tier');
    tierSel.innerHTML = '<option value="">All Tiers</option>';
    [1, 2, 3, 4].forEach(t => {
      const count = countByFilter('tier', t);
      const opt = document.createElement('option');
      opt.value = t; opt.textContent = `Tier ${t} (${count})`;
      tierSel.appendChild(opt);
    });

    const regions = [...new Set(allRaces.map(r => r.region).filter(Boolean))].sort();
    const regionSel = document.getElementById('gg-region');
    regionSel.innerHTML = '<option value="">All Regions</option>';
    // Add "International" meta-region (all non-US regions)
    const intlCount = allRaces.filter(r => r.region && !US_REGIONS.has(r.region)).length;
    if (intlCount > 0) {
      const intlOpt = document.createElement('option');
      intlOpt.value = 'International'; intlOpt.textContent = `International (${intlCount})`;
      regionSel.appendChild(intlOpt);
    }
    regions.forEach(r => {
      const count = countByFilter('region', r);
      const opt = document.createElement('option');
      opt.value = r; opt.textContent = `${r} (${count})`;
      regionSel.appendChild(opt);
    });

    const distSel = document.getElementById('gg-distance');
    distSel.innerHTML = '<option value="">Any Distance</option>';
    [['0-50', 'Under 50 mi'], ['50-100', '50-100 mi'], ['100-200', '100-200 mi'], ['200-999', '200+ mi']].forEach(([val, label]) => {
      const count = countByFilter('distance', val);
      const opt = document.createElement('option');
      opt.value = val; opt.textContent = `${label} (${count})`;
      distSel.appendChild(opt);
    });

    const months = ['January','February','March','April','May','June',
                    'July','August','September','October','November','December'];
    const monthSel = document.getElementById('gg-month');
    monthSel.innerHTML = '<option value="">Any Month</option>';
    months.forEach(m => {
      const count = countByFilter('month', m);
      if (count > 0) {
        const opt = document.createElement('option');
        opt.value = m; opt.textContent = `${m} (${count})`;
        monthSel.appendChild(opt);
      }
    });

    const profSel = document.getElementById('gg-profile');
    profSel.innerHTML = '<option value="">All</option>';
    const withProfile = countByFilter('profile', 'yes');
    const noProfile = countByFilter('profile', 'no');
    profSel.innerHTML += `<option value="yes">Has Profile (${withProfile})</option>`;
    profSel.innerHTML += `<option value="no">No Profile (${noProfile})</option>`;
  }

  function getFilters() {
    const search = document.getElementById('gg-search').value.toLowerCase();
    const tier = document.getElementById('gg-tier').value;
    const region = document.getElementById('gg-region').value;
    const distance = document.getElementById('gg-distance').value;
    const month = document.getElementById('gg-month').value;
    const profile = document.getElementById('gg-profile').value;
    return { search, tier, region, distance, month, profile };
  }

  function filterRaces() {
    const f = getFilters();
    return allRaces.filter(r => {
      if (f.search && !r.name.toLowerCase().includes(f.search) &&
          !(r.location || '').toLowerCase().includes(f.search)) return false;
      if (f.tier && r.tier != f.tier) return false;
      if (f.region === 'International' && (!r.region || US_REGIONS.has(r.region))) return false;
      if (f.region && f.region !== 'International' && r.region !== f.region) return false;
      if (f.month && r.month !== f.month) return false;
      if (f.profile === 'yes' && !r.has_profile) return false;
      if (f.profile === 'no' && r.has_profile) return false;
      if (f.distance) {
        const [min, max] = f.distance.split('-').map(Number);
        const d = r.distance_mi || 0;
        if (d < min || d > max) return false;
      }
      return true;
    });
  }

  function sortRaces(races) {
    const sorted = [...races];
    switch(currentSort) {
      case 'score':
        sorted.sort((a, b) => (b.overall_score || 0) - (a.overall_score || 0));
        break;
      case 'name':
        sorted.sort((a, b) => a.name.localeCompare(b.name));
        break;
      case 'distance':
        sorted.sort((a, b) => (b.distance_mi || 0) - (a.distance_mi || 0));
        break;
    }
    return sorted;
  }

  // ── Score / rendering helpers ──
  function scoreColor(score) {
    if (score >= 85) return '#3a2e25';
    if (score >= 75) return '#59473c';
    if (score >= 65) return '#8c7568';
    return '#cccccc';
  }

  const SCORE_LABELS = {
    logistics: 'Logistics', length: 'Length', technicality: 'Technicality',
    elevation: 'Elevation', climate: 'Climate', altitude: 'Altitude',
    adventure: 'Adventure', prestige: 'Prestige', race_quality: 'Race Quality',
    experience: 'Experience', community: 'Community', field_depth: 'Field Depth',
    value: 'Value', expenses: 'Expenses'
  };

  function renderScoreBreakdown(scores) {
    if (!scores || Object.keys(scores).length < 7) return '';
    const rows = Object.entries(SCORE_LABELS).map(([key, label]) => {
      const val = scores[key] || 0;
      const dots = Array.from({length: 5}, (_, i) =>
        `<span class="gg-score-dot${i < val ? ' filled' : ''}"></span>`
      ).join('');
      return `<div class="gg-score-row"><span class="gg-score-row-label">${label}</span><span class="gg-score-row-dots">${dots}</span></div>`;
    }).join('');
    return `<div class="gg-score-breakdown"><div class="gg-score-grid">${rows}</div></div>`;
  }

  function renderMiniRadar(scores) {
    if (!scores || Object.keys(scores).length < 7) return '';
    const vars = ['length','technicality','elevation','climate','altitude','logistics','adventure'];
    const cx = 40, cy = 40, r = 30;
    const n = vars.length;
    const points = vars.map((v, i) => {
      const val = (scores[v] || 1) / 5;
      const angle = (Math.PI * 2 * i / n) - Math.PI / 2;
      return [cx + r * val * Math.cos(angle), cy + r * val * Math.sin(angle)];
    });
    const poly = points.map(p => p.join(',')).join(' ');
    const grid = [0.2, 0.4, 0.6, 0.8, 1.0].map(s => {
      const gp = Array.from({length: n}, (_, i) => {
        const angle = (Math.PI * 2 * i / n) - Math.PI / 2;
        return [cx + r * s * Math.cos(angle), cy + r * s * Math.sin(angle)];
      });
      return `<polygon points="${gp.map(p=>p.join(',')).join(' ')}" fill="none" stroke="#d4c5b9" stroke-width="0.5"/>`;
    }).join('');
    return `<svg class="gg-radar" width="80" height="80" viewBox="0 0 80 80">
      ${grid}
      <polygon points="${poly}" fill="rgba(26,138,130,0.12)" stroke="#3a2e25" stroke-width="1.5"/>
    </svg>`;
  }

  function renderCard(race) {
    const nameTag = race.has_profile
      ? `<a class="gg-card-name" href="${race.profile_url}">${race.name}</a>`
      : `<span class="gg-card-name no-link">${race.name}</span>`;

    const breakdown = renderScoreBreakdown(race.scores);
    const scoreBar = race.overall_score
      ? `<div class="gg-score-bar" onclick="this.nextElementSibling&&this.nextElementSibling.classList.toggle('open')" title="Click for score breakdown">
          <div class="gg-score-track">
            <div class="gg-score-fill" style="width:${race.overall_score}%;background:${scoreColor(race.overall_score)}"></div>
          </div>
          <span class="gg-score-num">${race.overall_score}</span>
        </div>${breakdown}`
      : '';

    const radar = renderMiniRadar(race.scores);

    const matchBadge = (displayMode === 'match' && matchScores[race.slug] !== undefined)
      ? `<span class="gg-match-badge">${matchScores[race.slug]}% match</span>`
      : '';

    return `<div class="gg-card">
      <div class="gg-card-header">
        ${nameTag}
        <div style="display:flex;gap:6px;align-items:center">
          ${matchBadge}
          <span class="gg-tier-badge gg-tier-${race.tier}">TIER ${race.tier}</span>
        </div>
      </div>
      <div class="gg-card-meta">${race.location || 'Location TBD'}${race.month ? ' &middot; ' + race.month : ''}</div>
      <div class="gg-card-stats">
        ${race.distance_mi ? `<div class="gg-stat"><span class="gg-stat-val">${race.distance_mi}</span><span class="gg-stat-label">Miles</span></div>` : ''}
        ${race.elevation_ft ? `<div class="gg-stat"><span class="gg-stat-val">${Number(race.elevation_ft).toLocaleString()}</span><span class="gg-stat-label">Ft Elev</span></div>` : ''}
      </div>
      ${scoreBar}
      ${radar}
      ${race.tagline ? `<div class="gg-card-tagline">${race.tagline}</div>` : ''}
    </div>`;
  }

  // ── Tier grouping ──
  function groupByTier(races) {
    const groups = { 1: [], 2: [], 3: [], 4: [] };
    races.forEach(r => {
      const t = r.tier || 4;
      if (groups[t]) groups[t].push(r);
    });
    return groups;
  }

  function renderTierSections(filtered) {
    const groups = groupByTier(filtered);
    const container = document.getElementById('gg-tier-container');
    let html = '';

    [1, 2, 3, 4].forEach(t => {
      const races = groups[t];
      if (races.length === 0) return; // hide empty tiers

      const collapsed = tierCollapsed[t];
      const visible = races.slice(0, tierVisibleCounts[t]);
      const remaining = races.length - visible.length;

      html += `<div class="gg-tier-section">
        <div class="gg-tier-section-header tier-${t}" onclick="toggleTier(${t})">
          <div class="gg-tier-section-title">
            <span class="gg-tier-badge gg-tier-${t}">TIER ${t}</span>
            <h3>${TIER_NAMES[t]}</h3>
            <span class="gg-tier-section-count">${races.length} race${races.length !== 1 ? 's' : ''}</span>
          </div>
          <p class="gg-tier-section-desc">${TIER_DESCS[t]}</p>
          <span class="gg-tier-section-chevron${collapsed ? ' collapsed' : ''}">▾</span>
        </div>
        <div class="gg-tier-section-body${collapsed ? ' collapsed' : ''}">
          <div class="gg-grid">${visible.map(renderCard).join('')}</div>
          ${remaining > 0 ? `<button class="gg-load-more" onclick="loadMoreTier(${t})">Show ${Math.min(remaining, TIER_PAGE_SIZE)} more of ${remaining} remaining</button>` : ''}
        </div>
      </div>`;
    });

    if (!html) {
      html = '<div class="gg-no-results">No races match your filters.</div>';
    }
    container.innerHTML = html;
  }

  function renderMatchResults(filtered) {
    // Sort by match score descending
    const sorted = [...filtered].sort((a, b) => (matchScores[b.slug] || 0) - (matchScores[a.slug] || 0));
    const container = document.getElementById('gg-tier-container');

    let html = `<div class="gg-match-banner">
      <span>Showing results ranked by match score</span>
      <button onclick="resetMatch()">Back to Tiers</button>
    </div>`;

    if (sorted.length > 0) {
      html += `<div class="gg-grid">${sorted.map(renderCard).join('')}</div>`;
    } else {
      html += '<div class="gg-no-results">No races match your filters.</div>';
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
    const f = getFilters();
    const container = document.getElementById('gg-active-filters');
    const pills = [];

    const filterLabels = {
      search: f.search ? `"${f.search}"` : null,
      tier: f.tier ? `Tier ${f.tier}` : null,
      region: f.region || null,
      distance: f.distance ? {
        '0-50': 'Under 50 mi',
        '50-100': '50-100 mi',
        '100-200': '100-200 mi',
        '200-999': '200+ mi'
      }[f.distance] : null,
      month: f.month || null,
      profile: f.profile ? (f.profile === 'yes' ? 'Has Profile' : 'No Profile') : null
    };

    Object.entries(filterLabels).forEach(([key, label]) => {
      if (label) {
        const inputId = key === 'search' ? 'gg-search' : `gg-${key}`;
        pills.push(`<span class="gg-filter-pill">${label}<button onclick="document.getElementById('${inputId}').value='';document.getElementById('${inputId}').dispatchEvent(new Event('change'))">×</button></span>`);
      }
    });

    if (pills.length > 1) {
      pills.push('<button class="gg-clear-all" onclick="clearAllFilters()">Clear all</button>');
    }

    container.innerHTML = pills.join('');
  }

  function clearAllFilters() {
    document.getElementById('gg-search').value = '';
    document.getElementById('gg-tier').value = '';
    document.getElementById('gg-region').value = '';
    document.getElementById('gg-distance').value = '';
    document.getElementById('gg-month').value = '';
    document.getElementById('gg-profile').value = '';
    render();
  }
  window.clearAllFilters = clearAllFilters;

  // ── Main render ──
  function render(resetPages) {
    if (resetPages !== false) {
      tierVisibleCounts = { 1: TIER_PAGE_SIZE, 2: TIER_PAGE_SIZE, 3: TIER_PAGE_SIZE, 4: TIER_PAGE_SIZE };
    }

    const filtered = sortRaces(filterRaces());

    // If match mode was loaded from URL but scores not yet computed, compute now
    if (displayMode === 'match' && Object.keys(matchScores).length === 0) {
      const vals = getSliderValues();
      allRaces.forEach(r => {
        matchScores[r.slug] = computeMatchScore(r, vals);
      });
    }

    document.getElementById('gg-count').textContent =
      `${filtered.length} race${filtered.length !== 1 ? 's' : ''} found`;

    if (displayMode === 'match') {
      renderMatchResults(filtered);
    } else {
      renderTierSections(filtered);
    }

    renderActivePills();
    saveToURL();
  }

  // ── Event binding ──
  function bindEvents() {
    ['gg-search','gg-tier','gg-region','gg-distance','gg-month','gg-profile'].forEach(id => {
      document.getElementById(id).addEventListener('input', render);
      document.getElementById(id).addEventListener('change', render);
    });

    document.querySelectorAll('.gg-sort-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.gg-sort-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentSort = btn.dataset.sort;
        render();
      });
      if (btn.dataset.sort === currentSort) {
        document.querySelectorAll('.gg-sort-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
