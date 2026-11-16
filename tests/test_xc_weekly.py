"""XC Ski Labs Weekly: collection, the publication gate, rendering, sending."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import collect_xc_weekly as collect  # noqa: E402
import draft_xc_weekly as draft  # noqa: E402
import xc_weekly_issue as xi  # noqa: E402

NOW = datetime(2026, 11, 16, 6, 30, tzinfo=timezone.utc)


def rss(items: list[tuple[str, str, datetime, list[str]]], channel_link="https://example.no/") -> bytes:
    body = "".join(
        f"<item><title>{t}</title><link>{link}</link>"
        f"<pubDate>{d.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>"
        f"<description>&lt;p&gt;About {t}&lt;/p&gt;</description>"
        + "".join(f"<category>{c}</category>" for c in cats)
        + "</item>"
        for t, link, d, cats in items
    )
    return f'<?xml version="1.0"?><rss version="2.0"><channel><link>{channel_link}</link>{body}</channel></rss>'.encode()


class FakeSession:
    def __init__(self, pages: dict[str, bytes | int]):
        self.pages, self.calls = pages, []

    def get(self, url, timeout, headers):
        self.calls.append(url)
        value = self.pages.get(url, 404)
        if isinstance(value, int):
            response = SimpleNamespace(status_code=value)

            def fail():
                import requests
                raise requests.HTTPError(response=response)
            return SimpleNamespace(raise_for_status=fail, content=b"")
        return SimpleNamespace(raise_for_status=lambda: None, content=value)


# ── Sources ────────────────────────────────────────────────────

def test_source_config_is_https_unique_and_complete():
    config = collect.load_sources()
    sources = config["news"] + config["podcasts"]
    ids = [s["id"] for s in sources]
    assert len(ids) == len(set(ids))
    for s in sources:
        assert s["feed"].startswith("https://"), s["id"]
        assert s["lang"] in xi.LANG_NAMES
        assert s.get("show_url", "https://").startswith("https://")
    names = {s["name"] for s in config["news"]}
    assert {"Langrenn.com", "FasterSkier", "NRK Sport"} <= names
    assert config["podcasts"], "podcasts are part of the spec"


def test_parse_rss_and_atom():
    entries, link = collect.parse_feed(rss([("Klæbo vinner", "https://x.no/a", NOW, ["Langrenn"])]))
    assert link == "https://example.no/"
    assert entries[0]["title"] == "Klæbo vinner"
    assert entries[0]["description"] == "About Klæbo vinner"
    atom = (b'<feed xmlns="http://www.w3.org/2005/Atom"><link href="https://a.example/"/>'
            b'<entry><title>T</title><link href="https://a.example/1"/>'
            b'<updated>2026-11-15T10:00:00Z</updated><summary>S</summary></entry></feed>')
    entries, link = collect.parse_feed(atom)
    assert link == "https://a.example/"
    assert entries[0]["link"] == "https://a.example/1"
    assert entries[0]["published"] == datetime(2026, 11, 15, 10, tzinfo=timezone.utc)


@pytest.mark.parametrize("source,categories,title,kept", [
    ({"exclude_categories": ["skiskyting"]}, ["Skiskyting", "Idre"], "Öberg vinner", False),
    ({"exclude_categories": ["skiskyting"]}, ["Langrenn Allround"], "Klæbo", True),
    ({"include_keywords": ["langrenn"]}, ["sport, vintersport, langrenn"], "Visum", True),
    ({"include_keywords": ["langrenn"]}, ["Fotball"], "Kane scorer", False),
    ({"exclude_categories": ["skiskyting"]}, ["skiskyting, sport, vintersport"], "Botn", False),
])
def test_cross_country_filters(source, categories, title, kept):
    entry = {"title": title, "description": "", "categories": categories}
    assert collect.keep_entry(entry, source) is kept


def test_collect_keeps_window_pages_and_drops_unlinkable_items():
    old = NOW - timedelta(days=12)
    source = {"id": "langrenn", "name": "Langrenn.com", "lang": "no",
              "feed": "https://www.langrenn.com/feed", "pages": 5}
    session = FakeSession({
        "https://www.langrenn.com/feed": rss([
            ("Ny", "https://www.langrenn.com/ny", NOW - timedelta(hours=3), ["Langrenn"]),
            ("Uten lenke", "", NOW - timedelta(hours=4), ["Langrenn"]),
        ]),
        "https://www.langrenn.com/feed?paged=2": rss([
            ("Eldre", "https://www.langrenn.com/eldre", NOW - timedelta(days=2), []),
            ("For gammel", "https://www.langrenn.com/gammel", old, []),
        ]),
    })
    items, coverage = collect.collect_source(source, "news", NOW - timedelta(days=7), session)
    assert [i["title"] for i in items] == ["Ny", "Eldre"]
    assert coverage["errors"] == []
    assert "https://www.langrenn.com/feed?paged=3" not in session.calls  # stopped once past the window


def test_failed_feed_is_reported_not_replaced():
    source = {"id": "nrk", "name": "NRK Sport", "lang": "no", "feed": "https://www.nrk.no/x.rss"}
    items, coverage = collect.collect_source(source, "news", NOW - timedelta(days=7), FakeSession({}))
    assert items == []
    assert coverage["errors"] == ["https://www.nrk.no/x.rss: HTTP 404"]


def test_podcast_without_episode_link_uses_the_verified_show_page():
    source = {"id": "skidsnack", "name": "Skidsnack", "lang": "sv",
              "feed": "https://pod.example/feed", "show_url": "https://www.aftonbladet.se/skidsnack"}
    session = FakeSession({"https://pod.example/feed": rss([("239. Avsnitt", "", NOW - timedelta(days=1), [])])})
    items, _ = collect.collect_source(source, "podcast", NOW - timedelta(days=7), session)
    assert items[0]["url"] == "https://www.aftonbladet.se/skidsnack"


# ── The publication gate ───────────────────────────────────────

def evidence(n_news=6):
    items = [{
        "id": f"n{k}", "kind": "news", "sourceId": "langrenn", "sourceName": "Langrenn.com",
        "lang": "no", "title": f"Nyhet nummer {k} om langrenn", "url": f"https://www.langrenn.com/{k}",
        "published": (NOW - timedelta(days=1)).isoformat(), "categories": [],
        "excerpt": "Klæbo vant sprinten i Ruka foran hele det norske laget og sa at formen er god",
    } for k in range(1, n_news + 1)]
    items.append({
        "id": "p1", "kind": "podcast", "sourceId": "kershaw", "sourceName": "The Devon Kershaw Show",
        "lang": "en", "title": "Season opener", "url": "https://share.transistor.fm/s/abc",
        "published": (NOW - timedelta(days=2)).isoformat(), "categories": [], "excerpt": "",
    })
    return {"since": (NOW - timedelta(days=7)).isoformat(), "collectedAt": NOW.isoformat(),
            "items": items, "coverage": []}


def selection(**overrides):
    base = {
        "subject": "FIS keeps three Russians out of the opener",
        "preheader": "Plus registration opens for two Ski Classics races.",
        "take": ["I think the federation fight will run all winter [1]. The racing in Muonio "
                 "was the better story: unknown names beat the stars on a cold weekend, and "
                 "that is the best thing November can give you [2]. Register early for the "
                 "spring races, because the fields fill before the snow does."],
        "stories": [{"itemId": f"n{k}", "headline": f"Story {k} in plain words",
                     "blurb": "A short summary in my own words of what happened and why it matters."}
                    for k in range(1, 6)],
        "podcasts": [{"itemId": "p1", "blurb": "Kershaw talks through the first race weekend."}],
    }
    base.update(overrides)
    return base


def test_clean_issue_passes_and_takes_links_from_evidence():
    issue = xi.validate_issue(xi.assemble_issue(selection(), evidence(), 1, "2026-11-16"), evidence())
    assert issue["stories"][0]["url"] == "https://www.langrenn.com/1"
    assert issue["podcasts"][0]["show"] == "The Devon Kershaw Show"
    assert issue["status"] == "draft"


def test_unknown_or_wrong_kind_item_is_refused():
    with pytest.raises(xi.IssueError, match="not a collected news item"):
        xi.assemble_issue(selection(stories=[{"itemId": "made-up", "headline": "h", "blurb": "b"}]),
                          evidence(), 1, "2026-11-16")
    with pytest.raises(xi.IssueError, match="not a collected episode"):
        xi.assemble_issue(selection(podcasts=[{"itemId": "n1", "blurb": "b"}]), evidence(), 1, "2026-11-16")


@pytest.mark.parametrize("field,text,reason", [
    ("blurb", "An AI summary of the race.", "mentions AI"),
    ("blurb", "Matti thinks this matters.", "third person"),
    ("blurb", "Ask your coach about it.", "coach wording"),
    ("blurb", "He said “it was cold” after the race.", "quotation marks"),
    ("blurb", "Read more at https://example.com today.", "URL"),
    ("blurb", "A game-changer for the sport this winter.", "slop"),
    ("blurb", "Generated from the week's feeds.", "automation"),
    ("headline", "Klæbo — again — wins", "em dashes"),
])
def test_gate_refuses_banned_copy(field, text, reason):
    picks = selection()
    picks["stories"][0][field] = text
    with pytest.raises(xi.IssueError, match=reason):
        xi.validate_issue(xi.assemble_issue(picks, evidence(), 1, "2026-11-16"), evidence())


def test_gate_refuses_a_reprinted_passage():
    picks = selection()
    picks["stories"][0]["blurb"] = "Klæbo vant sprinten i Ruka foran hele det norske laget, again."
    with pytest.raises(xi.IssueError, match="reprints the source"):
        xi.validate_issue(xi.assemble_issue(picks, evidence(), 1, "2026-11-16"), evidence())


def test_take_markers_must_resolve_and_exist():
    for take, reason in (
        (["I think nothing happened this week worth arguing about, and the snow in Ruka was thin. "
          "That is all I have for you, so go ski."], "at least one story"),
        (["I think the federation fight will run all winter [9], and the racing was better than "
          "the politics on every count this week."], r"marker \[9\]"),
    ):
        with pytest.raises(xi.IssueError, match=reason):
            xi.validate_issue(xi.assemble_issue(selection(take=take), evidence(), 1, "2026-11-16"), evidence())


def test_story_count_limits():
    picks = selection(stories=selection()["stories"][:3])
    with pytest.raises(xi.IssueError, match="needs 4-10 stories"):
        xi.validate_issue(xi.assemble_issue(picks, evidence(), 1, "2026-11-16"), evidence())


def test_edited_issue_fails_the_hash():
    issue = xi.assemble_issue(selection(), evidence(), 1, "2026-11-16")
    issue["stories"][0]["url"] = "https://evil.example/"
    with pytest.raises(xi.IssueError, match="contentHash"):
        xi.validate_issue(issue, evidence())


# ── Rendering ──────────────────────────────────────────────────

def test_email_carries_can_spam_footer_unsubscribe_and_language_notes():
    issue = xi.assemble_issue(selection(), evidence(), 1, "2026-11-16")
    body = xi.render_email_html(issue)
    assert "XC Ski Labs · 2183 Lombardy St, Longmont, CO 80503" in body
    assert "{{{RESEND_UNSUBSCRIBE_URL}}}" in body
    assert "(in Norwegian)" in body
    assert "No. 001 · 16 November 2026" in body
    assert 'href="https://www.langrenn.com/1"' in body  # marker [1] links to its story
    assert "PREVIEW" not in body
    assert "Gravel God" not in body
    assert "PREVIEW FOR REVIEW" in xi.render_email_html(issue, preview_banner="PREVIEW FOR REVIEW")


def test_email_escapes_feed_text():
    ev = evidence()
    ev["items"][0]["sourceName"] = "<script>x</script>"
    issue = xi.assemble_issue(selection(), ev, 1, "2026-11-16")
    assert "<script>x</script>" not in xi.render_email_html(issue)


def test_review_markdown_lists_hash_links_and_coverage():
    issue = xi.assemble_issue(selection(), evidence(), 1, "2026-11-16")
    md = xi.render_review_markdown(issue, [{"name": "NRK Sport", "kind": "news", "kept": 0,
                                            "errors": ["HTTP 500"]}])
    assert issue["contentHash"] in md
    assert "[[1]](https://www.langrenn.com/1)" in md
    assert "| NRK Sport | news | 0 | HTTP 500 |" in md


def test_voice_brief_carries_the_rules():
    brief = draft.VOICE_PATH.read_text()
    for needle in ("Johnny Klister", "Never mention AI", "No quotation marks", "Summarise; never reprint",
                   "inbox/gravel-god/"):
        assert needle in brief


# ── Drafting ───────────────────────────────────────────────────

class FakeClient:
    def __init__(self, replies):
        self.replies, self.requests = list(replies), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        reply = self.replies.pop(0)
        return SimpleNamespace(stop_reason="end_turn",
                               content=[SimpleNamespace(type="text", text=json.dumps(reply))])


def test_draft_uses_opus_with_schema_and_repairs_once():
    bad = selection(take=["Matti thinks the opener mattered [1], and the rest of the week was quiet "
                          "enough that I spent it waxing."])
    client = FakeClient([bad, selection()])
    issue = draft.draft(evidence(), 3, "2026-11-16", client=client)
    assert issue["issueNumber"] == 3
    first = client.requests[0]
    assert first["model"] == "claude-opus-5-5"
    assert first["output_config"]["format"]["type"] == "json_schema"
    assert first["fallbacks"] == "default"
    assert "third person" in client.requests[1]["messages"][-1]["content"]


def test_draft_gives_up_after_one_repair():
    bad = selection(subject="An AI round-up")
    with pytest.raises(xi.IssueError):
        draft.draft(evidence(), 1, "2026-11-16", client=FakeClient([bad, bad]))


def test_load_evidence_merges_snapshots_and_trims_to_seven_days(tmp_path):
    a = evidence()
    a["items"].append({**a["items"][0], "id": "stale", "published": (NOW - timedelta(days=9)).isoformat()})
    a["coverage"] = [{"id": "langrenn", "name": "Langrenn.com", "kind": "news", "kept": 7, "errors": []}]
    b = {**evidence(), "collectedAt": (NOW - timedelta(days=1)).isoformat(),
         "coverage": [{"id": "langrenn", "name": "Langrenn.com", "kind": "news", "kept": 1, "errors": []}]}
    (tmp_path / "a.json").write_text(json.dumps(a))
    (tmp_path / "b.json").write_text(json.dumps(b))
    merged = draft.load_evidence([tmp_path / "a.json", tmp_path / "b.json"], NOW)
    ids = [i["id"] for i in merged["items"]]
    assert "stale" not in ids and len(ids) == len(set(ids)) == 7
    assert merged["coverage"][0]["kept"] == 6


def test_stage_never_allows_auto_send(tmp_path):
    issue = xi.assemble_issue(selection(), evidence(), 1, "2026-11-16")
    manifest = draft.stage(issue, evidence(), tmp_path)
    assert manifest["humanApprovalRequired"] is True and manifest["autoSendAllowed"] is False
    assert (tmp_path / "preview.html").read_text().count("Lombardy") == 1


# ── Sending ────────────────────────────────────────────────────

def test_broadcast_refuses_an_unapproved_hash(monkeypatch):
    import send_xc_weekly as send
    issue = xi.assemble_issue(selection(), evidence(), 1, "2026-11-16")
    monkeypatch.setattr(send, "fetch_opted_out", lambda: pytest.fail("must refuse before any lookup"))
    with pytest.raises(RuntimeError, match="not the approved hash"):
        send.broadcast(issue, "0000000000000000")


def test_next_issue_number_counts_sent_xc_broadcasts_only(monkeypatch):
    import send_xc_weekly as send
    monkeypatch.setattr(send, "list_broadcasts", lambda: [
        {"name": "XC Ski Labs Weekly No. 004 · 2026-12-07 · abc", "status": "sent"},
        {"name": "XC Ski Labs Weekly No. 005 · 2026-12-14 · def", "status": "draft"},
        {"name": "Gravel Weekly #031 · 2026-12-07 · x", "status": "sent"},
    ])
    assert send.next_issue_number() == 5


def test_subscriber_query_is_xc_opt_ins(monkeypatch):
    import send_xc_weekly as send
    seen = []

    def fake_req(url, headers=None):
        seen.append(url)
        return [{"contact_email": " A@Example.com "}] if len(seen) == 1 else []
    monkeypatch.setenv("SUPABASE_URL", "https://db.example")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    monkeypatch.setattr(send, "_req", fake_req)
    assert send.fetch_subscribers() == ["a@example.com"]
    assert "source_data-%3E%3Ebrand=eq.xcskilabs" in seen[0]
    assert "newsletter_opt_in_at=not.is.null" in seen[0]


def test_http_errors_show_the_api_reason_without_addresses(capsys, monkeypatch):
    import io
    import urllib.error

    import send_xc_weekly as sx

    body = b'{"message":"Contact rider@example.com is restricted","name":"restricted_api_key"}'
    error = urllib.error.HTTPError(
        "https://api.resend.com/contacts/rider%40example.com", 403, "Forbidden", {}, io.BytesIO(body))
    monkeypatch.setenv("RESEND_API_KEY", "test")
    monkeypatch.setattr(sx, "next_issue_number", lambda: (_ for _ in ()).throw(error))
    assert sx.main(["--next-issue-number"]) == 1
    err = capsys.readouterr().err
    assert "restricted_api_key" in err and "403" in err
    assert "rider" not in err and "example.com" not in err


def test_resend_requests_carry_a_user_agent(monkeypatch):
    import send_gravel_weekly as sg

    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout):
        seen.update(request.header_items())
        return Response()

    monkeypatch.setattr(sg.urllib.request, "urlopen", fake_urlopen)
    sg._req("https://api.resend.com/broadcasts")
    assert seen.get("User-agent", "").startswith("gravelgod-weekly/")
