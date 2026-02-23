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
    if (is_tag()) $dominated = true;
    if (is_feed()) $dominated = true;
    if (is_search()) $dominated = true;

    // WooCommerce pages (check function exists for non-WC installs)
    if (function_exists('is_cart') && is_cart()) $dominated = true;
    if (function_exists('is_account_page') && is_account_page()) $dominated = true;

    // URL-pattern matching for WooCommerce, LearnDash, xAPI, dashboard, junk pages
    $uri = $_SERVER['REQUEST_URI'] ?? '';
    $noindex_patterns = [
        '/cart',
        '/my-account',
        '/lesson',
        '/courses/',
        '/gb_xapi_content/',
        '/dashboard',
        '/student-registration',
        '/instructor-registration',
        '/questionnaire',
        '/coaching/apply',
        'wc-ajax=',
    ];

    // Noindex search page with query params (e.g. ?region=Midwest) to avoid
    // duplicate content — the canonical /gravel-races/ is the only one to index
    if (strpos($uri, '/gravel-races/') !== false && !empty($_SERVER['QUERY_STRING'])) {
        $dominated = true;
    }

    // Noindex blog preview pages (/blog/{slug}/) — thin content that duplicates
    // race profiles. Keep /blog/ index page indexed.
    if (preg_match('#^/blog/[a-z0-9-]+/?$#', $uri)) {
        $dominated = true;
    }
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

/**
 * Inject JSON-LD schema on /gravel-races/ page.
 * BreadcrumbList + CollectionPage for rich snippets in Google SERPs.
 */
function gg_search_page_schema() {
    $uri = $_SERVER['REQUEST_URI'] ?? '';
    if (strpos($uri, '/gravel-races') === false) return;

    $breadcrumb = [
        '@context' => 'https://schema.org',
        '@type' => 'BreadcrumbList',
        'itemListElement' => [
            ['@type' => 'ListItem', 'position' => 1, 'name' => 'Home', 'item' => 'https://gravelgodcycling.com/'],
            ['@type' => 'ListItem', 'position' => 2, 'name' => 'Gravel Races', 'item' => 'https://gravelgodcycling.com/gravel-races/'],
        ],
    ];

    $collection = [
        '@context' => 'https://schema.org',
        '@type' => 'CollectionPage',
        'name' => 'Find Your Gravel Race',
        'description' => 'Search and filter 328 gravel races worldwide by tier, distance, region, terrain, and date. Find your next gravel adventure with the Gravel God race database.',
        'url' => 'https://gravelgodcycling.com/gravel-races/',
        'numberOfItems' => 328,
        'publisher' => [
            '@type' => 'Organization',
            'name' => 'Gravel God',
            'url' => 'https://gravelgodcycling.com/',
        ],
    ];

    echo '<script type="application/ld+json">' . json_encode($breadcrumb, JSON_UNESCAPED_SLASHES) . '</script>' . "\n";
    echo '<script type="application/ld+json">' . json_encode($collection, JSON_UNESCAPED_SLASHES) . '</script>' . "\n";
}
add_action('wp_head', 'gg_search_page_schema', 5);
