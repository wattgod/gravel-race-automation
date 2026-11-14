"""The public finish-time planner on race pages.

Guards what LAUNCH_DECISIONS (2026-11-12) asks of the page: the planner shows
only for an eligible or flagged race (read from data, not a list in code); the
engine is the unchanged frozen copy; the page says estimate, range, past
race-day weather and course edition; improvement rows are never summed; no
private material ships; a failed solve shows no time.
"""
import base64
import hashlib
import json
from html import escape as html_escape
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

import race_planner  # noqa: E402
from generate_neo_brutalist import generate_page, load_race_data  # noqa: E402

PLANNER_JS = ROOT / "wordpress" / "planner"
STATUS = json.loads((ROOT / "data" / "planner" / "status.json").read_text())
SHOWN = sorted(s for s, e in STATUS["races"].items() if e["status"] in ("eligible", "flagged"))
HELD = sorted(s for s, e in STATUS["races"].items() if e["status"] not in ("eligible", "flagged"))
# Pinned: the engine copied from the planner research workspace (v12).
ENGINE_SHA256 = "b57400ca2ae0fb8b339d1aeb608b16f20411f4f11d3fcdc8ade36e5e19dc06f7"


def page(slug):
    return generate_page(load_race_data(ROOT / "race-data" / f"{slug}.json"))


def section(html):
    m = re.search(r'<section id="finish-time".*?</section>', html, re.S)
    assert m, "planner section missing"
    return m.group(0)


def config(html):
    m = re.search(r'<script type="application/json" class="gg-planner-config">(.*?)</script>', html, re.S)
    return json.loads(m.group(1))


# ---------- which pages get it ----------

def test_pilot_statuses_are_imported():
    assert set(STATUS["races"]) == set(json.loads((ROOT / "data/planner/rollout.json").read_text())["races"])
    assert SHOWN, "no eligible or flagged race imported"


@pytest.mark.parametrize("slug", SHOWN)
def test_eligible_and_flagged_pages_carry_the_planner(slug):
    html = page(slug)
    sec = section(html)
    assert 'id="race-calculator"' not in html, "the planner replaces the Endure Labs handoff"
    cfg = config(html)
    assert cfg["slug"] == slug and cfg["status"] == STATUS["races"][slug]["status"]
    for flag in STATUS["races"][slug].get("flags", []):
        assert flag["text"] in sec or flag["text"][0].upper() + flag["text"][1:] in sec


@pytest.mark.parametrize("slug", HELD)
def test_held_pages_are_unchanged(slug):
    html = page(slug)
    assert 'id="finish-time"' not in html
    assert "gg-planner" not in html
    assert "/race/assets/planner/" not in html


def test_status_is_read_from_data_not_code(tmp_path, monkeypatch):
    """A held race becomes eligible upstream: after an import it shows, with no code change."""
    status = json.loads(json.dumps(STATUS))
    slug = HELD[0] if HELD else "mid-south"
    status["races"][slug] = {"status": "eligible", "flags": []}
    courses = tmp_path / "courses"
    courses.mkdir()
    shutil.copy(race_planner.course_path(SHOWN[0]), courses / f"{slug}.json")
    (tmp_path / "status.json").write_text(json.dumps(status))
    monkeypatch.setattr(race_planner, "STATUS_PATH", tmp_path / "status.json")
    monkeypatch.setattr(race_planner, "COURSES_DIR", courses)
    race_planner._status.cache_clear()
    try:
        assert race_planner.planner_shown(slug)
        assert 'id="finish-time"' in page(slug)
    finally:
        race_planner._status.cache_clear()


def test_unknown_or_bad_slug_gets_nothing():
    assert race_planner.build_race_planner({"slug": "not-a-race", "name": "X"}) == ""
    assert race_planner.build_race_planner({"slug": "../etc", "name": "X"}) == ""


# ---------- the engine and the shipped data ----------

def test_engine_is_the_unchanged_frozen_copy():
    sha = hashlib.sha256((PLANNER_JS / "engine7.js").read_bytes()).hexdigest()
    assert sha == ENGINE_SHA256 == STATUS["engine_sha256"]


@pytest.mark.parametrize("slug", SHOWN)
def test_course_files_hold_only_public_fields(slug):
    course = json.loads(race_planner.course_path(slug).read_text())
    assert set(course) == {"schema", "slug", "built", "route", "target_edition", "bins", "weather", "engine"}
    assert set(course["bins"]["cols"]) == {"g", "kap", "alt", "la", "lo", "h", "ok"}
    assert set(course["engine"]) == {"crr", "wf", "cap", "phi", "solo_cda_default"}
    assert all(ed["start_iso"] for ed in course["weather"]["editions"])


# Competitor names the repo must never mention, base64-encoded so this test
# does not mention them either.
COMPETITORS = [r"\b" + re.escape(n).replace(r"\ ", r"\s*") + r"\b"
               for n in base64.b64decode("YmVzdCBiaWtlIHNwbGl0fGJlc3RiaWtlc3BsaXR8YmJzfGRpcnQgZmFjdG9yfGRpcnRmYWN0b3I=").decode().split("|")]
PRIVATE = COMPETITORS + [r"reference rider", r"mapbox",
           r"private demo", r"\bdev\b panel", r"development (rider|data)", r"sensor", r"accuracy of",
           r"\d+(\.\d+)?% (typical )?(miss|error)", r"within \d+%", r"4 times in 5", r"athlete",
           r"matti_", r"tier b"]


def shipped_text():
    files = [*PLANNER_JS.glob("gg-planner*.js"), ROOT / "wordpress" / "race_planner.py",
             ROOT / "scripts" / "import_planner_bundles.py", ROOT / "data/planner/status.json",
             ROOT / "data/planner/gear.json", *(ROOT / "data/planner/courses").glob("*.json")]
    return {f.name: f.read_text() for f in files}


@pytest.mark.parametrize("pattern", PRIVATE)
def test_no_private_material_ships(pattern):
    for name, text in shipped_text().items():
        assert not re.search(pattern, text, re.I), f"{pattern!r} in {name}"
    for slug in SHOWN:
        assert not re.search(pattern, section(page(slug)), re.I)


# ---------- page code rules ----------

@pytest.mark.parametrize("name", ["gg-planner.js", "gg-planner-worker.js", "gg-planner-core.js"])
def test_no_innerhtml_or_inline_handlers(name):
    js = (PLANNER_JS / name).read_text()
    assert "innerHTML" not in js and "outerHTML" not in js and "insertAdjacentHTML" not in js
    assert "document.write" not in js and "eval(" not in js


def test_section_has_no_inline_handlers_and_safe_config():
    sec = section(page(SHOWN[0]))
    assert not re.search(r"\son[a-z]+=", sec)
    cfg_raw = re.search(r'class="gg-planner-config">(.*?)</script>', sec, re.S).group(1)
    assert "<" not in cfg_raw


def test_analytics_events_go_through_gtag_behind_consent():
    js = (PLANNER_JS / "gg-planner.js").read_text()
    cfg = config(page(SHOWN[0]))
    assert cfg["events"] == {"result": "planner_result_shown", "cta": "plan_cta_click"}
    assert js.count('typeof gtag !== "function"') + js.count('typeof gtag === "function"') >= 2
    assert "gtag(\"event\", cfg.events.result" in js and "gtag(\"event\", cfg.events.cta" in js
    # fired from user actions only: no timers drive an event
    assert not re.search(r"setInterval", js)
    # the result event fires once per page view, not on every recalculation
    announce = re.search(r"function announce\(m\) \{(.*?)\n  \}", js, re.S).group(1)
    assert "if (shownOnce || typeof gtag !== \"function\") return;" in announce
    assert announce.index("shownOnce = true") < announce.index("gtag(\"event\"")
    assert js.count("shownOnce = true") == 1
    # the page's section-view observer fires on visibility, including on load:
    # the planner is not registered with it
    opening = re.match(r"<section[^>]*>", section(page(SHOWN[0]))).group(0)
    assert "data-measure-section" not in opening


def test_plan_button_goes_to_the_existing_checkout():
    cfg = config(page("unbound-200"))
    assert cfg["offer"]["href"] == "https://gravelgodcycling.com/training-plans/start/?race=unbound-200&src=race_planner"
    from pricing import PRICE_PER_WEEK
    assert cfg["offer"]["price"] == f"{PRICE_PER_WEEK} / week"
    # a weekly price next to "one-time payment" must say how the two fit
    from pricing import MIN_WEEKS
    assert cfg["offer"]["price_note"] == (f"Priced by the weeks until race day ({PRICE_PER_WEEK} a week, "
                                          f"{MIN_WEEKS}-week minimum), paid once at checkout.")
    assert "o.price_note" in (PLANNER_JS / "gg-planner.js").read_text()


def test_fuel_brackets_come_from_the_pipeline():
    sys.path.insert(0, str(ROOT / "pipeline"))
    from nutrition import DURATION_BRACKETS
    assert config(page(SHOWN[0]))["brackets"] == [list(b) for b in DURATION_BRACKETS]


# ---------- what the page says ----------

def test_wording():
    js = (PLANNER_JS / "gg-planner.js").read_text()
    sec = section(page("unbound-200"))
    assert "estimate" in js.lower() and "if you ride a level easier or harder" in js and "not an accuracy figure" in js
    assert "not added together" in js
    assert "not a forecast" in sec and "race day" in sec
    assert "2025 route" in sec and "The 2027 route isn't published yet." in sec
    assert "Effort (IF)" in sec and "IF " in js and "Type your own" in js
    assert '[1.03, "+3%"], [1.05, "+5%"], [1.10, "+10%"]' in js
    for word in ("total saving", "in total you", "combined", "all together"):
        assert word not in js.lower()
    # the brand is not a narrator ("Gravel God's default ...")
    for text in (js, sec):
        assert "Gravel God's" not in text and "Gravel God’s" not in text


def test_marker_opens_the_collapsed_source_list_on_phones():
    """On phones the page's Sources section starts collapsed; a planner [n]
    opens it through its own header before the jump."""
    js = (PLANNER_JS / "gg-planner.js").read_text()
    handler = re.search(r'section\.addEventListener\("click", function \(e\) \{(.*?)\n  \}\);', js, re.S).group(1)
    assert 'closest(".gg-planner-cite")' in handler
    assert 'classList.contains("gg-section-collapsed")' in handler and "header.click()" in handler


def test_size_rows_have_no_preselected_size():
    """Fitness (LAUNCH_DECISIONS 8), Position and Quicker stops are sizes the
    rider picks; the page starts with none picked."""
    js = (PLANNER_JS / "gg-planner.js").read_text()
    assert "var picks = { fit: null, pos: null, stopsCut: null };" in js


@pytest.mark.parametrize("slug", SHOWN)
def test_every_planner_marker_resolves_to_the_page_source_list(slug):
    html = page(slug)
    cfg = config(html)
    rd = load_race_data(ROOT / "race-data" / f"{slug}.json")
    n_race = len(rd.get("citations") or [])
    assert sorted(cfg["cite"].values()) == list(range(n_race + 1, n_race + 1 + len(race_planner.PLANNER_SOURCES)))
    items = re.findall(r'<li class="gg-citation-item" id="gg-citation-(\d+)">', html)
    assert [int(i) for i in items] == list(range(1, n_race + 1 + len(race_planner.PLANNER_SOURCES)))
    for n in re.findall(r'class="gg-planner-cite" href="#gg-citation-(\d+)">\[(\d+)\]', section(html)):
        assert n[0] == n[1] and int(n[0]) in cfg["cite"].values()
    js = (PLANNER_JS / "gg-planner.js").read_text()
    for key in re.findall(r'\{ cite: "([a-z_]+)" \}', js):
        assert key in cfg["cite"], key
    for key, label, _url in race_planner.PLANNER_SOURCES:
        assert re.search(r'id="gg-citation-%d">.*?%s' % (cfg["cite"][key], re.escape(html_escape(label))), html, re.S)
    # no author-year attribution left in visible planner copy: markers only
    for text in (section(html), js):
        for name in ("Smith et al", "Racinais", "Peiffer", "Defraeye", "Broker, Kyle", "Garmin's Edge"):
            assert name not in text, name


def test_unconfirmed_edition_is_said_as_it_is():
    flagged = [s for s in SHOWN if any(f["kind"] == "edition" for f in STATUS["races"][s].get("flags", []))]
    for slug in flagged:
        cfg = config(page(slug))
        assert "edition not confirmed" in cfg["edition_line"] and cfg["edition_short"] == "route edition not confirmed"


def test_climbing_heavy_gets_the_same_range_and_a_note():
    """Amendment 2: same effort span on climbing-heavy courses, plus the note;
    never a 'wider range'."""
    js = (PLANNER_JS / "gg-planner.js").read_text()
    assert "span_steps" not in js and "spanSteps" not in (PLANNER_JS / "gg-planner-core.js").read_text()
    for slug in SHOWN:
        kinds = {f["kind"] for f in STATUS["races"][slug].get("flags", [])}
        cfg = config(page(slug))
        assert "span_steps" not in cfg
        assert "wider" not in section(page(slug)).lower()
        if "climbing" in kinds:
            assert any("less certain and may read slow" in n for n in cfg["notes"])


def test_range_is_one_level_each_way_mirrored_at_the_ends():
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    script = (
        "const E=require(process.argv[1]),c=require(process.argv[2]),h=6,out={};"
        "for(const l of c.LEVELS){const d=E.ifDefault(l,h);"
        "out[l]={here:d,def:c.effortSpan(E,l,d,h),typed:c.effortSpan(E,l,0.7,h)};}"
        "out.curve=Object.fromEntries(c.LEVELS.map(l=>[l,E.ifDefault(l,h)]));"
        "process.stdout.write(JSON.stringify(out));"
    )
    res = subprocess.run(["node", "-e", script, str(PLANNER_JS / "engine7.js"), str(PLANNER_JS / "gg-planner-core.js")],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    curve, levels = out["curve"], ["beginner", "intermediate", "advanced", "elite"]
    for i, lvl in enumerate(levels):
        up = curve[levels[i + 1]] - curve[lvl] if i < 3 else None
        dn = curve[lvl] - curve[levels[i - 1]] if i > 0 else None
        up, dn = (up if up is not None else dn), (dn if dn is not None else up)
        span = out[lvl]["def"]
        assert span["up"] == pytest.approx(up) and span["dn"] == pytest.approx(dn), lvl
        assert span["fast"] == pytest.approx(min(1.05, out[lvl]["here"] + up))
        assert span["slow"] == pytest.approx(max(0.40, out[lvl]["here"] - dn))
        typed = out[lvl]["typed"]
        assert typed["fast"] == pytest.approx(0.7 + up) and typed["slow"] == pytest.approx(0.7 - dn), lvl


def test_assets_written_are_hashed_and_only_for_shown_races(tmp_path):
    assert race_planner.write_planner_assets(tmp_path, HELD) == []
    assert not (tmp_path / "assets").exists(), "a held race writes nothing"
    names = race_planner.write_planner_assets(tmp_path, list(STATUS["races"]))
    out = {p.name for p in (tmp_path / "assets" / "planner").iterdir()}
    assert out == set(names)
    for slug in SHOWN:
        assert any(n.startswith(slug + ".") for n in names)
    for slug in HELD:
        assert not any(n.startswith(slug + ".") for n in names)
    assert any(re.fullmatch(r"engine7\.[0-9a-f]{8}\.js", n) for n in names)
    # a single-race build into the same folder leaves other races' courses alone
    race_planner.write_planner_assets(tmp_path, [SHOWN[0]])
    assert {p.name for p in (tmp_path / "assets" / "planner").iterdir()} == out


def test_release_contract_accepts_the_planner_in_place_of_the_calculator():
    sys.path.insert(0, str(ROOT / "scripts"))
    import prepare_race_release as release
    slug = SHOWN[0]
    html = page(slug)
    parsed = release.Markup(); parsed.feed(html)
    hrefs = [a["href"] for a in parsed.anchors if a.get("data-cta") == "approved_custom_plan"]
    release.verify_page_contract(html, slug, hrefs)
    with pytest.raises(ValueError, match="Calculator"):
        release.verify_page_contract(html, "other-race", hrefs)


def test_release_package_must_ship_every_planner_asset_the_config_loads(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import prepare_race_release as release
    slug, other = SHOWN[0], SHOWN[1]
    pages = tmp_path / "pages"
    pages.mkdir()
    html = page(slug)
    race_planner.write_planner_assets(pages, [slug])
    release.verify_planner_assets(pages, slug, html)
    with pytest.raises(ValueError, match="does not belong"):
        release.verify_planner_assets(pages, other, html)
    worker = pages / "assets" / "planner" / config(html)["worker_url"].rsplit("/", 1)[1]
    worker.write_text(worker.read_text() + "\n")
    with pytest.raises(ValueError, match="worker_url"):
        release.verify_planner_assets(pages, slug, html)
    worker.unlink()
    with pytest.raises(ValueError, match="worker_url"):
        release.verify_planner_assets(pages, slug, html)


# ---------- the model runs on every shown course ----------

@pytest.fixture(scope="module")
def solved():
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    sys.path.insert(0, str(ROOT / "pipeline"))
    from nutrition import DURATION_BRACKETS
    res = subprocess.run(["node", str(ROOT / "tests" / "race_planner_solve.cjs"),
                          json.dumps([list(b) for b in DURATION_BRACKETS])],
                         capture_output=True, text=True, timeout=300)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


@pytest.mark.parametrize("slug", SHOWN)
def test_sample_rider_gets_a_time_on_every_shown_course(solved, slug):
    r = solved[slug]
    assert r["ok"], r
    assert 0 < r["fast_s"] <= r["mid_s"] <= r["slow_s"] < 30 * 3600
    keys = [row["key"] for row in r["rows"]]
    assert keys[:3] == ["fit", "gut", "heat"]
    assert all("saved_s" in row or "why" in row or row.get("ask") or row.get("already") for row in r["rows"])


@pytest.mark.parametrize("slug", SHOWN)
def test_unpicked_sizes_give_no_number(solved, slug):
    rows = {row["key"]: row for row in solved[slug]["rows_unpicked"]}
    for key in ("fit", "pos", "stops"):
        assert rows[key] == {"key": key, "pick": True}, key


@pytest.mark.parametrize("slug", SHOWN)
def test_a_failed_solve_shows_no_time_and_says_why(solved, slug):
    r = solved[slug]
    assert r["broken"] == {"ok": False, "why": "the course data has a gap", "has_time": False}
    assert r["solver_fail"]["ok"] is False and r["solver_fail"]["has_time"] is False
    assert r["solver_fail"]["why"].startswith("solve:")
    assert r["uncovered"] == {"ok": False, "has_time": False,
                              "why": "the past race-day weather does not cover your predicted time on course"}
    assert r["empty_weather"] == {"ok": False, "has_time": False, "why": "weather file has no hours or uneven columns"}
    assert r["no_crr"] == {"ok": False, "has_time": False, "why": "the model settings for this course are incomplete"}
