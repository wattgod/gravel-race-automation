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
SEO = re.compile(r"data/seo/seo-weekly-\d{4}-\d{2}-\d{2}\.json")
INTEL = re.compile(r"data/intel-snapshots/\d{4}-\d{2}-\d{2}\.(?:json|md)")
EMAIL = re.compile(rb"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

profile = sys.argv[1] if len(sys.argv) > 1 else "daily"
allowed = {"daily": DAILY, "aeo": AEO, "seo": SEO, "intel": INTEL}[profile]
if profile == "aeo":
    from aeo_weekly import validate_artifact as validate_aeo_artifact
elif profile == "seo":
    from seo_weekly import validate_artifact as validate_seo_artifact

def validate_content(relative: str, content: bytes) -> None:
    if not allowed.fullmatch(relative):
        raise SystemExit("Monitoring staging contains an unexpected path.")
    if EMAIL.search(content):
        raise SystemExit("Monitoring publication contains an email address.")
    if profile in {"aeo", "seo"}:
        try:
            artifact = json.loads(content)
        except ValueError:
            raise SystemExit("Monitoring publication contains invalid JSON.") from None
        if profile == "aeo" and validate_aeo_artifact(artifact, path=Path(relative)):
            raise SystemExit("AEO publication failed artifact validation.")
        if profile == "seo":
            if EMAIL.search(json.dumps(artifact, ensure_ascii=False).encode("utf-8")):
                raise SystemExit("Monitoring publication contains an email address.")
            try:
                errors = validate_seo_artifact(artifact, path=Path(relative), require_all_ok=True)
            except (TypeError, ValueError):
                raise SystemExit("SEO publication failed artifact validation.") from None
            if errors:
                raise SystemExit("SEO publication failed artifact validation.")


if profile == "seo" and len(sys.argv) == 3:
    reports = list(Path(sys.argv[2]).glob("seo-weekly-*.json"))
    if len(reports) != 1 or reports[0].is_symlink() or not reports[0].is_file():
        raise SystemExit("Expected exactly one regular SEO report.")
    validate_content(f"data/seo/{reports[0].name}", reports[0].read_bytes())
else:
    for path in subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"]).split(b"\0"):
        if not path:
            continue
        mode = subprocess.check_output(["git", "ls-files", "-s", "-z", "--", path]).partition(b" ")[0]
        if mode != b"100644":
            raise SystemExit("Daily monitoring staging contains a deleted or nonregular file.")
        content = subprocess.check_output(["git", "show", b":" + path])
        validate_content(path.decode("utf-8", errors="replace"), content)
