#!/usr/bin/env python3
"""Generate the pick'em pages: one per game in data/pickem/.

    python3 wordpress/generate_pickem.py [--output-dir DIR]

Writes {output}/pickem/{game}/index.html, which --sync-pages deploys to
/race/pickem/{game}/. Before the lock the page is the entry form; once
data/pickem/<game file>-leaderboard.json exists it shows the official podium
and the leaderboard instead.
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
from brand_tokens import (  # noqa: E402
    SITE_BASE_URL, get_favicon_head_snippet, get_font_face_css, get_ga4_head_snippet,
    get_preload_hints, get_tokens_css,
)
from cookie_consent import get_consent_banner_html  # noqa: E402
from pickem import CATEGORIES, PLACES, leaderboard_path, load_games, lock_time, rider_names  # noqa: E402
from shared_header import get_site_header_css, get_site_header_html, get_site_header_js  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_TZ = ZoneInfo("America/Chicago")


def esc(text) -> str:
    if text is None:
        return ""
    return html_mod.escape(str(text), quote=True)


def lock_label(game: dict) -> str:
    local = lock_time(game).astimezone(RACE_TZ)
    hour = local.strftime("%I:%M").lstrip("0")
    return f"{local.strftime('%A, %B')} {local.day}, {local.year}, {hour} {local.strftime('%p').lower()} {local.tzname()}"


def load_leaderboard(game: dict) -> dict | None:
    path = leaderboard_path(game)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build_racing(game: dict) -> str:
    """One-tap radio chips: is this rider racing it, and which distance."""
    chips = "".join(
        f'<label class="gg-pk-chip"><input type="radio" name="racing" value="{esc(o["value"])}" required>'
        f'<span>{esc(o["label"])}</span></label>'
        for o in game["racing"]["options"]
    )
    return (f'<fieldset class="gg-pk-racing"><legend>{esc(game["racing"]["question"])}</legend>'
            f'<div class="gg-pk-chips">{chips}</div></fieldset>')


def build_form(game: dict) -> str:
    datalists, fieldsets = [], []
    for cat, label in CATEGORIES:
        list_id = f"gg-pk-riders-{cat}"
        options = "".join(f'<option value="{esc(n)}"></option>' for n in rider_names(game, cat))
        datalists.append(f'<datalist id="{list_id}">{options}</datalist>')
        rows = []
        for i, place in enumerate(PLACES):
            input_id = f"gg-pk-{cat}-{i + 1}"
            rows.append(
                f'<div class="gg-pk-row"><label for="{input_id}">{place}</label>'
                f'<input id="{input_id}" name="{cat}_{i + 1}" type="text" list="{list_id}" '
                f'data-pick="{cat}" data-place="{i}" maxlength="80" autocomplete="off" required></div>'
            )
        fieldsets.append(
            f'<fieldset class="gg-pk-podium"><legend>{label}</legend>{"".join(rows)}</fieldset>'
        )
    return f'''<form id="gg-pk-form" class="gg-pk-form" novalidate
      data-worker="{esc(game['worker_url'])}" data-game="{esc(game['game'])}" data-lock="{esc(game['lock_utc'])}">
    <div class="gg-pk-podiums">{"".join(fieldsets)}</div>
    {"".join(datalists)}
    <div class="gg-pk-you">
      {build_racing(game)}
      <div class="gg-pk-row"><label for="gg-pk-email">Email</label>
        <input id="gg-pk-email" name="email" type="email" autocomplete="email" maxlength="254" required></div>
      <div class="gg-pk-row"><label for="gg-pk-name">Leaderboard name</label>
        <input id="gg-pk-name" name="display_name" type="text" autocomplete="nickname" maxlength="40" required></div>
      <label class="gg-pk-check"><input id="gg-pk-optin" name="opt_in" type="checkbox"> Email me the results and Unbound news</label>
      <div class="gg-pk-hp" aria-hidden="true"><label for="gg-pk-website">Website</label>
        <input id="gg-pk-website" name="website" type="text" tabindex="-1" autocomplete="off"></div>
    </div>
    <button type="submit" class="gg-pk-submit">Save picks</button>
    <p id="gg-pk-status" class="gg-pk-status" role="status" aria-live="polite"></p>
  </form>'''


def build_leaderboard(board: dict) -> str:
    podiums = []
    for cat, label in CATEGORIES:
        names = board.get("results", {}).get(cat) or []
        items = "".join(f"<li>{esc(n)}</li>" for n in names)
        podiums.append(f'<div class="gg-pk-result"><h3>{label}</h3><ol>{items}</ol></div>')
    rows = "".join(
        f'<tr><td>{int(r["rank"])}</td><td>{esc(r["display_name"])}</td><td>{int(r["points"])}</td></tr>'
        for r in board.get("entries", [])
    )
    return f'''<section class="gg-pk-board" id="leaderboard">
    <h2>Podium</h2>
    <div class="gg-pk-results">{"".join(podiums)}</div>
    <h2>Leaderboard</h2>
    <table class="gg-pk-table">
      <thead><tr><th scope="col">#</th><th scope="col">Name</th><th scope="col">Points</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </section>'''


PAGE_JS = r"""
(function () {
  var form = document.getElementById('gg-pk-form');
  if (!form) return;
  var status = document.getElementById('gg-pk-status');
  var button = form.querySelector('.gg-pk-submit');
  var lockAt = Date.parse(form.getAttribute('data-lock'));
  var storeKey = 'gg-pickem-' + form.getAttribute('data-game');

  function say(text, kind) {
    status.textContent = text;
    status.className = 'gg-pk-status' + (kind ? ' gg-pk-status--' + kind : '');
  }
  function lock() {
    Array.prototype.forEach.call(form.elements, function (el) { el.disabled = true; });
    form.classList.add('gg-pk-form--locked');
    button.textContent = 'Picks locked';
  }
  function picks() {
    var out = { women: ['', '', ''], men: ['', '', ''] };
    form.querySelectorAll('[data-pick]').forEach(function (el) {
      out[el.getAttribute('data-pick')][+el.getAttribute('data-place')] = el.value.trim();
    });
    return out;
  }

  if (Date.now() >= lockAt) { lock(); return; }

  try {
    var saved = JSON.parse(localStorage.getItem(storeKey) || 'null');
    if (saved && saved.picks) {
      form.querySelectorAll('[data-pick]').forEach(function (el) {
        var v = saved.picks[el.getAttribute('data-pick')];
        if (v && typeof v[+el.getAttribute('data-place')] === 'string') el.value = v[+el.getAttribute('data-place')];
      });
      if (typeof saved.display_name === 'string') form.elements.display_name.value = saved.display_name;
      if (typeof saved.racing === 'string') {
        form.querySelectorAll('input[name="racing"]').forEach(function (el) { el.checked = el.value === saved.racing; });
      }
    }
  } catch (e) {}

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    if (Date.now() >= lockAt) { lock(); say('Picks are locked.', 'error'); return; }
    var p = picks();
    var cats = { women: "women's", men: "men's" };
    for (var cat in cats) {
      if (p[cat].some(function (v) { return !v; })) { say('Pick 1st, 2nd and 3rd for the ' + cats[cat] + ' podium.', 'error'); return; }
      var lower = p[cat].map(function (v) { return v.toLowerCase(); });
      if (new Set(lower).size !== 3) { say('Same rider twice in the ' + cats[cat] + ' podium.', 'error'); return; }
    }
    var racingEl = form.querySelector('input[name="racing"]:checked');
    if (!racingEl) { say('Answer: ' + form.querySelector('.gg-pk-racing legend').textContent, 'error'); form.querySelector('input[name="racing"]').focus(); return; }
    if (!form.elements.email.checkValidity()) { say('Enter a valid email.', 'error'); form.elements.email.focus(); return; }
    var name = form.elements.display_name.value.trim();
    if (!name) { say('Enter a leaderboard name.', 'error'); form.elements.display_name.focus(); return; }

    var payload = {
      game: form.getAttribute('data-game'),
      email: form.elements.email.value.trim(),
      display_name: name,
      opt_in: form.elements.opt_in.checked,
      racing: racingEl.value,
      picks: p,
      website: form.elements.website.value
    };
    button.disabled = true;
    button.textContent = 'Saving...';
    say('', '');
    fetch(form.getAttribute('data-worker'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function (resp) {
      return resp.json().catch(function () { return {}; }).then(function (body) { return { ok: resp.ok, body: body }; });
    }).then(function (res) {
      if (res.ok && res.body.success) {
        try { localStorage.setItem(storeKey, JSON.stringify({ picks: p, display_name: name, racing: payload.racing })); } catch (e) {}
        say(res.body.replaced
          ? 'Saved. These picks replaced your earlier ones.'
          : 'Saved. To change them before the start, send the form again with the same email.', 'ok');
        if (typeof gtag === 'function') {
          gtag('event', 'pickem_submit', { game: payload.game, replaced: Boolean(res.body.replaced), opt_in: payload.opt_in });
        }
      } else if (res.body.locked) {
        lock();
        say('Picks are locked.', 'error');
        return;
      } else {
        say(res.body.error || 'Could not save. Try again.', 'error');
      }
      button.disabled = false;
      button.textContent = 'Save picks';
    }).catch(function () {
      say('Could not save. Check your connection and try again.', 'error');
      button.disabled = false;
      button.textContent = 'Save picks';
    });
  });
})();
"""


PAGE_CSS = """
body { margin: 0; background: var(--gg-color-warm-paper); }
*, *::before, *::after { border-radius: 0 !important; box-shadow: none !important; box-sizing: border-box; }
.gg-pk-page { max-width: 880px; margin: 0 auto; padding: 0 16px 48px; font-family: var(--gg-font-data); color: var(--gg-color-dark-brown); }
.gg-pk-breadcrumb { font-size: 11px; color: var(--gg-color-secondary-brown); padding: 12px 0; letter-spacing: 0.5px; }
.gg-pk-breadcrumb a { color: var(--gg-color-secondary-brown); }
.gg-pk-hero { border: 3px solid var(--gg-color-dark-brown); background: var(--gg-color-dark-brown); color: var(--gg-color-warm-paper); padding: 24px; margin-bottom: 24px; }
.gg-pk-hero h1 { font-size: 32px; line-height: 1.15; margin: 0 0 12px; text-transform: uppercase; letter-spacing: 1px; }
.gg-pk-facts { margin: 0; padding: 0; list-style: none; font-size: 13px; line-height: 1.7; }
.gg-pk-facts strong { color: var(--gg-color-gold); }
.gg-pk-podiums { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.gg-pk-podium, .gg-pk-you { border: 3px solid var(--gg-color-dark-brown); background: var(--gg-color-white); margin: 0 0 16px; padding: 16px; min-width: 0; }
.gg-pk-podium legend { font-weight: 700; text-transform: uppercase; letter-spacing: 1px; padding: 0 6px; background: var(--gg-color-warm-paper); border: 2px solid var(--gg-color-dark-brown); }
.gg-pk-row { display: grid; grid-template-columns: 4.5em 1fr; align-items: center; gap: 8px; margin-top: 10px; }
.gg-pk-you .gg-pk-row { grid-template-columns: 1fr; gap: 4px; }
.gg-pk-row label { font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
.gg-pk-form input[type=text], .gg-pk-form input[type=email] { width: 100%; min-width: 0; font: inherit; font-size: 16px; padding: 10px; border: 2px solid var(--gg-color-dark-brown); background: var(--gg-color-warm-paper); color: var(--gg-color-dark-brown); }
.gg-pk-form input:focus { outline: 3px solid var(--gg-color-teal); outline-offset: 0; }
.gg-pk-racing { border: 0; margin: 0; padding: 0; min-width: 0; }
.gg-pk-racing legend { padding: 0; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
.gg-pk-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; }
.gg-pk-chip { position: relative; flex: 1 1 auto; cursor: pointer; }
.gg-pk-chip input { position: absolute; opacity: 0; width: 1px; height: 1px; margin: 0; }
.gg-pk-chip span { display: block; min-height: 44px; padding: 10px 14px; text-align: center; font-size: 15px; font-weight: 700; border: 2px solid var(--gg-color-dark-brown); background: var(--gg-color-warm-paper); white-space: nowrap; }
.gg-pk-chip input:checked + span { background: var(--gg-color-dark-brown); color: var(--gg-color-warm-paper); }
.gg-pk-chip input:focus-visible + span { outline: 3px solid var(--gg-color-teal); outline-offset: 0; }
.gg-pk-check { display: flex; gap: 10px; align-items: flex-start; margin-top: 14px; font-size: 14px; line-height: 1.4; cursor: pointer; }
.gg-pk-check input { width: 20px; height: 20px; margin: 0; flex: none; accent-color: var(--gg-color-teal); }
.gg-pk-hp { position: absolute; left: -9999px; width: 1px; height: 1px; overflow: hidden; }
.gg-pk-submit { display: block; width: 100%; min-height: 52px; font: inherit; font-size: 16px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: var(--gg-color-white); background: var(--gg-color-teal); border: 3px solid var(--gg-color-dark-brown); cursor: pointer; }
.gg-pk-submit:hover { background: var(--gg-color-dark-brown); }
.gg-pk-form--locked { opacity: 0.5; }
.gg-pk-form--locked .gg-pk-submit { cursor: not-allowed; background: var(--gg-color-secondary-brown); }
.gg-pk-status { min-height: 1.5em; margin: 12px 0 0; font-size: 15px; font-weight: 700; }
.gg-pk-status--ok { border-left: 4px solid var(--gg-color-teal); padding-left: 10px; }
.gg-pk-status--error { border-left: 4px solid var(--gg-color-gold); padding-left: 10px; }
.gg-pk-board h2 { font-size: 20px; text-transform: uppercase; letter-spacing: 1px; border-bottom: 3px solid var(--gg-color-dark-brown); padding-bottom: 6px; }
.gg-pk-results { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.gg-pk-result { border: 3px solid var(--gg-color-dark-brown); background: var(--gg-color-white); padding: 12px 16px; }
.gg-pk-result h3 { margin: 0 0 6px; font-size: 14px; text-transform: uppercase; }
.gg-pk-result ol { margin: 0; padding-left: 1.4em; font-family: var(--gg-font-editorial); font-size: 16px; line-height: 1.6; }
.gg-pk-table { width: 100%; border-collapse: collapse; background: var(--gg-color-white); border: 3px solid var(--gg-color-dark-brown); }
.gg-pk-table th, .gg-pk-table td { text-align: left; padding: 8px 12px; border-bottom: 2px solid var(--gg-color-dark-brown); font-size: 14px; }
.gg-pk-table td:last-child, .gg-pk-table th:last-child { text-align: right; }
@media (max-width: 640px) {
  .gg-pk-hero { padding: 18px 16px; }
  .gg-pk-hero h1 { font-size: 24px; }
  .gg-pk-podiums, .gg-pk-results { grid-template-columns: 1fr; gap: 0; }
  .gg-pk-podium, .gg-pk-you { padding: 12px; }
  .gg-pk-row { grid-template-columns: 2.6em 1fr; }
  .gg-pk-results { gap: 12px; }
}
"""


def build_page(game: dict, board: dict | None = None) -> str:
    year = game["edition"]
    race = game["race_name"]
    canonical = f"{SITE_BASE_URL}{game['path']}"
    title = f"{race} {year} Pick'em | Gravel God"
    description = f"Pick the elite women's and men's podiums for {race} {year}."
    race_url = f"/race/{game['race_slug']}/"
    if board:
        body = build_leaderboard(board)
        facts = f'<li><strong>{len(board.get("entries", []))}</strong> entries scored</li>'
    else:
        body = build_form(game)
        facts = (
            f'<li><strong>Locks at the start:</strong> {esc(lock_label(game))}</li>'
            f'<li><strong>3 points:</strong> right rider, right place</li>'
            f'<li><strong>1 point:</strong> podium rider, wrong place</li>'
        )
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical)}">
  {get_favicon_head_snippet()}
  {get_preload_hints()}
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical)}">
  <style>
{get_font_face_css()}
{get_tokens_css()}
{get_site_header_css()}
{PAGE_CSS}
  </style>
  {get_ga4_head_snippet()}
</head>
<body>
<div class="gg-pk-page">
  {get_site_header_html(active="races")}
  <div class="gg-pk-breadcrumb"><a href="/">Home</a> &rsaquo; <a href="{esc(race_url)}">{esc(race)}</a> &rsaquo; Pick'em</div>
  <section class="gg-pk-hero">
    <h1>{esc(race)} {year} pick'em</h1>
    <ul class="gg-pk-facts">{facts}</ul>
  </section>
  {body}
</div>
<script>{get_site_header_js()}</script>
<script>{PAGE_JS}</script>
{get_consent_banner_html()}
</body>
</html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate pick'em pages")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    output_dir = Path(args.output_dir) if args.output_dir else PROJECT_ROOT / "wordpress" / "output"
    for game in load_games():
        rel = game["path"].strip("/").removeprefix("race/")
        page_dir = output_dir / rel
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "index.html").write_text(build_page(game, load_leaderboard(game)), encoding="utf-8")
        print(f"Generated {rel}/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
