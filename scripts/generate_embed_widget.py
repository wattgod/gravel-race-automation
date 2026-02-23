#!/usr/bin/env python3
"""Generate the embeddable race badge widget.

Produces:
  web/embed/embed-data.json  — compact race data for all 328 races
  web/embed/gg-embed.js      — self-contained widget renderer (~5KB)
  web/embed/demo.html        — copy-paste documentation page

Usage:
    python scripts/generate_embed_widget.py           # Generate all files
    python scripts/generate_embed_widget.py --dry-run  # Preview only
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
INDEX_FILE = PROJECT_ROOT / "web" / "race-index.json"
EMBED_DIR = PROJECT_ROOT / "web" / "embed"
SITE_URL = "https://gravelgodcycling.com"


def generate_embed_data():
    """Generate compact race data for the embed widget."""
    index = json.loads(INDEX_FILE.read_text())
    entries = []

    for race in index:
        slug = race["slug"]
        # Read full race data for date info
        race_file = RACE_DATA_DIR / f"{slug}.json"
        date_str = ""
        if race_file.exists():
            full = json.loads(race_file.read_text())
            r = full.get("race", full)
            vitals = r.get("vitals", {})
            date_str = vitals.get("date_specific", vitals.get("date", ""))

        entries.append({
            "s": slug,
            "n": race["name"],
            "t": race["tier"],
            "sc": race["overall_score"],
            "l": race["location"],
            "d": date_str,
            "u": f"{SITE_URL}/race/{slug}/",
        })

    return entries


def generate_embed_js():
    """Generate the self-contained embed widget JavaScript."""
    return r"""(function(){
  "use strict";
  var SITE="https://gravelgodcycling.com";
  var DATA_URL=SITE+"/embed/embed-data.json";
  var CSS=`
.gg-embed-card{font-family:'Sometype Mono',ui-monospace,monospace;border:3px solid #3a2e25;background:#f5efe6;padding:14px 16px;max-width:340px;color:#3a2e25;line-height:1.4;box-sizing:border-box}
.gg-embed-card *{box-sizing:border-box;margin:0;padding:0;border-radius:0}
.gg-embed-card a{color:inherit;text-decoration:none}
.gg-embed-card a:hover{text-decoration:underline}
.gg-embed-top{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:8px}
.gg-embed-name{font-size:14px;font-weight:700;flex:1}
.gg-embed-tier{display:inline-block;padding:2px 8px;font-size:11px;font-weight:700;color:#fff;letter-spacing:1px;white-space:nowrap}
.gg-embed-tier-1{background:#59473c}
.gg-embed-tier-2{background:#7d695d}
.gg-embed-tier-3{background:#766a5e}
.gg-embed-tier-4{background:#5e6868}
.gg-embed-score-row{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.gg-embed-score-num{font-size:20px;font-weight:700;min-width:36px}
.gg-embed-score-bar{flex:1;height:8px;background:#d4c5b9;position:relative}
.gg-embed-score-fill{position:absolute;top:0;left:0;height:100%;background:#59473c}
.gg-embed-meta{font-size:11px;color:#7d695d;display:flex;flex-wrap:wrap;gap:4px 12px;margin-bottom:8px}
.gg-embed-link{display:block;font-size:11px;font-weight:700;color:#178079;letter-spacing:0.5px}
.gg-embed-link:hover{text-decoration:underline}
.gg-embed-powered{font-size:9px;color:#7d695d;margin-top:6px;text-align:right}
`;

  var styleInjected=false;
  function injectCSS(){
    if(styleInjected)return;
    var s=document.createElement("style");
    s.textContent=CSS;
    document.head.appendChild(s);
    styleInjected=true;
  }

  var dataCache=null;
  var dataCallbacks=[];
  var dataLoading=false;

  function fetchData(cb){
    if(dataCache){cb(dataCache);return}
    dataCallbacks.push(cb);
    if(dataLoading)return;
    dataLoading=true;
    var x=new XMLHttpRequest();
    x.open("GET",DATA_URL,true);
    x.onload=function(){
      if(x.status===200){
        try{dataCache=JSON.parse(x.responseText)}catch(e){dataCache=[]}
      }else{dataCache=[]}
      for(var i=0;i<dataCallbacks.length;i++)dataCallbacks[i](dataCache);
      dataCallbacks=[];
    };
    x.onerror=function(){
      dataCache=[];
      for(var i=0;i<dataCallbacks.length;i++)dataCallbacks[i](dataCache);
      dataCallbacks=[];
    };
    x.send();
  }

  function renderCard(el,race){
    var tier=race.t;
    var tierLabel="T"+tier;
    var score=race.sc;
    var html='<div class="gg-embed-card">';
    html+='<div class="gg-embed-top">';
    html+='<a href="'+race.u+'" target="_blank" rel="noopener" class="gg-embed-name">'+esc(race.n)+'</a>';
    html+='<span class="gg-embed-tier gg-embed-tier-'+tier+'">'+tierLabel+'</span>';
    html+='</div>';
    html+='<div class="gg-embed-score-row">';
    html+='<span class="gg-embed-score-num">'+score+'</span>';
    html+='<div class="gg-embed-score-bar"><div class="gg-embed-score-fill" style="width:'+score+'%"></div></div>';
    html+='</div>';
    html+='<div class="gg-embed-meta">';
    if(race.l)html+='<span>'+esc(race.l)+'</span>';
    if(race.d)html+='<span>'+esc(race.d)+'</span>';
    html+='</div>';
    html+='<a href="'+race.u+'" target="_blank" rel="noopener" class="gg-embed-link">View on Gravel God &rarr;</a>';
    html+='<div class="gg-embed-powered"><a href="'+SITE+'" target="_blank" rel="noopener">Powered by Gravel God</a></div>';
    html+='</div>';
    el.innerHTML=html;

    // GA4 event
    if(typeof gtag==="function"){
      try{gtag("event","embed_load",{race_slug:race.s,race_tier:tier})}catch(e){}
    }
  }

  function esc(s){
    var d=document.createElement("div");
    d.textContent=s;
    return d.innerHTML;
  }

  function init(){
    injectCSS();
    var els=document.querySelectorAll(".gg-embed[data-slug]");
    if(!els.length)return;
    fetchData(function(data){
      var map={};
      for(var i=0;i<data.length;i++)map[data[i].s]=data[i];
      for(var j=0;j<els.length;j++){
        var slug=els[j].getAttribute("data-slug");
        var race=map[slug];
        if(race){
          renderCard(els[j],race);
        }else{
          els[j].innerHTML='<div class="gg-embed-card" style="text-align:center;padding:20px"><span style="color:#7d695d">Race not found: '+esc(slug)+'</span></div>';
        }
      }
    });
  }

  if(document.readyState==="loading"){
    document.addEventListener("DOMContentLoaded",init);
  }else{
    init();
  }
})();
"""


def generate_demo_html():
    """Generate the demo/documentation page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Gravel God Embed Widget</title>
<style>
  body {{ font-family: 'Sometype Mono', ui-monospace, monospace; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #3a2e25; background: #f5efe6; line-height: 1.6; }}
  h1 {{ font-size: 24px; border-bottom: 3px solid #3a2e25; padding-bottom: 8px; }}
  h2 {{ font-size: 18px; margin-top: 32px; }}
  code {{ background: #ede4d8; padding: 2px 6px; font-size: 13px; }}
  pre {{ background: #ede4d8; padding: 16px; border: 2px solid #3a2e25; overflow-x: auto; font-size: 13px; line-height: 1.5; }}
  .demo-row {{ display: flex; flex-wrap: wrap; gap: 20px; margin: 20px 0; }}
</style>
</head>
<body>
<h1>Gravel God Embed Widget</h1>
<p>Add a Gravel God race rating badge to your site. Compact, lightweight, and self-contained.</p>

<h2>Quick Start</h2>
<p>Paste this where you want the badge to appear:</p>
<pre>&lt;div class="gg-embed" data-slug="unbound-200"&gt;&lt;/div&gt;
&lt;script src="{SITE_URL}/embed/gg-embed.js" async&gt;&lt;/script&gt;</pre>

<p>Change <code>data-slug</code> to any race slug from the <a href="{SITE_URL}/gravel-races/">race database</a>.</p>

<h2>Multiple Badges</h2>
<p>Include the script once, add as many badges as you want:</p>
<pre>&lt;div class="gg-embed" data-slug="unbound-200"&gt;&lt;/div&gt;
&lt;div class="gg-embed" data-slug="leadville-100"&gt;&lt;/div&gt;
&lt;div class="gg-embed" data-slug="crusher-in-the-tushar"&gt;&lt;/div&gt;
&lt;script src="{SITE_URL}/embed/gg-embed.js" async&gt;&lt;/script&gt;</pre>

<h2>Live Examples</h2>
<div class="demo-row">
  <div class="gg-embed" data-slug="unbound-200"></div>
  <div class="gg-embed" data-slug="leadville-100"></div>
</div>
<div class="demo-row">
  <div class="gg-embed" data-slug="crusher-in-the-tushar"></div>
  <div class="gg-embed" data-slug="mid-south"></div>
</div>

<h2>How It Works</h2>
<ul>
  <li>The script loads a compact JSON file (~15KB) with all 328 race ratings</li>
  <li>Each badge is rendered client-side with race name, tier, score, location, and date</li>
  <li>Clicking the badge links to the full race profile on Gravel God</li>
  <li>No dependencies, no cookies, no tracking (GA4 event only on gravelgodcycling.com)</li>
  <li>Styles are scoped to <code>.gg-embed-card</code> and won't affect your site</li>
</ul>

<h2>Available Slugs</h2>
<p>Find any race slug at <a href="{SITE_URL}/gravel-races/">{SITE_URL}/gravel-races/</a>. The slug is the last part of the race profile URL.</p>

<script src="gg-embed.js"></script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="Generate embed widget files")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview only, don't write files")
    args = parser.parse_args()

    print("Generating embed widget...")

    # 1. Generate embed data
    embed_data = generate_embed_data()
    data_json = json.dumps(embed_data, separators=(",", ":"), ensure_ascii=False)
    print(f"  Embed data: {len(embed_data)} races, {len(data_json):,} bytes")

    # 2. Generate JS
    embed_js = generate_embed_js()
    print(f"  Embed JS: {len(embed_js):,} bytes")

    # 3. Generate demo HTML
    demo_html = generate_demo_html()
    print(f"  Demo HTML: {len(demo_html):,} bytes")

    if args.dry_run:
        print("\n  [dry run] Would write to web/embed/")
        return 0

    # Write files
    EMBED_DIR.mkdir(parents=True, exist_ok=True)

    (EMBED_DIR / "embed-data.json").write_text(data_json + "\n")
    print(f"  Wrote: web/embed/embed-data.json")

    (EMBED_DIR / "gg-embed.js").write_text(embed_js)
    print(f"  Wrote: web/embed/gg-embed.js")

    (EMBED_DIR / "demo.html").write_text(demo_html)
    print(f"  Wrote: web/embed/demo.html")

    return 0


if __name__ == "__main__":
    sys.exit(main())
