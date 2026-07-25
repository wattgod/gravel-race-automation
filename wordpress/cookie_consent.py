"""Shared geo-gated cookie consent for all generated pages.

Provides the synchronous Consent Mode head script and the lightweight,
brand-consistent footer controls used by every generated page.

Used by all generators that include GA4 tracking (33 generator call sites).

Consent behavior:
- EEA/UK/CH timezones default analytics to denied and show the banner
- Other known timezones default analytics to granted without showing it
- Missing timezone data fails closed to the stricter EEA posture
- Existing accepted/declined cookies override the geographic default
- The footer Privacy choices link opens the banner in every region
- Accept → sets gg_consent=accepted, updates consent mode to 'granted'
- Decline → sets gg_consent=declined, updates consent mode to 'denied'
- Links to /cookies/ for full cookie policy

Hex values MUST match tokens.css (source of truth):
  --gg-color-primary-brown: #59473c
  --gg-color-secondary-brown: #7d695d
  --gg-color-tan: #d4c5b9
  --gg-color-teal: #178079
  --gg-color-light-teal: #4ECDC4
  --gg-color-gold: #9a7e0a
  --gg-color-white: #ffffff

Note: This module uses hardcoded hex because the banner renders inline
before tokens.css loads. The mu-plugin (gg-cookie-consent.php) also
hardcodes hex because mu-plugins have no access to :root tokens.
Parity between Python and PHP is enforced by test_cookie_consent_mu_plugin.py.
"""
from __future__ import annotations

import json
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


# Explicit IANA timezones for the EEA member states, United Kingdom, and
# Switzerland. Cyprus has both Europe/* and Asia/* IANA identifiers. The three
# Atlantic zones are the EEA island zones called out in the consent decision.
# Do not broaden this to all Europe/*: Istanbul, Moscow, Minsk, Belgrade, Kyiv,
# and other non-EEA European zones must remain outside the opt-in geo-gate.
EEA_UK_CH_TIMEZONES = (
    "Africa/Ceuta",
    "Asia/Famagusta",
    "Asia/Nicosia",
    "Atlantic/Azores",
    "Atlantic/Canary",
    "Atlantic/Reykjavik",  # Iceland — EEA/EFTA, GDPR applies
    "Atlantic/Faroe",  # Faroe Islands — strict-side inclusion (Danish realm)
    "Atlantic/Madeira",
    "Europe/Amsterdam",
    "Europe/Athens",
    "Europe/Belfast",
    "Europe/Berlin",
    "Europe/Bratislava",
    "Europe/Brussels",
    "Europe/Bucharest",
    "Europe/Budapest",
    "Europe/Busingen",
    "Europe/Copenhagen",
    "Europe/Dublin",
    "Europe/Helsinki",
    "Europe/Lisbon",
    "Europe/Ljubljana",
    "Europe/London",
    "Europe/Luxembourg",
    "Europe/Madrid",
    "Europe/Malta",
    "Europe/Mariehamn",
    "Europe/Nicosia",
    "Europe/Oslo",
    "Europe/Paris",
    "Europe/Prague",
    "Europe/Riga",
    "Europe/Rome",
    "Europe/Sofia",
    "Europe/Stockholm",
    "Europe/Tallinn",
    "Europe/Vaduz",
    "Europe/Vienna",
    "Europe/Vilnius",
    "Europe/Warsaw",
    "Europe/Zagreb",
    "Europe/Zurich",
)


def requires_explicit_consent(timezone: str | None) -> bool:
    """Return whether ``timezone`` uses the strict opt-in consent posture.

    ``Intl.DateTimeFormat`` only returns browser-known IANA zones. A missing
    or empty result means detection failed and therefore fails closed.
    """
    if not timezone:
        return True
    try:
        ZoneInfo(timezone)
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        return True
    return timezone in EEA_UK_CH_TIMEZONES


def get_consent_head_script(ga_measurement_id: str) -> str:
    """Return the synchronous geo default and GA4 config in one script block.

    The timezone branch and Consent Mode default intentionally execute before
    ``gtag('config')`` in this exact block (repo pitfall #31). The async gtag.js
    loader is composed around this by ``brand_tokens.get_ga4_head_snippet``.
    """
    timezone_json = json.dumps(EEA_UK_CH_TIMEZONES, separators=(",", ":"))
    return (
        "<script>window.dataLayer=window.dataLayer||[];"
        "function gtag(){dataLayer.push(arguments)}"
        f"var ggConsentStrictTimezones=new Set({timezone_json});"
        "var ggConsentTimezone='';var ggConsentTimezoneKnown=false;"
        "try{ggConsentTimezone=Intl.DateTimeFormat().resolvedOptions().timeZone||'';"
        "if(ggConsentTimezone){new Intl.DateTimeFormat('en-US',"
        "{timeZone:ggConsentTimezone});ggConsentTimezoneKnown=true}}"
        "catch(ggConsentTimezoneError){}"
        "var ggConsentRequiresOptIn=!ggConsentTimezoneKnown||"
        "ggConsentStrictTimezones.has(ggConsentTimezone);"
        "window.ggConsentRequiresOptIn=ggConsentRequiresOptIn;"
        "var ggConsentAccepted=/(^|; )gg_consent=accepted/.test(document.cookie);"
        "var ggConsentDeclined=/(^|; )gg_consent=declined/.test(document.cookie);"
        "var ggConsentAnalytics=ggConsentAccepted?'granted':"
        "ggConsentDeclined?'denied':ggConsentRequiresOptIn?'denied':'granted';"
        "gtag('consent','default',{'analytics_storage':ggConsentAnalytics,"
        "'ad_storage':'denied','ad_user_data':'denied',"
        "'ad_personalization':'denied','wait_for_update':500});"
        "gtag('js',new Date());"
        f"gtag('config','{ga_measurement_id}');</script>"
    )


def get_consent_banner_html() -> str:
    """Return the footer privacy control and consent banner HTML/CSS/JS.

    Place this right before </body> on every page.
    """
    return '''<style>
.gg-privacy-choices-footer{padding:8px 16px;text-align:center;background:#59473c;font-family:'Sometype Mono',monospace}
.gg-privacy-choices{color:#d4c5b9;font-size:10px;letter-spacing:1px;text-transform:uppercase;text-decoration:underline;text-underline-offset:3px}
.gg-privacy-choices:hover{color:#ffffff}
.gg-privacy-choices:focus-visible{outline:2px solid #4ECDC4;outline-offset:2px}
.gg-consent-banner{position:fixed;bottom:0;left:0;right:0;z-index:9999;background:#59473c;border-top:3px solid #9a7e0a;padding:16px 24px;display:none;align-items:center;justify-content:center;gap:16px;flex-wrap:wrap;font-family:'Sometype Mono',monospace}
.gg-consent-banner.gg-consent-show{display:flex}
.gg-consent-text{color:#d4c5b9;font-size:13px;line-height:1.5;max-width:640px}
.gg-consent-text a{color:#4ECDC4;text-decoration:none}
.gg-consent-text a:hover{color:#ffffff}
.gg-consent-btn{padding:8px 20px;font-family:'Sometype Mono',monospace;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;cursor:pointer;border:2px solid;transition:background-color .3s,color .3s,border-color .3s}
.gg-consent-btn:focus-visible{outline:2px solid #4ECDC4;outline-offset:2px}
.gg-consent-accept{background:#178079;color:#ffffff;border-color:#178079}
.gg-consent-accept:hover{background:#59473c;border-color:#178079;color:#178079}
.gg-consent-decline{background:#7d695d;color:#ffffff;border-color:#7d695d}
.gg-consent-decline:hover{background:#59473c;border-color:#7d695d;color:#d4c5b9}
@media(max-width:600px){.gg-consent-banner{padding:10px 16px;gap:10px}.gg-consent-text{font-size:11px;text-align:center}.gg-consent-btn{padding:6px 14px;font-size:11px}}
@media(prefers-reduced-motion:reduce){.gg-consent-btn{transition:none}}
</style>
<div class="gg-privacy-choices-footer"><a class="gg-privacy-choices" id="gg-privacy-choices" href="/cookies/#privacy-choices">Privacy choices</a></div>
<div class="gg-consent-banner" id="gg-consent-banner" role="dialog" aria-label="Cookie consent" aria-describedby="gg-consent-desc">
  <p class="gg-consent-text" id="gg-consent-desc">We use cookies for analytics to improve this site. No ads, no tracking across sites. <a href="/cookies/">Learn more</a>.</p>
  <button class="gg-consent-btn gg-consent-accept" id="gg-consent-accept">Accept</button>
  <button class="gg-consent-btn gg-consent-decline" id="gg-consent-decline">Decline</button>
</div>
<script>
(function(){
  var b=document.getElementById('gg-consent-banner');
  var p=document.getElementById('gg-privacy-choices');
  if(!b)return;
  var tid;var autoPending=false;
  function cancelAutoShow(){
    if(!autoPending)return;autoPending=false;
    clearTimeout(tid);
    window.removeEventListener('scroll',showBanner);
  }
  function showBanner(){
    cancelAutoShow();
    b.classList.add('gg-consent-show');
  }
  if(p){p.addEventListener('click',function(e){e.preventDefault();showBanner()})}
  if(!/(^|; )gg_consent=/.test(document.cookie)&&window.ggConsentRequiresOptIn!==false){
    /* Delay showing: 3s timeout OR first scroll, whichever comes first */
    autoPending=true;
    window.addEventListener('scroll',showBanner,{passive:true,once:true});
    tid=setTimeout(showBanner,3000);
  }
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
