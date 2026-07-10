<?php
/**
 * Gravel God — Shared Header with Hamburger Nav for WordPress Pages
 *
 * Injects sticky header with hamburger mobile nav, dropdown desktop nav,
 * and auto-hide on scroll. Matches shared_header.py output exactly.
 *
 * Targets: all WP-managed pages (coaching, about, training plans, consulting, etc.)
 * Skips: admin, front page (has its own generated header)
 *
 * Strategy:
 *   1. wp_head: output CSS to hide Astra's header and style our header + hamburger
 *   2. wp_body_open: inject our header HTML right after <body>
 *   3. wp_footer: inject JS for hamburger toggle, sticky auto-hide, accessibility
 *
 * Deployed via SCP to wp-content/mu-plugins/gg-header.php
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

add_action( 'wp_head', 'gg_shared_header_css', 5 );
add_action( 'wp_head', 'gg_rss_feed_link', 6 );
add_action( 'wp_body_open', 'gg_shared_header_html', 1 );
add_action( 'wp_footer', 'gg_shared_header_js', 99 );
add_filter( 'body_class', 'gg_add_neo_brutalist_class' );

/**
 * Add RSS feed discovery link to <head> on all pages.
 */
function gg_rss_feed_link() {
    echo '<link rel="alternate" type="application/rss+xml" title="Gravel God Race Database" href="https://gravelgodcycling.com/feed/races.xml">' . "\n";
}

/**
 * Add gg-neo-brutalist-page class to body so existing Code Snippet overrides
 * (which use body:not(.gg-neo-brutalist-page)) don't apply teal link colors.
 */
function gg_add_neo_brutalist_class( $classes ) {
    if ( ! is_admin() && ! is_front_page() ) {
        $classes[] = 'gg-neo-brutalist-page';
    }
    return $classes;
}

/**
 * Check if current page should get our custom header.
 */
function gg_should_inject_header() {
    if ( is_admin() ) {
        return false;
    }
    if ( is_front_page() ) {
        return false;
    }
    return true;
}

function gg_shared_header_css() {
    if ( ! gg_should_inject_header() ) {
        return;
    }
    ?>
<style id="gg-shared-header-css">
/* Hide Astra theme header — our header replaces it */
.ast-above-header-wrap,
.ast-main-header-wrap,
.ast-below-header-wrap,
#ast-desktop-header,
#masthead,
.site-header,
header.site-header,
.ast-mobile-header-wrap { display: none !important; }

@import url('https://fonts.googleapis.com/css2?family=Sometype+Mono:wght@400;700&family=Source+Serif+4:wght@400;700&display=swap');

/* ── Sticky Header ── */
.gg-site-header { position: sticky !important; top: 0 !important; z-index: 900 !important; padding: 16px 24px !important; border-bottom: 2px solid #9a7e0a !important; background: #f5efe6 !important; transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important; }
.gg-site-header.gg-header-hidden { transform: translateY(-100%) !important; }
.gg-site-header-inner { display: flex !important; align-items: center !important; justify-content: space-between !important; max-width: 960px !important; margin: 0 auto !important; }
.gg-site-header-logo img { display: block !important; height: 50px !important; width: auto !important; }

/* ── Desktop Nav ── */
.gg-site-header-nav { display: flex !important; gap: 24px !important; align-items: center !important; }
.gg-site-header-nav > a,
.gg-site-header-nav > a:link,
.gg-site-header-nav > a:visited,
.gg-site-header-item > a,
.gg-site-header-item > a:link,
.gg-site-header-item > a:visited { color: #3a2e25 !important; text-decoration: none !important; font-family: 'Sometype Mono', monospace !important; font-size: 11px !important; font-weight: 700 !important; letter-spacing: 2px !important; text-transform: uppercase !important; transition: color 0.2s !important; }
.gg-site-header-nav > a:hover,
.gg-site-header-item > a:hover { color: #9a7e0a !important; }
.gg-site-header-nav > a[aria-current="page"],
.gg-site-header-item > a[aria-current="page"] { color: #9a7e0a !important; }
.gg-site-header-item { position: relative !important; }
.gg-site-header-dropdown { display: none; position: absolute !important; top: 100% !important; left: 0 !important; min-width: 200px !important; padding: 8px 0 !important; background: #f5efe6 !important; border: 2px solid #3a2e25 !important; z-index: 1000 !important; }
.gg-site-header-item:hover .gg-site-header-dropdown,
.gg-site-header-item:focus-within .gg-site-header-dropdown { display: block !important; }
.gg-site-header-dropdown a,
.gg-site-header-dropdown a:link,
.gg-site-header-dropdown a:visited { display: block !important; padding: 8px 16px !important; font-family: 'Sometype Mono', monospace !important; font-size: 11px !important; font-weight: 400 !important; letter-spacing: 1px !important; color: #3a2e25 !important; text-decoration: none !important; transition: color 0.2s !important; }
.gg-site-header-dropdown a:hover { color: #9a7e0a !important; }

/* ── Hamburger (hidden on desktop) ── */
.gg-hamburger { display: none !important; background: none !important; border: none !important; cursor: pointer !important; padding: 8px !important; width: 48px !important; height: 48px !important; flex-direction: column !important; justify-content: center !important; align-items: center !important; gap: 5px !important; }
.gg-hamburger-bar { display: block !important; width: 24px !important; height: 2px !important; background: #3a2e25 !important; transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important; }
.gg-hamburger.is-open .gg-hamburger-bar:nth-child(1) { transform: translateY(7px) rotate(45deg) !important; }
.gg-hamburger.is-open .gg-hamburger-bar:nth-child(2) { opacity: 0 !important; }
.gg-hamburger.is-open .gg-hamburger-bar:nth-child(3) { transform: translateY(-7px) rotate(-45deg) !important; }

/* ── Mobile Nav Drawer ── */
.gg-mobile-nav { display: none !important; flex-direction: column !important; padding: 0 24px 16px !important; border-top: 1px solid #d4c5b9 !important; background: #f5efe6 !important; }
.gg-mobile-nav.is-open { display: flex !important; }
.gg-mobile-nav-group { border-bottom: 1px solid #d4c5b9 !important; }
.gg-mobile-nav-toggle { display: flex !important; align-items: center !important; justify-content: space-between !important; width: 100% !important; padding: 14px 0 !important; background: none !important; border: none !important; cursor: pointer !important; font-family: 'Sometype Mono', monospace !important; font-size: 12px !important; font-weight: 700 !important; letter-spacing: 2px !important; text-transform: uppercase !important; color: #3a2e25 !important; }
.gg-mobile-nav-toggle::after { content: '+' !important; font-size: 18px !important; font-weight: 400 !important; color: #7d695d !important; transition: transform 0.2s !important; }
.gg-mobile-nav-toggle[aria-expanded="true"]::after { content: '\2212' !important; }
.gg-mobile-nav-sub { display: none !important; flex-direction: column !important; padding: 0 0 12px 16px !important; }
.gg-mobile-nav-sub.is-open { display: flex !important; }
.gg-mobile-nav-sub a,
.gg-mobile-nav-sub a:link,
.gg-mobile-nav-sub a:visited { padding: 10px 0 !important; font-family: 'Sometype Mono', monospace !important; font-size: 12px !important; font-weight: 400 !important; letter-spacing: 1px !important; color: #3a2e25 !important; text-decoration: none !important; transition: color 0.2s !important; }
.gg-mobile-nav-sub a:hover { color: #9a7e0a !important; }
.gg-mobile-nav-link,
.gg-mobile-nav-link:link,
.gg-mobile-nav-link:visited { padding: 14px 0 !important; font-family: 'Sometype Mono', monospace !important; font-size: 12px !important; font-weight: 700 !important; letter-spacing: 2px !important; text-transform: uppercase !important; color: #3a2e25 !important; text-decoration: none !important; display: block !important; }
.gg-mobile-nav-link:hover { color: #9a7e0a !important; }

/* ── Training Plans page fix: entrance animation doesn't fire in WP ── */
.tp-hero h1,
.tp-hero-sub,
.tp-hero-cta,
.tp-hero-bar { opacity: 1 !important; transform: none !important; }

/* ── Mobile breakpoint ── */
@media (max-width: 768px) {
  .gg-site-header { padding: 12px 16px !important; }
  .gg-site-header-logo img { height: 40px !important; }
  .gg-site-header-nav { display: none !important; }
  .gg-hamburger { display: flex !important; }
  .gg-mobile-nav { padding: 0 16px 12px !important; }
}
</style>
    <?php
}

function gg_shared_header_html() {
    if ( ! gg_should_inject_header() ) {
        return;
    }

    $uri = $_SERVER['REQUEST_URI'] ?? '';
    $active = '';
    if ( strpos( $uri, '/gravel-races' ) !== false || strpos( $uri, '/race/' ) !== false ) {
        $active = 'races';
    } elseif ( strpos( $uri, '/products/' ) !== false ) {
        $active = 'products';
    } elseif ( strpos( $uri, '/coaching' ) !== false || strpos( $uri, '/consulting' ) !== false ) {
        $active = 'services';
    } elseif ( strpos( $uri, '/articles' ) !== false || strpos( $uri, '/blog' ) !== false || strpos( $uri, '/insights' ) !== false ) {
        $active = 'articles';
    } elseif ( strpos( $uri, '/about' ) !== false ) {
        $active = 'about';
    }

    $base = 'https://gravelgodcycling.com';
    $substack = 'https://gravelgodcycling.substack.com';

    $aria = function( $key ) use ( $active ) {
        return $active === $key ? ' aria-current="page"' : '';
    };
    ?>
<header class="gg-site-header" id="gg-site-header">
  <div class="gg-site-header-inner">
    <a href="<?php echo $base; ?>/" class="gg-site-header-logo">
      <img src="<?php echo $base; ?>/wp-content/uploads/2021/09/cropped-Gravel-God-logo.png" alt="Gravel God" width="50" height="50">
    </a>
    <nav class="gg-site-header-nav" id="gg-nav-desktop">
      <div class="gg-site-header-item">
        <a href="<?php echo $base; ?>/gravel-races/"<?php echo $aria('races'); ?>>RACES</a>
        <div class="gg-site-header-dropdown">
          <a href="<?php echo $base; ?>/gravel-races/">All Gravel Races</a>
          <a href="<?php echo $base; ?>/race/methodology/">How We Rate</a>
        </div>
      </div>
      <div class="gg-site-header-item">
        <a href="<?php echo $base; ?>/products/training-plans/"<?php echo $aria('products'); ?>>PRODUCTS</a>
        <div class="gg-site-header-dropdown">
          <a href="<?php echo $base; ?>/products/training-plans/">Custom Training Plans</a>
          <a href="<?php echo $base; ?>/course/">Courses</a>
          <a href="<?php echo $base; ?>/guide/">Gravel Handbook</a>
        </div>
      </div>
      <div class="gg-site-header-item">
        <a href="<?php echo $base; ?>/coaching/"<?php echo $aria('services'); ?>>SERVICES</a>
        <div class="gg-site-header-dropdown">
          <a href="<?php echo $base; ?>/coaching/">Coaching</a>
          <a href="<?php echo $base; ?>/consulting/">Consulting</a>
        </div>
      </div>
      <div class="gg-site-header-item">
        <a href="<?php echo $base; ?>/articles/"<?php echo $aria('articles'); ?>>ARTICLES</a>
        <div class="gg-site-header-dropdown">
          <a href="<?php echo $substack; ?>" target="_blank" rel="noopener">Slow Mid 38s</a>
          <a href="<?php echo $base; ?>/articles/">Hot Takes</a>
          <a href="<?php echo $base; ?>/insights/">The State of Gravel</a>
          <a href="<?php echo $base; ?>/fueling-methodology/">White Papers</a>
        </div>
      </div>
      <a href="<?php echo $base; ?>/about/"<?php echo $aria('about'); ?>>ABOUT</a>
    </nav>
    <button class="gg-hamburger" id="gg-hamburger" aria-label="Open menu" aria-expanded="false" aria-controls="gg-mobile-nav">
      <span class="gg-hamburger-bar"></span>
      <span class="gg-hamburger-bar"></span>
      <span class="gg-hamburger-bar"></span>
    </button>
  </div>
  <nav class="gg-mobile-nav" id="gg-mobile-nav" aria-label="Mobile navigation">
    <div class="gg-mobile-nav-group">
      <button class="gg-mobile-nav-toggle" aria-expanded="false">RACES</button>
      <div class="gg-mobile-nav-sub">
        <a href="<?php echo $base; ?>/gravel-races/">All Gravel Races</a>
        <a href="<?php echo $base; ?>/race/methodology/">How We Rate</a>
      </div>
    </div>
    <div class="gg-mobile-nav-group">
      <button class="gg-mobile-nav-toggle" aria-expanded="false">PRODUCTS</button>
      <div class="gg-mobile-nav-sub">
        <a href="<?php echo $base; ?>/products/training-plans/">Custom Training Plans</a>
        <a href="<?php echo $base; ?>/course/">Courses</a>
        <a href="<?php echo $base; ?>/guide/">Gravel Handbook</a>
      </div>
    </div>
    <div class="gg-mobile-nav-group">
      <button class="gg-mobile-nav-toggle" aria-expanded="false">SERVICES</button>
      <div class="gg-mobile-nav-sub">
        <a href="<?php echo $base; ?>/coaching/">Coaching</a>
        <a href="<?php echo $base; ?>/consulting/">Consulting</a>
      </div>
    </div>
    <div class="gg-mobile-nav-group">
      <button class="gg-mobile-nav-toggle" aria-expanded="false">ARTICLES</button>
      <div class="gg-mobile-nav-sub">
        <a href="<?php echo $substack; ?>" target="_blank" rel="noopener">Slow Mid 38s</a>
        <a href="<?php echo $base; ?>/articles/">Hot Takes</a>
        <a href="<?php echo $base; ?>/insights/">The State of Gravel</a>
        <a href="<?php echo $base; ?>/fueling-methodology/">White Papers</a>
      </div>
    </div>
    <a href="<?php echo $base; ?>/about/" class="gg-mobile-nav-link">ABOUT</a>
  </nav>
</header>
    <?php
}

function gg_shared_header_js() {
    if ( ! gg_should_inject_header() ) {
        return;
    }
    ?>
<script id="gg-shared-header-js">
// ── Hamburger mobile menu ───────────────────────────────
(function() {
  var hamburger = document.getElementById('gg-hamburger');
  var mobileNav = document.getElementById('gg-mobile-nav');
  if (!hamburger || !mobileNav) return;
  var navIsOpen = false;

  function closeNav() {
    navIsOpen = false;
    hamburger.classList.remove('is-open');
    hamburger.setAttribute('aria-expanded', 'false');
    hamburger.setAttribute('aria-label', 'Open menu');
    mobileNav.classList.remove('is-open');
    document.body.style.overflow = '';
    hamburger.focus();
  }

  function openNav() {
    navIsOpen = true;
    hamburger.classList.add('is-open');
    hamburger.setAttribute('aria-expanded', 'true');
    hamburger.setAttribute('aria-label', 'Close menu');
    mobileNav.classList.add('is-open');
    document.body.style.overflow = 'hidden';
    var first = mobileNav.querySelector('button, a');
    if (first) first.focus();
  }

  hamburger.addEventListener('click', function() {
    navIsOpen ? closeNav() : openNav();
  });

  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && navIsOpen) { closeNav(); }
  });

  mobileNav.addEventListener('keydown', function(e) {
    if (e.key !== 'Tab' || !navIsOpen) return;
    var focusable = mobileNav.querySelectorAll('a, button');
    if (!focusable.length) return;
    var first = focusable[0];
    var last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault(); last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault(); hamburger.focus();
    }
  });

  mobileNav.querySelectorAll('.gg-mobile-nav-toggle').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var sub = btn.nextElementSibling;
      var expanded = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', !expanded);
      sub.classList.toggle('is-open', !expanded);
    });
  });

  mobileNav.querySelectorAll('a').forEach(function(link) {
    link.addEventListener('click', closeNav);
  });

  window._ggNavIsOpen = function() { return navIsOpen; };
})();

// ── Sticky header — auto-hide on scroll-down, reveal on scroll-up ──
(function() {
  var header = document.getElementById('gg-site-header');
  if (!header) return;
  var lastScrollY = 0;
  var ticking = false;

  function updateHeaderHeight() {
    var h = header.offsetHeight;
    document.documentElement.style.setProperty('--gg-header-height', h + 'px');
  }
  updateHeaderHeight();
  window.addEventListener('resize', updateHeaderHeight);

  function onScroll() {
    var currentY = window.scrollY;
    var headerHeight = header.offsetHeight;
    var navOpen = typeof window._ggNavIsOpen === 'function' && window._ggNavIsOpen();
    if (!navOpen && currentY > headerHeight && currentY > lastScrollY) {
      header.classList.add('gg-header-hidden');
    } else {
      header.classList.remove('gg-header-hidden');
    }
    lastScrollY = currentY;
    ticking = false;
  }

  window.addEventListener('scroll', function() {
    if (!ticking) {
      requestAnimationFrame(onScroll);
      ticking = true;
    }
  }, { passive: true });
})();
</script>
    <?php
}
