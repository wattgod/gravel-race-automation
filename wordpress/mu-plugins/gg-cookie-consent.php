<?php
/**
 * Plugin Name: Gravel God Cookie Consent
 * Description: Lightweight cookie consent banner with Google Consent Mode v2.
 * Version: 1.1
 *
 * Deployed via: python3 scripts/push_wordpress.py --sync-consent
 *
 * Injects a consent banner + Consent Mode defaults before GA4 fires.
 * When user accepts, updates consent and stores preference in gg_consent cookie.
 * Banner does not appear if consent was previously given.
 *
 * Works alongside gg-ga4.php — GA4 fires on every page but with consent mode
 * controlling what data is actually collected. No script blocking needed.
 *
 * IMPORTANT: Hex values must match tokens.css (source of truth).
 * Mu-plugins can't use var() tokens — hardcode hex with !important.
 * Parity with cookie_consent.py enforced by test_cookie_consent_mu_plugin.py.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

/**
 * Set Google Consent Mode defaults BEFORE gtag loads.
 * Must fire at priority 0 (before gg_ga4_tracking at priority 1).
 */
add_action( 'wp_head', 'gg_consent_mode_defaults', 0 );

function gg_consent_mode_defaults() {
    if ( is_admin() ) return;
    if ( current_user_can( 'edit_posts' ) ) return;
    ?>
<script>
window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}
gtag('consent','default',{
  'analytics_storage': /(^|; )gg_consent=accepted/.test(document.cookie) ? 'granted' : 'denied',
  'ad_storage': 'denied',
  'ad_user_data': 'denied',
  'ad_personalization': 'denied',
  'wait_for_update': 500
});
</script>
    <?php
}

/**
 * Inject the cookie consent banner in the footer.
 */
add_action( 'wp_footer', 'gg_cookie_consent_banner', 99 );

function gg_cookie_consent_banner() {
    if ( is_admin() ) return;
    if ( current_user_can( 'edit_posts' ) ) return;
    ?>
<style>
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
</script>
    <?php
}
