"""Deploys must not ship macOS AppleDouble (`._*`) files.

macOS tar adds `._name` metadata entries unless COPYFILE_DISABLE=1 is set.
They landed on the server (3,844 under /race/ by 2026-10-10) and tripped the
race page sync's file-count check. push_wordpress.py sets the variable at
import so every `tar -cf` subprocess inherits it.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import push_wordpress  # noqa: E402,F401


def test_import_sets_copyfile_disable():
    assert os.environ.get("COPYFILE_DISABLE") == "1"


@pytest.mark.skipif(sys.platform != "darwin", reason="AppleDouble files are a macOS tar behaviour")
def test_tar_archive_has_no_appledouble_entries(tmp_path):
    page = tmp_path / "src" / "index.html"
    page.parent.mkdir()
    page.write_text("<p>race</p>")
    # An extended attribute is what makes macOS tar emit `._index.html`.
    subprocess.run(["xattr", "-w", "com.apple.metadata:test", "x", str(page)], check=True)

    archive = tmp_path / "out.tar"
    with archive.open("wb") as fh:
        subprocess.run(["tar", "-cf", "-", "-C", str(page.parent), "index.html"], stdout=fh, check=True)

    names = tarfile.open(archive).getnames()
    assert names == ["index.html"]
