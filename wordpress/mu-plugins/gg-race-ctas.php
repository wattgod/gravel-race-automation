<?php
/**
 * Gravel God — Race Page CTAs on Blog Posts
 *
 * Appends race profile + prep kit CTAs to blog posts that reference
 * specific races in our database.
 *
 * Strategy:
 *   1. the_content filter appends CTA — works for Elementor wp-post pages
 *      (those with _wp_page_template = elementor_header_footer)
 *   2. wp_footer outputs CTA as raw HTML for posts rendered by the
 *      Elementor Theme Builder single-post template (ID 4524), where
 *      the_content modifications are discarded. Detected by
 *      _wp_page_template = 'default'.
 *
 * Deployed via SCP to wp-content/mu-plugins/gg-race-ctas.php
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

add_filter( 'the_content', 'gg_append_race_cta_filter', 99 );
add_action( 'wp_footer', 'gg_race_cta_footer_fallback', 99 );

function gg_append_race_cta_filter( $content ) {
    if ( ! is_singular( 'post' ) ) {
        return $content;
    }
    $cta = gg_build_race_cta();
    if ( $cta ) {
        $content .= $cta;
    }
    return $content;
}

function gg_race_cta_footer_fallback() {
    if ( ! is_singular( 'post' ) ) {
        return;
    }
    // Posts with elementor_header_footer template render their own Elementor
    // content — the_content filter works for these. Posts with 'default' template
    // use the Elementor Theme Builder single-post template (ID 4524), which
    // discards the_content modifications. Those need this wp_footer fallback.
    $post_id = get_the_ID();
    $tpl = get_post_meta( $post_id, '_wp_page_template', true );
    if ( $tpl === 'elementor_header_footer' ) {
        return; // the_content filter handles these posts
    }
    $cta = gg_build_race_cta();
    if ( ! $cta ) {
        return;
    }
    echo '<div id="gg-footer-cta-fallback" style="max-width:800px;margin:0 auto;padding:0 20px 40px;">'
        . $cta
        . '</div>';
}


function gg_build_race_cta() {
    $post_id = get_the_ID();

    $race_map = array(
        3203 => 'unbound-200',
        3749 => 'unbound-200',
        3433 => 'unbound-200',
        1964 => 'unbound-200',
        1923 => 'bwr-california',
        3483 => 'ned-gravel',
        2324 => 'steamboat-gravel',
        3520 => 'steamboat-gravel',
        3796 => 'big-horn-gravel',
        2065 => 'gunni-grinder',
        2790 => 'iron-horse-bicycle-classic',
        2209 => 'red-granite-grinder',
        2844 => 'red-granite-grinder',
        3537 => 'red-granite-grinder',
    );

    $names = array(
        'unbound-200'               => 'Unbound 200',
        'bwr-california'            => 'Belgian Waffle Ride',
        'ned-gravel'                => 'Ned Gravel',
        'steamboat-gravel'          => 'SBT GRVL',
        'big-horn-gravel'           => 'Big Horn Gravel',
        'gunni-grinder'             => 'Gunni Grinder',
        'iron-horse-bicycle-classic' => 'Iron Horse Bicycle Classic',
        'red-granite-grinder'       => 'Red Granite Grinder',
    );

    if ( isset( $race_map[ $post_id ] ) ) {
        $slug = $race_map[ $post_id ];
        $name = isset( $names[ $slug ] ) ? $names[ $slug ] : ucwords( str_replace( '-', ' ', $slug ) );
        $race_url = "https://gravelgodcycling.com/race/{$slug}/";
        $kit_url  = "https://gravelgodcycling.com/race/{$slug}/prep-kit/";
        return gg_race_cta_html( $name, $race_url, $kit_url );
    }

    if ( $post_id === 2014 ) {
        return gg_hydration_cta_html();
    }

    return null;
}

function gg_race_cta_html( $name, $race_url, $kit_url ) {
    return '<div data-gg-race-cta="1" style="background:#f5efe6;border:3px solid #59473c;padding:24px 28px;margin:40px 0 0;font-family:\'Source Serif 4\',Georgia,serif;">'
        . '<h3 style="margin:0 0 12px;color:#59473c;font-size:1.3em;">Racing ' . esc_html( $name ) . '?</h3>'
        . '<p style="margin:0 0 16px;color:#59473c;line-height:1.6;">We rated and analyzed 328 gravel races across 14 dimensions. See how ' . esc_html( $name ) . ' stacks up &mdash; plus grab a free race-day prep kit with pacing, fueling, and equipment checklists.</p>'
        . '<p style="margin:0;">'
        . '<a href="' . esc_url( $race_url ) . '" style="color:#178079;font-weight:700;text-decoration:underline;margin-right:20px;">' . esc_html( $name ) . ' Race Profile &rarr;</a>'
        . '<a href="' . esc_url( $kit_url ) . '" style="color:#9a7e0a;font-weight:700;text-decoration:underline;">Free Race Prep Kit &rarr;</a>'
        . '</p></div>';
}

function gg_hydration_cta_html() {
    return '<div data-gg-race-cta="1" style="background:#f5efe6;border:3px solid #59473c;padding:24px 28px;margin:40px 0 0;font-family:\'Source Serif 4\',Georgia,serif;">'
        . '<h3 style="margin:0 0 12px;color:#59473c;font-size:1.3em;">Race-Specific Hydration Plans</h3>'
        . '<p style="margin:0 0 16px;color:#59473c;line-height:1.6;">Our prep kits include personalized hydration and sodium calculators tailored to each race&#039;s climate, distance, and elevation. Get hour-by-hour fueling plans for 328 gravel races.</p>'
        . '<p style="margin:0;">'
        . '<a href="https://gravelgodcycling.com/gravel-races/" style="color:#178079;font-weight:700;text-decoration:underline;margin-right:20px;">Browse All 328 Races &rarr;</a>'
        . '<a href="https://gravelgodcycling.com/race/unbound-200/prep-kit/" style="color:#9a7e0a;font-weight:700;text-decoration:underline;">Example: Unbound 200 Prep Kit &rarr;</a>'
        . '</p></div>';
}
