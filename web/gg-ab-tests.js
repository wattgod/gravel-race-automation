/**
 * Gravel God A/B Testing — client-side experiment engine.
 *
 * Loaded as a deferred script. The inline bootstrap in <head> handles
 * returning visitors synchronously from localStorage to avoid flicker.
 * This module handles: new visitor assignment, GA4 event tracking,
 * and localStorage cache refresh.
 *
 * GA4 events:
 *   ab_impression  — variant shown to visitor
 *   ab_conversion  — CTA click attributed to experiment
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'gg_ab_assign';
  var CONFIG_URL = '/ab/experiments.json';

  // ── FNV-1a hash (deterministic visitor assignment) ─────────
  function fnv1a(str) {
    var hash = 0x811c9dc5;
    for (var i = 0; i < str.length; i++) {
      hash ^= str.charCodeAt(i);
      hash = (hash * 0x01000193) >>> 0;
    }
    return hash;
  }

  // ── Visitor ID (stable per browser) ────────────────────────
  function getVisitorId() {
    var key = 'gg_ab_vid';
    var vid = localStorage.getItem(key);
    if (vid) return vid;
    vid = Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
    localStorage.setItem(key, vid);
    return vid;
  }

  // ── Assignment storage ─────────────────────────────────────
  function getAssignments() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
    } catch (e) {
      return {};
    }
  }

  function saveAssignments(assignments) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(assignments));
  }

  // ── Variant assignment (deterministic via FNV-1a) ──────────
  function assignVariant(visitorId, experiment) {
    var hash = fnv1a(visitorId + ':' + experiment.id);
    // Traffic allocation: if hash falls outside traffic %, skip
    if (experiment.traffic < 1.0) {
      var trafficHash = (hash % 1000) / 1000;
      if (trafficHash >= experiment.traffic) return null;
    }
    var idx = hash % experiment.variants.length;
    return experiment.variants[idx];
  }

  // ── Page matching ──────────────────────────────────────────
  function matchesPage(pages) {
    var path = location.pathname;
    for (var i = 0; i < pages.length; i++) {
      var p = pages[i];
      if (p === path) return true;
      // Match /index.html to /
      if (p === '/' && path === '/index.html') return true;
      if (p === '/index.html' && path === '/') return true;
      // Trailing slash normalization
      if (p.replace(/\/$/, '') === path.replace(/\/$/, '')) return true;
    }
    return false;
  }

  // ── GA4 event helper ───────────────────────────────────────
  function fireGA4(eventName, params) {
    if (typeof gtag === 'function') {
      gtag('event', eventName, params);
    }
  }

  // ── DOM swap ───────────────────────────────────────────────
  function applyVariant(experiment, variant) {
    var el = document.querySelector(experiment.selector);
    if (!el) return;
    // All variants are plain text — textContent for XSS safety.
    // If rich HTML variants are needed later, add an explicit "html"
    // flag to the variant config.
    el.textContent = variant.content;
  }

  // ── Conversion tracking (deduplicated per session) ─────────
  function bindConversion(experiment, variant) {
    if (!experiment.conversion || experiment.conversion.type !== 'click') return;
    var targets = document.querySelectorAll(experiment.conversion.selector);
    for (var i = 0; i < targets.length; i++) {
      (function (target) {
        // Avoid double-binding on same element
        if (target.dataset.abConversion) return;
        target.dataset.abConversion = experiment.id;
        target.addEventListener('click', function () {
          // Deduplicate: one conversion per experiment per session
          var dedupKey = 'gg_ab_conv_' + experiment.id;
          try {
            if (sessionStorage.getItem(dedupKey)) return;
            sessionStorage.setItem(dedupKey, '1');
          } catch (e) { /* sessionStorage unavailable — fire anyway */ }
          fireGA4('ab_conversion', {
            experiment_id: experiment.id,
            variant_id: variant.id,
            variant_name: variant.name
          });
        });
      })(targets[i]);
    }
  }

  // ── Main ───────────────────────────────────────────────────
  function run(config) {
    var visitorId = getVisitorId();
    var assignments = getAssignments();
    var updated = false;
    var cache = {};

    var experiments = config.experiments || [];
    for (var i = 0; i < experiments.length; i++) {
      var exp = experiments[i];

      if (!matchesPage(exp.pages)) continue;

      var variant;
      // Check existing assignment
      if (assignments[exp.id]) {
        var assignedId = assignments[exp.id];
        variant = null;
        for (var j = 0; j < exp.variants.length; j++) {
          if (exp.variants[j].id === assignedId) {
            variant = exp.variants[j];
            break;
          }
        }
        // If variant was removed from config, reassign
        if (!variant) {
          variant = assignVariant(visitorId, exp);
          if (variant) {
            assignments[exp.id] = variant.id;
            updated = true;
          }
        }
      } else {
        // New assignment
        variant = assignVariant(visitorId, exp);
        if (variant) {
          assignments[exp.id] = variant.id;
          updated = true;
        }
      }

      if (!variant) continue;

      // Apply variant to DOM
      applyVariant(exp, variant);

      // Build cache for inline bootstrap (anti-flicker on return visits)
      cache[exp.id] = { sel: exp.selector, txt: variant.content };

      // Fire impression
      fireGA4('ab_impression', {
        experiment_id: exp.id,
        variant_id: variant.id,
        variant_name: variant.name
      });

      // Bind conversion tracking
      bindConversion(exp, variant);
    }

    if (updated) {
      saveAssignments(assignments);
    }
    // Save cache for inline bootstrap on next page load
    try { localStorage.setItem('gg_ab_cache', JSON.stringify(cache)); } catch (e) {}
  }

  // ── Fetch config and run ───────────────────────────────────
  fetch(CONFIG_URL)
    .then(function (res) {
      if (!res.ok) throw new Error('AB config fetch failed: ' + res.status);
      return res.json();
    })
    .then(run)
    .catch(function () {
      // Silent fail — site works fine without experiments
    });
})();
