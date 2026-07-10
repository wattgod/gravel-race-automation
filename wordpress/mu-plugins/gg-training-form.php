<?php
/**
 * Gravel God — Training Plan Questionnaire JS
 *
 * Loads training-plans-form.js on the questionnaire page (/questionnaire/).
 * This script handles form validation, GA4 tracking (tp_form_start,
 * tp_form_submit, begin_checkout), and Stripe Checkout redirect via
 * the Railway API.
 *
 * Without this mu-plugin, the "Submit & Pay" button does nothing —
 * discovered during Sprint Ralph Wiggum CTA audit (Mar 2026).
 *
 * Why a mu-plugin instead of wp_enqueue_script in the theme?
 * SiteGround Optimizer strips/combines scripts unpredictably.
 * Mu-plugins load before themes and can't be deactivated via admin UI,
 * making them the most reliable way to guarantee script loading.
 *
 * Deployed via SCP to wp-content/mu-plugins/gg-training-form.php
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

add_action( 'wp_enqueue_scripts', 'gg_enqueue_training_form_js' );

function gg_enqueue_training_form_js() {
    // Only load on the questionnaire page (page ID 5017)
    if ( ! is_page( 5017 ) ) {
        return;
    }

    // wp_enqueue_script is required instead of raw echo because
    // SiteGround Speed Optimizer strips anonymous <script> tags
    // from wp_footer output. Enqueued scripts are respected and
    // combined into the optimizer's bundled JS file.
    wp_enqueue_script(
        'gg-training-form',
        content_url( 'uploads/training-plans-form.js' ),
        array(),
        null,
        true
    );
}
