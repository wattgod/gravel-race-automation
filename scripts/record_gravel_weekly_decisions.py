#!/usr/bin/env python3
"""Mirror a canonical Gravel Weekly decision receipt into the control plane."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from validate_gravel_weekly import validate_issue
from validate_gravel_weekly_decisions import validate_decision_receipt

DEFAULT_ENDPOINT = "https://race-intelligence-control-plane.vercel.app/api/editorial-decision"


def post_decisions(receipt: dict, endpoint: str, secret: str) -> list[dict]:
    responses: list[dict] = []
    for decision in receipt["decisions"]:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(decision, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1_000]
            raise RuntimeError(f"control-plane decision rejected with HTTP {exc.code}: {detail}") from exc
        if not isinstance(payload, dict) or payload.get("accepted") is not True:
            raise RuntimeError("control plane did not acknowledge the editorial decision")
        responses.append(payload)
    return responses


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("issue", type=Path)
    parser.add_argument("--endpoint", default=os.environ.get("CONTROL_PLANE_EDITORIAL_DECISION_URL", DEFAULT_ENDPOINT))
    args = parser.parse_args()
    secret = os.environ.get("CONTROL_PLANE_INGEST_SECRET")
    if not secret:
        raise SystemExit("CONTROL_PLANE_INGEST_SECRET is required")
    issue = validate_issue(json.loads(args.issue.read_text(encoding="utf-8")))
    receipt = validate_decision_receipt(json.loads(args.receipt.read_text(encoding="utf-8")), issue)
    responses = post_decisions(receipt, args.endpoint, secret)
    recorded_voice = sum(bool(response.get("voiceEditRecorded")) for response in responses)
    print(f"Recorded {len(responses)} editorial decision(s); {recorded_voice} approved voice edit(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
