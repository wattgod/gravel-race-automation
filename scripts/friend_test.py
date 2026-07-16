#!/usr/bin/env python3
"""
The Friend Test — an LLM-judge quality gate for email-sequence voice.

The deterministic sibling of `wordpress/slop_rules.py` catches banned *phrases*.
This catches something a phrase-list can't: whether an email reads as a text
*from a specific friend*, not *from a company*. It runs three detectors:

    1. TOOL          (tone)     "If a friend texted me this, would I think
                                 they were a tool?"  -> cringe / neediness /
                                 try-hard / hype / being more excited than
                                 the reader.
    2. BODY-SNATCHER (voice)    "Would I think someone stole my friend's phone
                                 and wrote this?"  -> generic / AI-slop /
                                 could-be-any-brand / voice drift off Matti.
    3. FAMILIARITY   (premise)  "Would a friend actually SEND this — now, to
                                 ME?"  -> a scheduled/blasted marketing
                                 artifact no human would ever text. This one
                                 can veto an email out of existence.

All three must pass. Detector 3 is a *product* gate, not just copy-editing:
if you can't say why this is hitting their phone TODAY in a way a friend
would, it shouldn't send.

Calibrated on:
  - docs/bonk-bros-voice-patterns.md   (the "friend, not bullshitting" ref;
                                        distilled from real Bonk Bros episodes)
  - docs/email-voice-model.md          (Matti / Roadie Labs voice fingerprint)

GG pilot. Clone to road_*/xc once proven.

Usage:
    python3 scripts/friend_test.py                      # all GG emails (codex engine)
    python3 scripts/friend_test.py --sequence welcome   # one sequence
    python3 scripts/friend_test.py --dry-run            # list emails, no LLM calls
    python3 scripts/friend_test.py --brand roadielabs   # road sequences
    python3 scripts/friend_test.py --engine anthropic   # use ANTHROPIC_API_KEY instead

Backend: --engine codex (default) uses the locally-authenticated Codex CLI, no
key plumbing. --engine anthropic uses the anthropic SDK + ANTHROPIC_API_KEY,
matching scripts/adversarial_review.py (for cron/CI where the key is present).
Writes docs/friend-test-findings.md (+ .json). Review-only: ships nothing.
"""

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEQ_DIR = REPO / "mission_control" / "sequences"
TMPL_DIR = REPO / "mission_control" / "templates" / "emails" / "sequences"
DOCS = REPO / "docs"

# Two backends. anthropic = repo convention (needs ANTHROPIC_API_KEY, e.g. cron);
# codex = uses the locally-authenticated Codex CLI, no key plumbing required.
DEFAULT_MODEL = {"anthropic": "claude-sonnet-5", "codex": "gpt-5.6-sol"}

# ── Voice reference bundle ────────────────────────────────────────────────
# The judge is only as good as its fingerprint of "friend, not bullshitting."
# Prefer the distilled Bonk Bros patterns doc; fall back to an embedded gist
# so the gate still runs before that doc exists.

FALLBACK_BONK = """\
BONK BROS REFERENCE (condensed fallback — see docs/bonk-bros-voice-patterns.md
for the transcript-grounded version). Why friends-not-bullshitting reads as
BOTH trustworthy and entertaining:
- They concede they're wrong, admit they bonked / got dropped / don't know.
  Conceding IS the credibility.
- They call out hype, overrated races, and mid product to each other's faces.
- The roasting goes SIDEWAYS (host-to-host), never down at the listener; you're
  a fly on the wall enjoying it.
- Nobody performs authority or fakes enthusiasm; they're entertained by each
  other (self-amused), not managing your impression of them.
- Register: short, spoken, profanity as seasoning on opinions never on facts,
  running bits and callbacks, real reason to be talking right now.
They would NEVER: sell earnestly, PR-speak, punch down at the audience, fake
excitement, or send a "Day 5 of 7" anything.
"""


def load_reference(include_voice_model: bool = True) -> str:
    bonk = DOCS / "bonk-bros-voice-patterns.md"
    voice = DOCS / "email-voice-model.md"
    spec = DOCS / "specs" / "friend-first-sequences.md"
    parts = []
    parts.append(bonk.read_text() if bonk.exists() else FALLBACK_BONK)
    if include_voice_model and voice.exists():
        parts.append("MATTI / ROADIE LABS VOICE MODEL:\n" + voice.read_text())
    if not include_voice_model and spec.exists():
        # judging NEW friend-first copy: the spec governs, old voice model excluded
        parts.append("GOVERNING SPEC (device dispositions + constitution):\n" + spec.read_text())
    return "\n\n".join(parts)


# ── Email discovery ───────────────────────────────────────────────────────
# AST-based: walks each sequence file for dicts carrying an "emails" list and
# reads the sibling "brand" key (absent = gravelgod). Handles mixed-brand files
# (race_countdown.py) and subjects containing merge braces like {race_name},
# which the previous regex silently dropped (6 emails missed — sol review).


def _const(node):
    return node.value if isinstance(node, ast.Constant) else None


def _email_from_dict(node):
    d = {}
    for k, v in zip(node.keys, node.values):
        key = _const(k)
        if key in ("template", "subject", "delay_days", "delay_hours"):
            val = _const(v)
            if val is not None:
                d[key] = val
    return d if ("template" in d and "subject" in d) else None


def parse_sequences(seq_file: Path):
    """Yield (brand, email_dict) for every unique email in every sequence dict.

    Real shape: SEQUENCE = {..., "brand"?: str, "variants": {"A": {"steps":
    [...] | _STEPS_NAME}, ...}} where _STEPS may be a module-level list.
    Zero-weight legacy variants reuse the same steps — dedupe by
    (template, subject, delay)."""
    tree = ast.parse(seq_file.read_text())
    env = {}  # module-level name -> List node
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, (ast.List, ast.Tuple))):
            env[node.targets[0].id] = node.value

    def steps_elts(node):
        if isinstance(node, ast.Name):
            node = env.get(node.id)
        if isinstance(node, (ast.List, ast.Tuple)):
            return node.elts
        return []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = [_const(k) for k in node.keys]
        if "variants" not in keys:
            continue
        brand = "gravelgod"
        if "brand" in keys:
            b = _const(node.values[keys.index("brand")])
            if b:
                brand = b
        variants = node.values[keys.index("variants")]
        if not isinstance(variants, ast.Dict):
            continue
        seen = set()
        for vnode in variants.values:
            if not isinstance(vnode, ast.Dict):
                continue
            vkeys = [_const(k) for k in vnode.keys]
            if "steps" not in vkeys:
                continue
            for el in steps_elts(vnode.values[vkeys.index("steps")]):
                if isinstance(el, ast.Dict):
                    email = _email_from_dict(el)
                    if email:
                        key = (email["template"], email["subject"],
                               email.get("delay_days"))
                        if key not in seen:
                            seen.add(key)
                            yield brand, email


def branch_for(seq: str) -> bool:
    """True → render the race-supplied branch. Only sequences whose enrollment
    guarantees a race name (countdown, quiz/race-specific) see it."""
    return ("countdown" in seq) or ("race_specific" in seq) or ("quiz" in seq)


def discover(brand: str, only_sequence: str | None):
    """Yield (sequence_name, email_dict) for the requested brand, by brand KEY
    (not filename)."""
    for f in sorted(SEQ_DIR.glob("*.py")):
        if f.name.startswith("__"):
            continue
        seq_name = f.stem
        if only_sequence and only_sequence not in seq_name:
            continue
        for email_brand, email in parse_sequences(f):
            if email_brand == brand:
                yield seq_name, email


# ── Template -> readable text ─────────────────────────────────────────────

class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.buf = []

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "head"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("style", "script", "head") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.buf.append(data.strip())


def _resolve_mustache(text: str, present: bool) -> str:
    """Render ONE conditional branch, the way a real subscriber sees it — not
    both concatenated. {{#var}}..{{/var}} shows when the field is present;
    {{^var}}..{{/var}} shows when it's absent."""
    pos = re.compile(r"\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}", re.S)
    inv = re.compile(r"\{\{\^(\w+)\}\}(.*?)\{\{/\1\}\}", re.S)
    if present:
        text = pos.sub(lambda m: m.group(2), text)   # keep present branch
        text = inv.sub("", text)                       # drop absent branch
    else:
        text = pos.sub("", text)                       # drop present branch
        text = inv.sub(lambda m: m.group(2), text)    # keep absent branch
    return text


RACE_PLACEHOLDER = {"gravelgod": "Unbound", "roadielabs": "the Maratona", "xcskilabs": "the Birkie"}


def template_text(template: str, branch_present: bool = False,
                  race_placeholder: str = "Unbound") -> str | None:
    """Extract the reader-visible text of an email. Defaults to the anonymous
    (no race supplied) branch — most welcome-track subscribers never give a
    race. Pass branch_present=True for quiz/countdown sequences that guarantee
    race_name."""
    path = TMPL_DIR / f"{template}.html"
    if not path.exists():
        return None
    p = _Text()
    p.feed(path.read_text())
    text = " ".join(p.buf)
    text = _resolve_mustache(text, branch_present)
    text = (text.replace("{first_name}", "Alex")
                .replace("{race_name}", race_placeholder)
                .replace("{weeks_out}", "8"))
    text = re.sub(r"\{[^}]+\}", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ── The judge ─────────────────────────────────────────────────────────────

SYSTEM = """\
You are the Friend Test — a brutally honest voice critic for a cycling brand's
marketing emails. The brand (Gravel God Cycling / Roadie Labs) earns trust by
publishing harsh, honest race scores. Its emails must read as a text from a
specific friend who doesn't bullshit you — NOT as marketing. Your north star
for "friend, not bullshitting" is the Bonk Bros reference below.

You run THREE independent detectors on each email. Judge hard; a real friend
sets a high bar. Grade each detector: "pass", "warn", or "fail".

1. TOOL (tone). If a good friend texted you this, would you think they were a
   tool? FAIL on: hype, fake enthusiasm, being more excited about the reader
   than the reader is about you, exclamation-point energy, try-hard,
   salesiness, groveling for the open/click.

2. BODY_SNATCHER (voice/identity). Would you think someone stole your friend's
   phone and wrote this? FAIL when it's generic, AI-slop, or could have come
   from ANY brand's marketing department — i.e. it doesn't sound like the
   specific person in the voice model. A line can be non-cringe and still FAIL
   here by being faceless.

3. FAMILIARITY (premise). Would a friend actually SEND this — now, to this one
   person? FAIL on messages whose only reason to exist is a calendar slot,
   a broadcast blast, or a revenue target: "Day 5 of...", "just checking in!",
   "did you see my last email?", header-banner/three-CTA marketing furniture.
   A welcome reply passes (you just reached out). An unsubscribe link passes
   (it's a door, not a message). If you can't name a friend-plausible reason
   this hits their phone TODAY, it FAILS.

Return ONLY a JSON object, no prose, in exactly this shape:
{
  "friend_score": <int 1-5, would-a-friend-send-this gut check, 5 = totally>,
  "tool":          {"verdict": "pass|warn|fail", "worst_line": "<verbatim or ''>", "why": "<=20 words"},
  "body_snatcher": {"verdict": "pass|warn|fail", "worst_line": "<verbatim or ''>", "why": "<=20 words"},
  "familiarity":   {"verdict": "pass|warn|fail", "worst_line": "<verbatim or ''>", "why": "<=20 words"},
  "one_fix": "<the single highest-leverage rewrite, or '' if clean>"
}
"""

USER_TMPL = """\
=== VOICE REFERENCE ===
{reference}

=== EMAIL UNDER TEST ===
Sequence: {seq}   |   Sends: day {day} after enrollment
SUBJECT: {subject}
BODY:
{body}

Run the three detectors. JSON only.
"""


def _last_json(text: str):
    """Return the last TOP-LEVEL {...} object matching our schema. Scans only
    depth-0 objects (so nested detector objects aren't mistaken for the whole
    verdict) and, since codex may echo the answer twice, returns the last
    schema-matching one."""
    candidates = []
    i, n = 0, len(text)
    while i < n:
        if text[i] == "{":
            depth = 0
            for j in range(i, n):
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            candidates.append(json.loads(text[i : j + 1]))
                        except json.JSONDecodeError:
                            pass
                        i = j  # jump past this whole top-level object
                        break
        i += 1
    schema = [c for c in candidates if isinstance(c, dict) and ("friend_score" in c or "tool" in c)]
    if schema:
        return schema[-1]
    return candidates[-1] if candidates else None


def _build_user(reference, seq, email, body):
    return USER_TMPL.format(
        reference=reference[:14000],
        seq=seq,
        day=email.get("delay_days", "?"),
        subject=(email["subject"].replace("{race_name}", "Unbound")
                 .replace("{weeks_out}", "8").replace("{first_name}", "Alex")),
        body=body[:9000],
    )


def judge_anthropic(client, model, user):
    resp = client.messages.create(
        model=model, max_tokens=1024, system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text.strip()


def judge_codex(model, user):
    prompt = SYSTEM + "\n\n" + user
    proc = subprocess.run(
        ["codex", "exec", "-m", model, "-s", "read-only", "-C", str(REPO)],
        input=prompt, capture_output=True, text=True, timeout=300,
    )
    if proc.returncode != 0:
        return '{"error": "codex exit %d: %s"}' % (proc.returncode,
                                                    proc.stderr[-200:].replace('"', "'"))
    return proc.stdout


def judge(engine, client, model, reference, seq, email, body):
    user = _build_user(reference, seq, email, body)
    raw = judge_anthropic(client, model, user) if engine == "anthropic" else judge_codex(model, user)
    parsed = _last_json(raw)
    if parsed is None:
        return {"error": "no JSON parsed", "raw": raw[-300:]}
    return parsed


# ── Report ────────────────────────────────────────────────────────────────

SEV = {"fail": 2, "warn": 1, "pass": 0}


def severity(v):
    if "error" in v:
        return 99
    dets = [v.get(k, {}).get("verdict", "pass") for k in ("tool", "body_snatcher", "familiarity")]
    return sum(SEV.get(d, 0) for d in dets) * 10 + (5 - v.get("friend_score", 5))


def emoji(verdict):
    return {"pass": "✅", "warn": "⚠️", "fail": "❌"}.get(verdict, "❓")


def render(results) -> str:
    results = sorted(results, key=lambda r: -severity(r["verdict"]))
    lines = ["# Friend Test — findings", ""]
    fails = sum(
        1 for r in results
        if any(r["verdict"].get(k, {}).get("verdict") == "fail"
               for k in ("tool", "body_snatcher", "familiarity"))
    )
    lines.append(f"**{len(results)} emails judged · {fails} with at least one FAIL.** "
                 "Sorted worst-first. Nothing here is shipped or changed — review only.\n")
    for r in results:
        v = r["verdict"]
        if "error" in v:
            lines.append(f"### ⚠️ `{r['seq']}` — {r['subject']}\n_judge error: {v['error']}_\n")
            continue
        head = f"### {r['seq']} · day {r['day']} — “{r['subject']}”  (friend {v.get('friend_score','?')}/5)"
        lines.append(head)
        for k, label in (("tool", "Tool"), ("body_snatcher", "Body-Snatcher"), ("familiarity", "Familiarity")):
            d = v.get(k, {})
            lines.append(f"- {emoji(d.get('verdict'))} **{label}** — {d.get('why','')}"
                         + (f"  \n  ↳ _“{d['worst_line']}”_" if d.get("worst_line") else ""))
        if v.get("one_fix"):
            lines.append(f"- 🔧 **Fix:** {v['one_fix']}")
        lines.append("")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Friend Test voice gate for email sequences.")
    ap.add_argument("--brand", default="gravelgod", choices=["gravelgod", "roadielabs", "xcskilabs"])
    ap.add_argument("--sequence", help="substring filter, e.g. 'welcome'")
    ap.add_argument("--engine", default="codex", choices=["anthropic", "codex"],
                    help="codex = local Codex CLI (no key); anthropic = ANTHROPIC_API_KEY")
    ap.add_argument("--model", default=None, help="override; else per-engine default")
    ap.add_argument("--limit", type=int, help="cap number of emails judged")
    ap.add_argument("--dry-run", action="store_true", help="list emails, no LLM calls")
    ap.add_argument("--draft-file", help="judge a draft markdown file (### seq · day N · template / "
                    "SUBJECT: / BODY: format) instead of live templates; excludes the old "
                    "voice-model doc from the judge reference per spec §7")
    ap.add_argument("--gate", action="store_true",
                    help="exit 1 if any email has a detector FAIL or friend_score < 4; "
                         "exit 2 on judge errors. Ship-process gate, not per-commit CI.")
    ap.add_argument("--out", default=str(REPO / "docs" / "friend-test-findings.md"))
    args = ap.parse_args()

    if args.draft_file:
        raw = Path(args.draft_file).read_text()
        emails = []
        for chunk in re.split(r"^### ", raw, flags=re.M)[1:]:
            lines = chunk.splitlines()
            head = lines[0].strip().replace("`", "")
            m = re.match(r"([\w_]+) · day (\d+) · ([\w_]+)", head)
            if not m:
                continue
            seq, day, tmpl = m.group(1), int(m.group(2)), m.group(3)
            body_txt = chunk[chunk.find("BODY:") + 5:].strip() if "BODY:" in chunk else ""
            subj_m = re.search(r"^SUBJECT:\s*(.+)$", chunk, re.M)
            emails.append((seq, {"delay_days": day, "template": tmpl,
                                 "subject": subj_m.group(1).strip() if subj_m else "?",
                                 "_body": body_txt}))
    else:
        emails = list(discover(args.brand, args.sequence))
    if args.limit:
        emails = emails[: args.limit]
    if not emails:
        print("No emails matched.", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        for seq, e in emails:
            body = template_text(e["template"], branch_for(seq), RACE_PLACEHOLDER[args.brand])
            flag = "" if body else "  [!! template missing]"
            print(f"  {seq:16} day {e.get('delay_days','?'):>2}  {e['template']:24} {e['subject']}{flag}")
        print(f"\n{len(emails)} emails. (dry run — no judging)")
        return

    model = args.model or DEFAULT_MODEL[args.engine]
    client = None
    if args.engine == "anthropic":
        try:
            import anthropic
        except ImportError:
            sys.exit("pip install anthropic")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit("Set ANTHROPIC_API_KEY, or use --engine codex.")
        client = anthropic.Anthropic()

    reference = load_reference(include_voice_model=not args.draft_file)
    if not (DOCS / "bonk-bros-voice-patterns.md").exists():
        print("note: docs/bonk-bros-voice-patterns.md missing — using condensed fallback ref.",
              file=sys.stderr)

    results = []
    for i, (seq, e) in enumerate(emails, 1):
        if "_body" in e:
            body = _resolve_mustache(e["_body"], branch_for(seq))
            body = (body.replace("{first_name}", "Alex")
                        .replace("{race_name}", RACE_PLACEHOLDER[args.brand])
                        .replace("{weeks_out}", "8"))
            body = re.sub(r"\{[^}]+\}", "", body)
            body = re.sub(r"[ \t]+", " ", body).strip()
        else:
            body = template_text(e["template"], branch_for(seq), RACE_PLACEHOLDER[args.brand])
        if not body:
            print(f"  [{i}/{len(emails)}] SKIP {seq}/{e['template']} (no template)", file=sys.stderr)
            continue
        print(f"  [{i}/{len(emails)}] judging {seq} · {e['subject'][:45]}", file=sys.stderr)
        verdict = judge(args.engine, client, model, reference, seq, e, body)
        results.append({"seq": seq, "day": e.get("delay_days", "?"),
                        "subject": e["subject"], "verdict": verdict})

    report = render(results)
    Path(args.out).write_text(report)
    Path(args.out).with_suffix(".json").write_text(json.dumps(results, indent=2))
    print(f"\nWrote {args.out}")
    print(report)

    if args.gate:
        errors = [r for r in results if "error" in r["verdict"]]
        failing = [r for r in results if "error" not in r["verdict"] and (
            any(r["verdict"].get(k, {}).get("verdict") == "fail"
                for k in ("tool", "body_snatcher", "familiarity"))
            or r["verdict"].get("friend_score", 0) < 4)]
        if errors:
            print(f"GATE: {len(errors)} judge errors — inconclusive", file=sys.stderr)
            sys.exit(2)
        if failing:
            print(f"GATE: FAIL — {len(failing)}/{len(results)} emails below bar",
                  file=sys.stderr)
            sys.exit(1)
        print(f"GATE: PASS — all {len(results)} emails at bar", file=sys.stderr)


if __name__ == "__main__":
    main()
