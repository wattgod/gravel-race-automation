"""Email a Media Radar digest using the pipeline's existing Resend pattern."""

from __future__ import annotations

import html
import os


def deliver_digest(markdown: str, subject: str, recipient: str = "matti@endurelabs.app") -> dict:
    try:
        import resend
    except ImportError as exc:
        raise RuntimeError("Resend not installed. Run: pip install resend") from exc
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY environment variable not set")
    resend.api_key = api_key
    body = f"<pre style=\"white-space:pre-wrap;font:15px/1.5 monospace\">{html.escape(markdown)}</pre>"
    result = resend.Emails.send({
        "from": "Gravel God <plans@gravelgodcycling.com>",
        "to": [recipient], "subject": subject, "html": body,
    })
    return {"email_sent": True, "recipient": recipient, "resend_id": result.get("id") if isinstance(result, dict) else str(result)}

