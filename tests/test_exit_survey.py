"""The athlete exit survey at /coaching/exit/ (variant `exit`).

One renderer draws every questionnaire (generate_season_review.py). These
tests pin what is different about this one: its own URL and source, a page
with no optional modules, the 0-10 scale and the note, its own footer and
backstop email, and that every answer it can post is one the worker and
Mission Control keep. The browser run is tests/test_exit_survey_playwright.py;
the Mission Control side is mission_control/tests/test_athlete_exit.py.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.insert(0, str(ROOT / "scripts"))

from generate_season_review import (  # noqa: E402
    WORKER_SOURCES,
    answer_keys,
    build_season_review_js,
    check_unique_names,
    generate_season_review_page,
    input_names,
    output_name,
    page_path,
)
from season_review_variants import EXIT, VARIANTS  # noqa: E402

WORKER = (ROOT / "workers" / "fueling-lead-intake" / "worker.js").read_text(encoding="utf-8")
FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "exit_survey_submission.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def doc() -> str:
    return generate_season_review_page("exit")


@pytest.fixture(scope="module")
def form(doc) -> str:
    return doc[doc.index('<form id="season-form"'):doc.index("</form>")]


def _field(name):
    for sec in EXIT["sections"]:
        for f in sec["fields"]:
            for g in f.get("fields", [f]):
                if g.get("name") == name:
                    return g
    raise KeyError(name)


def _group(form_html: str, name: str) -> str:
    start = form_html.index(f'data-radio="{name}"')
    return form_html[form_html.rindex("<div", 0, start):form_html.index("</div></div>", start)]


class TestPlace:
    def test_own_url_file_and_title(self, doc):
        assert page_path("exit") == "/coaching/exit/"
        assert output_name("exit") == "coaching-exit.html"
        assert "<title>Before You Go | Gravel God</title>" in doc
        assert '<link rel="canonical" href="https://gravelgodcycling.com/coaching/exit/">' in doc

    def test_never_indexed(self, doc):
        assert '<meta name="robots" content="noindex, nofollow">' in doc

    def test_not_in_any_sitemap(self, tmp_path):
        from generate_sitemap import INDEXABLE_WORDPRESS_PAGES, generate_sitemap
        assert not any(p.startswith("/coaching/exit") for p in INDEXABLE_WORDPRESS_PAGES)
        out = tmp_path / "web" / "sitemap.xml"
        generate_sitemap([], out)
        assert "/coaching/exit" not in out.read_text(encoding="utf-8")

    def test_breadcrumb_is_not_season_review(self, doc):
        assert '<span class="gg-breadcrumb-current">Exit Interview</span>' in doc
        assert '<span class="gg-breadcrumb-current">Season Review</span>' in generate_season_review_page("athlete")


class TestTransport:
    def test_posts_as_athlete_exit_not_the_exit_popup(self):
        assert WORKER_SOURCES["exit"] == "athlete_exit"
        js = build_season_review_js(EXIT)
        assert 'LEAD_SOURCE = "athlete_exit"' in js
        assert "exit_intent" not in js

    def test_worker_only_and_no_formsubmit_on_the_page(self):
        """FormSubmit stopped delivering (2026-09-29). The worker is the
        record; no FormSubmit address is left on the page to post to."""
        assert 'TRANSPORT = "worker"' in build_season_review_js(EXIT)
        assert 'SUBMIT_URL = ""' in build_season_review_js(EXIT)
        assert "formsubmit" not in generate_season_review_page("exit").lower()

    def test_backstop_email_has_its_own_title_and_no_goal_export(self):
        js = build_season_review_js(EXIT)
        assert 'EMAIL_TITLE = "Exit survey"' in js
        assert "GOAL_EXPORT = false" in js
        # the early return sits before the goal flags and the Endure draft
        fmt = js[js.index("function formatSubmission"):js.index("/* The limiter interrogation")]
        assert fmt.index("if (!GOAL_EXPORT)") < fmt.index('"## Flags"') < fmt.index("Endure draft")
        assert 'payload.append("_subject", EMAIL_TITLE + ": " + d.name)' in js

    @pytest.mark.parametrize("slug", sorted(set(VARIANTS) - {"exit"}))
    def test_the_other_forms_keep_their_backstop_email(self, slug):
        js = build_season_review_js(VARIANTS[slug])
        assert f'EMAIL_TITLE = "Season Review 2026 [{slug}]"' in js
        assert "GOAL_EXPORT = true" in js


class TestNoModules:
    def test_no_extra_credit_heading_or_empty_toggles(self, doc):
        body = doc[doc.index("<form"):doc.index("</form>")]
        assert 'class="gg-sr-part"' not in body
        assert "<details" not in body
        assert "Extra credit" not in doc and "deep_title" not in EXIT

    def test_one_submit_button(self, doc):
        assert doc.count('class="gg-apply-submit-btn gg-sr-submit"') == 1
        assert 'id="submit-btn-2"' not in doc

    def test_the_other_forms_keep_both_buttons(self):
        assert generate_season_review_page("athlete").count('class="gg-apply-submit-btn gg-sr-submit"') == 2


class TestScale:
    def test_eleven_radios_zero_to_ten(self, form):
        values = re.findall(r'<input type="radio" name="recommend" value="(\d+)"', form)
        assert values == [str(n) for n in range(11)]

    def test_a_labelled_radiogroup_with_end_labels(self, form):
        assert '<label class="gg-apply-label" id="recommend-q">How likely are you to recommend me to a rider like you?</label>' in form
        assert 'role="radiogroup" aria-labelledby="recommend-q"' in form
        assert '<div class="gg-sr-scale-ends" aria-hidden="true"><span>Not likely</span><span>Already have</span></div>' in form
        # screen readers hear the ends on the end buttons
        assert 'value="0" aria-label="0 (Not likely)"' in form
        assert 'value="10" aria-label="10 (Already have)"' in form

    def test_radios_stay_focusable(self):
        # hidden with opacity, never display:none, or the keyboard loses them
        css = generate_season_review_page("exit")
        rule = css[css.index(".gg-sr-scale-option input {"):]
        rule = rule[:rule.index("}")]
        assert "opacity: 0" in rule and "display: none" not in rule
        assert ".gg-sr-scale-option input:focus-visible + .gg-sr-scale-n" in css

    def test_optional(self, form):
        assert 'name="recommend" value="0" required' not in form


class TestNote:
    def test_is_a_paragraph_with_no_input(self, form):
        note = html.unescape(_field("consent_note")["text"])
        assert f'<p class="gg-sr-note">{_field("consent_note")["text"]}</p>' in form
        assert 'name="consent_note"' not in form
        assert "consent_note" not in input_names(EXIT)
        assert note.startswith("Before anything goes up")

    def test_is_left_out_of_the_coach_email(self, form):
        # no data-q, so formatSubmission never prints it as a question
        start = form.index('<p class="gg-sr-note">')
        assert "data-q" not in form[start:form.index("</p>", start)]


class TestFooter:
    def test_says_what_happens_and_not_used_to_coach_you(self, doc):
        footer = doc[doc.index('<p class="gg-apply-confidential">'):]
        footer = footer[:footer.index("</p>")]
        assert "used to coach you" not in footer
        assert "stored in my system" in footer
        assert "coaching file" not in footer
        assert "FormSubmit" not in footer and "30 days" not in footer
        assert '<a href="/privacy/">Privacy Policy</a>' in footer

    def test_the_athlete_review_footer_keeps_its_wording_without_formsubmit(self):
        doc = generate_season_review_page("athlete")
        footer = doc[doc.index('<p class="gg-apply-confidential">'):]
        footer = footer[:footer.index("</p>")]
        assert "used to coach you" in footer
        assert "They come straight to me and are stored with your file. Drafts are saved" in footer
        assert "FormSubmit" not in footer and "30 days" not in footer


class TestCopy:
    """DRAFT copy pending Matti's read: pinned so nobody "improves" it."""

    def test_draft_marker_sits_above_the_variant(self):
        src = (ROOT / "wordpress" / "season_review_variants.py").read_text(encoding="utf-8")
        marker = "# DRAFT COPY: Matti's read pending before deploy (receipts spec §3.7: Matti writes every ask)."
        assert marker in src
        assert src.index(marker) < src.index("EXIT = {") < src.index(marker) + 200

    def test_header(self, doc):
        assert '<div class="gg-apply-badge">Exit Interview</div>' in doc
        assert "<h1>Before You Go</h1>" in doc
        assert ("Five minutes, less if you&#39;re quick. Apart from your name and email, only the "
                "first question is required. I read every one of these myself. It isn&#39;t anonymous, so say it straight. "
                "It saves as you go.") in doc

    def test_sections_in_order(self, form):
        titles = re.findall(r'gg-apply-section-title">([^<]+)</div>', form)
        assert titles == ["1. You", "2. Why Now", "3. The Report Card", "4. On the Record", "5. Loose Ends"]

    def test_buttons_and_messages(self, doc):
        assert ">Send It to Matti</button>" in doc
        assert "That&#39;s everything. Send it when you&#39;re ready." in doc
        js = build_season_review_js(EXIT)
        assert ("SUCCESS = \"Got it. I'll read every word, and I'll come back to you on "
                "anything you asked for above.\"") in js


class TestFields:
    def test_only_the_first_question_is_required(self, form):
        required = set(re.findall(r'name="([a-z_]+)"[^>]*\srequired', form))
        # name and email come prefilled from the personalised link
        assert required == {"name", "email", "exit_reason"}

    def test_carries_the_hidden_athlete_tag(self, form):
        assert '<input type="hidden" id="athlete" name="athlete">' in form

    def test_share_as_and_connection_stack_vertically(self, form):
        for name in ("share_as", "connection"):
            group = _group(form, name)
            assert 'class="gg-apply-radio-group"' in group, name
            assert "gg-apply-radio-horizontal" not in group, name

    def test_each_check_is_its_own_input(self, form):
        for key in ("where_site", "where_social", "where_email", "where_tp",
                    "need_zones", "need_notes", "need_billing", "need_tp"):
            assert form.count(f'name="{key}"') == 1, key
        assert 'name="share_where"' not in form and 'name="needs"' not in form

    def test_answer_keys(self):
        assert answer_keys(EXIT) == [
            "exit_reason", "exit_story", "stay_lever", "recommend", "keep_doing", "change_one",
            "what_changed", "quote", "not_for", "share_as", "age_group", "where_site", "where_social",
            "where_email", "where_tp", "connection", "reference", "come_back", "checkin",
            "need_zones", "need_notes", "need_billing", "need_tp", "last_word",
        ]

    def test_every_answer_key_is_rendered(self, form):
        for key in answer_keys(EXIT):
            assert f'name="{key}"' in form, key


class TestAgeGroup:
    def test_optional_select_after_the_sharing_question(self, form):
        assert '<select id="age_group" name="age_group">' in form
        assert form.index('data-radio="share_as"') < form.index('name="age_group"') < form.index('name="where_site"')
        assert "Your age group. It only shows if you picked first name and age group. If you&#39;re under 18, I&#39;ll need a parent&#39;s OK." in form

    def test_options(self, form):
        assert re.findall(r'<option value="([a-z0-9_]+)">', form[form.index('name="age_group"'):]) [:6] == [
            "under_18", "18_29", "30_39", "40_49", "50_59", "60_plus"]
        assert '<option value="18_29">18&ndash;29</option>' in form


class TestNothingCutSilently:
    """The worker and Mission Control keep 4000 characters of an answer; the
    page stops typing there instead of storing a quietly cut quote."""

    def test_every_text_and_area_field_on_every_form_is_capped(self):
        for slug, variant in VARIANTS.items():
            page_html = generate_season_review_page(slug)
            for tag in re.findall(r"<textarea [^>]*>|<input type=\"text\" [^>]*>", page_html):
                if 'class="gg-sr-long"' in tag or 'name="website"' in tag or "why_" in tag or "outcome_why" in tag:
                    continue  # timed free-writes, the honeypot and the why-chain are not _control text/area
                assert 'maxlength="4000"' in tag, (slug, tag)

    def test_matches_the_worker_and_mission_control(self):
        from generate_season_review import MAX_ANSWER_LEN
        assert f"const MAX_ANSWER_LEN = {MAX_ANSWER_LEN};" in WORKER
        webhooks = (ROOT / "mission_control" / "routers" / "webhooks.py").read_text(encoding="utf-8")
        assert f"_MAX_GOAL_ANSWER_LEN = {MAX_ANSWER_LEN}" in webhooks

    def test_the_quote_is_capped(self, form):
        assert '<textarea id="quote" name="quote" rows="3" placeholder=' in form
        start = form.index('<textarea id="quote"')
        assert 'maxlength="4000"' in form[start:form.index(">", start)]


class TestPersonalLinkStaysOutOfAnalytics:
    """?name=&email=&athlete= come off the address before GA4 reads it."""

    @pytest.mark.parametrize("slug", sorted(VARIANTS))
    def test_strip_runs_before_the_ga_snippet_on_every_variant(self, slug):
        page_html = generate_season_review_page(slug)
        strip = page_html.index("window.ggPersonalLink = found;")
        assert strip < page_html.index("gtag('config'")
        assert strip < page_html.index("googletagmanager.com/gtag/js")
        # and before anything else in <head> can request a resource
        assert strip < page_html.index("<link ")

    def test_removes_only_the_three_personal_params(self):
        from generate_season_review import PERSONAL_PARAMS, build_personal_link_js
        assert PERSONAL_PARAMS == ("name", "email", "athlete")
        js = build_personal_link_js()
        assert 'var KEYS = ["name", "email", "athlete"]' in js
        # the rest of the query is kept as the raw text it arrived as, hash too
        assert "kept.push(part)" in js and "window.location.hash" in js
        assert "history.replaceState" in js

    def test_prefill_reads_the_kept_values_not_the_address(self):
        js = build_season_review_js(EXIT)
        restore = js[js.index("function restore() {"):js.index("/* ── The email:")]
        assert "var prefill = window.ggPersonalLink || {};" in restore
        assert 'params.get(k)' not in restore

    def test_prefilled_values_are_saved_to_the_draft_at_once(self):
        # The stripped address can't prefill a reload, and iOS Safari often
        # skips beforeunload, so restore() saves the link's values itself.
        js = build_season_review_js(EXIT)
        restore = js[js.index("function restore() {"):js.index("/* ── The email:")]
        fill = restore.index("el.value = prefill[k]")
        assert restore.index("{ save(true); }", fill) > fill

    def test_global_ga_snippet_is_untouched(self):
        from brand_tokens import get_ga4_head_snippet
        assert "ggPersonalLink" not in get_ga4_head_snippet()
        assert "replaceState" not in get_ga4_head_snippet()


class TestUniqueNames:
    @pytest.mark.parametrize("slug", sorted(VARIANTS))
    def test_no_variant_reuses_an_input_name(self, slug):
        check_unique_names(VARIANTS[slug])

    def test_a_reused_name_refuses_to_render(self):
        bad = dict(EXIT, slug="bad", sections=[{"title": "x", "fields": [
            {"name": "a", "kind": "checks", "options": [("dup", "One")]},
            {"name": "dup", "kind": "text", "label": "Two"},
        ]}])
        with pytest.raises(ValueError, match="dup"):
            check_unique_names(bad)


class TestNothingDropped:
    """The handoff's worst bug: answers silently dropped by whitelists. Every
    key the page can post has to fit every cap on the way through."""

    def test_fixture_answers_every_question(self):
        assert list(FIXTURE["goal_answers"]) == answer_keys(EXIT)
        for name in ("name", "email", "athlete"):
            assert FIXTURE[name]

    def test_fixture_is_synthetic(self):
        assert FIXTURE["name"].startswith("Test Rider")
        assert FIXTURE["email"].endswith("@example.com")

    def test_key_count_fits_the_worker_cap(self):
        cap = int(re.search(r"const MAX_ANSWER_KEYS = (\d+);", WORKER).group(1))
        assert len(answer_keys(EXIT)) <= cap


class TestWorkerMirrorsTheForm:
    """The worker labels answers in Matti's alert; its labels must be the
    form's, or the alert says something the athlete did not pick."""

    def test_source_is_known_answer_bearing_and_storage_required(self):
        for const in ("KNOWN_SOURCES", "ANSWER_SOURCES", "STORAGE_REQUIRED"):
            line = re.search(rf"const {const} = \[([^\]]*)\]", WORKER).group(1)
            assert "'athlete_exit'" in line, const

    @pytest.mark.parametrize("name", ["exit_reason", "share_as", "age_group", "connection", "reference",
                                      "come_back", "checkin"])
    def test_radio_and_select_labels(self, name):
        block = WORKER[WORKER.index(f"  {name}: {{"):]
        block = block[:block.index("}")]
        for value, label, *_ in _field(name)["options"]:
            text = html.unescape(label)
            assert re.search(rf"""'?{re.escape(value)}'?: (['"]){re.escape(text)}\1""", block), (name, value, text)

    @pytest.mark.parametrize("name,const", [("share_where", "EXIT_CHANNEL_LABELS"), ("needs", "EXIT_NEED_LABELS")])
    def test_check_labels(self, name, const):
        block = WORKER[WORKER.index(f"const {const} = {{"):]
        block = block[:block.index("};")]
        for key, label in _field(name)["options"]:
            assert f"{key}: '{html.unescape(label)}'" in block, key
