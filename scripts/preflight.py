#!/usr/bin/env python3
"""
Pre-deploy preflight checker.

Runs all validation and generation steps in the correct order, stopping
on the first failure. Use --generate to also regenerate all output files.
Use --deploy to regenerate AND deploy to production.

Usage:
    python scripts/preflight.py              # Validate only (fast)
    python scripts/preflight.py --generate   # Validate + regenerate all output
    python scripts/preflight.py --deploy     # Validate + regenerate + deploy + post-deploy checks
    python scripts/preflight.py --skip-tests # Skip pytest (useful during rapid iteration)
"""

import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
WORDPRESS_DIR = PROJECT_ROOT / "wordpress"


class Preflight:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.timings = []

    def run_step(self, label, cmd, *, cwd=None, optional=False):
        """Run a command, print result, return True on success."""
        print(f"\n{'─' * 60}")
        print(f"  {label}")
        print(f"{'─' * 60}")

        start = time.time()
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or PROJECT_ROOT,
                capture_output=False,
                timeout=600,
            )
            elapsed = time.time() - start
            self.timings.append((label, elapsed))

            if result.returncode == 0:
                print(f"\n  PASS  {label} ({elapsed:.1f}s)")
                self.passed += 1
                return True
            else:
                if optional:
                    print(f"\n  WARN  {label} (exit {result.returncode}, {elapsed:.1f}s)")
                    self.skipped += 1
                    return True
                else:
                    print(f"\n  FAIL  {label} (exit {result.returncode}, {elapsed:.1f}s)")
                    self.failed += 1
                    return False

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            self.timings.append((label, elapsed))
            print(f"\n  FAIL  {label} (TIMEOUT after {elapsed:.0f}s)")
            self.failed += 1
            return False

    def summary(self):
        total_time = sum(t for _, t in self.timings)
        print(f"\n{'═' * 60}")
        print(f"  PREFLIGHT SUMMARY")
        print(f"{'═' * 60}")
        print(f"  Passed:  {self.passed}")
        if self.skipped:
            print(f"  Warned:  {self.skipped}")
        print(f"  Failed:  {self.failed}")
        print(f"  Total:   {total_time:.1f}s")
        print()
        if self.failed:
            print("  RESULT: FAILED — do NOT deploy")
        else:
            print("  RESULT: ALL CLEAR")
        print(f"{'═' * 60}\n")


def main():
    args = set(sys.argv[1:])
    do_generate = "--generate" in args or "--deploy" in args
    do_deploy = "--deploy" in args
    skip_tests = "--skip-tests" in args

    pf = Preflight()

    print(f"\n{'═' * 60}")
    mode = "DEPLOY" if do_deploy else ("GENERATE" if do_generate else "VALIDATE")
    print(f"  PREFLIGHT — {mode} MODE")
    print(f"{'═' * 60}")

    # ── Phase 1: Validation ──────────────────────────────────────

    if not skip_tests:
        ok = pf.run_step(
            "pytest",
            [sys.executable, "-m", "pytest", "tests/", "-q",
             "--tb=short", "-x"],
        )
        if not ok:
            pf.summary()
            return 1
    else:
        print("\n  SKIP  pytest (--skip-tests)")
        pf.skipped += 1

    ok = pf.run_step(
        "audit_colors.py",
        [sys.executable, str(SCRIPTS_DIR / "audit_colors.py")],
    )
    if not ok:
        pf.summary()
        return 1

    ok = pf.run_step(
        "validate_citations.py",
        [sys.executable, str(SCRIPTS_DIR / "validate_citations.py")],
    )
    if not ok:
        pf.summary()
        return 1

    ok = pf.run_step(
        "audit_race_data.py",
        [sys.executable, str(SCRIPTS_DIR / "audit_race_data.py")],
        optional=True,  # warn but don't block — known low-confidence profiles have issues
    )

    if not do_generate:
        pf.summary()
        return 1 if pf.failed else 0

    # ── Phase 2: Generation ──────────────────────────────────────

    ok = pf.run_step(
        "generate_index.py --with-jsonld",
        [sys.executable, str(SCRIPTS_DIR / "generate_index.py"), "--with-jsonld"],
    )
    if not ok:
        pf.summary()
        return 1

    ok = pf.run_step(
        "generate_sitemap.py",
        [sys.executable, str(SCRIPTS_DIR / "generate_sitemap.py")],
    )
    if not ok:
        pf.summary()
        return 1

    ok = pf.run_step(
        "generate_neo_brutalist.py --all",
        [sys.executable, str(WORDPRESS_DIR / "generate_neo_brutalist.py"), "--all"],
    )
    if not ok:
        pf.summary()
        return 1

    ok = pf.run_step(
        "generate_homepage.py",
        [sys.executable, str(WORDPRESS_DIR / "generate_homepage.py")],
    )
    if not ok:
        pf.summary()
        return 1

    ok = pf.run_step(
        "generate_methodology.py",
        [sys.executable, str(WORDPRESS_DIR / "generate_methodology.py")],
    )
    if not ok:
        pf.summary()
        return 1

    ok = pf.run_step(
        "generate_tier_hubs.py",
        [sys.executable, str(WORDPRESS_DIR / "generate_tier_hubs.py")],
    )
    if not ok:
        pf.summary()
        return 1

    if not do_deploy:
        pf.summary()
        return 1 if pf.failed else 0

    # ── Phase 3: Deploy ──────────────────────────────────────────

    ok = pf.run_step(
        "push_wordpress.py --deploy-content",
        [sys.executable, str(SCRIPTS_DIR / "push_wordpress.py"), "--deploy-content"],
    )
    if not ok:
        pf.summary()
        return 1

    ok = pf.run_step(
        "push_wordpress.py --sync-homepage",
        [sys.executable, str(SCRIPTS_DIR / "push_wordpress.py"), "--sync-homepage"],
    )
    if not ok:
        pf.summary()
        return 1

    # ── Phase 4: Post-deploy validation ──────────────────────────

    ok = pf.run_step(
        "validate_deploy.py",
        [sys.executable, str(SCRIPTS_DIR / "validate_deploy.py")],
    )
    if not ok:
        pf.summary()
        return 1

    ok = pf.run_step(
        "validate_redirects.py",
        [sys.executable, str(SCRIPTS_DIR / "validate_redirects.py")],
        optional=True,  # redirect validation is supplementary
    )

    pf.summary()
    return 1 if pf.failed else 0


if __name__ == "__main__":
    sys.exit(main())
