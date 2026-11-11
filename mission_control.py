#!/usr/bin/env python3
"""Gravel God Mission Control — Operations Dashboard.

Launch: python3 mission_control.py
Serves at http://0.0.0.0:8000 (or PORT env var)
"""

import os
import sys

import uvicorn

from mission_control.runtime_credentials import prepare_ga4_credentials

prepare_ga4_credentials()

from mission_control.config import HOST, PORT


def main():
    # Before anything logs: root at INFO, request-URL loggers at WARNING.
    from mission_control.app import configure_logging
    configure_logging()

    print("=" * 60)
    print("  Gravel God — Mission Control")
    print("=" * 60)

    # Validate required env vars
    supabase_url = os.environ.get("SUPABASE_URL", "")
    if not supabase_url:
        print("\n  WARNING: SUPABASE_URL not set. Set environment variables:")
        print("    SUPABASE_URL, SUPABASE_SERVICE_KEY")
        print("  Continuing anyway for local development...\n")

    # Start server
    print(f"Starting server on {HOST}:{PORT}")
    url = f"http://{HOST}:{PORT}"
    print(f"\n  Dashboard: {url}")
    print("  Press Ctrl+C to stop\n")

    from mission_control.app import create_app
    app = create_app()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
