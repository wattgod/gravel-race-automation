<?php
/**
 * Gravel God — A/B Testing Bootstrap
 *
 * Injects the A/B test inline bootstrap (returning visitor anti-flicker)
 * and deferred gg-ab-tests.js loader into wp_head on all front-end pages.
 * Priority 2 (after GA4 at priority 1) so gtag() is available.
 *
 * PARITY NOTE: The inline bootstrap JS below MUST match the output of
 * get_ab_bootstrap_js() in wordpress/brand_tokens.py. Tests enforce this.
 *
 * Deployed via SCP to wp-content/mu-plugins/gg-ab.php
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

add_action( 'wp_head', 'gg_ab_bootstrap', 2 );

function gg_ab_bootstrap() {
    if ( is_admin() ) {
        return;
    }
    if ( current_user_can( 'edit_posts' ) ) {
        return;
    }
    // Bootstrap JS — must match brand_tokens.py get_ab_bootstrap_js()
    echo '<!-- Gravel God A/B Tests -->' . "\n";
    echo '<script>' . "\n";
    echo '(function(){var s=localStorage.getItem("gg_ab_assign");if(!s)return;try{var a=JSON.parse(s);var c=localStorage.getItem("gg_ab_cache");if(!c)return;var cache=JSON.parse(c);for(var eid in a){if(!cache[eid])continue;var el=document.querySelector(cache[eid].sel);if(el)el.textContent=cache[eid].txt;}}catch(e){}})();' . "\n";
    echo '</script>' . "\n";
    // JS filename — mu-plugin uses unhashed path; SiteGround cache purge handles freshness.
    // Static pages use content-hashed filename via get_ab_js_filename().
    echo '<script defer src="/ab/gg-ab-tests.js"></script>' . "\n";
}
