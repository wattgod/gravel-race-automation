"""
Step 8: Generate PDF

Converts HTML guide to PDF using Playwright (Chromium).

Print styling lives in pipeline/print.css and is injected at render time.
This means print CSS changes only require re-running step 8 — never step 7.
"""

import os
from pathlib import Path

PRINT_CSS = Path(__file__).parent / "print.css"


def generate_pdf(html_path: Path, pdf_path: Path):
    """Convert HTML guide to PDF using Playwright.

    Injects pipeline/print.css at render time so print styling
    is decoupled from guide content generation (step 7).
    """
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
        page.wait_for_load_state("networkidle")

        # Inject print stylesheet — owned by step 8, not step 7
        if PRINT_CSS.exists():
            page.add_style_tag(content=PRINT_CSS.read_text())

        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={
                "top": "15mm",
                "bottom": "15mm",
                "left": "15mm",
                "right": "15mm",
            },
        )
        browser.close()
