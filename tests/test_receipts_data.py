"""receipts_data.py: the gg-receipts-v2 loader and validator (spec §6.2).

Every rejection rule has a test here. Ledgers are written to tmp_path with
synthetic people and tiny PNGs generated in the test; nothing real.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import re
import struct
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

import receipts_data as rd  # noqa: E402

TODAY = dt.date(2026, 10, 15)


def _png(path: Path, w: int = 4, h: int = 3) -> Path:
    raw = b"".join(b"\x00" + b"\x80\x80\x80" * w for _ in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    return path


def _entry(**overrides) -> dict:
    entry = {
        "id": "test-rider-a",
        "identity_tier": "first_last_initial",
        "display_name": "TestRider A.",
        "age_group": "40-44",
        "ability": "enthusiast",
        "tags": ["masters"],
        "hours_per_week": 7,
        "product": "coaching",
        "coached_since": "2024-02",
        "results": [{"event": "Example Gravel 100", "date": "2026-05-01", "placing": "3",
                     "field": 50, "time": "5:00:00",
                     "official_url": "https://example.com/results"}],
        "quote": "Synthetic quote.",
        "quote_approved_at": "2026-09-01",
        "render_approved_at": "2026-09-01",
        "material_connection": {"kind": "none", "display": ""},
        "channels": ["gravelgod", "social"],
        "consent_id": "synthetic-consent",
        "consent_expires": "2029-09-01",
        "withdrawn_at": None,
        "source_ref": "synthetic-source-ref-zz9",
        "story": {"text": "Synthetic story.", "voice": "athlete", "text_approved_at": "2026-09-01"},
        "exchanges": [{
            "id": "ex-1", "image": "media/ex-1.png",
            "alt": "Coach: synthetic. Test Rider A: synthetic.",
            "date": "2026-03-01", "theme": "synthetic", "rank": 1,
            "render_approved_at": "2026-09-01", "redaction_checked_at": "2026-09-01",
            "channels": ["gravelgod"],
        }],
    }
    entry.update(overrides)
    return entry


def _private_entry(**overrides) -> dict:
    """An entry with nothing production treats as fixture/template content
    (invented name, reserved .invalid TLD)."""
    entry = _entry(id="r-0001", display_name="Qazwi X.",
                   results=[{"event": "Sample Gravel 100", "date": "2026-05-01",
                             "official_url": "https://timing.invalid/results"}])
    entry.update(overrides)
    return entry


def _ledger(tmp_path: Path, entries, **top) -> Path:
    _png(tmp_path / "media" / "ex-1.png")
    doc = {"schema": rd.SCHEMA, "coached_count": 10, "coached_count_as_of": "2026-10-01",
           "coached_since": "2023-10", "receipts": entries}
    doc.update(top)
    path = tmp_path / "receipts.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _load(tmp_path, entries, channel="gravelgod", **top):
    return rd.load_ledger(channel, path=_ledger(tmp_path, entries, **top), today=TODAY)


def _rejected_reason(ledger, rid="test-rider-a") -> str:
    return " | ".join(why for eid, why in ledger.rejected if eid == rid)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(rd.ENV_PATH, raising=False)
    monkeypatch.delenv(rd.ENV_BUILD, raising=False)


# ── The happy path ───────────────────────────────────────────────────────


def test_valid_entry_loads(tmp_path):
    ledger = _load(tmp_path, [_entry()])
    assert [r.id for r in ledger.receipts] == ["test-rider-a"]
    r = ledger.receipts[0]
    assert r.age_band == "40s"
    assert r.exchanges[0].width == 4 and r.exchanges[0].height == 3
    assert r.exchanges[0].media_name == rd.opaque_key("test-rider-a/ex-1") + ".png"
    assert r.anchor == "athlete-" + rd.opaque_key("test-rider-a")
    assert ledger.rejected == []


def test_receipt_has_no_private_fields(tmp_path):
    r = _load(tmp_path, [_entry()]).receipts[0]
    assert not hasattr(r, "source_ref") and not hasattr(r, "consent_id")
    assert "synthetic-source-ref-zz9" not in repr(r)


def test_export_has_no_private_fields(tmp_path):
    path = _ledger(tmp_path, [_entry()])
    exported = json.dumps(rd.export_receipts("social", path=path))
    assert "synthetic-source-ref-zz9" not in exported
    assert "synthetic-consent" not in exported
    assert "source_ref" not in exported


# ── Each rejection rule ──────────────────────────────────────────────────


@pytest.mark.parametrize("field,value,reason", [
    ("consent_id", None, "missing consent_id"),
    ("consent_id", "", "missing consent_id"),
    ("render_approved_at", None, "missing render_approved_at"),
    ("quote_approved_at", None, "quote present without quote_approved_at"),
    ("consent_expires", "2026-10-14", "consent expired"),
    ("withdrawn_at", "2026-10-01", "withdrawn"),
    ("channels", ["roadie"], "not approved for channel"),
    ("identity_tier", "count_only", "count_only"),
    ("identity_tier", "nickname", "identity_tier"),
    ("ability", "pro", "ability"),
    ("product", "merch", "product"),
    ("age_group", "35-44", "age_group"),       # straddles two bands
    ("coached_since", "2024", "coached_since"),
    ("story", {"text": "Synthetic.", "voice": "athlete"}, "text_approved_at"),
    ("story", {"text": "Synthetic.", "text_approved_at": "2026-09-01"}, "story.voice"),
    ("material_connection", {"kind": "comped", "display": ""}, "material_connection.display"),
])
def test_entry_rejections(tmp_path, field, value, reason):
    ledger = _load(tmp_path, [_entry(**{field: value})])
    assert ledger.receipts == []
    assert reason in _rejected_reason(ledger), ledger.rejected


def test_consent_expiring_today_still_renders(tmp_path):
    assert _load(tmp_path, [_entry(consent_expires="2026-10-15")]).receipts


def test_no_quote_needs_no_quote_approval(tmp_path):
    assert _load(tmp_path, [_entry(quote="", quote_approved_at=None)]).receipts


@pytest.mark.parametrize("result,reason", [
    ({"event": "Example Gravel", "date": "2026-05-01"}, "official_url"),
    ({"event": "Example Gravel", "date": "2026-05-01", "official_url": ""}, "official_url"),
    ({"event": "Example Gravel", "date": "2026-05-01",
      "official_url": "http://example.com/results"}, "official_url"),
    ({"event": "", "date": "2026-05-01", "official_url": "https://example.com/r"}, "event"),
    ({"event": "Example Gravel", "date": "May 2026", "official_url": "https://example.com/r"}, "date"),
])
def test_result_rejections(tmp_path, result, reason):
    ledger = _load(tmp_path, [_entry(results=[result])])
    assert ledger.receipts == []
    assert reason in _rejected_reason(ledger)


@pytest.mark.parametrize("key", [
    "hr", "hrv", "weight", "wkg", "w_kg", "medication", "medical_notes", "heart_rate",
    "resting_hr", "body_fat", "weight_kg",
    # Review finding 3: all of these passed at 9bae68c.
    "avg_hr", "hr_avg", "hr_max", "threshold_hr", "hrv_rmssd", "rmssd", "pulse",
    "notes_medical", "diagnosis", "injury", "health",
])
def test_health_fields_fail_the_load(tmp_path, key):
    with pytest.raises(rd.ReceiptValidationError, match="health"):
        _load(tmp_path, [_entry(**{key: 1})])


def test_health_field_nested_in_a_result_fails(tmp_path):
    res = dict(_entry()["results"][0], wkg=4.2)
    with pytest.raises(rd.ReceiptValidationError, match="health"):
        _load(tmp_path, [_entry(results=[res])])


@pytest.mark.parametrize("where,text", [
    ("quote", "Dropped to 68 kg before the race."),
    ("quote", "Hit 4.5 W/kg for twenty minutes."),
    ("quote", "lost 12 lbs over the winter"),
    ("story", "Held 150 bpm all day."),
    ("story", "My HRV finally recovered."),
    ("alt", "Coach: what was your watts per kilo? Test Rider A: no idea."),
    ("alt", "Test Rider A: my resting heart rate is up."),
    # Review finding 3: all of these passed at 9bae68c.
    ("quote", "avg HR 172 the whole way"),
    ("quote", "HR 165"),
    ("quote", "my HR was through the roof"),
    ("quote", "Zone 2 HR cap"),
    ("quote", "4.2w/kg for 20 min"),
    ("quote", "holding 4.1 watts/kg"),
    ("alt", "Coach: resting pulse 44? Test Rider A: yep."),
    # Re-review finding B: lower-case hr readings passed at eb1f7de.
    ("quote", "avg hr 172"),
    ("story", "my hr was 180 on the climb"),
    ("alt", "Test Rider A: Hr: 171 at the top"),
    ("quote", "sat at 165 hr for an hour"),
])
def test_health_text_fails_the_load(tmp_path, where, text):
    entry = _entry()
    if where == "quote":
        entry["quote"] = text
    elif where == "story":
        entry["story"] = dict(entry["story"], text=text)
    else:
        entry["exchanges"][0]["alt"] = text
    with pytest.raises(rd.ReceiptValidationError, match="health"):
        _load(tmp_path, [entry])


def test_health_key_inside_an_exchange_fails(tmp_path):
    entry = _entry()
    entry["exchanges"][0]["avg_hr"] = 150
    with pytest.raises(rd.ReceiptValidationError, match="health"):
        _load(tmp_path, [entry])


def test_tags_are_an_allow_list(tmp_path):
    """Tags go to export_receipts (social/email); free text could leak."""
    ledger = _load(tmp_path, [_entry(tags=["masters", "recovering_from_surgery"])])
    assert ledger.receipts == []
    assert "allow-list" in _rejected_reason(ledger)


def test_health_reading_in_a_tag_fails_the_load(tmp_path):
    with pytest.raises(rd.ReceiptValidationError, match="health"):
        _load(tmp_path, [_entry(tags=["hr 172 club"])])


# ── Medical wording: excluded and logged, never shipped, never build-wide ──
# (re-review finding A)

MEDICAL = [
    ("story", "doc put me on meds"),
    ("story", "my cardiologist cleared me"),
    ("story", "asthma flared at mile 40"),
    ("story", "an afib episode in March"),
    ("quote", "beta blockers cap everything"),
    ("quote", "I came back from injury."),
    ("story", "After surgery I raced again."),
    ("quote", "they changed my prescribed medication"),
]


def _with_text(entry, where, text):
    if where == "quote":
        entry["quote"] = text
    elif where == "story":
        entry["story"] = dict(entry["story"], text=text)
    else:
        entry["exchanges"][0]["alt"] = text
    return entry


@pytest.mark.parametrize("where,text", MEDICAL)
def test_medical_wording_leaves_the_entry_out(tmp_path, where, text):
    ledger = _load(tmp_path, [_with_text(_entry(), where, text), _entry(id="test-rider-b")])
    assert [r.id for r in ledger.receipts] == ["test-rider-b"]  # the build still runs
    assert "medical context" in _rejected_reason(ledger)


@pytest.mark.parametrize("where,text", MEDICAL)
def test_reviewed_medical_wording_renders(tmp_path, where, text):
    entry = _with_text(_entry(health_wording_reviewed_at="2026-10-01"), where, text)
    assert [r.id for r in _load(tmp_path, [entry]).receipts] == ["test-rider-a"]


def test_review_never_overrides_numeric_readings(tmp_path):
    entry = _with_text(_entry(health_wording_reviewed_at="2026-10-01"), "quote", "avg HR 172")
    with pytest.raises(rd.ReceiptValidationError, match="health"):
        _load(tmp_path, [entry])


def test_bad_review_date_is_rejected(tmp_path):
    ledger = _load(tmp_path, [_entry(health_wording_reviewed_at="yes")])
    assert "health_wording_reviewed_at" in _rejected_reason(ledger)


def test_medical_wording_in_one_exchange_drops_only_that_exchange(tmp_path):
    entry = _with_text(_entry(), "alt", "Coach: how's the injury? Test Rider A: fine.")
    ledger = _load(tmp_path, [entry])
    assert ledger.receipts[0].exchanges == ()
    assert "medical context" in _rejected_reason(ledger)


@pytest.mark.parametrize("change", [
    {"withdrawn_at": "2026-10-01"},
    {"channels": ["roadie"]},
    {"consent_expires": "2026-01-01"},
    {"identity_tier": "count_only"},
])
@pytest.mark.parametrize("text", ["I came back from injury.", "avg HR 172", "lost 6 kg"])
def test_unrenderable_entries_are_never_content_checked(tmp_path, change, text):
    """A withdrawal must always build: content in an entry this channel can't
    render never stops the build."""
    bad = _with_text(_entry(**change), "quote", text)
    ledger = _load(tmp_path, [bad, _entry(id="test-rider-b")])
    assert [r.id for r in ledger.receipts] == ["test-rider-b"]


def test_withdrawn_exchange_is_never_content_checked(tmp_path):
    entry = _entry()
    entry["exchanges"][0].update(withdrawn_at="2026-10-01", alt="Test Rider A: avg HR 172")
    ledger = _load(tmp_path, [entry])
    assert ledger.receipts[0].exchanges == ()


@pytest.mark.parametrize("text", [
    "as prescribed", "Do the prescribed intervals", "the race doctor",
    "a depression in the gravel road", "diagnose the pacing problem", "the pulse of the race",
    "a 3 hr ride", "2hrs on the trainer", "a 10 hr week", "2 HRs of riding", "8 hrs/week",
    "the media day", "Medal at the finish.",
])
def test_ordinary_words_are_not_health_text(text):
    assert rd.health_text_findings(text) == []


@pytest.mark.parametrize("key,health", [
    ("mass_start_wave", False), ("medals", False), ("media", False), ("hours_per_week", False),
    ("health_wording_reviewed_at", False), ("body_mass", True), ("avg_hr", True),
    ("hrvRmssd", True), ("w_kg", True), ("heartrate", True), ("notes_medical", True),
])
def test_health_keys_are_matched_by_token(key, health):
    assert rd._is_health_key(key) is health


@pytest.mark.parametrize("tier,name,ok", [
    ("first_last_initial", "TestRider A.", True),
    ("first_last_initial", "Test Rider A", False),
    ("first_last_initial", "TestRider Abc", False),
    ("first_age_group", "TestRider", True),
    ("first_age_group", "TestRider A.", False),
    ("full_name", "Test Rider", True),
    ("full_name", "TestRider", False),
    # Re-review finding C.
    ("first_last_initial", "Jon Ø.", True),
    ("first_last_initial", "Åse Ø.", True),
    ("first_last_initial", "Jon ø.", False),
    ("first_last_initial", "Jon 3.", False),
    ("first_age_group", "Åse", True),
    ("first_age_group", "Mary-Ann", True),
    ("first_age_group", "O'Neil", True),
    ("first_age_group", "Jane.Smithson", False),
    ("first_age_group", "Jane_Smithson", False),
    ("first_age_group", "Jane2", False),
])
def test_display_name_fits_identity_tier(tmp_path, tier, name, ok):
    """Review finding 5: a 'first + initial' consent can't render a full name."""
    ledger = _load(tmp_path, [_entry(identity_tier=tier, display_name=name)])
    assert bool(ledger.receipts) == ok, ledger.rejected
    if not ok:
        assert "doesn't fit identity_tier" in _rejected_reason(ledger)


def test_results_and_media_keys_are_not_health_fields(tmp_path):
    """'media'/'medal' start with 'med' but aren't medical."""
    assert _load(tmp_path, [_entry(medal="gold", media_note="synthetic")]).receipts


# ── Exchanges ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("change,reason", [
    ({"alt": ""}, "missing alt"),
    ({"alt": None}, "missing alt"),
    ({"render_approved_at": None}, "missing render_approved_at"),
    ({"image": "media/missing.png"}, "image file missing"),
    ({"image": "../outside.png"}, "outside the ledger directory"),
    ({"image": "/etc/hosts"}, "relative to the ledger"),
    ({"image": "media/ex-1.gif"}, "image must be one of"),
    ({"channels": ["roadie"]}, "not approved for channel"),
    ({"rank": "1"}, "rank"),
    ({"date": "2026-03"}, "date"),
    # Review findings 3 and 4.
    ({"redaction_checked_at": None}, "redaction_checked_at"),
    ({"withdrawn_at": "2026-10-01"}, "withdrawn"),
    ({"consent_expires": "2026-10-14"}, "consent expired"),
    ({"consent_expires": "soon"}, "consent_expires"),
    ({"caption_override": "x"}, "unknown key"),
])
def test_exchange_rejections(tmp_path, change, reason):
    entry = _entry()
    entry["exchanges"][0].update(change)
    ledger = _load(tmp_path, [entry])
    # The athlete still renders; the bad exchange is left out.
    assert [r.id for r in ledger.receipts] == ["test-rider-a"]
    assert ledger.receipts[0].exchanges == ()
    assert reason in _rejected_reason(ledger), ledger.rejected


def test_exchange_note_keys_are_allowed(tmp_path):
    entry = _entry()
    entry["exchanges"][0]["//alt"] = "a note, like the template's"
    assert _load(tmp_path, [entry]).receipts[0].exchanges


def test_exchange_image_with_unreadable_dimensions(tmp_path):
    path = _ledger(tmp_path, [_entry()])
    (tmp_path / "media" / "ex-1.png").write_bytes(b"not a png")
    ledger = rd.load_ledger(path=path, today=TODAY)
    assert "dimensions" in _rejected_reason(ledger)


def test_exchanges_sorted_by_rank(tmp_path):
    entry = _entry()
    _png(tmp_path / "media" / "ex-2.png", 3, 5)
    entry["exchanges"].append(dict(entry["exchanges"][0], id="ex-2", image="media/ex-2.png", rank=0))
    ledger = _load(tmp_path, [entry])
    assert [e.id for e in ledger.exchanges] == ["ex-2", "ex-1"]


# ── Ledger-level rules ──────────────────────────────────────────────────


def test_wrong_schema_fails(tmp_path):
    with pytest.raises(rd.ReceiptValidationError, match="schema"):
        _load(tmp_path, [_entry()], schema="gg-testimonials-v1")


def test_duplicate_ids_fail(tmp_path):
    with pytest.raises(rd.ReceiptValidationError, match="duplicate"):
        _load(tmp_path, [_entry(), _entry()])


def test_coached_count_below_ledger_size_fails(tmp_path):
    with pytest.raises(rd.ReceiptValidationError, match="coached_count"):
        _load(tmp_path, [_entry(), _entry(id="test-rider-b")], coached_count=1)


def test_unknown_channel_argument_fails(tmp_path):
    with pytest.raises(ValueError):
        _load(tmp_path, [_entry()], channel="myspace")


# ── Path resolution and production builds ────────────────────────────────


def test_ci_falls_back_to_the_synthetic_fixture():
    assert rd.resolve_ledger_path() == rd.FIXTURE_PATH
    ledger = rd.load_ledger()
    assert ledger.synthetic and ledger.receipts


def test_env_path_wins(tmp_path, monkeypatch):
    path = _ledger(tmp_path, [_entry()])
    monkeypatch.setenv(rd.ENV_PATH, str(path))
    assert rd.resolve_ledger_path() == path


def test_production_refuses_the_fixture_fallback(monkeypatch):
    monkeypatch.setenv(rd.ENV_BUILD, "production")
    with pytest.raises(rd.ReceiptsConfigError, match="synthetic"):
        rd.load_ledger()


def test_production_refuses_the_fixture_even_by_path(monkeypatch):
    monkeypatch.setenv(rd.ENV_BUILD, "production")
    monkeypatch.setenv(rd.ENV_PATH, str(rd.FIXTURE_PATH))
    with pytest.raises(rd.ReceiptsConfigError, match="synthetic"):
        rd.load_ledger()


def test_production_refuses_a_ledger_marked_synthetic(tmp_path, monkeypatch):
    monkeypatch.setenv(rd.ENV_BUILD, "production")
    with pytest.raises(rd.ReceiptsConfigError):
        _load(tmp_path, [_entry()], synthetic=True)


@pytest.mark.parametrize("change,what", [
    ({"id": "synthetic-rider-z"}, "id"),
    ({"id": "example-rider"}, "id"),
    # Re-review finding D: ids are public, so production wants opaque r-NNN.
    ({"id": "jane-smithson"}, "opaque"),
    ({"id": "r-12"}, "opaque"),
    ({"display_name": "Test Rider Z", "identity_tier": "full_name"}, "display_name"),
    ({"display_name": "Example R."}, "display_name"),
    ({"results": [{"event": "X", "date": "2026-05-01",
                   "official_url": "https://www.example.org/r"}]}, "official_url"),
    ({"quote": "Example quote text. Replace with the athlete's exact approved words."},
     "template text"),
])
def test_production_refuses_fixture_or_template_content(tmp_path, monkeypatch, change, what):
    """Review finding 6: not just the synthetic flag."""
    monkeypatch.setenv(rd.ENV_BUILD, "production")
    with pytest.raises(rd.ReceiptsConfigError, match=what):
        _load(tmp_path, [_private_entry(**change)])


@pytest.mark.parametrize("rid", ["r-001", "r-0042", "r-1234"])
def test_production_accepts_opaque_ids(tmp_path, monkeypatch, rid):
    monkeypatch.setenv(rd.ENV_BUILD, "production")
    assert _load(tmp_path, [_private_entry(id=rid)]).receipts


def test_production_accepts_a_private_shaped_entry(tmp_path, monkeypatch):
    monkeypatch.setenv(rd.ENV_BUILD, "production")
    assert _load(tmp_path, [_private_entry()]).receipts


def test_production_reads_the_private_path(tmp_path, monkeypatch):
    path = _ledger(tmp_path, [_private_entry()])
    monkeypatch.setenv(rd.ENV_BUILD, "production")
    monkeypatch.setenv(rd.ENV_PATH, str(path))
    ledger = rd.load_ledger(today=TODAY)
    assert not ledger.synthetic and ledger.path == path and ledger.receipts


def test_missing_ledger_file_fails(tmp_path, monkeypatch):
    monkeypatch.setenv(rd.ENV_PATH, str(tmp_path / "nope.json"))
    with pytest.raises(rd.ReceiptsConfigError, match="not found"):
        rd.load_ledger()


def test_resolve_receipt_id(tmp_path):
    path = _ledger(tmp_path, [_entry(), _entry(id="test-rider-b", withdrawn_at="2026-10-01")])
    assert rd.resolve_receipt_id("test-rider-a", path=path)
    assert not rd.resolve_receipt_id("test-rider-b", path=path)
    assert not rd.resolve_receipt_id("made-up", path=path)


@pytest.mark.parametrize("group,band", [
    ("U23", "Under 30"), ("25-29", "Under 30"), ("30-34", "30s"), ("35-39", "30s"),
    ("40-44", "40s"), ("45-49", "40s"), ("50-54", "50+"), ("70+", "50+"),
    ("25-34", None), ("U35", None), ("40+", None), ("forty", None),
])
def test_age_band(group, band):
    assert rd.age_band(group) == band


# ── The committed fixture stays obviously fake ───────────────────────────


def test_fixture_people_are_obviously_synthetic():
    doc = json.loads(rd.FIXTURE_PATH.read_text(encoding="utf-8"))
    assert doc["synthetic"] is True
    race_names = {r["name"].lower() for r in json.loads(
        (ROOT / "web" / "race-index.json").read_text(encoding="utf-8"))}
    for e in doc["receipts"]:
        assert re.fullmatch(r"r-9\d\d", e["id"]), e["id"]  # r-9xx: fixture range
        assert e["display_name"] in ("",) or e["display_name"].startswith("Test"), e
        assert e["consent_id"].startswith("synthetic-")
        assert e["source_ref"].startswith("synthetic-")
        for text in (e.get("quote") or "", (e.get("story") or {}).get("text", "")):
            assert not text or "Synthetic" in text
        for res in e["results"]:
            assert res["official_url"].startswith(("https://example.com/", "https://example.org/"))
            assert res["event"].startswith("Example "), res["event"]
            assert res["event"].lower() not in race_names
        for ex in e["exchanges"]:
            assert "Synthetic" in ex["alt"] or "synthetic" in ex["alt"]
    blob = rd.FIXTURE_PATH.read_text(encoding="utf-8")
    assert "@" not in blob, "no email addresses in fixtures"
    assert not re.search(r"\+?\d[\d\s().-]{8,}\d", blob.replace("2026-", "").replace("2029-", "")
                         .replace("2023-", "").replace("2024-", "").replace("2025-", "")), \
        "nothing phone-shaped in fixtures"


def test_fixture_media_are_tiny_placeholders():
    media = sorted((rd.FIXTURE_PATH.parent / "receipts_media").glob("*"))
    assert media
    for f in media:
        assert f.stat().st_size < 1024, f"{f.name} is not a tiny synthetic placeholder"
        w, h = rd.image_size(f)
        assert w <= 16 and h <= 16


# ── The ledger template Matti copies (docs/receipts-ledger-template.json) ──

TEMPLATE = ROOT / "docs" / "receipts-ledger-template.json"


def test_template_is_a_valid_synthetic_ledger():
    doc = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    assert doc["synthetic"] is True
    assert len(doc["receipts"]) == 1
    ledger = rd.parse_ledger(doc, path=TEMPLATE, today=TODAY)
    assert [r.id for r in ledger.receipts] == ["r-001"]
    # Its screenshot doesn't exist in this repo, so the exchange is left out.
    assert any("image file missing" in why for _, why in ledger.rejected)


def test_template_documents_every_field():
    doc = json.loads(TEMPLATE.read_text(encoding="utf-8"))

    def undocumented(node, trail=""):
        missing = []
        if isinstance(node, dict):
            for key, value in node.items():
                if key.startswith("//"):
                    continue
                if f"//{key}" not in node:
                    missing.append(f"{trail}.{key}")
                missing += undocumented(value, f"{trail}.{key}")
        elif isinstance(node, list):
            for item in node:
                missing += undocumented(item, trail + "[]")
        return missing

    entry = doc["receipts"][0]
    assert undocumented(entry) == []
    for key in ("schema", "synthetic", "coached_count", "coached_count_as_of", "coached_since"):
        assert f"//{key}" in doc


def test_template_holds_no_real_data():
    blob = TEMPLATE.read_text(encoding="utf-8")
    entry = json.loads(blob)["receipts"][0]
    assert entry["display_name"].startswith("Example")
    assert entry["results"][0]["official_url"].startswith("https://example.com/")
    assert "@" not in blob
