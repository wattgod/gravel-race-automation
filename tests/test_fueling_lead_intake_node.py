"""Runs the lead-intake worker's node tests under pytest, so CI runs them.

tests/test_fueling_lead_intake.mjs imports workers/fueling-lead-intake/worker.js
directly and stubs fetch; it covers the athlete_exit alert and forwarding.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

SUITE = Path(__file__).resolve().parent / "test_fueling_lead_intake.mjs"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_worker_node_suite_passes():
    run = subprocess.run(["node", "--test", str(SUITE)], capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, (run.stdout[-6000:] + "\n" + run.stderr[-2000:])
