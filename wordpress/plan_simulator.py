"""Contract-driven TrainingPeaks calendar simulator shared by plan pages."""

from __future__ import annotations

import html
import json
import os
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
        "schema_version": "training-plan-preview-request/v1",
        "brand": brand,
        "endpoint": PREVIEW_ENDPOINT,
        "race": {
            "slug": slug,
            "name": str(race.get("name") or race.get("display_name") or slug),
            "discipline": str(discipline),
            "demands": normalized_demands,
        },
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
        <summary>Fine-tune the week</summary>
        <label class="tp-sim-field" for="tp-sim-hours-{_esc(slug)}"><span>Available hours / week</span><span class="tp-sim-range"><input id="tp-sim-hours-{_esc(slug)}" data-role="hours" type="range" min="4" max="18" step="1" value="8"><output data-role="hours-value">8 hours</output></span></label>
        <fieldset class="tp-sim-field tp-sim-days"><legend>Preferred training days</legend><div>{day_controls}</div><small data-role="day-help">Choose at least three days.</small></fieldset>
        <label class="tp-sim-field" for="tp-sim-level-{_esc(slug)}"><span>Experience level</span><select id="tp-sim-level-{_esc(slug)}" data-role="experience"><option value="beginner">New to structured training</option><option value="intermediate" selected>Experienced / intermediate</option><option value="advanced">Advanced racer</option></select></label>
      </details>
      <p class="tp-sim-input-note">This is a preview, so it asks only three questions. The full intake adds fitness markers, injury history, equipment, and life constraints.</p>
    </form>
    <div class="tp-sim-app" data-role="app" aria-live="polite" aria-busy="true">
      <header class="tp-sim-appbar"><div><span>TRAININGPEAKS</span><strong>CALENDAR PREVIEW</strong></div><p data-role="status">Building an 8-hour race-specific week…</p></header>
      <div class="tp-sim-weekbar"><div><span>BUILD WEEK</span><strong data-role="week-summary">8 HOURS · 4 TRAINING DAYS</strong></div><div><span>PLANNED</span><strong data-role="week-tss">— TSS</strong></div></div>
      <div class="tp-sim-calendar" data-role="calendar">{calendar_days}</div>
      <section class="tp-sim-detail" data-role="detail" hidden>
        <button type="button" data-role="detail-close" aria-label="Close workout detail">×</button>
        <p data-role="detail-type">WORKOUT</p><h3 data-role="detail-title"></h3>
        <p class="tp-sim-detail-meta" data-role="detail-meta"></p>
        <div class="tp-sim-detail-graph" data-role="detail-graph"></div>
        <div class="tp-sim-detail-copy"><div><span>FUELING</span><p data-role="detail-fueling"></p></div><div><span>COACH NOTE</span><p data-role="detail-coach"></p></div></div>
        <ol class="tp-sim-steps" data-role="detail-steps"></ol>
      </section>
      <div class="tp-sim-notes" data-role="notes" hidden><article><span>WEEK NOTE</span><p data-role="week-note"></p></article><article><span>SUNDAY SELF-REVIEW</span><p data-role="self-review"></p></article><article><span>HOW TO COMMENT</span><p data-role="comment-protocol"></p></article></div>
      <footer class="tp-sim-appfoot"><span data-role="versions">Waiting for engine…</span><span>Preview only · full progression unlocks after intake</span></footer>
    </div>
  </div>
  <div class="tp-sim-conversion"><p><strong>This week changes when your inputs change.</strong> The purchased plan carries that logic through every build, recovery, taper, and race week.</p><a class="tp-sim-cta" data-role="cta" data-cta="tpp_preview_build" href="{_esc(questionnaire_url)}">BUILD MY FULL PLAN →</a></div>
  <script type="application/json" id="{_esc(config_id)}">{_safe_json(config)}</script>
</section>'''


def get_plan_simulator_css(*, ink: str, paper: str, panel: str,
                           line: str, accent: str, data_font: str,
                           body_font: str) -> str:
    """Return isolated CSS; all estate colors/fonts arrive as brand tokens."""
    return f'''
.tp-sim {{ --sim-ink:{ink}; --sim-paper:{paper}; --sim-panel:{panel}; --sim-line:{line}; --sim-accent:{accent}; --sim-data:{data_font}; --sim-body:{body_font}; margin:52px 0; padding:30px; border:4px solid var(--sim-ink); background:var(--sim-paper); color:var(--sim-ink); }}
.tp-sim * {{ box-sizing:border-box; }}
.tp-sim-kicker {{ margin:0 0 8px; font:700 11px/1 var(--sim-data); letter-spacing:2px; color:var(--sim-accent); }}
.tp-sim > h2 {{ margin:0 0 10px; font:700 clamp(24px,3vw,34px)/1.08 var(--sim-data); text-transform:uppercase; }}
.tp-sim-lede {{ max-width:760px; margin:0 0 24px; font:17px/1.6 var(--sim-body); }}
.tp-sim-shell {{ display:grid; grid-template-columns:minmax(220px,300px) minmax(0,1fr); gap:22px; align-items:start; }}
.tp-sim-controls {{ display:grid; gap:18px; }}
.tp-sim-presets,.tp-sim-field {{ margin:0; padding:0; border:0; }}
.tp-sim-presets legend,.tp-sim-field>span,.tp-sim-field>legend {{ margin:0 0 8px; font:700 11px/1.2 var(--sim-data); letter-spacing:1px; text-transform:uppercase; }}
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
.tp-sim-field select {{ min-height:44px; width:100%; border:2px solid var(--sim-ink); background:var(--sim-panel); color:var(--sim-ink); padding:8px; font:700 11px/1.2 var(--sim-data); }}
.tp-sim-field small,.tp-sim-input-note {{ margin:0; font:12px/1.45 var(--sim-body); }} .tp-sim-day-error {{ color:var(--sim-accent); font-weight:700; }}
.tp-sim-app {{ position:relative; min-width:0; border:1px solid var(--sim-line); background:var(--sim-panel); overflow:hidden; color:var(--sim-ink); }}
.tp-sim-appbar {{ display:flex; align-items:center; justify-content:space-between; gap:16px; min-height:54px; padding:9px 14px; background:var(--sim-ink); color:var(--sim-paper); }} .tp-sim-appbar div {{ display:grid; }} .tp-sim-appbar span {{ font:700 9px/1 var(--sim-data); letter-spacing:1.8px; }} .tp-sim-appbar strong {{ font:700 14px/1.2 var(--sim-data); }} .tp-sim-appbar p {{ margin:0; max-width:60%; text-align:right; font:11px/1.35 var(--sim-data); }}
.tp-sim-weekbar {{ display:flex; justify-content:space-between; gap:16px; padding:10px 14px; border-bottom:1px solid var(--sim-line); }} .tp-sim-weekbar div {{ display:grid; gap:2px; }} .tp-sim-weekbar div:last-child {{ text-align:right; }} .tp-sim-weekbar span {{ font:700 8px/1 var(--sim-data); letter-spacing:1.3px; }} .tp-sim-weekbar strong {{ font:700 12px/1.2 var(--sim-data); }}
.tp-sim-calendar {{ display:grid; grid-template-columns:repeat(7,minmax(88px,1fr)); min-height:350px; overflow-x:auto; }}
.tp-sim-day {{ min-width:88px; border-right:1px solid var(--sim-line); }} .tp-sim-day:last-child {{ border-right:0; }} .tp-sim-day>header {{ display:flex; justify-content:space-between; gap:4px; min-height:34px; padding:8px; border-bottom:1px solid var(--sim-line); }} .tp-sim-day>header strong,.tp-sim-day>header span {{ font:700 9px/1 var(--sim-data); text-transform:uppercase; }} .tp-sim-day-sessions {{ display:grid; align-content:start; gap:6px; padding:6px; }}
.tp-sim-loading-tile,.tp-sim-rest {{ display:grid; min-height:58px; place-items:center; padding:6px; border:1px dashed var(--sim-line); font:9px/1.3 var(--sim-data); text-align:center; text-transform:uppercase; }}
.tp-sim-workout {{ width:100%; min-height:112px; display:grid; align-content:start; gap:5px; padding:7px; border:1px solid var(--sim-ink); border-top:5px solid var(--sim-accent); background:var(--sim-paper); color:var(--sim-ink); text-align:left; cursor:pointer; }} .tp-sim-workout:hover,.tp-sim-workout:focus-visible {{ outline:3px solid var(--sim-accent); outline-offset:1px; }} .tp-sim-workout-kind {{ font:700 7px/1 var(--sim-data); letter-spacing:1px; text-transform:uppercase; }} .tp-sim-workout-title {{ font:700 9px/1.25 var(--sim-data); }} .tp-sim-workout-meta {{ font:8px/1.2 var(--sim-data); }} .tp-sim-workout svg {{ width:100%; height:34px; border-top:1px solid var(--sim-line); border-bottom:1px solid var(--sim-line); }} .tp-sim-workout polyline {{ fill:none; stroke:var(--sim-accent); stroke-width:3; vector-effect:non-scaling-stroke; }}
.tp-sim-detail {{ position:absolute; inset:54px 0 0; z-index:4; padding:20px; overflow:auto; background:var(--sim-panel); }} .tp-sim-detail>[data-role=detail-close] {{ position:absolute; top:10px; right:10px; width:44px; height:44px; border:2px solid var(--sim-ink); background:var(--sim-paper); color:var(--sim-ink); font:28px/1 var(--sim-data); cursor:pointer; }} .tp-sim-detail>[data-role=detail-type] {{ margin:0 52px 5px 0; font:700 9px/1 var(--sim-data); letter-spacing:1.5px; color:var(--sim-accent); }} .tp-sim-detail h3 {{ margin:0 52px 6px 0; font:700 21px/1.15 var(--sim-data); }} .tp-sim-detail-meta {{ margin:0 0 15px; font:700 10px/1.3 var(--sim-data); text-transform:uppercase; }} .tp-sim-detail-graph svg {{ width:100%; height:110px; border:1px solid var(--sim-line); }} .tp-sim-detail-graph polyline {{ fill:none; stroke:var(--sim-accent); stroke-width:4; vector-effect:non-scaling-stroke; }} .tp-sim-detail-copy {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:14px; }} .tp-sim-detail-copy>div {{ border-top:3px solid var(--sim-ink); padding-top:8px; }} .tp-sim-detail-copy span,.tp-sim-notes span {{ font:700 8px/1 var(--sim-data); letter-spacing:1.2px; }} .tp-sim-detail-copy p,.tp-sim-notes p {{ margin:5px 0 0; font:14px/1.45 var(--sim-body); }} .tp-sim-steps {{ margin:16px 0 0; padding-left:22px; font:11px/1.5 var(--sim-data); }}
.tp-sim-notes {{ grid-template-columns:repeat(3,1fr); border-top:1px solid var(--sim-line); }} .tp-sim-notes article {{ padding:12px; border-right:1px solid var(--sim-line); }} .tp-sim-notes article:last-child {{ border-right:0; }}
.tp-sim-appfoot {{ display:flex; justify-content:space-between; gap:12px; padding:8px 12px; border-top:1px solid var(--sim-line); font:8px/1.3 var(--sim-data); letter-spacing:.5px; text-transform:uppercase; }}
.tp-sim-conversion {{ display:flex; align-items:center; justify-content:space-between; gap:20px; margin-top:22px; padding-top:20px; border-top:3px solid var(--sim-ink); }} .tp-sim-conversion p {{ max-width:640px; margin:0; font:15px/1.5 var(--sim-body); }} .tp-sim-cta {{ flex:none; display:inline-block; padding:13px 20px; border:3px solid var(--sim-ink); background:var(--sim-ink); color:var(--sim-paper); font:700 12px/1.2 var(--sim-data); letter-spacing:.8px; text-decoration:none; }} .tp-sim-cta:hover,.tp-sim-cta:focus-visible {{ background:var(--sim-accent); }}
@media(max-width:900px){{.tp-sim-shell{{grid-template-columns:1fr}}.tp-sim-presets>div{{grid-template-columns:repeat(3,1fr)}}.tp-sim-presets button{{grid-template-columns:1fr;text-align:center}}}}
@media(max-width:640px){{.tp-sim{{padding:20px 14px}}.tp-sim-presets>div{{grid-template-columns:1fr}}.tp-sim-presets button{{grid-template-columns:48px 1fr;text-align:left}}.tp-sim-calendar{{grid-template-columns:repeat(7,118px)}}.tp-sim-appbar{{align-items:flex-start}}.tp-sim-appbar p{{max-width:48%}}.tp-sim-notes{{grid-template-columns:1fr}}.tp-sim-notes article{{border-right:0;border-bottom:1px solid var(--sim-line)}}.tp-sim-detail-copy{{grid-template-columns:1fr}}.tp-sim-conversion{{align-items:stretch;flex-direction:column}}.tp-sim-cta{{text-align:center}}}}
@media(prefers-reduced-motion:reduce){{.tp-sim *{{scroll-behavior:auto!important}}}}
'''


def get_plan_simulator_js() -> str:
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
  function init(root){
    var configEl=document.getElementById(root.getAttribute('data-config-id'));if(!configEl)return;var config;try{config=JSON.parse(configEl.textContent);}catch(_error){return;}
    var controls=root.querySelector('[data-role=controls]');var app=root.querySelector('[data-role=app]');var hours=root.querySelector('[data-role=hours]');var hoursValue=root.querySelector('[data-role=hours-value]');var experience=root.querySelector('[data-role=experience]');var raceSelect=root.querySelector('[data-role=race]');var dayInputs=all(root,'.tp-sim-day-toggle input');var presets=all(root,'[data-preset]');var status=root.querySelector('[data-role=status]');var cta=root.querySelector('[data-role=cta]');var dayHelp=root.querySelector('[data-role=day-help]');var timer=null;var controller=null;var touched=false;var presetId='committed-8';var currentResponse=null;
    function selectedDays(){return dayInputs.filter(function(input){return input.checked;}).map(function(input){return input.value;});}
    function updateCta(){var url=new URL(cta.getAttribute('href'),window.location.origin);url.searchParams.set('race',config.race.slug);url.searchParams.set('hours',hours.value);url.searchParams.set('days',selectedDays().map(function(day){return DAY_LABELS[day];}).join(','));url.searchParams.set('experience',experience.value);cta.href=url.toString();}
    function requestBody(){return {schema_version:'training-plan-preview-request/v1',brand:config.brand,preset_id:presetId||undefined,race:config.race,rider:{hours_per_week:Number(hours.value),preferred_days:selectedDays(),experience_level:experience.value}};}
    function setLoading(){app.setAttribute('aria-busy','true');status.textContent='Building a '+hours.value+'-hour '+config.race.name+' week…';root.querySelector('[data-role=week-summary]').textContent=hours.value+' HOURS · '+selectedDays().length+' TRAINING DAYS';root.querySelector('[data-role=week-tss]').textContent='— TSS';}
    function setUnavailable(message){app.setAttribute('aria-busy','false');status.textContent=message||'Live preview temporarily unavailable.';all(root,'[data-calendar-day]').forEach(function(day){var box=day.querySelector('.tp-sim-day-sessions');clear(box);box.appendChild(textNode('span','Preview unavailable','tp-sim-loading-tile'));});root.querySelector('[data-role=notes]').hidden=true;root.querySelector('[data-role=versions]').textContent='Engine connection unavailable';}
    function showDetail(session){var detail=root.querySelector('[data-role=detail]');root.querySelector('[data-role=detail-type]').textContent=(session.kind||'workout').toUpperCase();root.querySelector('[data-role=detail-title]').textContent=session.title;root.querySelector('[data-role=detail-meta]').textContent=minutes(session.duration_minutes)+' · '+session.tss+' TSS'+(session.intensity_label?' · '+session.intensity_label:'');root.querySelector('[data-role=detail-fueling]').textContent=session.fueling_guidance||'No special fueling instruction for this session.';root.querySelector('[data-role=detail-coach]').textContent=session.coach_note||'Follow the written structure.';var graphBox=root.querySelector('[data-role=detail-graph]');clear(graphBox);var svg=graph(session.structure,110);if(svg)graphBox.appendChild(svg);else graphBox.appendChild(textNode('p','No structured graph for this calendar item.'));
      var steps=root.querySelector('[data-role=detail-steps]');clear(steps);var list=session.structure&&Array.isArray(session.structure.steps)?session.structure.steps:[];list.forEach(function(step){var target='';if(step.intensity_target_min!=null)target=Math.round(step.intensity_target_min*100)+(step.intensity_target_max!=null?'–'+Math.round(step.intensity_target_max*100):'')+'%';var cadence=step.cadence_rpm?' · '+step.cadence_rpm+' rpm':'';steps.appendChild(textNode('li',(step.type||'Step')+' · '+minutes(step.length_seconds/60)+(target?' · '+target:'')+cadence));});detail.hidden=false;detail.querySelector('[data-role=detail-close]').focus();}
    function render(response){if(!response||response.schema_version!=='training-plan-preview/v1'||!response.week||!Array.isArray(response.week.days)||response.week.days.length!==7)throw new Error('Bad preview contract');currentResponse=response;app.setAttribute('aria-busy','false');status.textContent='Built from '+config.race.name+' demands and your availability.';root.querySelector('[data-role=week-summary]').textContent=minutes(response.week.target_minutes).toUpperCase()+' · '+response.rider.preferred_days.length+' TRAINING DAYS';root.querySelector('[data-role=week-tss]').textContent=response.week.target_tss+' TSS';
      response.week.days.forEach(function(day,index){var column=root.querySelector('[data-calendar-day="'+day.day+'"]');if(!column)return;column.querySelector('header span').textContent=String(index+1).padStart(2,'0');var box=column.querySelector('.tp-sim-day-sessions');clear(box);if(!day.sessions.length){box.appendChild(textNode('span','Rest / mobility','tp-sim-rest'));return;}day.sessions.forEach(function(session){var button=document.createElement('button');button.type='button';button.className='tp-sim-workout';button.appendChild(textNode('span',(session.kind||'workout').toUpperCase(),'tp-sim-workout-kind'));button.appendChild(textNode('strong',session.title,'tp-sim-workout-title'));button.appendChild(textNode('span',minutes(session.duration_minutes)+' · '+session.tss+' TSS','tp-sim-workout-meta'));var svg=graph(session.structure,34);if(svg)button.appendChild(svg);button.addEventListener('click',function(){showDetail(session);});box.appendChild(button);});});
      var notes=root.querySelector('[data-role=notes]');notes.hidden=false;root.querySelector('[data-role=week-note]').textContent=response.week.coach_note;root.querySelector('[data-role=self-review]').textContent=response.week.weekly_self_review;root.querySelector('[data-role=comment-protocol]').textContent=response.week.comment_protocol;root.querySelector('[data-role=versions]').textContent='Engine '+shortVersion(response.engine_version)+' · Voice '+shortVersion(response.voice_version);root.dataset.engineVersion=response.engine_version;root.dataset.voiceVersion=response.voice_version;}
    function load(){if(controller)controller.abort();controller=typeof AbortController==='function'?new AbortController():null;setLoading();var endpoint=root.getAttribute('data-preview-endpoint')||config.endpoint;fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(requestBody()),signal:controller?controller.signal:undefined}).then(function(response){if(!response.ok)throw new Error('Preview '+response.status);return response.json();}).then(render).catch(function(error){if(error&&error.name==='AbortError')return;setUnavailable('Live preview temporarily unavailable. Your selections are saved for the full intake.');});}
    function schedule(immediate){clearTimeout(timer);updateCta();if(selectedDays().length<3)return;timer=setTimeout(load,immediate?0:350);if(touched&&typeof gtag==='function'){gtag('event','plan_preview_update',{source:'training_plan_simulator',race_slug:config.race.slug,hours_per_week:Number(hours.value),preferred_days_count:selectedDays().length,experience_level:experience.value,preset_id:presetId||'manual'});}}
    presets.forEach(function(button){button.setAttribute('aria-pressed',button.classList.contains('is-active')?'true':'false');button.addEventListener('click',function(){touched=true;presetId=button.getAttribute('data-preset');hours.value=button.getAttribute('data-hours');experience.value=button.getAttribute('data-experience');var wanted=button.getAttribute('data-days').split(',');dayInputs.forEach(function(input){input.checked=wanted.indexOf(input.value)!==-1;});presets.forEach(function(item){var active=item===button;item.classList.toggle('is-active',active);item.setAttribute('aria-pressed',active?'true':'false');});hoursValue.textContent=hours.value+' hours';dayHelp.classList.remove('tp-sim-day-error');schedule(true);});});
    controls.addEventListener('input',function(event){if(event.target===raceSelect&&Array.isArray(config.race_options)){var next=config.race_options.find(function(item){return item.slug===raceSelect.value;});if(next)config.race=next;}if(event.target.matches('.tp-sim-day-toggle input')&&selectedDays().length<3){event.target.checked=true;dayHelp.textContent='A useful preview needs at least three available days.';dayHelp.classList.add('tp-sim-day-error');return;}touched=true;presetId='';presets.forEach(function(item){item.classList.remove('is-active');item.setAttribute('aria-pressed','false');});hoursValue.textContent=hours.value+' hours';dayHelp.textContent='Choose at least three days.';dayHelp.classList.remove('tp-sim-day-error');schedule(false);});
    root.querySelector('[data-role=detail-close]').addEventListener('click',function(){root.querySelector('[data-role=detail]').hidden=true;});updateCta();schedule(true);
  }
  all(document,'[data-training-preview]').forEach(init);
})();
'''
