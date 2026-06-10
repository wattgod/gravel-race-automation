"""Shared site header used by all generated pages.

Provides get_site_header_html(), get_site_header_css(), and
get_site_header_js() for a consistent sticky header with hamburger
mobile nav across homepage, race profiles, coaching, about, prep kits,
series hubs, guide, methodology, state hubs, vs pages, power rankings,
calendar, tier hubs, and coaching apply pages.
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

    return f'''<header class="gg-site-header" id="gg-site-header">
  <div class="gg-site-header-inner">
    <a href="{SITE_BASE_URL}/" class="gg-site-header-logo">
      <img src="https://gravelgodcycling.com/wp-content/uploads/2021/09/cropped-Gravel-God-logo.png" alt="Gravel God" width="50" height="50">
    </a>
    <nav class="gg-site-header-nav" id="gg-nav-desktop">
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
    <button class="gg-hamburger" id="gg-hamburger" aria-label="Open menu" aria-expanded="false" aria-controls="gg-mobile-nav">
      <span class="gg-hamburger-bar"></span>
      <span class="gg-hamburger-bar"></span>
      <span class="gg-hamburger-bar"></span>
    </button>
  </div>
  <nav class="gg-mobile-nav" id="gg-mobile-nav" aria-label="Mobile navigation">
    <div class="gg-mobile-nav-group">
      <button class="gg-mobile-nav-toggle" aria-expanded="false">RACES</button>
      <div class="gg-mobile-nav-sub">
        <a href="{SITE_BASE_URL}/gravel-races/">All Gravel Races</a>
        <a href="{SITE_BASE_URL}/race/methodology/">How We Rate</a>
      </div>
    </div>
    <div class="gg-mobile-nav-group">
      <button class="gg-mobile-nav-toggle" aria-expanded="false">PRODUCTS</button>
      <div class="gg-mobile-nav-sub">
        <a href="{SITE_BASE_URL}/products/training-plans/">Custom Training Plans</a>
        <a href="{SITE_BASE_URL}/guide/">Gravel Handbook</a>
      </div>
    </div>
    <div class="gg-mobile-nav-group">
      <button class="gg-mobile-nav-toggle" aria-expanded="false">SERVICES</button>
      <div class="gg-mobile-nav-sub">
        <a href="{SITE_BASE_URL}/coaching/">Coaching</a>
        <a href="{SITE_BASE_URL}/consulting/">Consulting</a>
      </div>
    </div>
    <div class="gg-mobile-nav-group">
      <button class="gg-mobile-nav-toggle" aria-expanded="false">ARTICLES</button>
      <div class="gg-mobile-nav-sub">
        <a href="{SUBSTACK_URL}" target="_blank" rel="noopener">Slow Mid 38s</a>
        <a href="{SITE_BASE_URL}/articles/">Hot Takes</a>
        <a href="{SITE_BASE_URL}/insights/">The State of Gravel</a>
        <a href="{SITE_BASE_URL}/fueling-methodology/">White Papers</a>
      </div>
    </div>
    <a href="{SITE_BASE_URL}/about/" class="gg-mobile-nav-link">ABOUT</a>
  </nav>
</header>'''


def get_site_header_css() -> str:
    """Return the site header CSS using var(--gg-*) design tokens."""
    return """
/* ── Site Header — sticky with auto-hide ─────────────── */
.gg-site-header {
  position: sticky; top: 0; z-index: 900;
  padding: 16px 24px;
  border-bottom: 2px solid var(--gg-color-gold);
  background: var(--gg-color-warm-paper);
  transition: transform var(--gg-transition-hover);
}
.gg-site-header.gg-header-hidden { transform: translateY(-100%); }
.gg-site-header-inner { display: flex; align-items: center; justify-content: space-between; max-width: 960px; margin: 0 auto; }
.gg-site-header-logo img { display: block; height: 50px; width: auto; }
.gg-site-header-nav { display: flex; gap: 24px; align-items: center; }
.gg-site-header-nav > a,
.gg-site-header-item > a { color: var(--gg-color-dark-brown); text-decoration: none; font-family: var(--gg-font-data); font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; transition: color 0.2s; }
.gg-site-header-nav > a:hover,
.gg-site-header-item > a:hover { color: var(--gg-color-gold); }
.gg-site-header-nav > a[aria-current="page"],
.gg-site-header-item > a[aria-current="page"] { color: var(--gg-color-gold); }

/* Dropdown container — desktop */
.gg-site-header-item { position: relative; }
.gg-site-header-dropdown { display: none; position: absolute; top: 100%; left: 0; min-width: 200px; padding: 8px 0; background: var(--gg-color-warm-paper); border: 2px solid var(--gg-color-dark-brown); z-index: 1000; }
.gg-site-header-item:hover .gg-site-header-dropdown,
.gg-site-header-item:focus-within .gg-site-header-dropdown { display: block; }
.gg-site-header-dropdown a { display: block; padding: 8px 16px; font-family: var(--gg-font-data); font-size: 11px; font-weight: 400; letter-spacing: 1px; color: var(--gg-color-dark-brown); text-decoration: none; transition: color 0.2s; }
.gg-site-header-dropdown a:hover { color: var(--gg-color-gold); }

/* Hamburger — hidden on desktop */
.gg-hamburger { display: none; background: none; border: none; cursor: pointer; padding: 8px; width: 48px; height: 48px; flex-direction: column; justify-content: center; align-items: center; gap: 5px; }
.gg-hamburger-bar { display: block; width: 24px; height: 2px; background: var(--gg-color-dark-brown); transition: transform var(--gg-transition-hover); }
.gg-hamburger.is-open .gg-hamburger-bar:nth-child(1) { transform: translateY(7px) rotate(45deg); }
.gg-hamburger.is-open .gg-hamburger-bar:nth-child(2) { opacity: 0; }
.gg-hamburger.is-open .gg-hamburger-bar:nth-child(3) { transform: translateY(-7px) rotate(-45deg); }

/* Mobile nav drawer — hidden by default */
.gg-mobile-nav {
  display: none; flex-direction: column;
  padding: 0 24px 16px;
  border-top: 1px solid var(--gg-color-tan);
  background: var(--gg-color-warm-paper);
}
.gg-mobile-nav.is-open { display: flex; }
.gg-mobile-nav-group { border-bottom: 1px solid var(--gg-color-tan); }
.gg-mobile-nav-toggle {
  display: flex; align-items: center; justify-content: space-between;
  width: 100%; padding: 14px 0;
  background: none; border: none; cursor: pointer;
  font-family: var(--gg-font-data); font-size: 12px; font-weight: 700;
  letter-spacing: 2px; text-transform: uppercase;
  color: var(--gg-color-dark-brown);
}
.gg-mobile-nav-toggle::after {
  content: '+'; font-size: 18px; font-weight: 400; color: var(--gg-color-secondary-brown);
  transition: transform 0.2s;
}
.gg-mobile-nav-toggle[aria-expanded="true"]::after { content: '\\2212'; }
.gg-mobile-nav-sub {
  display: none; flex-direction: column;
  padding: 0 0 12px 16px;
}
.gg-mobile-nav-sub.is-open { display: flex; }
.gg-mobile-nav-sub a {
  padding: 10px 0;
  font-family: var(--gg-font-data); font-size: 12px; font-weight: 400;
  letter-spacing: 1px; color: var(--gg-color-dark-brown);
  text-decoration: none; transition: color 0.2s;
}
.gg-mobile-nav-sub a:hover { color: var(--gg-color-gold); }
.gg-mobile-nav-link {
  padding: 14px 0;
  font-family: var(--gg-font-data); font-size: 12px; font-weight: 700;
  letter-spacing: 2px; text-transform: uppercase;
  color: var(--gg-color-dark-brown); text-decoration: none;
  transition: color 0.2s;
}
.gg-mobile-nav-link:hover { color: var(--gg-color-gold); }

/* ── Mobile breakpoint ─────────────────────────────────── */
@media (max-width: 768px) {
  .gg-site-header { padding: 12px 16px; }
  .gg-site-header-logo img { height: 40px; }
  .gg-site-header-nav { display: none !important; }
  .gg-hamburger { display: flex; }
  .gg-mobile-nav { padding: 0 16px 12px; }
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
"""
