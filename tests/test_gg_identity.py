"""Organization markup and security.txt (sweep ALL-09, ALL-10, Gravel God side)."""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wordpress"))

import generate_homepage as gh  # noqa: E402

SECURITY = ROOT / "web" / ".well-known" / "security.txt"


def _org():
    html = gh.build_jsonld({"dimensions": 14})
    blocks = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html)]
    return [b for b in blocks if b["@type"] == "Organization"][0]


def test_organization_has_identity_fields():
    org = _org()
    assert org["logo"] == "https://gravelgodcycling.com/icon-512.png"
    assert org["legalName"] == "Gravel God Cycling LLC"
    assert org["contactPoint"]["email"] == "gravelgodcoaching@gmail.com"
    assert org["sameAs"] == ["https://gravelgodcycling.substack.com"]


def test_security_txt_is_valid_and_current():
    text = SECURITY.read_text()
    fields = dict(line.split(": ", 1) for line in text.strip().splitlines())
    assert fields["Contact"] == "mailto:gravelgodcoaching@gmail.com"
    assert fields["Canonical"] == "https://gravelgodcycling.com/.well-known/security.txt"
    expires = datetime.fromisoformat(fields["Expires"].replace("Z", "+00:00"))
    days = (expires - datetime.now(timezone.utc)).days
    # RFC 9116: no more than a year out. Renew before it lapses.
    assert 30 < days <= 366, f"security.txt Expires is {days} days away; renew it"


def test_security_txt_ships_with_llms_sync():
    src = (ROOT / "scripts" / "push_wordpress.py").read_text()
    assert '(".well-known/security.txt", ".well-known/security.txt")' in src
    assert "mkdir -p {remote_base}/.well-known" in src
