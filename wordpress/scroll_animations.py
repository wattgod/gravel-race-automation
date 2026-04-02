"""
Shared scroll-triggered animation CSS + JS for Gravel God pages.

Extracts the brand-canonical animation patterns from the design guide
into a reusable module. All animations:
  - Gated by .gg-has-js (no-JS fallback: content visible immediately)
  - Wrapped in @media (prefers-reduced-motion: no-preference)
  - Triggered by .gg-in-view via IntersectionObserver (threshold 0.2)
  - Fire once (observer.unobserve after trigger)

Usage:
    from scroll_animations import get_scroll_animation_css, get_scroll_animation_js

    css = get_scroll_animation_css(["fade-stagger"])
    js = get_scroll_animation_js()
"""

SUPPORTED_TYPES = {"fade-stagger", "bar", "progress"}

_EASING = "cubic-bezier(0.25, 0.46, 0.45, 0.94)"
_STAGGER_MS = 120  # ms between siblings for fade-stagger


def get_scroll_animation_css(types: list) -> str:
    """Return CSS for requested data-animate types.

    All rules wrapped in @media (prefers-reduced-motion: no-preference)
    and gated by .gg-has-js.
    """
    for t in types:
        if t not in SUPPORTED_TYPES:
            raise ValueError(f"Unknown animation type: {t!r}. Supported: {SUPPORTED_TYPES}")

    rules = []

    if "fade-stagger" in types:
        # Initial hidden state (opacity + transform for perceptible reveal)
        rules.append(
            f'.gg-has-js [data-animate="fade-stagger"] > * {{\n'
            f'  opacity: 0;\n'
            f'  transform: translateY(24px);\n'
            f'  transition: opacity 0.5s {_EASING}, transform 0.5s {_EASING};\n'
            f'}}'
        )
        # Visible state
        rules.append(
            f'.gg-in-view[data-animate="fade-stagger"] > * {{\n'
            f'  opacity: 1;\n'
            f'  transform: translateY(0);\n'
            f'}}'
        )
        # Stagger delays for up to 7 children (80ms increments)
        for i in range(2, 8):
            delay = _STAGGER_MS * (i - 1) / 1000
            rules.append(
                f'.gg-in-view[data-animate="fade-stagger"] > :nth-child({i}) {{\n'
                f'  transition-delay: {delay:.2f}s;\n'
                f'}}'
            )

    if "bar" in types:
        rules.append(
            f'.gg-has-js [data-animate="bar"] .gg-animated-bar__fill {{\n'
            f'  width: 0;\n'
            f'  transition: width 1s {_EASING};\n'
            f'}}'
        )
        rules.append(
            f'.gg-in-view[data-animate="bar"] .gg-animated-bar__fill {{\n'
            f'  width: var(--w);\n'
            f'}}'
        )
        for i in range(2, 6):
            delay = 100 * (i - 1) / 1000
            rules.append(
                f'.gg-in-view[data-animate="bar"] .gg-animated-bar__row:nth-child({i})'
                f' .gg-animated-bar__fill {{\n'
                f'  transition-delay: {delay:.1f}s;\n'
                f'}}'
            )

    if "progress" in types:
        rules.append(
            f'.gg-has-js [data-animate="progress"] .gg-animated-bar__fill {{\n'
            f'  width: 0;\n'
            f'  transition: width 1s {_EASING};\n'
            f'}}'
        )
        rules.append(
            f'.gg-in-view[data-animate="progress"] .gg-animated-bar__fill {{\n'
            f'  width: var(--w);\n'
            f'}}'
        )

    inner = "\n".join(rules)
    return (
        f'/* ── Scroll animations (shared) ── */\n'
        f'@media (prefers-reduced-motion: no-preference) {{\n'
        f'{inner}\n'
        f'}}'
    )


def get_scroll_animation_js() -> str:
    """Return IntersectionObserver JS for scroll-triggered animations.

    Adds .gg-has-js to <html>, observes [data-animate] elements,
    adds .gg-in-view on intersection (threshold 0.2), then unobserves.
    Elements already in viewport on load get .gg-in-view immediately.
    """
    return '''/* ── Scroll animation observer ── */
document.documentElement.classList.add('gg-has-js');
if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  var animObs = new IntersectionObserver(function(entries, obs) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('gg-in-view');
        obs.unobserve(entry.target);
      }
    });
  }, { threshold: 0.2 });
  document.querySelectorAll('[data-animate]').forEach(function(el) {
    var rect = el.getBoundingClientRect();
    if (rect.top < window.innerHeight && rect.bottom > 0) {
      el.classList.add('gg-in-view');
    } else {
      animObs.observe(el);
    }
  });
}'''
