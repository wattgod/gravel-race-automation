"""Redirects for retired races: every old URL of a race that left race-data/.

tar+ssh deploys only add files, so a retired race keeps its page, its .md
mirror, its sub-pages (prep kit, training plan, tires) and its head-to-head
pages on the server, serving stale content, until an .htaccess rule catches
each URL. In Nov 2026 eight races deleted in August (#63) were still live for
exactly that reason: their tombstones named a redirect nobody wrote as a rule.

So retiring a race is one step: add it to config/tombstones.json with a
redirect. This module turns that into rules, and fills the gaps the
hand-written rules leave:

- a page rule for every tombstone that has no hand-written one;
- for every retired slug (tombstones plus every slug whose page a rule in the
  block already retires, which covers the road migration and renames), its
  .md mirror, sub-pages and head-to-head pages go to its page URL, which the
  page rule then sends on.

push_wordpress.py splices the section into REDIRECT_BLOCK after the
hand-written rules, so those still win where they say something more specific
(merges keep sub-paths with $1). tests/test_retired_race_redirects.py checks
every retired URL redirects and no live page is caught;
`push_wordpress.py --check-retired-races` checks the server.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOMBSTONES_PATH = PROJECT_ROOT / "config" / "tombstones.json"
RACE_DATA_DIR = PROJECT_ROOT / "race-data"

SECTION_BEGIN = "# BEGIN GENERATED RETIRED RACE REDIRECTS"
SECTION_END = "# END GENERATED RETIRED RACE REDIRECTS"

# Sub-pages a race profile ships under /race/{slug}/.
SUB_PAGES = ("prep-kit", "training-plan", "tires")

# Apache config lines have a length ceiling; keep each alternation well under it.
MAX_ALTERNATION_CHARS = 1500

_SLUG = r"[a-z0-9][a-z0-9-]*"
_PAGE_RULE = re.compile(
    rf"^RewriteRule \^race/({_SLUG})/\?\$ (\S+) \[R=301,L\]$")


@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern
    target: str
    flags: str

    @property
    def permanent(self) -> bool:
        return "R=301" in self.flags


def load_tombstones(path: Path = TOMBSTONES_PATH) -> dict[str, str]:
    """slug -> redirect target, from config/tombstones.json."""
    entries = json.loads(Path(path).read_text())["tombstones"]
    return {t["slug"]: t["redirect"] for t in entries}


def live_race_slugs(race_data_dir: Path = RACE_DATA_DIR) -> set[str]:
    return {p.stem for p in Path(race_data_dir).glob("*.json")
            if p.stem != "_schema"}


def unconditional_rules(block: str) -> list[Rule]:
    """RewriteRules in order, skipping any guarded by a RewriteCond (those
    depend on the server's files, which a static read can't see)."""
    rules, guarded = [], False
    for line in block.splitlines():
        line = line.strip()
        if line.startswith("RewriteCond"):
            guarded = True
        elif line.startswith("RewriteRule"):
            parts = line.split()
            if not guarded and len(parts) >= 4:
                rules.append(Rule(re.compile(parts[1]), parts[2], parts[3]))
            guarded = False
    return rules


def first_match(rules: list[Rule], path: str) -> Rule | None:
    """The rule Apache applies to `path` (no leading slash, as .htaccess sees it)."""
    for rule in rules:
        if rule.pattern.search(path):
            return rule
    return None


def page_rules(block: str) -> dict[str, str]:
    """slug -> target for every literal 301 page rule `^race/{slug}/?$`."""
    out = {}
    for line in block.splitlines():
        m = _PAGE_RULE.match(line.strip())
        if m and "-vs-" not in m[1]:
            out.setdefault(m[1], m[2])
    return out


def retired_slugs(block: str, tombstones: dict[str, str],
                  live: set[str]) -> list[str]:
    """Tombstones plus every slug whose page the block retires, never a live race."""
    return sorted((set(tombstones) | set(page_rules(block))) - live)


def retired_paths(slug: str) -> list[str]:
    """Every URL shape a retired race left on the server (no leading slash)."""
    return ([f"race/{slug}/", f"race/{slug}.md"]
            + [f"race/{slug}/{sub}/" for sub in SUB_PAGES]
            + [f"race/{slug}-vs-unbound-200/", f"race/unbound-200-vs-{slug}/"])


def _alternations(slugs: list[str]) -> list[str]:
    groups, current = [], []
    for slug in slugs:
        if current and len("|".join(current + [slug])) > MAX_ALTERNATION_CHARS:
            groups.append("|".join(current))
            current = []
        current.append(slug)
    if current:
        groups.append("|".join(current))
    return groups


def generate_section(block: str, tombstones: dict[str, str] | None = None,
                     live: set[str] | None = None) -> str:
    """The generated section for the hand-written `block` it will sit in."""
    tombstones = load_tombstones() if tombstones is None else tombstones
    live = live_race_slugs() if live is None else live
    written = page_rules(block)
    lines = [
        SECTION_BEGIN,
        "# Generated by scripts/retired_races.py from config/tombstones.json and",
        "# the page rules above; do not hand-edit. Retire a race with a tombstone.",
    ]
    for slug in sorted(set(tombstones) - set(written) - live):
        lines.append(f"RewriteRule ^race/{slug}/?$ {tombstones[slug]} [R=301,L]")
    lines.append("# Everything under a retired race page goes where the page goes.")
    for group in _alternations(retired_slugs(block, tombstones, live)):
        lines += [
            f"RewriteRule ^race/({group})(?:\\.md|/.+|-vs-[a-z0-9-]+/?)$ /race/$1/ [R=301,L]",
            f"RewriteRule ^race/[a-z0-9-]+-vs-({group})/?$ /race/$1/ [R=301,L]",
        ]
    lines.append(SECTION_END)
    return "\n".join(lines) + "\n"


_LISTING_ENTRY = re.compile(
    rf"({_SLUG})(\.md|/(?:{'|'.join(SUB_PAGES)}))/?")


def server_orphans(listing: str, live: set[str], rules: list[Rule]) -> list[str]:
    """Race files on the server that belong to no live race and no rule
    redirects. `listing` is `ls -1d *.md */prep-kit ...` run inside /race/."""
    orphans = set()
    for entry in listing.split():
        m = _LISTING_ENTRY.fullmatch(entry)
        if not m or m[1] in live:
            continue
        path = f"race/{m[1]}.md" if m[2] == ".md" else f"race/{m[1]}{m[2]}/"
        rule = first_match(rules, path)
        if rule is None or not rule.permanent:
            orphans.add("/" + path)
    return sorted(orphans)
