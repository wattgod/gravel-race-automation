"""Shared site header used by all generated pages.

Provides get_site_header_html() and get_site_header_css() for a consistent
5-item dropdown nav (RACES, PRODUCTS, SERVICES, ARTICLES, ABOUT) across
homepage, race profiles, coaching, about, prep kits, series hubs, guide,
methodology, state hubs, vs pages, power rankings, calendar, tier hubs,
and coaching apply pages.
"""
from __future__ import annotations

SITE_BASE_URL = "https://gravelgodcycling.com"
SUBSTACK_URL = "https://gravelgodcycling.substack.com"


def get_site_header_html(active: str | None = None) -> str:
    """Return the shared site header HTML block.

    Args:
        active: Which top-level nav item is current. One of:
                "races", "products", "services", "articles", "about".
                Adds aria-current="page" to the matching top-level link.
    """

    def _aria(key: str) -> str:
        return ' aria-current="page"' if active == key else ""

    return f'''<header class="gg-site-header">
  <div class="gg-site-header-inner">
    <a href="{SITE_BASE_URL}/" class="gg-site-header-logo">
      <img src="https://gravelgodcycling.com/wp-content/uploads/2021/09/cropped-Gravel-God-logo.png" alt="Gravel God" width="50" height="50">
    </a>
    <nav class="gg-site-header-nav">
      <div class="gg-site-header-item">
        <a href="{SITE_BASE_URL}/gravel-races/"{_aria("races")}>RACES</a>
        <div class="gg-site-header-dropdown">
          <a href="{SITE_BASE_URL}/gravel-races/">All Gravel Races</a>
          <a href="{SITE_BASE_URL}/race/methodology/">How We Rate</a>
        </div>
      </div>
      <div class="gg-site-header-item">
        <a href="{SITE_BASE_URL}/products/training-plans/"{_aria("products")}>PRODUCTS</a>
        <div class="gg-site-header-dropdown">
          <a href="{SITE_BASE_URL}/products/training-plans/">Custom Training Plans</a>
          <a href="{SITE_BASE_URL}/guide/">Gravel Handbook</a>
        </div>
      </div>
      <div class="gg-site-header-item">
        <a href="{SITE_BASE_URL}/coaching/"{_aria("services")}>SERVICES</a>
        <div class="gg-site-header-dropdown">
          <a href="{SITE_BASE_URL}/coaching/">Coaching</a>
          <a href="{SITE_BASE_URL}/consulting/">Consulting</a>
        </div>
      </div>
      <div class="gg-site-header-item">
        <a href="{SITE_BASE_URL}/articles/"{_aria("articles")}>ARTICLES</a>
        <div class="gg-site-header-dropdown">
          <a href="{SUBSTACK_URL}" target="_blank" rel="noopener">Slow Mid 38s</a>
          <a href="{SITE_BASE_URL}/articles/">Hot Takes</a>
          <a href="{SITE_BASE_URL}/insights/">The State of Gravel</a>
          <a href="{SITE_BASE_URL}/fueling-methodology/">White Papers</a>
        </div>
      </div>
      <a href="{SITE_BASE_URL}/about/"{_aria("about")}>ABOUT</a>
    </nav>
  </div>
</header>'''


def get_site_header_css() -> str:
    """Return the site header CSS using var(--gg-*) design tokens."""
    return """
/* ── Site Header ──────────────────────────────────────── */
.gg-site-header { padding: 16px 24px; border-bottom: 2px solid var(--gg-color-gold); }
.gg-site-header-inner { display: flex; align-items: center; justify-content: space-between; max-width: 960px; margin: 0 auto; }
.gg-site-header-logo img { display: block; height: 50px; width: auto; }
.gg-site-header-nav { display: flex; gap: 24px; align-items: center; }
.gg-site-header-nav > a,
.gg-site-header-item > a { color: var(--gg-color-dark-brown); text-decoration: none; font-family: var(--gg-font-data); font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; transition: color 0.2s; }
.gg-site-header-nav > a:hover,
.gg-site-header-item > a:hover { color: var(--gg-color-gold); }
.gg-site-header-nav > a[aria-current="page"],
.gg-site-header-item > a[aria-current="page"] { color: var(--gg-color-gold); }

/* Dropdown container */
.gg-site-header-item { position: relative; }
.gg-site-header-dropdown { display: none; position: absolute; top: 100%; left: 0; min-width: 200px; padding: 8px 0; background: var(--gg-color-warm-paper); border: 2px solid var(--gg-color-dark-brown); z-index: 1000; }
.gg-site-header-item:hover .gg-site-header-dropdown,
.gg-site-header-item:focus-within .gg-site-header-dropdown { display: block; }
.gg-site-header-dropdown a { display: block; padding: 8px 16px; font-family: var(--gg-font-data); font-size: 11px; font-weight: 400; letter-spacing: 1px; color: var(--gg-color-dark-brown); text-decoration: none; transition: color 0.2s; }
.gg-site-header-dropdown a:hover { color: var(--gg-color-gold); }

/* Mobile: flat nav, no dropdowns */
@media (max-width: 600px) {
  .gg-site-header { padding: 12px 16px; }
  .gg-site-header-inner { flex-wrap: wrap; justify-content: center; gap: 10px; }
  .gg-site-header-logo img { height: 40px; }
  .gg-site-header-nav { gap: 12px; flex-wrap: wrap; justify-content: center; }
  .gg-site-header-nav > a,
  .gg-site-header-item > a { font-size: 10px; letter-spacing: 1.5px; }
  .gg-site-header-dropdown { display: none !important; }
}
"""


def get_site_header_js() -> str:
    """Return the site header JavaScript for hamburger toggle and sticky auto-hide."""
    return """
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

// ── Trail capture — first-party breadcrumb for personalized welcome emails ──
// (docs/specs/friend-first-sequences.md §4.2). No network requests here; the
// email-capture forms read these keys when a visitor later subscribes.
// Every localStorage access is wrapped in try/catch (private browsing throws).
(function() {
  // Race profile pages: /race/{slug}/ — keep last 5 viewed, most-recent-first,
  // deduped by slug.
  try {
    var slugMatch = window.location.pathname.match(/^\/race\/([^\/]+)\//);
    var slug = slugMatch ? slugMatch[1] : '';
    if (slug) {
      var titleEl = document.querySelector('.gg-hero h1');
      var name = titleEl ? titleEl.textContent.trim() : '';
      if (!name) {
        var docTitle = document.title || '';
        name = (docTitle.split(' Review ')[0] || docTitle.split('|')[0] || '').trim();
      }
      if (name) {
        var races = [];
        try {
          races = JSON.parse(localStorage.getItem('gg_viewed_races') || '[]');
        } catch (e2) {}
        if (!Array.isArray(races)) races = [];
        races = races.filter(function(r) { return r && r.slug !== slug; });
        races.unshift({ slug: slug, name: name });
        localStorage.setItem('gg_viewed_races', JSON.stringify(races.slice(0, 5)));
      }
    }
  } catch (e) {}

  // Guide chapter pages carry their title in .gg-guide-chapter-title — last
  // chapter read wins (single value, no history).
  try {
    var chapterEl = document.querySelector('.gg-guide-chapter-title');
    if (chapterEl) {
      var chapterTitle = chapterEl.textContent.trim();
      if (chapterTitle) localStorage.setItem('gg_guide_chapter', chapterTitle);
    }
  } catch (e) {}
})();
"""
