"""Shared site header used by all generated pages.

Provides get_site_header_html() and get_site_header_css() for a consistent
5-item dropdown nav across homepage, race profiles, coaching, about, prep kits,
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
