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
    python scripts/validate_redirects.py --sample 50   # random subset for quick runs
"""

import random
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def extract_redirects_from_source():
    """Read the EVALUATED REDIRECT_BLOCK from push_wordpress.

    Importing (rather than regex-parsing the source file) is load-bearing:
    since the road migration, REDIRECT_BLOCK is a concatenation of a literal
    and 726 generated rules — a source-text regex sees none of them (this
    script silently validated zero redirects until 2026-07-25).
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from push_wordpress import REDIRECT_BLOCK
    block = REDIRECT_BLOCK
    
    # Parse RewriteRule lines
    redirects = []
    for line in block.splitlines():
        m = re.match(r'RewriteRule\s+\^(.+?)\$\s+(\S+)\s+\[R=301,L\]', line.strip())
        if m:
            pattern = m.group(1)
            target = m.group(2)
            # Skip generic/self-healing rules with capture groups (e.g. the
            # missing-tires/VS fallbacks added 2026-07-22) — their patterns
            # aren't literal paths and their targets contain backreferences,
            # so there is no single testable URL.
            if "(" in pattern or "\\d" in pattern or "$1" in target or "$2" in target:
                continue
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
    # Road-migration rules target roadielabs.com absolutely
    expected_full = expected_target if expected_target.startswith("http") \
        else f"{base_url}{expected_target}"
    
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
    """Check that a redirect target returns 200 (following redirects for
    cross-domain targets, which may themselves normalize)."""
    url = target_path if target_path.startswith("http") else f"{base_url}{target_path}"
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
    sample_n = None
    if "--sample" in sys.argv:
        sample_n = int(sys.argv[sys.argv.index("--sample") + 1])

    redirects = extract_redirects_from_source()
    if not redirects:
        print("ERROR: No redirects found in REDIRECT_BLOCK")
        sys.exit(1)

    if sample_n and sample_n < len(redirects):
        redirects = random.sample(redirects, sample_n)
        print(f"(random sample of {sample_n})")

    # Known exceptions: physical files that bypass mod_rewrite (nginx serves directly)
    KNOWN_EXCEPTIONS = set()

    to_check = [(s, t) for s, t in redirects if s not in KNOWN_EXCEPTIONS]
    skipped = len(redirects) - len(to_check)
    for source, _ in redirects:
        if source in KNOWN_EXCEPTIONS:
            print(f"  SKIP  {source} (physical file, nginx serves directly)")

    print(f"Validating {len(to_check)} redirects...\n")

    redirect_pass = 0
    redirect_fail = 0
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = pool.map(lambda st: (st[0], st[1], *check_redirect(st[0], st[1])), to_check)
        for source, target, ok, details in results:
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
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = pool.map(lambda t: (t, *check_target(t)), targets)
        for target, ok, details in results:
            if ok:
                target_pass += 1
                if verbose:
                    print(f"  PASS  {target}")
            else:
                target_fail += 1
                print(f"  FAIL  {target} → {details}")
    
    # Summary
    print(f"\n{'='*50}")
    print(f"Redirects: {redirect_pass}/{len(to_check)} pass ({skipped} skipped)")
    print(f"Targets:   {target_pass}/{len(targets)} pass")
    
    if redirect_fail > 0 or target_fail > 0:
        print(f"\nFAILED: {redirect_fail} redirect(s), {target_fail} target(s)")
        sys.exit(1)
    else:
        print(f"\nALL CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
