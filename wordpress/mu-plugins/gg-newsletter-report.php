<?php
/** Plugin Name: Gravel God Newsletter Report
 * Private aggregate report and allowlisted welcome links. No subscriber email is rendered.
 */
if (!defined('ABSPATH')) { exit; }

function gg_newsletter_service($path, $body = null) {
    $secret = get_option('gg_newsletter_ingest_secret', '');
    if (!$secret) { return new WP_Error('not_configured', 'Newsletter reporting is not configured.'); }
    $args = array('timeout' => 8, 'headers' => array('Authorization' => 'Bearer ' . $secret));
    if ($body !== null) {
        $args['method'] = 'POST';
        $args['headers']['Content-Type'] = 'application/json';
        $args['body'] = wp_json_encode($body);
    }
    $response = wp_remote_request('https://newsletter-attribution.gravelgodcoaching.workers.dev' . $path, $args);
    if (is_wp_error($response)) { return $response; }
    if (wp_remote_retrieve_response_code($response) !== 200) {
        return new WP_Error('service_unavailable', 'Newsletter reporting is temporarily unavailable.');
    }
    $data = json_decode(wp_remote_retrieve_body($response), true);
    return is_array($data) ? $data : new WP_Error('invalid_report', 'Newsletter report could not be read.');
}

function gg_newsletter_essays() {
    return array(
        'sweet-spot' => 'https://gravelgodcycling.substack.com/p/sweet-spot-isnt-that-sweet',
        'unbound' => 'https://gravelgodcycling.substack.com/p/unbound-two-huni-mean-five-point',
        'kids' => 'https://gravelgodcycling.substack.com/p/i-lied-having-kids-makes-you-slow',
    );
}

function gg_newsletter_test_token_valid($token) {
    $parts = explode('.', $token, 2);
    if (count($parts) !== 2 || !ctype_digit($parts[0])) { return false; }
    $expires = (int) $parts[0];
    $secret = get_option('gg_newsletter_ingest_secret', '');
    return $secret && $expires >= time() && $expires <= time() + HOUR_IN_SECONDS
        && hash_equals(hash_hmac('sha256', 'newsletter-test:' . $parts[0], $secret), $parts[1]);
}

add_action('template_redirect', function () {
    // A short-lived signed marker excludes the owned end-to-end test browser.
    // It grants no account access and changes no reader's subscription.
    if (isset($_GET['gg_newsletter_test'])) {
        $token = sanitize_text_field(wp_unslash($_GET['gg_newsletter_test']));
        nocache_headers();
        header('Referrer-Policy: no-referrer');
        if (!gg_newsletter_test_token_valid($token)) { status_header(403); exit; }
        setcookie('gg_newsletter_test', $token, array('expires' => (int) explode('.', $token)[0], 'path' => '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Lax'));
        wp_safe_redirect(home_url('/articles/')); exit;
    }
    if (!isset($_GET['gg_welcome'])) { return; }
    $essay = sanitize_key(wp_unslash($_GET['gg_welcome']));
    $essays = gg_newsletter_essays();
    if (!isset($essays[$essay])) { status_header(404); exit; }
    nocache_headers();
    header('X-Robots-Tag: noindex, nofollow');
    header('Referrer-Policy: no-referrer');
    $method = isset($_SERVER['REQUEST_METHOD']) ? $_SERVER['REQUEST_METHOD'] : '';
    if ($method === 'GET') {
        $consent = isset($_COOKIE['gg_consent']) && $_COOKIE['gg_consent'] === 'accepted';
        $visitor = $consent && isset($_COOKIE['gg_welcome_reader']) ? sanitize_text_field(wp_unslash($_COOKIE['gg_welcome_reader'])) : '';
        if ($consent && !preg_match('/^[a-f0-9-]{36}$/i', $visitor)) {
            $visitor = wp_generate_uuid4();
            setcookie('gg_welcome_reader', $visitor, array('expires' => time() + 90 * DAY_IN_SECONDS, 'path' => '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Lax'));
        }
        // Test clicks in the coach's authenticated browser stay out of normal results.
        $result = gg_newsletter_service('/click', array(
            'essay' => $essay,
            'visitor' => $visitor,
            'user_agent' => substr(isset($_SERVER['HTTP_USER_AGENT']) ? $_SERVER['HTTP_USER_AGENT'] : '', 0, 1000),
            'purpose' => substr((isset($_SERVER['HTTP_PURPOSE']) ? $_SERVER['HTTP_PURPOSE'] : '') . ' ' . (isset($_SERVER['HTTP_SEC_PURPOSE']) ? $_SERVER['HTTP_SEC_PURPOSE'] : ''), 0, 100),
            'is_test' => current_user_can('manage_options') || (isset($_COOKIE['gg_newsletter_test']) && gg_newsletter_test_token_valid(wp_unslash($_COOKIE['gg_newsletter_test']))),
        ));
        if (is_wp_error($result)) { error_log('Gravel God newsletter click recording failed'); }
    }
    // The reading destination must work even if reporting is unavailable.
    wp_redirect($essays[$essay], 302, 'Gravel God Newsletter');
    exit;
}, 1);

add_action('admin_menu', function () {
    add_management_page('Newsletter report', 'Newsletter report', 'manage_options', 'gg-newsletter-report', 'gg_newsletter_report_page');
});

function gg_newsletter_report_page() {
    if (!current_user_can('manage_options')) { wp_die('Not authorized.'); }
    nocache_headers();
    $days = isset($_GET['days']) ? absint($_GET['days']) : 30;
    if (!in_array($days, array(30, 90, 365), true)) { $days = 30; }
    $tests = isset($_GET['tests']) && $_GET['tests'] === '1';
    $data = gg_newsletter_service('/report?days=' . $days . ($tests ? '&tests=1' : ''));
    echo '<div class="wrap"><h1>Newsletter report</h1>';
    echo '<form method="get"><input type="hidden" name="page" value="gg-newsletter-report"><label for="gg-newsletter-days">Period </label><select id="gg-newsletter-days" name="days">';
    foreach (array(30, 90, 365) as $period) {
        echo '<option value="' . esc_attr($period) . '"' . selected($days, $period, false) . '>Last ' . esc_html($period) . ' days</option>';
    }
    echo '</select> <label><input type="checkbox" name="tests" value="1"' . checked($tests, true, false) . '> Include test activity</label> ';
    submit_button('Update', 'secondary', '', false);
    echo '</form>';
    if (is_wp_error($data)) {
        echo '<div class="notice notice-error"><p>' . esc_html($data->get_error_message()) . '</p></div></div>'; return;
    }
    if ($tests) { echo '<div class="notice notice-warning"><p>Test activity is included in this view.</p></div>'; }
    $sync = !empty($data['last_sync']) ? gmdate('M j, Y H:i', $data['last_sync']) . ' UTC' : 'Not yet synced';
    echo '<p>Last confirmation sync: <strong>' . esc_html($sync) . '</strong></p>';
    if (empty($data['last_sync']) || time() - $data['last_sync'] > 30 * MINUTE_IN_SECONDS) {
        echo '<div class="notice notice-warning"><p>Confirmation sync is stale. Subscriber counts may be incomplete.</p></div>';
    }
    if (!empty($data['sync_rejected'])) {
        echo '<div class="notice notice-error"><p>A subscriber notification could not be verified. Confirmation counts may be incomplete.</p></div>';
    }
    echo '<h2>' . esc_html($data['confirmed']) . ' confirmed subscribers in this period</h2>';
    echo '<p>' . esc_html($data['unattributed']) . ' have no verified website article attribution. Pending attempts and Subscribe clicks are not counted.</p>';
    echo '<p>' . esc_html(isset($data['starting_export_in_period']) ? $data['starting_export_in_period'] : 0) . ' existing subscriber records in this period came from the starting export. They are separate from new verified confirmations.</p>';
    echo '<h2>Website articles → confirmed subscribers</h2><table class="widefat striped"><thead><tr><th>Article</th><th>Confirmed subscribers</th></tr></thead><tbody>';
    foreach ($data['articles'] as $article) {
        echo '<tr><td><a href="' . esc_url('https://gravelgodcycling.com' . $article['article']) . '">' . esc_html($article['article']) . '</a></td><td>' . esc_html($article['confirmed']) . '</td></tr>';
    }
    if (!$data['articles']) { echo '<tr><td colspan="2">No confirmed article-attributed subscribers in this period.</td></tr>'; }
    echo '</tbody></table><h2>Welcome essays</h2><table class="widefat striped"><thead><tr><th>Essay</th><th>Clicks</th><th>Distinct browsers with consent</th></tr></thead><tbody>';
    foreach ($data['essays'] as $essay) {
        echo '<tr><td><a href="' . esc_url($essay['url']) . '">' . esc_html($essay['title']) . '</a></td><td>' . esc_html($essay['clicks']) . '</td><td>' . esc_html($essay['readers']) . '</td></tr>';
    }
    echo '</tbody></table><p>' . esc_html($data['click_definition']) . '</p>';
    echo '<h2>Goals</h2><p><strong>$3,000/month</strong> sustained for three months; track fees, refunds and delivery hours separately. <strong>100 new confirmed subscribers/month</strong> is the initial audience target. Revenue attribution is not measured by this report.</p>';
    echo '<p>' . esc_html($data['historical_website_unattributed']) . ' subscribers in the starting export had gravelgodcycling.com as their source. Historical article attribution cannot be reconstructed from that export.</p></div>';
}
