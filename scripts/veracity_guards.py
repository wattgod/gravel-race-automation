"""Guards for the rankings veracity bot (scripts/verify_race_rankings.py).

Why this exists: the bot's 2026-10-01 and 2026-10-08 runs (commits 564145d5,
217d624f) wrote a one-off 2026 fire reroute onto Leadville's standard course,
took Nordic Chase's elevation from a tracker (Dotwatcher) over the organizer's
own figure and the profile's own elevation_m, replaced flagship distances with
shorter options (Majka 73 -> 45 mi, Nordsjorittet 96 -> 56 mi), and never
regenerated web/race-index.json, which kept main's CI red for 9 days.

Every function here is pure, so each guard is unit-testable without the API.

Rules:
  1. Source priority: official race site > official results > reputable
     outlets > everything else > trackers. A weaker source never overwrites a
     value backed by a stronger one. Only official site/results auto-commit;
     outlets and unknown sites go to human review (many profiles carry a
     placeholder website, so a real organizer domain can rank unknown);
     trackers are never written.
  2. Course scope: the profile describes the flagship/standard course. One-off
     reroutes, fire/weather detours and single-edition changes are recorded as
     a note, never written as the value. A shorter course option never
     replaces the flagship distance.
  3. Change limits: a distance/elevation change over 15%, or any score change
     of 2+ points, never auto-commits; it goes to a labelled review PR.
  4. Unit sanity: the profile's own metric twin (elevation_m, distance_km)
     moves with every write; when the twin agrees with neither the old nor
     the new value, or old -> new looks like a km/mi or m/ft mix-up, the
     change goes to review.
"""

import re
from urllib.parse import urlparse

# --- 1. Source priority -----------------------------------------------------

TIER_TRACKER = 0
TIER_OTHER = 1
TIER_OUTLET = 2
TIER_RESULTS = 3
TIER_OFFICIAL = 4

TIER_NAMES = {
    TIER_TRACKER: "tracker",
    TIER_OTHER: "unknown/aggregator",
    TIER_OUTLET: "reputable outlet",
    TIER_RESULTS: "official results",
    TIER_OFFICIAL: "official race site",
}

# Live trackers and route/activity platforms: their numbers describe one
# edition's GPS trace (or one rider's), not the published course.
TRACKER_DOMAINS = {
    "dotwatcher.cc", "trackleaders.com", "followmychallenge.com",
    "maprogress.com", "strava.com", "ridewithgps.com", "komoot.com",
    "garmin.com", "trackrace.tk", "racemap.com", "legendstracking.com",
    "opentracking.co.uk", "pinktracker.com",
}

RESULTS_DOMAINS = {
    "athlinks.com", "webscorer.com", "raceresult.com", "my.raceresult.com",
    "sportstats.ca", "sportstats.one", "chronotrack.com", "mylaps.com",
    "runsignup.com", "itsyourrace.com", "racetimer.se", "sportident.com",
    "datasport.com", "results.chronotrack.com", "endurancecui.active.com",
}

OUTLET_DOMAINS = {
    "cyclingnews.com", "velo.outsideonline.com", "velonews.com",
    "outsideonline.com", "escapecollective.com", "bikeradar.com",
    "cyclingweekly.com", "gravelcyclist.com", "bikepacking.com",
    "road.cc", "cyclist.co.uk", "rouleur.cc", "pinkbike.com",
    "singletracks.com", "cxmagazine.com", "theradavist.com",
    "globalcyclingnetwork.com", "gcn.eu", "cyclingtips.com",
    "bicycling.com", "ridinggravel.com", "mbaction.com", "procyclingstats.com",
}


def _domain(url):
    if not url:
        return ""
    host = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
    host = host.split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _domain_matches(host, domains):
    return any(host == d or host.endswith("." + d) for d in domains)


def official_domains(race):
    """Domains the profile itself names as the organizer's own site."""
    urls = []
    vitals = race.get("vitals") or {}
    for key in ("website", "registration_url", "official_site"):
        urls.append(vitals.get(key))
    for block, keys in (("logistics", ("official_site", "registration_url")),
                        ("organizer", ("website",)),
                        ("source_review", ("official_url", "registration_url")),
                        ("links", ("website", "registration"))):
        b = race.get(block)
        if isinstance(b, dict):
            urls.extend(b.get(k) for k in keys)
    for c in race.get("citations") or []:
        if isinstance(c, dict) and c.get("category") == "official":
            urls.append(c.get("url"))
    hosts = {_domain(u) for u in urls if isinstance(u, str) and u.strip()}
    # Registration platforms are not the organizer's site.
    hosts -= {"bikereg.com", "runsignup.com", "eventbrite.com", "active.com",
              "ultrasignup.com", "raceroster.com", "letsdothis.com"}
    return {h for h in hosts if h}


def source_tier(url, race):
    """Rank a source URL for this race. Unknown domains rank OTHER."""
    host = _domain(url)
    if not host:
        return TIER_TRACKER  # no source at all is the weakest possible
    if _domain_matches(host, TRACKER_DOMAINS):
        return TIER_TRACKER
    if _domain_matches(host, official_domains(race)):
        return TIER_OFFICIAL
    if _domain_matches(host, RESULTS_DOMAINS):
        return TIER_RESULTS
    if _domain_matches(host, OUTLET_DOMAINS):
        return TIER_OUTLET
    return TIER_OTHER


def existing_backing_tier(race, field, current_value, provenance=None):
    """How strongly the profile's CURRENT value is backed.

    provenance: verify_state[slug]["sources"] — what the bot recorded the
    last time it confirmed or wrote this field. Otherwise a profile researched
    from the organizer's own pages (an "official" citation) is treated as
    official-backed.
    """
    best = TIER_OTHER
    rec = (provenance or {}).get(field)
    if rec and _same_value(rec.get("value"), current_value):
        best = max(best, int(rec.get("tier", TIER_OTHER)))
    if any(isinstance(c, dict) and c.get("category") == "official"
           for c in race.get("citations") or []):
        best = max(best, TIER_OFFICIAL)
    return best


def _same_value(a, b):
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return str(a).strip().lower() == str(b).strip().lower()


# --- 2. Course scope ----------------------------------------------------------

COURSE_SCOPES = ["standard_course", "one_off_edition", "shorter_option", "unknown"]

ONE_OFF_RE = re.compile(
    r"re-?rout|detour|wild\s?fire|\bfire\b|smoke|weather|snow|flood|storm"
    r"|modified|altered|alternate|shortened|neutrali[sz]ed|construction"
    r"|road closure|closed section|excludes?\b|one-?off|this year'?s"
    r"|\b20\d\d\b (?:course|route) (?:was|is|will)",
    re.IGNORECASE,
)
SHORTER_OPTION_RE = re.compile(
    r"\bdistances\b|\boptions?\b|medio\s?fondo|\bshort(?:er)? (?:course|route|option|distance)"
    r"|\bhalf\b|\bmini\b|\blite\b|\bsprint\b|\bthree (?:routes|courses)"
    r"|\btwo (?:routes|courses)",
    re.IGNORECASE,
)
_DIST_NUM_RE = re.compile(r"\d+(?:\.\d+)?\s?(?:km|mi|miles|mile)\b", re.IGNORECASE)


def course_scope_block(verdict):
    """Return a reason string if this verdict must not be written as the value.

    Uses the agent's own course_scope label AND a keyword backstop on its
    note — Haiku labelled the Leadville fire reroute "high confidence" with a
    note that said "Modified due to Willow Fire".
    """
    scope = verdict.get("course_scope") or "unknown"
    note = verdict.get("note") or ""
    if scope == "one_off_edition" or ONE_OFF_RE.search(note):
        return "one_off"
    if scope == "shorter_option":
        return "shorter_option"
    return None


def is_shorter_option(verdict, old, new):
    """A distance decrease that the evidence says is another (shorter) option."""
    if new is None or old is None or new >= old:
        return False
    note = verdict.get("note") or ""
    if (verdict.get("course_scope") == "shorter_option"
            or SHORTER_OPTION_RE.search(note)
            or len(_DIST_NUM_RE.findall(note)) >= 2):
        return True
    return False


# --- 3. Change limits -----------------------------------------------------------

MAX_AUTO_VITAL_REL_CHANGE = 0.15
MAX_AUTO_SCORE_DELTA = 1  # a delta of 2+ points needs a human


def rel_change(old, new):
    if not old:
        return float("inf") if new else 0.0
    return abs(new - old) / abs(old)


def score_delta_needs_review(old, new):
    try:
        return abs(float(new) - float(old)) > MAX_AUTO_SCORE_DELTA
    except (TypeError, ValueError):
        return False


# --- 4. Unit sanity ---------------------------------------------------------------

M_TO_FT = 3.28084
KM_TO_MI = 0.621371
UNIT_TOLERANCE = 0.03

METRIC_TWINS = {
    "elevation_ft": ("elevation_m", M_TO_FT),
    "distance_mi": ("distance_km", KM_TO_MI),
}


def _close(a, b, tol=UNIT_TOLERANCE):
    return b and abs(a - b) / abs(b) <= tol


def _twin(vitals, field):
    twin = METRIC_TWINS.get(field)
    if not twin:
        return None, None, None
    twin_field, factor = twin
    try:
        return twin_field, float(vitals.get(twin_field)), factor
    except (TypeError, ValueError):
        return None, None, None


def unit_twin_conflict(vitals, field, new):
    """Genuine conflict: the profile's own metric twin agrees with NEITHER the
    current imperial value nor the new one, so we can't tell which number is
    right. Route to human review. A consistent profile (old value matches the
    twin) is a normal change; write it and move the twin with
    sync_metric_twin.

    Returns a reason string or None.
    """
    twin_field, twin_val, factor = _twin(vitals, field)
    if twin_field is None:
        return None
    expected = twin_val * factor
    try:
        old = float(vitals.get(field))
    except (TypeError, ValueError):
        old = None
    if _close(new, expected) or (old is not None and _close(old, expected)):
        return None
    return (f"{field} {new:g} and current {old if old is None else f'{old:g}'} both "
            f"disagree with the profile's own {twin_field} {twin_val:g} "
            f"(= {expected:,.0f})")


def sync_metric_twin(vitals, field, new):
    """After writing an imperial value, keep its metric twin consistent.
    Returns (twin_field, old, new) when the twin moved, else None."""
    twin_field, twin_val, factor = _twin(vitals, field)
    if twin_field is None:
        return None
    new_twin = int(round(new / factor))
    if _close(new, twin_val * factor, tol=0.005):
        return None
    vitals[twin_field] = new_twin
    return twin_field, twin_val, new_twin


def looks_like_unit_mixup(field, old, new):
    """old -> new is exactly a km/mi or m/ft conversion: a units bug, not a
    real correction (e.g. Majka 73 'mi' that was really 73 km)."""
    if not old or not new:
        return False
    factor = M_TO_FT if field.startswith("elevation") else 1 / KM_TO_MI
    return _close(new, old * factor) or _close(new, old / factor)
