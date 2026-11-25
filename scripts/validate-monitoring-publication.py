"""Validate staged outputs before publishing to the public monitoring branch."""
import re
import subprocess

ALLOWED = re.compile(
    r"(?:data/gsc-snapshots/\d{4}-\d{2}-\d{2}\.json"
    r"|data/cwv-snapshots/\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.json"
    r"|reports/\d{4}-\d{2}-\d{2}\.md)"
)
EMAIL = re.compile(rb"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

for path in subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"]).split(b"\0"):
    if not path:
        continue
    if not ALLOWED.fullmatch(path.decode("utf-8", errors="replace")):
        raise SystemExit("Daily monitoring staging contains an unexpected path.")
    mode = subprocess.check_output(["git", "ls-files", "-s", "-z", "--", path]).partition(b" ")[0]
    if mode != b"100644":
        raise SystemExit("Daily monitoring staging contains a deleted or nonregular file.")
    content = subprocess.check_output(["git", "show", b":" + path])
    if EMAIL.search(content):
        raise SystemExit("Daily monitoring publication contains an email address.")
