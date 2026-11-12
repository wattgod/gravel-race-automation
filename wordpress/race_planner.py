"""Public finish-time planner on race pages.

A race page gets the planner only when ``data/planner/status.json`` marks the
race ``eligible`` or ``flagged`` and its public course exists in
``data/planner/courses/``. Both come from ``scripts/import_planner_bundles.py``,
which reads the planner research workspace's eligibility check. A held race,
or one with no course, gets nothing: the page is unchanged. No race list is
hard-coded here.

The page runs the frozen planner engine (``wordpress/planner/engine7.js``,
byte-identical copy) in a Web Worker, so its globals never meet the page's
scripts. Everything visible is built with ``textContent``/``createElement``.

What the page says (LAUNCH_DECISIONS, 2026-11-12):
- an *estimate* of riding time, shown as a range, with no accuracy figure;
- weather labelled as a past race day's weather, never a forecast;
- the course edition next to the result;
- the effort default (level-and-duration curves) shown as an editable value;
- improvement rows one at a time, never summed; Fitness size chosen by the rider;
- the plan button goes to the existing Custom Training Plan checkout.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from brand_tokens import SITE_BASE_URL
from pricing import PRICE_PER_WEEK, RACE_PLAN

REPO = Path(__file__).resolve().parent.parent
PLANNER_DIR = REPO / "data" / "planner"
STATUS_PATH = PLANNER_DIR / "status.json"
COURSES_DIR = PLANNER_DIR / "courses"
GEAR_PATH = PLANNER_DIR / "gear.json"
JS_DIR = Path(__file__).resolve().parent / "planner"
ENGINE_JS = JS_DIR / "engine7.js"
CORE_JS = JS_DIR / "gg-planner-core.js"
WORKER_JS = JS_DIR / "gg-planner-worker.js"
UI_JS = JS_DIR / "gg-planner.js"

ASSET_DIR = "planner"            # under the race output's assets/
ASSET_URL = "/race/assets/planner"
SHOWN = ("eligible", "flagged")
PLAN_URL = f"{SITE_BASE_URL}/training-plans/start/"
EVENT_RESULT = "planner_result_shown"
EVENT_CTA = "plan_cta_click"

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _esc(text) -> str:
    return html.escape(str(text), quote=True)


def _safe_json(obj) -> str:
    """JSON safe inside a <script> element: no </script>, no <!--."""
    return (json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


@lru_cache(maxsize=1)
def _status() -> dict:
    if not STATUS_PATH.exists():
        return {}
    return json.loads(STATUS_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _gear() -> dict | None:
    return json.loads(GEAR_PATH.read_text(encoding="utf-8")) if GEAR_PATH.exists() else None


def duration_brackets() -> list:
    """GGC's fuelling brackets, read from pipeline/nutrition.py (the one source)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("ggc_nutrition", REPO / "pipeline" / "nutrition.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return [list(b) for b in mod.DURATION_BRACKETS]


def _hashed(path: Path) -> str:
    data = path.read_bytes()
    return f"{path.stem}.{hashlib.md5(data).hexdigest()[:8]}{path.suffix}"


def course_path(slug: str) -> Path:
    return COURSES_DIR / f"{slug}.json"


def planner_status(slug: str) -> dict | None:
    """The race's imported status entry, or None when it has none."""
    if not isinstance(slug, str) or not _SLUG.fullmatch(slug):
        return None
    return (_status().get("races") or {}).get(slug)


def planner_shown(slug: str) -> bool:
    entry = planner_status(slug)
    return bool(entry and entry.get("status") in SHOWN and course_path(slug).exists() and _gear())


def asset_names() -> dict:
    """Content-hashed file names, computed without writing anything."""
    return {
        "engine": _hashed(ENGINE_JS),
        "core": _hashed(CORE_JS),
        "worker": _hashed(WORKER_JS),
        "ui": _hashed(UI_JS),
    }


def _css_name() -> str:
    css = get_race_planner_css().encode()
    return f"gg-planner.{hashlib.md5(css).hexdigest()[:8]}.css"


def planner_head_tags(inline: bool = False) -> str:
    """Planner styles, only on pages that carry the planner. Inline when the
    page is built without external assets (tests, single-file previews)."""
    if inline:
        return f"<style>{get_race_planner_css()}</style>"
    return f'<link rel="stylesheet" href="{ASSET_URL}/{_css_name()}">'


def write_planner_assets(output_dir: Path, slugs) -> list[str]:
    """Write the planner's files for the races being generated into
    ``<output>/assets/planner/``, content-hashed: the shared scripts and
    stylesheet plus each shown race's course. Nothing is written when none of
    ``slugs`` shows the planner, so other pages' output is unchanged. Only
    older hashes of the files written here are removed; other races' courses
    in a shared output folder are left alone. Returns the written names."""
    shown = [s for s in slugs if planner_shown(s)]
    if not shown:
        return []
    dst = Path(output_dir) / "assets" / ASSET_DIR
    dst.mkdir(parents=True, exist_ok=True)
    files = {_hashed(src): src.read_bytes() for src in (ENGINE_JS, CORE_JS, WORKER_JS, UI_JS)}
    files.update({_hashed(course_path(s)): course_path(s).read_bytes() for s in shown})
    files[_css_name()] = get_race_planner_css().encode("utf-8")
    for name, data in files.items():
        stem, suffix = name.split(".", 1)[0], Path(name).suffix
        for old in dst.glob(f"{stem}.*{suffix}"):
            if old.name != name and re.fullmatch(re.escape(stem) + r"\.[0-9a-f]{8}" + re.escape(suffix), old.name):
                old.unlink()
        (dst / name).write_bytes(data)
    return sorted(files)


def _course_summary(slug: str) -> dict:
    """The few course facts the page prints before the course file loads."""
    course = json.loads(course_path(slug).read_text(encoding="utf-8"))
    route, target = course["route"], course["target_edition"]
    ed = course["weather"]["editions"][0]
    return {
        "route_name": route["name"],
        "route_url": route["source"],
        "edition_year": route.get("edition_year"),
        "updated_year": route.get("updated_year"),
        "distance_m": route["distance_m"],
        "target_year": target.get("year"),
        "target_date": target.get("date"),
        "weather_date": ed["date"],
        "weather_start": ed["start_local"],
    }


def _edition_line(summary: dict, flags: list[dict]) -> str:
    """'2025 route' or the flag text when the edition is not confirmed."""
    for flag in flags:
        if flag["kind"] == "edition":
            return flag["text"]
    return f"{summary['edition_year']} route (Ride with GPS)"


def _target_line(summary: dict, flags: list[dict]) -> str:
    """'The 2027 route isn't published yet.' when the shown route is older."""
    if any(f["kind"] == "edition" for f in flags):
        return ""
    year, target = summary["edition_year"], summary["target_year"]
    if isinstance(year, int) and isinstance(target, int) and target > year:
        return f"The {target} route isn't published yet."
    return ""


def _weather_line(summary: dict) -> str:
    d = date.fromisoformat(summary["weather_date"])
    return (f"Weather from the {d.year} race day ({d.strftime('%B')} {d.day}, {d.year}, "
            f"{summary['weather_start']} start), not a forecast.")


def planner_config(rd: dict, show_offer: bool) -> dict | None:
    slug = rd.get("slug")
    if not planner_shown(slug):
        return None
    entry = planner_status(slug)
    flags = entry.get("flags", [])
    kinds = {f["kind"] for f in flags}
    summary = _course_summary(slug)
    names = asset_names()
    gear = _gear()
    return {
        "slug": slug,
        "race": str(rd.get("name") or slug),
        "route_url": summary["route_url"],
        "status": entry["status"],
        "course_url": f"{ASSET_URL}/{_hashed(course_path(slug))}",
        "worker_url": f"{ASSET_URL}/{names['worker']}",
        "engine_url": f"{ASSET_URL}/{names['engine']}",
        "core_url": f"{ASSET_URL}/{names['core']}",
        "edition_line": _edition_line(summary, flags),
        "target_line": _target_line(summary, flags),
        "edition_short": (f"{summary['edition_year']} route" if summary["edition_year"]
                          and not any(f["kind"] == "edition" for f in flags) else "route edition not confirmed"),
        "weather_line": _weather_line(summary),
        "distance_m": summary["distance_m"],
        "notes": [f["text"] for f in flags if f["kind"] == "climbing"],
        "visitor_sets_effort": "visitor_sets_effort" in kinds,
        "brackets": duration_brackets(),
        "bikes": [{"id": b["id"], "label": b["label"], "kg": b["kg"]} for b in gear["bikes"]],
        "bottle": {"ml": gear["bottle"]["ml"], "kg": round((gear["bottle"]["ml"] + gear["bottle"]["g"]) / 1000, 3)},
        "offer": ({
            "href": f"{PLAN_URL}?race={slug}&src=race_planner",
            "price": f"{PRICE_PER_WEEK} / week",
            "includes": list(RACE_PLAN["inclusions"]),
        } if show_offer else None),
        "events": {"result": EVENT_RESULT, "cta": EVENT_CTA},
    }


def _gear_sources_html() -> str:
    gear = _gear()
    parts = []
    for b in gear["bikes"]:
        models = ", ".join(
            f'<a href="{_esc(m["url"])}" rel="noopener" target="_blank">{_esc(m["model"])}</a> {m["kg"]:.2f} kg'
            for m in b["models"])
        parts.append(f"<li><b>{_esc(b['label'])}</b>, average {b['kg']:.2f} kg: {models}.</li>")
    bt = gear["bottle"]
    parts.append(f'<li><b>Bottles</b>: <a href="{_esc(bt["url"])}" rel="noopener" target="_blank">'
                 f'{_esc(bt["model"])}</a>, {bt["g"]} g empty, full of water.</li>')
    return f'<ul class="gg-planner-sources">{"".join(parts)}</ul><p>Weights as listed on the makers\' pages, checked {_esc(gear["checked"])}.</p>'


def build_race_planner(rd: dict, show_offer: bool = True) -> str:
    """The planner section, or '' when this race has no eligible course."""
    cfg = planner_config(rd, show_offer)
    if cfg is None:
        return ""
    race = _esc(cfg["race"])
    dist_mi = cfg["distance_m"] / 1609.344
    notes = "".join(f'<p class="gg-planner-flag">{_esc(n[0].upper() + n[1:])}.</p>' for n in cfg["notes"])
    hours = "".join(
        f'<label class="gg-planner-chip"><input type="radio" name="hours" value="{h}"> {h.replace("-", "–")} h</label>'
        for h in ("3-5", "5-7", "7-10", "10-12", "12-15", "15+"))
    groups = "".join(
        f'<label class="gg-planner-chip"><input type="radio" name="group" value="{v}"> {t}</label>'
        for v, t in (("solo", "On my own"), ("some", "In a group some of the day"), ("most", "In a group most of the day")))
    bikes = "".join(
        f'<label class="gg-planner-chip"><input type="radio" name="bike" value="{_esc(b["id"])}"'
        f'{" checked" if b["id"] == "all_round_carbon" else ""}> {_esc(b["label"])}</label>'
        for b in cfg["bikes"])
    levels = "".join(
        f'<label class="gg-planner-chip"><input type="radio" name="level" value="{v}"> {t}</label>'
        for v, t in (("", "From my hours"), ("beginner", "Beginner"), ("intermediate", "Intermediate"),
                     ("advanced", "Advanced"), ("elite", "Elite")))
    effort_note = ("This course has no default effort: type the effort (IF) you held in a race of a similar length."
                   if cfg["visitor_sets_effort"] else
                   "Blank uses Gravel God's default for your level and riding time. Type your own to override it.")
    return f'''<section id="finish-time" class="gg-planner" aria-labelledby="gg-planner-title">
  <div class="gg-planner-head">
    <span class="gg-planner-kicker">Free · no account</span>
    <h2 id="gg-planner-title">How long will {race} take you?</h2>
    <p class="gg-planner-course">Course: {_esc(cfg["edition_line"])}, {dist_mi:.1f} mi (<a href="{_esc(cfg["route_url"])}" rel="noopener" target="_blank">route</a>).{(" " + _esc(cfg["target_line"])) if cfg["target_line"] else ""} {_esc(cfg["weather_line"])}</p>
    {notes}
  </div>
  <form class="gg-planner-form" novalidate>
    <div class="gg-planner-row">
      <label class="gg-planner-field" data-power="ftp"><span>Your FTP</span><span class="gg-planner-in"><input name="ftp" inputmode="numeric" autocomplete="off" aria-label="FTP in watts"><em>W</em></span></label>
      <label class="gg-planner-field"><span>Your weight</span><span class="gg-planner-in"><input name="kg" inputmode="decimal" autocomplete="off" aria-label="Your weight"><em data-unit="weight">lb</em></span></label>
    </div>
    <div class="gg-planner-band" hidden>
      <div class="gg-planner-chips" role="radiogroup" aria-label="Table"><label class="gg-planner-chip"><input type="radio" name="sex" value="m" checked> Men's table</label><label class="gg-planner-chip"><input type="radio" name="sex" value="f"> Women's table</label></div>
      <div class="gg-planner-chips" role="radiogroup" aria-label="Power band"><label class="gg-planner-chip"><input type="radio" name="band" value="Fair"> Fair</label><label class="gg-planner-chip"><input type="radio" name="band" value="Good"> Good</label><label class="gg-planner-chip"><input type="radio" name="band" value="Excellent"> Excellent</label></div>
      <small>Allen and Coggan FTP ratings in W/kg, as printed in Garmin's Edge 530 manual. The middle of the band sets your time; its ends widen the range.</small>
    </div>
    <label class="gg-planner-toggle"><input type="checkbox" name="noftp"> I don't know my FTP</label>
    <button type="submit" class="gg-planner-go">See my finish time &rarr;</button>
    <div class="gg-planner-more" hidden>
      <fieldset class="gg-planner-field"><legend>Hours a week you can train</legend><div class="gg-planner-chips">{hours}</div><small>Sets your level, and your level sets your default effort.</small></fieldset>
      <fieldset class="gg-planner-field"><legend>Who will you ride with?</legend><div class="gg-planner-chips">{groups}</div><small>Inside a group you have about a third less drag on flat road (Broker, Kyle and Burke 1999). Climbs and descents get no shelter.</small></fieldset>
      <fieldset class="gg-planner-field"><legend>Your bike</legend><div class="gg-planner-chips">{bikes}</div>
        <label class="gg-planner-inline">Bottles of {cfg["bottle"]["ml"]} ml <input name="bottles" inputmode="numeric" value="2" aria-label="Number of full bottles" size="2"></label>
        <details class="gg-planner-info"><summary>Where the weights come from</summary>{_gear_sources_html()}</details></fieldset>
      <div class="gg-planner-row">
        <label class="gg-planner-field"><span>Time stopped, all day (optional)</span><span class="gg-planner-in"><input name="stops" inputmode="numeric" autocomplete="off" aria-label="Minutes stopped"><em>min</em></span><small>Blank shows riding time only.</small></label>
        <label class="gg-planner-field"><span>Carbs an hour on long rides (optional)</span><span class="gg-planner-in"><input name="carbs" inputmode="numeric" autocomplete="off" aria-label="Carbs per hour in grams"><em>g/h</em></span><small>Sizes your gut-training row.</small></label>
      </div>
      <fieldset class="gg-planner-field"><legend>Your level (optional)</legend><div class="gg-planner-chips">{levels}</div></fieldset>
      <label class="gg-planner-field"><span>Effort (IF){" " if cfg["visitor_sets_effort"] else " (optional)"}</span><span class="gg-planner-in"><input name="if" inputmode="decimal" autocomplete="off" aria-label="Effort as intensity factor"><em>IF</em></span><small>{effort_note} IF is normalized power divided by FTP.</small></label>
      <label class="gg-planner-toggle"><input type="checkbox" name="heat"> I have trained in the heat this season</label>
      <div class="gg-planner-units" role="group" aria-label="Units"><button type="button" data-units="imp">lb · mi</button><button type="button" data-units="met">kg · km</button></div>
    </div>
    <p class="gg-planner-need" aria-live="polite"></p>
  </form>
  <div class="gg-planner-out" aria-live="polite" hidden></div>
  <noscript><p>The finish-time estimate runs in your browser and needs JavaScript.</p></noscript>
  <script type="application/json" class="gg-planner-config">{_safe_json(cfg)}</script>
</section>'''


def planner_script_tag() -> str:
    return f'<script src="{ASSET_URL}/{asset_names()["ui"]}" defer></script>'


def get_race_planner_css() -> str:
    p = ".gg-neo-brutalist-page .gg-planner"
    return f'''
{p} {{ margin: var(--gg-spacing-lg) 0; padding: var(--gg-spacing-lg); border: var(--gg-border-standard); border-top: 6px solid var(--gg-color-teal); background: var(--gg-color-warm-paper); color: var(--gg-color-dark-brown); scroll-margin-top: calc(var(--gg-header-height, 80px) + var(--gg-spacing-md)); }}
{p} h2 {{ margin: var(--gg-spacing-2xs) 0 var(--gg-spacing-xs); font-family: var(--gg-font-editorial); line-height: 1.15; }}
{p} h3 {{ margin: 0 0 var(--gg-spacing-xs); font-family: var(--gg-font-data); font-size: var(--gg-font-size-sm); letter-spacing: .08em; text-transform: uppercase; }}
{p}-kicker, {p}-eyebrow {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); letter-spacing: .12em; text-transform: uppercase; }}
{p}-course, {p}-flag, {p} small, {p}-fine {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); line-height: 1.5; }}
{p}-flag {{ border-left: 3px solid var(--gg-color-gold); padding-left: var(--gg-spacing-xs); }}
{p}-form {{ display: grid; gap: var(--gg-spacing-sm); margin-top: var(--gg-spacing-md); }}
{p}-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: var(--gg-spacing-sm); }}
{p}-field {{ display: grid; gap: var(--gg-spacing-2xs); min-width: 0; border: 0; padding: 0; margin: 0; font-family: var(--gg-font-data); }}
{p}-field > span:first-child, {p}-field legend {{ font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-bold); letter-spacing: .08em; text-transform: uppercase; }}
{p}-in {{ display: flex; align-items: center; border: var(--gg-border-standard); background: var(--gg-color-white); min-height: 44px; }}
{p}-in input {{ flex: 1; min-width: 0; border: 0; padding: var(--gg-spacing-xs); font: inherit; font-size: var(--gg-font-size-base); background: transparent; color: inherit; }}
{p}-in em {{ padding: 0 var(--gg-spacing-xs); font-style: normal; font-size: var(--gg-font-size-xs); }}
{p}-chips {{ display: flex; flex-wrap: wrap; gap: var(--gg-spacing-2xs); }}
{p}-chip {{ display: inline-flex; align-items: center; gap: 4px; min-height: 40px; padding: 0 var(--gg-spacing-xs); border: 2px solid var(--gg-color-dark-brown); font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); cursor: pointer; background: var(--gg-color-white); }}
{p}-chip:has(input:checked) {{ background: var(--gg-color-dark-brown); color: var(--gg-color-warm-paper); }}
{p}-chip input {{ accent-color: var(--gg-color-teal); }}
{p}-inline {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); }}
{p}-inline input {{ width: 3em; min-height: 36px; border: 2px solid var(--gg-color-dark-brown); font: inherit; text-align: center; }}
{p}-toggle {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); display: flex; gap: var(--gg-spacing-2xs); align-items: center; min-height: 32px; }}
{p}-go, {p}-cta {{ display: block; width: 100%; min-height: 48px; border: 3px solid var(--gg-color-dark-brown); background: var(--gg-color-gold); color: var(--gg-color-dark-brown); font-family: var(--gg-font-data); font-weight: var(--gg-font-weight-bold); letter-spacing: .1em; text-transform: uppercase; text-align: center; text-decoration: none; cursor: pointer; padding: var(--gg-spacing-sm); }}
{p}-more {{ display: grid; gap: var(--gg-spacing-md); }}
{p}-more[hidden], {p}-band[hidden], {p}-out[hidden] {{ display: none; }}
{p}-edit {{ justify-self: start; min-height: 40px; padding: 0 var(--gg-spacing-sm); border: 2px solid var(--gg-color-dark-brown); background: var(--gg-color-white); color: var(--gg-color-dark-brown); font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); text-transform: uppercase; letter-spacing: .08em; cursor: pointer; }}
{p}-units button {{ min-height: 36px; border: 2px solid var(--gg-color-dark-brown); background: var(--gg-color-white); font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); cursor: pointer; }}
{p}-units button[aria-pressed="true"] {{ background: var(--gg-color-dark-brown); color: var(--gg-color-warm-paper); }}
{p}-need {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); margin: 0; }}
{p}-out {{ display: grid; gap: var(--gg-spacing-md); margin-top: var(--gg-spacing-md); }}
{p}-card {{ border: 3px solid var(--gg-color-dark-brown); background: var(--gg-color-white); padding: var(--gg-spacing-md); display: grid; gap: var(--gg-spacing-xs); min-width: 0; }}
{p}-big {{ font-family: var(--gg-font-editorial); font-size: clamp(2.2rem, 9vw, 3.4rem); font-weight: 700; line-height: 1; color: var(--gg-color-gold); font-variant-numeric: tabular-nums; }}
{p}-fail {{ border-left: 6px solid var(--gg-color-gold); }}
{p}-kv {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: var(--gg-spacing-xs); font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); text-transform: uppercase; letter-spacing: .05em; }}
{p}-kv b {{ display: block; font-size: var(--gg-font-size-base); letter-spacing: 0; text-transform: none; }}
{p}-map {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 2fr); gap: var(--gg-spacing-sm); align-items: end; }}
{p}-map svg {{ width: 100%; height: auto; display: block; }}
{p}-route {{ fill: none; stroke: var(--gg-color-teal); stroke-width: 3; stroke-linejoin: round; }}
{p}-prof {{ fill: var(--gg-color-tan); stroke: var(--gg-color-dark-brown); stroke-width: 1; }}
{p}-dot {{ fill: var(--gg-color-gold); stroke: var(--gg-color-dark-brown); stroke-width: 2; }}
{p}-tick {{ stroke: var(--gg-color-dark-brown); stroke-width: 1; stroke-dasharray: 2 3; }}
{p}-tlabel {{ font-family: var(--gg-font-data); font-size: 11px; fill: var(--gg-color-dark-brown); }}
{p}-table {{ overflow-x: auto; }}
{p}-table table {{ border-collapse: collapse; width: 100%; font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); font-variant-numeric: tabular-nums; }}
{p}-table th, {p}-table td {{ border-bottom: 1px solid var(--gg-color-tan); padding: 6px 8px; text-align: left; white-space: nowrap; }}
{p}-rows {{ display: grid; gap: var(--gg-spacing-xs); }}
{p}-imp {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 4px var(--gg-spacing-sm); padding: var(--gg-spacing-xs) 0; border-bottom: 1px solid var(--gg-color-tan); font-family: var(--gg-font-data); font-size: var(--gg-font-size-sm); }}
{p}-imp b {{ font-variant-numeric: tabular-nums; text-align: right; }}
{p}-imp small, {p}-imp {p}-chips {{ grid-column: 1 / -1; }}
{p}-tag {{ display: inline-block; margin-left: 4px; padding: 0 4px; border: 1px solid var(--gg-color-dark-brown); font-size: 10px; text-transform: uppercase; letter-spacing: .06em; }}
{p}-offer ul {{ margin: 0; padding-left: 1.2em; font-size: var(--gg-font-size-sm); }}
{p}-info summary {{ cursor: pointer; font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); text-decoration: underline; }}
{p}-sources {{ font-size: var(--gg-font-size-xs); padding-left: 1.2em; }}
{p} :focus-visible {{ outline: 3px solid var(--gg-color-teal); outline-offset: 2px; }}
@media (max-width: 640px) {{ {p} {{ padding: var(--gg-spacing-md); }} {p}-map {{ grid-template-columns: 1fr; }} }}
@media (max-width: 420px) {{ {p}-row {{ grid-template-columns: 1fr; }} }}
'''
