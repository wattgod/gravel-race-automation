"""Tests for the MC pre-deploy audit script.

This test runs the actual audit script and verifies it passes.
If this test fails, it means the codebase has a bug that the audit catches.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)


class TestPreDeployAudit:
    def test_audit_passes_with_zero_failures(self):
        """The pre-deploy audit must pass clean — zero failures."""
        result = subprocess.run(
            [sys.executable, "scripts/mc_pre_deploy_audit.py"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0, (
            f"Pre-deploy audit failed with {result.returncode}:\n{result.stdout}\n{result.stderr}"
        )

    def test_audit_checks_css_classes(self):
        """Verify the CSS class check runs."""
        result = subprocess.run(
            [sys.executable, "scripts/mc_pre_deploy_audit.py"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert "CSS CLASS MATCH" in result.stdout

    def test_audit_checks_sequence_templates(self):
        """Verify the sequence template check runs."""
        result = subprocess.run(
            [sys.executable, "scripts/mc_pre_deploy_audit.py"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert "SEQUENCE EMAIL TEMPLATES" in result.stdout

    def test_audit_checks_webhook_auth(self):
        """Verify the webhook auth check runs."""
        result = subprocess.run(
            [sys.executable, "scripts/mc_pre_deploy_audit.py"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert "WEBHOOK AUTHENTICATION" in result.stdout

    def test_audit_checks_all_seven_categories(self):
        """All 7 check categories must appear in output."""
        result = subprocess.run(
            [sys.executable, "scripts/mc_pre_deploy_audit.py"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        for check in [
            "CSS CLASS MATCH",
            "SEQUENCE EMAIL TEMPLATES",
            "WEBHOOK AUTHENTICATION",
            "HEALTH ENDPOINT",
            "DEPRECATED API USAGE",
            "TEMPLATE VARIABLE CHECKS",
            "SUPABASE UPSERT BUG",
        ]:
            assert check in result.stdout, f"Missing check: {check}"
