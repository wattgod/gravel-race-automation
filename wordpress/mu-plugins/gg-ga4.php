<?php
/**
 * Gravel God — GA4 Analytics
 *
 * Lightweight replacement for MonsterInsights Pro + 5 addons.
 * Injects the GA4 gtag.js snippet into wp_head on all front-end pages.
 *
 * Deployed via SCP to wp-content/mu-plugins/gg-ga4.php
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

add_action( 'wp_head', 'gg_ga4_tracking', 1 );

function gg_ga4_tracking() {
    if ( is_admin() ) {
        return;
    }
    // Skip tracking for logged-in admins/editors to keep analytics clean
    if ( current_user_can( 'edit_posts' ) ) {
        return;
    }
    $id = 'G-EJJZ9T6M52';
    echo '<!-- Gravel God GA4 -->' . "\n";
    echo '<script async src="https://www.googletagmanager.com/gtag/js?id=' . esc_attr( $id ) . '"></script>' . "\n";
    echo '<script>' . "\n";
    echo 'window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}' . "\n";
    echo 'gtag("js",new Date());gtag("config","' . esc_js( $id ) . '");' . "\n";
    echo '</script>' . "\n";
}
