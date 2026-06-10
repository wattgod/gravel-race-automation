#!/usr/bin/env python3
"""
Questionnaire parity check — repo file vs live Elementor page.

The /questionnaire/ page is an Elementor HTML widget (page 5017, widget
3f59420). It does NOT deploy from the repo: editing post_content does
nothing, and tar+ssh/SCP deploys never touch it. In June 2026 the page
silently missed two shipped commits (trust strip, WCAG teal) because
nothing compared the repo file against the live page.

This check fetches the live page and verifies that every form field
name/id and a set of content markers from the repo file are present.
Run standalone or via preflight_quality.

Exit codes: 0 = parity, 1 = drift detected, 2 = fetch/parse error.
"""

import re
import sys
import urllib.request
from pathlib import Path

REPO_FILE = Path(__file__).parent.parent / 'web' / 'training-plans-questionnaire.html'
LIVE_URL = 'https://gravelgodcycling.com/questionnaire/'
USER_AGENT = 'Mozilla/5.0 (parity-check; gravel-god-automation)'

# Content markers that must exist on the live page whenever they exist in
# the repo file. Cheap canaries for whole feature blocks.
CONTENT_MARKERS = [
    'gg-trust-strip',        # conversion trust strip (commit 6939db7c)
    'travelDatesGroup',      # travel-dates field (commit 72c6a741)
    '#178079',               # WCAG AA teal (color audit sprint)
]


def extract_fields(html: str) -> set:
    """All name= and id= attribute values in form elements."""
    fields = set(re.findall(r'<(?:input|select|textarea)[^>]*\bname="([^"]+)"', html))
    fields |= set(re.findall(r'<(?:div|input|select|textarea)[^>]*\bid="([^"]+)"', html))
    return fields


def fetch_live() -> str:
    req = urllib.request.Request(LIVE_URL, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode('utf-8', errors='replace')


def check_parity(live_html: str = None, repo_html: str = None) -> list:
    """Return a list of drift findings (empty = parity)."""
    if repo_html is None:
        repo_html = REPO_FILE.read_text()
    if live_html is None:
        live_html = fetch_live()

    findings = []

    repo_fields = extract_fields(repo_html)
    for field in sorted(repo_fields):
        if field not in live_html:
            findings.append(f"form field '{field}' in repo but missing live")

    for marker in CONTENT_MARKERS:
        if marker in repo_html and marker not in live_html:
            findings.append(f"content marker '{marker}' in repo but missing live")

    return findings


def main():
    try:
        findings = check_parity()
    except Exception as e:
        print(f"✗ Questionnaire parity check failed to run: {e}")
        return 2

    if findings:
        print(f"✗ Questionnaire DRIFT detected ({len(findings)} findings):")
        for f in findings:
            print(f"  - {f}")
        print("\n  The live page is an Elementor widget (page 5017, widget "
              "3f59420).\n  Fix via the Elementor editor or its JS API — see "
              "CLAUDE.md 'Deploy'.")
        return 1

    print("✓ Questionnaire parity: repo file and live page agree")
    return 0


if __name__ == '__main__':
    sys.exit(main())
