"""Endure Labs offers: the site-footer trial and the race-page trial."""
from urllib.parse import urlencode

SIGNUP_URL = "https://endurelabs.app/sign-up?" + urlencode({
    "source": "ggc", "intent": "training",
    "utm_source": "gravel-god", "utm_medium": "referral",
    "utm_campaign": "endure_trial", "utm_content": "site_footer",
})

def get_endure_offer_html() -> str:
    return f'''<aside class="endure-trial-offer" aria-label="Endure training app">
<style>
.endure-trial-offer {{max-width:960px;margin:0 auto;padding:24px;box-sizing:border-box;text-align:left;color:var(--gg-color-tan,#d4c5b9);background:var(--gg-color-dark-brown,#3a2e25);border-top:1px solid currentColor}}
.endure-trial-offer h4 {{color:inherit;font:700 14px var(--gg-font-data,monospace);letter-spacing:.08em;margin:0 0 8px}}
.endure-trial-offer p {{font:16px/1.5 var(--gg-font-editorial,Georgia,serif);margin:8px 0;max-width:66ch;color:inherit}}
.endure-trial-offer nav {{color:inherit;display:flex;flex-wrap:wrap;gap:12px}}
.endure-trial-offer a {{display:inline-flex;align-items:center;min-height:44px;padding:0 12px;color:inherit;font:700 13px var(--gg-font-data,monospace);text-decoration:underline}}
.endure-trial-offer a:focus-visible {{outline:2px solid currentColor;outline-offset:3px}}
.endure-trial-offer .endure-trial-terms {{font-size:14px}}
</style>
<h4>ENDURE</h4>
<p>Your training, in one place.</p>
<nav aria-label="Endure"><a href="{SIGNUP_URL.replace('&', '&amp;')}" data-ga="endure_trial_click" data-ga-label="site_footer">Try Endure for 14 days</a><a href="https://endurelabs.app/help">Endure Help Center</a></nav>
<p class="endure-trial-terms">14 days free. Card required. Then your selected plan bills automatically unless you cancel. Cancel online before your trial ends to avoid a charge. Available to eligible new subscribers.</p>
</aside>'''


# Race-page offer: the Endure Labs trial. One place for the terms, so the
# page copy and the tests read the same numbers.
TRIAL_DAYS = 14
PRICE_MONTHLY = "$24"
PRICE_YEARLY = "$199"
TRIAL_CTA = "endure_trial"  # data-cta, so GA4 cta_click reports cta_name=endure_trial
TRIAL_BUTTON = f"START {TRIAL_DAYS} DAYS FREE"
TRIAL_PRICE_LINE = f"{PRICE_MONTHLY} / MONTH \u00b7 {PRICE_YEARLY} / YEAR"
TRIAL_TERMS = f"Card required. Billing starts after {TRIAL_DAYS} days unless you cancel."


def endure_trial_url(slug: str) -> str:
    """Endure sign-up for a race page.

    Endure reads race (matched in its race_catalog to prefill the goal event),
    utm_source (brand) and interval (annual is preselected).
    """
    return "https://endurelabs.app/sign-up?" + urlencode({
        "race": slug,
        "utm_source": "gravel-god",
        "utm_medium": "race-page",
        "utm_campaign": "endure_trial",
        "interval": "year",
    })
