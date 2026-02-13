#!/usr/bin/env python3
"""
Generate the blog index page at /blog/index.html.

Static HTML with client-side JS that fetches /blog/blog-index.json
for filtering and sorting. Follows the search widget architectural pattern.

Usage:
    python wordpress/generate_blog_index_page.py
    python wordpress/generate_blog_index_page.py --output-dir DIR
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "wordpress" / "output"
SITE_URL = "https://gravelgodcycling.com"


def generate_blog_index_page(output_dir=None):
    """Generate the blog index HTML page."""
    out_dir = output_dir or OUTPUT_DIR
    today = date.today()
    today_str = today.strftime("%B %d, %Y")

    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "Gravel God Blog",
        "description": "Race previews, season roundups, and race recaps from the Gravel God gravel race database.",
        "url": f"{SITE_URL}/blog/",
        "publisher": {
            "@type": "Organization",
            "name": "Gravel God",
            "url": SITE_URL,
        },
    }, separators=(",", ":"))

    page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Gravel God Blog — Race Previews, Roundups &amp; Recaps</title>
  <meta name="description" content="Race previews, season roundups, and race recaps from the Gravel God gravel race database. 328 races rated and ranked.">
  <meta property="og:title" content="Gravel God Blog — Race Previews, Roundups &amp; Recaps">
  <meta property="og:description" content="Race previews, season roundups, and race recaps. 328 gravel races rated and ranked.">
  <meta property="og:url" content="{SITE_URL}/blog/">
  <link rel="canonical" href="{SITE_URL}/blog/">
  <script type="application/ld+json">{jsonld}</script>
  <style>
    :root {{
      --gg-dark-brown: #3a2e25;
      --gg-primary-brown: #59473c;
      --gg-secondary-brown: #7d695d;
      --gg-teal: #178079;
      --gg-light-teal: #4ECDC4;
      --gg-warm-paper: #f5efe6;
      --gg-sand: #ede4d8;
      --gg-white: #ffffff;
      --gg-gold: #9a7e0a;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; border-radius: 0; }}
    body {{
      font-family: 'Source Serif 4', Georgia, serif;
      background: var(--gg-warm-paper);
      color: var(--gg-dark-brown);
      line-height: 1.7;
    }}
    .gg-blog-index {{ max-width: 1100px; margin: 0 auto; padding: 32px 24px; }}

    /* Hero */
    .gg-bi-hero {{
      background: var(--gg-primary-brown);
      color: var(--gg-warm-paper);
      padding: 48px 32px;
      border: 3px solid var(--gg-dark-brown);
      margin-bottom: 24px;
      text-align: center;
    }}
    .gg-bi-hero h1 {{
      font-size: 32px;
      font-weight: 700;
      line-height: 1.2;
      margin-bottom: 8px;
    }}
    .gg-bi-hero-sub {{
      font-family: 'Sometype Mono', monospace;
      font-size: 13px;
      opacity: 0.7;
    }}

    /* Filters */
    .gg-bi-filters {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      margin-bottom: 24px;
      padding: 16px;
      border: 2px solid var(--gg-dark-brown);
      background: var(--gg-white);
    }}
    .gg-bi-filter-group {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      align-items: center;
    }}
    .gg-bi-filter-label {{
      font-family: 'Sometype Mono', monospace;
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      color: var(--gg-secondary-brown);
      margin-right: 4px;
    }}
    .gg-bi-chip {{
      font-family: 'Sometype Mono', monospace;
      font-size: 11px;
      font-weight: 700;
      padding: 4px 12px;
      border: 2px solid var(--gg-dark-brown);
      background: var(--gg-warm-paper);
      color: var(--gg-dark-brown);
      cursor: pointer;
      text-transform: uppercase;
      letter-spacing: 1px;
    }}
    .gg-bi-chip:hover {{ background: var(--gg-sand); }}
    .gg-bi-chip.active {{
      background: var(--gg-primary-brown);
      color: var(--gg-warm-paper);
    }}
    .gg-bi-sort {{
      margin-left: auto;
      font-family: 'Sometype Mono', monospace;
      font-size: 11px;
      border: 2px solid var(--gg-dark-brown);
      padding: 4px 8px;
      background: var(--gg-warm-paper);
    }}

    /* Results count */
    .gg-bi-count {{
      font-family: 'Sometype Mono', monospace;
      font-size: 11px;
      color: var(--gg-secondary-brown);
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-bottom: 16px;
    }}

    /* Card Grid */
    .gg-bi-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 20px;
      margin-bottom: 32px;
    }}
    .gg-bi-card {{
      border: 2px solid var(--gg-dark-brown);
      background: var(--gg-white);
      padding: 20px;
      display: flex;
      flex-direction: column;
    }}
    .gg-bi-card-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }}
    .gg-bi-cat {{
      font-family: 'Sometype Mono', monospace;
      font-size: 9px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      padding: 2px 8px;
      border: 1px solid var(--gg-secondary-brown);
      color: var(--gg-secondary-brown);
    }}
    .gg-bi-cat-roundup {{ border-color: var(--gg-teal); color: var(--gg-teal); }}
    .gg-bi-cat-recap {{ border-color: var(--gg-gold); color: var(--gg-gold); }}
    .gg-bi-tier {{
      font-family: 'Sometype Mono', monospace;
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      color: var(--gg-warm-paper);
    }}
    .gg-bi-card h3 {{
      font-size: 16px;
      font-weight: 700;
      line-height: 1.3;
      margin-bottom: 6px;
    }}
    .gg-bi-card h3 a {{
      color: var(--gg-dark-brown);
      text-decoration: none;
    }}
    .gg-bi-card h3 a:hover {{ text-decoration: underline; }}
    .gg-bi-date {{
      font-family: 'Sometype Mono', monospace;
      font-size: 10px;
      color: var(--gg-secondary-brown);
      margin-bottom: 8px;
    }}
    .gg-bi-excerpt {{
      font-size: 14px;
      color: var(--gg-secondary-brown);
      line-height: 1.5;
      flex: 1;
    }}

    /* Empty state */
    .gg-bi-empty {{
      text-align: center;
      padding: 48px;
      border: 2px solid var(--gg-dark-brown);
      background: var(--gg-white);
      font-family: 'Sometype Mono', monospace;
      font-size: 13px;
      color: var(--gg-secondary-brown);
    }}

    /* Footer */
    .gg-bi-footer {{
      text-align: center;
      font-family: 'Sometype Mono', monospace;
      font-size: 11px;
      color: var(--gg-secondary-brown);
      padding: 24px;
      text-transform: uppercase;
      letter-spacing: 1.5px;
    }}
    .gg-bi-footer a {{ color: var(--gg-teal); text-decoration: none; }}

    @media (max-width: 900px) {{
      .gg-bi-grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
    @media (max-width: 600px) {{
      .gg-bi-hero {{ padding: 32px 20px; }}
      .gg-bi-hero h1 {{ font-size: 24px; }}
      .gg-bi-grid {{ grid-template-columns: 1fr; }}
      .gg-bi-filters {{ flex-direction: column; align-items: flex-start; }}
      .gg-bi-sort {{ margin-left: 0; }}
    }}
  </style>
</head>
<body>
  <div class="gg-blog-index">
    <div class="gg-bi-hero">
      <h1>Gravel God Blog</h1>
      <div class="gg-bi-hero-sub">Race Previews &middot; Season Roundups &middot; Race Recaps</div>
    </div>

    <div class="gg-bi-filters">
      <div class="gg-bi-filter-group">
        <span class="gg-bi-filter-label">Category</span>
        <button class="gg-bi-chip active" data-filter="category" data-value="all">All</button>
        <button class="gg-bi-chip" data-filter="category" data-value="preview">Race Previews</button>
        <button class="gg-bi-chip" data-filter="category" data-value="roundup">Season Roundups</button>
        <button class="gg-bi-chip" data-filter="category" data-value="recap">Race Recaps</button>
      </div>
      <div class="gg-bi-filter-group">
        <span class="gg-bi-filter-label">Tier</span>
        <button class="gg-bi-chip active" data-filter="tier" data-value="0">Any</button>
        <button class="gg-bi-chip" data-filter="tier" data-value="1">T1</button>
        <button class="gg-bi-chip" data-filter="tier" data-value="2">T2</button>
        <button class="gg-bi-chip" data-filter="tier" data-value="3">T3</button>
        <button class="gg-bi-chip" data-filter="tier" data-value="4">T4</button>
      </div>
      <select class="gg-bi-sort" id="gg-bi-sort">
        <option value="date">Newest First</option>
        <option value="tier">Tier (High&rarr;Low)</option>
        <option value="alpha">A-Z</option>
      </select>
    </div>

    <div class="gg-bi-count" id="gg-bi-count">Loading...</div>
    <div class="gg-bi-grid" id="gg-bi-grid"></div>
    <div class="gg-bi-empty" id="gg-bi-empty" style="display:none">No articles match your filters.</div>

    <div class="gg-bi-footer">
      <a href="{SITE_URL}">Gravel God</a> &middot;
      <a href="{SITE_URL}/gravel-races/">Race Database</a> &middot;
      {today_str}
    </div>
  </div>

  <script>
  (function() {{
    var TIER_COLORS = {{1:'#59473c',2:'#7d695d',3:'#766a5e',4:'#5e6868'}};
    var CAT_LABELS = {{preview:'Race Preview',roundup:'Season Roundup',recap:'Race Recap'}};
    var blogData = [];
    var currentCategory = 'all';
    var currentTier = 0;
    var currentSort = 'date';

    function loadIndex() {{
      fetch('/blog/blog-index.json')
        .then(function(r) {{ return r.json(); }})
        .then(function(data) {{
          blogData = data;
          readUrlParams();
          render();
        }})
        .catch(function() {{
          document.getElementById('gg-bi-count').textContent = 'Failed to load blog index.';
        }});
    }}

    function readUrlParams() {{
      var p = new URLSearchParams(window.location.search);
      if (p.get('category')) currentCategory = p.get('category');
      if (p.get('tier')) currentTier = parseInt(p.get('tier')) || 0;
      if (p.get('sort')) currentSort = p.get('sort');
      // Update chip states
      document.querySelectorAll('[data-filter="category"]').forEach(function(el) {{
        el.classList.toggle('active', el.dataset.value === currentCategory);
      }});
      document.querySelectorAll('[data-filter="tier"]').forEach(function(el) {{
        el.classList.toggle('active', el.dataset.value === String(currentTier));
      }});
      document.getElementById('gg-bi-sort').value = currentSort;
    }}

    function updateUrl() {{
      var p = new URLSearchParams();
      if (currentCategory !== 'all') p.set('category', currentCategory);
      if (currentTier > 0) p.set('tier', currentTier);
      if (currentSort !== 'date') p.set('sort', currentSort);
      var qs = p.toString();
      var newUrl = window.location.pathname + (qs ? '?' + qs : '');
      history.replaceState(null, '', newUrl);
    }}

    function filterAndSort() {{
      var filtered = blogData.filter(function(e) {{
        if (currentCategory !== 'all' && e.category !== currentCategory) return false;
        if (currentTier > 0 && e.tier !== currentTier) return false;
        return true;
      }});
      filtered.sort(function(a, b) {{
        if (currentSort === 'date') return a.date < b.date ? 1 : a.date > b.date ? -1 : 0;
        if (currentSort === 'tier') return (a.tier || 99) - (b.tier || 99) || (b.date > a.date ? 1 : -1);
        if (currentSort === 'alpha') return a.title.localeCompare(b.title);
        return 0;
      }});
      return filtered;
    }}

    function renderCard(entry) {{
      var catClass = 'gg-bi-cat-' + entry.category;
      var catLabel = CAT_LABELS[entry.category] || entry.category;
      var tierHtml = '';
      if (entry.tier > 0) {{
        var color = TIER_COLORS[entry.tier] || '#5e6868';
        tierHtml = '<span class="gg-bi-tier" style="background:' + color + '">T' + entry.tier + '</span>';
      }}
      var dateStr = entry.date || '';
      var excerpt = entry.excerpt || '';
      if (excerpt.length > 160) excerpt = excerpt.substring(0, 157) + '...';

      return '<div class="gg-bi-card">' +
        '<div class="gg-bi-card-top">' +
          '<span class="gg-bi-cat ' + catClass + '">' + catLabel + '</span>' +
          tierHtml +
        '</div>' +
        '<h3><a href="' + entry.url + '">' + escHtml(entry.title) + '</a></h3>' +
        '<div class="gg-bi-date">' + dateStr + '</div>' +
        '<div class="gg-bi-excerpt">' + escHtml(excerpt) + '</div>' +
      '</div>';
    }}

    function escHtml(s) {{
      var d = document.createElement('div');
      d.textContent = s;
      return d.innerHTML;
    }}

    function render() {{
      var items = filterAndSort();
      var grid = document.getElementById('gg-bi-grid');
      var empty = document.getElementById('gg-bi-empty');
      var count = document.getElementById('gg-bi-count');

      count.textContent = items.length + ' article' + (items.length !== 1 ? 's' : '');
      if (items.length === 0) {{
        grid.innerHTML = '';
        empty.style.display = '';
      }} else {{
        empty.style.display = 'none';
        grid.innerHTML = items.map(renderCard).join('');
      }}
      updateUrl();
    }}

    // Event listeners
    document.querySelectorAll('.gg-bi-chip').forEach(function(chip) {{
      chip.addEventListener('click', function() {{
        var filter = this.dataset.filter;
        var value = this.dataset.value;
        if (filter === 'category') {{
          currentCategory = value;
          document.querySelectorAll('[data-filter="category"]').forEach(function(el) {{
            el.classList.toggle('active', el.dataset.value === value);
          }});
        }} else if (filter === 'tier') {{
          currentTier = parseInt(value) || 0;
          document.querySelectorAll('[data-filter="tier"]').forEach(function(el) {{
            el.classList.toggle('active', el.dataset.value === value);
          }});
        }}
        render();
      }});
    }});

    document.getElementById('gg-bi-sort').addEventListener('change', function() {{
      currentSort = this.value;
      render();
    }});

    loadIndex();
  }})();
  </script>
</body>
</html>"""

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "blog-index.html"
    out_file.write_text(page_html)
    print(f"Generated blog index page: {out_file}")
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Generate blog index page")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR,
                        help="Output directory")
    args = parser.parse_args()

    generate_blog_index_page(args.output_dir)


if __name__ == "__main__":
    main()
