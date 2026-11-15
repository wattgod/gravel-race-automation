"""/llms-full.txt must be served from a file AIOSEO doesn't manage (GG-01).

AIOSEO owns the physical llms*.txt names in the webroot; after a clean upload
the public /llms-full.txt still answered 404 on 2026-11-15, while /llms.txt
worked through its llms-repo.txt rewrite. llms.txt links llms-full.txt.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import push_wordpress as pw  # noqa: E402


def test_rewrite_serves_repo_copy():
    assert "RewriteRule ^llms-full\\.txt$ /llms-full-repo.txt [L]" in pw.REDIRECT_BLOCK


def test_sync_uploads_repo_copy_and_requires_it(monkeypatch):
    import subprocess
    monkeypatch.chdir(ROOT)
    monkeypatch.setattr(pw, "get_ssh_credentials", lambda: ("h", "u", "22"))
    sent = []

    def fake_run(cmd, *a, **kw):
        if cmd[0] == "scp":
            sent.append(cmd[-1].rsplit("/", 1)[-1])
            if cmd[-1].endswith("/llms-full-repo.txt"):
                raise subprocess.CalledProcessError(1, cmd, stderr="denied")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(pw.subprocess, "run", fake_run)
    assert not pw.sync_llms_txt()
    assert "llms-full-repo.txt" in sent
