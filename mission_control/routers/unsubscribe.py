"""Unsubscribe endpoint — public, no auth required.

CAN-SPAM compliant: one-click link in every marketing email.
Uses HMAC token to prevent spoofed unsubscribes.
"""

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from mission_control import supabase_client as db
from mission_control.services.sequence_engine import (
    unsubscribe,
    verify_unsubscribe_token,
)

router = APIRouter()

_BRANDS = {
    "gravelgod": ("Gravel God", "gravelgodcycling.com"),
    "roadielabs": ("Roadie Labs", "roadielabs.com"),
    "xcskilabs": ("XC Ski Labs", "xcskilabs.com"),
}


def _resolve_brand(email: str, requested: str) -> str:
    if requested in _BRANDS:
        return requested
    # Older email links have no brand parameter. Use the latest enrollment so
    # those links also return the reader to the brand that sent the email.
    try:
        rows = db.select(
            "gg_sequence_enrollments", columns="source_data",
            match={"contact_email": email}, order="enrolled_at",
            order_desc=True, limit=1,
        )
        if rows:
            brand = (rows[0].get("source_data") or {}).get("brand")
            if brand in _BRANDS:
                return brand
    except Exception:
        pass
    return "gravelgod"


@router.get("/unsubscribe")
async def unsubscribe_page(
    email: str = Query(""),
    token: str = Query(""),
    brand: str = Query(""),
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

    display_brand = _resolve_brand(email, brand)
    count = unsubscribe(email)

    if count > 0:
        return HTMLResponse(_render_page(
            "You've Been Unsubscribed",
            f"We've removed <strong>{email}</strong> from all active email sequences. "
            "You won't receive any more marketing emails from us.",
            success=True,
            brand=display_brand,
        ))
    else:
        return HTMLResponse(_render_page(
            "Already Unsubscribed",
            f"<strong>{email}</strong> has no active email subscriptions. "
            "You're not receiving marketing emails from us.",
            success=True,
            brand=display_brand,
        ))


def _render_page(title: str, message: str, success: bool, brand: str = "gravelgod") -> str:
    name, domain = _BRANDS[brand]
    color = "#1A8A82" if success else "#c0392b"
    background, ink, border, header, accent, footer = (
        "#f8f3ec", "#3a2e25", "#d4c5b9", "#3a2e25", "#B7950B", "#8c7568"
    )
    if brand == "roadielabs":
        background, ink, border, header, accent, footer = (
            "white", "black", "gray", "black", "white", "gray"
        )
        color = "black" if success else "firebrick"
    elif brand == "xcskilabs":
        background, ink, border, header, accent, footer = (
            "linen", "black", "gray", "black", "white", "gray"
        )
        color = "firebrick"
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — {name}</title>
  <style>
    body {{ font-family: Georgia, serif; background: {background}; margin: 0; padding: 40px 20px; color: {ink}; }}
    .container {{ max-width: 500px; margin: 0 auto; background: white; border: 2px solid {border}; }}
    .header {{ background: {header}; padding: 24px 32px; }}
    .header h1 {{ color: {accent}; font-size: 20px; margin: 0; letter-spacing: -0.5px; }}
    .body {{ padding: 32px; line-height: 1.7; font-size: 16px; }}
    .body h2 {{ color: {color}; font-size: 18px; margin: 0 0 16px; }}
    .body p {{ margin: 0 0 16px; }}
    .footer {{ padding: 16px 32px; border-top: 2px solid {border}; font-family: 'Courier New', monospace; font-size: 11px; color: {footer}; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>{name}</h1>
    </div>
    <div class="body">
      <h2>{title}</h2>
      <p>{message}</p>
    </div>
    <div class="footer">
      {name} &middot; {domain}
    </div>
  </div>
</body>
</html>"""
