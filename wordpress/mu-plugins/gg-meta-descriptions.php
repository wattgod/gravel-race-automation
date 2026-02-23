<?php
/**
 * Plugin Name: Gravel God Meta Descriptions
 * Description: Inject meta descriptions via AIOSEO filter hooks from a JSON data file.
 * Version: 1.0
 *
 * Deployed via: python3 scripts/push_wordpress.py --sync-meta-descriptions
 *
 * Reads wp-content/uploads/gg-meta-descriptions.json and hooks into AIOSEO's
 * aioseo_title, aioseo_description, and aioseo_og_description filters to
 * override titles and descriptions for WordPress-managed pages and posts.
 *
 * Fully reversible: delete this file to revert to AIOSEO defaults.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

/**
 * Load and cache meta description data from JSON file.
 * Returns array indexed by wp_id, or empty array on failure.
 */
function gg_meta_get_data() {
    static $data = null;
    if ( $data !== null ) {
        return $data;
    }

    $json_path = WP_CONTENT_DIR . '/uploads/gg-meta-descriptions.json';
    if ( ! file_exists( $json_path ) ) {
        $data = array();
        return $data;
    }

    $raw = file_get_contents( $json_path );
    $parsed = json_decode( $raw, true );
    if ( ! $parsed || ! isset( $parsed['entries'] ) ) {
        $data = array();
        return $data;
    }

    // Index by wp_id for O(1) lookup
    $data = array();
    foreach ( $parsed['entries'] as $entry ) {
        if ( isset( $entry['wp_id'] ) ) {
            $data[ $entry['wp_id'] ] = $entry;
        }
    }
    return $data;
}

/**
 * Get the current post ID reliably.
 * Uses get_queried_object_id() (works outside the loop) with get_the_ID() fallback.
 * Returns 0 if no valid post ID can be determined.
 */
function gg_meta_get_post_id() {
    // Only override on singular posts/pages — never on archives, search, 404, feeds.
    // On archive pages, get_the_ID() can return the first loop post ID, which would
    // incorrectly replace the archive description with a single post's description.
    if ( ! is_singular() ) {
        return 0;
    }

    $post_id = get_queried_object_id();
    if ( ! $post_id ) {
        $post_id = get_the_ID();
    }
    return (int) $post_id;
}

/**
 * Override AIOSEO meta description for posts/pages in our data file.
 */
function gg_meta_filter_description( $description ) {
    $post_id = gg_meta_get_post_id();
    if ( ! $post_id ) {
        return $description;
    }

    $data = gg_meta_get_data();
    if ( isset( $data[ $post_id ] ) && ! empty( $data[ $post_id ]['description'] ) ) {
        return $data[ $post_id ]['description'];
    }
    return $description;
}

/**
 * Override AIOSEO Open Graph description.
 */
function gg_meta_filter_og_description( $description ) {
    $post_id = gg_meta_get_post_id();
    if ( ! $post_id ) {
        return $description;
    }

    $data = gg_meta_get_data();
    if ( isset( $data[ $post_id ] ) ) {
        // Use og_description if set, otherwise fall back to description
        $og = ! empty( $data[ $post_id ]['og_description'] )
            ? $data[ $post_id ]['og_description']
            : ( ! empty( $data[ $post_id ]['description'] ) ? $data[ $post_id ]['description'] : '' );
        if ( $og ) {
            return $og;
        }
    }
    return $description;
}

/**
 * Override AIOSEO page title.
 */
function gg_meta_filter_title( $title ) {
    $post_id = gg_meta_get_post_id();
    if ( ! $post_id ) {
        return $title;
    }

    $data = gg_meta_get_data();
    if ( isset( $data[ $post_id ] ) && ! empty( $data[ $post_id ]['title'] ) ) {
        return $data[ $post_id ]['title'];
    }
    return $title;
}

add_filter( 'aioseo_title', 'gg_meta_filter_title', 10 );
add_filter( 'aioseo_description', 'gg_meta_filter_description', 10 );
add_filter( 'aioseo_og_description', 'gg_meta_filter_og_description', 10 );
