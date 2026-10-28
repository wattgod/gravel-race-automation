"""Handbook charts, rebuilt (2026-10-28).

Each group module (ch1_ch2, ch3, ch4_ch5, ch6_ch7) exports:
  RENDERERS: {asset_id: render(block) -> str}  — overrides guide_infographics
  CSS: str                                      — appended to the guide stylesheet
  JS: str                                       — appended inside the guide script (runs once, DOM ready)
"""
from importlib import import_module

GROUPS = ("ch1_ch2", "ch3", "ch4_ch5", "ch6_ch7")

from guide_ig import glyph  # shared Endure Glyph kit: its CSS/JS lead the bundle

RENDERERS: dict = {}
CSS_PARTS: list[str] = [glyph.CSS]
JS_PARTS: list[str] = [glyph.JS]

for _name in GROUPS:
    try:
        _mod = import_module(f"guide_ig.{_name}")
    except ModuleNotFoundError as exc:
        if exc.name != f"guide_ig.{_name}":
            raise
        continue
    RENDERERS.update(getattr(_mod, "RENDERERS", {}))
    CSS_PARTS.append(getattr(_mod, "CSS", ""))
    JS_PARTS.append(getattr(_mod, "JS", ""))

CSS = "\n".join(p for p in CSS_PARTS if p)
JS = "\n".join(p for p in JS_PARTS if p)
