"""Canonical conversion tracking shared by generated editorial pages."""


def get_plan_intent_tracking_script() -> str:
    """Track only genuine plan-intent links with the canonical GA4 event."""
    return r'''<script>
(function () {
  var selector = [
    'a[href*="/questionnaire"]',
    'a[href*="/prep-kit/"]',
    'a[href^="https://buy.stripe.com/"]',
    'a[data-cta][href*="/coaching"]',
    'a[data-cta][href*="/training-plans"]'
  ].join(',');
  document.querySelectorAll(selector).forEach(function (link) {
    link.addEventListener('click', function () {
      if (typeof gtag !== 'function') return;
      gtag('event', 'cta_click', {
        source: 'editorial',
        cta_name: link.getAttribute('data-cta') || 'plan_intent',
        cta_href: link.getAttribute('href') || '',
        page_path: window.location.pathname
      });
    });
  });
}());
</script>'''
