// ── Hamburger mobile menu ───────────────────────────────
(function() {
  var hamburger = document.getElementById('gg-hamburger');
  var mobileNav = document.getElementById('gg-mobile-nav');
  if (!hamburger || !mobileNav) return;
  var navIsOpen = false;

  function closeNav() {
    navIsOpen = false;
    hamburger.classList.remove('is-open');
    hamburger.setAttribute('aria-expanded', 'false');
    hamburger.setAttribute('aria-label', 'Open menu');
    mobileNav.classList.remove('is-open');
    document.body.style.overflow = '';
    hamburger.focus();
  }

  function openNav() {
    navIsOpen = true;
    hamburger.classList.add('is-open');
    hamburger.setAttribute('aria-expanded', 'true');
    hamburger.setAttribute('aria-label', 'Close menu');
    mobileNav.classList.add('is-open');
    document.body.style.overflow = 'hidden';
    // Focus first interactive element in nav
    var first = mobileNav.querySelector('button, a');
    if (first) first.focus();
  }

  hamburger.addEventListener('click', function() {
    navIsOpen ? closeNav() : openNav();
  });

  // Escape key to close
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && navIsOpen) {
      closeNav();
    }
  });

  // Focus trap — keep Tab within mobile nav when open
  mobileNav.addEventListener('keydown', function(e) {
    if (e.key !== 'Tab' || !navIsOpen) return;
    var focusable = mobileNav.querySelectorAll('a, button');
    if (!focusable.length) return;
    var first = focusable[0];
    var last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      hamburger.focus();
    }
  });

  // Accordion toggles for mobile sub-menus
  mobileNav.querySelectorAll('.gg-mobile-nav-toggle').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var sub = btn.nextElementSibling;
      var expanded = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', !expanded);
      sub.classList.toggle('is-open', !expanded);
    });
  });

  // Close mobile nav on link click
  mobileNav.querySelectorAll('a').forEach(function(link) {
    link.addEventListener('click', closeNav);
  });

  // Expose nav state for header auto-hide guard
  window._ggNavIsOpen = function() { return navIsOpen; };
})();

// ── Sticky header — auto-hide on scroll-down, reveal on scroll-up ──
(function() {
  var header = document.getElementById('gg-site-header');
  if (!header) return;
  var lastScrollY = 0;
  var ticking = false;

  // Publish header height as CSS custom property for sticky children
  function updateHeaderHeight() {
    var h = header.offsetHeight;
    document.documentElement.style.setProperty('--gg-header-height', h + 'px');
  }
  updateHeaderHeight();
  window.addEventListener('resize', updateHeaderHeight);

  function onScroll() {
    var currentY = window.scrollY;
    var headerHeight = header.offsetHeight;
    // Never hide header while mobile nav is open
    var navOpen = typeof window._ggNavIsOpen === 'function' && window._ggNavIsOpen();
    if (!navOpen && currentY > headerHeight && currentY > lastScrollY) {
      header.classList.add('gg-header-hidden');
    } else {
      header.classList.remove('gg-header-hidden');
    }
    lastScrollY = currentY;
    ticking = false;
  }

  window.addEventListener('scroll', function() {
    if (!ticking) {
      requestAnimationFrame(onScroll);
      ticking = true;
    }
  }, { passive: true });
})();

// Race day countdown (HTML shows date for crawlers; JS replaces with day count)
(function() {
  var cd = document.querySelector('.gg-countdown');
  if (!cd) return;
  var dateStr = cd.getAttribute('data-date');
  if (!dateStr) return;
  var raceDate = new Date(dateStr + 'T00:00:00');
  var now = new Date();
  var diff = Math.ceil((raceDate - now) / (1000 * 60 * 60 * 24));
  var el = document.getElementById('gg-days-left');
  if (el && diff > 0) {
    el.textContent = diff;
    // Replace "RACE NAME" with "DAYS UNTIL RACE NAME"
    var textNodes = cd.childNodes;
    for (var i = 0; i < textNodes.length; i++) {
      if (textNodes[i].nodeType === 3 && textNodes[i].textContent.trim()) {
        textNodes[i].textContent = ' DAYS UNTIL' + textNodes[i].textContent;
        break;
      }
    }
  } else if (el && diff <= 0) {
    cd.style.display = 'none';
  }
})();

// Tabbed radar chart interactions — every GA4 event below follows a real click
// or keyboard activation. Data-derived explanation copy moves via textContent.
(function() {
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.gg-rating-tablist [role="tab"]'));
  function setTab(tab, shouldTrack) {
    tabs.forEach(function(candidate) {
      var selected = candidate === tab;
      candidate.setAttribute('aria-selected', selected ? 'true' : 'false');
      candidate.setAttribute('tabindex', selected ? '0' : '-1');
      var panel = document.getElementById(candidate.getAttribute('aria-controls'));
      if (panel) panel.hidden = !selected;
    });
    var activePanel = document.getElementById(tab.getAttribute('aria-controls'));
    if (shouldTrack && typeof gtag === 'function') {
      gtag('event', 'rating_tab_click', {rating_group: activePanel ? activePanel.getAttribute('data-rating-group') : ''});
    }
  }
  tabs.forEach(function(tab, index) {
    tab.addEventListener('click', function() { setTab(tab, true); });
    tab.addEventListener('keydown', function(event) {
      var next = index;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      else if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = tabs.length - 1;
      else return;
      event.preventDefault();
      tabs[next].focus();
      setTab(tabs[next], true);
    });
  });

  function findTile(panel, key) {
    var tiles = panel.querySelectorAll('.gg-rating-tile');
    for (var i = 0; i < tiles.length; i++) {
      if (tiles[i].getAttribute('data-rating-key') === key) return tiles[i];
    }
    return null;
  }
  function selectDimension(group, key, shouldTrack) {
    var panel = document.getElementById('gg-rating-panel-' + group);
    if (!panel) return;
    var tile = findTile(panel, key);
    if (!tile) return;
    panel.querySelectorAll('.gg-rating-tile').forEach(function(candidate) {
      candidate.setAttribute('aria-pressed', candidate === tile ? 'true' : 'false');
    });
    panel.querySelectorAll('.gg-radar-hit').forEach(function(hit) {
      var active = hit.getAttribute('data-rating-key') === key;
      hit.classList.toggle('is-active', active);
      var ring = hit.nextElementSibling ? hit.nextElementSibling.nextElementSibling : null;
      if (ring) ring.style.opacity = active ? '1' : '0';
    });
    panel.querySelectorAll('.gg-radar-spoke').forEach(function(spoke) {
      spoke.classList.toggle('is-active', spoke.getAttribute('data-rating-key') === key);
    });
    var detail = document.getElementById('gg-rating-detail-' + group);
    var source = tile.querySelector('.gg-rating-source');
    if (detail && source) {
      detail.querySelector('.gg-rating-explanation-label').textContent = tile.querySelector('.gg-rating-tile-label').textContent;
      detail.querySelector('.gg-rating-explanation-score').textContent = tile.querySelector('.gg-rating-tile-score').textContent;
      detail.querySelector('p').textContent = source.textContent;
    }
    if (shouldTrack && typeof gtag === 'function') {
      gtag('event', 'rating_criterion_click', {rating_group: group, rating_criterion: key});
    }
  }
  document.querySelectorAll('.gg-rating-tile').forEach(function(tile) {
    tile.addEventListener('click', function() {
      selectDimension(tile.getAttribute('data-rating-group'), tile.getAttribute('data-rating-key'), true);
    });
  });
  document.querySelectorAll('.gg-rating-panel').forEach(function(panel) {
    var initial = panel.querySelector('.gg-rating-tile[aria-pressed="true"]');
    if (initial) selectDimension(initial.getAttribute('data-rating-group'), initial.getAttribute('data-rating-key'), false);
  });

  // Click + hover on data points
  document.querySelectorAll('.gg-radar-hit').forEach(function(hit) {
    var svg = hit.closest('svg');
    var ring = hit.nextElementSibling ? hit.nextElementSibling.nextElementSibling : null;
    var tooltipBg = svg.querySelector('.gg-radar-tooltip-bg');
    var tooltipText = svg.querySelector('.gg-radar-tooltip-text');

    function showTip() {
      if (ring) ring.style.opacity = '1';
      // Show tooltip
      var label = hit.getAttribute('data-label');
      var score = hit.getAttribute('data-score');
      var txt = label + ': ' + score + '/5';
      var cx = parseFloat(hit.getAttribute('cx'));
      var cy = parseFloat(hit.getAttribute('cy'));
      tooltipText.textContent = txt;
      var tLen = txt.length * 6.5 + 16;
      tooltipText.setAttribute('x', cx);
      tooltipText.setAttribute('y', cy - 22);
      tooltipText.setAttribute('text-anchor', 'middle');
      tooltipText.style.opacity = '1';
      tooltipBg.setAttribute('x', cx - tLen / 2);
      tooltipBg.setAttribute('y', cy - 34);
      tooltipBg.setAttribute('width', tLen);
      tooltipBg.setAttribute('height', 22);
      tooltipBg.style.opacity = '0.9';
    }

    function hideTip() {
      if (ring && !hit.classList.contains('is-active')) ring.style.opacity = '0';
      tooltipText.style.opacity = '0';
      tooltipBg.style.opacity = '0';
    }
    hit.addEventListener('mouseenter', showTip);
    hit.addEventListener('focus', showTip);
    hit.addEventListener('mouseleave', hideTip);
    hit.addEventListener('blur', hideTip);

    function activate() {
      selectDimension(hit.getAttribute('data-rating-group'), hit.getAttribute('data-rating-key'), true);
    }
    hit.addEventListener('click', activate);
    hit.addEventListener('keydown', function(event) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        activate();
      }
    });
  });
})();

// Stat card count-up on scroll
(function() {
  if (!('IntersectionObserver' in window)) return;
  var statObs = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (!entry.isIntersecting) return;
      var el = entry.target;
      var text = el.textContent.trim();
      var match = text.match(/^[~$]?([\d,]+)/);
      if (!match) { statObs.unobserve(el); return; }
      var prefix = text.substring(0, text.indexOf(match[1]));
      var suffix = text.substring(text.indexOf(match[1]) + match[1].length);
      var target = parseInt(match[1].replace(/,/g, ''), 10);
      if (!target || target > 100000) { statObs.unobserve(el); return; }
      var duration = 1200;
      var start = null;
      function step(ts) {
        if (!start) start = ts;
        var progress = Math.min((ts - start) / duration, 1);
        var ease = 1 - Math.pow(1 - progress, 3);
        var val = Math.round(ease * target);
        el.textContent = prefix + val.toLocaleString() + suffix;
        if (progress < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
      statObs.unobserve(el);
    });
  }, { threshold: 0.5 });
  document.querySelectorAll('.gg-stat-countable').forEach(function(el) {
    statObs.observe(el);
  });
})();

// Staggered timeline + suffering zone reveals
(function() {
  if (!('IntersectionObserver' in window)) return;
  function staggerReveal(selector, baseDelay) {
    var items = document.querySelectorAll(selector);
    if (!items.length) return;
    var parent = items[0].closest('.gg-section');
    if (!parent) return;
    new IntersectionObserver(function(entries, obs) {
      if (entries[0].isIntersecting) {
        items.forEach(function(item, i) {
          setTimeout(function() { item.classList.add('is-visible'); }, baseDelay + i * 120);
        });
        obs.unobserve(parent);
      }
    }, { threshold: 0.2 }).observe(parent);
  }
  staggerReveal('.gg-timeline-item', 200);
  staggerReveal('.gg-suffering-zone', 100);
})();

// Sticky CTA + scroll fade-in
if ('IntersectionObserver' in window) {
  var stickyCta = document.getElementById('gg-sticky-cta');
  try { if (sessionStorage.getItem('gg-cta-dismissed')) { if (stickyCta) stickyCta.style.display = 'none'; stickyCta = null; } } catch(e) {}
  var dismissBtn = document.getElementById('gg-sticky-dismiss');
  if (dismissBtn) {
    dismissBtn.addEventListener('click', function() {
      if (stickyCta) stickyCta.style.display = 'none';
      stickyCta = null;
      try { sessionStorage.setItem('gg-cta-dismissed', '1'); } catch(e) {}
    });
  }
  var hero = document.querySelector('.gg-hero');
  var training = document.getElementById('training');

  var heroVisible = true;
  var trainingVisible = false;

  function updateSticky() {
    if (!stickyCta) return;
    if (!heroVisible && !trainingVisible) {
      stickyCta.classList.add('is-visible');
    } else {
      stickyCta.classList.remove('is-visible');
    }
  }

  if (hero) {
    new IntersectionObserver(function(entries) {
      heroVisible = entries[0].isIntersecting;
      updateSticky();
    }).observe(hero);
  }
  if (training) {
    new IntersectionObserver(function(entries) {
      trainingVisible = entries[0].isIntersecting;
      updateSticky();
    }).observe(training);
  }

  // Scroll fade-in — progressive enhancement
  // Enable animations only after JS loads; content stays visible without JS
  var pageWrapper = document.querySelector('.gg-neo-brutalist-page');
  if (pageWrapper) {
    pageWrapper.classList.add('gg-animations-ready');
  }

  var fadeObserver = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        fadeObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15 });

  document.querySelectorAll('.gg-fade-section').forEach(function(el) {
    // If element is already in viewport on page load, make it visible immediately
    var rect = el.getBoundingClientRect();
    if (rect.top < window.innerHeight && rect.bottom > 0) {
      el.classList.add('is-visible');
    } else {
      fadeObserver.observe(el);
    }
  });

  // Back to top button
  var btt = document.getElementById('gg-back-to-top');
  if (btt && hero) {
    new IntersectionObserver(function(entries) {
      if (entries[0].isIntersecting) {
        btt.classList.remove('is-visible');
      } else {
        btt.classList.add('is-visible');
      }
    }).observe(hero);
    btt.addEventListener('click', function() {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }
}

// TOC — scroll-spy + mobile toggle
(function() {
  var toc = document.getElementById('gg-toc');
  var tocToggle = document.getElementById('gg-toc-toggle');
  var tocLinks = document.getElementById('gg-toc-links');
  if (!toc) return;

  // Mobile toggle
  if (tocToggle && tocLinks) {
    tocToggle.addEventListener('click', function() {
      var expanded = tocToggle.getAttribute('aria-expanded') === 'true';
      tocToggle.setAttribute('aria-expanded', !expanded);
      tocLinks.classList.toggle('is-open', !expanded);
    });
    // Close on link click (mobile)
    tocLinks.querySelectorAll('a').forEach(function(a) {
      a.addEventListener('click', function() {
        tocToggle.setAttribute('aria-expanded', 'false');
        tocLinks.classList.remove('is-open');
      });
    });
  }

  // Scroll-spy: highlight active section in TOC
  var tocAnchors = toc.querySelectorAll('a[data-toc-target]');
  if (!tocAnchors.length) return;
  var sectionIds = Array.from(tocAnchors).map(function(a) { return a.getAttribute('data-toc-target'); });
  var sections = sectionIds.map(function(id) { return document.getElementById(id); }).filter(Boolean);
  if (!sections.length) return;

  var spyObserver = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        tocAnchors.forEach(function(a) { a.classList.remove('gg-toc-active'); });
        var active = toc.querySelector('a[data-toc-target="' + entry.target.id + '"]');
        if (active) active.classList.add('gg-toc-active');
      }
    });
  }, { rootMargin: '-' + (parseInt(getComputedStyle(document.documentElement).getPropertyValue('--gg-header-height')) || 80) + 'px 0px -60% 0px', threshold: 0 });

  sections.forEach(function(s) { spyObserver.observe(s); });
})();

// Reading progress bar
(function() {
  var bar = document.getElementById('gg-reading-progress-bar');
  if (!bar) return;
  var ticking = false;
  window.addEventListener('scroll', function() {
    if (!ticking) {
      requestAnimationFrame(function() {
        var scrollTop = window.scrollY;
        var docHeight = document.documentElement.scrollHeight - window.innerHeight;
        var pct = docHeight > 0 ? Math.min((scrollTop / docHeight) * 100, 100) : 0;
        bar.style.width = pct + '%';
        ticking = false;
      });
      ticking = true;
    }
  }, { passive: true });
})();

// News ticker — multi-source (Google News + Reddit)
(function() {
  var ticker = document.getElementById('gg-news-ticker');
  var feed = document.getElementById('gg-news-feed');
  if (!ticker || !feed) return;
  var query = ticker.getAttribute('data-query');
  if (!query) return;

  function parseItem(item) {
    var title = item.title || '';
    var source = item.author || '';
    var dashIdx = title.lastIndexOf(' - ');
    if (!source && dashIdx > 0) {
      source = title.substring(dashIdx + 3).trim();
      title = title.substring(0, dashIdx).trim();
    }
    return { title: title, link: item.link, source: source, date: new Date(item.pubDate) };
  }

  // Use quoted query for exact match in Google News
  var newsUrl = 'https://api.rss2json.com/v1/api.json?rss_url=' + encodeURIComponent(
    'https://news.google.com/rss/search?q=' + encodeURIComponent('"' + query.replace(/\+/g, ' ') + '"') + '&hl=en-US&gl=US&ceid=US:en');
  var redditUrl = 'https://api.rss2json.com/v1/api.json?rss_url=' + encodeURIComponent(
    'https://www.reddit.com/search.rss?q=' + encodeURIComponent('"' + query.replace(/\+/g, ' ') + '"') + '&sort=new&t=year');

  // Build keywords from race name for relevance filtering
  var nameWords = query.replace(/\+/g, ' ').toLowerCase().split(' ').filter(function(w) { return w.length > 2; });

  // Timeout helper — abort fetch after 6 seconds
  function fetchWithTimeout(url, ms) {
    var controller = new AbortController();
    var timer = setTimeout(function() { controller.abort(); }, ms);
    return fetch(url, { signal: controller.signal })
      .then(function(r) { clearTimeout(timer); return r.json(); })
      .catch(function() { clearTimeout(timer); return { items: [] }; });
  }

  Promise.allSettled([
    fetchWithTimeout(newsUrl, 6000),
    fetchWithTimeout(redditUrl, 6000)
  ]).then(function(results) {
    var all = [];
    results.forEach(function(result) {
      if (result.status === 'fulfilled' && result.value.items) {
        result.value.items.forEach(function(item) {
          var parsed = parseItem(item);
          // Relevance filter: title must contain at least one key word from race name
          var titleLow = parsed.title.toLowerCase();
          var relevant = nameWords.some(function(w) { return titleLow.indexOf(w) !== -1; });
          if (relevant) all.push(parsed);
        });
      }
    });

    // Sort by date descending, take top 8
    all.sort(function(a, b) { return b.date - a.date; });
    all = all.slice(0, 8);

    if (all.length === 0) {
      ticker.style.display = 'none';
      return;
    }

    function buildTickerItems(items) {
      var frag = document.createDocumentFragment();
      items.forEach(function(item, i) {
        if (i > 0) {
          var sep = document.createElement('span');
          sep.className = 'gg-news-ticker-sep';
          sep.textContent = '\u25C6';
          frag.appendChild(sep);
        }
        var span = document.createElement('span');
        span.className = 'gg-news-ticker-item';
        var a = document.createElement('a');
        a.href = item.link;
        a.target = '_blank';
        a.rel = 'noopener';
        a.textContent = item.title;
        span.appendChild(a);
        if (item.source) {
          var src = document.createElement('span');
          src.className = 'gg-news-ticker-source';
          src.textContent = item.source;
          span.appendChild(src);
        }
        frag.appendChild(span);
      });
      return frag;
    }
    feed.innerHTML = '';
    feed.appendChild(buildTickerItems(all));
    ticker.style.display = '';
    // Spacer + duplicate for seamless loop
    var spacer = document.createElement('span');
    spacer.style.padding = '0 80px';
    feed.appendChild(spacer);
    feed.appendChild(buildTickerItems(all));
  });
})();

// Review expand button — no inline handlers
document.querySelectorAll('.gg-review-expand-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    var expandable = btn.nextElementSibling;
    if (expandable) expandable.style.display = 'block';
    btn.style.display = 'none';
  });
});

// FAQ accordion toggle
document.querySelectorAll('.gg-faq-question').forEach(function(q) {
  q.addEventListener('click', function() {
    var item = this.parentElement;
    item.classList.toggle('open');
    this.setAttribute('aria-expanded', item.classList.contains('open'));
  });
  q.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      this.click();
    }
  });
});

// CTA click tracking — GA4. Explicit data-cta values keep copy tests from
// silently changing event classification.
(function() {
  if (typeof gtag !== 'function') return;
  var page = document.querySelector('.gg-neo-brutalist-page');
  var raceSlug = page ? (page.getAttribute('data-race-slug') || '') : '';
  var pageFormat = page ? (page.getAttribute('data-page-format') || '') : '';
  document.querySelectorAll('a[data-cta], a.gg-btn, a.gg-btn--outline, a.gg-prep-kit-link').forEach(function(link) {
    link.addEventListener('click', function() {
      var text = this.textContent.trim().replace(/\s+/g, ' ');
      var href = this.getAttribute('href') || '';
      var T = text.toUpperCase();
      var cta_type = this.getAttribute('data-cta') || 'other';
      if (cta_type === 'other' && T.indexOf('BUILD MY') !== -1) cta_type = 'build_plan';
      else if (T.indexOf('PREP KIT') !== -1) cta_type = 'prep_kit';
      else if (T.indexOf('COACHING') !== -1) cta_type = 'coaching';
      var section = this.closest('.gg-section, .gg-sticky-cta');
      var section_id = section ? (section.id || section.className.split(' ')[0]) : 'unknown';
      gtag('event', 'cta_click', {
        cta_type: cta_type,
        cta_text: text.substring(0, 50),
        cta_section: section_id,
        cta_href: href,
        race_slug: raceSlug,
        page_format: pageFormat
      });
    });
  });
})();

// Section exposure — one event per measured section after it becomes visible.
// This records real scrolling/viewport behavior without synthetic page-load hits.
(function() {
  var crumb = document.getElementById('gg-races-crumb');
  if (!crumb || !document.referrer) return;
  try {
    var referrer = new URL(document.referrer);
    var path = referrer.pathname;
    var isDiscovery = referrer.origin === window.location.origin && (
      path.indexOf('/gravel-races/') === 0 ||
      path.indexOf('/race/calendar/') === 0 ||
      path.indexOf('/race/best-') === 0 ||
      path.indexOf('/race/tier-') === 0 ||
      path.indexOf('/race/series/') === 0
    );
    if (isDiscovery) {
      crumb.href = path + referrer.search;
      crumb.textContent = 'Back to results';
    }
  } catch(e) {}
})();

(function() {
  if (typeof gtag !== 'function' || !('IntersectionObserver' in window)) return;
  var page = document.querySelector('.gg-neo-brutalist-page');
  var raceSlug = page ? (page.getAttribute('data-race-slug') || '') : '';
  var pageFormat = page ? (page.getAttribute('data-page-format') || '') : '';
  var seen = {};
  var observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (!entry.isIntersecting) return;
      var section = entry.target.getAttribute('data-measure-section') || ('deep_' + (entry.target.id || 'section'));
      if (!section || seen[section]) return;
      seen[section] = true;
      gtag('event', 'race_section_view', {race_slug: raceSlug, page_format: pageFormat, section: section, section_name: section});
      observer.unobserve(entry.target);
    });
  }, {threshold: 0.25});
  document.querySelectorAll('[data-measure-section], .gg-deep-dive > section[id]').forEach(function(el) { observer.observe(el); });
})();

document.querySelectorAll('a[data-related-race]').forEach(function(link) {
  link.addEventListener('click', function() {
    if (typeof gtag !== 'function') return;
    var page = document.querySelector('.gg-neo-brutalist-page');
    gtag('event', 'related_race_click', {
      race_slug: page ? (page.getAttribute('data-race-slug') || '') : '',
      page_format: page ? (page.getAttribute('data-page-format') || '') : '',
      related_race_slug: link.getAttribute('data-related-race') || ''
    });
  });
});

// Calendar download — avoids executable data in inline event attributes.
document.querySelectorAll('.gg-cal-btn--ics').forEach(function(link) {
  link.addEventListener('click', function(event) {
    event.preventDefault();
    var content = (link.getAttribute('data-ics-content') || '').replace(/\\n/g, '\n');
    if (!content) return;
    var blob = new Blob([content], {type: 'text/calendar'});
    var download = document.createElement('a');
    var objectUrl = URL.createObjectURL(blob);
    download.href = objectUrl;
    download.download = link.getAttribute('data-ics-filename') || 'race.ics';
    download.click();
    URL.revokeObjectURL(objectUrl);
  });
});

// Shared inline-form error display — never show a success state without a
// confirmed 2xx response from the worker (CLAUDE.md: "never show a success
// message without actually submitting the email").
function ggShowFormError(form, msg) {
  var err = form.querySelector('.gg-form-error');
  if (!err) {
    err = document.createElement('p');
    err.className = 'gg-form-error';
    err.setAttribute('role', 'alert');
    err.style.cssText = 'font-family:var(--gg-font-data);font-size:12px;color:var(--gg-color-error);font-weight:700;margin-top:8px';
    form.appendChild(err);
  }
  err.textContent = msg;
  err.style.display = 'block';
}
function ggClearFormError(form) {
  var err = form.querySelector('.gg-form-error');
  if (err) err.style.display = 'none';
}
var GG_FORM_ERROR_MSG = 'Something went wrong — please try again.';

// Email capture form — prep kit CTA
(function() {
  var WORKER_URL='https://fueling-lead-intake.gravelgodcoaching.workers.dev';
  var LS_KEY='gg-pk-fueling';
  var EXPIRY_DAYS=90;
  var form=document.getElementById('gg-email-capture-form');
  if(!form) return;

  /* Check if already captured */
  try{
    var cached=JSON.parse(localStorage.getItem(LS_KEY)||'null');
    if(cached&&cached.email&&cached.exp>Date.now()){
      /* Already captured — show success state */
      form.style.display='none';
      var success=document.getElementById('gg-email-capture-success');
      if(success) success.style.display='block';
      return;
    }
  }catch(e){}

  form.addEventListener('submit',function(e){
    e.preventDefault();
    var email=form.email.value.trim();
    if(!email||!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){
      alert('Please enter a valid email address.');return;
    }
    if(form.website&&form.website.value) return;
    ggClearFormError(form);
    /* POST to Worker */
    var payload={
      email:email,
      race_slug:form.race_slug.value,
      race_name:form.race_name.value,
      source:form.source.value,
      website:form.website.value
    };
    fetch(WORKER_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
      .then(function(r){
        if(!r.ok) throw new Error('bad status');
        /* Cache email — only after a confirmed successful submission */
        try{
          localStorage.setItem(LS_KEY,JSON.stringify({email:email,exp:Date.now()+EXPIRY_DAYS*86400000}));
        }catch(ex){}
        /* GA4 */
        if(typeof gtag==='function'){
          gtag('event','email_capture',{race_slug:form.race_slug.value,source:'race_profile'});
        }
        /* Show success state */
        form.style.display='none';
        var success=document.getElementById('gg-email-capture-success');
        if(success) success.style.display='block';
      })
      .catch(function(){
        ggShowFormError(form, GG_FORM_ERROR_MSG);
      });
  });
})();

// Plan ladder — race-specific plan capture (SITE-SYNC S2). Multiple
// independent forms can exist on one page (one per private/unlisted tier),
// so this attaches per-form instead of assuming a single #id like the
// prep-kit and date-reminder handlers above.
(function() {
  var WORKER_URL='https://fueling-lead-intake.gravelgodcoaching.workers.dev';
  var forms=document.querySelectorAll('.gg-plan-ladder-form');
  forms.forEach(function(form){
    form.addEventListener('submit',function(e){
      e.preventDefault();
      var email=form.email.value.trim();
      if(!email||!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){
        alert('Please enter a valid email address.');return;
      }
      if(form.website&&form.website.value) return;
      ggClearFormError(form);
      var payload={
        email:email,
        race_slug:form.race_slug.value,
        race_name:form.race_name.value,
        tier:form.tier.value,
        source:form.source.value,
        website:form.website.value
      };
      fetch(WORKER_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
        .then(function(r){
          if(!r.ok) throw new Error('bad status');
          if(typeof gtag==='function'){
            gtag('event','email_capture',{race_slug:form.race_slug.value,tier:form.tier.value,source:'race_plan_ladder'});
          }
          form.style.display='none';
          var success=form.nextElementSibling;
          if(success&&success.classList.contains('gg-plan-ladder-success')) success.style.display='block';
        })
        .catch(function(){
          ggShowFormError(form, GG_FORM_ERROR_MSG);
        });
    });
  });
})();

// Inline review form
(function() {
  var WORKER_URL='https://review-intake.gravelgodcoaching.workers.dev';
  var form=document.getElementById('gg-review-form');
  if(!form) return;

  /* Star rating interaction */
  var starBtns=document.querySelectorAll('.gg-review-star-btn');
  var starsInput=document.getElementById('gg-review-stars-val');
  starBtns.forEach(function(btn){
    btn.addEventListener('click',function(){
      var val=parseInt(this.getAttribute('data-star'));
      starsInput.value=val;
      starBtns.forEach(function(b){
        var active=parseInt(b.getAttribute('data-star'))<=val;
        b.classList.toggle('is-active',active);
        b.setAttribute('aria-checked',active?'true':'false');
      });
    });
    btn.addEventListener('mouseenter',function(){
      var val=parseInt(this.getAttribute('data-star'));
      starBtns.forEach(function(b){
        if(parseInt(b.getAttribute('data-star'))<=val) b.style.color='var(--gg-color-gold)';
        else b.style.color='var(--gg-color-tan)';
      });
    });
    btn.addEventListener('mouseleave',function(){
      starBtns.forEach(function(b){b.style.color='';});
    });
  });

  /* Character counts on textareas */
  document.querySelectorAll('.gg-review-charcount').forEach(function(el){
    var ta=document.getElementById(el.getAttribute('data-for'));
    if(ta){ta.addEventListener('input',function(){el.textContent=ta.value.length+'/500';});}
  });

  form.addEventListener('submit',function(e){
    e.preventDefault();
    var email=form.email.value.trim();
    var stars=parseInt(starsInput.value);
    if(!stars||stars<1||stars>5){alert('Please select a star rating.');return;}
    if(!email||!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){alert('Please enter a valid email.');return;}
    if(form.website&&form.website.value) return;

    ggClearFormError(form);
    var payload={
      email:email,
      source:'race_review',
      race_slug:form.race_slug.value,
      race_name:form.race_name.value,
      stars:stars,
      year_raced:form.year_raced.value,
      would_race_again:form.would_race_again.value,
      finish_position:form.finish_position.value,
      best:form.best.value,
      worst:form.worst.value,
      website:form.website.value
    };
    fetch(WORKER_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
      .then(function(r){
        if(!r.ok) throw new Error('bad status');
        if(typeof gtag==='function') gtag('event','review_submit',{race_slug:form.race_slug.value,stars:stars});

        /* Show success, clear char counts */
        document.querySelectorAll('.gg-review-charcount').forEach(function(el){el.textContent='0/500';});
        document.getElementById('gg-review-form-wrap').querySelector('.gg-review-form').style.display='none';
        document.getElementById('gg-review-success').style.display='block';
      })
      .catch(function(){
        ggShowFormError(form, GG_FORM_ERROR_MSG);
      });
  });
})();

// Lite-YouTube facade — click to load iframe (zero perf cost until interaction)
document.querySelectorAll('.gg-lite-youtube').forEach(function(el) {
  el.addEventListener('click', function() {
    var id = el.getAttribute('data-videoid');
    if (!id) return;
    var iframe = document.createElement('iframe');
    iframe.src = 'https://www.youtube-nocookie.com/embed/' + id + '?autoplay=1&rel=0';
    iframe.allow = 'accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture';
    iframe.allowFullscreen = true;
    iframe.loading = 'lazy';
    el.textContent = '';
    el.appendChild(iframe);
  });
});

/* ── Train for Race: Workout panel toggle ── */
(function() {
  var toggleBtn = document.getElementById('gg-pack-toggle-btn');
  var panel = document.getElementById('gg-pack-workouts-panel');
  var toggleText = document.getElementById('gg-pack-toggle-text');
  if (!toggleBtn || !panel) return;
  // Read actual workout count from panel instead of hardcoding
  var workoutCount = panel.querySelectorAll('.gg-pack-workout').length;
  var seeText = 'SEE ' + workoutCount + ' SAMPLE WORKOUTS';
  var hideText = 'HIDE SAMPLE WORKOUTS';
  // Set initial text from actual count (defense against generator/JS mismatch)
  if (toggleText) toggleText.textContent = seeText;
  toggleBtn.addEventListener('click', function() {
    var expanded = toggleBtn.getAttribute('aria-expanded') === 'true';
    if (expanded) {
      panel.style.display = 'none';
      toggleBtn.setAttribute('aria-expanded', 'false');
      if (toggleText) toggleText.textContent = seeText;
      toggleBtn.focus();
    } else {
      panel.style.display = 'block';
      toggleBtn.setAttribute('aria-expanded', 'true');
      if (toggleText) toggleText.textContent = hideText;
      // Move focus to panel for screen readers
      panel.setAttribute('tabindex', '-1');
      panel.focus();
      panel.removeAttribute('tabindex');
      if (typeof gtag === 'function') {
        gtag('event', 'workouts_panel_expand', {
          race_slug: (window.__GG_RACE_DATA__ || {}).slug || '',
          workout_count: workoutCount
        });
      }
    }
  });
})();

/* ── Train for Race: Workout expand/collapse ── */
document.querySelectorAll('.gg-pack-workout').forEach(function(card) {
  card.addEventListener('click', function(e) {
    if (e.target.closest('a')) return;
    var detail = this.querySelector('.gg-pack-workout-detail');
    var wasActive = this.classList.contains('active');
    // Close all others
    document.querySelectorAll('.gg-pack-workout').forEach(function(c) {
      c.classList.remove('active');
      var d = c.querySelector('.gg-pack-workout-detail');
      if (d) d.style.display = 'none';
    });
    if (!wasActive) {
      this.classList.add('active');
      if (detail) detail.style.display = 'block';
    }
  });
});

/* ── Plan Preview Mini-Configurator ── */
(function() {
  var rd = window.__GG_RACE_DATA__;
  if (!rd) return;
  var btn = document.getElementById('gg-cfg-btn');
  var dateInput = document.getElementById('gg-cfg-date');
  if (!btn || !dateInput) return;
  var previewActive = false;

  // Pre-fill race date from date_specific — handles multiple formats:
  //   "2026: June 6"                          → June 6, 2026
  //   "2026: June 6-7"                        → June 6, 2026 (first day)
  //   "July 20, 2026 (subject to ...)"        → July 20, 2026
  //   "2026: September 20 - 21"               → September 20, 2026
  //   "TBD" / "check website"                 → no pre-fill
  function parseRaceDate(ds) {
    if (!ds) return null;
    var parsed = null;
    // Format 1: "YYYY: Month Day..." (most common)
    var m1 = ds.match(/(\d{4}):\s*([A-Za-z]+)\s+(\d{1,2})/);
    if (m1) {
      parsed = new Date(m1[2] + ' ' + m1[3] + ', ' + m1[1]);
      if (!isNaN(parsed.getTime())) return parsed;
    }
    // Format 2: "Month Day, YYYY" anywhere in string
    var m2 = ds.match(/([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})/);
    if (m2) {
      parsed = new Date(m2[1] + ' ' + m2[2] + ', ' + m2[3]);
      if (!isNaN(parsed.getTime())) return parsed;
    }
    // Format 3: ISO-ish "YYYY-MM-DD" anywhere
    var m3 = ds.match(/(\d{4})-(\d{2})-(\d{2})/);
    if (m3) {
      parsed = new Date(m3[1] + '-' + m3[2] + '-' + m3[3] + 'T00:00:00');
      if (!isNaN(parsed.getTime())) return parsed;
    }
    return null;
  }
  var raceDateParsed = parseRaceDate(rd.date_specific);
  if (raceDateParsed) {
    var y = raceDateParsed.getFullYear();
    var mo = String(raceDateParsed.getMonth() + 1).padStart(2, '0');
    var da = String(raceDateParsed.getDate()).padStart(2, '0');
    dateInput.value = y + '-' + mo + '-' + da;
  }

  // Level config: VO2 range, threshold range (matches nate_workout_generator.py scaling)
  var LEVELS = {
    beginner:     { vo2: '105\u2013108% FTP', thr: '92\u201396% FTP'  },
    intermediate: { vo2: '108\u2013112% FTP', thr: '96\u2013100% FTP' },
    advanced:     { vo2: '112\u2013118% FTP', thr: '100\u2013105% FTP'},
    elite:        { vo2: '115\u2013120% FTP', thr: '105\u2013108% FTP'}
  };

  // Hours config: quality sessions, endurance rides, avg hours
  var HOURS = {
    '6-8':  { quality: 2, endurance: 2, avg: 7  },
    '8-12': { quality: 3, endurance: 2, avg: 10 },
    '12-16':{ quality: 3, endurance: 3, avg: 14 },
    '16+':  { quality: 4, endurance: 3, avg: 18 }
  };

  // Category to phase mapping — names must match web/race-packs/*.json exactly
  // Source of truth: scripts/generate_race_pack_previews.py weight matrix (19 categories)
  var PHASE_MAP = {
    'Endurance': 'base', 'HVLI_Extended': 'base', 'LT1_MAF': 'base',
    'Tempo': 'base', 'Cadence_Work': 'base',
    'TT_Threshold': 'build', 'Over_Under': 'build', 'Mixed_Climbing': 'build',
    'SFR_Muscle_Force': 'build', 'Blended': 'build', 'G_Spot': 'build',
    'Norwegian_Double': 'build',
    'VO2max': 'peak', 'Durability': 'peak', 'Race_Simulation': 'peak',
    'Gravel_Specific': 'peak', 'Anaerobic_Capacity': 'peak',
    'Critical_Power': 'peak', 'Sprint_Neuromuscular': 'peak'
  };

  var PHASE_LABELS = { base: 'BASE PHASE', build: 'BUILD PHASE', peak: 'PEAK PHASE' };
  var PHASE_CSS = { base: 'gg-cfg-phase-base', build: 'gg-cfg-phase-build', peak: 'gg-cfg-phase-peak' };

  btn.addEventListener('click', function() {
    var level = document.getElementById('gg-cfg-level').value;
    var hours = document.getElementById('gg-cfg-hours').value;
    var raceDateStr = dateInput.value;

    if (!raceDateStr) {
      dateInput.focus();
      return;
    }

    var raceDate = new Date(raceDateStr + 'T00:00:00');
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var diffMs = raceDate.getTime() - today.getTime();
    var weeksRaw = Math.ceil(diffMs / (7 * 24 * 60 * 60 * 1000));
    var weeks = Math.max(4, weeksRaw);

    // Phase split
    var taper = 1;
    var remaining = weeks - taper;
    var base = Math.round(remaining * 0.4);
    var build = Math.round(remaining * 0.35);
    var peak = remaining - base - build;
    if (peak < 1) { peak = 1; base = Math.max(1, base - 1); }

    // Price
    var price = Math.min(249, Math.max(60, weeks * 15));

    // Session structure
    var hCfg = HOURS[hours] || HOURS['8-12'];
    var lCfg = LEVELS[level] || LEVELS['intermediate'];
    var sessionsPerWeek = hCfg.quality + hCfg.endurance + 1; // +1 for recovery/easy ride
    var totalWorkouts = weeks * sessionsPerWeek;

    // Build summary
    var summaryEl = document.getElementById('gg-cfg-summary');
    var titleEl = document.getElementById('gg-cfg-summary-title');
    var timelineEl = document.getElementById('gg-cfg-timeline');
    var barEl = document.getElementById('gg-cfg-timeline-bar');
    var detailsEl = document.getElementById('gg-cfg-details');

    titleEl.textContent = 'YOUR ' + weeks + '-WEEK ' + rd.race_name.toUpperCase() + ' PLAN';

    // Timeline text
    timelineEl.textContent = '';
    var phases = [
      { name: 'BASE', wk: base },
      { name: 'BUILD', wk: build },
      { name: 'PEAK', wk: peak },
      { name: 'TAPER', wk: taper }
    ];
    phases.forEach(function(p, idx) {
      if (idx > 0) {
        var sep = document.createElement('span');
        sep.className = 'gg-cfg-timeline-sep';
        sep.textContent = '\u25b8';
        timelineEl.appendChild(sep);
      }
      var sp = document.createElement('span');
      sp.textContent = p.name + ' (' + p.wk + 'wk)';
      timelineEl.appendChild(sp);
    });

    // Timeline bar (proportional widths)
    barEl.textContent = '';
    var colors = ['base', 'build', 'peak', 'taper'];
    phases.forEach(function(p, idx) {
      var seg = document.createElement('div');
      seg.className = 'gg-cfg-bar-' + colors[idx];
      seg.style.flex = String(p.wk);
      barEl.appendChild(seg);
    });

    // Details text
    detailsEl.textContent = '';
    var line1 = document.createElement('div');
    line1.textContent = hCfg.quality + ' quality sessions + ' + hCfg.endurance + ' endurance rides/week \u00b7 ' + hCfg.avg + ' hrs/week';
    detailsEl.appendChild(line1);
    var line2 = document.createElement('div');
    line2.textContent = totalWorkouts + ' structured workouts \u00b7 ZWO files for Zwift/Wahoo/Garmin';
    detailsEl.appendChild(line2);

    summaryEl.style.display = 'block';

    // Phase badges on workout cards
    document.querySelectorAll('.gg-pack-workout').forEach(function(card) {
      var cat = card.getAttribute('data-workout-cat') || '';
      var phase = PHASE_MAP[cat] || 'build';
      var badge = card.querySelector('.gg-cfg-phase-badge');
      if (badge) {
        badge.textContent = PHASE_LABELS[phase] || 'BUILD PHASE';
        badge.className = 'gg-cfg-phase-badge ' + (PHASE_CSS[phase] || 'gg-cfg-phase-build');
        badge.style.display = 'block';
      }
      // Level annotation
      var note = card.querySelector('.gg-cfg-level-note');
      if (note) {
        note.textContent = 'YOUR TARGETS: VO2 at ' + lCfg.vo2 + ' \u00b7 Threshold at ' + lCfg.thr;
        note.style.display = 'block';
      }
    });

    // Update default CTA to personalized CTA
    var defaultCta = document.getElementById('gg-pack-cta-default');
    var cfgCta = document.getElementById('gg-cfg-cta');
    var cfgCtaLink = document.getElementById('gg-cfg-cta-link');
    var cfgCtaDetail = document.getElementById('gg-cfg-cta-detail');
    if (defaultCta) {
      defaultCta.style.display = 'none';
      defaultCta.setAttribute('aria-hidden', 'true');
    }
    if (cfgCta && cfgCtaLink && cfgCtaDetail) {
      var ctaText = 'GET YOUR ' + weeks + '-WEEK ' + rd.race_name.toUpperCase() + ' PLAN \u2014 $' + price;
      cfgCtaLink.textContent = ctaText;
      cfgCtaLink.removeAttribute('tabindex');
      // Pass configurator selections to questionnaire for pre-population
      cfgCtaLink.href = '/questionnaire/?race=' + encodeURIComponent(rd.slug) +
        '&level=' + encodeURIComponent(level) +
        '&hours=' + encodeURIComponent(hours) +
        '&weeks=' + weeks;
      cfgCtaDetail.textContent = totalWorkouts + ' workouts \u00b7 ZWO files \u00b7 Phase-periodized for ' + rd.race_name;
      cfgCta.style.display = 'block';
      cfgCta.removeAttribute('aria-hidden');
    }

    // Update sticky CTA
    var stickyText = document.getElementById('gg-sticky-cta-text');
    var stickyLink = document.getElementById('gg-sticky-cta-link');
    if (stickyText) {
      stickyText.textContent = weeks + '-WEEK PLAN \u2014 $' + price;
    }
    if (stickyLink) {
      stickyLink.href = '/questionnaire/?race=' + encodeURIComponent(rd.slug) +
        '&level=' + encodeURIComponent(level) +
        '&hours=' + encodeURIComponent(hours) +
        '&weeks=' + weeks;
    }

    previewActive = true;
    btn.textContent = 'PREVIEW MY PLAN';

    // GA4 events
    if (typeof gtag === 'function') {
      gtag('event', 'configurator_preview', {
        race_slug: rd.slug,
        level: level,
        hours: hours,
        weeks: weeks,
        price: price
      });
    }
  });

  // Track configurator interactions + mark preview stale when inputs change
  ['gg-cfg-level', 'gg-cfg-hours', 'gg-cfg-date'].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', function() {
        // Mark preview as stale — hide summary and reset badges
        if (previewActive) {
          var sum = document.getElementById('gg-cfg-summary');
          if (sum) sum.style.display = 'none';
          document.querySelectorAll('.gg-cfg-phase-badge').forEach(function(b) { b.style.display = 'none'; });
          document.querySelectorAll('.gg-cfg-level-note').forEach(function(n) { n.style.display = 'none'; });
          var defCta = document.getElementById('gg-pack-cta-default');
          var cfgC = document.getElementById('gg-cfg-cta');
          if (defCta) { defCta.style.display = ''; defCta.removeAttribute('aria-hidden'); }
          if (cfgC) { cfgC.style.display = 'none'; cfgC.setAttribute('aria-hidden', 'true'); }
          var stickyT = document.getElementById('gg-sticky-cta-text');
          if (stickyT) stickyT.textContent = 'BUILD MY PLAN \u2014 $15/WK';
          previewActive = false;
          btn.textContent = 'UPDATE PREVIEW';
        }
        if (typeof gtag === 'function') {
          gtag('event', 'configurator_interact', {
            race_slug: rd.slug,
            field: id.replace('gg-cfg-', ''),
            value: el.value
          });
        }
      });
    }
  });

  // Track personalized CTA clicks
  var cfgCtaLinkEl = document.getElementById('gg-cfg-cta-link');
  if (cfgCtaLinkEl) {
    cfgCtaLinkEl.addEventListener('click', function() {
      if (typeof gtag === 'function') {
        gtag('event', 'configurator_cta_click', {
          race_slug: rd.slug,
          cta_text: cfgCtaLinkEl.textContent
        });
      }
    });
  }
})();

// Date reminder handler
(function() {
  var WORKER_URL='https://fueling-lead-intake.gravelgodcoaching.workers.dev';
  var button=document.getElementById('gg-date-reminder-opt-in');
  if(!button) return;
  button.addEventListener('click',function(e) {
    e.preventDefault();
    var cached=null;
    try { cached=JSON.parse(localStorage.getItem('gg-pk-fueling')||'null'); } catch(ex) {}
    var email=cached&&cached.email ? cached.email : '';
    if(!email) return;
    var slug=button.getAttribute('data-race-slug')||'';
    var raceDate=button.getAttribute('data-race-date')||'';
    var container=document.getElementById('gg-email-capture-success')||button.parentElement;
    ggClearFormError(container);
    var payload={
      email:email,
      source:'date_reminder',
      race_slug:slug,
      race_date:raceDate,
      website:''
    };
    fetch(WORKER_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
      .then(function(r){
        if(!r.ok) throw new Error('bad status');
        if(typeof gtag==='function') {
          gtag('event','email_capture',{source:'date_reminder',race_slug:slug});
        }
        button.textContent='\u2713 We will remind you 12 weeks out.';
        button.disabled=true;
      })
      .catch(function(){
        ggShowFormError(container, GG_FORM_ERROR_MSG);
      });
  });
})();

// Deep-dive disclosures — keep trust/SEO content server-rendered while reducing
// the first visual pass. Hash targets automatically open their owning section.
(function() {
  var hash = window.location.hash ? window.location.hash.substring(1) : '';
  var sections = document.querySelectorAll('.gg-deep-dive > .gg-section, .gg-deep-dive > .gg-racer-reviews');
  function setExpanded(section, expanded) {
    var header = section.querySelector('.gg-section-header');
    var body = section.querySelector('.gg-section-body');
    if (!header || !body) return;
    section.classList.toggle('gg-section-collapsed', !expanded);
    body.hidden = !expanded;
    header.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    var chevron = header.querySelector('.gg-section-chevron');
    if (chevron) chevron.textContent = expanded ? '\u25B4' : '\u25BE';
  }
  sections.forEach(function(section) {
    var target = hash ? document.getElementById(hash) : null;
    var startExpanded = Boolean(target && (target === section || section.contains(target)));
    if (startExpanded && target && target.tagName === 'DETAILS') target.open = true;
    section.classList.add('gg-section-collapsible');
    var header = section.querySelector('.gg-section-header');
    var body = section.querySelector('.gg-section-body');
    if (!header || !body) return;
    header.setAttribute('role', 'button');
    header.setAttribute('tabindex', '0');
    header.style.cursor = 'pointer';
    var chevron = document.createElement('span');
    chevron.className = 'gg-section-chevron';
    chevron.setAttribute('aria-hidden', 'true');
    header.appendChild(chevron);
    function toggle() {
      setExpanded(section, section.classList.contains('gg-section-collapsed'));
    }
    header.addEventListener('click', toggle);
    header.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); }
    });
    setExpanded(section, startExpanded);
  });
  document.querySelectorAll('.gg-breakdown-tile, .gg-toc a').forEach(function(link) {
    link.addEventListener('click', function() {
      var id = (link.getAttribute('href') || '').replace(/^#/, '');
      var target = id ? document.getElementById(id) : null;
      var section = target ? target.closest('.gg-deep-dive > .gg-section, .gg-deep-dive > .gg-racer-reviews') : null;
      if (target && target.tagName === 'DETAILS') target.open = true;
      if (section) setExpanded(section, true);
    });
  });
})();