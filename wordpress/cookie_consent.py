"""Shared cookie consent banner for all generated pages.

Provides get_consent_banner_html() for a lightweight, brand-consistent
consent banner with Google Consent Mode v2 integration.

Used by all generators that include GA4 tracking (~24 generators).

The banner:
- Shows only if no gg_consent cookie exists
- Accept → sets gg_consent=accepted, updates consent mode to 'granted'
- Decline → sets gg_consent=declined, updates consent mode to 'denied'
- Links to /cookies/ for full cookie policy

Hex values MUST match tokens.css (source of truth):
  --gg-color-primary-brown: #59473c
  --gg-color-secondary-brown: #8c7568
  --gg-color-tan: #d4c5b9
  --gg-color-teal: #1A8A82
  --gg-color-light-teal: #4ECDC4
  --gg-color-gold: #B7950B
  --gg-color-white: #ffffff

Note: This module uses hardcoded hex because the banner renders inline
before tokens.css loads. The mu-plugin (gg-cookie-consent.php) also
hardcodes hex because mu-plugins have no access to :root tokens.
Parity between Python and PHP is enforced by test_cookie_consent_mu_plugin.py.
"""
from __future__ import annotations


def get_consent_banner_html() -> str:
    """Return the cookie consent banner HTML + inline CSS + JS.

    Place this right before </body> on every page.
    """
    return '''<style>
.gg-consent-banner{position:fixed;bottom:0;left:0;right:0;z-index:9999;background:#59473c;border-top:3px solid #B7950B;padding:16px 24px;display:none;align-items:center;justify-content:center;gap:16px;flex-wrap:wrap;font-family:'Sometype Mono',monospace}
.gg-consent-banner.gg-consent-show{display:flex}
.gg-consent-text{color:#d4c5b9;font-size:13px;line-height:1.5;max-width:640px}
.gg-consent-text a{color:#4ECDC4;text-decoration:none}
.gg-consent-text a:hover{color:#ffffff}
.gg-consent-btn{padding:8px 20px;font-family:'Sometype Mono',monospace;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;cursor:pointer;border:2px solid;transition:background-color .3s,color .3s,border-color .3s}
.gg-consent-btn:focus-visible{outline:2px solid #4ECDC4;outline-offset:2px}
.gg-consent-accept{background:#1A8A82;color:#ffffff;border-color:#1A8A82}
.gg-consent-accept:hover{background:#59473c;border-color:#1A8A82;color:#1A8A82}
.gg-consent-decline{background:transparent;color:#d4c5b9;border-color:#8c7568}
.gg-consent-decline:hover{border-color:#d4c5b9;color:#ffffff}
@media(max-width:600px){.gg-consent-banner{flex-direction:column;text-align:center;padding:12px 16px}.gg-consent-text{font-size:12px}}
@media(prefers-reduced-motion:reduce){.gg-consent-btn{transition:none}}
</style>
<div class="gg-consent-banner" id="gg-consent-banner" role="dialog" aria-label="Cookie consent" aria-describedby="gg-consent-desc">
  <p class="gg-consent-text" id="gg-consent-desc">We use cookies for analytics to improve this site. No ads, no tracking across sites. <a href="/cookies/">Learn more</a>.</p>
  <button class="gg-consent-btn gg-consent-accept" id="gg-consent-accept">Accept</button>
  <button class="gg-consent-btn gg-consent-decline" id="gg-consent-decline">Decline</button>
</div>
<script>
(function(){
  var b=document.getElementById('gg-consent-banner');
  if(!b)return;
  if(/(^|; )gg_consent=/.test(document.cookie))return;
  b.classList.add('gg-consent-show');
  document.getElementById('gg-consent-accept').addEventListener('click',function(){
    document.cookie='gg_consent=accepted;path=/;max-age=31536000;SameSite=Lax;Secure';
    if(typeof gtag==='function'){gtag('consent','update',{'analytics_storage':'granted'})}
    b.classList.remove('gg-consent-show');
  });
  document.getElementById('gg-consent-decline').addEventListener('click',function(){
    document.cookie='gg_consent=declined;path=/;max-age=31536000;SameSite=Lax;Secure';
    if(typeof gtag==='function'){gtag('consent','update',{'analytics_storage':'denied'})}
    b.classList.remove('gg-consent-show');
  });
})();
</script>'''
