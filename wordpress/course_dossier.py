"""Course Dossier race page (mock 6, chosen by Matti 2026-11-17, issue #675).

The first screen of every race page: a dark hero whose image is the course's
elevation profile, three cards lifted over its edge (why the score, the course,
your race), and a sticky route bar that indexes the section cards below.

Everything here draws only on real data:
- elevation: data/route-elevation/<slug>.json (scripts/fetch_route_elevation.py),
  used only while the race profile still lists that RideWithGPS route;
- route map: data/route-geometry/<slug>.json, same rule;
- race-day hours: the finish-time planner's Open-Meteo archive day
  (data/planner/courses/<slug>.json), only on pages that show the planner;
- the plan strip: weeks from today to the confirmed race date, or to last
  year's slot (labelled) when the date is not announced.
Anything missing is left out or labelled missing, never filled in.
"""

from __future__ import annotations

import html
import json
import math
import re
from datetime import date
from pathlib import Path

from pricing import BLOCK_PRICE, BLOCK_WEEKS
from season import PAST, UPCOMING, canonical, estimate_next, parse_edition
from season import today as season_today

ROOT = Path(__file__).resolve().parent.parent
ELEVATION_DIR = ROOT / "data" / "route-elevation"
GEOMETRY_DIR = ROOT / "data" / "route-geometry"
PLANNER_COURSES = ROOT / "data" / "planner" / "courses"

assert BLOCK_WEEKS == 4, "the rate line says four weeks"
# The only price copy on the page (Matti, 2026-11-17): the rate, never a total
# or a payment count.
PRICE_RATE = f"{BLOCK_PRICE} / four weeks"

M_PER_MI = 1609.344
FT_PER_M = 3.28084

DIM_SHORT = {
    'logistics': 'LOG', 'length': 'LEN', 'technicality': 'TEC', 'elevation': 'ELV',
    'climate': 'CLM', 'altitude': 'ALT', 'adventure': 'ADV', 'prestige': 'PRS',
    'race_quality': 'QLT', 'experience': 'EXP', 'community': 'COM',
    'field_depth': 'FLD', 'value': 'VAL', 'expenses': 'CST',
}


def esc(text) -> str:
    if text is None:
        return ''
    return html.escape(str(text), quote=True)


# ── Plan weeks ────────────────────────────────────────────────

def weeks_to(race_day: date, on: date) -> int:
    """Whole training weeks from ``on`` to race day: ceil(days / 7), 0 if past."""
    days = (race_day - on).days
    return math.ceil(days / 7) if days > 0 else 0


def plan_phases(n: int) -> dict:
    """Split ``n`` weeks: taper min(2, n), race-specific min(8, rest),
    build min(8, rest), base the remainder."""
    n = max(0, int(n))
    taper = min(2, n)
    specific = min(8, n - taper)
    build = min(8, n - taper - specific)
    base = n - taper - specific - build
    return {'base': base, 'build': build, 'specific': specific, 'taper': taper}


def dress_rehearsal_week(n: int) -> int | None:
    """The week three weeks out from race week (week ``n``), when there is one."""
    return n - 3 if n > 4 else None


def plan_weeks(n: int) -> list[list[dict]]:
    """Weeks 1..n in 4-week blocks; each week has its phase and dress flag."""
    ph = plan_phases(n)
    dress = dress_rehearsal_week(n)
    blocks: list[list[dict]] = []
    for w in range(1, n + 1):
        if w > n - ph['taper']:
            phase = 'taper'
        elif w > n - ph['taper'] - ph['specific']:
            phase = 'specific'
        elif w > ph['base']:
            phase = 'build'
        else:
            phase = 'base'
        if (w - 1) % BLOCK_WEEKS == 0:
            blocks.append([])
        blocks[-1].append({'week': w, 'phase': phase, 'dress': w == dress})
    return blocks


def _fmt(d: date) -> str:
    return f"{d:%a}, {d:%b} {d.day}, {d.year}"


def plan_target(rd: dict, on: date | None = None) -> dict | None:
    """The day the plan counts to.

    ``{'date', 'kind': 'confirmed'}`` for an upcoming, confirmed date.
    ``{'date', 'kind': 'last_year', 'last'}`` when the next date isn't
    announced: last year's slot (same weekday of the month) projected to the
    next edition. None when neither exists or the race isn't running.
    """
    on = on or season_today()
    vitals = rd.get('vitals') or {}
    ds = vitals.get('date_specific')
    ed = parse_edition(ds)
    if ed.state(on) == UPCOMING and ed.date and not ed.estimated:
        return {'date': ed.date, 'kind': 'confirmed'}
    if rd.get('taking_a_break') or vitals.get('course_status') == 'source_blocked':
        return None
    past = []
    if ed.state(on) == PAST and ed.date:
        past.append(ed.date)
    for entry in rd.get('editions') or []:
        try:
            d = date.fromisoformat(str(entry.get('date') or '')[:10])
        except ValueError:
            continue
        if d < on:
            past.append(d)
    if not past:
        return None
    last = max(past)
    est = estimate_next(canonical(parse_edition(last.isoformat())), on)
    while est and est.date and est.date <= on:
        est = estimate_next(canonical(est), on)
    if not est or not est.date:
        return None
    return {'date': est.date, 'kind': 'last_year', 'last': last}


def plan_note(target: dict) -> str:
    if target['kind'] == 'confirmed':
        return f"Counted from today to {_fmt(target['date'])}."
    return (f"The {target['date'].year} date isn't announced yet, so I'm counting to "
            f"last year's slot, {_fmt(target['date'])} (it ran {_fmt(target['last'])}).")


def build_plan_strip(target: dict, on: date | None = None) -> str:
    """The week strip as rendered at build time; the page script recounts it
    from today when it loads."""
    on = on or season_today()
    n = weeks_to(target['date'], on)
    if n <= 0:
        return ''
    blocks = []
    for block in plan_weeks(n):
        cells = ''.join(
            f'<i class="gg-cd-w gg-cd-w--{w["phase"]}{" gg-cd-w--dress" if w["dress"] else ""}" '
            f'title="Week {w["week"]}"></i>'
            for w in block)
        blocks.append(f'<span class="gg-cd-blk" style="--n:{len(block)}">{cells}</span>')
    ph = plan_phases(n)
    label = (f'{n} training weeks in {math.ceil(n / BLOCK_WEEKS)} four-week blocks: '
             f'{ph["base"]} base, {ph["build"]} build, {ph["specific"]} race-specific, {ph["taper"]} taper')
    return (f'<div class="gg-cd-q">My plan: <span data-cd-runway>{n} week{"s" if n != 1 else ""} '
            f'to the start line</span></div>'
            f'<div class="gg-cd-weeks" data-cd-weeks data-race="{target["date"].isoformat()}" '
            f'role="img" aria-label="{esc(label)}">{"".join(blocks)}</div>'
            '<div class="gg-cd-key"><span><i class="gg-cd-w--base"></i>Base</span>'
            '<span><i class="gg-cd-w--build"></i>Build</span>'
            '<span><i class="gg-cd-w--specific"></i>Race-specific</span>'
            '<span><i class="gg-cd-w--taper"></i>Taper</span>'
            '<span><i class="gg-cd-w--dress"></i>Dress rehearsal</span></div>'
            f'<p class="gg-cd-fine">{esc(plan_note(target))}</p>')


# ── Stored course data ────────────────────────────────────────

def _listed_route_id(rd: dict) -> str | None:
    rid = (rd.get('course') or {}).get('ridewithgps_id')
    return str(rid) if rid else None


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def load_elevation(rd: dict) -> dict | None:
    """The cached profile of the route the race still lists, else None."""
    rid = _listed_route_id(rd)
    rec = _load(ELEVATION_DIR / f"{rd.get('slug')}.json") if rid else None
    if not rec or str(rec.get('ridewithgps_id')) != rid:
        return None
    if len(rec.get('elevation_m') or []) < 2:
        return None
    return rec


def load_geometry(rd: dict) -> dict | None:
    """The cached RideWithGPS route drawing, only while the race still lists that route."""
    rid = _listed_route_id(rd)
    rec = _load(GEOMETRY_DIR / f"{rd.get('slug')}.json") if rid else None
    if not rec or not rec.get('path_d') or not rec.get('viewbox'):
        return None
    return rec if str(rec.get('ridewithgps_id')) == rid else None


def race_day_hours(slug: str, hours: int = 15) -> dict | None:
    """Hourly temperature for the planner's archived race day, from the start hour."""
    course = _load(PLANNER_COURSES / f"{slug}.json")
    try:
        ed = course['weather']['editions'][0]
        hourly = ed['openmeteo'][0]['hourly']
        times, temps = hourly['time'], hourly['temperature_2m']
        start_hour = int(ed['start_local'].split(':')[0])
        day = ed['date']
    except (TypeError, KeyError, IndexError, ValueError):
        return None
    first = f"{day}T{start_hour:02d}:00"
    if first not in times:
        return None
    i = times.index(first)
    rows = [(times[j][11:16], temps[j]) for j in range(i, min(i + hours, len(times)))
            if isinstance(temps[j], (int, float))]
    if len(rows) < 3:
        return None
    return {'date': date.fromisoformat(day), 'start': ed['start_local'],
            'source': course['weather'].get('source', ''),
            'rows': [(t, round(c * 9 / 5 + 32)) for t, c in rows]}


# ── SVG drawings ──────────────────────────────────────────────

def _nice_step(total: float) -> float:
    for step in (5, 10, 20, 25, 50, 100, 200, 250, 500, 1000):
        if total / step <= 5:
            return step
    return 2000


def elevation_figure(elev: dict, marks: list[dict], variant: str, cite_n: int | None = None) -> str:
    """Area profile in miles and feet; labels are HTML so they never stretch."""
    dist_mi = [d * 1000 / M_PER_MI for d in elev['distance_km']]
    ele_ft = [e * FT_PER_M for e in elev['elevation_m']]
    total = dist_mi[-1]
    lo, hi = min(ele_ft), max(ele_ft)
    span = max(hi - lo, 1.0)
    w, h, top, bottom = 1200.0, 200.0, 10.0, 196.0

    def xy(i):
        return (dist_mi[i] / total * w, bottom - (ele_ft[i] - lo) / span * (bottom - top))

    pts = [xy(i) for i in range(len(dist_mi))]
    line = 'M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in pts)
    area = f'{line}L{w:.0f} {h:.0f}L0 {h:.0f}Z'
    lines = ''.join(
        f'<line class="gg-cd-prof-mark" x1="{m["mile"] / total * w:.1f}" y1="0" '
        f'x2="{m["mile"] / total * w:.1f}" y2="{h:.0f}"/>'
        for m in marks)
    # Every mark gets its line; a label is left off when it would collide
    # with the previous one (labels are ~12% of a phone-width profile).
    labelled, last = [], None
    for m in sorted(marks, key=lambda m: m['mile']):
        pct = m['mile'] / total * 100
        if last is None or pct - last >= 12:
            labelled.append((m, pct))
            last = pct
    mark_labels = ''.join(
        f'<span class="gg-cd-prof-ml{" gg-cd-prof-ml--end" if pct > 70 else ""}" '
        f'style="left:{pct:.2f}%">MI {m["mile"]:g}</span>'
        for m, pct in labelled)
    step = _nice_step(total)
    ticks = [0.0]
    t = step
    while t < total - step * 0.4:
        ticks.append(t)
        t += step
    ticks.append(total)
    tick_labels = ''.join(
        f'<span style="left:{v / total * 100:.2f}%">{v:,.0f} mi</span>' for v in ticks)
    route = esc(elev.get('route_name') or 'RideWithGPS route')
    label = (f'Elevation profile of the route on file, {total:,.1f} miles, '
             f'{lo:,.0f} to {hi:,.0f} feet')
    gid = f'gg-cd-grad-{variant}'
    return f'''<figure class="gg-cd-prof gg-cd-prof--{variant}">
  <div class="gg-cd-prof-marks" aria-hidden="true">{mark_labels}</div>
  <svg viewBox="0 0 {w:.0f} {h:.0f}" preserveAspectRatio="none" role="img" aria-label="{esc(label)}"><defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop class="gg-cd-stop-a" offset="0"/><stop class="gg-cd-stop-b" offset="1"/></linearGradient></defs><path class="gg-cd-prof-area" d="{area}" fill="url(#{gid})"/><path class="gg-cd-prof-line" d="{line}" vector-effect="non-scaling-stroke"/>{lines}</svg>
  <div class="gg-cd-prof-ticks" aria-hidden="true">{tick_labels}</div>
  <figcaption>Elevation {lo:,.0f}&ndash;{hi:,.0f} ft &middot; <a href="{esc(elev['source_url'])}" rel="noopener" target="_blank">{route}</a> on RideWithGPS{_cite(cite_n)}</figcaption>
</figure>'''


_START = re.compile(r'^\s*M\s*(-?[\d.]+)[ ,](-?[\d.]+)')


def route_map_svg(geo: dict, variant: str, marks_xy: str = '') -> str:
    m = _START.match(geo['path_d'])
    start = (f'<circle class="gg-cd-map-start" cx="{float(m.group(1)):.1f}" '
             f'cy="{float(m.group(2)):.1f}" r="16"/>') if m else ''
    return (f'<svg class="gg-cd-map gg-cd-map--{variant}" viewBox="{esc(geo["viewbox"])}" '
            f'role="img" aria-label="Route map{" with the start marked" if start else ""}">'
            f'<path class="gg-cd-map-line" d="{esc(geo["path_d"])}"/>{start}{marks_xy}</svg>')


# ── Sections ──────────────────────────────────────────────────

def course_marks(rd: dict, total_mi: float | None) -> list[dict]:
    """Suffering zones with a mile inside the route on file."""
    out = []
    for z in (rd.get('course') or {}).get('suffering_zones') or []:
        mile = z.get('mile') if isinstance(z, dict) else None
        if not isinstance(mile, (int, float)) or mile <= 0:
            continue
        if total_mi is not None and mile >= total_mi:
            continue
        out.append({'mile': float(mile), 'label': z.get('label') or z.get('named_section') or '',
                    'desc': z.get('desc') or ''})
    return out[:5]


def _rank(rd: dict, race_index: list) -> tuple[int, int] | None:
    ranked = [r for r in race_index or []
              if (r.get('status') or 'active') == 'active'
              and isinstance(r.get('overall_score'), (int, float))]
    if not any(r.get('slug') == rd.get('slug') for r in ranked):
        return None
    score = rd.get('overall_score') or 0
    return 1 + sum(1 for r in ranked if r['overall_score'] > score), len(ranked)


def build_hero(rd: dict, race_index: list, elev: dict | None, marks: list[dict],
               rider_cell: str, rated_by: str, discipline_label: str = '',
               route_cite: int | None = None) -> str:
    v = rd.get('vitals') or {}
    lab = [esc(rd.get('tier_label', '').title())]
    if discipline_label:
        lab.append(f'<span class="gg-series-badge">{esc(discipline_label)}</span>')
    series = rd.get('series') or {}
    if series.get('id') and series.get('name'):
        lab.append(f'<a href="/race/series/{esc(series["id"])}/">{esc(series["name"])}</a>')
    if v.get('location') and v['location'] != '--':
        lab.append(esc(v['location']))
    if v.get('date') and v['date'] != '--':
        lab.append(esc(v['date']))
    verdict = (rd.get('final_verdict') or {}).get('one_liner', '').strip()
    rank = _rank(rd, race_index)
    meta = 'OF 100'
    if rank:
        meta += f' &middot; #{rank[0]} OF {rank[1]}'
    profile = elevation_figure(elev, marks, 'hero', route_cite) if elev else ''
    brk = rd.get('taking_a_break') or {}
    break_html = (f'<p class="gg-cd-break"><b>{esc(brk["label"])}</b> {esc(brk["line"])}</p>'
                  if brk.get('label') and brk.get('line') else '')
    return f'''<header class="gg-cd-hero{'' if profile else ' gg-cd-hero--flat'}" data-measure-section="hero">
  <div class="gg-cd-hero-top">
    <div class="gg-cd-hero-text">
      <div class="gg-cd-lab">{' &middot; '.join(lab)}</div>
      <h1>{esc(rd['name'])}</h1>
      {f'<p class="gg-cd-verdict">{esc(verdict)}</p>' if verdict else ''}
      {break_html}
    </div>
    <div class="gg-cd-big">
      <b data-target="{esc(rd.get('overall_score'))}">{esc(rd.get('overall_score'))}</b>
      <span>{meta}<br>RATED BY {esc(rated_by.upper())}</span>
      <div class="gg-cd-rider">{rider_cell}</div>
    </div>
  </div>
  {profile}
</header>'''


def _first_sentence(text: str) -> str:
    text = ' '.join(str(text or '').split())
    m = re.match(r'(.+?[.!?])(\s|$)', text)
    return m.group(1) if m else text


def build_why_card(rd: dict, dims_course: list, dims_editorial: list, labels: dict,
                   parse_score) -> str:
    score = rd.get('overall_score')
    heading = _first_sentence((rd.get('biased_opinion') or {}).get('summary', ''))
    impact = parse_score((rd.get('rating') or {}).get('cultural_impact', 0))
    split = f'Course {esc(rd.get("course_profile"))}/35 &middot; Editorial {esc(rd.get("opinion_total"))}/35'
    if impact:
        split += f' &middot; +{impact:g} impact'
    cols = []
    for dim in dims_course + dims_editorial:
        s = max(0, min(5, round(parse_score((rd['explanations'].get(dim) or {}).get('score', 0)))))
        shade = 3 if s >= 5 else 2 if s >= 3 else 1
        cells = ''.join(f'<i{" class=on" if k >= 5 - s else ""}></i>' for k in range(5))
        cols.append(f'<div class="gg-cd-s{shade}" title="{esc(labels.get(dim, dim))} {s}/5">'
                    f'{cells}<span>{DIM_SHORT.get(dim, dim[:3].upper())}</span></div>')
    n_src = len(rd.get('citations') or [])
    src = f' &middot; {n_src} source{"s" if n_src != 1 else ""}' if n_src else ''
    return f'''<div class="gg-cd-card gg-cd-why">
    <div class="gg-cd-lab">Why {esc(score)}</div>
    {f'<h2 class="gg-cd-h3">{esc(heading)}</h2>' if heading else ''}
    <div class="gg-cd-split">{split}</div>
    <div class="gg-cd-lab gg-cd-mt">What it asks of you</div>
    <div class="gg-cd-dg" role="img" aria-label="Fourteen criteria, each scored 1 to 5">{''.join(cols)}</div>
    <div class="gg-cd-dgk"><span>Course</span><span>Editorial</span></div>
    <div class="gg-cd-by">14 criteria{src} &middot; <a href="#ratings">full scorecard &darr;</a></div>
  </div>'''


def build_course_card(rd: dict, geo: dict | None, elev: dict | None,
                      route_cite: int | None = None) -> str:
    v = rd.get('vitals') or {}
    facts = []
    if v.get('distance') and v['distance'] != '--':
        facts.append((v['distance'], 'distance'))
    if v.get('elevation') and v['elevation'] != '--':
        facts.append((v['elevation'], 'climbing'))
    if elev and isinstance(elev.get('high_m'), (int, float)):
        facts.append((f"{elev['high_m'] * FT_PER_M:,.0f} ft", 'high point', route_cite))
    if not facts and not geo:
        return ''
    facts_html = ''.join(f'<div><b>{esc(f[0])}</b><small>{esc(f[1])}{_cite(f[2] if len(f) > 2 else None)}</small></div>'
                         for f in facts)
    map_html = route_map_svg(geo, 'mini') if geo else ''
    foot = []
    reg = str(v.get('registration') or '')
    cost = re.search(r'[\$€£][\d,]+(?:\.\d{2})?', reg)
    if cost:
        foot.append(f'Entry {esc(cost.group(0))}')
    foot.append('<a href="#course">course detail &darr;</a>')
    return f'''<div class="gg-cd-card gg-cd-coursecard">
    <div class="gg-cd-lab">The course</div>
    <div class="gg-cd-mapfacts{'' if geo else ' gg-cd-mapfacts--nomap'}">{map_html}<div class="gg-cd-facts">{facts_html}</div></div>
    <div class="gg-cd-by">{' &middot; '.join(foot)}</div>
  </div>'''


def build_yours_card(rd: dict, *, planner_route: str | None, plan_href: str | None,
                     coaching_href: str | None, target: dict | None,
                     on: date | None = None) -> str:
    """Estimator (pages with the finish-time planner) and the plan offer
    (pages that sell one). '' when the page has neither."""
    parts = []
    if planner_route is not None:
        parts.append(f'''<form class="gg-cd-well gg-cd-est" data-cd-estimator novalidate>
      <div class="gg-cd-q">How long will it take you?</div>
      <div class="gg-cd-fields"><input name="ftp" inputmode="numeric" autocomplete="off" placeholder="FTP, W" aria-label="FTP in watts"><input name="kg" inputmode="decimal" autocomplete="off" placeholder="Weight, lb" aria-label="Weight in pounds"></div>
      <button class="gg-cd-ghost" type="submit">Estimate on the {esc(planner_route)}</button>
    </form>''')
    if plan_href:
        strip = build_plan_strip(target, on) if target else ''
        if not strip and target and target['kind'] == 'confirmed':
            strip = ('<div class="gg-cd-q">My plan</div><p class="gg-cd-fine">It&#x27;s race day, '
                     'so there are no weeks left to count.</p>')
        if not strip:
            strip = ('<div class="gg-cd-q">My plan</div><p class="gg-cd-fine">The next race date '
                     "isn't announced, so there's no week count yet.</p>")
        coach = (f'<a class="gg-cd-coach" href="{esc(coaching_href)}" data-cta="approved_coaching">'
                 'Or have me coach you all season &rarr;</a>') if coaching_href else ''
        parts.append(f'''<div class="gg-cd-plan">{strip}</div>
    <a class="gg-cd-buy" href="{esc(plan_href)}" data-cta="approved_custom_plan">Start my plan</a>
    <div class="gg-cd-fine">{esc(PRICE_RATE)}. Cancel any time.</div>
    {coach}''')
    if not parts:
        return ''
    return f'''<div class="gg-cd-card gg-cd-yours" id="plan"{' data-measure-section="custom-plan"' if plan_href else ''}>
    <div class="gg-cd-lab">Your {esc(rd['name'])}</div>
    {''.join(parts)}
  </div>'''


def build_fold(cards: list[str]) -> str:
    cards = [c for c in cards if c]
    if not cards:
        return ''
    return f'<div class="gg-cd-fold gg-cd-fold--{len(cards)}">{"".join(cards)}</div>'


def build_route_bar(stops: list[tuple[str, str, str]], plan_label: str | None) -> str:
    """Sticky index: (anchor, label, count) per section that is on the page."""
    if not stops:
        return ''
    n = len(stops)
    links = []
    for i, (anchor, label, count) in enumerate(stops):
        left = 4 + (92 * i / (n - 1) if n > 1 else 46)
        links.append(f'<a href="#{esc(anchor)}" style="left:{left:.1f}%" data-cd-stop="{esc(anchor)}">'
                     f'<i></i><span>{esc(label)}</span>{f"<small>{esc(count)}</small>" if count else ""}</a>')
    cta = (f'<a class="gg-cd-cta" href="#plan" data-cta="route_bar_plan">My {esc(plan_label)} plan</a>'
           if plan_label else '')
    return f'''<nav class="gg-cd-route" aria-label="On this page" data-measure-section="route-bar">
  <span class="gg-cd-count">{n} SECTIONS</span>
  <div class="gg-cd-track" data-cd-track><div class="gg-cd-done" data-cd-done></div>
    {''.join(links)}
    <div class="gg-cd-rider-dot" data-cd-rider aria-hidden="true"></div>
  </div>
  {cta}
</nav>'''


def _cite(n: int | None) -> str:
    return f'<a class="gg-cd-cite" href="#gg-citation-{n}">[{n}]</a>' if n else ''


_ROUTE_ID = re.compile(r'ridewithgps\.com/routes/(\d+)')


def route_citation(rd: dict, elev: dict | None, next_n: int) -> tuple[int | None, str]:
    """The source number for the stored route's elevation: the race's own
    citation of that RideWithGPS route when it has one, otherwise a new item
    numbered ``next_n``. Returns (number, extra list item or '')."""
    if not elev:
        return None, ''
    rid = str(elev.get('ridewithgps_id') or '')
    for i, c in enumerate(rd.get('citations') or [], start=1):
        m = _ROUTE_ID.search(str((c or {}).get('url') or ''))
        if m and m.group(1) == rid:
            return i, ''
    url = elev['source_url']
    item = (f'<li class="gg-citation-item" id="gg-citation-{next_n}"><span class="gg-citation-cat">Route Maps</span> '
            f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer" class="gg-citation-link">'
            f'RideWithGPS: {esc(elev.get("route_name") or "course route")}</a>'
            f'<span class="gg-citation-url">{esc(url.split("://", 1)[1])}</span></li>')
    return next_n, item


WEATHER_SOURCE = ("Open-Meteo historical weather archive",
                  "https://open-meteo.com/en/docs/historical-weather-api")


def weather_citation_item(n: int) -> str:
    label, url = WEATHER_SOURCE
    return (f'<li class="gg-citation-item" id="gg-citation-{n}"><span class="gg-citation-cat">Race-day weather</span> '
            f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer" class="gg-citation-link">{esc(label)}</a>'
            f'<span class="gg-citation-url">{esc(url.split("://", 1)[1])}</span></li>')


def build_race_day(hours: dict | None, cite_n: int | None = None) -> str:
    if not hours or not cite_n:
        return ''
    rows = hours['rows']
    temps = [t for _, t in rows]
    lo, hi = min(temps), max(temps)
    peak_t = rows[temps.index(hi)][0]
    span = max(hi - lo, 1)
    bars = ''.join(
        f'<i class="{"gg-cd-hot" if t >= hi - (hi - lo) * 0.2 else ""}" '
        f'style="height:{20 + (t - lo) / span * 80:.0f}%" title="{esc(tm)} {t}°F"></i>'
        for tm, t in rows)
    d = hours['date']
    peak_h = int(peak_t[:2])
    peak = f"{(peak_h % 12) or 12} {'am' if peak_h < 12 else 'pm'}"
    return f'''<section id="race-day" class="gg-section gg-cd-section" data-measure-section="race-day">
    <div class="gg-section-header"><span class="gg-cd-sub">Race day &middot; {d.day} {d:%b} {d.year}</span>
      <h2 class="gg-section-title">{rows[0][1]}&deg;F at the start, {hi}&deg;F by {peak}</h2></div>
    <div class="gg-section-body">
      <p>Recorded hourly on the {d.year} race day from the {esc(hours['start'])} start, not a forecast.<a class="gg-cd-cite" href="#gg-citation-{cite_n}">[{cite_n}]</a></p>
      <div class="gg-cd-hrs" role="img" aria-label="Hourly temperature from {esc(rows[0][0])} to {esc(rows[-1][0])}, {lo} to {hi} degrees F">{bars}</div>
      <div class="gg-cd-hrs-axis"><span>{esc(rows[0][0])}</span><span>{esc(rows[len(rows) // 2][0])}</span><span>{esc(rows[-1][0])}</span></div>
    </div>
  </section>'''


def build_should(rd: dict, linked_alternatives: str) -> str:
    fv = rd.get('final_verdict') or {}
    bo = rd.get('biased_opinion') or {}
    text = (fv.get('should_you_race') or '').strip()
    strengths, weaknesses = bo.get('strengths') or [], bo.get('weaknesses') or []
    if not text and not strengths and not weaknesses and not linked_alternatives:
        return ''
    pos = 'Race it if' if rd.get('race_plan_eligible', True) else 'Ride it if'

    def lst(title, items, cls):
        if not items:
            return ''
        li = ''.join(f'<li>{esc(x)}</li>' for x in items)
        return f'<div class="gg-cd-yn gg-cd-yn--{cls}"><h3>{title}</h3><ul>{li}</ul></div>'

    alts = (f'<p class="gg-cd-alts"><b>Alternatives:</b> {linked_alternatives}</p>'
            if linked_alternatives else '')
    return f'''<section id="should" class="gg-section gg-cd-section" data-measure-section="should">
    <div class="gg-section-header">
      <h2 class="gg-section-title">Should you race it?</h2></div>
    <div class="gg-section-body">
      {f'<p>{esc(text)}</p>' if text else ''}
      <div class="gg-cd-yesno">{lst(pos, strengths, 'y')}{lst('Skip it if', weaknesses, 'n')}</div>
      {alts}
    </div>
  </section>'''


_CITE = re.compile(r'\[(\d+)\]')


def cite_links(escaped: str, n_sources: int) -> str:
    """Turn [n] markers in escaped text into links to source n on this page."""
    return _CITE.sub(
        lambda m: (f'<a class="gg-cd-cite" href="#gg-citation-{m.group(1)}">[{m.group(1)}]</a>'
                   if 1 <= int(m.group(1)) <= n_sources else m.group(0)), escaped)


def build_ratings(rd: dict, dims_course: list, dims_editorial: list, labels: dict,
                  parse_score, n_sources: int) -> str:
    summaries = rd.get('rating_summaries') or {}

    def group(title, total, dims, key):
        rows = []
        for dim in dims:
            entry = rd['explanations'].get(dim) or {}
            s = max(0, min(5, parse_score(entry.get('score', 0))))
            pips = ''.join(f'<i{" class=on" if k < round(s) else ""}></i>' for k in range(5))
            text = (entry.get('explanation') or '').strip()
            body = cite_links(esc(text), n_sources) if text else '<em>No written reason yet.</em>'
            rows.append(f'<div class="gg-cd-r"><b>{esc(labels.get(dim, dim))} {s:g}/5</b>'
                        f'<div class="gg-cd-pp" aria-hidden="true">{pips}</div><span>{body}</span></div>')
        verdict = (summaries.get(key) or '').strip()
        return (f'<div class="gg-cd-rgroup" data-rating-group="{key}"><h3>{title} <span>{esc(total)}/35</span></h3>'
                f'{f"<p class=gg-cd-rverdict>{cite_links(esc(verdict), n_sources)}</p>" if verdict else ""}'
                f'<div class="gg-cd-rt">{"".join(rows)}</div></div>')

    return f'''<section id="ratings" class="gg-section gg-cd-section gg-cd-keep-open" data-measure-section="rating">
    <div class="gg-section-header">
      <h2 class="gg-section-title">Why it scores {esc(rd.get('overall_score'))}</h2></div>
    <div class="gg-section-body">
      {group('Course', rd.get('course_profile'), dims_course, 'course')}
      {group('Editorial', rd.get('opinion_total'), dims_editorial, 'editorial')}
      <p class="gg-cd-fine"><a class="gg-rating-methodology" href="/race/methodology/">How I score races &rarr;</a></p>
    </div>
  </section>'''


def build_course_figure(rd: dict, geo: dict | None, elev: dict | None, marks: list[dict],
                        route_cite: int | None = None) -> str:
    """Map plus light elevation profile and the numbered marks, for the Course card."""
    if not geo and not elev:
        return ''
    fig_map = route_map_svg(geo, 'course') if geo else ''
    fig_prof = elevation_figure(elev, marks, 'course', route_cite) if elev else ''
    marks_html = ''.join(
        f'<div><b>{m["mile"]:g}</b><strong>{esc(m["label"])}</strong> {esc(m["desc"])}</div>'
        for m in marks) if elev else ''
    return (f'<div class="gg-cd-cfig{"" if geo and elev else " gg-cd-cfig--one"}">'
            f'{f"<div class=gg-cd-cfig-map>{fig_map}</div>" if fig_map else ""}'
            f'{f"<div>{fig_prof}</div>" if fig_prof else ""}</div>'
            f'{f"<div class=gg-cd-marks>{marks_html}</div>" if marks_html else ""}')


# ── Styles and script ─────────────────────────────────────────

def get_css() -> str:
    """Course Dossier styles. Colours are brand tokens; the radius and shadow
    are the mock's (Matti chose it 2026-11-17) and live only on these cards."""
    return '''
.gg-cd-page{--cd-night:var(--gg-color-near-black);--cd-card:var(--gg-color-white);--cd-well:var(--gg-color-warm-paper);--cd-line:var(--gg-color-sand);--cd-ink:var(--gg-color-near-black);--cd-ink2:var(--gg-color-dark-brown);--cd-ink3:var(--gg-color-secondary-brown);--cd-none:var(--gg-color-tan);--cd-gold:var(--gg-color-light-gold);--cd-gold-d:var(--gg-color-gold);--cd-r:10px;--cd-shadow:0 1px 2px color-mix(in srgb,var(--gg-color-dark-brown) 8%,transparent),0 2px 6px color-mix(in srgb,var(--gg-color-dark-brown) 8%,transparent);}
.gg-cd-page .gg-cd-lab{font:700 11px/1.4 var(--gg-font-data);letter-spacing:.14em;text-transform:uppercase;color:var(--cd-ink3)}
.gg-cd-page .gg-cd-lab a{color:inherit}
.gg-cd-hero{position:relative;background:var(--cd-night);color:var(--gg-color-warm-paper);box-shadow:0 0 0 100vmax var(--cd-night)!important;clip-path:inset(0 -100vmax);padding:40px 0 92px;margin-top:8px}
.gg-cd-hero--flat{padding-bottom:84px}
.gg-cd-hero .gg-cd-lab{color:var(--gg-color-warm-brown)}
.gg-cd-hero .gg-series-badge{all:unset;font:inherit;letter-spacing:inherit;color:inherit}
.gg-cd-hero-top{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:40px;align-items:end}
.gg-cd-hero h1{font:700 clamp(40px,6.4vw,88px)/.98 var(--gg-font-editorial);letter-spacing:-.025em;margin:14px 0 16px;color:var(--gg-color-warm-paper);overflow-wrap:anywhere}
.gg-cd-verdict{font:italic 400 clamp(19px,2.2vw,26px)/1.35 var(--gg-font-editorial);color:var(--gg-color-sand);margin:0;max-width:34ch}
.gg-cd-break{margin:14px 0 0;font:400 15px/1.5 var(--gg-font-editorial);color:var(--gg-color-sand)}
.gg-cd-break b{display:block;font:700 11px/1.4 var(--gg-font-data);letter-spacing:.12em;color:var(--cd-gold)}
.gg-cd-big{text-align:right}
.gg-cd-big b{display:block;font:800 clamp(84px,11vw,140px)/.8 var(--gg-font-data);color:var(--cd-gold);letter-spacing:-.04em}
.gg-cd-big span{display:block;margin-top:14px;font:700 12px/1.6 var(--gg-font-data);color:var(--gg-color-tan);letter-spacing:.1em}
.gg-cd-rider{margin-top:6px}
.gg-cd-rider a,.gg-cd-rider div{font:700 11px/1.5 var(--gg-font-data);letter-spacing:.08em;color:var(--gg-color-warm-brown)!important;text-decoration:underline;text-underline-offset:3px}
.gg-cd-rider .gg-hero-score-number{display:inline;font-size:20px;color:var(--gg-color-warm-paper)}
.gg-cd-prof{position:relative;margin:26px 0 0}
.gg-cd-prof svg{display:block;width:100%;height:200px}
.gg-cd-prof-area{stroke:none}
.gg-cd-prof--hero .gg-cd-stop-a{stop-color:var(--gg-color-primary-brown)}
.gg-cd-prof--hero .gg-cd-stop-b{stop-color:var(--gg-color-dark-brown)}
.gg-cd-prof--hero .gg-cd-prof-line{fill:none;stroke:var(--cd-gold);stroke-width:1.6}
.gg-cd-prof--course .gg-cd-stop-a,.gg-cd-prof--course .gg-cd-stop-b{stop-color:var(--gg-color-tan)}
.gg-cd-prof--course .gg-cd-prof-line{fill:none;stroke:var(--gg-color-primary-brown);stroke-width:1.4}
.gg-cd-prof-mark{stroke:var(--cd-ink3);stroke-dasharray:2 4;vector-effect:non-scaling-stroke}
.gg-cd-prof--course .gg-cd-prof-mark{stroke:var(--cd-ink)}
.gg-cd-prof-marks{position:relative;height:18px}
.gg-cd-prof-marks span,.gg-cd-prof-ticks span{position:absolute;top:0;transform:translateX(-50%);white-space:nowrap;font:400 11px/1.4 var(--gg-font-data)}
.gg-cd-prof-marks span{transform:none;padding-left:5px;color:var(--gg-color-tan)}
.gg-cd-prof-marks span.gg-cd-prof-ml--end{transform:translateX(-100%);padding:0 5px 0 0}
.gg-cd-prof--course .gg-cd-prof-marks span{color:var(--cd-ink);font-weight:700}
.gg-cd-prof-ticks{position:relative;height:20px;margin-top:6px;color:var(--gg-color-warm-brown)}
.gg-cd-prof-ticks span:first-child{transform:none}
.gg-cd-prof-ticks span:last-child{transform:translateX(-100%)}
.gg-cd-prof--course .gg-cd-prof-ticks{color:var(--cd-ink3)}
.gg-cd-prof figcaption{font:400 11px/1.5 var(--gg-font-data);color:var(--gg-color-warm-brown);margin-top:4px}
.gg-cd-prof figcaption a{color:inherit}
.gg-cd-prof--course figcaption{color:var(--cd-ink3)}
.gg-cd-fold{display:grid;grid-template-columns:1.2fr 1fr 1fr;gap:14px;margin-top:-64px;position:relative;z-index:1}
.gg-cd-fold--2{grid-template-columns:1.2fr 1fr}
.gg-cd-fold--1{grid-template-columns:minmax(0,1fr)}
.gg-cd-card{background:var(--cd-card);border-radius:var(--cd-r)!important;box-shadow:var(--cd-shadow)!important;padding:22px;min-width:0;color:var(--cd-ink)}
.gg-cd-h3{font:700 19px/1.25 var(--gg-font-editorial);margin:6px 0 10px;color:var(--cd-ink)}
.gg-cd-split{font:700 12.5px/1.45 var(--gg-font-data);color:var(--cd-ink2)}
.gg-cd-mt{margin-top:14px}
.gg-cd-dg{display:grid;grid-template-columns:repeat(14,minmax(0,1fr));gap:3px;margin-top:12px}
.gg-cd-dg div{display:grid;gap:2px}
.gg-cd-dg i{display:block;height:9px;border-radius:2px!important;background:var(--cd-well)}
.gg-cd-s1 i.on{background:var(--cd-none)}.gg-cd-s2 i.on{background:var(--cd-ink3)}.gg-cd-s3 i.on{background:var(--cd-ink)}
.gg-cd-dg span{font:700 9px/1 var(--gg-font-data);color:var(--cd-ink3);text-align:center;margin-top:5px;white-space:nowrap;overflow:hidden}
.gg-cd-dgk{display:flex;justify-content:space-between;font:400 11px/1 var(--gg-font-data);color:var(--cd-ink3);margin-top:8px}
.gg-cd-by{font:400 11.5px/1.5 var(--gg-font-data);color:var(--cd-ink3);margin-top:14px;border-top:1px solid var(--cd-line);padding-top:10px}
.gg-cd-by a{color:var(--cd-ink2)}
.gg-cd-mapfacts{display:grid;grid-template-columns:96px minmax(0,1fr);gap:16px;align-items:center;margin-top:10px}
.gg-cd-mapfacts--nomap{grid-template-columns:minmax(0,1fr)}
.gg-cd-map{display:block;width:100%;height:auto}
.gg-cd-map-line{fill:none;stroke:var(--cd-ink);stroke-width:7;stroke-linejoin:round;stroke-linecap:round}
.gg-cd-map--course .gg-cd-map-line{stroke-width:4}
.gg-cd-map-start{fill:var(--cd-gold-d)}
.gg-cd-facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(104px,1fr));gap:10px}
.gg-cd-facts div{background:var(--cd-well);border-radius:8px!important;padding:10px;min-width:0}
.gg-cd-facts b{display:block;font:700 15px/1.2 var(--gg-font-data);white-space:nowrap}
.gg-cd-facts small{font:400 11px/1.3 var(--gg-font-data);color:var(--cd-ink3)}
.gg-cd-yours{display:grid;gap:12px;align-content:start;scroll-margin-top:calc(var(--gg-header-height,56px) + 84px)}
.gg-cd-well{background:var(--cd-well);border-radius:8px!important;padding:14px;margin:0}
.gg-cd-q{font:600 15px/1.3 var(--gg-font-editorial);color:var(--cd-ink)}
.gg-cd-fields{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}
.gg-cd-fields input{width:100%;min-width:0;font:700 15px/1 var(--gg-font-data);padding:10px;border:1px solid var(--cd-none);border-radius:6px!important;background:var(--cd-card);color:var(--cd-ink)}
.gg-cd-ghost{font:700 11.5px/1.2 var(--gg-font-data);letter-spacing:.08em;text-transform:uppercase;padding:12px 14px;border-radius:8px!important;border:1px solid var(--cd-ink);background:var(--cd-card);color:var(--cd-ink);width:100%;margin-top:8px;cursor:pointer}
.gg-cd-weeks{display:flex;gap:5px;margin:10px 0 6px}
.gg-cd-blk{display:flex;gap:2px;flex:var(--n) 1 0;min-width:0}
.gg-cd-w{flex:1;height:26px;border-radius:2px!important;min-width:0}
.gg-cd-w--base,.gg-cd-key .gg-cd-w--base{background:var(--gg-color-sand)}
.gg-cd-w--build,.gg-cd-key .gg-cd-w--build{background:var(--cd-none)}
.gg-cd-w--specific,.gg-cd-key .gg-cd-w--specific{background:var(--cd-ink)}
.gg-cd-w--taper,.gg-cd-key .gg-cd-w--taper{background:var(--cd-ink3)}
.gg-cd-weeks .gg-cd-w--dress{box-shadow:0 0 0 2px var(--cd-card),0 0 0 3px var(--cd-gold-d)!important}
.gg-cd-key{display:flex;flex-wrap:wrap;gap:4px 12px;font:400 10.5px/1.4 var(--gg-font-data);color:var(--cd-ink3)}
.gg-cd-key i{display:inline-block;width:10px;height:10px;border-radius:2px!important;vertical-align:-1px;margin-right:5px}
.gg-cd-key i.gg-cd-w--dress{box-shadow:inset 0 0 0 2px var(--cd-gold-d)!important}
.gg-cd-fine{font:400 11.5px/1.5 var(--gg-font-data);color:var(--cd-ink3);margin:6px 0 0}
.gg-cd-buy{display:block;text-align:center;text-decoration:none;font:700 12.5px/1 var(--gg-font-data);letter-spacing:.08em;text-transform:uppercase;padding:15px;border-radius:8px!important;background:var(--cd-ink);color:var(--cd-card)!important}
.gg-cd-buy:hover{background:var(--cd-ink2)}
.gg-cd-coach{font:400 12px/1.4 var(--gg-font-editorial);color:var(--cd-ink2)}
.gg-cd-route{position:sticky;top:var(--gg-header-height,0px);z-index:20;display:flex;align-items:center;gap:22px;height:70px;margin-top:28px;background:var(--gg-color-warm-paper);box-shadow:0 0 0 100vmax var(--gg-color-warm-paper)!important;clip-path:inset(0 -100vmax -1px);border-bottom:1px solid var(--cd-line)}
.gg-cd-count{font:700 11px/1.3 var(--gg-font-data);color:var(--cd-ink3);white-space:nowrap}
.gg-cd-track{position:relative;flex:1;height:70px;min-width:0}
.gg-cd-track::before{content:"";position:absolute;left:0;right:0;top:22px;height:2px;background:var(--cd-line)}
.gg-cd-done{position:absolute;left:0;top:22px;height:2px;background:var(--cd-ink);width:0}
.gg-cd-track a{position:absolute;top:16px;transform:translateX(-50%);text-decoration:none;text-align:center}
.gg-cd-track a i{display:block;width:14px;height:14px;margin:0 auto;background:var(--gg-color-warm-paper);border:2px solid var(--cd-ink3)}
.gg-cd-track a span{display:block;margin-top:7px;font:700 10.5px/1 var(--gg-font-data);letter-spacing:.04em;color:var(--cd-ink2);white-space:nowrap}
.gg-cd-track a small{display:block;margin-top:3px;font:400 9.5px/1 var(--gg-font-data);color:var(--cd-ink3);white-space:nowrap}
.gg-cd-track a.gg-cd-past i{background:var(--cd-ink);border-color:var(--cd-ink)}
.gg-cd-rider-dot{position:absolute;top:15px;left:0;width:16px;height:16px;border-radius:50%!important;background:var(--cd-gold-d);transform:translateX(-50%);box-shadow:0 0 0 3px var(--gg-color-warm-paper)!important;pointer-events:none}
.gg-cd-cta{font:700 12px/1 var(--gg-font-data);letter-spacing:.08em;text-transform:uppercase;background:var(--cd-ink);color:var(--cd-card)!important;text-decoration:none;padding:12px 14px;border-radius:8px!important;white-space:nowrap}
.gg-cd-page .gg-cd-grid::before{content:none;display:none}
.gg-cd-page .gg-cd-grid{margin-top:0;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px;padding:22px 0 48px;counter-reset:cd}
.gg-cd-grid>*{grid-column:1/-1;min-width:0}
.gg-cd-grid>.gg-cd-half{grid-column:auto}
.gg-cd-grid>.gg-section,.gg-cd-grid>#finish-time,.gg-cd-grid>.gg-latest,.gg-cd-grid>.gg-racer-reviews{background:var(--cd-card);border:0;border-radius:var(--cd-r)!important;box-shadow:var(--cd-shadow)!important;margin:0;scroll-margin-top:calc(var(--gg-header-height,56px) + 84px)}
.gg-cd-grid>.gg-section{counter-increment:cd}
.gg-cd-page .gg-cd-grid>.gg-racer-reviews,.gg-cd-page .gg-cd-grid>.gg-latest{background:var(--cd-card);padding:22px 28px;border:0;grid-row:auto}
.gg-cd-grid>.gg-section>.gg-section-header{background:transparent;border:0;padding:26px 28px 0;display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px;color:var(--cd-ink)}
.gg-cd-grid>.gg-section>.gg-section-header::before{content:counter(cd,decimal-leading-zero);font:800 12px/1 var(--gg-font-data);color:var(--cd-gold-d)}
.gg-cd-grid>.gg-section .gg-section-kicker{display:none}
.gg-cd-grid .gg-cd-sub{font:700 11px/1.4 var(--gg-font-data);letter-spacing:.14em;text-transform:uppercase;color:var(--cd-ink3)}
.gg-cd-grid>.gg-section>.gg-section-header .gg-section-title{flex-basis:100%;font:700 clamp(22px,2.4vw,30px)/1.15 var(--gg-font-editorial);letter-spacing:-.012em;color:var(--cd-ink);margin:6px 0 0}
.gg-cd-grid>.gg-section>.gg-section-body{padding:14px 28px 26px}
.gg-cd-cite{font:700 10px/1 var(--gg-font-data);color:var(--gg-color-teal);text-decoration:none;vertical-align:super}
.gg-cd-rgroup+.gg-cd-rgroup{margin-top:22px}
.gg-cd-rgroup h3{font:700 12px/1.4 var(--gg-font-data);letter-spacing:.12em;text-transform:uppercase;color:var(--cd-ink2);margin:0 0 6px}
.gg-cd-rgroup h3 span{color:var(--cd-ink3)}
.gg-cd-rverdict{font:600 17px/1.45 var(--gg-font-editorial);margin:0 0 8px;max-width:72ch}
.gg-cd-rt{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 28px}
.gg-cd-r{display:grid;grid-template-columns:128px 64px minmax(0,1fr);gap:10px;align-items:start;padding:10px 0;border-top:1px solid var(--cd-line);font:400 14.5px/1.5 var(--gg-font-editorial);color:var(--cd-ink2)}
.gg-cd-r b{font:700 12px/1.5 var(--gg-font-data);color:var(--cd-ink)}
.gg-cd-pp{display:grid;grid-template-columns:repeat(5,1fr);gap:2px;padding-top:5px}
.gg-cd-pp i{height:8px;border-radius:2px!important;background:var(--cd-well)}
.gg-cd-pp i.on{background:var(--cd-ink)}
.gg-cd-cfig{display:grid;grid-template-columns:minmax(0,200px) minmax(0,1fr);gap:28px;align-items:end;margin:8px 0 18px}
.gg-cd-cfig--one{grid-template-columns:minmax(0,1fr)}
.gg-cd-cfig--one .gg-cd-cfig-map{max-width:240px}
.gg-cd-marks{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:18px;margin:0 0 20px}
.gg-cd-marks div{border-top:2px solid var(--cd-ink);padding-top:10px;font:400 15px/1.45 var(--gg-font-editorial);color:var(--cd-ink2)}
.gg-cd-marks b{display:block;font:800 24px/1 var(--gg-font-data);color:var(--cd-ink);margin-bottom:6px}
.gg-cd-marks strong{display:block;color:var(--cd-ink)}
.gg-cd-route-link{font:400 12px/1.5 var(--gg-font-data);margin:0 0 18px}
.gg-cd-hrs{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:2px;align-items:end;height:96px;margin-top:10px}
.gg-cd-hrs i{border-radius:2px 2px 0 0!important;background:var(--cd-ink3)}
.gg-cd-hrs i.gg-cd-hot{background:var(--cd-ink)}
.gg-cd-hrs-axis{display:flex;justify-content:space-between;font:400 10px/1 var(--gg-font-data);color:var(--cd-ink3);margin-top:6px}
.gg-cd-yesno{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:6px}
.gg-cd-yn h3{font:700 11px/1.4 var(--gg-font-data);letter-spacing:.12em;text-transform:uppercase;margin:0 0 6px;color:var(--cd-ink2)}
.gg-cd-yn ul{margin:0;padding-left:18px;font:400 14.5px/1.5 var(--gg-font-editorial)}
.gg-cd-alts{margin-top:14px;font:400 15px/1.5 var(--gg-font-editorial)}
.gg-cd-grid .gg-field-video-grid{grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}
.gg-cd-grid .gg-lite-youtube{aspect-ratio:16/9;height:auto;border-radius:8px!important;overflow:hidden}
.gg-cd-grid .gg-lite-youtube-thumb{width:100%;height:100%;object-fit:cover}
.gg-cd-page :focus-visible{outline:2px solid var(--gg-color-teal);outline-offset:3px}
@media (max-width:1060px){.gg-cd-fold,.gg-cd-fold--2{grid-template-columns:1fr 1fr}.gg-cd-fold--3 .gg-cd-yours{grid-column:1/-1}}
@media (max-width:900px){
  .gg-cd-hero{padding:28px 0 76px}
  .gg-cd-hero-top{grid-template-columns:minmax(0,1fr);gap:16px}
  .gg-cd-big{text-align:left;display:flex;flex-wrap:wrap;align-items:flex-end;gap:6px 14px}
  .gg-cd-big b{font-size:80px}
  .gg-cd-big span{margin-top:0}
  .gg-cd-rider{flex-basis:100%}
  .gg-cd-prof--hero svg{height:140px}
  .gg-cd-prof--hero .gg-cd-prof-marks,.gg-cd-prof--hero .gg-cd-prof-mark{display:none}
  .gg-cd-count,.gg-cd-cta{display:none}
  .gg-cd-route{height:56px}
  .gg-cd-track{height:56px}
  .gg-cd-track a span,.gg-cd-track a small{display:none}
  .gg-cd-track a.gg-cd-cur span{display:block;position:absolute;left:50%;transform:translateX(-50%)}
  .gg-cd-cfig{grid-template-columns:minmax(0,1fr)}
  .gg-cd-cfig-map{max-width:180px}
}
@media (max-width:720px){
  .gg-cd-fold,.gg-cd-fold--2,.gg-cd-grid,.gg-cd-rt,.gg-cd-yesno{grid-template-columns:minmax(0,1fr)}
  .gg-cd-card{padding:18px}
  .gg-cd-grid>.gg-section>.gg-section-header{padding:18px 18px 0}
  .gg-cd-grid>.gg-section>.gg-section-body{padding:12px 18px 20px}
  .gg-cd-dg{grid-template-columns:repeat(7,minmax(0,1fr));row-gap:10px}
  .gg-cd-r{grid-template-columns:110px 56px}
  .gg-cd-r span{grid-column:1/-1}
}
'''


def get_js() -> str:
    """Route bar rider dot, the plan strip recount from today, and the
    estimator hand-off to the finish-time planner. textContent/createElement only."""
    return r'''
(function() {
  var page = document.querySelector('.gg-cd-page');
  if (!page) return;
  // Plan strip: weeks from today to race day, ceil(days / 7), in 4-week blocks.
  var weeks = page.querySelector('[data-cd-weeks]');
  if (weeks) {
    var race = new Date(weeks.getAttribute('data-race') + 'T00:00:00');
    var today = new Date(); today.setHours(0, 0, 0, 0);
    var n = Math.ceil(Math.round((race - today) / 864e5) / 7);
    var plan = weeks.closest('.gg-cd-plan');
    if (!(n > 0)) {
      if (plan) plan.hidden = true;
    } else {
      var taper = Math.min(2, n), spec = Math.min(8, n - taper);
      var build = Math.min(8, n - taper - spec), base = n - taper - spec - build;
      var dress = n > 4 ? n - 3 : 0;
      while (weeks.firstChild) weeks.removeChild(weeks.firstChild);
      var blk = null;
      for (var w = 1; w <= n; w++) {
        if ((w - 1) % 4 === 0) { blk = document.createElement('span'); blk.className = 'gg-cd-blk'; weeks.appendChild(blk); }
        var phase = w > n - taper ? 'taper' : w > n - taper - spec ? 'specific' : w > base ? 'build' : 'base';
        var i = document.createElement('i');
        i.className = 'gg-cd-w gg-cd-w--' + phase + (w === dress ? ' gg-cd-w--dress' : '');
        i.title = 'Week ' + w;
        blk.appendChild(i);
      }
      Array.prototype.forEach.call(weeks.children, function(b) { b.style.setProperty('--n', b.children.length); });
      var runway = page.querySelector('[data-cd-runway]');
      if (runway) runway.textContent = n + (n === 1 ? ' week' : ' weeks') + ' to the start line';
      weeks.setAttribute('aria-label', n + ' training weeks in ' + Math.ceil(n / 4) + ' four-week blocks: ' +
        base + ' base, ' + build + ' build, ' + spec + ' race-specific, ' + taper + ' taper');
    }
  }
  // Route bar: the rider dot follows the reader through the section cards.
  var track = page.querySelector('[data-cd-track]');
  if (track) {
    var rider = track.querySelector('[data-cd-rider]'), done = track.querySelector('[data-cd-done]');
    var stops = Array.prototype.slice.call(track.querySelectorAll('a[data-cd-stop]'));
    var targets = stops.map(function(a) { return document.getElementById(a.getAttribute('data-cd-stop')); });
    var ticking = false;
    function update() {
      ticking = false;
      var line = window.innerHeight * 0.4, cur = -1, frac = 0;
      targets.forEach(function(t, i) {
        if (!t) return;
        var r = t.getBoundingClientRect();
        if (r.top < line) { cur = i; frac = Math.max(0, Math.min(1, (line - r.top) / Math.max(1, r.height))); }
      });
      var pos = function(i) { return parseFloat(stops[i].style.left) || 0; };
      var left = 0;
      if (cur >= 0) {
        var next = cur + 1 < stops.length ? pos(cur + 1) : 100;
        left = pos(cur) + (next - pos(cur)) * frac;
      }
      rider.style.left = left + '%';
      done.style.width = left + '%';
      stops.forEach(function(a, i) {
        a.classList.toggle('gg-cd-past', cur >= 0 && i <= cur);
        a.classList.toggle('gg-cd-cur', i === Math.max(cur, 0));
      });
    }
    function onScroll() { if (!ticking) { ticking = true; window.requestAnimationFrame(update); } }
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    update();
  }
  // Estimator: hand FTP and weight to the finish-time planner and run it.
  var est = page.querySelector('[data-cd-estimator]');
  var planner = document.getElementById('finish-time');
  if (est && planner) {
    est.addEventListener('submit', function(e) {
      e.preventDefault();
      var form = planner.querySelector('form');
      ['ftp', 'kg'].forEach(function(name) {
        var from = est.querySelector('input[name="' + name + '"]');
        var to = form && form.querySelector('input[name="' + name + '"]');
        if (from && to && from.value) {
          // The estimator asks for pounds; the planner may be set to kg.
          var unit = planner.querySelector('[data-units][aria-pressed="true"]');
          var metric = unit && unit.getAttribute('data-units') === 'met';
          var lb = parseFloat(from.value);
          to.value = (name === 'kg' && metric && !isNaN(lb))
            ? String(Math.round(lb * 0.45359237 * 10) / 10) : from.value;
          to.dispatchEvent(new Event('input', { bubbles: true }));
        }
      });
      planner.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (form && typeof form.requestSubmit === 'function') form.requestSubmit();
    });
  }
})();
'''
