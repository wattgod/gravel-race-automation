"""Unsubscribe endpoint — public, no auth required.

CAN-SPAM compliant: one-click link in every marketing email.
Uses HMAC token to prevent spoofed unsubscribes.
"""

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from mission_control.services.sequence_engine import (
    unsubscribe,
    verify_unsubscribe_token,
)

router = APIRouter()


@router.get("/unsubscribe")
async def unsubscribe_page(
    email: str = Query(""),
    token: str = Query(""),
):
    if not email or not token:
        return HTMLResponse(_render_page(
            "Invalid Link",
            "This unsubscribe link is missing required information. "
            "If you'd like to unsubscribe, reply to any email from us with 'unsubscribe'.",
            success=False,
        ))

    if not verify_unsubscribe_token(email, token):
        return HTMLResponse(_render_page(
            "Invalid Link",
            "This unsubscribe link is invalid or expired. "
            "If you'd like to unsubscribe, reply to any email from us with 'unsubscribe'.",
            success=False,
        ))

    count = unsubscribe(email)

    if count > 0:
        return HTMLResponse(_render_page(
            "You've Been Unsubscribed",
            f"We've removed <strong>{email}</strong> from all active email sequences. "
            "You won't receive any more marketing emails from us.",
            success=True,
        ))
    else:
        return HTMLResponse(_render_page(
            "Already Unsubscribed",
            f"<strong>{email}</strong> has no active email subscriptions. "
            "You're not receiving marketing emails from us.",
            success=True,
        ))


def _render_page(title: str, message: str, success: bool) -> str:
    color = "#1A8A82" if success else "#c0392b"
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — Gravel God</title>
  <style>
    body {{ font-family: Georgia, serif; background: #f8f3ec; margin: 0; padding: 40px 20px; color: #3a2e25; }}
    .container {{ max-width: 500px; margin: 0 auto; background: #fff; border: 2px solid #d4c5b9; }}
    .header {{ background: #3a2e25; padding: 24px 32px; }}
    .header h1 {{ color: #B7950B; font-size: 20px; margin: 0; letter-spacing: -0.5px; }}
    .body {{ padding: 32px; line-height: 1.7; font-size: 16px; }}
    .body h2 {{ color: {color}; font-size: 18px; margin: 0 0 16px; }}
    .body p {{ margin: 0 0 16px; }}
    .footer {{ padding: 16px 32px; border-top: 2px solid #d4c5b9; font-family: 'Courier New', monospace; font-size: 11px; color: #8c7568; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Gravel God</h1>
    </div>
    <div class="body">
      <h2>{title}</h2>
      <p>{message}</p>
    </div>
    <div class="footer">
      Gravel God &middot; gravelgodcycling.com
    </div>
  </div>
</body>
</html>"""
