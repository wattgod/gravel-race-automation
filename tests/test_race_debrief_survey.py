"""The race debrief at /race-debrief/ (variant `race_debrief`).

For everyone who bought a plan: the TrainingPeaks marketplace plans and the
custom plans. One renderer draws every questionnaire
(generate_season_review.py); these tests pin what is different about this
one: its own URL and source, worker-only transport, the ?plan= / ?ref= hidden
fields and their validation, its own GA4 events, the TP rating line, the
reused "On the Record" block, and that every answer it can post fits every cap
on the way through. The browser run is tests/test_race_debrief_playwright.py;
the Mission Control side is mission_control/tests/test_plan_debrief.py.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.insert(0, str(ROOT / "scripts"))

from generate_season_review import (  # noqa: E402
    PERSONAL_PARAMS,
    TP_PLAN_URL,
    WORKER_SOURCES,
    answer_keys,
    build_season_review_js,
    generate_season_review_page,
    input_names,
    max_answer_chars,
    output_name,
    page_path,
)
from season_review_variants import (  # noqa: E402
    EXIT,
    PLAN_ID_PATTERN,
    PLAN_REF_PATTERN,
    RACE_DEBRIEF,
    VARIANTS,
)

WORKER_PATH = ROOT / "workers" / "fueling-lead-intake" / "worker.js"
WORKER = WORKER_PATH.read_text(encoding="utf-8")
WEBHOOKS = (ROOT / "mission_control" / "routers" / "webhooks.py").read_text(encoding="utf-8")
FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "race_debrief_submission.json").read_text(encoding="utf-8"))
ROADIE_FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "race_debrief_submission_roadie.json").read_text(encoding="utf-8"))
# The Roadie Labs page (road-race-automation wordpress/generate_race_debrief.py)
# names its own site and social channel; its tests pin the same strings.
ROADIE_CHANNELS = {
    "where_site": "roadielabs.com",
    "where_social": "Roadie Labs social posts",
    "where_email": "Emails to riders choosing a plan",
    "where_tp": "The plan's TrainingPeaks page",
}


@pytest.fixture(scope="module")
def doc() -> str:
    return generate_season_review_page("race_debrief")


@pytest.fixture(scope="module")
def form(doc) -> str:
    return doc[doc.index('<form id="season-form"'):doc.index("</form>")]


@pytest.fixture(scope="module")
def js() -> str:
    return build_season_review_js(RACE_DEBRIEF)


def _field(name, variant=RACE_DEBRIEF):
    for sec in variant["sections"]:
        for f in sec["fields"]:
            for g in f.get("fields", [f]):
                if g.get("name") == name:
                    return g
    raise KeyError(name)


def _group(form_html: str, name: str) -> str:
    start = form_html.index(f'data-radio="{name}"')
    return form_html[form_html.rindex("<div", 0, start):form_html.index("</div></div>", start)]


def _worker_consts(*names) -> dict:
    """The worker's own constants, read by running it in node."""
    src = WORKER + f"\nexport const __TEST__ = {{ {', '.join(names)} }};\n"
    script = ("const src = require('fs').readFileSync(0, 'utf8');"
              "import('data:text/javascript;base64,' + Buffer.from(src).toString('base64'))"
              ".then((m) => process.stdout.write(JSON.stringify(m.__TEST__, (k, v) => v instanceof RegExp ? v.source : v)));")
    run = subprocess.run(["node", "-e", script], input=src, capture_output=True, text=True, timeout=60, check=True)
    return json.loads(run.stdout)


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


class TestPlace:
    def test_own_url_file_and_title(self, doc):
        assert page_path("race_debrief") == "/race-debrief/"
        assert output_name("race_debrief") == "race-debrief.html"
        assert "<title>How Did It Go? | Gravel God</title>" in doc
        assert '<link rel="canonical" href="https://gravelgodcycling.com/race-debrief/">' in doc

    def test_never_indexed(self, doc):
        assert '<meta name="robots" content="noindex, nofollow">' in doc

    def test_not_in_any_sitemap(self, tmp_path):
        from generate_sitemap import INDEXABLE_WORDPRESS_PAGES, generate_sitemap
        assert not any(p.startswith("/race-debrief") for p in INDEXABLE_WORDPRESS_PAGES)
        out = tmp_path / "web" / "sitemap.xml"
        generate_sitemap([], out)
        assert "/race-debrief" not in out.read_text(encoding="utf-8")

    def test_breadcrumb_is_training_plans_not_coaching(self, doc):
        crumbs = doc[doc.index('<div class="gg-breadcrumb">'):]
        crumbs = crumbs[:crumbs.index("</div>")]
        assert '<a href="https://gravelgodcycling.com/products/training-plans/">Training Plans</a>' in crumbs
        assert "/coaching/" not in crumbs
        assert '<span class="gg-breadcrumb-current">Race Debrief</span>' in crumbs

    def test_the_exit_breadcrumb_is_unchanged(self):
        assert '<a href="https://gravelgodcycling.com/coaching/">Coaching</a>' in generate_season_review_page("exit")


class TestTransport:
    def test_posts_as_plan_debrief_not_the_race_debrief_email(self, js):
        assert WORKER_SOURCES["race_debrief"] == "plan_debrief"
        assert 'LEAD_SOURCE = "plan_debrief"' in js

    def test_worker_only_no_formsubmit_backstop(self, js):
        # strangers' answers: the worker is the record, no copy at FormSubmit
        assert 'TRANSPORT = "worker"' in js
        assert 'var mailOk = TRANSPORT === "worker" ? Promise.resolve(false)' in js

    def test_no_goal_export(self, js):
        assert "GOAL_EXPORT = false" in js and 'EMAIL_TITLE = "Race debrief"' in js


class TestNoModules:
    def test_no_extra_credit_and_one_submit_button(self, doc):
        body = doc[doc.index("<form"):doc.index("</form>")]
        assert 'class="gg-sr-part"' not in body and "<details" not in body
        assert doc.count('class="gg-apply-submit-btn gg-sr-submit"') == 1


class TestUrlFields:
    """?plan= and ?ref= from the links in the plans' notes."""

    def test_hidden_inputs_carry_their_param_and_pattern(self, form):
        assert (f'<input type="hidden" id="plan" name="plan" data-param="plan" '
                f'data-pattern="{PLAN_ID_PATTERN}">') in form
        assert (f'<input type="hidden" id="ref" name="ref" data-param="ref" '
                f'data-pattern="{PLAN_REF_PATTERN}">') in form

    def test_they_stay_in_the_address(self):
        # not personal, and GA4 counts note clicks per plan from them
        assert "plan" not in PERSONAL_PARAMS and "ref" not in PERSONAL_PARAMS

    def test_posted_top_level_never_as_answers(self, js):
        assert 'var TOP_LEVEL = ["name", "email", "athlete", "plan", "ref"];' in js
        assert "if (TOP_LEVEL.indexOf(k) === -1" in js
        assert "URL_FIELDS.forEach(function(el) { if (d[el.name]) { body[el.name] = d[el.name]; } });" in js
        assert "plan" not in answer_keys(RACE_DEBRIEF) and "ref" not in answer_keys(RACE_DEBRIEF)

    def test_the_address_wins_over_a_draft_and_a_bad_draft_value_is_cleared(self, js):
        fill = js[js.index("function fillFromAddress() {"):js.index("/* Whether each one is there")]
        assert "if (v && matches(el, v)) { el.value = v; }" in fill
        # a link naming a plan or ref clears the other; a bare address keeps
        # the draft's (tests/test_race_debrief_playwright.py drives both)
        assert 'var fromLink = URL_FIELDS.some(function(el) { return params.has(el.getAttribute("data-param")); });' in fill
        assert 'else if (fromLink || (el.value && !matches(el, el.value))) { el.value = ""; }' in fill
        restore = js[js.index("function restore() {"):js.index("/* ── The email:")]
        assert restore.index("fillFromAddress();") > restore.index("var prefill = window.ggPersonalLink")

    @needs_node
    def test_page_worker_and_mission_control_agree_on_every_value(self):
        """One table through all three checks: the page's pattern (as the
        browser runs it), the worker's regexes, and Mission Control's."""
        from mission_control.services.plan_debrief import clean_plan, clean_ref
        plans = ["123456", "1", "123456789012", "1234567890123", "12a456", "", " 123456", "123456 ",
                 "123456\n", "-1", "1.5", "１２３", "0x12"]
        refs = ["test-ref-0001", "abcdEFGH", "a" * 32, "a" * 33, "short", "has space1", "has/slash1",
                "under_score_1", "", "test-ref-0001\n", "ümlaut-ref-1"]
        script = ("const [pp, rp, plans, refs] = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
                  "const w = [/^[0-9]{1,12}$/, /^[A-Za-z0-9_-]{8,32}$/];"
                  "process.stdout.write(JSON.stringify({"
                  "page: [plans.map((v) => new RegExp(pp).test(v)), refs.map((v) => new RegExp(rp).test(v))],"
                  "worker: [plans.map((v) => w[0].test(v)), refs.map((v) => w[1].test(v))]}));")
        run = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60, check=True,
                             input=json.dumps([PLAN_ID_PATTERN, PLAN_REF_PATTERN, plans, refs]))
        out = json.loads(run.stdout)
        consts = _worker_consts("PLAN_ID_RE", "PLAN_REF_RE")
        # the regexes in that script are the worker's own
        assert (consts["PLAN_ID_RE"], consts["PLAN_REF_RE"]) == ("^[0-9]{1,12}$", "^[A-Za-z0-9_-]{8,32}$")
        mc = [[bool(clean_plan(v)) for v in plans], [bool(clean_ref(v)) for v in refs]]
        assert out["page"] == out["worker"] == mc
        assert mc[0] == [True, True, True, False, False, False, False, False, False, False, False, False, False]
        assert mc[1] == [True, True, True, False, False, False, False, True, False, False, False]


class TestAnalytics:
    """debrief_start / debrief_submit, with has_plan / has_ref (never the
    values), fired on manual interaction only."""

    def test_own_events_not_the_goals_funnel(self, js):
        assert 'START_EVENT = "debrief_start"' in js and 'SUBMIT_EVENT = "debrief_submit"' in js
        assert "ga4(START_EVENT, withPresence({ variant: VARIANT }))" in js
        assert "ga4(SUBMIT_EVENT, withPresence({ variant: VARIANT }))" in js
        assert 'ga4("goal_start"' not in js and 'ga4("goal_submit"' not in js

    @pytest.mark.parametrize("slug", sorted(set(VARIANTS) - {"race_debrief"}))
    def test_the_other_forms_keep_the_goals_events(self, slug):
        other = build_season_review_js(VARIANTS[slug])
        assert 'START_EVENT = "goal_start"' in other and 'SUBMIT_EVENT = "goal_submit"' in other

    def test_presence_only(self, js):
        fn = js[js.index("function withPresence(params) {"):]
        fn = fn[:fn.index("\n  }\n")]
        assert 'params["has_" + el.name] = el.value ? "yes" : "no";' in fn
        assert "= el.value;" not in fn

    def test_start_fires_on_the_first_edit_not_on_load_or_a_timer(self, js):
        on_edit = js[js.index("function onEdit(e) {"):js.index('form.addEventListener("input", onEdit);')]
        assert "ga4(START_EVENT" in on_edit
        assert js.count("ga4(START_EVENT") == 1 and js.count("ga4(SUBMIT_EVENT") == 1
        for timer in re.findall(r"set(?:Timeout|Interval)\(function\(\) \{[^}]*\}", js):
            assert "ga4(" not in timer

    def test_documented_for_registration(self):
        doc = (ROOT / "docs" / "ga4-key-events.md").read_text(encoding="utf-8")
        for name in ("debrief_start", "debrief_submit", "has_plan", "has_ref"):
            assert name in doc, name


class TestRatingLine:
    """Receipts spec §5.6: one line, shown to every marketplace buyer."""

    def test_hidden_until_a_stored_submission_with_a_plan(self, doc, js):
        assert ('<p id="tp-rating" class="gg-sr-rating" hidden>If you have a minute, '
                '<a id="tp-rating-link" href="https://www.trainingpeaks.com/training-plans/" '
                'target="_blank" rel="noopener">rate the plan on TrainingPeaks</a>, '
                "whatever score you&#39;d give it.</p>") in doc
        assert doc.index('id="message"') < doc.index('id="tp-rating"') < doc.index("<form")
        assert "if (lastStored) { showRating(d); }" in js

    def test_links_the_plans_own_page(self, js):
        assert TP_PLAN_URL == "https://www.trainingpeaks.com/training-plans/cycling/tp-"
        assert f'TP_PLAN_URL = "{TP_PLAN_URL}"' in js
        fn = js[js.index("function showRating(d) {"):js.index("function showMessage(")]
        assert 'document.getElementById("tp-rating-link").href = TP_PLAN_URL + d.plan;' in fn
        # the value is checked again before it goes into a link
        assert "!matches(plan, d.plan)" in fn

    def test_not_gated_on_any_answer(self, js):
        fn = js[js.index("function showRating(d) {"):js.index("function showMessage(")]
        for answer in ("recommend", "raced", "goal_met", "load", "completion"):
            assert answer not in fn, answer

    def test_other_forms_have_no_rating_line(self):
        for slug in set(VARIANTS) - {"race_debrief"}:
            assert 'id="tp-rating"' not in generate_season_review_page(slug), slug


class TestScale:
    def test_labelled_radiogroup_with_end_labels(self, form):
        assert ('<label class="gg-apply-label" id="recommend-q">How likely are you to recommend this plan '
                "to a rider doing this race?</label>") in form
        assert '<div class="gg-sr-scale-ends" aria-hidden="true"><span>Not likely</span><span>Already have</span></div>' in form
        assert re.findall(r'<input type="radio" name="recommend" value="(\d+)"', form) == [str(n) for n in range(11)]


class TestFooter:
    def test_says_what_happens_and_nothing_about_formsubmit(self, doc):
        footer = doc[doc.index('<p class="gg-apply-confidential">'):]
        footer = footer[:footer.index("</p>")]
        assert footer == (
            '<p class="gg-apply-confidential">Your answers come straight to me and are stored in my system. '
            "If you said I can share your words, nothing goes up until you&#39;ve approved the exact wording. "
            "Drafts are saved only in this browser until you submit. Questions? Email gravelgodcoaching@gmail.com"
            ' &middot; <a href="/privacy/">Privacy Policy</a>')
        assert "FormSubmit" not in footer and "used to coach you" not in footer


class TestCopy:
    """DRAFT copy pending Matti's read: pinned so nobody "improves" it."""

    def test_draft_marker_sits_above_the_variant(self):
        src = (ROOT / "wordpress" / "season_review_variants.py").read_text(encoding="utf-8")
        marker = "# DRAFT COPY: Matti's read pending before deploy (receipts spec §3.7: Matti writes every ask)."
        assert src.index(marker, src.index("def _exit_record_field")) < src.index("RACE_DEBRIEF = {") \
            < src.index(marker, src.index("def _exit_record_field")) + 200

    def test_header(self, doc):
        assert '<div class="gg-apply-badge">Race Debrief</div>' in doc
        assert "<h1>How Did It Go?</h1>" in doc
        assert ("Five minutes, less if you&#39;re quick. Apart from your name and email, only the first "
                "question is required. I read every one of these myself. It saves as you go.") in doc

    def test_sections_in_order(self, form):
        titles = re.findall(r'gg-apply-section-title">([^<]+)</div>', form)
        assert titles == ["1. You", "2. Race Day", "3. The Plan", "4. On the Record", "5. What&#39;s Next"]
        assert '<p class="gg-apply-section-sub">Optional. Skip it and nothing changes.</p>' in form

    def test_buttons_and_messages(self, doc, js):
        assert ">Send It to Matti</button>" in doc
        assert "That&#39;s everything. Send it when you&#39;re ready." in doc
        assert 'SUCCESS = "Got it. I\'ll read every word."' in js

    def test_approved_exit_lines_are_reused_unchanged(self):
        for name in ("share_as", "age_group", "consent_note"):
            assert _field(name) == _field(name, EXIT), name
        assert _field("quote")["ph"] == _field("quote", EXIT)["ph"]
        assert _field("change_one")["ph"] == _field("change_one", EXIT)["ph"]
        assert _field("last_word") == _field("last_word", EXIT)
        assert _field("reference")["options"] == _field("reference", EXIT)["options"]
        assert RACE_DEBRIEF["submit"] == EXIT["submit"]
        assert _field("recommend")["low"] == "Not likely" and _field("recommend")["high"] == "Already have"
        exit_record = next(s for s in EXIT["sections"] if s["title"] == "On the Record")
        debrief_record = next(s for s in RACE_DEBRIEF["sections"] if s["title"] == "On the Record")
        assert debrief_record["sub"] == exit_record["sub"]

    def test_only_the_coaching_words_change_in_the_consent_block(self):
        assert _field("quote")["label"] == "If a rider doing this race asked about the plan, what would you tell them?"
        assert _field("not_for")["label"] == "And who shouldn&#39;t buy it?"
        assert _field("not_for")["ph"] == "The rider this plan wouldn&#39;t work for"
        assert dict(_field("share_where")["options"]) == {
            "where_site": "gravelgodcycling.com", "where_social": "Gravel God social posts",
            "where_email": "Emails to riders choosing a plan", "where_tp": "The plan&#39;s TrainingPeaks page"}
        exit_conn, conn = dict(_field("connection", EXIT)["options"]), dict(_field("connection")["options"])
        assert conn["comped"] == "You gave me the plan free or at a discount"
        assert conn["none"] == "No, only the plan"  # flagged for Matti: "just coaching" misfits a plan buyer
        assert {k: v for k, v in conn.items() if k not in ("none", "comped")} == \
            {k: v for k, v in exit_conn.items() if k not in ("none", "comped")}
        assert _field("reference")["label"] == ("If someone deciding on this plan wants to talk to a real "
                                                "rider, can I introduce you by email?")

    def test_no_exclamation_marks(self, doc):
        body = doc[doc.index('<div class="gg-apply-header">'):doc.index("</form>")]
        assert "!" not in re.sub(r"<!--.*?-->", "", body)


class TestFields:
    def test_only_the_first_question_is_required(self, form):
        required = set(re.findall(r'name="([a-z_]+)"[^>]*\srequired', form))
        assert required == {"name", "email", "raced"}

    def test_long_options_stack_vertically(self, form):
        for name in ("raced", "goal_met", "completion", "share_as", "connection", "next_want"):
            assert "gg-apply-radio-horizontal" not in _group(form, name), name
        for name in ("load", "fit_week", "reference"):
            assert "gg-apply-radio-horizontal" in _group(form, name), name

    def test_each_check_is_its_own_input(self, form):
        for key in ("where_site", "where_social", "where_email", "where_tp"):
            assert form.count(f'name="{key}"') == 1, key

    def test_answer_keys(self):
        assert answer_keys(RACE_DEBRIEF) == [
            "raced", "result", "result_url", "goal_met", "completion", "load", "fit_week", "worked",
            "change_one", "recommend", "quote", "not_for", "share_as", "age_group", "where_site",
            "where_social", "where_email", "where_tp", "connection", "reference", "next_race",
            "next_want", "last_word",
        ]

    def test_every_input_is_rendered(self, form):
        for key in input_names(RACE_DEBRIEF):
            assert f'name="{key}"' in form, key


class TestNothingCutSilently:
    def test_every_text_and_area_field_is_capped(self, doc):
        for tag in re.findall(r"<textarea [^>]*>|<input type=\"text\" [^>]*>", doc):
            if 'name="website"' in tag:
                continue
            assert 'maxlength="4000"' in tag, tag

    @pytest.mark.parametrize("variant", [EXIT, RACE_DEBRIEF], ids=["exit", "race_debrief"])
    def test_the_total_budget_fits_a_full_form(self, variant):
        """Every text answer at 4000 must fit the worker's and Mission
        Control's total, or the last answers are silently dropped."""
        most = max_answer_chars(variant)
        worker = int(re.search(r"const MAX_ANSWERS_TOTAL = (\d+);", WORKER).group(1))
        mc = int(re.search(r"_MAX_GOAL_ANSWERS_TOTAL = (\d+)", WEBHOOKS).group(1))
        assert worker == mc == 40000
        assert most is not None and most <= worker
        # the raise from 30000 is load-bearing for both forms
        assert most > 30000

    def test_uncapped_forms_say_so(self):
        # timed free-writes and the why-chain have no maxlength
        assert max_answer_chars(VARIANTS["goal_2027"]) is None


class TestNothingDropped:
    def test_fixture_answers_every_question(self):
        assert list(FIXTURE["goal_answers"]) == answer_keys(RACE_DEBRIEF)
        assert list(ROADIE_FIXTURE["goal_answers"]) == answer_keys(RACE_DEBRIEF)
        assert re.fullmatch(PLAN_ID_PATTERN.strip("^$"), FIXTURE["plan"])

    def test_fixtures_are_synthetic(self):
        for fx in (FIXTURE, ROADIE_FIXTURE):
            assert fx["name"].startswith("Test Rider")
            assert fx["email"].endswith("@example.com")
            free_text = [k for k in answer_keys(RACE_DEBRIEF)
                         if not k.startswith("where_") and _field(k)["kind"] in ("text", "area")]
            assert all(fx["goal_answers"][k].startswith(("Test answer", "https://results.example.com/"))
                       for k in free_text)

    def test_key_count_fits_the_worker_cap(self):
        cap = int(re.search(r"const MAX_ANSWER_KEYS = (\d+);", WORKER).group(1))
        assert len(answer_keys(RACE_DEBRIEF)) <= cap


@needs_node
class TestWorkerMirrorsTheForm:
    """The worker labels answers in Matti's alert; its labels must be the
    form's, or the alert says something the rider did not pick."""

    def test_source_is_known_answer_bearing_storage_required_and_not_a_lead(self):
        consts = _worker_consts("KNOWN_SOURCES", "ANSWER_SOURCES", "STORAGE_REQUIRED", "NOT_LEAD_SOURCES")
        for name, values in consts.items():
            assert "plan_debrief" in values, name
        assert consts["NOT_LEAD_SOURCES"] == ["athlete_exit", "plan_debrief"]

    def test_option_labels(self):
        labels = _worker_consts("DEBRIEF_OPTION_LABELS")["DEBRIEF_OPTION_LABELS"]
        for name in ("raced", "goal_met", "completion", "load", "fit_week", "share_as", "age_group",
                     "connection", "reference", "next_want"):
            form_labels = {o[0]: html.unescape(o[1]) for o in _field(name)["options"]}
            assert labels[name] == form_labels, name

    def test_channel_labels_per_brand(self):
        channels = _worker_consts("DEBRIEF_CHANNEL_LABELS")["DEBRIEF_CHANNEL_LABELS"]
        assert channels["gravelgod"] == {k: html.unescape(v) for k, v in _field("share_where")["options"]}
        assert channels["roadielabs"] == ROADIE_CHANNELS

    def test_mission_control_labels_match(self):
        from mission_control.services import plan_debrief as pd
        assert pd.CHANNEL_LABELS["gravelgod"] == {k: html.unescape(v) for k, v in _field("share_where")["options"]}
        assert pd.CHANNEL_LABELS["roadielabs"] == ROADIE_CHANNELS
        assert pd.CONNECTION_LABELS == {o[0]: html.unescape(o[1]) for o in _field("connection")["options"]}
