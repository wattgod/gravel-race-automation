"""
Step 8: Generate PDF

Converts HTML guide to PDF using Playwright (Chromium).
Adapted from Zwift Batcher/create_brutalist_pdf.py
"""

import os
from pathlib import Path


def generate_pdf(html_path: Path, pdf_path: Path):
    """Convert HTML guide to PDF using Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright not installed. Run: pip install playwright && playwright install chromium"
        )

    abs_html = os.path.abspath(html_path)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"file://{abs_html}")
        # Wait for fonts to load
        page.wait_for_load_state("networkidle")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={
                "top": "20mm",
                "bottom": "20mm",
                "left": "15mm",
                "right": "15mm",
            },
        )
        browser.close()
