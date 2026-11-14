"""Tests for step 2 of the two-step questionnaire (2026-10-23).

/training-plans/details/ (step 2, after payment: every other question). Step 1
(/training-plans/start/) was retired with the one-off plan on 2026-11-13: the
plan billed every 4 weeks sells from the one-page questionnaire only, so the
start page is no longer generated and /training-plans/start/ 302s to
/questionnaire/. Step 2 stays for buyers of the old two-step checkout.

Covers: step 2 keeps every question of the full questionnaire with the same
input names and option values; the copied JS blocks (FIELD_MAP,
mapToWorkerFormat, identifyBlindspots, pricing and attribution helpers) stay
identical to web/training-plans-form.js; prices only from pricing.json;
Desert Editorial fonts; noindex + canonical; the start -> /questionnaire/ 302
and the deploy path that keeps step 2 out of the /race/ sweep.
"""
from __future__ import annotations

import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.insert(0, str(ROOT / "scripts"))

import generate_plan_intake_pages as gen  # noqa: E402
import pricing  # noqa: E402

FORM_JS = ROOT / "web" / "training-plans-form.js"
DETAILS_JS = ROOT / "web" / "training-plans-details.js"
QUESTIONNAIRE_HTML = ROOT / "web" / "training-plans-questionnaire.html"


@pytest.fixture(scope="module")
def details_page() -> str:
    return gen.generate_page("details")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ── JS block extraction ──────────────────────────────────────


def extract_block(src: str, name: str) -> str:
    """Source of `function NAME(...) {...}` or `var NAME = {...};`, brace
    matched, from its line's indentation through the closing brace."""
    m = re.search(r"^[ \t]*function " + re.escape(name) + r"\(", src, re.M)
    if not m:
        m = re.search(r"^[ \t]*var " + re.escape(name) + r" = \{", src, re.M)
    if not m:
        raise KeyError(name)
    i = src.index("{", m.end() - 1)
    depth, in_str, esc_next, j = 0, None, False, i
    while j < len(src):
        c = src[j]
        if in_str:
            if esc_next:
                esc_next = False
            elif c == "\\":
                esc_next = True
            elif c == in_str:
                in_str = None
        elif c in ("'", '"'):
            in_str = c
        elif c == "/" and src[j + 1:j + 2] == "/":
            j = src.index("\n", j)
            continue
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                if src[end:end + 1] == ";":
                    end += 1
                return src[m.start():end]
        j += 1
    raise ValueError(name)


def span(src: str, start: str, end: str) -> str:
    i = src.index(start)
    return src[i:src.index(end, i) + len(end)]


ATTRIBUTION_SPANS = (
    ("  var CHECKOUT_PENDING_KEY", "  } catch (e) {}"),
    ("  var ENTRY_SURFACE_KEY", "  var ENTRY_SURFACE = resolveEntrySurface();"),
    ("  var OFFER_VARIANT_KEY", "  var OFFER_VARIANT = resolveOfferVariant();"),
    ("  var ENTRY_SRC_KEY", "  var ENTRY_SRC = resolveEntrySrc();"),
)


@pytest.mark.parametrize("name", ["FIELD_MAP", "mapToWorkerFormat", "identifyBlindspots"])
def test_details_js_field_mapping_is_verbatim(name):
    """`fields` must be exactly what the full form sends to /create-checkout."""
    assert extract_block(_read(DETAILS_JS), name) == extract_block(_read(FORM_JS), name)


@pytest.mark.parametrize("start,end", ATTRIBUTION_SPANS, ids=[s.split()[1] for s, _ in ATTRIBUTION_SPANS])
def test_attribution_state_is_verbatim(start, end):
    assert span(_read(DETAILS_JS), start, end) == span(_read(FORM_JS), start, end)


def test_track_is_verbatim():
    assert extract_block(_read(DETAILS_JS), "track") == extract_block(_read(FORM_JS), "track")


def test_start_page_is_retired():
    """Step 1 sold the one-off plan; the plan billed every 4 weeks can't be
    bought through a two-step checkout (the server refuses intake_flow)."""
    import generate_pricing_js

    assert list(gen.PAGES) == ["details"]
    assert not (ROOT / "web" / "training-plans-start.js").exists()
    assert generate_pricing_js.JS_PATHS == (FORM_JS,)


def test_details_js_never_sends_a_slug_or_identity():
    body = _read(DETAILS_JS)
    # mapToWorkerFormat only adds race_slug when prefilledRaceSlug is set.
    assert "var prefilledRaceSlug = null;" in body
    assert "prefilledRaceSlug =" not in body.replace("var prefilledRaceSlug = null;", "")


# ── Step 2 keeps every question (same names, same option values) ──


class _Fields(HTMLParser):
    """Collects form controls: name → {"tag", "type", "values"}."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fields: dict[str, dict] = {}
        self._select: str | None = None
        self.ids: set[str] = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag in ("input", "select", "textarea") and a.get("name"):
            entry = self.fields.setdefault(a["name"], {"tag": tag, "type": a.get("type", ""), "values": set()})
            if tag == "input" and a.get("type") in ("radio", "checkbox"):
                entry["values"].add(a.get("value", ""))
            if tag == "select":
                self._select = a["name"]
        elif tag == "option" and self._select:
            self.fields[self._select]["values"].add(a.get("value", ""))

    def handle_endtag(self, tag):
        if tag == "select":
            self._select = None


def _fields(doc: str) -> _Fields:
    p = _Fields()
    p.feed(doc)
    return p


def _questionnaire_fields() -> dict[str, dict]:
    doc = _read(QUESTIONNAIRE_HTML)
    form = doc[doc.index('<form id="gg-training-form">'):doc.index("</form>")]
    return _fields(form).fields


STEP1_ONLY = {"name", "email"}


def test_questionnaire_reference_still_parses():
    fields = _questionnaire_fields()
    assert {"sex", "weeklyHours", "longRideDays", "additionalNotes"} <= set(fields)


def test_details_has_every_question_except_step1_fields(details_page):
    expected = {n for n in _questionnaire_fields() if n not in STEP1_ONLY}
    got = set(_fields(details_page).fields)
    assert expected - got == set(), f"missing on step 2: {sorted(expected - got)}"


def test_details_asks_nothing_new_except_the_a_race_details(details_page):
    expected = {n for n in _questionnaire_fields() if n not in STEP1_ONLY}
    extra = set(_fields(details_page).fields) - expected
    assert extra == {"race_a_distance", "race_a_goal"}


def test_details_has_no_name_email_or_a_race_name_date(details_page):
    names = set(_fields(details_page).fields)
    assert not names & {"name", "email", "race_name", "race_date", "race_0_name", "race_0_date"}


@pytest.mark.parametrize("name", sorted(
    n for n, f in _questionnaire_fields().items() if f["values"] and n not in STEP1_ONLY
))
def test_details_option_values_match_questionnaire(details_page, name):
    assert _fields(details_page).fields[name]["values"] == _questionnaire_fields()[name]["values"]


def test_details_input_types_and_required_match_questionnaire(details_page):
    q = _read(QUESTIONNAIRE_HTML)
    for name, f in _questionnaire_fields().items():
        if name in STEP1_ONLY:
            continue
        got = _fields(details_page).fields[name]
        assert (got["tag"], got["type"]) == (f["tag"], f["type"]), name
        q_required = re.search(r'name="%s"[^>]*\brequired\b' % re.escape(name), q) is not None
        d_required = re.search(r'name="%s"[^>]*\brequired\b' % re.escape(name), details_page) is not None
        assert q_required == d_required, f"{name}: required differs"


def _js_options(block: str, field: str) -> set[str]:
    sel = block[re.search(r"_%s\"[^>]*>" % field, block).start():]
    sel = sel[:sel.index("</select>")]
    return set(re.findall(r'<option value="([^"]*)"', sel))


@pytest.mark.parametrize("field", ["distance", "goal"])
def test_extra_race_options_match_the_full_form(details_page, field):
    form_block = extract_block(_read(FORM_JS), "createRaceEntry")
    details_block = extract_block(_read(DETAILS_JS), "createRaceEntry")
    assert _js_options(details_block, field) == _js_options(form_block, field)
    # The A-race selects on the page use the same values too.
    assert _fields(details_page).fields["race_a_" + field]["values"] == _js_options(form_block, field)


def test_extra_races_are_b_or_c_only():
    block = extract_block(_read(DETAILS_JS), "createRaceEntry")
    assert _js_options(block, "priority") == {"", "B", "C"}


def test_details_has_five_pages_in_order(details_page):
    titles = re.findall(r'class="gg-pd-page" data-title="([^"]+)"', details_page)
    assert titles == ["About you", "Races", "Fitness", "Schedule", "Strength and notes"]


def test_details_conditionals_start_hidden(details_page):
    ids = _fields(details_page).ids
    assert {"cycle-row", "travelDatesGroup", "powerFields", "hrFields", "pwCalc"} <= ids
    for el_id in ("cycle-row", "travelDatesGroup", "powerFields", "hrFields"):
        assert re.search(r'id="%s"[^>]*style="display: none;"' % el_id, details_page), el_id
    js = _read(DETAILS_JS)
    assert "sexSelect.value === 'female'" in js
    assert "(tv && tv !== 'none')" in js


def test_details_copy(details_page):
    assert "No power meter? Heart rate works." in details_page
    js = _read(DETAILS_JS)
    assert "It\\u2019ll be in your TrainingPeaks within " in js
    assert "Got it. Your plan is building." in details_page
    assert "This link isn&rsquo;t valid." in details_page
    assert "reply to your receipt email" in details_page.lower()


def test_details_js_api_contract():
    js = _read(DETAILS_JS)
    assert "API_BASE + '/intake-details/' + encodeURIComponent(token)" in js
    assert "{ fields: fields, submit: false }" in js
    assert "{ fields: fields, submit: true }" in js
    assert "result.status === 'building' || result.status === 'received'" in js
    assert "response.status === 409 && result.status === 'already_complete'" in js
    assert "response.status === 404" in js
    assert "data.status === 'complete'" in js
    assert "STORAGE_PREFIX + token" in js
    assert "DRAFT_DEBOUNCE_MS = 2000" in js


def test_details_js_builds_fields_like_the_full_form():
    js = _read(DETAILS_JS)
    for line in (
        "if (key.startsWith('race_')) delete data[key];",
        "data.longRideDays = getCheckboxValues('longRideDays');",
        "data.intervalDays = getCheckboxValues('intervalDays');",
        "data.daysOff = getCheckboxValues('daysOff');",
        "data.pwRatio = (parseFloat(ftpInput.value) / wKg).toFixed(2);",
        "data.estimatedCategory = catValue ? catValue.textContent : '';",
        "data.blindspots = identifyBlindspots(data);",
        "return mapToWorkerFormat(data);",
    ):
        assert line in js, line


@pytest.mark.parametrize("event", ["tp_step2_view", "tp_step2_start", "tp_step2_page", "tp_step2_submit", "tp_form_error"])
def test_details_ga4_events(event):
    assert f"track('{event}'" in _read(DETAILS_JS)


# ── Prices, brand, SEO ───────────────────────────────────────

MONEY_LITERAL = re.compile(r"\$\s?\d")


@pytest.mark.parametrize("path", [
    DETAILS_JS, ROOT / "wordpress" / "generate_plan_intake_pages.py",
], ids=["details.js", "generator"])
def test_no_money_literals_in_sources(path):
    hits = [line.strip() for line in _read(path).splitlines() if MONEY_LITERAL.search(line)]
    assert hits == []


def test_noindex_and_canonical(details_page):
    doc = details_page
    assert '<meta name="robots" content="noindex, follow">' in doc
    assert '<link rel="canonical" href="https://gravelgodcycling.com/training-plans/details/">' in doc


def test_brand_fonts_and_shell(details_page):
    doc = details_page
    css = gen.build_intake_css()
    assert "font-family: 'Source Serif 4'" in doc
    assert "font-family: 'Sometype Mono'" in doc
    assert "font-family: var(--gg-font-editorial)" in css
    assert "font-family: var(--gg-font-data)" in css
    # No fonts but the two brand tokens, square corners only.
    own = css[css.index(".gg-pi {"):]
    assert set(re.findall(r"font-family:\s*([^;]+);", own)) == {"var(--gg-font-editorial)", "var(--gg-font-data)"}
    assert "border-radius: 0" in own
    assert not re.search(r"border-radius:\s*[1-9]", own)
    assert "#" not in re.sub(r"#gg-[\w-]+", "", own.split("</style>")[0])  # tokens, no hex
    assert "googletagmanager.com/gtag/js?id=G-" in doc
    assert 'class="gg-site-header"' in doc
    assert "gg-mega-footer" in doc


def test_buttons_and_labels_use_the_data_font_only():
    css = gen.build_intake_css()
    rules = dict(re.findall(r"\n(\.gg-pi-btn|\.gg-pi label, \.gg-pi \.gg-pi-label) \{([^}]*)\}", css))
    assert "var(--gg-font-data)" in rules[".gg-pi-btn"]
    assert "var(--gg-font-data)" in rules[".gg-pi label, .gg-pi .gg-pi-label"]
    cta = rules[".gg-pi-btn"]
    assert "color: var(--gg-color-dark-brown)" in cta and "gold" in cta


def test_page_js_is_inlined(details_page):
    assert _read(DETAILS_JS) in details_page


# ── Deploy: redirect + its own upload path ───────────────────


def test_retired_step_one_302s_to_the_questionnaire():
    import push_wordpress

    block = push_wordpress.REDIRECT_BLOCK
    assert "RewriteRule ^training-plans/start/?$ /questionnaire/ [R=302,L]" in block
    # /questionnaire/ serves the one-page form again: nothing redirects it.
    assert "RewriteRule ^questionnaire/" not in block
    assert "RewriteRule ^season-plan/?$ /questionnaire/ [R=301,L]" in block
    # Step 2 is never redirected: old two-step buyers still finish there.
    rules = [line for line in block.splitlines() if line.startswith("RewriteRule")]
    assert not [line for line in rules if "training-plans/details" in line]


def test_pages_stay_out_of_the_race_sweep():
    """Without this, sync_pages would ship plan-details.html at
    /race/plan-details/ (see sync_season_plan's docstring)."""
    import push_wordpress

    for page in gen.PAGES.values():
        assert Path(page["output_path"]).stem in push_wordpress.ROOT_CANONICAL_SLUGS
    assert hasattr(push_wordpress, "sync_plan_intake")


def test_sync_flag_uploads_to_the_served_paths():
    import inspect

    import push_wordpress

    src = inspect.getsource(push_wordpress.sync_plan_intake)
    assert "plan-start.html" not in src
    assert '"plan-details.html", "training-plans/details"' in src.replace("output_dir / ", "").replace("(", "")
    assert "/index.html" in src
    assert '"--sync-plan-intake"' in _read(ROOT / "scripts" / "push_wordpress.py")


def test_every_css_token_exists():
    from brand_tokens import get_tokens_css

    tokens = get_tokens_css()
    used = set(re.findall(r"var\((--gg-[a-z0-9-]+)\)", gen.build_intake_css()))
    missing = sorted(t for t in used if f"{t}:" not in tokens)
    assert missing == []


def test_token_leaves_the_address_bar_before_ga4(details_page):
    """The step-2 link token is a bearer credential: it must be stored and
    scrubbed from the URL before GA4's first page_view records the URL."""
    scrub = details_page.index("sessionStorage.setItem('gg_tp_details_token'")
    ga4 = details_page.index("googletagmanager.com/gtag/js")
    assert scrub < ga4
