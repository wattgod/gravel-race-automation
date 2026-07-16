"""Brand routing — sequences, senders, and UTM tags are brand-scoped.

Roadie Labs leads must never receive Gravel God copy (and vice versa),
road sends must use the road sender identity, and UTM injection must tag
links for whichever brand's domain appears in the email.
"""

from unittest.mock import patch

from mission_control.config import BRAND_SEQUENCE_SENDERS
from mission_control.sequences import (
    SEQUENCES,
    get_sequences_for_trigger,
    sequence_brand,
)
from mission_control.services.sequence_engine import (
    _inject_utm_params,
    _send_email_sync,
)


class TestSequenceBrandScoping:
    def test_gravel_sequences_default_brand(self):
        for seq_id in ("welcome_v1", "nurture_v1", "race_specific_v1",
                       "post_purchase_v1", "win_back_v1"):
            assert sequence_brand(SEQUENCES[seq_id]) == "gravelgod"

    def test_road_sequences_carry_brand(self):
        for seq_id in ("road_welcome_v1", "road_nurture_v1",
                       "road_race_specific_v1", "road_post_purchase_v1"):
            assert sequence_brand(SEQUENCES[seq_id]) == "roadielabs"

    def test_trigger_filter_defaults_to_gravel(self):
        ids = {s["id"] for s in get_sequences_for_trigger("new_subscriber")}
        assert "welcome_v1" in ids
        assert not any(i.startswith("road_") for i in ids)

    def test_road_trigger_returns_no_gravel_sequences(self):
        # Road sequences are inactive until Resend domain verification,
        # so the road filter returns [] — but never a gravel sequence.
        seqs = get_sequences_for_trigger("new_subscriber", brand="roadielabs")
        assert all(sequence_brand(s) == "roadielabs" for s in seqs)

    def test_road_sequences_activate_cleanly(self):
        # Simulate post-verification activation: active road sequences
        # must surface for the road brand and stay hidden from gravel.
        road = SEQUENCES["road_welcome_v1"]
        original = road["active"]
        try:
            road["active"] = True
            road_ids = {s["id"] for s in
                        get_sequences_for_trigger("new_subscriber", brand="roadielabs")}
            gravel_ids = {s["id"] for s in get_sequences_for_trigger("new_subscriber")}
            assert "road_welcome_v1" in road_ids
            assert "road_welcome_v1" not in gravel_ids
        finally:
            road["active"] = original

    def test_all_road_templates_exist(self):
        from pathlib import Path
        tpl_dir = (Path(__file__).resolve().parent.parent
                   / "templates" / "emails" / "sequences")
        for seq in SEQUENCES.values():
            for variant in seq["variants"].values():
                for step in variant["steps"]:
                    assert (tpl_dir / f"{step['template']}.html").exists(), (
                        f"{seq['id']} references missing template {step['template']}"
                    )


class TestBrandSenders:
    def test_both_brands_configured(self):
        for brand in ("gravelgod", "roadielabs"):
            sender = BRAND_SEQUENCE_SENDERS[brand]
            assert sender["from_email"] and "@" in sender["from_email"]
            assert sender["from_name"]
            assert sender["reply_to"]
            assert sender["utm_source"]

    def test_send_uses_road_sender_for_road_brand(self):
        sent = {}

        def fake_send(payload):
            sent.update(payload)
            return {"id": "fake"}

        with patch("resend.Emails.send", side_effect=fake_send), \
             patch("resend.api_key", "test-key"):
            _send_email_sync("rider@example.com", "subj", "<p>hi</p>", "roadielabs")

        road = BRAND_SEQUENCE_SENDERS["roadielabs"]
        assert road["from_email"] in sent["from"]
        assert road["from_name"] in sent["from"]

    def test_send_defaults_to_gravel_sender(self):
        sent = {}

        def fake_send(payload):
            sent.update(payload)
            return {"id": "fake"}

        with patch("resend.Emails.send", side_effect=fake_send), \
             patch("resend.api_key", "test-key"):
            _send_email_sync("rider@example.com", "subj", "<p>hi</p>")

        gravel = BRAND_SEQUENCE_SENDERS["gravelgod"]
        assert gravel["from_email"] in sent["from"]


class TestBrandUtm:
    def test_road_links_get_road_utm_source(self):
        html = '<a href="https://roadielabs.com/road-races/">db</a>'
        out = _inject_utm_params(html, "road_welcome_v1", "A", 0, brand="roadielabs")
        assert "utm_source=roadie_labs" in out
        assert "utm_campaign=road_welcome_v1" in out

    def test_gravel_links_get_gravel_utm_source(self):
        html = '<a href="https://gravelgodcycling.com/guide/">guide</a>'
        out = _inject_utm_params(html, "welcome_v1", "A", 1)
        assert "utm_source=gravel_god" in out

    def test_existing_query_params_preserved(self):
        html = '<a href="https://roadielabs.com/road-races/?tier=1">t1</a>'
        out = _inject_utm_params(html, "road_welcome_v1", "A", 0, brand="roadielabs")
        assert "?tier=1&" in out


class TestConditionalPersonalization:
    """The friend-opener rule: talk about THEM when the capture told us
    anything; never leak an empty placeholder or mustache syntax."""

    def _render(self, tpl, source_data):
        from mission_control.services.sequence_engine import _render_template
        return _render_template(tpl, {"contact_name": "Test Rider",
                                      "source_data": source_data})

    # Both welcome_value templates moved off race_name/race_slug onto the
    # friend-register wb_* context keys (docs/specs/friend-register-copy.md,
    # docs/specs/friend-register-copy-road.md) — they're covered separately
    # below.
    RACE_CONDITIONAL = ("anti_pitch", "repitch", "race_prep_tips",
                        "road_anti_pitch", "road_repitch",
                        "road_prep_variables")

    def test_all_race_conditional_templates_render_both_branches(self):
        for tpl in self.RACE_CONDITIONAL:
            known = self._render(tpl, {"race_name": "Big Sugar",
                                       "race_slug": "big-sugar"})
            anon = self._render(tpl, {})
            assert "Big Sugar" in known, f"{tpl}: race not personalized"
            assert "Big Sugar" not in anon, f"{tpl}: race leaked into anon branch"
            for html in (known, anon):
                assert "{{" not in html and "}}" not in html, f"{tpl}: mustache leak"

    def test_welcome_value_renders_without_leaking_placeholders(self):
        # The pitch-count-promise machinery is gone — welcome_value is now
        # the 4-branch friend-register opener (guide/trail/race/anonymous,
        # offseason-aware). This just asserts both the fully anonymous case
        # and a race-context case render clean: no mustache tags, no raw
        # {wb_*} placeholders leaking through.
        for tpl in ("welcome_value", "road_welcome_value"):
            for sd in ({}, {"race_name": "X", "race_slug": "x"}):
                html = self._render(tpl, sd)
                assert "{{" not in html and "}}" not in html, f"{tpl}: mustache leak"
                assert "{wb_guide}" not in html
                assert "{wb_trail}" not in html
                assert "{wb_race}" not in html

    def test_welcome_value_branches_are_mutually_exclusive(self):
        # Exactly one wb_* branch renders when its key + any_context are set.
        for tpl in ("welcome_value", "road_welcome_value"):
            html = self._render(tpl, {"wb_race": "Big Sugar",
                                      "any_context": "1"})
            assert "Big Sugar" in html
            assert "what race are you getting ready for" not in html
            assert "happy offseason" not in html
            assert "{{" not in html and "}}" not in html

    def test_welcome_value_offseason_branch(self):
        for tpl in ("welcome_value", "road_welcome_value"):
            html = self._render(tpl, {"offseason": "1"})
            assert "offseason" in html.lower()
            assert "what race are you getting ready for" not in html
            assert "{{" not in html and "}}" not in html
