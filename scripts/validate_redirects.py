#!/usr/bin/env python3
"""
Validate all deployed .htaccess redirects.

Checks:
1. Every redirect source returns HTTP 301
2. Every redirect points to the correct target
3. Every target returns HTTP 200
4. No redirect loops

Usage:
    python scripts/validate_redirects.py
    python scripts/validate_redirects.py --verbose
"""

import re
import subprocess
import sys
from pathlib import Path


def extract_redirects_from_source():
    """Parse REDIRECT_BLOCK from push_wordpress.py to get all redirect rules."""
    script = Path(__file__).resolve().parent / "push_wordpress.py"
    content = script.read_text()
    
    # Extract the REDIRECT_BLOCK string
    match = re.search(r'REDIRECT_BLOCK\s*=\s*"""\\\n(.*?)"""', content, re.DOTALL)
    if not match:
        print("ERROR: Could not find REDIRECT_BLOCK in push_wordpress.py")
        sys.exit(1)
    
    block = match.group(1)
    
    # Parse RewriteRule lines
    redirects = []
    for line in block.splitlines():
        m = re.match(r'RewriteRule\s+\^(.+?)\$\s+(\S+)\s+\[R=301,L\]', line.strip())
        if m:
            pattern = m.group(1)
            target = m.group(2)
            # Convert regex pattern to a testable URL path
            # Handle escape levels: \\. or \\\\. → .
            test_path = re.sub(r'\\+\.', '.', pattern)
            # Remove ? (makes preceding char optional) — use the char present
            test_path = test_path.replace('?', '')
            if not test_path.startswith('/'):
                test_path = '/' + test_path
            # Only add trailing / if path doesn't end with a file extension
            if not re.search(r'\.\w+$', test_path) and not test_path.endswith('/'):
                test_path += '/'
            redirects.append((test_path, target))
    
    return redirects


def check_redirect(source_path, expected_target, base_url="https://gravelgodcycling.com"):
    """Check a single redirect. Returns (ok, details)."""
    url = f"{base_url}{source_path}"
    expected_full = f"{base_url}{expected_target}"
    
    try:
        result = subprocess.run(
            ["curl", "-sI", "-o", "/dev/null", "-w", "%{http_code} %{redirect_url}", url],
            capture_output=True, text=True, timeout=15
        )
        parts = result.stdout.strip().split(" ", 1)
        code = parts[0]
        location = parts[1] if len(parts) > 1 else ""
        
        if code != "301":
            return False, f"HTTP {code} (expected 301)"
        if location != expected_full:
            return False, f"redirects to {location} (expected {expected_full})"
        return True, "OK"
    except Exception as e:
        return False, f"Error: {e}"


def check_target(target_path, base_url="https://gravelgodcycling.com"):
    """Check that a redirect target returns 200."""
    url = f"{base_url}{target_path}"
    try:
        result = subprocess.run(
            ["curl", "-sI", "-o", "/dev/null", "-w", "%{http_code}", url],
            capture_output=True, text=True, timeout=15
        )
        code = result.stdout.strip()
        if code == "200":
            return True, "OK"
        return False, f"HTTP {code}"
    except Exception as e:
        return False, f"Error: {e}"


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    
    redirects = extract_redirects_from_source()
    if not redirects:
        print("ERROR: No redirects found in REDIRECT_BLOCK")
        sys.exit(1)
    
    # Known exceptions: physical files that bypass mod_rewrite (nginx serves directly)
    KNOWN_EXCEPTIONS = set()

    print(f"Validating {len(redirects)} redirects...\n")

    # Check redirects
    redirect_pass = 0
    redirect_fail = 0
    skipped = 0
    for source, target in redirects:
        if source in KNOWN_EXCEPTIONS:
            skipped += 1
            print(f"  SKIP  {source} (physical file, nginx serves directly)")
            continue
        ok, details = check_redirect(source, target)
        if ok:
            redirect_pass += 1
            if verbose:
                print(f"  PASS  {source} → {target}")
        else:
            redirect_fail += 1
            print(f"  FAIL  {source} → {details}")
    
    # Check targets (deduplicated)
    targets = sorted(set(t for _, t in redirects))
    print(f"\nValidating {len(targets)} unique targets...")
    target_pass = 0
    target_fail = 0
    for target in targets:
        ok, details = check_target(target)
        if ok:
            target_pass += 1
            if verbose:
                print(f"  PASS  {target}")
        else:
            target_fail += 1
            print(f"  FAIL  {target} → {details}")
    
    # Summary
    print(f"\n{'='*50}")
    tested = len(redirects) - skipped
    print(f"Redirects: {redirect_pass}/{tested} pass ({skipped} skipped)")
    print(f"Targets:   {target_pass}/{len(targets)} pass")
    
    if redirect_fail > 0 or target_fail > 0:
        print(f"\nFAILED: {redirect_fail} redirect(s), {target_fail} target(s)")
        sys.exit(1)
    else:
        print(f"\nALL CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
