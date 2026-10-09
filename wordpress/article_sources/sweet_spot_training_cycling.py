"""Source for /articles/sweet-spot-training-cycling/ on the editorial shell.

The article text is the live page's, verbatim (snapshot #438), in
sweet-spot-training-cycling.body.html; this file adds the page metadata, the
"In short" claims and the three figures' chart CSS/JS.

Regenerate after editing the body, the shell or data/pricing.json:

    python3 wordpress/article_sources/sweet_spot_training_cycling.py

tests/test_editorial_shell.py fails if the committed index.html is stale.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORDPRESS = HERE.parent
if str(WORDPRESS) not in sys.path:
    sys.path.insert(0, str(WORDPRESS))

from editorial_shell import (  # noqa: E402
    ArticleMeta,
    Claim,
    HeroImage,
    OgImage,
    render_editorial_page,
)

SLUG = "sweet-spot-training-cycling"
URL = f"https://gravelgodcycling.com/articles/{SLUG}/"
BODY_PATH = HERE / f"{SLUG}.body.html"
OUTPUT_PATH = WORDPRESS / "articles" / SLUG / "index.html"

ARTICLE_LD = {
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "Sweet Spot Training Isn't That Sweet — The Science Says You're Wasting Time",
    "author": {"@type": "Person", "name": "Matti Rowe", "url": "https://gravelgodcycling.com"},
    "publisher": {"@type": "Organization", "name": "Gravel God", "url": "https://gravelgodcycling.com"},
    "datePublished": "2026-03-26",
    "dateModified": "2026-03-26",
    "description": "Sweet Spot training is made up, makes you slower, and science hates it. The evidence for polarized training is clear.",
    "mainEntityOfPage": URL,
    "keywords": ["sweet spot training", "cycling training zones", "polarized training", "FTP", "threshold training", "cycling science"],
    "citation": [
        {"@type": "ScholarlyArticle", "name": "Autonomic recovery after exercise in trained athletes", "author": "Seiler, Haugen, Kuffel", "datePublished": "2007"},
        {"@type": "ScholarlyArticle", "name": "Six weeks of a polarized training-intensity distribution leads to greater physiological and performance adaptations", "author": "Neal et al.", "datePublished": "2013"},
        {"@type": "ScholarlyArticle", "name": "Polarized training has greater impact on key endurance variables", "author": "Stöggl, Sperlich", "datePublished": "2014"},
        {"@type": "ScholarlyArticle", "name": "Impact of training intensity distribution on performance in endurance athletes", "author": "Esteve-Lanao, Foster, Seiler, Lucia", "datePublished": "2007"},
        {"@type": "ScholarlyArticle", "name": "Polarized vs. threshold training intensity distribution on endurance sport performance", "author": "Rosenblat et al.", "datePublished": "2019"},
        {"@type": "ScholarlyArticle", "name": "Which training intensity distribution intervention will produce the greatest improvements", "author": "Rosenblat, Seiler et al.", "datePublished": "2025"},
    ],
}

FAQ_LD = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
        {
            "@type": "Question",
            "name": "What is Sweet Spot training in cycling?",
            "acceptedAnswer": {"@type": "Answer", "text": "Sweet Spot training targets 88-94% of Functional Threshold Power (FTP). It was coined by Frank Overton of FasCat Coaching around 2004, based on a hypothetical, unitless graph by exercise physiologist Andy Coggan that was 'only ever intended as conveying a concept.' It lacks rigorous scientific foundation."},
        },
        {
            "@type": "Question",
            "name": "Is polarized training better than Sweet Spot?",
            "acceptedAnswer": {"@type": "Answer", "text": "Yes. Multiple studies show polarized training (75-90% below LT1, 15-20% above LT2) consistently outperforms threshold-heavy training. Neal et al. (2013) showed 8% peak power gains vs 3% for threshold. Stöggl and Sperlich (2014) found polarized improved VO2peak by 11.7%. The 2025 network meta-analysis by Rosenblat and Seiler confirmed threshold-heavy approaches ranked worst for competitive athletes."},
        },
        {
            "@type": "Question",
            "name": "Why does Sweet Spot training make you slower?",
            "acceptedAnswer": {"@type": "Answer", "text": "Sweet Spot sits in Seiler's 'black hole' of training intensity. Your autonomic nervous system treats it like threshold work (same recovery cost), it inhibits fat oxidation by locking out CPT1/CPT2 enzymes, and it's not intense enough to maximally trigger mitochondrial biogenesis. You get the recovery cost of hard training with the adaptive stimulus of not-that-hard training."},
        },
        {
            "@type": "Question",
            "name": "Do most cyclists actually train at Sweet Spot intensity?",
            "acceptedAnswer": {"@type": "Answer", "text": "No. Most cyclists overestimate their FTP by 5-10%, meaning their 'Sweet Spot' workouts at 88-94% of inflated FTP actually put them at or above their true threshold. They're doing threshold work while thinking they found a training hack."},
        },
    ],
}

META = ArticleMeta(
    slug=SLUG,
    canonical_url=URL,
    title="Sweet Spot Training Isn't That Sweet | The Science Says You're Wasting Time | Gravel God",
    description="Sweet Spot training is made up, makes you slower, and science hates it. The evidence for polarized training is clear. 88-94% FTP is a marketing trick.",
    og_title="Sweet Spot Training Isn't That Sweet | Gravel God",
    og_description="It's made up, it makes you slower, science hates it, the name is weird, and its marketing makes us all dumber.",
    og_image=OgImage(url=f"{URL}img/sweet-spot-rip.png", width=734, height=894),
    headline="Sweet Spot Isn’t That Sweet",
    kicker="Training · Science · Opinion",
    dek="It’s made up, it makes you slower, science hates it, the name is weird, and its marketing makes us all dumber",
    date_published=date(2026, 3, 26),
    hero=HeroImage(
        src="img/sweet-spot-rip.png",
        alt="Cyclist standing on a gravestone reading Sweet Spot 2004-2026",
        width=734,
        height=894,
    ),
    json_ld=(ARTICLE_LD, FAQ_LD),
)

# Copy from the design brief (Matt picked D, 2026-10-08). Section indexes are
# 0-based h2 positions: 01 origin, 03 threshold, 05 slow, 07 polarized.
IN_SHORT = (
    Claim("Sweet Spot (88&ndash;94% of FTP) grew out of a hypothetical, unitless graph. Coggan said it was only meant to convey a concept.",
          "#fig-graph", "See the graph · §01", 0),
    Claim("Most riders&rsquo; FTP is 5&ndash;10% optimistic, so a &ldquo;Sweet Spot&rdquo; workout is usually threshold work.",
          "#fig-drift", "See the 250 W case study · §03", 2),
    Claim("Above LT1, your nervous system bills sweet spot like threshold.",
          "#fig-recovery", "See recovery cost vs intensity · §05", 4),
    Claim("Polarized training beat threshold-heavy training in study after study, including a 2025 meta-analysis.",
          "#fig-polarized", "See the studies · §07", 6),
)

# Chart internals for the three figures (drift, recovery, polarized).
CHART_CSS = """
.slot-drift{margin:34px 0 26px}
.drift h5{font:700 30px/1.15 var(--serif);letter-spacing:-.01em;margin:0 0 6px;color:var(--ink)}
.drift .sub{font:500 15px/1.5 var(--mono);color:var(--ink2);margin:0 0 20px}
.legend2{display:flex;flex-wrap:wrap;gap:8px 18px;margin:0 0 18px;font:700 13px var(--mono);text-transform:uppercase;letter-spacing:.04em;color:var(--ink)}
.legend2 span{display:inline-flex;align-items:center;gap:7px}
.sw{display:inline-block;width:18px;height:14px}
.sw.plan{box-shadow:inset 0 0 0 3px var(--ink)}
.sw.act{background:var(--cobalt)}
.sw.amb{background:var(--caution)}
.sw.red{background:var(--stop)}
.plot{display:grid;grid-template-columns:52px repeat(4,minmax(0,1fr));column-gap:14px;position:relative}
.cap{grid-row:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:6px;padding-bottom:12px;text-align:center}
.pill{display:inline-flex;align-items:center;font:700 16px var(--mono);border-radius:999px;padding:5px 12px;white-space:nowrap}
.pill.thin{color:var(--ink);box-shadow:inset 0 0 0 2px var(--ink)}
.pill.thick{color:var(--caution-text);box-shadow:inset 0 0 0 5px var(--caution);padding:7px 14px}
.pill.fill{color:#fff;background:var(--stop)}
.zone{font:700 12px/1.25 var(--mono);letter-spacing:.04em;text-transform:uppercase;color:var(--ink)}
.yax{grid-row:2;position:relative;height:320px}
.yax em{font-style:normal}
.yax span{position:absolute;right:0;transform:translateY(50%);font:700 12px var(--mono);color:var(--ink3);white-space:nowrap}
.col{grid-row:2;position:relative;height:320px;border-bottom:4px solid var(--ink)}
.col .plan{position:absolute;left:0;right:0;bottom:0;box-shadow:inset 0 0 0 3px var(--ink);z-index:2;pointer-events:none}
.col .act{position:absolute;left:3px;right:3px;bottom:0;background:var(--cobalt);display:flex;justify-content:center;align-items:flex-start;padding-top:10px}
.col .over{position:absolute;left:3px;right:3px;display:flex;justify-content:center;align-items:center}
.col .over.amb{background:var(--caution)}
.col .over.red{background:var(--stop)}
.col .act .v,.col .over .v{font:700 16px var(--mono);color:#fff;white-space:nowrap}
.col .over.amb .v{color:var(--ink)}
.tested{position:relative;height:320px;z-index:3;pointer-events:none}
.tested i{position:absolute;left:-8px;right:0;height:0;border-top:3px dashed var(--ink2)}
.tested span{position:absolute;right:0;margin-bottom:6px;font:700 12px var(--mono);letter-spacing:.06em;color:var(--ink2);background:var(--fig);padding:0 0 0 6px}
.xl{grid-row:3;text-align:center;padding-top:10px;font:700 13px/1.3 var(--mono);color:var(--ink);text-transform:uppercase}
.xl small{display:block;font-weight:700;font-size:12px;color:var(--ink3)}
.verdict{display:grid;grid-template-columns:1fr;gap:24px;margin-top:28px;align-items:start}
.verdict blockquote{margin:0;padding:0;box-shadow:none;font:italic 400 24px/1.35 var(--serif);color:var(--ink)}
.verdict blockquote cite{display:block;font:700 12px var(--mono);font-style:normal;letter-spacing:.08em;text-transform:uppercase;color:var(--ink3);margin-top:10px}
.band h6{font:700 13px var(--mono);letter-spacing:.08em;text-transform:uppercase;margin:0 0 12px;color:var(--ink)}
.brow{display:grid;grid-template-columns:150px 1fr;gap:10px;align-items:center;margin-bottom:8px}
.brow .lab{font:700 12px/1.25 var(--mono);text-transform:uppercase;color:var(--ink2)}
.track{position:relative;height:30px;background:var(--sand)}
.track i{position:absolute;top:0;bottom:0}
.track i.o{box-shadow:inset 0 0 0 3px var(--ink)}
.track i.s{background:var(--cobalt)}
.track b{position:absolute;top:50%;transform:translate(-50%,-50%);font:700 12px var(--mono);white-space:nowrap}
.track i.s + b{color:#fff}
.ticks{position:relative;height:18px;margin-left:160px;font:700 12px var(--mono);color:var(--ink3)}
.ticks span{position:absolute;transform:translateX(-50%);white-space:nowrap}
.ticks span:last-child{transform:translateX(-100%)}
.mathbar{margin-top:24px}
.mathbar .btn{background:var(--ink)}
.mathbar .btn:hover{background:#000}
.math[hidden]{display:none}
.math{margin-top:18px}
.slot-recovery{margin:30px 0}
.rec .row{display:grid;grid-template-columns:1fr 6px 1fr 1fr;gap:14px;align-items:end;height:190px}
.rec .bar{box-shadow:inset 0 0 0 3px var(--ink);background:repeating-linear-gradient(135deg,transparent 0 9px,rgba(42,33,27,.14) 9px 12px)}
.rec .bar.hi{height:82%}
.rec .bar.lo{height:16%}
.rec .lt1{height:100%;background:var(--ink);position:relative}
.rec .lt1 span{position:absolute;top:0;left:12px;font:700 12px var(--mono);white-space:nowrap;letter-spacing:.06em}
.rec .lbls{display:grid;grid-template-columns:1fr 6px 1fr 1fr;gap:14px;margin-top:10px;font:700 13px/1.3 var(--mono);text-transform:uppercase;text-align:center}
.rec .lbls small{display:block;color:var(--ink3);font-size:12px}
.kick .note{color:var(--ink2);text-transform:none;letter-spacing:0;font-weight:700}
.slot-polarized{margin:30px 0}
.stack{display:flex;height:64px;gap:4px}
.stack .easy{flex:80;background:var(--teal);color:#fff;display:flex;align-items:center;padding-left:14px;font:700 20px var(--mono)}
.stack .hole{flex:5;background:var(--hole)}
.stack .hard{flex:15;background:var(--stop);color:#fff;display:flex;align-items:center;justify-content:center;font:700 16px var(--mono)}
.keys{display:flex;flex-wrap:wrap;gap:8px 26px;margin:14px 0 26px;font:700 14px var(--mono);color:var(--ink)}
.keys span{display:inline-flex;align-items:center;gap:8px;white-space:nowrap}
.keys .sw{width:16px;height:16px}
.neal h6{font:700 13px var(--mono);letter-spacing:.08em;text-transform:uppercase;margin:0 0 12px}
.nrow{display:grid;grid-template-columns:110px 1fr;gap:12px;align-items:center;margin-bottom:10px}
.nrow .lab{font:700 13px var(--mono);text-transform:uppercase}
.nbar{height:44px;display:flex;align-items:center;justify-content:flex-end;padding-right:10px;font:700 22px var(--mono)}
.nbar.s{background:var(--teal);color:#fff}
.nbar.o{box-shadow:inset 0 0 0 3px var(--ink);color:var(--ink)}
.more{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:22px}
.article .more p{margin:0;font:700 13px/1.4 var(--mono);color:var(--ink2)}
.more b{display:block;font:700 22px var(--mono);color:var(--ink)}
@media (max-width:640px){
  .drift h5{font-size:24px}
  .drift .sub{font-size:14px}
  .plot{grid-template-columns:30px repeat(4,minmax(0,1fr));column-gap:6px}
  .yax span em{display:none}
  .pill{font-size:14px;padding:4px 7px}
  .pill.thick{padding:6px 8px;box-shadow:inset 0 0 0 4px var(--caution)}
  .zone{letter-spacing:0;overflow-wrap:anywhere}
  .col,.yax,.tested{height:280px}
  .col .act .v,.col .over .v{font-size:13px}
  .xl{font-size:12px}
  .brow{grid-template-columns:84px 1fr}
  .ticks{margin-left:94px}
  .verdict blockquote{font-size:21px}
  .stack .easy{font-size:16px}
  .stack .hard{font-size:13px}
  .keys{flex-direction:column;font-size:13px}
  .nrow{grid-template-columns:92px 1fr}
  .nbar{font-size:18px}
  .more{grid-template-columns:1fr}
  .rec .row,.rec .lbls{gap:8px}
  .rec .lbls{font-size:12px}
}
"""

# The case study's full math sits behind a real button inside the drift
# figure. Without JS it simply stays where it is in the text.
CHART_JS = """<script>
(function(){
  var cs=document.querySelector('.gg-case-study'), math=document.getElementById('math'), btn=document.getElementById('mathbtn');
  if(!(cs&&math&&btn)) return;
  math.appendChild(cs); math.hidden=true; btn.setAttribute('aria-expanded','false');
  btn.firstChild.nodeValue='Show the full math ';
  btn.addEventListener('click',function(){
    var open=math.hidden; math.hidden=!open; btn.setAttribute('aria-expanded',String(open));
    btn.firstChild.nodeValue=(open?'Hide':'Show')+' the full math ';
  });
})();
</script>"""


def render() -> str:
    return render_editorial_page(
        META,
        BODY_PATH.read_text(encoding="utf-8"),
        in_short=IN_SHORT,
        ladder=True,
        extra_css=CHART_CSS,
        extra_body_end=CHART_JS,
    )


def main() -> None:
    OUTPUT_PATH.write_text(render(), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH.relative_to(WORDPRESS.parent)}")


if __name__ == "__main__":
    main()
