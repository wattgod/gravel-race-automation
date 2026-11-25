"""Validate staged outputs before publishing to the public monitoring branch."""
import json
import re
import subprocess
import sys
from pathlib import Path

DAILY = re.compile(
    r"(?:data/gsc-snapshots/\d{4}-\d{2}-\d{2}\.json"
    r"|data/cwv-snapshots/\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.json"
    r"|reports/\d{4}-\d{2}-\d{2}\.md)"
)
AEO = re.compile(r"data/aeo/aeo-weekly-\d{4}-\d{2}-\d{2}\.json")
INTEL = re.compile(r"data/intel-snapshots/\d{4}-\d{2}-\d{2}\.(?:json|md)")
EMAIL = re.compile(rb"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

profile = sys.argv[1] if len(sys.argv) > 1 else "daily"
allowed = {"daily": DAILY, "aeo": AEO, "intel": INTEL}[profile]
if profile == "aeo":
    from aeo_weekly import validate_artifact

for path in subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"]).split(b"\0"):
    if not path:
        continue
    relative = path.decode("utf-8", errors="replace")
    if not allowed.fullmatch(relative):
        raise SystemExit("Monitoring staging contains an unexpected path.")
    mode = subprocess.check_output(["git", "ls-files", "-s", "-z", "--", path]).partition(b" ")[0]
    if mode != b"100644":
        raise SystemExit("Daily monitoring staging contains a deleted or nonregular file.")
    content = subprocess.check_output(["git", "show", b":" + path])
    if EMAIL.search(content):
        raise SystemExit("Monitoring publication contains an email address.")
    if profile == "aeo":
        try:
            artifact = json.loads(content)
        except ValueError:
            raise SystemExit("AEO publication contains invalid JSON.") from None
        if validate_artifact(artifact, path=Path(relative)):
            raise SystemExit("AEO publication failed artifact validation.")
