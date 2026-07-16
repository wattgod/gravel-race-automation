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

# 2026 brand mark — inline (never 404s, recolors via currentColor). Source:
# gravel-god-brand/logo/gg-logo-2026.svg
GG_LOGO_SVG = '<svg class="gg-logo-mark" role="img" aria-label="Gravel God" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1888 2240"> <g transform="translate(0, 2240) scale(0.1, -0.1)"> <path d="M4200 20330 c-96 -32 -587 -194 -1090 -360 -503 -166 -934 -308 -956 -316 l-42 -15 2 -1104 c1 -1099 1 -1105 21 -1105 11 0 36 5 55 10 19 6 454 116 965 245 512 128 984 248 1050 265 66 17 137 36 158 41 l37 10 0 1194 c0 950 -3 1195 -12 1194 -7 0 -92 -27 -188 -59z M13981 19201 c-1 -744 1 -1191 7 -1195 6 -3 115 -33 243 -65 129 -33 342 -87 474 -121 132 -34 310 -79 395 -100 165 -40 731 -184 993 -252 86 -22 161 -38 165 -34 7 7 16 2206 9 2206 -2 0 -178 59 -393 131 -603 203 -1866 619 -1879 619 -9 0 -13 -270 -14 -1189z M8420 20214 c-343 -32 -558 -51 -825 -74 -126 -11 -236 -23 -242 -25 -10 -3 -13 -110 -13 -489 0 -538 7 -487 -65 -500 -54 -9 -833 -156 -1105 -207 -292 -56 -860 -159 -872 -159 -5 0 -8 -556 -8 -1235 l0 -1235 23 5 c12 2 92 18 177 34 455 87 558 107 815 157 154 31 447 89 651 130 204 41 374 74 377 74 4 0 7 -303 7 -674 l0 -673 -52 -11 c-29 -6 -141 -29 -248 -51 -107 -22 -260 -54 -340 -72 -80 -17 -273 -57 -430 -89 -157 -32 -350 -73 -430 -90 -80 -17 -287 -60 -460 -95 -323 -66 -737 -151 -870 -179 -41 -9 -83 -16 -92 -16 -17 0 -18 54 -18 994 l0 993 -62 -17 c-35 -10 -115 -34 -178 -53 -63 -20 -223 -67 -355 -106 -132 -38 -278 -80 -325 -94 -47 -14 -125 -36 -175 -50 -49 -14 -187 -54 -305 -90 -118 -35 -287 -85 -375 -110 -88 -25 -232 -67 -320 -93 -88 -25 -169 -49 -179 -52 -19 -5 -19 -29 -13 -1091 4 -597 7 -1087 7 -1088 0 -7 105 -2 268 12 97 8 317 26 487 40 171 13 340 27 378 31 l67 6 0 -621 0 -620 -37 -10 c-21 -6 -69 -17 -108 -25 -79 -17 -187 -40 -390 -85 -77 -17 -239 -51 -360 -76 -286 -59 -305 -64 -306 -84 0 -17 0 -125 1 -1431 l0 -786 510 4 510 4 0 -691 0 -691 -510 0 -510 0 0 -1095 0 -1094 43 -11 c23 -6 148 -42 277 -80 129 -38 314 -91 410 -119 274 -78 451 -130 461 -136 5 -4 9 -257 9 -626 l0 -619 -27 0 c-16 1 -116 11 -223 24 -662 79 -940 109 -947 102 -4 -4 -7 -501 -5 -1104 l3 -1097 97 -32 c157 -51 459 -146 727 -228 260 -80 454 -141 785 -245 603 -190 612 -193 621 -179 5 8 9 18 9 22 0 8 67 524 75 582 3 17 16 118 30 225 14 107 32 245 40 305 8 61 24 182 35 270 11 88 30 223 40 300 11 77 33 246 50 375 17 129 36 274 43 322 6 51 16 88 22 88 6 0 202 -38 436 -85 233 -47 591 -119 794 -160 204 -41 603 -122 888 -179 285 -57 520 -106 523 -108 5 -5 6 -1309 1 -1314 -2 -2 -120 17 -263 42 -142 24 -378 65 -524 90 -146 25 -373 66 -505 90 -270 51 -698 125 -701 121 -8 -7 -14 -536 -16 -1421 l-3 -1010 110 -18 c155 -25 1222 -209 1575 -271 l295 -52 260 1 c143 0 457 1 698 2 l437 2 0 5086 0 5086 -92 -6 c-96 -7 -836 -33 -1698 -61 -272 -9 -580 -19 -685 -23 l-190 -7 -2 -807 -1 -808 654 -2 654 -3 0 -1129 c0 -621 -1 -1130 -2 -1132 -2 -1 -55 9 -118 22 -316 68 -401 86 -595 128 -115 25 -286 61 -380 81 -93 19 -188 40 -210 45 -57 13 -350 78 -480 105 -60 13 -180 39 -265 59 -85 19 -250 53 -366 77 -117 23 -217 45 -223 48 -8 5 -11 696 -11 2521 0 1382 2 2515 5 2518 2 3 165 38 362 78 468 96 1566 323 1903 394 336 71 374 78 380 75 3 -2 5 -161 5 -354 l0 -351 678 0 677 0 0 4030 c0 3832 -1 4030 -17 4029 -10 -1 -128 -12 -263 -25z M9680 10389 l0 -9849 643 -1 c353 -1 669 -1 702 0 33 1 233 31 445 67 363 62 863 146 1367 232 l223 37 -6 1210 c-4 666 -9 1213 -13 1216 -3 4 -181 -24 -396 -62 -214 -38 -482 -85 -595 -104 -253 -44 -545 -96 -794 -141 -104 -19 -197 -34 -207 -34 -16 0 -17 41 -19 660 -1 532 2 661 12 664 7 2 135 27 283 56 301 58 1346 266 1959 390 219 45 402 77 407 73 4 -4 15 -73 24 -153 9 -80 18 -152 20 -160 2 -8 20 -136 40 -285 19 -148 44 -337 55 -420 11 -82 38 -287 60 -455 21 -168 59 -455 84 -639 26 -183 46 -338 46 -345 1 -36 16 -35 165 10 83 25 229 70 325 99 96 29 225 69 285 88 61 20 322 101 580 181 259 79 513 159 565 177 52 17 145 46 205 64 l110 32 5 1090 c3 599 3 1098 2 1108 -5 22 48 26 -647 -54 -397 -46 -547 -62 -550 -59 -8 8 -6 1231 2 1238 4 5 40 17 78 28 90 26 753 218 952 276 84 24 156 46 160 49 4 3 7 496 5 1096 l-2 1091 -475 0 -475 0 0 615 0 615 -22 4 c-13 3 -72 7 -133 10 -299 15 -1583 92 -2488 150 -104 6 -190 9 -193 7 -2 -2 -4 -310 -4 -683 l0 -678 33 0 c17 0 154 -4 302 -10 149 -5 347 -12 440 -15 94 -3 233 -8 310 -11 l140 -6 1 -779 c1 -704 -1 -779 -15 -784 -9 -2 -65 -14 -126 -26 -60 -11 -220 -45 -355 -76 -135 -30 -308 -68 -385 -84 -77 -16 -169 -36 -205 -44 -90 -21 -118 -27 -335 -74 -104 -22 -287 -61 -405 -86 -655 -140 -778 -167 -807 -172 l-33 -6 0 3083 0 3082 38 -7 c20 -3 143 -29 272 -56 287 -61 690 -145 1200 -249 212 -43 466 -97 565 -119 99 -22 263 -56 365 -77 102 -20 195 -40 208 -45 l22 -9 0 -421 c-1 -232 3 -425 7 -429 4 -4 49 -13 98 -20 50 -6 207 -30 350 -51 143 -22 397 -60 565 -84 168 -25 312 -46 320 -48 13 -2 15 152 12 1346 l-3 1347 23 0 c13 0 210 -16 438 -35 540 -46 738 -60 744 -54 3 3 6 495 7 1094 l1 1088 -119 34 c-65 19 -154 45 -198 57 -175 49 -545 158 -630 186 -49 16 -171 52 -270 80 -336 96 -460 132 -695 202 -129 39 -255 76 -280 83 -25 6 -55 15 -67 19 l-23 7 0 -995 0 -996 -21 0 c-11 0 -55 9 -97 19 -43 11 -102 24 -132 30 -30 6 -188 38 -350 71 -162 33 -371 76 -465 95 -93 18 -235 48 -315 65 -80 17 -219 46 -310 65 -91 19 -185 39 -210 44 -90 20 -764 158 -997 204 l-53 10 0 675 0 675 48 -6 c27 -3 100 -17 163 -31 63 -14 245 -50 404 -81 160 -31 389 -76 510 -100 121 -24 328 -65 460 -90 132 -26 276 -55 320 -65 44 -10 97 -21 118 -24 l37 -7 -2 1233 -3 1233 -200 37 c-110 20 -339 64 -510 97 -170 33 -384 74 -475 91 -91 17 -223 42 -295 55 -468 88 -560 105 -568 105 -4 0 -7 219 -6 486 0 267 -1 487 -3 489 -2 2 -109 13 -238 24 -129 11 -408 36 -620 55 -212 20 -409 37 -437 40 l-53 5 0 -9850z"/> </g> </svg>'


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
    <a href="{SITE_BASE_URL}/" class="gg-site-header-logo" aria-label="Gravel God home">
      {GG_LOGO_SVG}
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
          <a href="{SITE_BASE_URL}/course/">Courses</a>
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
        <a href="{SITE_BASE_URL}/course/">Courses</a>
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
.gg-site-header-logo { display: block; }
.gg-site-header-logo .gg-logo-mark { display: block; height: 46px; width: auto; fill: currentColor; color: var(--gg-color-dark-brown); }
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
  .gg-site-header-logo .gg-logo-mark { height: 38px; }
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
