"""Public race metadata handoff; personal calculation stays in Endure Labs."""

import html
import math
import re

ENDURE_CALCULATOR_URL = "https://endurelabs.app/plan/races/calculator"
_KEY = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_MEASUREMENT = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(mi|mile|miles|km|k)\s*$", re.I)


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and 0 < number <= 10000 else None


def _year(race, vitals):
    if vitals.get("course_status") == "source_blocked":
        return None
    for value in (race.get("edition_year"), vitals.get("edition_year")):
        if not isinstance(value, bool) and re.fullmatch(r"\d{4}", str(value or "")):
            year = int(value)
            if 1900 <= year <= 2200:
                return year
    # Only the leading edition is authoritative. A later historical year in
    # prose must not displace it, and today's year is never a fallback.
    match = re.match(r"^\s*(\d{4})(?::|-(?:\d{2})-\d{2}(?:\b|T))", str(vitals.get("date_specific") or ""))
    if match and 1900 <= int(match.group(1)) <= 2200:
        return int(match.group(1))
    return None


def _distance(value):
    item = _mapping(value)
    number = _number(item.get("distance_mi"))
    unit = "mile"
    if number is None:
        number = _number(item.get("distance_km"))
        unit = "km"
    if number is None:
        raw = item.get("distance", value if isinstance(value, str) else None)
        match = _MEASUREMENT.fullmatch(raw) if isinstance(raw, str) else None
        if match:
            number = _number(match.group(1))
            unit = "mile" if match.group(2).lower().startswith("mi") else "km"
        elif isinstance(raw, (int, float)) and not isinstance(raw, bool):
            explicit_unit = str(item.get("unit") or "").lower()
            if explicit_unit in ("mi", "mile", "miles", "km", "kilometers", "kilometres"):
                number = _number(raw)
                unit = "mile" if explicit_unit.startswith("mi") else "km"
    if number is None:
        return None
    figure = format(number, ".10g")
    key = next((str(item[field]) for field in ("key", "slug", "id")
                if isinstance(item.get(field), str) and len(item[field]) <= 120 and _KEY.fullmatch(item[field])), None)
    key = key or figure.replace(".", "-") + "-" + unit
    measurement = figure + (" mi" if unit == "mile" else " km")
    name = item.get("label") or item.get("name")
    label = str(name).strip()[:160] if isinstance(name, str) and name.strip() else measurement
    if name and label.lower() != measurement.lower():
        label += " · " + measurement
    return {"key": key, "label": label}


def race_calculator_context(race):
    """Retain only public, source-supported metadata from a raw profile."""
    race = _mapping(race)
    vitals = _mapping(race.get("vitals"))
    slug = race.get("slug")
    slug = slug if isinstance(slug, str) and len(slug) <= 120 and _SLUG.fullmatch(slug) else None
    blocked = vitals.get("course_status") == "source_blocked"
    options = []
    ambiguous = set()
    seen = {}
    if not blocked:
        for owner in (race, vitals):
            for field in ("distances", "distance_options", "distance_variants"):
                rows = owner.get(field)
                if not isinstance(rows, list):
                    continue
                for raw in rows[:100]:
                    option = _distance(raw)
                    if option is None:
                        continue
                    key = option["key"]
                    if key in seen and seen[key] != option["label"]:
                        ambiguous.add(key)
                    elif key not in seen and len(options) < 40:
                        seen[key] = option["label"]
                        options.append(option)
        options = [option for option in options if option["key"] not in ambiguous]
        if not options:
            primary = _distance({"distance_mi": vitals.get("distance_mi")})
            if primary and primary["key"] not in ambiguous:
                options.append(primary)
    return {"slug": slug, "edition": _year(race, vitals), "distances": options, "source_blocked": blocked}


def build_race_calculator(rd):
    """A native GET form works without JS and never carries health inputs."""
    context = rd.get("calculator")
    if not isinstance(context, dict):
        context = race_calculator_context(rd)
    esc = html.escape
    slug = context.get("slug")
    safe_slug = isinstance(slug, str) and len(slug) <= 120 and _SLUG.fullmatch(slug)
    fields = '<input type="hidden" name="source" value="gravel">'
    if safe_slug:
        fields += '<input type="hidden" name="race" value="' + esc(slug) + '">'
    edition = context.get("edition")
    if safe_slug and isinstance(edition, int) and not isinstance(edition, bool) and 1900 <= edition <= 2200:
        fields += '<input type="hidden" name="edition" value="' + str(edition) + '">'
    options = context.get("distances") if safe_slug else []
    options = options if isinstance(options, list) else []
    valid = [option for option in options[:40] if isinstance(option, dict)
             and isinstance(option.get("key"), str) and len(option["key"]) <= 120
             and _KEY.fullmatch(option["key"]) and isinstance(option.get("label"), str)]
    if valid:
        choices = "".join('<option value="' + esc(option["key"]) + '">' + esc(option["label"]) + '</option>' for option in valid)
        choice = '<label for="gg-calculator-distance">Distance</label><select id="gg-calculator-distance" name="distance">' + choices + '</select>'
    else:
        choice = '<p class="gg-race-calculator-unknown">Choose your distance in Endure Labs.</p>'
    note = ("Confirm this race's edition and course file in Endure Labs." if context.get("source_blocked")
            else "Choose the edition and course file in Endure Labs.")
    return '''<section id="race-calculator" class="gg-race-calculator" aria-labelledby="gg-calculator-title" data-measure-section="race-calculator">
  <div class="gg-race-calculator-heading"><span class="gg-race-calculator-kicker">Endure Labs</span><h2 id="gg-calculator-title">Race calculator</h2></div>
  <p class="gg-race-calculator-intro">Explore power and weather choices for ''' + esc(str(rd.get("name") or "this race")) + '''.</p>
  <form action="''' + ENDURE_CALCULATOR_URL + '''" method="get" class="gg-race-calculator-form">
    ''' + fields + choice + '''
    <button type="submit" class="gg-race-calculator-button" data-cta="race_calculator_open">Open in Endure Labs <span aria-hidden="true">↗</span></button>
  </form>
  <p class="gg-race-calculator-note">''' + esc(note) + '''</p>
</section>'''


def get_race_calculator_css():
    """GG×Glyph control surface; host fonts and token chain stay intact."""
    return '''
.gg-neo-brutalist-page .gg-race-calculator { margin: var(--gg-spacing-xl) 0; padding: var(--gg-spacing-lg); border: var(--gg-border-standard); background: var(--gg-color-warm-paper); color: var(--gg-color-dark-brown); scroll-margin-top: calc(var(--gg-header-height, 80px) + var(--gg-spacing-4xl)); }
.gg-neo-brutalist-page .gg-race-calculator-heading { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: var(--gg-spacing-sm); }
.gg-neo-brutalist-page .gg-race-calculator-heading h2 { margin: 0; font-family: var(--gg-font-data); font-size: var(--gg-font-size-lg); }
.gg-neo-brutalist-page .gg-race-calculator-kicker { font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); font-weight: var(--gg-font-weight-bold); letter-spacing: var(--gg-letter-spacing-wide); }
.gg-neo-brutalist-page .gg-race-calculator-intro { margin: var(--gg-spacing-md) 0; font-family: var(--gg-font-editorial); overflow-wrap: anywhere; }
.gg-neo-brutalist-page .gg-race-calculator-form { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: var(--gg-spacing-sm); font-family: var(--gg-font-data); }
.gg-neo-brutalist-page .gg-race-calculator-form label { font-size: var(--gg-font-size-sm); }
.gg-neo-brutalist-page .gg-race-calculator-form select { width: 100%; min-width: 0; min-height: var(--gg-spacing-2xl); padding: var(--gg-spacing-xs) var(--gg-spacing-sm); border: var(--gg-border-standard); border-radius: 0; background: var(--gg-color-warm-paper); color: var(--gg-color-dark-brown); font: inherit; }
.gg-neo-brutalist-page .gg-race-calculator-button { min-height: var(--gg-spacing-2xl); padding: var(--gg-spacing-xs) var(--gg-spacing-md); border: var(--gg-border-standard); border-radius: 0; background: var(--gg-color-dark-brown); color: var(--gg-color-warm-paper); font: inherit; font-weight: var(--gg-font-weight-bold); cursor: pointer; transition: transform 150ms ease; }
.gg-neo-brutalist-page .gg-race-calculator-button:hover { transform: translateY(-1px); }
.gg-neo-brutalist-page .gg-race-calculator-form :focus-visible { outline: var(--gg-border-width-standard) solid var(--gg-color-teal); outline-offset: var(--gg-spacing-2xs); }
.gg-neo-brutalist-page .gg-race-calculator-note, .gg-neo-brutalist-page .gg-race-calculator-unknown { margin: var(--gg-spacing-md) 0 0; font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); }
.gg-neo-brutalist-page .gg-race-calculator-note { border-top: var(--gg-border-width-subtle) dotted var(--gg-color-secondary-brown); padding-top: var(--gg-spacing-sm); }
.gg-neo-brutalist-page .gg-race-calculator-unknown { grid-column: 1 / 3; margin: 0; }
@media (max-width: 640px) { .gg-neo-brutalist-page .gg-race-calculator-form { grid-template-columns: 1fr; } .gg-neo-brutalist-page .gg-race-calculator-unknown { grid-column: auto; } .gg-neo-brutalist-page .gg-race-calculator-button { width: 100%; } }
@media (prefers-reduced-motion: reduce) { .gg-neo-brutalist-page .gg-race-calculator-button { transition: none; } .gg-neo-brutalist-page .gg-race-calculator-button:hover { transform: none; } }
'''
