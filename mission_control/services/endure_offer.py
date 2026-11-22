"""Endure trial offer: the one place Mission Control keeps its wording.

The disclosure is the approved small print that sits under every Endure
sign-up button. It is the same text as the site footer offer in
wordpress/endure_offer.py (tests/test_endure_offer_terms in
mission_control/tests/test_endure_plan_url.py checks the two match by reading
that file as text). Mission Control never imports wordpress/.

Templates never hard-code it: the engine supplies it as the server-derived
{endure_trial_terms} token (sequence_engine._render_template).
"""

ENDURE_SIGNUP_URL = "https://endurelabs.app/sign-up"

ENDURE_TRIAL_TERMS = (
    "14 days free. Card required. Then your selected plan bills automatically "
    "unless you cancel. Cancel online before your trial ends to avoid a charge. "
    "Available to eligible new subscribers."
)

# utm_campaign on the kit email's sign-up link.
ENDURE_KIT_CAMPAIGN = "kit_endure_plan"

# Brands whose kit leads get the Endure race offer, and the utm_source each
# one's link carries. XC Ski Labs is absent on purpose: Endure builds gravel,
# road and mtb seasons only.
ENDURE_UTM_SOURCES = {
    "gravelgod": "gravel-god",
    "roadielabs": "roadie-labs",
}

# Race disciplines Endure builds a season for, as the race data spells them.
ENDURE_DISCIPLINES = {
    "gravel": "gravel",
    "mtb": "mtb",
    "mountain_bike": "mtb",
    "mountain-bike": "mtb",
    "road": "road",
}

# Endure drops race dates more than two years out.
ENDURE_MAX_DAYS_AHEAD = 730
