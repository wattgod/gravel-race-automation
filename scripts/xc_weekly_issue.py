#!/usr/bin/env python3
"""XC Ski Labs Weekly issue: assemble, validate, hash and render.

An issue is built from the model's selections plus the collected evidence.
URLs, outlet names and languages always come from the evidence, never from
model text. validate_issue() is the publication gate the staging and send
workflows both run; it refuses anything that could put an invented link,
a reprinted passage, an AI mention or third-person coach wording in front of
a subscriber.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mission_control.config import BRAND_FOOTER_NAMES, SENDER_POSTAL_ADDRESS  # noqa: E402

BRAND = "xcskilabs"
SITE_URL = "https://xcskilabs.com"
SIGNUP_URL = f"{SITE_URL}/weekly/"
TITLE = "XC Ski Labs Weekly"

# Sledge Stores (xc-ski-labs docs/brand/sledge-stores/tokens.json, Wool theme).
# Email clients cannot read CSS variables, so the hex values live here.
COLORS = {
    "wool": "#f1e9dc",
    "oat": "#ddd0bc",
    "navy": "#1e2b3c",
    "graphite": "#4a5566",
    "salmon": "#e3876d",
}

LANG_NAMES = {"no": "Norwegian", "sv": "Swedish", "de": "German", "fi": "Finnish", "fr": "French", "en": None}

# Dark-mode surfaces (prefers-color-scheme: dark). Inline styles keep the light
# palette for clients that ignore the media query.
DARK = {
    "page": "#141c27",
    "card": "#1e2b3c",
    "text": "#f1e9dc",
    "muted": "#c9bfae",
    "take": "#3a2a26",
}

MIN_STORIES, MAX_STORIES = 4, 10
MAX_PODCASTS = 5
MAX_HEADLINE_CHARS = 90
MAX_BLURB_WORDS = 60
MAX_TAKE_WORDS = 220
MIN_TAKE_WORDS = 40
MAX_SUBJECT_CHARS = 60      # prompts/xc-weekly-voice.md rule 10
MAX_PREHEADER_CHARS = 110
SHARED_RUN_WORDS = 8

# Customer copy never brings up AI or the machinery, and never talks about
# Matti in the third person (global rules, 2026-11-15).
FORBIDDEN_PATTERNS = [
    (re.compile(r"\bA\.?I\.?\b"), "mentions AI"),
    (re.compile(r"artificial intelligence|\bchatbot|\bChatGPT\b|\bGPT\b|\bClaude\b|\bCodex\b|\bLLM", re.I), "mentions AI tooling"),
    (re.compile(r"\balgorithm|\bautomat(ed|ion|ically)\b|\bgenerated\b|\bgenerator\b", re.I), "mentions automation"),
    (re.compile(r"\bMatt\b|\bMatti\b", re.I), "names Matti in the third person"),
    (re.compile(r"\b(your|the) coach\b|\bcoach matti\b", re.I), "third-person coach wording"),
    (re.compile(r"sources say|according to (our|my) research|our research", re.I), "research-process wording"),
    (re.compile(r"https?://|www\.", re.I), "writes a URL into copy"),
    (re.compile(r"[\"“”„«»]"), "uses quotation marks (paraphrase and link instead)"),
    (re.compile(r"\b(delve|testament|game[- ]chang\w*|elevate|unlock|supercharge|tapestry|realm|"
                r"paradigm|leverage|robust|cutting-edge|transformative|pivotal|you won'?t believe|"
                r"here'?s the thing|let'?s dive)\b", re.I), "slop wording"),
]
MARKER_RE = re.compile(r"\[(\d+)\]")
WORD_RE = re.compile(r"[\w'’-]+", re.UNICODE)


class IssueError(ValueError):
    """The issue fails the publication gate."""


def _words(text: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(text)]


def shared_run(copy: str, source: str, length: int = SHARED_RUN_WORDS) -> str | None:
    """Return the first run of `length` words copy shares with source, if any."""
    src = _words(source)
    grams = {tuple(src[i:i + length]) for i in range(len(src) - length + 1)}
    words = _words(copy)
    for i in range(len(words) - length + 1):
        gram = tuple(words[i:i + length])
        if gram in grams:
            return " ".join(gram)
    return None


def _join_items(selection: dict, evidence: dict) -> tuple[list[dict], list[dict]]:
    """Join picked stories and podcasts to the evidence. Unknown ids are refused."""
    by_id = {item["id"]: item for item in evidence["items"]}
    stories = []
    for pick in selection["stories"]:
        item = by_id.get(pick["itemId"])
        if item is None or item["kind"] != "news":
            raise IssueError(f"story itemId {pick['itemId']!r} is not a collected news item")
        also = []
        for other_id in pick.get("alsoItemIds", []):
            other = by_id.get(other_id)
            if other is None or other["kind"] != "news" or other_id == item["id"]:
                raise IssueError(f"alsoItemId {other_id!r} is not another collected news item")
            also.append({"itemId": other["id"], "sourceName": other["sourceName"],
                         "url": other["url"], "lang": other["lang"]})
        stories.append({
            "itemId": item["id"],
            "headline": pick["headline"].strip(),
            "blurb": pick["blurb"].strip(),
            "url": item["url"],
            "sourceName": item["sourceName"],
            "lang": item["lang"],
            "published": item["published"],
            "also": also,
        })
    podcasts = []
    for pick in selection.get("podcasts", []):
        item = by_id.get(pick["itemId"])
        if item is None or item["kind"] != "podcast":
            raise IssueError(f"podcast itemId {pick['itemId']!r} is not a collected episode")
        podcasts.append({
            "itemId": item["id"],
            "show": item["sourceName"],
            "episodeTitle": item["title"],
            "blurb": pick["blurb"].strip(),
            "url": item["url"],
            "lang": item["lang"],
            "published": item["published"],
        })
    return stories, podcasts


def assemble_brief(selection: dict, evidence: dict) -> dict:
    """The Sunday shortlist Matti reads and reacts to. It has no take yet."""
    stories, podcasts = _join_items(selection, evidence)
    return {
        "brand": BRAND,
        "window": {"since": evidence["since"], "until": evidence["collectedAt"]},
        "stories": stories,
        "podcasts": podcasts,
    }


def assemble_issue(selection: dict, evidence: dict, issue_number: int, issue_date: str) -> dict:
    """Join the model's selection to the evidence. Unknown ids are refused."""
    stories, podcasts = _join_items(selection, evidence)
    issue = {
        "brand": BRAND,
        "issueNumber": issue_number,
        "issueDate": issue_date,
        "window": {"since": evidence["since"], "until": evidence["collectedAt"]},
        "subject": selection["subject"].strip(),
        "preheader": selection["preheader"].strip(),
        "take": [p.strip() for p in selection["take"] if p.strip()],
        "stories": stories,
        "podcasts": podcasts,
        "status": "draft",
    }
    issue["contentHash"] = content_hash(issue)
    return issue


def content_hash(issue: dict) -> str:
    body = {k: v for k, v in issue.items() if k not in ("status", "contentHash")}
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _check_copy(label: str, text: str, problems: list[str], *, allow_em_dash: int = 0) -> None:
    for pattern, reason in FORBIDDEN_PATTERNS:
        if pattern.search(text):
            problems.append(f"{label}: {reason}")
    if text.count("—") > allow_em_dash:
        problems.append(f"{label}: too many em dashes")


def _check_items(issue: dict, evidence: dict | None, problems: list[str]) -> None:
    """Story and podcast checks shared by the brief and the issue gate."""
    stories = issue.get("stories", [])
    if not MIN_STORIES <= len(stories) <= MAX_STORIES:
        problems.append(f"needs {MIN_STORIES}-{MAX_STORIES} stories, has {len(stories)}")
    podcasts = issue.get("podcasts", [])
    if len(podcasts) > MAX_PODCASTS:
        problems.append(f"at most {MAX_PODCASTS} podcasts")
    ids = ([s["itemId"] for s in stories] + [a["itemId"] for s in stories for a in s.get("also", [])]
           + [p["itemId"] for p in podcasts])
    if len(ids) != len(set(ids)):
        problems.append("an item is used twice")

    evidence_by_id = {i["id"]: i for i in (evidence or {}).get("items", [])}
    for n, story in enumerate(stories, 1):
        label = f"story {n}"
        if not story.get("url", "").startswith("https://"):
            problems.append(f"{label}: link must be https")
        headline, blurb = story.get("headline", ""), story.get("blurb", "")
        if not headline or len(headline) > MAX_HEADLINE_CHARS:
            problems.append(f"{label}: headline must be 1-{MAX_HEADLINE_CHARS} characters")
        if not blurb or len(_words(blurb)) > MAX_BLURB_WORDS:
            problems.append(f"{label}: blurb must be 1-{MAX_BLURB_WORDS} words")
        _check_copy(f"{label} headline", headline, problems)
        _check_copy(f"{label} blurb", blurb, problems)
        if evidence is not None:
            item = evidence_by_id.get(story.get("itemId"))
            if item is None:
                problems.append(f"{label}: not in the collected evidence")
            else:
                if item["url"] != story.get("url"):
                    problems.append(f"{label}: link differs from the evidence")
                for other in story.get("also", []):
                    known = evidence_by_id.get(other["itemId"])
                    if known is None or known["url"] != other["url"]:
                        problems.append(f"{label}: an also-at link is not in the evidence")
                # Every collected text about the event, drafting detail included.
                related = [item] + [evidence_by_id[a["itemId"]] for a in story.get("also", [])
                                    if a["itemId"] in evidence_by_id]
                source_text = " ".join(f"{i['title']} {i['excerpt']} {i.get('detail', '')}" for i in related)
                for part in (headline, blurb):
                    run = shared_run(part, source_text)
                    if run:
                        problems.append(f"{label}: reprints the source ({run!r})")

    for n, pod in enumerate(podcasts, 1):
        label = f"podcast {n}"
        if not pod.get("url", "").startswith("https://"):
            problems.append(f"{label}: link must be https")
        blurb = pod.get("blurb", "")
        if not blurb or len(_words(blurb)) > MAX_BLURB_WORDS:
            problems.append(f"{label}: blurb must be 1-{MAX_BLURB_WORDS} words")
        _check_copy(f"{label} blurb", blurb, problems)
        if evidence is not None:
            item = evidence_by_id.get(pod.get("itemId"))
            if item is None:
                problems.append(f"{label}: not in the collected evidence")
            else:
                if item["url"] != pod.get("url"):
                    problems.append(f"{label}: link differs from the evidence")
                run = shared_run(blurb, f"{item['title']} {item['excerpt']} {item.get('detail', '')}")
                if run:
                    problems.append(f"{label}: reprints the source ({run!r})")


def validate_brief(brief: dict, evidence: dict) -> dict:
    """Raise IssueError listing every problem in the shortlist; return it when clean."""
    problems: list[str] = []
    if brief.get("brand") != BRAND:
        problems.append("brand must be xcskilabs")
    _check_items(brief, evidence, problems)
    if problems:
        raise IssueError("; ".join(problems))
    return brief


def validate_issue(issue: dict, evidence: dict | None = None) -> dict:
    """Raise IssueError listing every problem; return the issue when clean."""
    problems: list[str] = []
    if issue.get("brand") != BRAND:
        problems.append("brand must be xcskilabs")
    if issue.get("contentHash") != content_hash(issue):
        problems.append("contentHash does not match the issue body")
    subject = issue.get("subject", "")
    if not subject or len(subject) > MAX_SUBJECT_CHARS:
        problems.append(f"subject must be 1-{MAX_SUBJECT_CHARS} characters")
    _check_copy("subject", subject, problems)
    preheader = issue.get("preheader", "")
    if not preheader or len(preheader) > MAX_PREHEADER_CHARS:
        problems.append(f"preheader must be 1-{MAX_PREHEADER_CHARS} characters")
    _check_copy("preheader", preheader, problems)

    _check_items(issue, evidence, problems)
    stories = issue.get("stories", [])
    evidence_by_id = {i["id"]: i for i in (evidence or {}).get("items", [])}

    take = issue.get("take", [])
    if not 1 <= len(take) <= 2:
        problems.append("take must be one or two paragraphs")
    take_text = " ".join(take)
    words = len(_words(MARKER_RE.sub("", take_text)))
    if not MIN_TAKE_WORDS <= words <= MAX_TAKE_WORDS:
        problems.append(f"take must be {MIN_TAKE_WORDS}-{MAX_TAKE_WORDS} words, has {words}")
    _check_copy("take", take_text, problems, allow_em_dash=1)
    markers = [int(m) for m in MARKER_RE.findall(take_text)]
    if not markers:
        problems.append("take must cite at least one story with a [n] marker")
    for marker in markers:
        if not 1 <= marker <= len(stories):
            problems.append(f"take marker [{marker}] has no story")

    if evidence is not None:
        # The take, subject and preheader may not reprint any story's sources either.
        story_ids = {s["itemId"] for s in stories} | {a["itemId"] for s in stories for a in s.get("also", [])}
        all_text = " ".join(f"{i['title']} {i['excerpt']} {i.get('detail', '')}"
                            for i in evidence_by_id.values() if i["id"] in story_ids)
        for label, text in (("take", MARKER_RE.sub("", take_text)), ("subject", subject),
                            ("preheader", preheader)):
            run = shared_run(text, all_text)
            if run:
                problems.append(f"{label}: reprints a source ({run!r})")

    if problems:
        raise IssueError("; ".join(problems))
    return issue


# ── Rendering ──────────────────────────────────────────────────

def _lang_note(lang: str) -> str:
    name = LANG_NAMES.get(lang)
    return f" (in {name})" if name else ""


def _take_html(paragraph: str, stories: list[dict]) -> str:
    """Markers become short outlet-name links, e.g. (TV 2), not bare footnotes."""
    out, last = [], 0
    for match in MARKER_RE.finditer(paragraph):
        out.append(html.escape(paragraph[last:match.start()].rstrip()))
        story = stories[int(match.group(1)) - 1]
        out.append(f' (<a class="xl" href="{html.escape(story["url"])}" style="color:{COLORS["navy"]};">'
                   f'{html.escape(story["sourceName"])}</a>)')
        last = match.end()
    out.append(html.escape(paragraph[last:]))
    return "".join(out)


def _take_text(paragraph: str, stories: list[dict]) -> str:
    return MARKER_RE.sub(lambda m: f"({stories[int(m.group(1)) - 1]['sourceName']})", paragraph)


def _date_label(issue_date: str) -> str:
    from datetime import date
    d = date.fromisoformat(issue_date)
    return f"{d.day} {d.strftime('%B %Y')}"


def footer_line() -> str:
    return f"{BRAND_FOOTER_NAMES[BRAND]} · {SENDER_POSTAL_ADDRESS}"


def _attribution_html(story: dict) -> str:
    """Outlet and language, then any other outlets that covered the same event."""
    c = COLORS
    line = f"{html.escape(story['sourceName'])}{html.escape(_lang_note(story['lang']))}"
    also = story.get("also", [])
    if also:
        links = ", ".join(
            f'<a class="xm" href="{html.escape(a["url"])}" style="color:{c["graphite"]};">'
            f'{html.escape(a["sourceName"])}</a>' for a in also)
        line += f" · also at {links}"
    return (f'<div class="xm" style="font:13px/1.5 Arial,sans-serif;color:{c["graphite"]};'
            f'margin-top:6px;">{line}</div>')


_DARK_CSS = """
:root{{color-scheme:light dark;supported-color-schemes:light dark;}}
@media (prefers-color-scheme: dark){{
  body,.xp{{background:{page}!important;}}
  .xc{{background:{card}!important;}}
  .xt{{background:{take}!important;}}
  .xh,.xh a,.xb,.xl{{color:{text}!important;}}
  .xm,.xm a{{color:{muted}!important;}}
}}
[data-ogsc] .xh,[data-ogsc] .xh a,[data-ogsc] .xb,[data-ogsc] .xl{{color:{text}!important;}}
[data-ogsc] .xm,[data-ogsc] .xm a{{color:{muted}!important;}}
"""

_HEADING = ('<tr><td style="padding:{pad};"><h2 class="xh" style="margin:0;font:700 12px Arial,sans-serif;'
            'letter-spacing:3px;color:{navy};">{text}</h2></td></tr>')

_LEAD = """<tr><td style="padding:0 0 16px;">
  <div class="xc" style="background:{oat};border-left:4px solid {navy};padding:16px 18px;">
    <h3 class="xh" style="margin:0 0 8px;font:700 22px/1.25 Georgia,serif;color:{navy};"><a href="{url}" style="color:{navy};text-decoration:none;">{headline}</a></h3>
    <p class="xb" style="margin:0;font:17px/1.5 Georgia,serif;color:{navy};">{blurb}</p>
    {attribution}
  </div>
</td></tr>"""

_ROW = """<tr><td style="padding:0 0 14px;border-bottom:1px solid {oat};">
  <h3 class="xh" style="margin:0 0 4px;font:700 18px/1.3 Georgia,serif;color:{navy};"><a href="{url}" style="color:{navy};text-decoration:none;display:inline-block;padding:2px 0;">{headline}</a></h3>
  <p class="xb" style="margin:0;font:16px/1.5 Georgia,serif;color:{navy};">{blurb}</p>
  {attribution}
</td></tr>
<tr><td style="height:12px;line-height:12px;font-size:0;">&nbsp;</td></tr>"""

_PODCAST = ('<p class="xb" style="margin:0 0 14px;font:16px/1.5 Georgia,serif;color:{navy};">'
            '<a class="xl" href="{url}" style="color:{navy};font-weight:700;display:inline-block;padding:2px 0;">{show}</a> '
            '{blurb}<br><span class="xm" style="font:13px/1.5 Arial,sans-serif;color:{graphite};">'
            'Episode: {title}{lang}</span></p>')

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">
<title>{subject}</title><style>{css}</style></head>
<body style="margin:0;padding:0;background:{wool};">
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{preheader}</div>
{banner}
<table class="xp" role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{wool};"><tr><td align="center" style="padding:0 16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:620px;">
<tr><td style="background:{navy};padding:18px 20px;">
  <h1 style="margin:0;font:800 26px Arial,sans-serif;letter-spacing:3px;color:{wool};">XC SKI LABS WEEKLY</h1>
  <div style="font:700 12px Arial,sans-serif;letter-spacing:2px;color:{wool};margin-top:6px;">{label}</div>
</td></tr>
{week_heading}
{stories}
<tr><td style="padding:8px 0 16px;">
  <div class="xt" style="background:{salmon};padding:16px 18px;">
    <h2 class="xh" style="margin:0 0 8px;font:700 12px Arial,sans-serif;letter-spacing:3px;color:{navy};">MY TAKE</h2>
    {take}
  </div>
</td></tr>
{podcasts}
<tr><td style="padding:12px 0 28px;border-top:2px solid {navy};">
  <p class="xb" style="margin:12px 0 8px;font:15px/1.5 Georgia,serif;color:{navy};">Reply to this email and it comes straight to me.</p>
  <p class="xm" style="margin:0 0 8px;font:14px/1.5 Arial,sans-serif;color:{graphite};">Forwarded this? <a class="xm" href="{signup}" style="color:{graphite};">Get it every week at xcskilabs.com/weekly</a>.</p>
  <p class="xm" style="margin:0 0 8px;font:14px/1.5 Arial,sans-serif;color:{graphite};">You signed up for the XC Ski Labs Weekly at xcskilabs.com.</p>
  <p style="margin:0 0 12px;font:14px/1.5 Arial,sans-serif;"><a class="xm" href="{{{{{{RESEND_UNSUBSCRIBE_URL}}}}}}" style="color:{graphite};display:inline-block;padding:6px 0;">Unsubscribe</a></p>
  <p class="xm" style="margin:0;font:13px/1.5 Arial,sans-serif;color:{graphite};">{footer}</p>
</td></tr>
</table></td></tr></table>
</body></html>"""


def render_email_html(issue: dict, *, preview_banner: str | None = None) -> str:
    """The broadcast body. {{{RESEND_UNSUBSCRIBE_URL}}} is filled by Resend.

    Order: masthead, the week (one lead story, then compact rows), my take,
    podcasts, footer. Each story has one link (its headline) plus an
    attribution line naming every outlet that covered it.
    """
    c = COLORS
    esc = html.escape
    banner = ""
    if preview_banner:
        banner = (f'<div style="background:{c["navy"]};color:{c["wool"]};padding:10px 16px;'
                  f'font:700 13px Arial,sans-serif;letter-spacing:1px;">{esc(preview_banner)}</div>')

    def story_html(template: str, s: dict) -> str:
        return template.format(oat=c["oat"], navy=c["navy"], url=esc(s["url"]), headline=esc(s["headline"]),
                               blurb=esc(s["blurb"]), attribution=_attribution_html(s))

    stories = story_html(_LEAD, issue["stories"][0]) + "".join(story_html(_ROW, s) for s in issue["stories"][1:])
    take = "".join(
        f'<p class="xb" style="margin:0 0 12px;font:17px/1.55 Georgia,serif;color:{c["navy"]};">'
        f'{_take_html(p, issue["stories"])}</p>' for p in issue["take"])
    podcasts = ""
    if issue["podcasts"]:
        rows = "".join(_PODCAST.format(navy=c["navy"], graphite=c["graphite"], url=esc(p["url"]),
                                       show=esc(p["show"]), blurb=esc(p["blurb"]), title=esc(p["episodeTitle"]),
                                       lang=esc(_lang_note(p["lang"]))) for p in issue["podcasts"])
        podcasts = (_HEADING.format(pad="8px 0 8px", navy=c["navy"], text="IN YOUR EARS")
                    + f'\n<tr><td style="padding:4px 0;">{rows}</td></tr>')
    # Pad the hidden preheader so the inbox snippet stops after it.
    preheader = esc(issue["preheader"]) + "&#847;&zwnj;&nbsp;" * 60
    return _PAGE.format(
        subject=esc(issue["subject"]), css=_DARK_CSS.format(**DARK), preheader=preheader, banner=banner,
        label=esc(f"No. {issue['issueNumber']:03d} · {_date_label(issue['issueDate'])}"),
        week_heading=_HEADING.format(pad="20px 0 10px", navy=c["navy"], text="THE WEEK"),
        stories=stories, take=take, podcasts=podcasts, signup=SIGNUP_URL, footer=esc(footer_line()),
        **c)


def render_email_text(issue: dict) -> str:
    """The plain-text edition sent alongside the HTML: same order, numbered links."""
    links: list[str] = []

    def ref(url: str) -> str:
        links.append(url)
        return f"[{len(links)}]"

    lines = [f"XC SKI LABS WEEKLY · No. {issue['issueNumber']:03d} · {_date_label(issue['issueDate'])}", "",
             "THE WEEK", ""]
    for s in issue["stories"]:
        lines += [f"{s['headline']} {ref(s['url'])}", s["blurb"]]
        attribution = f"{s['sourceName']}{_lang_note(s['lang'])}"
        if s.get("also"):
            attribution += " · also at " + ", ".join(f"{a['sourceName']} {ref(a['url'])}" for a in s["also"])
        lines += [attribution, ""]
    lines += ["MY TAKE", ""]
    for paragraph in issue["take"]:
        lines += [_take_text(paragraph, issue["stories"]), ""]
    if issue["podcasts"]:
        lines += ["IN YOUR EARS", ""]
        for p in issue["podcasts"]:
            lines += [f"{p['show']} {ref(p['url'])}: {p['blurb']}",
                      f"Episode: {p['episodeTitle']}{_lang_note(p['lang'])}", ""]
    lines += ["Links:"] + [f"[{n}] {url}" for n, url in enumerate(links, 1)]
    lines += ["", "Reply to this email and it comes straight to me.",
              f"Forwarded this? Get it every week at {SIGNUP_URL}",
              "You signed up for the XC Ski Labs Weekly at xcskilabs.com.",
              "Unsubscribe: {{{RESEND_UNSUBSCRIBE_URL}}}",
              footer_line()]
    return "\n".join(lines) + "\n"


def render_review_markdown(issue: dict, coverage: list[dict] | None = None) -> str:
    """The staged review Matti reads in the GitHub issue."""
    lines = _partial_week_lines(coverage) + [
        f"**Subject:** {issue['subject']}  ",
        f"**Preheader:** {issue['preheader']}  ",
        f"**Issue:** No. {issue['issueNumber']:03d} · {issue['issueDate']} · hash `{issue['contentHash']}`",
        "",
        "### My take",
        "",
    ]
    for paragraph in issue["take"]:
        lines += [MARKER_RE.sub(lambda m: f"[[{m.group(1)}]]({issue['stories'][int(m.group(1)) - 1]['url']})", paragraph), ""]
    lines += ["### The week", ""]
    for n, s in enumerate(issue["stories"], 1):
        lines.append(f"{n}. **[{s['headline']}]({s['url']})** · {s['sourceName']}{_lang_note(s['lang'])}{_also_md(s)}  ")
        lines.append(f"   {s['blurb']}")
    if issue["podcasts"]:
        lines += ["", "### In your ears", ""]
        for p in issue["podcasts"]:
            lines.append(f"- **[{p['show']}: {p['episodeTitle']}]({p['url']})**{_lang_note(p['lang'])}: {p['blurb']}")
    lines += _coverage_lines(coverage)
    return "\n".join(lines) + "\n"


def render_brief_markdown(brief: dict, coverage: list[dict] | None = None) -> str:
    """The Sunday headline brief Matti reads before reacting."""
    lines = _partial_week_lines(coverage) + ["### The week's headlines", ""]
    for n, s in enumerate(brief["stories"], 1):
        lines.append(f"{n}. **[{s['headline']}]({s['url']})** · {s['sourceName']}{_lang_note(s['lang'])}{_also_md(s)}  ")
        lines.append(f"   {s['blurb']}")
    if brief["podcasts"]:
        lines += ["", "### Podcasts", ""]
        for p in brief["podcasts"]:
            lines.append(f"- **[{p['show']}: {p['episodeTitle']}]({p['url']})**{_lang_note(p['lang'])}: {p['blurb']}")
    lines += _coverage_lines(coverage)
    return "\n".join(lines) + "\n"


def _also_md(story: dict) -> str:
    also = story.get("also", [])
    if not also:
        return ""
    return " · also at " + ", ".join(f"[{a['sourceName']}]({a['url']})" for a in also)


def _partial_week_lines(coverage: list[dict] | None) -> list[str]:
    """Failed fetches go above everything else, never only in the collapsed table."""
    failed = [c for c in (coverage or []) if c.get("failedRuns") or c.get("errors")]
    if not failed:
        return []
    lines = ["> [!WARNING]", "> **Partial week.** These sources failed at least once, so stories may be missing:"]
    for cov in failed:
        runs = cov.get("failedRuns") or [{"at": "latest run", "errors": cov.get("errors", [])}]
        total = cov.get("runs", len(runs))
        when = ", ".join(r["at"][:10] for r in runs)
        lines.append(f"> - {cov['name']}{' (core)' if cov.get('core') else ''}: failed {when}; "
                     f"{total - len(runs)} of {total} runs fetched")
    return lines + [""]


def _coverage_lines(coverage: list[dict] | None) -> list[str]:
    if coverage is None:
        return []
    lines = ["", "<details><summary>Source coverage this week</summary>", "",
             "| Source | Kind | In window | Error |", "|---|---|---|---|"]
    for cov in coverage:
        error = ("; ".join(e for r in cov.get("failedRuns", []) for e in r["errors"])
                 or "; ".join(cov["errors"]))
        lines.append(f"| {cov['name']} | {cov['kind']} | {cov['kept']} | {error} |")
    return lines + ["", "</details>"]
