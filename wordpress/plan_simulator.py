"""Contract-driven TrainingPeaks calendar simulator shared by plan pages."""

from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime
from typing import Any, Mapping


PREVIEW_ENDPOINT = os.environ.get(
    "PLAN_PREVIEW_ENDPOINT",
    "https://athlete-custom-training-plan-pipeline-production.up.railway.app/"
    "api/training-plan-preview",
)


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/")


def _race_date(race: Mapping[str, Any]) -> str:
    """Return a verified-looking ISO date from the race record, or blank."""
    vitals = race.get("vitals") or {}
    training = race.get("training_config") or {}
    candidates = (
        race.get("race_date"), training.get("race_date"),
        vitals.get("date_specific"), vitals.get("date"), race.get("date"),
    )
    for raw in candidates:
        value = str(raw or "")
        iso = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", value)
        if iso:
            try:
                return datetime.strptime(iso.group(0), "%Y-%m-%d").date().isoformat()
            except ValueError:
                pass
        for pattern in (r"\b(20\d{2})\s*:\s*([A-Za-z]+\s+\d{1,2})\b",
                        r"\b([A-Za-z]+\s+\d{1,2},\s*20\d{2})\b"):
            match = re.search(pattern, value)
            if not match:
                continue
            rendered = (f"{match.group(2)} {match.group(1)}"
                        if match.lastindex == 2 else match.group(1))
            try:
                return datetime.strptime(rendered, "%B %d %Y").date().isoformat()
            except ValueError:
                try:
                    return datetime.strptime(rendered, "%B %d, %Y").date().isoformat()
                except ValueError:
                    pass
    return ""


def _default_duration_hours(race: Mapping[str, Any], discipline: str) -> int:
    vitals = race.get("vitals") or {}
    if "ski" in discipline.lower():
        return 4
    distance = vitals.get("distance_mi")
    if distance is None and vitals.get("distance_km") is not None:
        try:
            distance = float(vitals["distance_km"]) * 0.621371
        except (TypeError, ValueError):
            distance = None
    try:
        miles = float(distance)
    except (TypeError, ValueError):
        return 8
    return 12 if miles >= 180 else 8 if miles >= 100 else 5


def _plan_modules(brand: str) -> list[dict[str, Any]]:
    """Public module catalog; paid add-ons can join without changing markup."""
    modules = [
        {
            "id": "strength",
            "name": "Race-specific strength",
            "status": "Included",
            "description": "Sets, reps, rest, and movement cues placed around your key sessions.",
        },
        {
            "id": "fueling",
            "name": "Fueling practice",
            "status": "Included",
            "description": "Session-level targets that turn race nutrition into something you rehearse.",
        },
    ]
    if brand in {"gravel_god", "gravelgod"}:
        modules.insert(0, {
            "id": "gravel_grit",
            "addon_id": "gravel_grit",
            "name": "Gravel Grit",
            "status": "Included",
            "description": "Four mental-skills notes built into the plan. It stays included—not an extra charge.",
        })
    return modules


def render_plan_simulator(*, brand: str, race: Mapping[str, Any],
                          demands: Mapping[str, Any], questionnaire_url: str,
                          heading: str, lede: str,
                          race_options: list[Mapping[str, Any]] | None = None) -> str:
    slug = str(race.get("slug") or "")
    vitals = race.get("vitals") or {}
    discipline = (vitals.get("discipline") or race.get("discipline")
                  or ("gravel" if brand == "gravel_god" else "road"))
    normalized_demands = {}
    for key, value in demands.items():
        try:
            normalized_demands[str(key)] = max(0, min(10, int(round(float(value)))))
        except (TypeError, ValueError):
            continue
    if not normalized_demands:
        normalized_demands = {"race_specificity": 5}

    config = {
        "schema_version": "training-plan-preview-request/v2",
        "brand": brand,
        "endpoint": PREVIEW_ENDPOINT,
        "plan_weeks": 21,
        "race_date": _race_date(race),
        "expected_duration_hours": _default_duration_hours(race, str(discipline)),
        "race": {
            "slug": slug,
            "name": str(race.get("name") or race.get("display_name") or slug),
            "discipline": str(discipline),
            "demands": normalized_demands,
        },
        "plan_modules": _plan_modules(brand),
    }
    normalized_options = []
    for option in race_options or []:
        option_vitals = option.get("vitals") or {}
        option_demands = option.get("demands") or {}
        cleaned_demands = {}
        for key, value in option_demands.items():
            try:
                cleaned_demands[str(key)] = max(
                    0, min(10, int(round(float(value)))))
            except (TypeError, ValueError):
                continue
        if not cleaned_demands:
            continue
        normalized_options.append({
            "slug": str(option.get("slug") or ""),
            "name": str(option.get("name") or option.get("display_name") or ""),
            "discipline": str(option_vitals.get("discipline")
                              or option.get("discipline") or discipline),
            "demands": cleaned_demands,
            "date": _race_date(option),
            "expected_duration_hours": _default_duration_hours(
                option, str(option_vitals.get("discipline")
                            or option.get("discipline") or discipline)),
        })
    if normalized_options:
        config["race_options"] = normalized_options
    config_id = f"tp-sim-config-{slug}"
    day_controls = "".join(
        f'''<label class="tp-sim-day-toggle"><input type="checkbox" value="{day.lower()}"'''
        f'''{" checked" if day in ("Tue", "Thu", "Sat", "Sun") else ""}>'''
        f'''<span>{day}</span></label>'''
        for day in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    )
    calendar_days = "".join(
        f'''<section class="tp-sim-day" data-calendar-day="{day}">'''
        f'''<header><strong>{day.title()}</strong><span>—</span></header>'''
        f'''<div class="tp-sim-day-sessions"><span class="tp-sim-loading-tile">Loading…</span></div></section>'''
        for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    )
    race_select = ""
    if normalized_options:
        choices = "".join(
            f'''<option value="{_esc(option["slug"])}"'''
            f'''{" selected" if option["slug"] == slug else ""}>'''
            f'''{_esc(option["name"])}</option>'''
            for option in normalized_options
        )
        race_select = f'''<label class="tp-sim-field tp-sim-race" for="tp-sim-race-{_esc(slug)}"><span>Goal race</span><select id="tp-sim-race-{_esc(slug)}" data-role="race">{choices}</select></label>'''
    module_cards = "".join(
        f'''<article class="tp-sim-module" data-plan-module="{_esc(module["id"])}"'''
        f'''{f' data-plan-addon="{_esc(module["addon_id"])}"' if module.get("addon_id") else ""}>'''
        f'''<span>{_esc(module["status"])}</span><strong>{_esc(module["name"])}</strong>'''
        f'''<p>{_esc(module["description"])}</p></article>'''
        for module in config["plan_modules"]
    )
    return f'''<section class="tp-sim" id="custom-plan-preview" data-training-preview data-config-id="{_esc(config_id)}">
  <p class="tp-sim-kicker">YOUR WEEK, INSIDE TRAININGPEAKS</p>
  <h2>{_esc(heading)}</h2>
  <p class="tp-sim-lede">{_esc(lede)}</p>
  <div class="tp-sim-shell">
    <form class="tp-sim-controls" data-role="controls">
      {race_select}
      <fieldset class="tp-sim-presets">
        <legend>Start with a real-life week</legend>
        <div>
          <button type="button" data-preset="starter-5" data-hours="5" data-days="tue,thu,sat" data-experience="beginner"><strong>5H</strong><span>3 days · newer</span></button>
          <button type="button" class="is-active" aria-pressed="true" data-preset="committed-8" data-hours="8" data-days="tue,thu,sat,sun" data-experience="intermediate"><strong>8H</strong><span>4 days · experienced</span></button>
          <button type="button" data-preset="advanced-12" data-hours="12" data-days="tue,wed,thu,sat,sun" data-experience="advanced"><strong>12H</strong><span>5 days · advanced</span></button>
        </div>
      </fieldset>
      <details class="tp-sim-manual">
        <summary>Fine-tune your plan</summary>
        <label class="tp-sim-field" for="tp-sim-hours-{_esc(slug)}"><span>Available hours / week</span><span class="tp-sim-range"><input id="tp-sim-hours-{_esc(slug)}" data-role="hours" type="range" min="4" max="18" step="1" value="8"><output data-role="hours-value">8 hours</output></span></label>
        <fieldset class="tp-sim-field tp-sim-days"><legend>Preferred training days</legend><div>{day_controls}</div><small data-role="day-help">Choose at least three days.</small></fieldset>
        <label class="tp-sim-field" for="tp-sim-level-{_esc(slug)}"><span>Experience level</span><select id="tp-sim-level-{_esc(slug)}" data-role="experience"><option value="beginner">New to structured training</option><option value="intermediate" selected>Experienced / intermediate</option><option value="advanced">Advanced racer</option></select></label>
        <label class="tp-sim-field" for="tp-sim-goal-{_esc(slug)}"><span>Race goal</span><select id="tp-sim-goal-{_esc(slug)}" data-role="goal"><option value="finish">Finish ready</option><option value="compete" selected>Compete well</option><option value="podium">Podium / front group</option></select></label>
        <label class="tp-sim-field" for="tp-sim-control-{_esc(slug)}"><span>Workout targets</span><select id="tp-sim-control-{_esc(slug)}" data-role="control"><option value="power" selected>Power</option><option value="hr">Heart rate</option><option value="rpe">RPE / feel</option></select></label>
        <label class="tp-sim-field" data-role="ftp-field" for="tp-sim-ftp-{_esc(slug)}"><span>Current FTP</span><span class="tp-sim-number"><input id="tp-sim-ftp-{_esc(slug)}" data-role="ftp" type="number" min="50" max="500" step="1" value="250"><small>watts</small></span></label>
        <div data-role="hr-fields" hidden><label class="tp-sim-field" for="tp-sim-lthr-{_esc(slug)}"><span>Threshold heart rate</span><span class="tp-sim-number"><input id="tp-sim-lthr-{_esc(slug)}" data-role="lthr" type="number" min="80" max="220" step="1" value="170"><small>bpm</small></span></label><label class="tp-sim-field" for="tp-sim-maxhr-{_esc(slug)}"><span>Maximum heart rate</span><span class="tp-sim-number"><input id="tp-sim-maxhr-{_esc(slug)}" data-role="maxhr" type="number" min="100" max="230" step="1" value="190"><small>bpm</small></span></label></div>
        <label class="tp-sim-field" for="tp-sim-equipment-{_esc(slug)}"><span>Strength setup</span><select id="tp-sim-equipment-{_esc(slug)}" data-role="equipment"><option value="none">Bodyweight / no equipment</option><option value="home-basic">Basic home gym</option><option value="full-gym" selected>Full gym</option></select></label>
        <label class="tp-sim-field" for="tp-sim-duration-{_esc(slug)}"><span>Expected race time</span><span class="tp-sim-number"><input id="tp-sim-duration-{_esc(slug)}" data-role="duration" type="number" min="1" max="30" step="0.5" value="{config['expected_duration_hours']}"><small>hours</small></span></label>
        <label class="tp-sim-field" for="tp-sim-date-{_esc(slug)}"><span>Race date</span><input id="tp-sim-date-{_esc(slug)}" data-role="race-date" type="date" value="{_esc(config['race_date'])}"></label>
        <label class="tp-sim-field" for="tp-sim-cap-{_esc(slug)}"><span>Weekday session cap</span><select id="tp-sim-cap-{_esc(slug)}" data-role="weekday-cap"><option value="60">60 minutes</option><option value="90" selected>90 minutes</option><option value="120">120 minutes</option><option value="180">3 hours</option></select></label>
      </details>
      <p class="tp-sim-input-note">This preview uses your schedule, tested control method, strength setup, goal, and race demands. Medical history and deeper life constraints stay in the private intake.</p>
    </form>
    <div class="tp-sim-app" data-role="app" aria-live="polite" aria-busy="true">
      <header class="tp-sim-appbar"><div><span>TRAININGPEAKS</span><strong>DELIVERY PREVIEW</strong></div><p data-role="status">Building your race-specific plan…</p></header>
      <div class="tp-sim-view-tabs" role="tablist"><button type="button" role="tab" aria-selected="true" data-view="calendar">CALENDAR WEEK</button><button type="button" role="tab" aria-selected="false" data-view="load">TRAINING LOAD BY WEEK</button></div>
      <div data-role="calendar-view"><nav class="tp-sim-week-tabs" data-role="week-tabs" aria-label="Sample weeks"></nav><div class="tp-sim-weekbar"><div><span data-role="week-label">SAMPLE WEEK</span><strong data-role="week-summary">—</strong></div><div><span>PLANNED</span><strong data-role="week-tss">— TSS</strong></div></div><div class="tp-sim-calendar" data-role="calendar">{calendar_days}</div></div>
      <section class="tp-sim-load" data-role="load-view" hidden><header><div><strong>Training Load By Week</strong><span>SELECT ANY WEEK TO OPEN ITS EXACT CALENDAR</span></div><p data-role="plan-total"></p></header><div class="tp-sim-load-legend"><span>DURATION</span><span>TSS</span></div><div class="tp-sim-load-chart" data-role="load-chart"></div></section>
      <section class="tp-sim-detail" data-role="detail" hidden>
        <button type="button" data-role="detail-close" aria-label="Close workout detail">×</button>
        <p data-role="detail-type">WORKOUT</p><h3 data-role="detail-title"></h3>
        <p class="tp-sim-detail-meta" data-role="detail-meta"></p>
        <div class="tp-sim-purpose"><span>WHY THIS IS HERE</span><p data-role="detail-purpose"></p></div>
        <div class="tp-sim-detail-graph" data-role="detail-graph"></div>
        <div class="tp-sim-detail-copy"><div><span>FUELING</span><p data-role="detail-fueling"></p></div><div><span>COACH NOTE</span><p data-role="detail-coach"></p></div></div>
        <ol class="tp-sim-steps" data-role="detail-steps"></ol>
        <section class="tp-sim-strength" data-role="detail-strength" hidden><span>STRENGTH BLOCK</span><strong data-role="strength-focus"></strong><ol data-role="strength-exercises"></ol></section>
      </section>
      <div class="tp-sim-notes" data-role="notes" hidden><article><span>WEEK NOTE</span><p data-role="week-note"></p></article><article><span>SUNDAY SELF-REVIEW</span><p data-role="self-review"></p></article><article><span>HOW TO COMMENT</span><p data-role="comment-protocol"></p></article></div>
      <footer class="tp-sim-appfoot"><span data-role="versions">Waiting for engine…</span><span>Preview only · full progression unlocks after intake</span></footer>
    </div>
  </div>
  <section class="tp-sim-modules"><button type="button" data-role="modules-toggle" aria-expanded="false">SHOW PLAN MODULES +</button><div data-role="modules-panel" hidden>{module_cards}</div></section>
  <div class="tp-sim-conversion"><p><strong>This week changes when your inputs change.</strong> The purchased plan carries that logic through every build, recovery, taper, and race week.</p><a class="tp-sim-cta" data-role="cta" data-cta="tpp_preview_build" href="{_esc(questionnaire_url)}">BUILD MY FULL PLAN →</a></div>
  <script type="application/json" id="{_esc(config_id)}">{_safe_json(config)}</script>
</section>'''


def get_plan_simulator_css(*, ink: str, paper: str, panel: str,
                           line: str, accent: str, data_font: str,
                           body_font: str) -> str:
    """Return isolated CSS; all estate colors/fonts arrive as brand tokens."""
    return f'''
.tp-sim {{ --sim-ink:{ink}; --sim-paper:{paper}; --sim-panel:{panel}; --sim-line:{line}; --sim-accent:{accent}; --sim-data:{data_font}; --sim-body:{body_font}; box-sizing:border-box; position:relative; left:50%; width:min(1400px,calc(100vw - 32px)); transform:translateX(-50%); margin:64px 0; padding:clamp(22px,3vw,40px); border:4px solid var(--sim-ink); background:var(--sim-paper); color:var(--sim-ink); }}
.tp-sim * {{ box-sizing:border-box; }}
.tp-sim-kicker {{ margin:0 0 8px; font:700 11px/1 var(--sim-data); letter-spacing:2px; color:var(--sim-accent); }}
.tp-sim > h2 {{ margin:0 0 10px; font:700 clamp(24px,3vw,34px)/1.08 var(--sim-data); text-transform:uppercase; }}
.tp-sim-lede {{ max-width:820px; margin:0 0 28px; font:18px/1.6 var(--sim-body); }}
.tp-sim-shell {{ display:grid; grid-template-columns:minmax(220px,300px) minmax(0,1fr); gap:22px; align-items:start; }}
.tp-sim-controls {{ display:grid; gap:18px; }}
.tp-sim-presets,.tp-sim-field {{ margin:0; padding:0; border:0; }}
.tp-sim-presets legend,.tp-sim-field>span,.tp-sim-field>legend {{ margin:0 0 8px; font:700 12px/1.2 var(--sim-data); letter-spacing:1px; text-transform:uppercase; }}
.tp-sim-presets>div {{ display:grid; gap:7px; }}
.tp-sim-presets button {{ display:grid; grid-template-columns:48px 1fr; align-items:center; min-height:52px; padding:7px 10px; border:2px solid var(--sim-line); background:var(--sim-panel); color:var(--sim-ink); text-align:left; cursor:pointer; }}
.tp-sim-presets button strong {{ font:700 18px/1 var(--sim-data); }}
.tp-sim-presets button span {{ font:700 10px/1.3 var(--sim-data); letter-spacing:.5px; text-transform:uppercase; }}
.tp-sim-presets button:hover,.tp-sim-presets button:focus-visible,.tp-sim-presets button.is-active {{ border-color:var(--sim-ink); background:var(--sim-ink); color:var(--sim-paper); }}
.tp-sim-manual {{ border-top:2px solid var(--sim-line); padding-top:12px; }}
.tp-sim-manual summary {{ min-height:44px; display:flex; align-items:center; justify-content:space-between; font:700 11px/1 var(--sim-data); letter-spacing:1px; text-transform:uppercase; cursor:pointer; }}
.tp-sim-manual[open] summary {{ margin-bottom:16px; }}
.tp-sim-field {{ display:grid; gap:8px; margin-top:16px; }}
.tp-sim-range {{ display:flex; gap:10px; align-items:center; }} .tp-sim-range input {{ flex:1; accent-color:var(--sim-accent); }} .tp-sim-range output {{ min-width:62px; text-align:right; font:700 11px/1 var(--sim-data); }}
.tp-sim-days>div {{ display:grid; grid-template-columns:repeat(4,1fr); gap:5px; }}
.tp-sim-day-toggle {{ position:relative; cursor:pointer; }} .tp-sim-day-toggle input {{ position:absolute; opacity:0; pointer-events:none; }} .tp-sim-day-toggle span {{ display:grid; min-height:44px; place-items:center; border:2px solid var(--sim-line); background:var(--sim-panel); font:700 10px/1 var(--sim-data); }} .tp-sim-day-toggle input:checked+span {{ border-color:var(--sim-ink); background:var(--sim-ink); color:var(--sim-paper); }} .tp-sim-day-toggle input:focus-visible+span {{ outline:3px solid var(--sim-accent); outline-offset:2px; }}
.tp-sim-field select,.tp-sim-field input[type=date],.tp-sim-number {{ min-height:46px; width:100%; border:2px solid var(--sim-ink); background:var(--sim-panel); color:var(--sim-ink); padding:9px; font:700 12px/1.2 var(--sim-data); }} .tp-sim-number {{ display:flex; align-items:center; gap:7px; }} .tp-sim-number input {{ min-width:0; flex:1; border:0; background:transparent; color:inherit; font:700 16px/1 var(--sim-data); }} .tp-sim-number small {{ flex:none; font:700 10px/1 var(--sim-data); text-transform:uppercase; }}
.tp-sim-field small,.tp-sim-input-note {{ margin:0; font:12px/1.45 var(--sim-body); }} .tp-sim-day-error {{ color:var(--sim-accent); font-weight:700; }}
.tp-sim-app {{ position:relative; min-width:0; border:1px solid var(--sim-line); background:var(--sim-panel); overflow:hidden; color:var(--sim-ink); }}
.tp-sim-appbar {{ display:flex; align-items:center; justify-content:space-between; gap:16px; min-height:54px; padding:9px 14px; background:var(--sim-ink); color:var(--sim-paper); }} .tp-sim-appbar div {{ display:grid; }} .tp-sim-appbar span {{ font:700 9px/1 var(--sim-data); letter-spacing:1.8px; }} .tp-sim-appbar strong {{ font:700 14px/1.2 var(--sim-data); }} .tp-sim-appbar p {{ margin:0; max-width:60%; text-align:right; font:11px/1.35 var(--sim-data); }}
.tp-sim-view-tabs {{ display:grid; grid-template-columns:1fr 1fr; border-bottom:1px solid var(--sim-line); }} .tp-sim-view-tabs button {{ min-height:48px; border:0; border-right:1px solid var(--sim-line); background:var(--sim-panel); color:var(--sim-ink); font:700 11px/1 var(--sim-data); letter-spacing:1px; cursor:pointer; }} .tp-sim-view-tabs button:last-child {{ border-right:0; }} .tp-sim-view-tabs button[aria-selected=true] {{ background:var(--sim-paper); box-shadow:inset 0 -4px 0 var(--sim-accent); color:var(--sim-accent); }} .tp-sim-view-tabs button:focus-visible {{ outline:3px solid var(--sim-accent); outline-offset:-3px; }}
.tp-sim-week-tabs {{ display:flex; min-height:44px; overflow-x:auto; border-bottom:1px solid var(--sim-line); background:var(--sim-paper); }} .tp-sim-week-tabs button {{ flex:1 0 auto; min-width:110px; border:0; border-right:1px solid var(--sim-line); background:transparent; color:var(--sim-ink); padding:9px 12px; font:700 10px/1.25 var(--sim-data); cursor:pointer; }} .tp-sim-week-tabs button[aria-current=true] {{ background:var(--sim-accent); color:var(--sim-paper); }}
.tp-sim-weekbar {{ display:flex; justify-content:space-between; gap:16px; padding:10px 14px; border-bottom:1px solid var(--sim-line); }} .tp-sim-weekbar div {{ display:grid; gap:2px; }} .tp-sim-weekbar div:last-child {{ text-align:right; }} .tp-sim-weekbar span {{ font:700 8px/1 var(--sim-data); letter-spacing:1.3px; }} .tp-sim-weekbar strong {{ font:700 12px/1.2 var(--sim-data); }}
.tp-sim-calendar {{ display:grid; grid-template-columns:repeat(7,minmax(122px,1fr)); min-height:410px; overflow-x:auto; }}
.tp-sim-day {{ min-width:88px; border-right:1px solid var(--sim-line); }} .tp-sim-day:last-child {{ border-right:0; }} .tp-sim-day>header {{ display:flex; justify-content:space-between; gap:4px; min-height:34px; padding:8px; border-bottom:1px solid var(--sim-line); }} .tp-sim-day>header strong,.tp-sim-day>header span {{ font:700 9px/1 var(--sim-data); text-transform:uppercase; }} .tp-sim-day-sessions {{ display:grid; align-content:start; gap:6px; padding:6px; }}
.tp-sim-loading-tile,.tp-sim-rest {{ display:grid; min-height:58px; place-items:center; padding:6px; border:1px dashed var(--sim-line); font:9px/1.3 var(--sim-data); text-align:center; text-transform:uppercase; }}
.tp-sim-workout {{ --sim-kind:var(--sim-accent); width:100%; min-height:168px; display:grid; align-content:start; gap:7px; padding:9px; border:1px solid var(--sim-ink); border-top:6px solid var(--sim-kind); background:var(--sim-paper); color:var(--sim-ink); text-align:left; cursor:pointer; }} .tp-sim-workout--bike {{ --sim-kind:var(--sim-accent); }} .tp-sim-workout--ski {{ --sim-kind:var(--sim-accent); }} .tp-sim-workout--strength {{ --sim-kind:var(--sim-ink); }} .tp-sim-workout--race {{ --sim-kind:var(--sim-accent); }} .tp-sim-workout:hover,.tp-sim-workout:focus-visible {{ outline:3px solid var(--sim-kind); outline-offset:1px; }} .tp-sim-workout-head {{ display:flex; align-items:center; justify-content:space-between; gap:4px; }} .tp-sim-workout-kind,.tp-sim-workout-structured {{ font:700 8px/1 var(--sim-data); letter-spacing:1px; text-transform:uppercase; }} .tp-sim-workout-structured {{ color:var(--sim-kind); letter-spacing:.4px; }} .tp-sim-workout-title {{ font:700 12px/1.25 var(--sim-data); }} .tp-sim-workout-meta {{ font:700 11px/1.2 var(--sim-data); }} .tp-sim-workout svg {{ width:100%; height:38px; border-top:1px solid var(--sim-line); border-bottom:3px solid var(--sim-line); }} .tp-sim-workout polyline {{ fill:none; stroke:var(--sim-kind); stroke-width:3; vector-effect:non-scaling-stroke; }} .tp-sim-workout .tp-sim-strength-bar {{ fill:var(--sim-kind); opacity:.82; }} .tp-sim-workout-copy {{ max-height:52px; overflow:hidden; margin:0; font:12px/1.35 var(--sim-body); mask-image:linear-gradient(var(--sim-ink) 45%,transparent); -webkit-mask-image:linear-gradient(var(--sim-ink) 45%,transparent); }}
.tp-sim-load {{ min-height:485px; padding:18px; background:var(--sim-paper); }} .tp-sim-load>header {{ display:flex; align-items:end; justify-content:space-between; gap:20px; margin-bottom:12px; }} .tp-sim-load>header div {{ display:grid; gap:4px; }} .tp-sim-load>header strong {{ font:700 20px/1.1 var(--sim-data); }} .tp-sim-load>header span,.tp-sim-load>header p,.tp-sim-load-legend {{ margin:0; font:700 9px/1.3 var(--sim-data); letter-spacing:1px; }} .tp-sim-load-legend {{ display:flex; gap:16px; justify-content:flex-end; margin-bottom:8px; }} .tp-sim-load-chart {{ display:grid; grid-template-columns:repeat(21,minmax(40px,1fr)); align-items:end; gap:2px; min-height:350px; overflow-x:auto; border-bottom:2px solid var(--sim-ink); }} .tp-sim-load-week {{ position:relative; display:grid; grid-template-columns:1fr 1fr; align-items:end; gap:2px; min-width:40px; height:330px; padding:0 3px 28px; border:0; background:transparent; color:var(--sim-ink); cursor:pointer; }} .tp-sim-load-week:hover,.tp-sim-load-week:focus-visible,.tp-sim-load-week[aria-current=true] {{ background:color-mix(in srgb,var(--sim-accent) 10%,transparent); outline:2px solid var(--sim-accent); outline-offset:-2px; }} .tp-sim-load-week i {{ display:block; min-height:3px; background:var(--sim-accent); height:var(--duration-height); }} .tp-sim-load-week i+ i {{ background:var(--sim-line); height:var(--tss-height); }} .tp-sim-load-week b {{ position:absolute; inset:auto 0 7px; font:700 9px/1 var(--sim-data); text-align:center; }} .tp-sim-load-week em {{ position:absolute; top:3px; left:50%; transform:translateX(-50%); font:700 7px/1 var(--sim-data); font-style:normal; writing-mode:vertical-rl; opacity:.7; text-transform:uppercase; }}
.tp-sim-detail {{ position:absolute; inset:54px 0 0; z-index:4; padding:20px; overflow:auto; background:var(--sim-panel); }} .tp-sim-detail>[data-role=detail-close] {{ position:absolute; top:10px; right:10px; width:44px; height:44px; border:2px solid var(--sim-ink); background:var(--sim-paper); color:var(--sim-ink); font:28px/1 var(--sim-data); cursor:pointer; }} .tp-sim-detail>[data-role=detail-type] {{ margin:0 52px 5px 0; font:700 9px/1 var(--sim-data); letter-spacing:1.5px; color:var(--sim-accent); }} .tp-sim-detail h3 {{ margin:0 52px 6px 0; font:700 21px/1.15 var(--sim-data); }} .tp-sim-detail-meta {{ margin:0 0 15px; font:700 10px/1.3 var(--sim-data); text-transform:uppercase; }} .tp-sim-purpose {{ margin:0 0 14px; padding:11px 12px; border-left:5px solid var(--sim-accent); background:var(--sim-paper); }} .tp-sim-purpose span,.tp-sim-strength>span {{ font:700 8px/1 var(--sim-data); letter-spacing:1.2px; }} .tp-sim-purpose p {{ margin:5px 0 0; font:15px/1.45 var(--sim-body); }} .tp-sim-detail-graph svg {{ width:100%; height:110px; border:1px solid var(--sim-line); }} .tp-sim-detail-graph polyline {{ fill:none; stroke:var(--sim-accent); stroke-width:4; vector-effect:non-scaling-stroke; }} .tp-sim-detail-graph .tp-sim-strength-bar {{ fill:#c75b23; opacity:.82; }} .tp-sim-detail-copy {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:14px; }} .tp-sim-detail-copy>div {{ border-top:3px solid var(--sim-ink); padding-top:8px; }} .tp-sim-detail-copy span,.tp-sim-notes span {{ font:700 8px/1 var(--sim-data); letter-spacing:1.2px; }} .tp-sim-detail-copy p,.tp-sim-notes p {{ margin:5px 0 0; font:14px/1.45 var(--sim-body); }} .tp-sim-steps {{ margin:16px 0 0; padding-left:22px; font:11px/1.5 var(--sim-data); }} .tp-sim-strength {{ margin-top:16px; border-top:3px solid var(--sim-ink); padding-top:10px; }} .tp-sim-strength>strong {{ display:block; margin:6px 0 10px; font:700 13px/1.3 var(--sim-data); }} .tp-sim-strength ol {{ display:grid; gap:7px; margin:0; padding:0; list-style:none; }} .tp-sim-strength li {{ display:grid; grid-template-columns:minmax(130px,1fr) auto; gap:3px 12px; padding:9px; border:1px solid var(--sim-line); background:var(--sim-paper); }} .tp-sim-strength li strong {{ font:700 11px/1.25 var(--sim-data); }} .tp-sim-strength li span {{ font:700 9px/1.25 var(--sim-data); }} .tp-sim-strength li p {{ grid-column:1/-1; margin:0; font:13px/1.35 var(--sim-body); }}
.tp-sim-notes {{ grid-template-columns:repeat(3,1fr); border-top:1px solid var(--sim-line); }} .tp-sim-notes article {{ padding:12px; border-right:1px solid var(--sim-line); }} .tp-sim-notes article:last-child {{ border-right:0; }}
.tp-sim-appfoot {{ display:flex; justify-content:space-between; gap:12px; padding:8px 12px; border-top:1px solid var(--sim-line); font:8px/1.3 var(--sim-data); letter-spacing:.5px; text-transform:uppercase; }}
.tp-sim-modules {{ margin-top:22px; }} .tp-sim-modules>button {{ width:100%; min-height:48px; border:2px solid var(--sim-ink); background:var(--sim-panel); color:var(--sim-ink); font:700 11px/1.2 var(--sim-data); letter-spacing:1px; cursor:pointer; }} .tp-sim-modules>button:hover,.tp-sim-modules>button:focus-visible {{ background:var(--sim-ink); color:var(--sim-paper); }} .tp-sim-modules>div {{ grid-template-columns:repeat(3,1fr); gap:8px; margin-top:8px; }} .tp-sim-module {{ min-width:0; padding:14px; border:2px solid var(--sim-line); background:var(--sim-panel); }} .tp-sim-module>span {{ display:block; margin-bottom:7px; font:700 8px/1 var(--sim-data); letter-spacing:1.2px; color:var(--sim-accent); text-transform:uppercase; }} .tp-sim-module>strong {{ display:block; font:700 13px/1.25 var(--sim-data); text-transform:uppercase; }} .tp-sim-module>p {{ margin:7px 0 0; font:13px/1.4 var(--sim-body); }}
.tp-sim-conversion {{ display:flex; align-items:center; justify-content:space-between; gap:20px; margin-top:22px; padding-top:20px; border-top:3px solid var(--sim-ink); }} .tp-sim-conversion p {{ max-width:640px; margin:0; font:15px/1.5 var(--sim-body); }} .tp-sim-cta {{ flex:none; display:inline-block; padding:13px 20px; border:3px solid var(--sim-ink); background:var(--sim-ink); color:var(--sim-paper); font:700 12px/1.2 var(--sim-data); letter-spacing:.8px; text-decoration:none; }} .tp-sim-cta:hover,.tp-sim-cta:focus-visible {{ background:var(--sim-accent); }}
@media(max-width:900px){{.tp-sim-shell{{grid-template-columns:1fr}}.tp-sim-presets>div{{grid-template-columns:repeat(3,1fr)}}.tp-sim-presets button{{grid-template-columns:1fr;text-align:center}}}}
@media(max-width:640px){{.tp-sim{{padding:20px 14px}}.tp-sim-presets>div{{grid-template-columns:1fr}}.tp-sim-presets button{{grid-template-columns:48px 1fr;text-align:left}}.tp-sim-calendar{{grid-template-columns:repeat(7,132px)}}.tp-sim-appbar{{align-items:flex-start}}.tp-sim-appbar p{{max-width:48%}}.tp-sim-notes{{grid-template-columns:1fr}}.tp-sim-notes article{{border-right:0;border-bottom:1px solid var(--sim-line)}}.tp-sim-detail-copy{{grid-template-columns:1fr}}.tp-sim-modules>div{{grid-template-columns:1fr}}.tp-sim-conversion{{align-items:stretch;flex-direction:column}}.tp-sim-cta{{text-align:center}}.tp-sim-load{{padding:12px 6px}}.tp-sim-load>header{{align-items:start;flex-direction:column}}}}
@media(prefers-reduced-motion:reduce){{.tp-sim *{{scroll-behavior:auto!important}}}}
'''


def _get_plan_simulator_js_v1() -> str:
    """Progressively enhance all contract-backed simulator roots."""
    return r'''
(function(){
  var DAY_LABELS={mon:'Mon',tue:'Tue',wed:'Wed',thu:'Thu',fri:'Fri',sat:'Sat',sun:'Sun'};
  function all(root,selector){return Array.prototype.slice.call(root.querySelectorAll(selector));}
  function clear(node){while(node.firstChild)node.removeChild(node.firstChild);}
  function textNode(tag,value,className){var el=document.createElement(tag);if(className)el.className=className;el.textContent=value||'';return el;}
  function minutes(value){var total=Number(value)||0;var h=Math.floor(total/60);var m=total%60;return h?(h+'h'+(m?' '+m+'m':'')):(m+'m');}
  function shortVersion(value){value=String(value||'unknown');return value.length>22?value.slice(0,22):value;}
  function graph(structure,height){
    var points=structure&&Array.isArray(structure.polyline)?structure.polyline:[];
    if(!points.length)return null;
    var ns='http://www.w3.org/2000/svg';var svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 100 '+height);svg.setAttribute('aria-hidden','true');svg.setAttribute('preserveAspectRatio','none');
    var line=document.createElementNS(ns,'polyline');line.setAttribute('points',points.map(function(p){var x=Math.max(0,Math.min(1,Number(p[0])||0))*100;var y=height-Math.max(0,Math.min(1.5,Number(p[1])||0))/1.5*(height-4)-2;return x.toFixed(2)+','+y.toFixed(2);}).join(' '));svg.appendChild(line);return svg;
  }
  function strengthGraph(strength,height){var exercises=strength&&Array.isArray(strength.exercises)?strength.exercises:[];if(!exercises.length)return null;var ns='http://www.w3.org/2000/svg';var svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 100 '+height);svg.setAttribute('aria-hidden','true');var visible=exercises.slice(0,5);var row=height/visible.length;visible.forEach(function(exercise,index){var rect=document.createElementNS(ns,'rect');rect.setAttribute('class','tp-sim-strength-bar');rect.setAttribute('x','2');rect.setAttribute('y',String(index*row+2));rect.setAttribute('height',String(Math.max(3,row-4)));rect.setAttribute('width',String(Math.min(96,28+(Number(exercise.sets)||1)*12)));svg.appendChild(rect);});return svg;}
  function init(root){
    var configEl=document.getElementById(root.getAttribute('data-config-id'));if(!configEl)return;var config;try{config=JSON.parse(configEl.textContent);}catch(_error){return;}
    var controls=root.querySelector('[data-role=controls]');var app=root.querySelector('[data-role=app]');var hours=root.querySelector('[data-role=hours]');var hoursValue=root.querySelector('[data-role=hours-value]');var experience=root.querySelector('[data-role=experience]');var raceSelect=root.querySelector('[data-role=race]');var dayInputs=all(root,'.tp-sim-day-toggle input');var presets=all(root,'[data-preset]');var status=root.querySelector('[data-role=status]');var cta=root.querySelector('[data-role=cta]');var dayHelp=root.querySelector('[data-role=day-help]');var timer=null;var controller=null;var touched=false;var presetId='committed-8';var currentResponse=null;
    function selectedDays(){return dayInputs.filter(function(input){return input.checked;}).map(function(input){return input.value;});}
    function updateCta(){var url=new URL(cta.getAttribute('href'),window.location.origin);url.searchParams.set('race',config.race.slug);url.searchParams.set('hours',hours.value);url.searchParams.set('days',selectedDays().map(function(day){return DAY_LABELS[day];}).join(','));url.searchParams.set('experience',experience.value);cta.href=url.toString();}
    function requestBody(){return {schema_version:'training-plan-preview-request/v1',brand:config.brand,preset_id:presetId||undefined,race:config.race,rider:{hours_per_week:Number(hours.value),preferred_days:selectedDays(),experience_level:experience.value}};}
    function setLoading(){app.setAttribute('aria-busy','true');status.textContent='Building a '+hours.value+'-hour '+config.race.name+' week…';root.querySelector('[data-role=week-summary]').textContent=hours.value+' HOURS · '+selectedDays().length+' TRAINING DAYS';root.querySelector('[data-role=week-tss]').textContent='— TSS';}
    function setUnavailable(message){app.setAttribute('aria-busy','false');status.textContent=message||'Live preview temporarily unavailable.';all(root,'[data-calendar-day]').forEach(function(day){var box=day.querySelector('.tp-sim-day-sessions');clear(box);box.appendChild(textNode('span','Preview unavailable','tp-sim-loading-tile'));});root.querySelector('[data-role=notes]').hidden=true;root.querySelector('[data-role=versions]').textContent='Engine connection unavailable';}
    function showDetail(session){var detail=root.querySelector('[data-role=detail]');root.querySelector('[data-role=detail-type]').textContent=(session.kind||'workout').toUpperCase();root.querySelector('[data-role=detail-title]').textContent=session.title;root.querySelector('[data-role=detail-meta]').textContent=minutes(session.duration_minutes)+' · '+session.tss+' TSS'+(session.intensity_label?' · '+session.intensity_label:'');root.querySelector('[data-role=detail-purpose]').textContent=session.purpose||'This session earns its place through the demands of your race and week.';root.querySelector('[data-role=detail-fueling]').textContent=session.fueling_guidance||'No special fueling instruction for this session.';root.querySelector('[data-role=detail-coach]').textContent=session.coach_note||'Follow the written structure.';var graphBox=root.querySelector('[data-role=detail-graph]');clear(graphBox);var svg=session.kind==='strength'?strengthGraph(session.strength,110):graph(session.structure,110);if(svg)graphBox.appendChild(svg);else graphBox.appendChild(textNode('p','No structured graph for this calendar item.'));
      var steps=root.querySelector('[data-role=detail-steps]');clear(steps);var list=session.structure&&Array.isArray(session.structure.steps)?session.structure.steps:[];list.forEach(function(step){var target='';if(step.intensity_target_min!=null)target=Math.round(step.intensity_target_min*100)+(step.intensity_target_max!=null?'–'+Math.round(step.intensity_target_max*100):'')+'%';var cadence=step.cadence_rpm?' · '+step.cadence_rpm+' rpm':'';steps.appendChild(textNode('li',(step.label||step.type||'Step')+' · '+minutes(step.length_seconds/60)+(target?' · '+target:'')+cadence));});var strengthBox=root.querySelector('[data-role=detail-strength]');var exercises=root.querySelector('[data-role=strength-exercises]');clear(exercises);var strength=session.strength&&Array.isArray(session.strength.exercises)?session.strength:null;strengthBox.hidden=!strength;if(strength){root.querySelector('[data-role=strength-focus]').textContent=strength.focus;strength.exercises.forEach(function(exercise){var item=document.createElement('li');item.appendChild(textNode('strong',exercise.name));var prescription=exercise.sets+' × '+exercise.reps+(exercise.rest_seconds?' · '+exercise.rest_seconds+'s rest':'');item.appendChild(textNode('span',prescription));item.appendChild(textNode('p',exercise.cue));exercises.appendChild(item);});}detail.hidden=false;detail.querySelector('[data-role=detail-close]').focus();}
    function render(response){if(!response||response.schema_version!=='training-plan-preview/v1'||!response.week||!Array.isArray(response.week.days)||response.week.days.length!==7)throw new Error('Bad preview contract');var expected=requestBody();var responseDays=response.rider&&Array.isArray(response.rider.preferred_days)?response.rider.preferred_days.join(','):'';if(!response.race||response.race.slug!==expected.race.slug||!response.rider||Number(response.rider.hours_per_week)!==expected.rider.hours_per_week||response.rider.experience_level!==expected.rider.experience_level||responseDays!==expected.rider.preferred_days.join(','))throw new Error('Stale preview contract');currentResponse=response;app.setAttribute('aria-busy','false');status.textContent='Built from '+config.race.name+' demands and your availability.';root.querySelector('[data-role=week-summary]').textContent=minutes(response.week.target_minutes).toUpperCase()+' · '+response.rider.preferred_days.length+' TRAINING DAYS';root.querySelector('[data-role=week-tss]').textContent=response.week.target_tss+' TSS';
      response.week.days.forEach(function(day,index){var column=root.querySelector('[data-calendar-day="'+day.day+'"]');if(!column)return;column.querySelector('header span').textContent=String(index+1).padStart(2,'0');var box=column.querySelector('.tp-sim-day-sessions');clear(box);if(!day.sessions.length){box.appendChild(textNode('span','Rest / mobility','tp-sim-rest'));return;}day.sessions.forEach(function(session){var button=document.createElement('button');button.type='button';button.className='tp-sim-workout tp-sim-workout--'+(session.kind||'workout');var head=textNode('span','','tp-sim-workout-head');head.appendChild(textNode('span',(session.kind||'workout').toUpperCase(),'tp-sim-workout-kind'));head.appendChild(textNode('span',session.kind==='strength'?'STRUCTURED STRENGTH':'STRUCTURED','tp-sim-workout-structured'));button.appendChild(head);button.appendChild(textNode('strong',session.title,'tp-sim-workout-title'));var exerciseCount=session.strength&&Array.isArray(session.strength.exercises)?' · '+session.strength.exercises.length+' EXERCISES':'';button.appendChild(textNode('span',minutes(session.duration_minutes)+' · '+session.tss+' TSS'+exerciseCount,'tp-sim-workout-meta'));var svg=session.kind==='strength'?strengthGraph(session.strength,34):graph(session.structure,34);if(svg)button.appendChild(svg);button.addEventListener('click',function(){showDetail(session);});box.appendChild(button);});});
      var notes=root.querySelector('[data-role=notes]');notes.hidden=false;root.querySelector('[data-role=week-note]').textContent=response.week.coach_note;root.querySelector('[data-role=self-review]').textContent=response.week.weekly_self_review;root.querySelector('[data-role=comment-protocol]').textContent=response.week.comment_protocol;root.querySelector('[data-role=versions]').textContent='Engine '+shortVersion(response.engine_version)+' · Voice '+shortVersion(response.voice_version);root.dataset.engineVersion=response.engine_version;root.dataset.voiceVersion=response.voice_version;}
    function load(){if(controller)controller.abort();controller=typeof AbortController==='function'?new AbortController():null;setLoading();var endpoint=root.getAttribute('data-preview-endpoint')||config.endpoint;fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(requestBody()),signal:controller?controller.signal:undefined}).then(function(response){if(!response.ok)throw new Error('Preview '+response.status);return response.json();}).then(render).catch(function(error){if(error&&error.name==='AbortError')return;setUnavailable('Live preview temporarily unavailable. Your selections are saved for the full intake.');});}
    function schedule(immediate){clearTimeout(timer);updateCta();if(selectedDays().length<3)return;timer=setTimeout(load,immediate?0:350);if(touched&&typeof gtag==='function'){gtag('event','plan_preview_update',{source:'training_plan_simulator',race_slug:config.race.slug,hours_per_week:Number(hours.value),preferred_days_count:selectedDays().length,experience_level:experience.value,preset_id:presetId||'manual'});}}
    presets.forEach(function(button){button.setAttribute('aria-pressed',button.classList.contains('is-active')?'true':'false');button.addEventListener('click',function(){touched=true;presetId=button.getAttribute('data-preset');hours.value=button.getAttribute('data-hours');experience.value=button.getAttribute('data-experience');var wanted=button.getAttribute('data-days').split(',');dayInputs.forEach(function(input){input.checked=wanted.indexOf(input.value)!==-1;});presets.forEach(function(item){var active=item===button;item.classList.toggle('is-active',active);item.setAttribute('aria-pressed',active?'true':'false');});hoursValue.textContent=hours.value+' hours';dayHelp.classList.remove('tp-sim-day-error');schedule(true);});});
    controls.addEventListener('input',function(event){if(event.target===raceSelect&&Array.isArray(config.race_options)){var next=config.race_options.find(function(item){return item.slug===raceSelect.value;});if(next)config.race=next;}if(event.target.matches('.tp-sim-day-toggle input')&&selectedDays().length<3){event.target.checked=true;dayHelp.textContent='A useful preview needs at least three available days.';dayHelp.classList.add('tp-sim-day-error');return;}touched=true;presetId='';presets.forEach(function(item){item.classList.remove('is-active');item.setAttribute('aria-pressed','false');});hoursValue.textContent=hours.value+' hours';dayHelp.textContent='Choose at least three days.';dayHelp.classList.remove('tp-sim-day-error');schedule(false);});
    root.querySelector('[data-role=detail-close]').addEventListener('click',function(){root.querySelector('[data-role=detail]').hidden=true;});var moduleToggle=root.querySelector('[data-role=modules-toggle]');var modulePanel=root.querySelector('[data-role=modules-panel]');moduleToggle.addEventListener('click',function(){var open=moduleToggle.getAttribute('aria-expanded')!=='true';moduleToggle.setAttribute('aria-expanded',open?'true':'false');moduleToggle.textContent=open?'HIDE PLAN MODULES −':'SHOW PLAN MODULES +';modulePanel.hidden=!open;if(open&&typeof gtag==='function')gtag('event','plan_modules_open',{source:'training_plan_simulator',race_slug:config.race.slug});});updateCta();schedule(true);
  }
  all(document,'[data-training-preview]').forEach(init);
})();
'''


def get_plan_simulator_js() -> str:
    """Progressively enhance v2 full-plan simulators without static workouts."""
    return r'''
(function(){
  var DAY_LABELS={mon:'Mon',tue:'Tue',wed:'Wed',thu:'Thu',fri:'Fri',sat:'Sat',sun:'Sun'};
  function all(root,selector){return Array.prototype.slice.call(root.querySelectorAll(selector));}
  function clear(node){while(node.firstChild)node.removeChild(node.firstChild);}
  function node(tag,value,className){var el=document.createElement(tag);if(className)el.className=className;if(value!=null)el.textContent=String(value);return el;}
  function durationText(value){var total=Math.round(Number(value)||0),hours=Math.floor(total/60),minutes=total%60;return hours?(hours+':'+String(minutes).padStart(2,'0')+':00'):(minutes+':00');}
  function compactDuration(value){var total=Math.round(Number(value)||0),hours=Math.floor(total/60),minutes=total%60;return hours?(hours+'h'+(minutes?' '+minutes+'m':'')):(minutes+'m');}
  function shortDate(value){try{return new Intl.DateTimeFormat(undefined,{month:'short',day:'numeric'}).format(new Date(value+'T12:00:00'));}catch(_error){return value||'—';}}
  function shortVersion(value){value=String(value||'unknown');return value.length>24?value.slice(0,24):value;}
  function graph(structure,height){
    var points=structure&&Array.isArray(structure.polyline)?structure.polyline:[];
    if(!points.length)return null;
    var ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 100 '+height);svg.setAttribute('aria-hidden','true');svg.setAttribute('preserveAspectRatio','none');
    var line=document.createElementNS(ns,'polyline');line.setAttribute('points',points.map(function(point){var x=Math.max(0,Math.min(1,Number(point[0])||0))*100,y=height-Math.max(0,Math.min(1.5,Number(point[1])||0))/1.5*(height-4)-2;return x.toFixed(2)+','+y.toFixed(2);}).join(' '));svg.appendChild(line);return svg;
  }
  function strengthGraph(strength,height){var exercises=strength&&Array.isArray(strength.exercises)?strength.exercises:[];if(!exercises.length)return null;var ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 100 '+height);svg.setAttribute('aria-hidden','true');exercises.slice(0,5).forEach(function(exercise,index){var row=height/Math.min(5,exercises.length),rect=document.createElementNS(ns,'rect');rect.setAttribute('class','tp-sim-strength-bar');rect.setAttribute('x','2');rect.setAttribute('y',String(index*row+2));rect.setAttribute('height',String(Math.max(3,row-4)));rect.setAttribute('width',String(Math.min(96,28+(Number(exercise.sets)||1)*12)));svg.appendChild(rect);});return svg;}
  function init(root){
    var configEl=document.getElementById(root.getAttribute('data-config-id')),config;try{config=JSON.parse(configEl.textContent);}catch(_error){return;}
    var controls=root.querySelector('[data-role=controls]'),app=root.querySelector('[data-role=app]'),hours=root.querySelector('[data-role=hours]'),hoursValue=root.querySelector('[data-role=hours-value]'),experience=root.querySelector('[data-role=experience]'),goal=root.querySelector('[data-role=goal]'),control=root.querySelector('[data-role=control]'),ftp=root.querySelector('[data-role=ftp]'),lthr=root.querySelector('[data-role=lthr]'),maxhr=root.querySelector('[data-role=maxhr]'),equipment=root.querySelector('[data-role=equipment]'),duration=root.querySelector('[data-role=duration]'),raceDate=root.querySelector('[data-role=race-date]'),weekdayCap=root.querySelector('[data-role=weekday-cap]'),raceSelect=root.querySelector('[data-role=race]'),dayInputs=all(root,'.tp-sim-day-toggle input'),presets=all(root,'[data-preset]'),status=root.querySelector('[data-role=status]'),cta=root.querySelector('[data-role=cta]'),dayHelp=root.querySelector('[data-role=day-help]');
    var touched=false;var timer=null,controller=null,presetId='committed-8',responseData=null,selectedWeek=null,requestedWeek=null,currentView='calendar';
    function selectedDays(){return dayInputs.filter(function(input){return input.checked;}).map(function(input){return input.value;});}
    function dayCaps(){var cap=Number(weekdayCap.value),result={};selectedDays().forEach(function(day){if(['mon','tue','wed','thu','fri'].indexOf(day)!==-1)result[day]=cap;});return result;}
    function updateControlFields(){root.querySelector('[data-role=ftp-field]').hidden=control.value!=='power';root.querySelector('[data-role=hr-fields]').hidden=control.value!=='hr';}
    function updateCta(){var url=new URL(cta.getAttribute('href'),window.location.origin);url.searchParams.set('race',config.race.slug);url.searchParams.set('hours',hours.value);url.searchParams.set('days',selectedDays().map(function(day){return DAY_LABELS[day];}).join(','));url.searchParams.set('experience',experience.value);url.searchParams.set('goal',goal.value);url.searchParams.set('control',control.value);url.searchParams.set('strength_equipment',equipment.value);url.searchParams.set('race_date',raceDate.value);url.searchParams.set('expected_hours',duration.value);cta.href=url.toString();}
    function requestBody(){var rider={hours_per_week:Number(hours.value),preferred_days:selectedDays(),experience_level:experience.value,goal_type:goal.value,control_method:control.value,strength_equipment:equipment.value,day_caps_minutes:dayCaps()};if(control.value==='power')rider.ftp_watts=Number(ftp.value);if(control.value==='hr'){rider.lthr_bpm=Number(lthr.value);rider.max_hr_bpm=Number(maxhr.value);}var race=Object.assign({},config.race,{date:raceDate.value,expected_duration_hours:Number(duration.value)});var body={schema_version:'training-plan-preview-request/v2',brand:config.brand,preset_id:presetId||undefined,plan_weeks:Number(config.plan_weeks||21),race:race,rider:rider};if(requestedWeek)body.sample_week_number=requestedWeek;return body;}
    function setLoading(){app.setAttribute('aria-busy','true');status.textContent='Motoren is rebuilding '+config.race.name+' around these constraints…';}
    function setUnavailable(message){app.setAttribute('aria-busy','false');status.textContent=message||'Live preview temporarily unavailable.';all(root,'[data-calendar-day]').forEach(function(day){var box=day.querySelector('.tp-sim-day-sessions');clear(box);box.appendChild(node('span','Preview unavailable','tp-sim-loading-tile'));});root.querySelector('[data-role=notes]').hidden=true;root.querySelector('[data-role=versions]').textContent='Engine connection unavailable';}
    function showDetail(session){var detail=root.querySelector('[data-role=detail]');root.querySelector('[data-role=detail-type]').textContent=(session.kind||'workout').toUpperCase();root.querySelector('[data-role=detail-title]').textContent=session.title;root.querySelector('[data-role=detail-meta]').textContent=durationText(session.duration_minutes)+' · '+session.tss+' TSS'+(session.intensity_label?' · '+session.intensity_label:'');root.querySelector('[data-role=detail-purpose]').textContent=session.purpose||'';root.querySelector('[data-role=detail-fueling]').textContent=session.fueling_guidance||'';root.querySelector('[data-role=detail-coach]').textContent=session.coach_note||'';var graphBox=root.querySelector('[data-role=detail-graph]');clear(graphBox);var svg=session.kind==='strength'?strengthGraph(session.strength,110):graph(session.structure,110);if(svg)graphBox.appendChild(svg);else graphBox.appendChild(node('p',session.kind==='race'?'Race day is delivered as FreeRide—no fake target graph.':'No structure graph for this calendar item.'));var steps=root.querySelector('[data-role=detail-steps]');clear(steps);var list=session.structure&&Array.isArray(session.structure.steps)?session.structure.steps:[];list.forEach(function(step){var target='';if(step.intensity_target_min!=null)target=Math.round(step.intensity_target_min*100)+(step.intensity_target_max!=null?'–'+Math.round(step.intensity_target_max*100):'')+'%';var cadence=step.cadence_rpm?' · '+step.cadence_rpm+' rpm':'';steps.appendChild(node('li',(step.label||step.type||'Step')+' · '+compactDuration(step.length_seconds/60)+(target?' · '+target:'')+cadence));});var strengthBox=root.querySelector('[data-role=detail-strength]'),exercises=root.querySelector('[data-role=strength-exercises]');clear(exercises);var strength=session.strength&&Array.isArray(session.strength.exercises)?session.strength:null;strengthBox.hidden=!strength;if(strength){root.querySelector('[data-role=strength-focus]').textContent=strength.focus;strength.exercises.forEach(function(exercise){var item=document.createElement('li');item.appendChild(node('strong',exercise.name));item.appendChild(node('span',exercise.sets+' × '+exercise.reps+(exercise.rest_seconds?' · '+exercise.rest_seconds+'s rest':'')));item.appendChild(node('p',exercise.cue));exercises.appendChild(item);});}detail.hidden=false;detail.querySelector('[data-role=detail-close]').focus();}
    function findWeek(number){return responseData&&responseData.sample_weeks.find(function(week){return week.week_number===number;});}
    function renderWeekTabs(){var wrap=root.querySelector('[data-role=week-tabs]');clear(wrap);responseData.sample_weeks.forEach(function(week){var button=node('button','WEEK '+week.week_number+' · '+week.phase.replace('_',' ').toUpperCase());button.type='button';button.setAttribute('aria-current',week.week_number===selectedWeek?'true':'false');button.addEventListener('click',function(){selectedWeek=week.week_number;renderCalendar();});wrap.appendChild(button);});}
    function renderCalendar(){var week=findWeek(selectedWeek)||responseData.sample_weeks[0];selectedWeek=week.week_number;renderWeekTabs();root.querySelector('[data-role=week-label]').textContent='WEEK '+week.week_number+' · '+week.phase.replace('_',' ').toUpperCase()+' · '+week.type.replace('_',' ').toUpperCase();root.querySelector('[data-role=week-summary]').textContent=compactDuration(week.target_minutes).toUpperCase()+' · '+week.days.reduce(function(total,day){return total+day.sessions.length;},0)+' SESSIONS';root.querySelector('[data-role=week-tss]').textContent=week.target_tss+' TSS';week.days.forEach(function(day){var column=root.querySelector('[data-calendar-day="'+day.day+'"]');if(!column)return;column.querySelector('header span').textContent=shortDate(day.date);var box=column.querySelector('.tp-sim-day-sessions');clear(box);if(!day.sessions.length){box.appendChild(node('span','Rest / mobility','tp-sim-rest'));return;}day.sessions.forEach(function(session){var button=document.createElement('button');button.type='button';button.className='tp-sim-workout tp-sim-workout--'+(session.kind||'workout');var head=node('span',null,'tp-sim-workout-head');head.appendChild(node('span',(session.kind||'workout').toUpperCase(),'tp-sim-workout-kind'));head.appendChild(node('span',session.structure?'STRUCTURED':session.kind==='strength'?'STRUCTURED STRENGTH':'FREE RIDE','tp-sim-workout-structured'));button.appendChild(head);button.appendChild(node('strong',session.title,'tp-sim-workout-title'));var exerciseCount=session.strength&&Array.isArray(session.strength.exercises)?' · '+session.strength.exercises.length+' EXERCISES':'';button.appendChild(node('span',durationText(session.duration_minutes)+' · '+session.tss+' TSS'+exerciseCount,'tp-sim-workout-meta'));var svg=session.kind==='strength'?strengthGraph(session.strength,38):graph(session.structure,38);if(svg)button.appendChild(svg);button.appendChild(node('p',(session.purpose||'')+' '+(session.coach_note||''),'tp-sim-workout-copy'));button.addEventListener('click',function(){showDetail(session);});box.appendChild(button);});});var notes=root.querySelector('[data-role=notes]');notes.hidden=false;root.querySelector('[data-role=week-note]').textContent=week.coach_note;root.querySelector('[data-role=self-review]').textContent=week.weekly_self_review;root.querySelector('[data-role=comment-protocol]').textContent=week.comment_protocol;renderLoadChart();}
    function renderLoadChart(){var wrap=root.querySelector('[data-role=load-chart]');clear(wrap);var maxMinutes=Math.max.apply(null,responseData.planned_volume.map(function(week){return week.target_minutes;})),maxTss=Math.max.apply(null,responseData.planned_volume.map(function(week){return week.target_tss;}));responseData.planned_volume.forEach(function(week){var button=document.createElement('button');button.type='button';button.className='tp-sim-load-week';button.style.setProperty('--duration-height',Math.max(3,Math.round(270*week.target_minutes/maxMinutes))+'px');button.style.setProperty('--tss-height',Math.max(3,Math.round(270*week.target_tss/maxTss))+'px');button.setAttribute('aria-label','Week '+week.week_number+', '+compactDuration(week.target_minutes)+', '+week.target_tss+' TSS, '+week.phase.replace('_',' ')+' '+week.type.replace('_',' '));button.setAttribute('aria-current',week.week_number===selectedWeek?'true':'false');button.appendChild(node('i'));button.appendChild(node('i'));button.appendChild(node('em',week.phase.replace('_',' ')));button.appendChild(node('b',week.week_number));button.addEventListener('click',function(){selectedWeek=week.week_number;var available=findWeek(selectedWeek);if(available){setView('calendar');renderCalendar();return;}requestedWeek=selectedWeek;setView('calendar');load();});wrap.appendChild(button);});var total=responseData.planned_volume.reduce(function(sum,week){return sum+week.target_minutes;},0);root.querySelector('[data-role=plan-total]').textContent=responseData.plan.total_weeks+' WEEKS · '+compactDuration(total)+' TOTAL';}
    function setView(view){currentView=view;all(root,'[data-view]').forEach(function(button){button.setAttribute('aria-selected',button.getAttribute('data-view')===view?'true':'false');});root.querySelector('[data-role=calendar-view]').hidden=view!=='calendar';root.querySelector('[data-role=load-view]').hidden=view!=='load';if(view==='load'&&responseData)renderLoadChart();}
    function render(response){var expected=requestBody();if(!response||response.schema_version!=='training-plan-preview/v2'||!response.plan||!Array.isArray(response.planned_volume)||!Array.isArray(response.sample_weeks))throw new Error('Bad preview contract');var responseDays=response.rider&&Array.isArray(response.rider.preferred_days)?response.rider.preferred_days.join(','):'';if(!response.race||response.race.slug!==expected.race.slug||response.race.date!==expected.race.date||!response.rider||Number(response.rider.hours_per_week)!==expected.rider.hours_per_week||response.rider.experience_level!==expected.rider.experience_level||responseDays!==expected.rider.preferred_days.join(','))throw new Error('Stale preview contract');responseData=response;if(requestedWeek&&findWeek(requestedWeek))selectedWeek=requestedWeek;if(!selectedWeek){var nonRace=response.sample_weeks.filter(function(week){return week.type!=='race';});selectedWeek=(nonRace[nonRace.length-1]||response.sample_weeks[0]).week_number;}requestedWeek=null;app.setAttribute('aria-busy','false');status.textContent='Motoren built this from '+config.race.name+', your tested targets, and your available week.';root.querySelector('[data-role=versions]').textContent='Engine '+shortVersion(response.engine_version)+' · Voice '+shortVersion(response.voice_version);root.dataset.engineVersion=response.engine_version;root.dataset.voiceVersion=response.voice_version;renderCalendar();setView(currentView);}
    function load(){if(selectedDays().length<3)return;if(!raceDate.value){setUnavailable('Choose a confirmed race date to build the plan preview.');return;}if(controller)controller.abort();controller=typeof AbortController==='function'?new AbortController():null;setLoading();var endpoint=root.getAttribute('data-preview-endpoint')||config.endpoint;fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(requestBody()),signal:controller?controller.signal:undefined}).then(function(response){if(!response.ok)throw new Error('Preview '+response.status);return response.json();}).then(render).catch(function(error){if(error&&error.name==='AbortError')return;setUnavailable(config.brand==='xc_ski_labs'?'Native ski preview is not available yet. We will not show you cycling workouts labeled as ski training.':'Live preview temporarily unavailable. Your selections are saved for the full intake.');});}
    function schedule(immediate){clearTimeout(timer);updateControlFields();updateCta();if(selectedDays().length<3)return;requestedWeek=null;selectedWeek=null;timer=setTimeout(load,immediate?0:350);if(touched&&typeof gtag==='function'){gtag('event','plan_preview_update',{source:'training_plan_simulator',race_slug:config.race.slug,hours_per_week:Number(hours.value),preferred_days_count:selectedDays().length,experience_level:experience.value,goal_type:goal.value,control_method:control.value,preset_id:presetId||'manual'});}}
    presets.forEach(function(button){button.setAttribute('aria-pressed',button.classList.contains('is-active')?'true':'false');button.addEventListener('click',function(){touched=true;presetId=button.getAttribute('data-preset');hours.value=button.getAttribute('data-hours');experience.value=button.getAttribute('data-experience');var wanted=button.getAttribute('data-days').split(',');dayInputs.forEach(function(input){input.checked=wanted.indexOf(input.value)!==-1;});presets.forEach(function(item){var active=item===button;item.classList.toggle('is-active',active);item.setAttribute('aria-pressed',active?'true':'false');});hoursValue.textContent=hours.value+' hours';dayHelp.classList.remove('tp-sim-day-error');schedule(true);});});
    controls.addEventListener('input',function(event){if(event.target===raceSelect&&Array.isArray(config.race_options)){var next=config.race_options.find(function(item){return item.slug===raceSelect.value;});if(next){config.race=next;raceDate.value=next.date||'';duration.value=next.expected_duration_hours||config.expected_duration_hours;}}if(event.target.matches('.tp-sim-day-toggle input')&&selectedDays().length<3){event.target.checked=true;dayHelp.textContent='A useful preview needs at least three available days.';dayHelp.classList.add('tp-sim-day-error');return;}touched=true;presetId='';presets.forEach(function(item){item.classList.remove('is-active');item.setAttribute('aria-pressed','false');});hoursValue.textContent=hours.value+' hours';dayHelp.textContent='Choose at least three days.';dayHelp.classList.remove('tp-sim-day-error');schedule(false);});
    all(root,'[data-view]').forEach(function(button){button.addEventListener('click',function(){setView(button.getAttribute('data-view'));});});root.querySelector('[data-role=detail-close]').addEventListener('click',function(){root.querySelector('[data-role=detail]').hidden=true;});var moduleToggle=root.querySelector('[data-role=modules-toggle]'),modulePanel=root.querySelector('[data-role=modules-panel]'),manual=root.querySelector('.tp-sim-manual');if(window.matchMedia&&window.matchMedia('(min-width:901px)').matches)manual.open=true;moduleToggle.addEventListener('click',function(){var open=moduleToggle.getAttribute('aria-expanded')!=='true';moduleToggle.setAttribute('aria-expanded',open?'true':'false');moduleToggle.textContent=open?'HIDE PLAN MODULES −':'SHOW PLAN MODULES +';modulePanel.hidden=!open;if(open&&typeof gtag==='function')gtag('event','plan_modules_open',{source:'training_plan_simulator',race_slug:config.race.slug});});updateControlFields();updateCta();schedule(true);
  }
  all(document,'[data-training-preview]').forEach(init);
})();
'''
