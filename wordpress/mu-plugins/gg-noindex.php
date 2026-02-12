<?php
/**
 * Plugin Name: Gravel God Noindex
 * Description: Add noindex to junk pages that waste Google crawl budget.
 * Version: 1.0
 *
 * Deployed via: python3 scripts/push_wordpress.py --sync-noindex
 * Targets: date archives, pagination, categories, WooCommerce, LearnDash, feeds
 *
 * Google merges multiple robots meta tags using the most restrictive directive,
 * so this coexists safely with AIOSEO's existing robots meta tag.
 */

function gg_noindex_junk_pages() {
    $dominated = false;

    // WordPress template conditionals
    if (is_date()) $dominated = true;
    if (is_paged()) $dominated = true;
    if (is_category()) $dominated = true;
    if (is_feed()) $dominated = true;
    if (is_search()) $dominated = true;

    // WooCommerce pages (check function exists for non-WC installs)
    if (function_exists('is_cart') && is_cart()) $dominated = true;
    if (function_exists('is_account_page') && is_account_page()) $dominated = true;

    // URL-pattern matching for WooCommerce, LearnDash, xAPI, dashboard
    $uri = $_SERVER['REQUEST_URI'] ?? '';
    $noindex_patterns = [
        '/cart',
        '/my-account',
        '/lesson',
        '/courses/',
        '/gb_xapi_content/',
        '/dashboard',
        'wc-ajax=',
    ];
    foreach ($noindex_patterns as $pattern) {
        if (strpos($uri, $pattern) !== false) {
            $dominated = true;
            break;
        }
    }

    if ($dominated) {
        echo '<meta name="robots" content="noindex, follow" />' . "\n";
    }
}
add_action('wp_head', 'gg_noindex_junk_pages', 1);
