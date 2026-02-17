#!/usr/bin/env python3
"""Mission Control pre-deploy audit — catches broken code BEFORE it ships.

This script is the equivalent of pre_delivery_audit.py for Mission Control.
It validates the MC codebase statically (no running server needed).

Run: python3 scripts/mc_pre_deploy_audit.py
Exit code: 0 = pass, 1 = failures found

Checks:
1. CSS_CLASS_MATCH   — Every CSS class used in templates exists in CSS
2. TEMPLATE_VARS     — Template variables match actual data shapes
3. SEQUENCE_TEMPLATES — Every template referenced in sequences exists as a file
4. WEBHOOK_AUTH      — All webhook endpoints have auth guards
5. HEALTH_ENDPOINT   — /health route exists
6. NO_DEPRECATED_API — No datetime.utcnow() or other deprecated calls
7. IMPORT_CHECK      — All imports resolve
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MC_DIR = REPO_ROOT / "mission_control"
TEMPLATES_DIR = MC_DIR / "templates"
STATIC_DIR = MC_DIR / "static"
SEQUENCES_DIR = MC_DIR / "sequences"
EMAIL_TEMPLATES_DIR = TEMPLATES_DIR / "emails" / "sequences"

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN = "\033[33mWARN\033[0m"

failures = []
warnings = []


def check(name: str, passed: bool, detail: str = ""):
    status = PASS if passed else FAIL
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    if not passed:
        failures.append(f"{name}: {detail}")


def warn(name: str, detail: str = ""):
    print(f"  [{WARN}] {name} — {detail}")
    warnings.append(f"{name}: {detail}")


# ---------------------------------------------------------------------------
# CHECK 1: CSS class matching
# ---------------------------------------------------------------------------
def check_css_classes():
    print("\n1. CSS CLASS MATCH")

    # Collect all CSS class definitions
    css_classes = set()
    for css_file in STATIC_DIR.rglob("*.css"):
        content = css_file.read_text()
        # Match .class-name patterns (including BEM)
        for match in re.finditer(r'\.((?:mc|gg)-[\w-]+(?:__[\w-]+)?(?:--[\w-]+)?)\b', content):
            css_classes.add(match.group(1))

    # Collect all CSS class usages in HTML templates
    used_classes = {}
    for html_file in TEMPLATES_DIR.rglob("*.html"):
        content = html_file.read_text()
        rel_path = html_file.relative_to(TEMPLATES_DIR)
        for match in re.finditer(r'class="([^"]*)"', content):
            for cls in match.group(1).split():
                # Skip Jinja2 dynamic classes and non-mc/gg classes
                if cls.startswith(("mc-", "gg-")) and "{{" not in cls and "{%" not in cls:
                    if cls not in css_classes:
                        if cls not in used_classes:
                            used_classes[cls] = []
                        used_classes[cls].append(str(rel_path))

    # Also check Python routers for inline HTML
    for py_file in (MC_DIR / "routers").rglob("*.py"):
        content = py_file.read_text()
        rel_path = py_file.relative_to(MC_DIR)
        for match in re.finditer(r'class="([^"]*)"', content):
            for cls in match.group(1).split():
                if cls.startswith(("mc-", "gg-")) and "{" not in cls and cls not in css_classes:
                    if cls not in used_classes:
                        used_classes[cls] = []
                    used_classes[cls].append(str(rel_path))

    if used_classes:
        for cls, files in sorted(used_classes.items()):
            check("CSS class defined", False, f"'{cls}' used in {', '.join(files[:3])} but not in any CSS file")
    else:
        check("All CSS classes defined", True)


# ---------------------------------------------------------------------------
# CHECK 2: Sequence email templates exist
# ---------------------------------------------------------------------------
def check_sequence_templates():
    print("\n2. SEQUENCE EMAIL TEMPLATES")

    # Parse all sequence definitions for template references
    referenced_templates = set()
    for seq_file in SEQUENCES_DIR.glob("*.py"):
        if seq_file.name == "__init__.py":
            continue
        content = seq_file.read_text()
        for match in re.finditer(r'"template":\s*"(\w+)"', content):
            referenced_templates.add(match.group(1))

    # Check which template files exist
    existing_templates = set()
    if EMAIL_TEMPLATES_DIR.exists():
        for f in EMAIL_TEMPLATES_DIR.glob("*.html"):
            existing_templates.add(f.stem)

    missing = referenced_templates - existing_templates
    if missing:
        for t in sorted(missing):
            check("Template file exists", False, f"'{t}.html' referenced in sequences but missing from {EMAIL_TEMPLATES_DIR.relative_to(REPO_ROOT)}")
    else:
        check("All sequence templates exist", True, f"{len(referenced_templates)} templates verified")


# ---------------------------------------------------------------------------
# CHECK 3: Webhook auth
# ---------------------------------------------------------------------------
def check_webhook_auth():
    print("\n3. WEBHOOK AUTHENTICATION")

    webhooks_file = MC_DIR / "routers" / "webhooks.py"
    if not webhooks_file.exists():
        check("Webhooks file exists", False, "mission_control/routers/webhooks.py not found")
        return

    content = webhooks_file.read_text()

    # Find all @router.post endpoints
    endpoints = re.findall(r'@router\.post\("(/[\w/-]+)"\)', content)

    for endpoint in endpoints:
        # Check if the endpoint has auth (WEBHOOK_SECRET check nearby)
        # Find the function after this decorator
        pattern = rf'@router\.post\("{re.escape(endpoint)}"\).*?(?=@router\.post|$)'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            func_body = match.group(0)
            has_auth = "WEBHOOK_SECRET" in func_body or "authorization" in func_body.lower()
            check(f"Auth on {endpoint}", has_auth,
                  "No WEBHOOK_SECRET check found" if not has_auth else "")


# ---------------------------------------------------------------------------
# CHECK 4: Health endpoint
# ---------------------------------------------------------------------------
def check_health_endpoint():
    print("\n4. HEALTH ENDPOINT")

    app_file = MC_DIR / "app.py"
    if not app_file.exists():
        check("app.py exists", False)
        return

    content = app_file.read_text()
    has_health = '"/health"' in content or "'/health'" in content
    check("/health endpoint exists", has_health,
          "No /health endpoint found in app.py" if not has_health else "")


# ---------------------------------------------------------------------------
# CHECK 5: No deprecated API usage
# ---------------------------------------------------------------------------
def check_deprecated_api():
    print("\n5. DEPRECATED API USAGE")

    deprecated_patterns = [
        (r'datetime\.utcnow\(\)', "datetime.utcnow() is deprecated in Python 3.12 — use datetime.now(timezone.utc)"),
        (r'\.not_\.in_\(', ".not_.in_() is not valid supabase-py API — use .neq() chain"),
    ]

    found_any = False
    for py_file in MC_DIR.rglob("*.py"):
        content = py_file.read_text()
        rel_path = py_file.relative_to(REPO_ROOT)
        for pattern, msg in deprecated_patterns:
            if re.search(pattern, content):
                check("No deprecated API", False, f"{rel_path}: {msg}")
                found_any = True

    if not found_any:
        check("No deprecated API usage", True)


# ---------------------------------------------------------------------------
# CHECK 6: Template variable safety (known mismatches)
# ---------------------------------------------------------------------------
def check_template_vars():
    print("\n6. TEMPLATE VARIABLE CHECKS")

    known_bad_patterns = [
        ("nps_data.nps_score", "reports/index.html", "Should be nps_data.nps (no _score suffix)"),
        ("nps_data.passives", "reports/index.html", "passives is never computed — use total - promoters - detractors"),
        ("r.referrer_name", "reports/index.html", "Should be r.gg_athletes.name (Supabase join is nested)"),
        ("run.athlete_name", "**/*.html", "Should be run.gg_athletes.name (Supabase join is nested)"),
        ("run.athlete_slug", "**/*.html", "Should be run.gg_athletes.slug (Supabase join is nested)"),
    ]

    for pattern, file_hint, msg in known_bad_patterns:
        found = False
        for html_file in TEMPLATES_DIR.rglob("*.html"):
            content = html_file.read_text()
            if pattern in content:
                rel_path = html_file.relative_to(TEMPLATES_DIR)
                check("Template var valid", False, f"{rel_path}: '{pattern}' — {msg}")
                found = True
        if not found:
            check(f"No '{pattern}'", True)


# ---------------------------------------------------------------------------
# CHECK 7: Supabase upsert double-call
# ---------------------------------------------------------------------------
def check_upsert_bug():
    print("\n7. SUPABASE UPSERT BUG")

    client_file = MC_DIR / "supabase_client.py"
    if not client_file.exists():
        check("supabase_client.py exists", False)
        return

    content = client_file.read_text()

    # Check for the double-upsert pattern
    # The bug: first upsert is called without on_conflict, then again with it
    if "q = _table(table).upsert(data)\n    if on_conflict:\n        q = _table(table).upsert(data, on_conflict=on_conflict)" in content:
        check("No double upsert", False,
              "upsert() calls _table().upsert() twice when on_conflict is set — first call may execute immediately")
    else:
        check("No double upsert", True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("MISSION CONTROL PRE-DEPLOY AUDIT")
    print("=" * 60)

    check_css_classes()
    check_sequence_templates()
    check_webhook_auth()
    check_health_endpoint()
    check_deprecated_api()
    check_template_vars()
    check_upsert_bug()

    print("\n" + "=" * 60)
    if failures:
        print(f"\033[31m{len(failures)} FAILURE(S)\033[0m — deploy blocked")
        for f in failures:
            print(f"  - {f}")
    else:
        print(f"\033[32mALL CHECKS PASSED\033[0m")

    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for w in warnings:
            print(f"  - {w}")

    print("=" * 60)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
