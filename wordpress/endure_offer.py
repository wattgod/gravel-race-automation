"""Separate Endure subscription offer; plan and coaching purchases keep their terms."""
import re
from datetime import date, timedelta
from urllib.parse import urlencode

SIGNUP_URL = "https://endurelabs.app/sign-up?" + urlencode({
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


ENDURE_PLAN_COPY = "Or train in Endure: $24/month, 14 days free"

# Beta: only these race pages carry the secondary Endure link (spec G-A, 10-20 races).
# Each has a single confirmed 2027 date, a distance and a climbing figure, so the
# sign-up can be pre-filled. Pages whose date lapses drop the link on their own.
ENDURE_PLAN_RACES = frozenset({
    "unbound-200", "bwr-california", "bwr-arizona", "ukiah-mendo-gravel-epic",
    "bootlegger-100", "the-gralloch", "low-gap-grasshopper", "huffmaster-grasshopper",
    "dirty-30", "bend-dirt-fest", "coast-to-coast", "sasquatch-duro",
    "oregon-coast-gravel-epic", "barry-roubaix", "hungry-bear-100",
})

_MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], 1)}
# "2027: June 5 ..." but not a range ("March 13-20"), and not a guess.
_DATE_RE = re.compile(r"^(\d{4}): ([A-Z][a-z]+) (\d{1,2})(?![\d\u2013-])")
_UNSURE_RE = re.compile(r"PATTERN|ESTIMATE|TBD|DROPPED|CANCEL|tentative", re.I)
_MAX_DAYS_AHEAD = 730  # Endure drops dates past 2 years


def _race_date(vitals: dict, today: date) -> "date | None":
    text = vitals.get("date_specific") or ""
    match = _DATE_RE.match(text)
    if not match or _UNSURE_RE.search(text):
        return None
    month = _MONTHS.get(match.group(2))
    if not month:
        return None
    try:
        when = date(int(match.group(1)), month, int(match.group(3)))
    except ValueError:
        return None
    return when if today < when <= today + timedelta(days=_MAX_DAYS_AHEAD) else None


def _number(value) -> "str | None":
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    return f"{value:g}"


def _climbing_ft(vitals: dict) -> "str | None":
    raw = _number(vitals.get("elevation_ft"))
    if raw:
        return raw
    # Page data carries climbing pre-formatted, e.g. "11,000 ft".
    match = re.fullmatch(r"([\d,]+(?:\.\d+)?) ft", str(vitals.get("elevation") or "").strip())
    return _number(float(match.group(1).replace(",", ""))) if match else None


def endure_plan_url(race: dict, today: "date | None" = None) -> "str | None":
    """Endure sign-up link carrying the race facts (read by Endure's race hand-off).

    Returns None unless the race is on the beta list and has a confirmed future
    date, distance and climbing.
    """
    if race.get("slug") not in ENDURE_PLAN_RACES:
        return None
    vitals = race.get("vitals") or {}
    when = _race_date(vitals, today or date.today())
    distance = _number(vitals.get("distance_mi"))
    climbing = _climbing_ft(vitals)
    name = race.get("name")
    if not (when and distance and climbing and isinstance(name, str) and name.strip()):
        return None
    return "https://endurelabs.app/sign-up?" + urlencode({
        "race": race["slug"],
        "race_name": name.strip(),
        "race_date": when.isoformat(),
        "distance_mi": distance,
        "elevation_ft": climbing,
        "discipline": "gravel",
        "utm_source": "gravel-god",
        "utm_medium": "race-page",
        "utm_campaign": "endure_plan",
    })
