"""Generate Mission Control dashboard — internal ops page for Gravel God.

Bakes all data at generation time from local files. No server dependency,
no API calls, zero hosting cost. Deployed to /mission-control/ (noindex).
"""
from __future__ import annotations

import argparse
import html
import json
import subprocess
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from brand_tokens import get_preload_hints, get_tokens_css
from generate_neo_brutalist import (
    SITE_BASE_URL,
    get_page_css,
    write_shared_assets,
)

OUTPUT_DIR = Path(__file__).parent / "output"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CURRENT_DATE = date.today()


def esc(text) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


# ── Data Collectors ──────────────────────────────────────────────


def collect_health_overview() -> dict:
    """Race count, test status, quality gates."""
    try:
        race_dir = PROJECT_ROOT / "race-data"
        race_count = len(list(race_dir.glob("*.json"))) if race_dir.exists() else 0

        # Try to get test results from last pytest run
        test_pass = 0
        test_fail = 0
        test_error = 0
        test_ran = False

        # Quality gates — check if scripts exist
        gates = {}
        gate_scripts = {
            "PREFLIGHT": "scripts/preflight_quality.py",
            "COLORS": "scripts/audit_colors.py",
            "CITATIONS": "scripts/validate_citations.py",
            "BLOG": "scripts/validate_blog_content.py",
        }
        for label, script in gate_scripts.items():
            gates[label] = (PROJECT_ROOT / script).exists()

        # Health score: simple heuristic based on what we can detect locally
        # 100 = everything looks good, lower = issues detected
        score = 100
        if race_count < 300:
            score -= 20
        # We can't run tests at generation time, so score is data-based
        # Deductions happen from stale data (handled by caller if needed)

        return {
            "race_count": race_count,
            "test_pass": test_pass,
            "test_fail": test_fail,
            "test_error": test_error,
            "test_ran": test_ran,
            "gates": gates,
            "health_score": score,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        return {"error": str(e)}


def collect_data_freshness() -> dict:
    """Stale dates, tiers, gaps from race-data/*.json."""
    try:
        race_dir = PROJECT_ROOT / "race-data"
        if not race_dir.exists():
            return {"error": "race-data/ not found"}

        total = 0
        current_dates = 0
        stale_dates = 0
        tbd_dates = 0
        stubs = 0
        missing_coords = 0
        tier_counts: Counter = Counter()
        stale_races: list[dict] = []

        for f in sorted(race_dir.glob("*.json")):
            try:
                with open(f) as fp:
                    data = json.load(fp)
            except (json.JSONDecodeError, OSError):
                continue

            total += 1
            race = data.get("race", {})
            gg = race.get("gravel_god_rating", {})
            tier = gg.get("display_tier") or gg.get("tier")

            if tier:
                tier_counts[tier] += 1

            # Check date
            race_date = race.get("date")
            if not race_date or race_date == "TBD":
                tbd_dates += 1
            elif "2026" in str(race_date):
                current_dates += 1
            else:
                stale_dates += 1
                stale_races.append({
                    "slug": f.stem,
                    "name": race.get("name", f.stem),
                    "date": str(race_date),
                    "tier": tier or "?",
                })

            # Stubs
            fv = gg.get("final_verdict", {})
            if not fv.get("course_description"):
                stubs += 1

            # Coords
            loc = race.get("location", {})
            if not loc.get("lat") or not loc.get("lng"):
                missing_coords += 1

        # Sort stale races by tier (T1 first)
        tier_order = {"T1": 0, "T2": 1, "T3": 2, "T4": 3, "?": 4}
        stale_races.sort(key=lambda r: tier_order.get(r["tier"], 4))

        return {
            "total": total,
            "current_dates": current_dates,
            "stale_dates": stale_dates,
            "tbd_dates": tbd_dates,
            "stubs": stubs,
            "missing_coords": missing_coords,
            "tier_counts": dict(sorted(tier_counts.items())),
            "stale_races": stale_races[:15],
        }
    except Exception as e:
        return {"error": str(e)}


def collect_content_pipeline() -> dict:
    """Auto-discover generators and count outputs."""
    try:
        wp_dir = PROJECT_ROOT / "wordpress"
        generators = sorted(wp_dir.glob("generate_*.py"))
        gen_names = [g.stem.replace("generate_", "") for g in generators]

        # Count outputs for known multi-output generators
        output_dir = wp_dir / "output"
        output_counts: dict[str, dict] = {}

        # Map generator names to their output patterns
        output_patterns = {
            "neo_brutalist": ("race/*/index.html", "Race profiles"),
            "prep_kit": ("prep-kit/*/index.html", "Prep kits"),
            "blog_preview": ("blog/*/index.html", "Blog previews"),
            "race_recap": ("blog/*/index.html", "Race recaps"),
            "season_roundup": ("blog/*/index.html", "Season roundups"),
            "series_hubs": ("race/series/*/index.html", "Series hubs"),
            "homepage": ("homepage.html", "Homepage"),
            "about": ("about.html", "About page"),
            "coaching": ("coaching.html", "Coaching page"),
            "coaching_apply": ("coaching-apply.html", "Coaching apply"),
            "consulting": ("consulting.html", "Consulting page"),
            "methodology": ("methodology.html", "Methodology page"),
            "guide": ("guide/index.html", "Training guide"),
            "success_pages": ("*-success.html", "Success pages"),
            "blog_index_page": ("blog-index.html", "Blog index"),
            "courses": ("course/*/index.html", "Course pages"),
            "calendar": ("calendar.html", "Calendar"),
            "quiz": ("quiz.html", "Quiz"),
            "vs_pages": ("vs/*/index.html", "VS pages"),
            "tier_hubs": ("tier/*/index.html", "Tier hubs"),
            "state_hubs": ("state/*/index.html", "State hubs"),
            "power_rankings": ("power-rankings.html", "Power rankings"),
            "tire_guide": ("tire-guide.html", "Tire guide"),
            "tire_pages": ("tires/*/index.html", "Tire pages"),
            "tire_vs_pages": ("tires/vs/*/index.html", "Tire VS pages"),
            "admin_dashboard": ("admin-dashboard.html", "Admin dashboard"),
        }

        for gen_name in gen_names:
            if gen_name in output_patterns:
                pattern, label = output_patterns[gen_name]
                matches = list(output_dir.glob(pattern)) if output_dir.exists() else []
                output_counts[gen_name] = {
                    "label": label,
                    "count": len(matches),
                    "pattern": pattern,
                }
            else:
                output_counts[gen_name] = {
                    "label": gen_name.replace("_", " ").title(),
                    "count": 0,
                    "pattern": "?",
                }

        return {
            "total_generators": len(generators),
            "generators": gen_names,
            "output_counts": output_counts,
        }
    except Exception as e:
        return {"error": str(e)}


def collect_deploy_targets() -> dict:
    """Parse push_wordpress.py for --sync-* flags."""
    try:
        push_script = PROJECT_ROOT / "scripts" / "push_wordpress.py"
        if not push_script.exists():
            return {"error": "push_wordpress.py not found"}

        source = push_script.read_text(encoding="utf-8")

        # Extract --sync-* flags from argparse add_argument calls
        import re
        sync_flags = re.findall(r'"(--sync-[\w-]+)"', source)
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_flags: list[str] = []
        for f in sync_flags:
            if f not in seen:
                seen.add(f)
                unique_flags.append(f)

        # Categorize
        content_flags = [
            "--sync-pages", "--sync-homepage", "--sync-about",
            "--sync-coaching", "--sync-coaching-apply", "--sync-consulting",
            "--sync-success", "--sync-prep-kits", "--sync-series",
            "--sync-guide", "--sync-courses",
        ]
        data_flags = [
            "--sync-index", "--sync-widget", "--sync-training",
            "--sync-blog-index", "--sync-sitemap",
        ]
        asset_flags = [
            "--sync-og", "--sync-photos", "--sync-ab",
            "--sync-blog",
        ]
        infra_flags = [
            "--sync-redirects", "--sync-noindex", "--sync-ctas",
            "--sync-ga4", "--sync-header",
        ]

        categorized = {
            "Content": [f for f in unique_flags if f in content_flags],
            "Data": [f for f in unique_flags if f in data_flags],
            "Assets": [f for f in unique_flags if f in asset_flags],
            "Infra": [f for f in unique_flags if f in infra_flags],
        }

        # Catch any uncategorized
        all_categorized = set()
        for flags in categorized.values():
            all_categorized.update(flags)
        uncategorized = [f for f in unique_flags if f not in all_categorized]
        if uncategorized:
            categorized["Other"] = uncategorized

        return {
            "total": len(unique_flags),
            "flags": unique_flags,
            "categorized": categorized,
        }
    except Exception as e:
        return {"error": str(e)}


def collect_seo_pulse() -> dict:
    """Latest GSC snapshot data."""
    try:
        snapshot_dir = PROJECT_ROOT / "data" / "gsc-snapshots"
        if not snapshot_dir.exists() or not list(snapshot_dir.glob("*.json")):
            return {"configured": False}

        # Get latest snapshot
        snapshots = sorted(snapshot_dir.glob("*.json"))
        latest = snapshots[-1]
        with open(latest) as f:
            data = json.load(f)

        return {
            "configured": True,
            "snapshot_date": latest.stem,
            "clicks": data.get("totals", {}).get("clicks", 0),
            "impressions": data.get("totals", {}).get("impressions", 0),
            "ctr": data.get("totals", {}).get("ctr", 0),
            "position": data.get("totals", {}).get("position", 0),
            "top_queries": data.get("top_queries", [])[:10],
            "top_pages": data.get("top_pages", [])[:10],
        }
    except Exception as e:
        return {"error": str(e)}


def collect_quick_commands() -> dict:
    """Hardcoded command reference."""
    return {
        "Generate": [
            ("python wordpress/generate_neo_brutalist.py --all", "Regenerate all 328 race profiles"),
            ("python wordpress/generate_prep_kit.py --all", "Regenerate all 328 prep kits"),
            ("python wordpress/generate_homepage.py", "Regenerate homepage"),
            ("python wordpress/generate_about.py", "Regenerate about page"),
            ("python wordpress/generate_coaching.py", "Regenerate coaching page"),
            ("python wordpress/generate_consulting.py", "Regenerate consulting page"),
            ("python wordpress/generate_mission_control.py", "Regenerate this dashboard"),
            ("python scripts/generate_index.py --with-jsonld", "Regenerate race index + JSON-LD"),
        ],
        "Deploy": [
            ("python3 scripts/push_wordpress.py --deploy-content", "Deploy pages + index + widget + cache"),
            ("python3 scripts/push_wordpress.py --deploy-all", "Deploy everything + purge cache"),
            ("python3 scripts/push_wordpress.py --sync-homepage --purge-cache", "Deploy homepage"),
            ("python3 scripts/push_wordpress.py --sync-about --purge-cache", "Deploy about page"),
            ("python3 scripts/push_wordpress.py --sync-coaching --purge-cache", "Deploy coaching page"),
            ("python3 scripts/push_wordpress.py --sync-mission-control --purge-cache", "Deploy this dashboard"),
        ],
        "Validate": [
            ("pytest", "Run all tests"),
            ("python scripts/preflight_quality.py", "Run preflight quality checks"),
            ("python scripts/audit_colors.py", "Audit WCAG color contrast"),
            ("python scripts/validate_citations.py", "Validate citation quality"),
            ("python scripts/validate_blog_content.py", "Validate blog content"),
            ("python scripts/validate_deploy.py", "Post-deploy validation (78 checks)"),
            ("python scripts/audit_fabricated_claims.py", "Audit fabricated claims"),
        ],
        "Data": [
            ("python scripts/batch_date_search.py --dry-run", "Search for 2026 race dates (dry run)"),
            ("python scripts/extract_metadata.py", "Extract metadata from research dumps"),
            ("python scripts/geocode_races.py", "Geocode missing lat/lng"),
            ("python scripts/recalculate_tiers.py", "Recalculate tiers from scores"),
            ("python scripts/audit_race_data.py", "Audit race data quality"),
            ("python scripts/audit_date_freshness.py", "Audit date freshness"),
        ],
    }


def collect_sprint_log() -> dict:
    """Recent sprints and remaining work (hardcoded from MEMORY.md)."""
    return {
        "recent_sprints": [
            {
                "number": 38,
                "title": "Coaching Landing Page + Intake Form",
                "items": [
                    "Coaching page (/coaching/, 10 sections)",
                    "Athlete intake form (/coaching/apply/, 12 sections)",
                    "Fixed dead wattgod.com/apply links across 986 pages",
                    "112 new tests",
                ],
            },
            {
                "number": 37,
                "title": "Data Freshness + Saved Filters + GSC Tracker",
                "items": [
                    "5 races updated to 2026 dates",
                    "Saved filter configs (viewMode/favorites/compare)",
                    "GSC tracker script",
                    "WP performance audit script",
                ],
            },
            {
                "number": 36,
                "title": "Training Plan Checkout",
                "items": [
                    "Stripe integration ($15/wk pricing)",
                    "Webhook pipeline on Railway",
                    "Success pages deployed",
                ],
            },
        ],
        "remaining_work": [
            "7 profiles with TBD dates (genuinely undateable)",
            "33 profiles with stale 2025 dates",
            "1 stub profile (gravel-grit-n-grind)",
            "GSC monitoring needs GOOGLE_APPLICATION_CREDENTIALS",
            "Race photos v2 needs fresh GOOGLE_AI_API_KEY",
            "Stripe SMTP needs Gmail App Password on Railway",
        ],
    }


# ── Section Builders ─────────────────────────────────────────────


def build_health_hero(data: dict) -> str:
    """Dark hero banner with health score and quality gates."""
    if data.get("error"):
        return f'<section class="gg-mc-hero"><p class="gg-mc-error">Error: {esc(data["error"])}</p></section>'

    score = data.get("health_score", 0)
    race_count = data.get("race_count", 0)
    generated = data.get("generated_at", "?")

    gates_html = ""
    for label, exists in data.get("gates", {}).items():
        status_cls = "gg-mc-gate-ok" if exists else "gg-mc-gate-missing"
        gates_html += f'<span class="gg-mc-gate {status_cls}">{esc(label)}</span>\n'

    test_line = ""
    if data.get("test_ran"):
        tp = data.get("test_pass", 0)
        tf = data.get("test_fail", 0)
        te = data.get("test_error", 0)
        test_line = f'<span class="gg-mc-stat">{tp} pass / {tf} fail / {te} error</span>'
    else:
        test_line = '<span class="gg-mc-stat gg-mc-muted">Tests: run pytest to populate</span>'

    return f'''<section class="gg-mc-hero">
  <div class="gg-mc-hero-inner">
    <div class="gg-mc-score-block">
      <span class="gg-mc-score-num">{score}</span>
      <span class="gg-mc-score-label">HEALTH</span>
    </div>
    <div class="gg-mc-hero-meta">
      <h1 class="gg-mc-title">Mission Control</h1>
      <p class="gg-mc-subtitle">{race_count} races &middot; Generated {esc(generated)}</p>
      <div class="gg-mc-gates">{gates_html}</div>
      <div class="gg-mc-tests">{test_line}</div>
    </div>
  </div>
</section>'''


def build_data_freshness(data: dict) -> str:
    """Data freshness section with tier bar and stale races table."""
    if data.get("error"):
        return f'<section class="gg-mc-section"><h2>Data Freshness</h2><p class="gg-mc-error">Error: {esc(data["error"])}</p></section>'

    total = data.get("total", 0)
    current = data.get("current_dates", 0)
    stale = data.get("stale_dates", 0)
    tbd = data.get("tbd_dates", 0)
    stubs = data.get("stubs", 0)

    # Tier distribution bar
    tier_counts = data.get("tier_counts", {})
    tier_bar = ""
    for tier_label in ("T1", "T2", "T3", "T4"):
        count = tier_counts.get(tier_label, 0)
        pct = round(count / total * 100, 1) if total else 0
        tier_bar += f'<div class="gg-mc-tier-seg gg-mc-tier-{tier_label.lower()}" style="width:{pct}%">{tier_label}: {count}</div>\n'

    # Stale races table
    stale_rows = ""
    stale_races = data.get("stale_races", [])
    if stale_races:
        for r in stale_races:
            stale_rows += f'<tr><td>{esc(r.get("tier", "?"))}</td><td>{esc(r.get("name", ""))}</td><td>{esc(r.get("date", ""))}</td></tr>\n'
    else:
        stale_rows = '<tr><td colspan="3">No stale races</td></tr>'

    return f'''<section class="gg-mc-section">
  <h2 class="gg-mc-section-title">Data Freshness</h2>
  <div class="gg-mc-metric-row">
    <div class="gg-mc-metric"><span class="gg-mc-metric-num">{total}</span><span class="gg-mc-metric-label">Total</span></div>
    <div class="gg-mc-metric"><span class="gg-mc-metric-num">{current}</span><span class="gg-mc-metric-label">Current</span></div>
    <div class="gg-mc-metric"><span class="gg-mc-metric-num">{stale}</span><span class="gg-mc-metric-label">Stale</span></div>
    <div class="gg-mc-metric"><span class="gg-mc-metric-num">{tbd}</span><span class="gg-mc-metric-label">TBD</span></div>
    <div class="gg-mc-metric"><span class="gg-mc-metric-num">{stubs}</span><span class="gg-mc-metric-label">Stubs</span></div>
  </div>
  <div class="gg-mc-tier-bar">{tier_bar}</div>
  <h3 class="gg-mc-sub-title">Stale Races (T1 first)</h3>
  <table class="gg-mc-table">
    <thead><tr><th>Tier</th><th>Race</th><th>Date</th></tr></thead>
    <tbody>{stale_rows}</tbody>
  </table>
</section>'''


def build_content_pipeline(data: dict) -> str:
    """Content pipeline section showing generators and output counts."""
    if data.get("error"):
        return f'<section class="gg-mc-section"><h2>Content Pipeline</h2><p class="gg-mc-error">Error: {esc(data["error"])}</p></section>'

    total_gen = data.get("total_generators", 0)
    output_counts = data.get("output_counts", {})

    # Split into multi-output and single-page
    multi_cards = ""
    single_cards = ""
    for gen_name, info in output_counts.items():
        count = info.get("count", 0)
        label = info.get("label", gen_name)
        status_cls = "gg-mc-pipe-ok" if count > 0 else "gg-mc-pipe-empty"
        card = f'''<div class="gg-mc-pipe-card {status_cls}">
      <span class="gg-mc-pipe-count">{count}</span>
      <span class="gg-mc-pipe-label">{esc(label)}</span>
    </div>\n'''
        if count > 1:
            multi_cards += card
        else:
            single_cards += card

    return f'''<section class="gg-mc-section">
  <h2 class="gg-mc-section-title">Content Pipeline <span class="gg-mc-badge">{total_gen} generators</span></h2>
  <h3 class="gg-mc-sub-title">Multi-Output</h3>
  <div class="gg-mc-pipe-grid">{multi_cards}</div>
  <h3 class="gg-mc-sub-title">Single Page</h3>
  <div class="gg-mc-pipe-grid">{single_cards}</div>
</section>'''


def build_deploy_map(data: dict) -> str:
    """Deploy targets grouped by category with copy buttons."""
    if data.get("error"):
        return f'<section class="gg-mc-section"><h2>Deploy Map</h2><p class="gg-mc-error">Error: {esc(data["error"])}</p></section>'

    total = data.get("total", 0)
    categorized = data.get("categorized", {})

    groups_html = ""
    for category, flags in categorized.items():
        cards = ""
        for flag in flags:
            cmd = f"python3 scripts/push_wordpress.py {flag}"
            cards += f'''<div class="gg-mc-deploy-card">
        <code class="gg-mc-deploy-cmd">{esc(flag)}</code>
        <button class="gg-mc-copy-btn" data-cmd="{esc(cmd)}" title="Copy command">cp</button>
      </div>\n'''
        groups_html += f'''<div class="gg-mc-deploy-group">
      <h3 class="gg-mc-sub-title">{esc(category)}</h3>
      <div class="gg-mc-deploy-grid">{cards}</div>
    </div>\n'''

    # Composite commands
    composites = f'''<div class="gg-mc-deploy-composites">
    <div class="gg-mc-deploy-card gg-mc-deploy-composite">
      <code class="gg-mc-deploy-cmd">--deploy-content</code>
      <span class="gg-mc-deploy-desc">pages + index + widget + cache</span>
      <button class="gg-mc-copy-btn" data-cmd="python3 scripts/push_wordpress.py --deploy-content" title="Copy command">cp</button>
    </div>
    <div class="gg-mc-deploy-card gg-mc-deploy-composite">
      <code class="gg-mc-deploy-cmd">--deploy-all</code>
      <span class="gg-mc-deploy-desc">all sync targets + cache</span>
      <button class="gg-mc-copy-btn" data-cmd="python3 scripts/push_wordpress.py --deploy-all" title="Copy command">cp</button>
    </div>
  </div>'''

    return f'''<section class="gg-mc-section">
  <h2 class="gg-mc-section-title">Deploy Map <span class="gg-mc-badge">{total} targets</span></h2>
  {groups_html}
  {composites}
</section>'''


def build_seo_pulse(data: dict) -> str:
    """SEO metrics from GSC snapshot."""
    if data.get("error"):
        return f'<section class="gg-mc-section"><h2>SEO Pulse</h2><p class="gg-mc-error">Error: {esc(data["error"])}</p></section>'

    if not data.get("configured"):
        return f'''<section class="gg-mc-section">
  <h2 class="gg-mc-section-title">SEO Pulse</h2>
  <div class="gg-mc-empty">
    <p>No GSC data available.</p>
    <p>Set <code>GOOGLE_APPLICATION_CREDENTIALS</code> and run:</p>
    <code class="gg-mc-cmd-block">python scripts/gsc_tracker.py --snapshot</code>
  </div>
</section>'''

    clicks = data.get("clicks", 0)
    impressions = data.get("impressions", 0)
    ctr = data.get("ctr", 0)
    position = data.get("position", 0)
    snap_date = data.get("snapshot_date", "?")

    # Top queries table
    queries_rows = ""
    for q in data.get("top_queries", []):
        queries_rows += f'<tr><td>{esc(q.get("query", ""))}</td><td>{q.get("clicks", 0)}</td><td>{q.get("impressions", 0)}</td></tr>\n'

    # Top pages table
    pages_rows = ""
    for p in data.get("top_pages", []):
        page_url = p.get("page", "")
        short = page_url.replace("https://gravelgodcycling.com", "") or "/"
        pages_rows += f'<tr><td>{esc(short)}</td><td>{p.get("clicks", 0)}</td><td>{p.get("impressions", 0)}</td></tr>\n'

    return f'''<section class="gg-mc-section">
  <h2 class="gg-mc-section-title">SEO Pulse <span class="gg-mc-muted">({esc(snap_date)})</span></h2>
  <div class="gg-mc-metric-row">
    <div class="gg-mc-metric"><span class="gg-mc-metric-num">{clicks:,}</span><span class="gg-mc-metric-label">Clicks</span></div>
    <div class="gg-mc-metric"><span class="gg-mc-metric-num">{impressions:,}</span><span class="gg-mc-metric-label">Impressions</span></div>
    <div class="gg-mc-metric"><span class="gg-mc-metric-num">{ctr:.1%}</span><span class="gg-mc-metric-label">CTR</span></div>
    <div class="gg-mc-metric"><span class="gg-mc-metric-num">{position:.1f}</span><span class="gg-mc-metric-label">Avg Position</span></div>
  </div>
  <div class="gg-mc-two-col">
    <div>
      <h3 class="gg-mc-sub-title">Top Queries</h3>
      <table class="gg-mc-table"><thead><tr><th>Query</th><th>Clicks</th><th>Impr</th></tr></thead>
      <tbody>{queries_rows if queries_rows else '<tr><td colspan="3">No data</td></tr>'}</tbody></table>
    </div>
    <div>
      <h3 class="gg-mc-sub-title">Top Pages</h3>
      <table class="gg-mc-table"><thead><tr><th>Page</th><th>Clicks</th><th>Impr</th></tr></thead>
      <tbody>{pages_rows if pages_rows else '<tr><td colspan="3">No data</td></tr>'}</tbody></table>
    </div>
  </div>
</section>'''


def build_quick_commands(data: dict) -> str:
    """Collapsible command reference groups."""
    groups_html = ""
    for group_name, commands in data.items():
        rows = ""
        for cmd, desc in commands:
            rows += f'''<div class="gg-mc-cmd-row">
        <code class="gg-mc-cmd">{esc(cmd)}</code>
        <span class="gg-mc-cmd-desc">{esc(desc)}</span>
        <button class="gg-mc-copy-btn" data-cmd="{esc(cmd)}" title="Copy command">cp</button>
      </div>\n'''
        groups_html += f'''<details class="gg-mc-cmd-group" open>
      <summary class="gg-mc-cmd-summary">{esc(group_name)}</summary>
      <div class="gg-mc-cmd-list">{rows}</div>
    </details>\n'''

    return f'''<section class="gg-mc-section">
  <h2 class="gg-mc-section-title">Quick Commands</h2>
  {groups_html}
</section>'''


def build_sprint_log(data: dict) -> str:
    """Recent sprints and remaining work."""
    sprints_html = ""
    for sprint in data.get("recent_sprints", []):
        items = ""
        for item in sprint.get("items", []):
            items += f"<li>{esc(item)}</li>\n"
        sprints_html += f'''<div class="gg-mc-sprint">
      <h3 class="gg-mc-sprint-title">Sprint {sprint.get("number", "?")} &mdash; {esc(sprint.get("title", ""))}</h3>
      <ul class="gg-mc-sprint-items">{items}</ul>
    </div>\n'''

    remaining_html = ""
    for item in data.get("remaining_work", []):
        remaining_html += f"<li>{esc(item)}</li>\n"

    return f'''<section class="gg-mc-section">
  <h2 class="gg-mc-section-title">Sprint Log</h2>
  {sprints_html}
  <h3 class="gg-mc-sub-title">Remaining Work</h3>
  <ul class="gg-mc-remaining">{remaining_html}</ul>
</section>'''


# ── CSS / JS ─────────────────────────────────────────────────────


def build_mc_css() -> str:
    """Dark-theme CSS for mission control dashboard."""
    return '''<style>
/* ── Mission Control Dashboard ── */

.gg-mc-page {
  background: var(--gg-color-near-black);
  color: var(--gg-color-sand);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  line-height: 1.5;
  margin: 0;
  padding: 0;
  min-height: 100vh;
}

.gg-mc-wrap {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

/* ── Hero ── */

.gg-mc-hero {
  background: var(--gg-color-dark-brown);
  border: 2px solid var(--gg-color-secondary-brown);
  padding: 32px;
  margin-bottom: 24px;
}

.gg-mc-hero-inner {
  display: flex;
  align-items: center;
  gap: 32px;
}

.gg-mc-score-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 100px;
}

.gg-mc-score-num {
  font-size: var(--gg-font-size-5xl);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-teal);
  line-height: 1;
}

.gg-mc-score-label {
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
  text-transform: uppercase;
  letter-spacing: 2px;
}

.gg-mc-title {
  font-size: var(--gg-font-size-2xl);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-warm-paper);
  margin: 0 0 4px 0;
}

.gg-mc-subtitle {
  color: var(--gg-color-secondary-brown);
  margin: 0 0 12px 0;
}

.gg-mc-gates {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.gg-mc-gate {
  display: inline-block;
  padding: 2px 8px;
  font-size: var(--gg-font-size-2xs);
  text-transform: uppercase;
  letter-spacing: 1px;
  border: 1px solid;
}

.gg-mc-gate-ok {
  color: var(--gg-color-teal);
  border-color: var(--gg-color-teal);
}

.gg-mc-gate-missing {
  color: var(--gg-color-error);
  border-color: var(--gg-color-error);
}

.gg-mc-tests {
  margin-top: 8px;
}

.gg-mc-stat {
  font-size: var(--gg-font-size-xs);
}

.gg-mc-muted {
  color: var(--gg-color-secondary-brown);
}

.gg-mc-error {
  color: var(--gg-color-error);
}

/* ── Sections ── */

.gg-mc-section {
  background: var(--gg-color-dark-brown);
  border: 2px solid var(--gg-color-secondary-brown);
  padding: 24px;
  margin-bottom: 24px;
}

.gg-mc-section-title {
  font-size: var(--gg-font-size-lg);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-warm-paper);
  margin: 0 0 16px 0;
  border-bottom: 1px solid var(--gg-color-secondary-brown);
  padding-bottom: 8px;
}

.gg-mc-sub-title {
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-semibold);
  color: var(--gg-color-tan);
  margin: 16px 0 8px 0;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.gg-mc-badge {
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-regular);
  color: var(--gg-color-secondary-brown);
}

/* ── Metrics Row ── */

.gg-mc-metric-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.gg-mc-metric {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 20px;
  border: 1px solid var(--gg-color-secondary-brown);
  min-width: 80px;
}

.gg-mc-metric-num {
  font-size: var(--gg-font-size-xl);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-warm-paper);
}

.gg-mc-metric-label {
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  text-transform: uppercase;
  letter-spacing: 1px;
}

/* ── Tier Bar ── */

.gg-mc-tier-bar {
  display: flex;
  height: 28px;
  border: 1px solid var(--gg-color-secondary-brown);
  margin-bottom: 16px;
  overflow: hidden;
}

.gg-mc-tier-seg {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-warm-paper);
  white-space: nowrap;
  overflow: hidden;
}

.gg-mc-tier-t1 { background: var(--gg-color-tier-1); }
.gg-mc-tier-t2 { background: var(--gg-color-tier-2); }
.gg-mc-tier-t3 { background: color-mix(in srgb, var(--gg-color-tier-3) 60%, transparent); }
.gg-mc-tier-t4 { background: color-mix(in srgb, var(--gg-color-tier-4) 30%, transparent); }

/* ── Table ── */

.gg-mc-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--gg-font-size-xs);
}

.gg-mc-table th,
.gg-mc-table td {
  text-align: left;
  padding: 6px 10px;
  border-bottom: 1px solid color-mix(in srgb, var(--gg-color-secondary-brown) 40%, transparent);
}

.gg-mc-table th {
  color: var(--gg-color-tan);
  text-transform: uppercase;
  letter-spacing: 1px;
  font-size: var(--gg-font-size-2xs);
}

.gg-mc-table td {
  color: var(--gg-color-sand);
}

/* ── Pipeline Grid ── */

.gg-mc-pipe-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 8px;
  margin-bottom: 16px;
}

.gg-mc-pipe-card {
  border: 1px solid var(--gg-color-secondary-brown);
  padding: 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.gg-mc-pipe-ok {
  border-color: var(--gg-color-teal);
}

.gg-mc-pipe-empty {
  border-color: var(--gg-color-error);
}

.gg-mc-pipe-count {
  font-size: var(--gg-font-size-lg);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-warm-paper);
}

.gg-mc-pipe-label {
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  text-align: center;
}

/* ── Deploy Grid ── */

.gg-mc-deploy-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px;
  margin-bottom: 16px;
}

.gg-mc-deploy-card {
  border: 1px solid var(--gg-color-secondary-brown);
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.gg-mc-deploy-cmd {
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-light-teal);
  flex: 1;
}

.gg-mc-deploy-desc {
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
}

.gg-mc-deploy-composites {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 16px;
}

.gg-mc-deploy-composite {
  border-color: var(--gg-color-teal);
  flex: 1;
  min-width: 200px;
}

/* ── Copy Button ── */

.gg-mc-copy-btn {
  background: none;
  border: 1px solid var(--gg-color-secondary-brown);
  color: var(--gg-color-secondary-brown);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  padding: 2px 6px;
  cursor: pointer;
  white-space: nowrap;
}

.gg-mc-copy-btn:hover {
  border-color: var(--gg-color-teal);
  color: var(--gg-color-teal);
}

/* ── Commands ── */

.gg-mc-cmd-group {
  margin-bottom: 12px;
}

.gg-mc-cmd-summary {
  cursor: pointer;
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-semibold);
  color: var(--gg-color-tan);
  text-transform: uppercase;
  letter-spacing: 1px;
  padding: 8px 0;
  border-bottom: 1px solid var(--gg-color-secondary-brown);
}

.gg-mc-cmd-list {
  padding: 8px 0;
}

.gg-mc-cmd-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 0;
  border-bottom: 1px solid color-mix(in srgb, var(--gg-color-secondary-brown) 30%, transparent);
}

.gg-mc-cmd {
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-light-teal);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gg-mc-cmd-desc {
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  flex-shrink: 0;
  max-width: 280px;
}

.gg-mc-cmd-block {
  display: block;
  background: color-mix(in srgb, var(--gg-color-near-black) 80%, transparent);
  padding: 8px 12px;
  margin-top: 8px;
  color: var(--gg-color-light-teal);
  font-size: var(--gg-font-size-xs);
}

/* ── Two Column ── */

.gg-mc-two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

/* ── Sprint Log ── */

.gg-mc-sprint {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid color-mix(in srgb, var(--gg-color-secondary-brown) 30%, transparent);
}

.gg-mc-sprint-title {
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-semibold);
  color: var(--gg-color-warm-paper);
  margin: 0 0 8px 0;
}

.gg-mc-sprint-items,
.gg-mc-remaining {
  margin: 0;
  padding-left: 20px;
  color: var(--gg-color-sand);
  font-size: var(--gg-font-size-xs);
}

.gg-mc-sprint-items li,
.gg-mc-remaining li {
  margin-bottom: 4px;
}

/* ── Empty State ── */

.gg-mc-empty {
  text-align: center;
  padding: 24px;
  color: var(--gg-color-secondary-brown);
}

.gg-mc-empty code {
  color: var(--gg-color-light-teal);
}

/* ── Responsive ── */

@media (max-width: 768px) {
  .gg-mc-hero-inner {
    flex-direction: column;
    text-align: center;
  }
  .gg-mc-metric-row {
    flex-wrap: wrap;
    justify-content: center;
  }
  .gg-mc-two-col {
    grid-template-columns: 1fr;
  }
  .gg-mc-deploy-grid {
    grid-template-columns: 1fr;
  }
  .gg-mc-cmd-row {
    flex-direction: column;
    align-items: flex-start;
  }
  .gg-mc-cmd-desc {
    max-width: 100%;
  }
}
</style>'''


def build_mc_js() -> str:
    """JS for copy-to-clipboard and collapsible sections."""
    return '''<script>
(function(){
  document.querySelectorAll('.gg-mc-copy-btn').forEach(function(btn){
    btn.addEventListener('click', function(){
      var cmd = btn.getAttribute('data-cmd');
      if (!cmd) return;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(cmd).then(function(){
          var orig = btn.textContent;
          btn.textContent = 'ok';
          setTimeout(function(){ btn.textContent = orig; }, 1200);
        });
      } else {
        var ta = document.createElement('textarea');
        ta.value = cmd;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        var orig = btn.textContent;
        btn.textContent = 'ok';
        setTimeout(function(){ btn.textContent = orig; }, 1200);
      }
    });
  });
})();
</script>'''


# ── Page Assembly ────────────────────────────────────────────────


def generate_mc_page() -> str:
    """Assemble the complete Mission Control HTML page."""
    # Collect all data
    health = collect_health_overview()
    freshness = collect_data_freshness()
    pipeline = collect_content_pipeline()
    deploy = collect_deploy_targets()
    seo = collect_seo_pulse()
    commands = collect_quick_commands()
    sprints = collect_sprint_log()

    # Adjust health score based on freshness data
    if not freshness.get("error"):
        stale = freshness.get("stale_dates", 0)
        total = freshness.get("total", 1)
        stale_pct = stale / total if total else 0
        if stale_pct > 0.2:
            health["health_score"] = max(0, health.get("health_score", 100) - 20)
        elif stale_pct > 0.1:
            health["health_score"] = max(0, health.get("health_score", 100) - 10)

    # Build sections
    hero = build_health_hero(health)
    freshness_section = build_data_freshness(freshness)
    pipeline_section = build_content_pipeline(pipeline)
    deploy_section = build_deploy_map(deploy)
    seo_section = build_seo_pulse(seo)
    commands_section = build_quick_commands(commands)
    sprint_section = build_sprint_log(sprints)

    # Build CSS/JS
    mc_css = build_mc_css()
    mc_js = build_mc_js()
    tokens_css = get_tokens_css()
    preload = get_preload_hints()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex, nofollow">
  <title>Mission Control | Gravel God</title>
  {preload}
  <style>{tokens_css}</style>
  {mc_css}
</head>
<body class="gg-mc-page">
<div class="gg-mc-wrap">
  {hero}
  {freshness_section}
  {pipeline_section}
  {deploy_section}
  {seo_section}
  {commands_section}
  {sprint_section}
</div>
{mc_js}
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(
        description="Generate Mission Control dashboard"
    )
    parser.add_argument(
        "--output-dir",
        default=str(OUTPUT_DIR),
        help="Output directory (default: wordpress/output)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    mc_dir = output_dir / "mission-control"
    mc_dir.mkdir(parents=True, exist_ok=True)

    html_content = generate_mc_page()

    output_file = mc_dir / "index.html"
    output_file.write_text(html_content, encoding="utf-8")
    print(f"Generated {output_file} ({len(html_content):,} bytes)")


if __name__ == "__main__":
    main()
