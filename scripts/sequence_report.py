#!/usr/bin/env python3
"""
Per-variant report for email sequences: enrollments, opens, clicks,
purchases, with chi-squared significance between variants.

Decision tool for the welcome-sequence A/B (Value-first vs Sober).
Weights are shifted MANUALLY in mission_control/sequences/*.py once a
variant wins at meaningful volume — no automated bandit at this list
size, it would chase noise.

Usage:
    railway run python3 scripts/sequence_report.py            # prod data
    python3 scripts/sequence_report.py --sequence welcome_v1  # one sequence

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SERVICE_KEY)
"""

import argparse
import json
import math
import os
import sys
import urllib.parse
import urllib.request

MIN_SENDS_FOR_SIGNIFICANCE = 100  # per variant, before p-values mean much

# Purchase definition matches the engine's customer-suppression statuses
PURCHASED_STATUSES = ("delivered", "approved", "audit_passed")


def _req(path: str, params: str = "") -> list:
    base = os.environ["SUPABASE_URL"]
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_SERVICE_KEY", ""))
    url = f"{base}/rest/v1/{path}?{params}"
    req = urllib.request.Request(
        url, headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def chi2_p(a_hit: int, a_n: int, b_hit: int, b_n: int) -> float | None:
    """2x2 chi-squared p-value (df=1), no scipy needed."""
    if a_n == 0 or b_n == 0:
        return None
    table = [[a_hit, a_n - a_hit], [b_hit, b_n - b_hit]]
    total = a_n + b_n
    col_hit = a_hit + b_hit
    col_miss = total - col_hit
    if col_hit == 0 or col_miss == 0:
        return None
    chi2 = 0.0
    for i, row_n in enumerate((a_n, b_n)):
        for j, col_n in enumerate((col_hit, col_miss)):
            expected = row_n * col_n / total
            if expected == 0:
                return None
            chi2 += (table[i][j] - expected) ** 2 / expected
    return math.erfc(math.sqrt(chi2 / 2))


def pct(hit: int, n: int) -> str:
    return f"{hit / n * 100:5.1f}%" if n else "    —"


def report(sequence_id: str | None) -> None:
    seq_filter = f"&sequence_id=eq.{sequence_id}" if sequence_id else ""
    enrollments = _req(
        "gg_sequence_enrollments",
        f"select=id,sequence_id,variant,status,contact_email{seq_filter}")
    if not enrollments:
        print("No enrollments found.")
        return

    enrollment_ids = {e["id"]: e for e in enrollments}
    sends = _req("gg_sequence_sends",
                 "select=enrollment_id,opened_at,clicked_at,status")
    sends = [s for s in sends if s["enrollment_id"] in enrollment_ids]

    purchased_emails = {
        a["email"].strip().lower()
        for a in _req("gg_athletes", "select=email,plan_status")
        if a.get("email") and a.get("plan_status") in PURCHASED_STATUSES
    }

    by_seq: dict = {}
    for e in enrollments:
        v = by_seq.setdefault(e["sequence_id"], {}).setdefault(e["variant"], {
            "enrolled": 0, "unsubscribed": 0, "sends": 0,
            "opens": 0, "clicks": 0, "purchases": 0,
        })
        v["enrolled"] += 1
        if e["status"] == "unsubscribed":
            v["unsubscribed"] += 1
        if (e.get("contact_email") or "").strip().lower() in purchased_emails:
            v["purchases"] += 1
    for s in sends:
        e = enrollment_ids[s["enrollment_id"]]
        v = by_seq[e["sequence_id"]][e["variant"]]
        v["sends"] += 1
        if s.get("opened_at"):
            v["opens"] += 1
        if s.get("clicked_at"):
            v["clicks"] += 1

    for seq_id, variants in sorted(by_seq.items()):
        print(f"\n=== {seq_id} ===")
        print(f"{'variant':<8}{'enrolled':>9}{'unsub':>7}{'sends':>7}"
              f"{'opens':>7}{'open%':>8}{'clicks':>8}{'click%':>8}{'buys':>6}")
        for vk in sorted(variants):
            v = variants[vk]
            print(f"{vk:<8}{v['enrolled']:>9}{v['unsubscribed']:>7}"
                  f"{v['sends']:>7}{v['opens']:>7}{pct(v['opens'], v['sends']):>8}"
                  f"{v['clicks']:>8}{pct(v['clicks'], v['sends']):>8}"
                  f"{v['purchases']:>6}")

        keys = sorted(variants)
        if len(keys) == 2:
            a, b = variants[keys[0]], variants[keys[1]]
            for metric, hit in (("opens", "opens"), ("clicks", "clicks")):
                p = chi2_p(a[hit], a["sends"], b[hit], b["sends"])
                if p is None:
                    continue
                verdict = "SIGNIFICANT" if p < 0.05 else "not significant"
                print(f"  {metric}: p={p:.3f} ({verdict})")
            under = [k for k in keys
                     if variants[k]["sends"] < MIN_SENDS_FOR_SIGNIFICANCE]
            if under:
                print(f"  note: variant(s) {', '.join(under)} below "
                      f"{MIN_SENDS_FOR_SIGNIFICANCE} sends — p-values are "
                      f"premature, keep 50/50 and wait")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequence", help="Limit to one sequence_id")
    args = parser.parse_args()
    if not os.environ.get("SUPABASE_URL"):
        print("Set SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY "
              "(tip: `railway run python3 scripts/sequence_report.py`)")
        return 1
    report(args.sequence)
    return 0


if __name__ == "__main__":
    sys.exit(main())
