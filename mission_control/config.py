"""Mission Control configuration — loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Root of the plan engine repo
REPO_ROOT = Path(__file__).resolve().parent.parent

# Key directories (still needed for local pipeline execution)
ATHLETES_DIR = REPO_ROOT / "athletes"
TEMPLATES_DIR = REPO_ROOT / "templates" / "emails"
INTAKES_DIR = REPO_ROOT / "intakes"
PLANS_DIR = REPO_ROOT / "plans"

# Pipeline entry point
PIPELINE_SCRIPT = REPO_ROOT / "run_pipeline.py"
PRE_DELIVERY_AUDIT = REPO_ROOT / "scripts" / "pre_delivery_audit.py"

# Jinja2 templates for the web UI
WEB_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# Resend (email sending)
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "plans@gravelgodcycling.com")
RESEND_FROM_NAME = os.environ.get("RESEND_FROM_NAME", "Gravel God Training")

# Sequence email identity (marketing automation)
SEQUENCE_FROM_EMAIL = os.environ.get("SEQUENCE_FROM_EMAIL", "matt@gravelgodcycling.com")
SEQUENCE_FROM_NAME = os.environ.get("SEQUENCE_FROM_NAME", "Matt at Gravel God")

# Webhook secret (for Worker → Mission Control auth)
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

# Server
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))

# Storage bucket name
STORAGE_BUCKET = os.environ.get("STORAGE_BUCKET", "plans")

# GA4 Analytics
GA4_PROPERTY_ID = os.environ.get("GA4_PROPERTY_ID", "")
GA4_CREDENTIALS_PATH = os.environ.get("GA4_CREDENTIALS_PATH", "")

# Stripe (optional)
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")
