"""
Step 10: Deliver

Sends email with training guide link, PDF attachment, and ZWO instructions.
Uses Resend API (already used in athlete-os-web).
"""

import os
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict


def deliver(intake: Dict, guide_url: str, pdf_path: Path, workouts_dir: Path) -> Dict:
    """
    Send delivery email to athlete.

    Returns receipt dict.
    """
    try:
        import resend
    except ImportError:
        raise RuntimeError("Resend not installed. Run: pip install resend")

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY environment variable not set")

    resend.api_key = api_key

    athlete_name = intake["name"]
    athlete_email = intake["email"]
    race_name = intake["races"][0]["name"] if intake.get("races") else "Your Race"
    race_distance = intake["races"][0].get("distance_miles", "") if intake.get("races") else ""

    # Prepare PDF attachment
    attachments = []
    if pdf_path.exists():
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        attachments.append({
            "filename": f"{athlete_name.replace(' ', '_')}_Training_Guide.pdf",
            "content": base64.b64encode(pdf_bytes).decode("utf-8"),
            "type": "application/pdf",
        })

    # Count ZWO files
    zwo_count = len(list(workouts_dir.glob("*.zwo")))

    # Build email HTML
    html_body = f"""
    <div style="font-family: 'Courier New', monospace; max-width: 600px; margin: 0 auto;">
        <div style="background: #2c2c2c; color: #4ecdc4; padding: 30px; text-align: center;">
            <h1 style="margin: 0;">Your Training Plan is Ready</h1>
            <p style="color: #aaa; margin-top: 10px;">{race_name} {race_distance}mi</p>
        </div>

        <div style="padding: 30px; background: #f5f5f0;">
            <p>Hey {athlete_name},</p>

            <p>Your personalized training plan for <strong>{race_name} {race_distance}mi</strong>
            is ready. Here's what's included:</p>

            <ul>
                <li><strong>Training Guide:</strong>
                    <a href="{guide_url}" style="color: #4ecdc4;">View Online</a>
                    (PDF also attached)</li>
                <li><strong>{zwo_count} ZWO Workouts:</strong> Ready for Zwift / TrainingPeaks</li>
            </ul>

            <div style="background: #4ecdc4; color: #2c2c2c; padding: 15px; margin: 20px 0; font-weight: bold;">
                NEXT STEP: Import your ZWO files into Zwift or TrainingPeaks.
                Instructions are in your training guide.
            </div>

            <p>Questions? Reply to this email.</p>

            <p style="color: #888; font-size: 0.85em; margin-top: 30px;">
                Gravel God Cycling | gravelgodcycling.com
            </p>
        </div>
    </div>
    """

    # Send email
    result = resend.Emails.send({
        "from": "Gravel God <plans@gravelgodcycling.com>",
        "to": [athlete_email],
        "subject": f"Your {race_name} Training Plan is Ready",
        "html": html_body,
        "attachments": attachments,
    })

    return {
        "email_sent": True,
        "recipient": athlete_email,
        "guide_url": guide_url,
        "zwo_count": zwo_count,
        "resend_id": result.get("id") if isinstance(result, dict) else str(result),
        "timestamp": datetime.now().isoformat(),
    }
