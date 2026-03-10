"""Admin authentication middleware — Bearer token via MISSION_CONTROL_SECRET.

Fail-closed: if MISSION_CONTROL_SECRET is not set, ALL protected requests
are denied with 401. This prevents accidental exposure on misconfigured deploys.
"""

import os

from fastapi import Header, HTTPException


def _get_secret() -> str:
    """Read the secret at call time so tests can patch env vars."""
    return os.environ.get("MISSION_CONTROL_SECRET", "")


async def require_admin(authorization: str = Header("")) -> None:
    """FastAPI dependency — verifies ``Authorization: Bearer <secret>``.

    Raises 401 if:
    - ``MISSION_CONTROL_SECRET`` is not set (fail closed)
    - Header is missing or does not match
    """
    secret = _get_secret()

    if not secret:
        raise HTTPException(
            status_code=401,
            detail="MISSION_CONTROL_SECRET is not configured — all admin access denied",
        )

    expected = f"Bearer {secret}"
    if authorization != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing admin credentials",
        )
