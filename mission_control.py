#!/usr/bin/env python3
"""Gravel God Mission Control — Operations Dashboard.

Launch: python3 mission_control.py
Serves at http://0.0.0.0:8000 (or PORT env var)
"""

import os
import sys

import uvicorn

from mission_control.config import HOST, PORT


def main():
    print("=" * 60)
    print("  Gravel God — Mission Control")
    print("=" * 60)

    # Validate required env vars
    supabase_url = os.environ.get("SUPABASE_URL", "")
    if not supabase_url:
        print("\n  WARNING: SUPABASE_URL not set. Set environment variables:")
        print("    SUPABASE_URL, SUPABASE_SERVICE_KEY")
        print("  Continuing anyway for local development...\n")

    # Sync filesystem athletes into Supabase
    if supabase_url:
        print("\n[1/2] Syncing athletes from filesystem to Supabase...")
        try:
            from mission_control.sync import sync_all
            stats = sync_all()
            print(f"  -> {stats['athletes']} athletes synced")
            print(f"  -> {stats['touchpoints']} touchpoints loaded")
            if stats["skipped"]:
                print(f"  -> {stats['skipped']} directories skipped (no intake.json)")
        except Exception as e:
            print(f"  -> Sync failed: {e}")
            print("  -> Continuing without sync...")
    else:
        print("\n[1/2] Skipping sync (no Supabase connection)")

    # Start server
    print(f"[2/2] Starting server on {HOST}:{PORT}")
    url = f"http://{HOST}:{PORT}"
    print(f"\n  Dashboard: {url}")
    print("  Press Ctrl+C to stop\n")

    from mission_control.app import create_app
    app = create_app()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
