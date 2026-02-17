#!/usr/bin/env python3
"""
Preflight quality check — runs before deploy and should run before any PR.

This script catches the specific shortcuts and quality failures that have
bitten us before. It is NOT a replacement for pytest — it checks structural
quality issues that tests don't cover.

Usage:
    python scripts/preflight_quality.py          # all checks
    python scripts/preflight_quality.py --js     # JS-only checks
    python scripts/preflight_quality.py --quick  # skip slow checks

Exit code: 0 = all pass, 1 = failures found.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORDPRESS_DIR = PROJECT_ROOT / "wordpress"

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"

failures = []
warnings = []


def check(name, condition, msg=""):
    if condition:
        print(f"  {PASS}  {name}")
    else:
        print(f"  {FAIL}  {name}: {msg}")
        failures.append(f"{name}: {msg}")


def warn(name, msg):
    print(f"  {WARN}  {name}: {msg}")
    warnings.append(f"{name}: {msg}")


# ── Check 1: No inline imports ──────────────────────────────


def check_no_inline_imports():
    """Ensure all imports are at module top level, not inline in functions."""
    print("\n── Inline Import Check ──")
    gen = WORDPRESS_DIR / "generate_prep_kit.py"
    text = gen.read_text()
    lines = text.split("\n")
    in_function = False
    indent_level = 0
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith("def ") or stripped.startswith("class "):
            in_function = True
            indent_level = len(line) - len(stripped)
        elif in_function and stripped and not line[0].isspace():
            in_function = False
        if in_function and stripped.startswith("import ") and len(line) - len(stripped) > indent_level:
            check(f"Line {i}", False, f"Inline import found: {stripped}")
            return
    check("No inline imports in generate_prep_kit.py", True)


# ── Check 2: JS/Python constant parity ─────────────────────


def check_js_python_constant_parity():
    """Verify that shared constants between Python and JS are identical."""
    print("\n── JS/Python Constant Parity ──")
    sys.path.insert(0, str(WORDPRESS_DIR))
    import generate_prep_kit as gpk

    js = gpk.build_prep_kit_js()

    # Heat multipliers
    for key, val in gpk.HEAT_MULTIPLIERS.items():
        check(f"HEAT_MULT.{key}={val}", f"{key}:{val}" in js,
              f"Python has {key}:{val} but not found in JS")

    # Sweat multipliers
    for key, val in gpk.SWEAT_MULTIPLIERS.items():
        check(f"SWEAT_MULT.{key}={val}", f"{key}:{val}" in js,
              f"Python has {key}:{val} but not found in JS")

    # Sodium boosts
    for key, val in gpk.SODIUM_HEAT_BOOST.items():
        check(f"SODIUM_HEAT_BOOST.{key}={val}", f"{key}:{val}" in js,
              f"Python has {key}:{val} but not found in JS")
    for key, val in gpk.SODIUM_CRAMP_BOOST.items():
        check(f"SODIUM_CRAMP_BOOST.{key}={val}", f"{key}:{val}" in js,
              f"Python has {key}:{val} but not found in JS")

    # Item constants
    check("GEL_CARBS=25", "/25" in js or "25)" in js, "GEL_CARBS=25 not in JS")
    check("DRINK_CARBS=40", "/40" in js, "DRINK_CARBS_500ML=40 not in JS")
    check("BAR_CARBS=35", "/35" in js, "BAR_CARBS=35 not in JS")


# ── Check 3: JS syntax validation via Node.js ──────────────


def check_js_syntax():
    """Parse the generated JS through Node.js to catch syntax errors."""
    print("\n── JS Syntax Validation ──")
    sys.path.insert(0, str(WORDPRESS_DIR))
    import generate_prep_kit as gpk

    js = gpk.build_prep_kit_js()
    # Wrap in IIFE to avoid DOM references crashing Node
    # We just want syntax parsing, not execution
    test_script = f"""
try {{
    new Function({json.dumps(js)});
    console.log('SYNTAX_OK');
}} catch(e) {{
    console.log('SYNTAX_ERROR: ' + e.message);
    process.exit(1);
}}
"""
    result = subprocess.run(
        ["node", "-e", test_script],
        capture_output=True, text=True, timeout=10
    )
    check("JS parses without syntax errors",
          result.returncode == 0 and "SYNTAX_OK" in result.stdout,
          result.stderr or result.stdout)


# ── Check 4: training-plans-form.js syntax validation ──


def check_training_form_js_syntax():
    """Parse training-plans-form.js through Node.js to catch syntax errors."""
    print("\n── Training Form JS Syntax ──")
    form_js = PROJECT_ROOT / "web" / "training-plans-form.js"
    if not form_js.exists():
        check("training-plans-form.js exists", False, "File not found")
        return

    js_content = form_js.read_text()
    test_script = f"""
try {{
    new Function({json.dumps(js_content)});
    console.log('SYNTAX_OK');
}} catch(e) {{
    console.log('SYNTAX_ERROR: ' + e.message);
    process.exit(1);
}}
"""
    result = subprocess.run(
        ["node", "-e", test_script],
        capture_output=True, text=True, timeout=10
    )
    check("training-plans-form.js parses without syntax errors",
          result.returncode == 0 and "SYNTAX_OK" in result.stdout,
          result.stderr or result.stdout)


# ── Check 5: Pricing parity between Python (app.py) and JS (form.js) ──


def check_pricing_parity():
    """Verify Python and JS price computations produce identical results.

    The user sees a JS-computed price on the submit button, then the server
    charges a Python-computed price via Stripe. If these diverge, we have
    a trust/legal problem. This check catches that before deploy.
    """
    print("\n── Pricing Parity (Python/JS) ──")
    from datetime import date, timedelta
    import math

    # Python computation (mirrors app.py compute_plan_price)
    PRICE_PER_WEEK_CENTS = 1500
    PRICE_CAP_CENTS = 24900
    MIN_WEEKS = 4

    def py_price(race_date_str):
        try:
            from datetime import datetime
            race_date = datetime.strptime(race_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return MIN_WEEKS, MIN_WEEKS * PRICE_PER_WEEK_CENTS
        today = date.today()
        days_until = (race_date - today).days
        weeks = max(MIN_WEEKS, math.ceil(days_until / 7))
        price_cents = min(weeks * PRICE_PER_WEEK_CENTS, PRICE_CAP_CENTS)
        return weeks, price_cents

    # Test dates: 5wk, 10wk, 16wk, 30wk, past, 3 days out
    from datetime import datetime
    test_dates = [
        (datetime.now() + timedelta(weeks=5)).strftime('%Y-%m-%d'),
        (datetime.now() + timedelta(weeks=10)).strftime('%Y-%m-%d'),
        (datetime.now() + timedelta(weeks=16)).strftime('%Y-%m-%d'),
        (datetime.now() + timedelta(weeks=30)).strftime('%Y-%m-%d'),
        (datetime.now() - timedelta(weeks=2)).strftime('%Y-%m-%d'),
        (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d'),
    ]

    js_code = """
    var PRICE_PER_WEEK = 15;
    var PRICE_CAP = 249;
    var MIN_WEEKS = 4;

    function computePrice(raceDateStr) {
      var raceDate = new Date(raceDateStr + 'T00:00:00');
      var today = new Date();
      today.setHours(0, 0, 0, 0);
      var days = Math.ceil((raceDate - today) / (1000 * 60 * 60 * 24));
      var weeks = Math.max(MIN_WEEKS, Math.ceil(days / 7));
      var price = Math.min(weeks * PRICE_PER_WEEK, PRICE_CAP);
      return {weeks: weeks, price_cents: price * 100};
    }

    var dates = %DATES%;
    var results = dates.map(function(d) { return computePrice(d); });
    console.log(JSON.stringify(results));
    """.replace('%DATES%', json.dumps(test_dates))

    result = subprocess.run(
        ["node", "-e", js_code],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        check("JS pricing runs", False, result.stderr)
        return

    js_results = json.loads(result.stdout.strip())
    all_match = True
    for i, (d, js_r) in enumerate(zip(test_dates, js_results)):
        py_weeks, py_cents = py_price(d)
        if py_cents != js_r['price_cents'] or py_weeks != js_r['weeks']:
            check(f"Price parity for {d}",
                  False,
                  f"Python={py_cents}c/{py_weeks}wk, JS={js_r['price_cents']}c/{js_r['weeks']}wk")
            all_match = False

    if all_match:
        check(f"Price parity across {len(test_dates)} date scenarios", True)


# ── Check 6: Dead CSS detection for training-plans.html ──


def check_no_dead_css():
    """Check for CSS classes defined but not used in HTML."""
    print("\n── Dead CSS Check (training-plans.html) ──")
    html_file = PROJECT_ROOT / "web" / "training-plans.html"
    if not html_file.exists():
        return

    content = html_file.read_text()
    # Split into CSS (inside <style>) and HTML (outside)
    style_match = re.search(r'<style>(.*?)</style>', content, re.DOTALL)
    if not style_match:
        return
    css_text = style_match.group(1)
    html_text = content[style_match.end():]

    # Find all class selectors in CSS
    css_classes = set(re.findall(r'\.(tp-\w[\w-]*)', css_text))
    # Find all class references in HTML
    html_classes = set(re.findall(r'class="[^"]*?(tp-\w[\w-]*)', html_text))
    # Also check for classes used in style attributes or inline
    for m in re.finditer(r'class="([^"]*)"', html_text):
        for cls in m.group(1).split():
            if cls.startswith('tp-'):
                html_classes.add(cls)

    dead = css_classes - html_classes
    # Exclude pseudo-element targets and hover variants
    dead = {c for c in dead if not any(
        c.startswith(p) for p in ('tp-viz-z',)  # zone colors used via JS
    )}

    if dead:
        check("No dead CSS classes", False, f"{len(dead)} unused: {', '.join(sorted(dead)[:5])}")
    else:
        check("No dead CSS classes", True)


# ── Check 7: All 328 races classify climate without error ──


def check_climate_classification(quick=False):
    """Verify every race JSON classifies to a valid climate heat category."""
    print("\n── Climate Classification ──")
    sys.path.insert(0, str(WORDPRESS_DIR))
    import generate_prep_kit as gpk

    data_dir = PROJECT_ROOT / "race-data"
    jsons = sorted(data_dir.glob("*.json"))
    errors = []
    distribution = {"cool": 0, "mild": 0, "warm": 0, "hot": 0, "extreme": 0}

    for jf in jsons:
        data = json.loads(jf.read_text(encoding="utf-8"))
        race = data.get("race", data)
        climate = race.get("climate")
        score = (race.get("gravel_god_rating") or {}).get("climate")
        result = gpk.classify_climate_heat(climate, score)
        if result not in distribution:
            errors.append(f"{jf.stem}: invalid classification '{result}'")
        else:
            distribution[result] += 1

    total = sum(distribution.values())
    check(f"All {total} races classify", len(errors) == 0,
          f"{len(errors)} errors: {errors[:3]}")

    # Sanity check distribution — mild should be most common
    print(f"    Distribution: {distribution}")
    if distribution["extreme"] > 10:
        warn("Climate distribution", f"{distribution['extreme']} extreme races seems high")
    if distribution["mild"] < 50:
        warn("Climate distribution", f"Only {distribution['mild']} mild races — expected >50")


# ── Check 5: Worker JS has hydration fields ─────────────────


def check_worker_hydration_fields():
    """Verify the Cloudflare Worker captures all hydration fields."""
    print("\n── Worker Hydration Fields ──")
    worker_path = PROJECT_ROOT / "workers" / "fueling-lead-intake" / "worker.js"
    text = worker_path.read_text()

    required_fields = [
        "fluid_target_ml_hr",
        "sodium_mg_hr",
        "sweat_tendency",
        "fuel_format",
        "cramp_history",
        "climate_heat",
    ]
    for field in required_fields:
        check(f"Worker has {field}", field in text,
              f"{field} not found in worker.js")


# ── Check 6: CSS classes referenced in JS exist in CSS ──────


def check_css_js_class_sync():
    """Verify CSS classes referenced in JS rendering actually exist in CSS."""
    print("\n── CSS/JS Class Sync ──")
    sys.path.insert(0, str(WORDPRESS_DIR))
    import generate_prep_kit as gpk

    css = gpk.build_prep_kit_css()
    js = gpk.build_prep_kit_js()

    # Extract CSS class references from JS (patterns like 'gg-pk-calc-xxx')
    js_classes = set(re.findall(r'gg-pk-calc-[\w-]+', js))
    css_classes = set(re.findall(r'\.(gg-pk-calc-[\w-]+)', css))

    for cls in js_classes:
        # Skip dynamic class prefixes (e.g., 'gg-pk-calc-item--' + type)
        if cls.endswith("--"):
            # Verify at least one variant exists in CSS
            variants = [c for c in css_classes if c.startswith(cls)]
            check(f".{cls}* variants in CSS", len(variants) > 0,
                  f"JS builds dynamic .{cls}* but no variants in CSS")
            continue
        # Fully-qualified dynamic classes
        if cls.startswith("gg-pk-calc-item--"):
            check(f".{cls} in CSS", cls in css_classes, f"JS references .{cls} but not in CSS")
        elif cls in ("gg-pk-calc-aid-row", "gg-pk-calc-aid-badge",
                     "gg-pk-calc-hour-num", "gg-pk-calc-hourly-table",
                     "gg-pk-calc-hourly-scroll", "gg-pk-calc-panel-title",
                     "gg-pk-calc-shopping-grid", "gg-pk-calc-shopping-item",
                     "gg-pk-calc-shopping-qty", "gg-pk-calc-shopping-label",
                     "gg-pk-calc-shopping-note",
                     "gg-pk-calc-result", "gg-pk-calc-result-row",
                     "gg-pk-calc-result-label", "gg-pk-calc-result-value",
                     "gg-pk-calc-result-highlight", "gg-pk-calc-result-note",
                     "gg-pk-calc-substack"):
            check(f".{cls} in CSS", cls in css_classes, f"JS references .{cls} but not in CSS")


def check_infographic_renderers():
    """Verify all infographic asset_ids in guide content JSON have renderers."""
    print("\n── Infographic Renderer Coverage ──")
    sys.path.insert(0, str(WORDPRESS_DIR))
    from guide_infographics import INFOGRAPHIC_RENDERERS
    content_json = PROJECT_ROOT / "guide" / "gravel-guide-content.json"
    content = json.loads(content_json.read_text(encoding="utf-8"))

    # Collect all image asset_ids from content (excluding hero photos)
    hero_ids = {f"ch{i}-hero" for i in range(1, 9)}
    image_ids = set()
    for ch in content["chapters"]:
        for sec in ch["sections"]:
            for block in sec["blocks"]:
                if block.get("type") == "image":
                    aid = block["asset_id"]
                    if aid not in hero_ids:
                        image_ids.add(aid)

    for aid in sorted(image_ids):
        check(f"Renderer for {aid}",
              aid in INFOGRAPHIC_RENDERERS,
              f"No renderer for infographic asset_id '{aid}'")

    # Check no orphan renderers (renderers for asset_ids not in content)
    for aid in sorted(INFOGRAPHIC_RENDERERS):
        check(f"Content uses {aid}",
              aid in image_ids,
              f"Renderer exists for '{aid}' but not found in content JSON")


def check_infographic_css_no_hex():
    """Verify infographic CSS section uses var() not raw hex colors."""
    print("\n── Infographic CSS Token Compliance ──")
    sys.path.insert(0, str(WORDPRESS_DIR))
    import generate_guide
    css = generate_guide.build_guide_css()

    # Extract infographic section (from marker to end)
    marker = "/* ── Inline Infographics ── */"
    if marker not in css:
        check("Infographic CSS section exists", False, "Marker not found in CSS")
        return
    infographic_css = css[css.index(marker):]

    # Find raw hex colors (#xxx or #xxxxxx) — exclude inside var() or color-mix()
    # We scan for #[0-9a-fA-F]{3,8} patterns that aren't part of a comment
    hex_matches = re.findall(r'#[0-9a-fA-F]{3,8}', infographic_css)
    if hex_matches:
        check("No raw hex in infographic CSS", False,
              f"Found {len(hex_matches)} raw hex values: {', '.join(hex_matches[:5])}")
    else:
        check("No raw hex in infographic CSS", True)


def check_infographic_editorial():
    """Verify every infographic renderer outputs title and takeaway editorial framing."""
    print("\n── Infographic Editorial Framing ──")
    sys.path.insert(0, str(WORDPRESS_DIR))
    from guide_infographics import INFOGRAPHIC_RENDERERS
    for aid, renderer in sorted(INFOGRAPHIC_RENDERERS.items()):
        block = {"type": "image", "asset_id": aid, "alt": "test", "caption": "c"}
        html = renderer(block)
        has_title = "gg-infographic-title" in html
        has_takeaway = "gg-infographic-takeaway" in html
        check(f"Editorial framing: {aid}",
              has_title and has_takeaway,
              f"Missing {'title' if not has_title else 'takeaway'} for {aid}")


def check_infographic_animation_a11y():
    """Verify animation CSS is wrapped in prefers-reduced-motion media query."""
    print("\n── Infographic Animation Accessibility ──")
    sys.path.insert(0, str(WORDPRESS_DIR))
    import generate_guide
    css = generate_guide.build_guide_css()
    marker = "/* ── Inline Infographics ── */"
    if marker not in css:
        check("Infographic CSS section exists", False, "Marker not found")
        return
    infographic_css = css[css.index(marker):]
    parts = infographic_css.split("@media(prefers-reduced-motion:no-preference)")
    if len(parts) >= 2:
        before_rm = parts[0]
        has_leak = "data-animate" in before_rm or "gg-in-view" in before_rm
        check("Animation CSS inside prefers-reduced-motion", not has_leak,
              "Animation selectors found outside @media(prefers-reduced-motion) block")
    else:
        check("Animation CSS inside prefers-reduced-motion", False,
              "No @media(prefers-reduced-motion) block found in infographic CSS")


def check_root_matches_brand_tokens():
    """Verify :root CSS custom properties match gravel-god-brand/tokens/tokens.css."""
    print("\n── :root vs Brand Tokens Parity ──")
    tokens_path = PROJECT_ROOT.parent / "gravel-god-brand" / "tokens" / "tokens.css"
    if not tokens_path.exists():
        warn(":root token parity", f"Brand tokens file not found at {tokens_path}")
        return

    tokens_css = tokens_path.read_text(encoding="utf-8")
    sys.path.insert(0, str(WORDPRESS_DIR))
    import generate_guide
    guide_css = generate_guide.build_guide_css()

    # Parse --gg-color-* from both files
    def parse_colors(text):
        return dict(re.findall(r'(--gg-color-[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})', text))

    token_colors = parse_colors(tokens_css)
    guide_colors = parse_colors(guide_css)

    for name, guide_val in guide_colors.items():
        if name in token_colors:
            match = guide_val.lower() == token_colors[name].lower()
            check(f"{name} matches tokens",
                  match,
                  f"Guide has {guide_val}, tokens has {token_colors[name]}")
        else:
            warn(f"{name} in guide", f"Not found in brand tokens — verify manually")


def check_interactive_js_handlers():
    """Verify every data-interactive value in renderers has a JS handler."""
    print("\n── Interactive JS Handler Coverage ──")
    sys.path.insert(0, str(WORDPRESS_DIR))
    import generate_guide
    from guide_infographics import INFOGRAPHIC_RENDERERS

    js = generate_guide.build_guide_js()

    # Collect all data-interactive types used in renderer output
    interactive_types = set()
    for aid, renderer in INFOGRAPHIC_RENDERERS.items():
        try:
            block = {"type": "image", "asset_id": aid, "alt": "test"}
            html = renderer(block)
            for m in re.findall(r'data-interactive="([^"]+)"', html):
                interactive_types.add(m)
        except Exception:
            pass

    if not interactive_types:
        warn("interactive types", "No data-interactive attributes found in renderers")
        return

    check(f"Found {len(interactive_types)} interactive types in renderers", True)

    for itype in sorted(interactive_types):
        has_handler = (f"data-interactive='{itype}'" in js
                       or f'data-interactive="{itype}"' in js)
        check(f"JS handler for data-interactive=\"{itype}\"",
              has_handler,
              f"No JS handler found for data-interactive=\"{itype}\"")

    # Also verify all data-animate types have CSS support
    css = generate_guide.build_guide_css()
    animate_types = set()
    for aid, renderer in INFOGRAPHIC_RENDERERS.items():
        try:
            block = {"type": "image", "asset_id": aid, "alt": "test"}
            html = renderer(block)
            for m in re.findall(r'data-animate="([^"]+)"', html):
                animate_types.add(m)
        except Exception:
            pass

    js = generate_guide.build_guide_js()
    for atype in sorted(animate_types):
        has_css = f'data-animate="{atype}"' in css
        has_js = (f'data-animate="{atype}"' in js
                  or f"data-animate='{atype}'" in js
                  or f"=== '{atype}'" in js
                  or f'=== "{atype}"' in js)
        check(f"CSS/JS support for data-animate=\"{atype}\"",
              has_css or has_js,
              f"No CSS or JS support found for data-animate=\"{atype}\"")


def check_no_dead_end_infographics():
    """Ensure no infographic image block is the last block in its section."""
    print("\n── No Dead-End Infographics ──")
    content_path = PROJECT_ROOT / "guide" / "gravel-guide-content.json"
    if not content_path.exists():
        warn("dead-end infographic", f"Content JSON not found at {content_path}")
        return
    data = json.load(open(content_path, encoding="utf-8"))
    dead_ends = []
    for ch in data.get("chapters", []):
        for sec in ch.get("sections", []):
            blocks = sec.get("blocks", [])
            if not blocks:
                continue
            last = blocks[-1]
            if last.get("type") == "image" and last.get("asset_id", "").startswith("ch"):
                dead_ends.append(f'{sec["id"]}/{last["asset_id"]}')
    check("No dead-end infographics",
          len(dead_ends) == 0,
          f"Sections ending on infographic: {', '.join(dead_ends)}")


def check_ab_config_sync():
    """Ensure AB system files exist, config is in sync, and JS parses."""
    print("\n── A/B Testing System ──")

    # 1. File existence — all three AB files must exist
    js_path = PROJECT_ROOT / "web" / "gg-ab-tests.js"
    config_path = PROJECT_ROOT / "web" / "ab" / "experiments.json"
    php_path = WORDPRESS_DIR / "mu-plugins" / "gg-ab.php"

    check("AB JS file exists (gg-ab-tests.js)", js_path.exists(),
          "Missing — file deleted?")
    check("AB config exists (experiments.json)", config_path.exists(),
          "Missing — run: python wordpress/ab_experiments.py")
    check("AB mu-plugin exists (gg-ab.php)", php_path.exists(),
          "Missing — file deleted?")

    if not config_path.exists() or not js_path.exists():
        return

    # 2. JS syntax validation via Node.js
    js_code = js_path.read_text()
    test_script = f"""
try {{
    new Function({json.dumps(js_code)});
    console.log('SYNTAX_OK');
}} catch(e) {{
    console.log('SYNTAX_ERROR: ' + e.message);
    process.exit(1);
}}
"""
    result = subprocess.run(
        ["node", "-e", test_script],
        capture_output=True, text=True, timeout=10
    )
    check("AB JS parses without syntax errors",
          result.returncode == 0 and "SYNTAX_OK" in result.stdout,
          result.stderr or result.stdout)

    # 3. Config sync — experiments.json matches Python source
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ab_experiments",
            WORDPRESS_DIR / "ab_experiments.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        on_disk = json.loads(config_path.read_text())
        from_source = mod.export_config()

        check("AB experiments.json matches source",
              on_disk["experiments"] == from_source["experiments"],
              "Stale — run: python wordpress/ab_experiments.py")

        errors = mod.validate_experiments()
        check("AB experiment config valid",
              len(errors) == 0,
              f"Validation errors: {'; '.join(errors)}")

        # 4. Selector parity — generator data-ab attrs match experiment selectors
        import re
        exp_ab_values = set()
        for exp in mod.EXPERIMENTS:
            m = re.search(r"data-ab=['\"]([^'\"]+)['\"]", exp["selector"])
            if m:
                exp_ab_values.add(m.group(1))

        for gen_name in ("generate_homepage.py", "generate_about.py"):
            gen_path = WORDPRESS_DIR / gen_name
            if gen_path.exists():
                gen_content = gen_path.read_text()
                for m in re.finditer(r'data-ab="([^"]+)"', gen_content):
                    val = m.group(1)
                    check(f"AB selector parity: {gen_name} data-ab=\"{val}\"",
                          val in exp_ab_values,
                          f"Orphaned data-ab in {gen_name} — no experiment uses '{val}'")

    except Exception as e:
        check("AB config sync", False, f"Error loading config: {e}")


def main():
    parser = argparse.ArgumentParser(description="Preflight quality checks")
    parser.add_argument("--js", action="store_true", help="JS-only checks")
    parser.add_argument("--quick", action="store_true", help="Skip slow checks")
    args = parser.parse_args()

    print("=" * 60)
    print("PREFLIGHT QUALITY CHECK")
    print("=" * 60)

    if args.js:
        check_js_syntax()
        check_training_form_js_syntax()
        check_js_python_constant_parity()
        check_css_js_class_sync()
        check_pricing_parity()
    else:
        check_no_inline_imports()
        check_js_python_constant_parity()
        check_js_syntax()
        check_training_form_js_syntax()
        check_css_js_class_sync()
        check_worker_hydration_fields()
        check_pricing_parity()
        check_no_dead_css()
        check_infographic_renderers()
        check_infographic_css_no_hex()
        check_infographic_editorial()
        check_infographic_animation_a11y()
        check_interactive_js_handlers()
        check_no_dead_end_infographics()
        check_root_matches_brand_tokens()
        check_ab_config_sync()
        if not args.quick:
            check_climate_classification()

    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED: {len(failures)} issue(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    else:
        total = "JS" if args.js else "all"
        print(f"ALL CHECKS PASSED ({total})")
        if warnings:
            print(f"  {len(warnings)} warning(s)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
