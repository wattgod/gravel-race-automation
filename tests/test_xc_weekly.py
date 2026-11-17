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
    entry = {"title": title, "description": "", "categories": categories, "link": "https://a.example/x"}
    assert collect.keep_entry(entry, source) is kept


SVT = {"keep_url_paths": ["/sport/langdskidor/"], "include_keywords": ["vasalopp"]}


@pytest.mark.parametrize("link,title,kept", [
    ("https://www.svt.se/sport/langdskidor/poromaa", "Poromaa om skadan", True),  # section, no keyword
    ("https://www.svt.se/nyheter/lokalt/dalarna/x", "Vasaloppet förlänger reptiderna", True),  # keyword
    ("https://www.svt.se/sport/parasport/arsjo", "Årsjö nominerad på Idrottsgalan", False),
])
def test_section_path_keeps_items_without_keywords(link, title, kept):
    entry = {"title": title, "description": "", "categories": [], "link": link}
    assert collect.keep_entry(entry, SVT) is kept


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


def brief_selection():
    sel = selection()
    return {"stories": sel["stories"], "podcasts": sel["podcasts"]}


def test_shortlist_has_no_take_and_passes_the_item_gate(tmp_path):
    client = FakeClient([brief_selection()])
    brief = draft.shortlist(evidence(), client=client)
    assert "take" not in brief and len(brief["stories"]) == 5
    assert client.requests[0]["output_config"]["format"]["schema"] is draft.BRIEF_SCHEMA
    assert "shortlist step" in client.requests[0]["messages"][0]["content"]
    draft.stage_brief(brief, evidence(), tmp_path)
    md = (tmp_path / "brief.md").read_text()
    assert "1. **[Story 1 in plain words](https://www.langrenn.com/1)**" in md
    assert (tmp_path / "evidence.json").exists() and (tmp_path / "brief.json").exists()


def test_shortlist_gate_refuses_banned_copy():
    bad = brief_selection()
    bad["stories"][0]["blurb"] = "An AI summary of the race."
    with pytest.raises(xi.IssueError):
        draft.shortlist(evidence(), client=FakeClient([bad, bad]))


def make_brief():
    return xi.validate_brief(xi.assemble_brief(brief_selection(), evidence()), evidence())


def test_draft_uses_opus_with_schema_and_repairs_once():
    bad = selection(take=["Matti thinks the opener mattered [1], and the rest of the week was quiet "
                          "enough that I spent it waxing."])
    client = FakeClient([bad, selection()])
    issue = draft.draft(evidence(), make_brief(), "1: lead with this. I think FIS is stalling.",
                        3, "2026-11-16", client=client)
    assert issue["issueNumber"] == 3
    first = client.requests[0]
    assert first["model"] == "claude-opus-5-5"
    assert first["output_config"]["format"]["schema"] is draft.SELECTION_SCHEMA
    assert first["fallbacks"] == "default"
    assert "third person" in client.requests[1]["messages"][-1]["content"]


def test_draft_carries_the_shortlist_and_reactions():
    client = FakeClient([selection()])
    draft.draft(evidence(), make_brief(), "2: drop it. I think FIS is stalling.", 1, "2026-11-16",
                client=client)
    prompt = client.requests[0]["messages"][0]["content"]
    assert "<reactions>\n2: drop it. I think FIS is stalling.\n</reactions>" in prompt
    assert '"n": 1' in prompt and "Add no opinion he did not give" in prompt


def test_draft_refuses_without_reactions():
    client = FakeClient([selection()])
    with pytest.raises(xi.IssueError, match="no reactions"):
        draft.draft(evidence(), make_brief(), "  ", 1, "2026-11-16", client=client)
    assert client.requests == []


def test_draft_gives_up_after_one_repair():
    bad = selection(subject="An AI round-up")
    with pytest.raises(xi.IssueError):
        draft.draft(evidence(), make_brief(), "I think it was a good week.", 1, "2026-11-16",
                    client=FakeClient([bad, bad]))


@pytest.mark.parametrize("bodies, expected", [
    ([], None),
    (["   "], None),
    (["Lead with 3."], "Lead with 3."),
    (["Lead with 3.", "Go!"], None),
    (["Lead with 3.", "looks good", "Drop 5, it's sponsor fluff."],
     "Lead with 3.\n\n---\n\nDrop 5, it's sponsor fluff."),
])
def test_reactions_from_comments(bodies, expected):
    assert draft.reactions_from_comments(bodies) == expected


def test_main_without_a_new_reaction_stages_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    draft.stage_brief(make_brief(), evidence(), tmp_path / "brief")
    (tmp_path / "r.json").write_text(json.dumps(["Lead with 1.", "send it"]))
    rc = draft.main(["--from-brief", str(tmp_path / "brief"), "--reactions", str(tmp_path / "r.json"),
                     "--issue-number", "2", "--output-dir", str(tmp_path / "stage")])
    assert rc == 3 and not (tmp_path / "stage").exists()


def test_workflows_wait_for_matti():
    wf = ROOT / ".github" / "workflows"
    staging = (wf / "xc-weekly-draft-staging.yml").read_text()
    assert "schedule:" not in staging and "issue_comment:" in staging
    assert "github.event.comment.user.login == 'wattgod'" in staging
    assert 'select(.user.login == "wattgod")' in staging
    assert "contains(github.event.issue.labels.*.name, 'xc-weekly-brief')" in staging
    assert "--broadcast" not in staging
    # Devin review on #642: the run id must be usable in the same step, and a
    # skipped job (someone else's comment) must not cancel Matti's draft.
    assert 'BRIEF_RUN="$(python3' in staging and "GITHUB_ENV" not in staging
    assert staging.index("concurrency:") > staging.index("  stage:")
    send = (wf / "xc-weekly-send.yml").read_text()
    assert "any(.comments[]; .body | contains(env.HASH))" in send
    brief = (wf / "xc-weekly-brief.yml").read_text()
    assert "--assignee wattgod" in brief and "xc-weekly-brief-run: $GITHUB_RUN_ID" in brief
    assert "send_xc_weekly" not in brief


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


# ── Top fixes from the Fable and Astra reviews (#644) ─────────────

class FlakySession:
    """Serves a block page first, then the real feed, from the same URL."""

    def __init__(self, bodies):
        self.bodies, self.calls = list(bodies), []

    def get(self, url, timeout, headers):
        self.calls.append(url)
        body = self.bodies.pop(0)
        return SimpleNamespace(raise_for_status=lambda: None, content=body)


def test_feed_parse_failure_is_retried_on_the_same_url():
    feed = rss([("Ny", "https://www.langrenn.com/ny", NOW - timedelta(hours=3), [])])
    session = FlakySession([b"<html><body>blocked</p></body></html>", feed])
    waits = []
    source = {"id": "langrenn", "name": "Langrenn.com", "lang": "no", "feed": "https://www.langrenn.com/feed"}
    items, coverage = collect.collect_source(source, "news", NOW - timedelta(days=7), session, waits.append)
    assert [i["title"] for i in items] == ["Ny"] and coverage["errors"] == []
    assert session.calls == ["https://www.langrenn.com/feed"] * 2 and waits == [5]


def test_feed_that_never_parses_records_what_came_back():
    session = FlakySession([b"<html>blocked</p></html>"] * 3)
    source = {"id": "langd", "name": "Längd.se", "lang": "sv", "feed": "https://www.langd.se/feed", "core": False}
    items, coverage = collect.collect_source(source, "news", NOW - timedelta(days=7), session, lambda s: None)
    assert items == [] and len(session.calls) == 3
    assert "ParseError" in coverage["errors"][0] and "starting '<html>blocked" in coverage["errors"][0]


def test_client_errors_are_not_retried():
    session = FakeSession({})
    source = {"id": "nrk", "name": "NRK Sport", "lang": "no", "feed": "https://www.nrk.no/x.rss"}
    collect.collect_source(source, "news", NOW - timedelta(days=7), session, lambda s: pytest.fail("no retry"))
    assert len(session.calls) == 1


def test_item_ids_follow_the_normalized_url_and_wp_tails_are_stripped():
    feed = (b'<?xml version="1.0"?><rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">'
            b"<channel><link>https://x.no/</link>"
            b"<item><title>Edited headline</title><link>https://x.no/a?utm_source=rss#top</link>"
            b"<pubDate>Sun, 15 Nov 2026 10:00:00 +0000</pubDate>"
            b"<description>Short. The post Edited headline appeared first on Langrenn.com.</description>"
            b"<content:encoded>&lt;p&gt;Full paragraph about the race.&lt;/p&gt;</content:encoded></item>"
            b"</channel></rss>")
    source = {"id": "x", "name": "X", "lang": "no", "feed": "https://x.no/feed"}
    items, _ = collect.collect_source(source, "news", NOW - timedelta(days=7), FakeSession({"https://x.no/feed": feed}))
    assert items[0]["url"] == "https://x.no/a"
    assert items[0]["id"] == collect.item_id("https://x.no/a")
    assert items[0]["excerpt"] == "Short."
    assert items[0]["detail"] == "Full paragraph about the race."
    shows = {"id": "s", "name": "S", "lang": "sv", "feed": "https://pod.example/feed",
             "show_url": "https://pod.example/show"}
    session = FakeSession({"https://pod.example/feed": rss([("Ep 1", "", NOW - timedelta(days=1), []),
                                                             ("Ep 2", "", NOW - timedelta(days=2), [])])})
    eps, _ = collect.collect_source(shows, "podcast", NOW - timedelta(days=7), session)
    assert len({e["id"] for e in eps}) == 2  # shared show URL, distinct episodes


def test_core_sources_are_flagged_in_config():
    core = {s["id"] for s in collect.load_sources()["news"] if s.get("core")}
    assert core == {"langrenn", "fasterskier", "nrk"}


def snapshot(at, errors_by_source):
    return {"collectedAt": at.isoformat(), "items": evidence()["items"],
            "coverage": [{"id": sid, "name": sid.title(), "kind": "news", "core": sid == "langrenn",
                          "kept": 1, "errors": errs} for sid, errs in errors_by_source.items()]}


def test_load_evidence_keeps_every_runs_errors(tmp_path):
    (tmp_path / "wed.json").write_text(json.dumps(snapshot(NOW - timedelta(days=4), {"langrenn": ["ParseError"]})))
    (tmp_path / "mon.json").write_text(json.dumps(snapshot(NOW, {"langrenn": []})))
    merged = draft.load_evidence([tmp_path / "mon.json", tmp_path / "wed.json"], NOW)
    row = merged["coverage"][0]
    assert row["runs"] == 2 and row["errors"] == []
    assert row["failedRuns"] == [{"at": (NOW - timedelta(days=4)).isoformat(), "errors": ["ParseError"]}]
    assert draft.missing_core_sources(merged, {"langrenn"}) == []
    assert draft.missing_core_sources(merged, {"langrenn", "nrk"}) == ["nrk"]  # absent counts as missing
    md = xi.render_brief_markdown(xi.validate_brief(xi.assemble_brief(brief_selection(), evidence()), evidence()),
                                  merged["coverage"])
    assert md.startswith("> [!WARNING]") and "Langrenn (core): failed 2026-11-12; 1 of 2 runs fetched" in md


def test_brief_refuses_a_week_without_a_core_source(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    (tmp_path / "a.json").write_text(json.dumps(snapshot(NOW, {"langrenn": ["ParseError"]})))
    monkeypatch.setattr(draft, "shortlist", lambda ev: pytest.fail("must refuse before drafting"))
    rc = draft.main(["--brief", str(tmp_path / "a.json"), "--output-dir", str(tmp_path / "out")])
    assert rc == 1 and not (tmp_path / "out").exists()


def also_selection():
    sel = selection()
    sel["stories"][0]["alsoItemIds"] = ["n6"]
    return sel


def test_also_at_links_come_from_the_evidence_and_render():
    issue = xi.validate_issue(xi.assemble_issue(also_selection(), evidence(), 1, "2026-11-16"), evidence())
    assert issue["stories"][0]["also"] == [{"itemId": "n6", "sourceName": "Langrenn.com",
                                            "url": "https://www.langrenn.com/6", "lang": "no"}]
    assert 'also at <a class="xm" href="https://www.langrenn.com/6"' in xi.render_email_html(issue)
    assert "also at [Langrenn.com](https://www.langrenn.com/6)" in xi.render_review_markdown(issue)


def test_also_items_cannot_be_unknown_or_reused():
    bad = selection()
    bad["stories"][0]["alsoItemIds"] = ["nope"]
    with pytest.raises(xi.IssueError, match="alsoItemId"):
        xi.assemble_issue(bad, evidence(), 1, "2026-11-16")
    reused = selection()
    reused["stories"][0]["alsoItemIds"] = ["n2"]  # n2 is already story 2
    with pytest.raises(xi.IssueError, match="used twice"):
        xi.validate_issue(xi.assemble_issue(reused, evidence(), 1, "2026-11-16"), evidence())


def test_take_may_not_reprint_a_source():
    sel = selection(take=["I think Klæbo vant sprinten i Ruka foran hele det norske laget [1], and the "
                          "rest of the week was quiet enough that I spent most of it waxing skis for spring."])
    with pytest.raises(xi.IssueError, match="take: reprints a source"):
        xi.validate_issue(xi.assemble_issue(sel, evidence(), 1, "2026-11-16"), evidence())


def test_new_drafts_follow_the_brief_limits_but_staged_issues_still_send():
    assert (xi.DRAFT_SUBJECT_CHARS, xi.DRAFT_PREHEADER_CHARS) == (60, 110)
    long = xi.assemble_issue(selection(subject="Sixty-five characters of subject line for an older staged issue"),
                             evidence(), 1, "2026-11-16")
    assert 60 < len(long["subject"]) <= xi.MAX_SUBJECT_CHARS
    xi.validate_issue(long, evidence())  # already-staged issues keep their publication contract
    with pytest.raises(xi.IssueError, match="at most 60"):
        xi.check_draft_limits(long)
    client = FakeClient([selection(subject=long["subject"]), selection()])
    issue = draft.draft(evidence(), make_brief(), "I think it was a good week.", 1, "2026-11-16", client=client)
    assert len(issue["subject"]) <= 60 and "at most 60" in client.requests[1]["messages"][-1]["content"]


def test_html_block_page_is_a_failed_fetch_not_an_empty_feed():
    session = FlakySession([b"<html><body>Access denied</body></html>"] * 3)
    source = {"id": "langrenn", "name": "Langrenn.com", "lang": "no", "feed": "https://www.langrenn.com/feed"}
    items, coverage = collect.collect_source(source, "news", NOW - timedelta(days=7), session, lambda s: None)
    assert items == [] and len(session.calls) == 3
    assert "not an RSS or Atom feed" in coverage["errors"][0]


def test_merge_keeps_one_item_per_article_across_id_schemes():
    old = {**evidence()["items"][0], "id": "legacyhash", "url": "https://www.langrenn.com/1?utm_source=rss"}
    merged = collect.merge_items(evidence()["items"], [old])
    assert sum(1 for i in merged if "langrenn.com/1" in i["url"]) == 1


def test_runs_before_the_window_do_not_vouch_for_the_week(tmp_path):
    (tmp_path / "old.json").write_text(json.dumps(snapshot(NOW - timedelta(days=7, hours=12), {"langrenn": []})))
    (tmp_path / "now.json").write_text(json.dumps(snapshot(NOW, {"langrenn": ["ParseError"]})))
    merged = draft.load_evidence([tmp_path / "old.json", tmp_path / "now.json"], NOW)
    assert draft.missing_core_sources(merged, {"langrenn"}) == ["Langrenn"]


def test_reader_copy_is_checked_against_all_evidence_and_attribution():
    ev = evidence()
    ev["items"].append({**ev["items"][0], "id": "x9", "url": "https://www.langrenn.com/x9",
                        "excerpt": "", "detail": "Johaug sier at sesongen blir den siste hun går på ski"})
    sel = selection(take=["I think Johaug sier at sesongen blir den siste hun går på ski [1], which is a "
                          "bigger deal than the opener and worth a long spring of reading."])
    with pytest.raises(xi.IssueError, match="take: reprints a source"):
        xi.validate_issue(xi.assemble_issue(sel, ev, 1, "2026-11-16"), ev)
    issue = xi.assemble_issue(also_selection(), evidence(), 1, "2026-11-16")
    issue["stories"][0]["also"][0]["sourceName"] = "Matti uses AI to write this"
    issue["contentHash"] = xi.content_hash(issue)
    with pytest.raises(xi.IssueError, match="also-at link is not in the evidence"):
        xi.validate_issue(issue, evidence())


def test_email_puts_the_week_first_with_one_link_per_story_and_dark_mode():
    issue = xi.assemble_issue(selection(), evidence(), 1, "2026-11-16")
    body = xi.render_email_html(issue)
    assert body.index("THE WEEK") < body.index("MY TAKE") < body.index("IN YOUR EARS")
    assert "Read it at" not in body
    assert body.count('href="https://www.langrenn.com/3"') == 1  # uncited story: headline only
    assert '(<a class="xl" href="https://www.langrenn.com/1"' in body and "[1]" not in body
    assert '<meta name="color-scheme" content="light dark">' in body and "prefers-color-scheme: dark" in body
    assert "font:700 22px" in body  # the lead story is bigger than the rest
    assert body.index("The Devon Kershaw Show</a>") < body.index("Episode: Season opener")
    assert 'href="https://xcskilabs.com/weekly/"' in body  # forwarded copies can sign up
    assert body.count("&zwnj;") >= 30  # preheader padding


def test_plain_text_edition_matches_and_is_sent(monkeypatch):
    import send_xc_weekly as send
    issue = xi.assemble_issue(also_selection(), evidence(), 1, "2026-11-16")
    text = xi.render_email_text(issue)
    assert text.index("THE WEEK") < text.index("MY TAKE")
    assert "also at Langrenn.com [2]" in text and "[2] https://www.langrenn.com/6" in text
    assert "(Langrenn.com)" in text and "[1]" in text.split("MY TAKE")[0]
    assert "Unsubscribe: {{{RESEND_UNSUBSCRIBE_URL}}}" in text and "2183 Lombardy St" in text
    assert "<" not in text
    sent = []
    monkeypatch.setattr(send, "resend", lambda path, method="GET", body=None: sent.append(body) or {"id": "e1"})
    send.send_preview(issue)
    assert sent[0]["text"] == text
