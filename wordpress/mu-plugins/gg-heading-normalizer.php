<?php
/**
 * Plugin Name: Gravel God Heading Normalizer
 * Description: Guarantee one meaningful H1 on WordPress-managed public pages.
 * Version: 1.0.0
 *
 * Deployed via: python3 scripts/push_wordpress.py --sync-headings
 *
 * Legacy Elementor templates contain three recurring defects:
 *   - no H1 at all;
 *   - a literal [POST_TITLE] or empty first H1;
 *   - footer and section headings incorrectly marked up as additional H1s.
 *
 * This plugin corrects the final server-rendered HTML. Static race and guide
 * pages bypass WordPress and remain the responsibility of their generators.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

/**
 * Normalize a complete HTML response to one meaningful H1.
 */
function gg_h1_normalize_markup( $html, $title ) {
    if ( ! is_string( $html ) || $html === '' ) {
        return $html;
    }

    $title = trim( wp_strip_all_tags( (string) $title ) );
    if ( $title === '' ) {
        return $html;
    }

    $h1_pattern = '~<h1\b([^>]*)>(.*?)</h1\s*>~is';
    $h1_count = preg_match_all( $h1_pattern, $html );

    if ( $h1_count > 0 ) {
        $seen = 0;
        return preg_replace_callback(
            $h1_pattern,
            function ( $match ) use ( &$seen, $title ) {
                $seen++;
                $heading_text = trim(
                    wp_strip_all_tags(
                        html_entity_decode( $match[2], ENT_QUOTES | ENT_HTML5, 'UTF-8' )
                    )
                );

                if ( $seen === 1 ) {
                    if ( $heading_text === '' || preg_match( '/^\[POST_TITLE\]$/i', $heading_text ) ) {
                        return '<h1' . $match[1] . '>' . esc_html( $title ) . '</h1>';
                    }
                    return $match[0];
                }

                return '<h2' . $match[1] . '>' . $match[2] . '</h2>';
            },
            $html
        );
    }

    $heading = '<div class="gg-auto-title-wrap"><h1 class="gg-auto-title">'
        . esc_html( $title )
        . '</h1></div>';
    $inserted = 0;

    // Elementor header/footer templates have no <main>. Insert immediately
    // before their page root so the title appears after site navigation.
    $html = preg_replace(
        '~(?=<div\b[^>]*\bdata-elementor-type=(["\'])wp-page\1[^>]*>)~i',
        $heading,
        $html,
        1,
        $inserted
    );
    if ( $inserted ) {
        return $html;
    }

    // Astra's default template provides a main landmark.
    $html = preg_replace( '~(<main\b[^>]*>)~i', '$1' . $heading, $html, 1, $inserted );
    if ( $inserted ) {
        return $html;
    }

    // Defensive fallback for an unusual singular template.
    return preg_replace( '~(<body\b[^>]*>)~i', '$1' . $heading, $html, 1 );
}

/**
 * Resolve the queried title only after WordPress has built the response.
 */
function gg_h1_normalize_response( $html ) {
    $post_id = get_queried_object_id();
    return gg_h1_normalize_markup( $html, get_the_title( $post_id ) );
}

/**
 * Buffer singular public responses so Elementor and theme markup can be fixed
 * after every component has rendered, while bots still receive corrected HTML.
 */
function gg_h1_begin_response_buffer() {
    if ( is_admin() || ! is_singular() || is_feed() || wp_doing_ajax() ) {
        return;
    }
    ob_start( 'gg_h1_normalize_response' );
}
add_action( 'template_redirect', 'gg_h1_begin_response_buffer', 0 );

/**
 * Styling for titles injected into pages whose legacy template omitted one.
 */
function gg_h1_normalizer_styles() {
    if ( ! is_singular() ) {
        return;
    }
    echo '<style id="gg-heading-normalizer-css">'
        . '.gg-auto-title-wrap{max-width:1100px;margin:0 auto;padding:32px 24px 16px}'
        . '.gg-auto-title{margin:0;color:#3a2e25;font-family:"Source Serif 4",Georgia,serif;'
        . 'font-size:clamp(32px,5vw,64px);font-weight:700;line-height:1.05;letter-spacing:-.025em}'
        . '@media(max-width:600px){.gg-auto-title-wrap{padding:24px 20px 12px}}'
        . '</style>' . "\n";
}
add_action( 'wp_head', 'gg_h1_normalizer_styles', 20 );
