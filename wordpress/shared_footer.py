"""Shared mega-footer used by all generated pages.

Provides get_mega_footer_html() and get_mega_footer_css() for a consistent
6-column footer across homepage, race profiles, coaching, about, prep kits,
series hubs, and coaching apply pages.
"""
from __future__ import annotations

from datetime import date

SITE_BASE_URL = "https://gravelgodcycling.com"
SUBSTACK_URL = "https://gravelgodcycling.substack.com"
CURRENT_YEAR = date.today().year


def get_mega_footer_html() -> str:
    """Return the shared mega-footer HTML block."""
    return f'''<footer class="gg-mega-footer">
  <div class="gg-mega-footer-grid">
    <div class="gg-mega-footer-col gg-mega-footer-brand">
      <h3 class="gg-mega-footer-brand-title">GRAVEL GOD CYCLING</h3>
      <p class="gg-mega-footer-brand-tagline">Practical coaching and training for people with real lives who still want to go fast.</p>
    </div>
    <div class="gg-mega-footer-col">
      <h4 class="gg-mega-footer-heading">RACES</h4>
      <nav class="gg-mega-footer-links">
        <a href="{SITE_BASE_URL}/gravel-races/">All Gravel Races</a>
        <a href="{SITE_BASE_URL}/race/methodology/">How We Rate</a>
      </nav>
    </div>
    <div class="gg-mega-footer-col">
      <h4 class="gg-mega-footer-heading">PRODUCTS</h4>
      <nav class="gg-mega-footer-links">
        <a href="{SITE_BASE_URL}/products/training-plans/">Custom Training Plans</a>
        <a href="{SITE_BASE_URL}/guide/">Gravel Handbook</a>
      </nav>
    </div>
    <div class="gg-mega-footer-col">
      <h4 class="gg-mega-footer-heading">SERVICES</h4>
      <nav class="gg-mega-footer-links">
        <a href="{SITE_BASE_URL}/coaching/">Coaching</a>
        <a href="{SITE_BASE_URL}/consulting/">Consulting</a>
      </nav>
    </div>
    <div class="gg-mega-footer-col">
      <h4 class="gg-mega-footer-heading">ARTICLES</h4>
      <nav class="gg-mega-footer-links">
        <a href="{SUBSTACK_URL}" target="_blank" rel="noopener">Slow Mid 38s</a>
        <a href="{SITE_BASE_URL}/articles/">Hot Takes</a>
      </nav>
    </div>
    <div class="gg-mega-footer-col gg-mega-footer-newsletter">
      <h4 class="gg-mega-footer-heading">NEWSLETTER</h4>
      <p class="gg-mega-footer-newsletter-desc">Essays on training, meaning, and not majoring in the minors.</p>
      <a href="{SUBSTACK_URL}" class="gg-mega-footer-subscribe" target="_blank" rel="noopener" data-ga="subscribe_click" data-ga-label="mega_footer">SUBSCRIBE</a>
    </div>
  </div>
  <div class="gg-mega-footer-legal">
    <span>&copy; {CURRENT_YEAR} Gravel God Cycling. All rights reserved.</span>
    <nav class="gg-mega-footer-legal-links">
      <a href="{SITE_BASE_URL}/privacy/">Privacy</a>
      <a href="{SITE_BASE_URL}/terms/">Terms</a>
      <a href="{SITE_BASE_URL}/cookies/">Cookies</a>
    </nav>
  </div>
  <div class="gg-mega-footer-disclaimer">
    <p>This content is produced independently by Gravel God and is not affiliated with, endorsed by, or officially connected to any race organizer, event, or governing body mentioned on this page. All ratings, opinions, and assessments represent the editorial views of Gravel God based on publicly available information and community research. Race details are subject to change &mdash; always verify with official race sources.</p>
  </div>
</footer>'''


def get_mega_footer_css() -> str:
    """Return the mega-footer CSS using var(--gg-*) design tokens."""
    return """
/* ── Mega Footer ───────────────────────────────────────── */
.gg-mega-footer { background: var(--gg-color-dark-brown); border-top: var(--gg-border-gold); margin-top: var(--gg-spacing-xl); }
.gg-mega-footer-grid { display: grid; grid-template-columns: 1.5fr 1fr 1fr 1fr 1fr 1fr; gap: var(--gg-spacing-lg); padding: var(--gg-spacing-2xl) var(--gg-spacing-xl); max-width: 960px; margin: 0 auto; }
.gg-mega-footer-brand-title { font-family: var(--gg-font-data); font-size: var(--gg-font-size-sm); font-weight: var(--gg-font-weight-bold); letter-spacing: var(--gg-letter-spacing-ultra-wide); color: var(--gg-color-white); margin: 0 0 var(--gg-spacing-sm) 0; }
.gg-mega-footer-brand-tagline { font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-xs); line-height: var(--gg-line-height-prose); color: var(--gg-color-tan); margin: 0; }
.gg-mega-footer-heading { font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); font-weight: var(--gg-font-weight-bold); letter-spacing: var(--gg-letter-spacing-ultra-wide); text-transform: uppercase; color: var(--gg-color-gold); margin: 0 0 var(--gg-spacing-md) 0; }
.gg-mega-footer-links { display: flex; flex-direction: column; gap: var(--gg-spacing-xs); }
.gg-mega-footer-links a { color: var(--gg-color-tan); font-family: var(--gg-font-data); font-size: 12px; text-decoration: none; transition: color var(--gg-transition-hover); }
.gg-mega-footer-links a:hover { color: var(--gg-color-white); }
.gg-mega-footer-newsletter-desc { font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-xs); color: var(--gg-color-tan); line-height: var(--gg-line-height-prose); margin: 0 0 var(--gg-spacing-md) 0; }
.gg-mega-footer-subscribe { display: inline-block; padding: var(--gg-spacing-xs) var(--gg-spacing-lg); font-family: var(--gg-font-data); font-size: 11px; font-weight: var(--gg-font-weight-bold); letter-spacing: var(--gg-letter-spacing-wider); background: var(--gg-color-teal); color: var(--gg-color-white); text-decoration: none; border: var(--gg-border-width-standard) solid var(--gg-color-teal); transition: background-color var(--gg-transition-hover), border-color var(--gg-transition-hover); }
.gg-mega-footer-subscribe:hover { background: transparent; border-color: var(--gg-color-teal); }
.gg-mega-footer-legal { padding: var(--gg-spacing-md) var(--gg-spacing-xl); border-top: 1px solid var(--gg-color-primary-brown); text-align: center; font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); color: var(--gg-color-secondary-brown); letter-spacing: var(--gg-letter-spacing-wide); max-width: 960px; margin: 0 auto; display: flex; justify-content: center; align-items: center; gap: var(--gg-spacing-md); flex-wrap: wrap; }
.gg-mega-footer-legal-links { display: flex; gap: var(--gg-spacing-md); }
.gg-mega-footer-legal-links a { color: var(--gg-color-secondary-brown); text-decoration: none; transition: color var(--gg-transition-hover); }
.gg-mega-footer-legal-links a:hover { color: var(--gg-color-tan); }
.gg-mega-footer-disclaimer { padding: var(--gg-spacing-sm) var(--gg-spacing-xl) var(--gg-spacing-lg); max-width: 960px; margin: 0 auto; }
.gg-mega-footer-disclaimer p { font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-2xs); color: var(--gg-color-secondary-brown); line-height: var(--gg-line-height-relaxed); margin: 0; text-align: center; }

/* Tablet: 3-column */
@media (max-width: 900px) {
  .gg-mega-footer-grid { grid-template-columns: 1fr 1fr 1fr; }
}

/* Mobile: 1-column */
@media (max-width: 600px) {
  .gg-mega-footer-grid { grid-template-columns: 1fr; gap: var(--gg-spacing-lg); padding: var(--gg-spacing-xl) var(--gg-spacing-md); }
  .gg-mega-footer-legal { padding: var(--gg-spacing-sm) var(--gg-spacing-md); }
  .gg-mega-footer-disclaimer { padding: var(--gg-spacing-sm) var(--gg-spacing-md) var(--gg-spacing-md); }
}
"""
