"""Source for /articles/sweet-spot-training-cycling/ on the editorial shell.

The article text is the live page's, verbatim (snapshot #438), in
sweet-spot-training-cycling.body.html; this file adds the page metadata, the
"In short" claims, the chart CSS/JS for the three hand-built figures (drift,
recovery, polarized) and the shell figures placed at the body's
<!--GG:FIGURE name--> markers: the three Gravel God scenes, the Coggan
reconstruction and the studies table (FIGURES below). To add a figure, add
one line to FIGURES, e.g.

    EssayFigure(Picture.from_stem("img/meme-x", "alt text", 1200, 900), after="lmao.)</p>"),

(`after` is an exact snippet of the body file; the figure goes after the
paragraph or list that holds it.) Image files live in
wordpress/articles/sweet-spot-training-cycling/img/.

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
    DataTable,
    EssayFigure,
    HeroImage,
    OgImage,
    Picture,
    PlayOnceVideo,
    SvgFigure,
    TableCell,
    TableColumn,
    TableLink,
    TableRow,
    render_editorial_page,
)

SLUG = "sweet-spot-training-cycling"
URL = f"https://gravelgodcycling.com/articles/{SLUG}/"
BODY_PATH = HERE / f"{SLUG}.body.html"
OUTPUT_PATH = WORDPRESS / "articles" / SLUG / "index.html"
IMG_DIR = OUTPUT_PATH.parent / "img"

# ── Gravel God scenes (prototype 2026-10-09; Matt approved) ──
SCENE_TOMBSTONE = Picture.from_stem(
    "img/scene-tombstone",
    "Cartoon Gravel God stands with his head bowed beside his gravel bike at a weathered, cracked headstone "
    "engraved \"SWEET SPOT, 2004 – 2026\", with wilted flowers on the grave and a low desert sun behind.",
    1600, 1000, phone=(1130, 635),
)
SCENE_TABLET = Picture.from_stem(
    "img/scene-tablet",
    "Cartoon Gravel God stands on a rocky outcrop in the desert, arms straight up like Moses, holding a stone "
    "tablet engraved \"86–92%\" while rays of light fan out behind it.",
    1600, 1000, phone=(660, 825),
)
SCENE_BLACK_HOLE = Picture.from_stem(
    "img/scene-black-hole",
    "Cartoon Gravel God, a mustachioed rider in a white tee and denim shorts, pedals a black gravel bike down a "
    "desert road that lifts off the ground and spirals into a swirling black hole in the sky; he glances back "
    "over his shoulder, eyebrows raised in alarm.",
    1600, 1000, phone=(900, 760),
)
BLACK_HOLE_CLIP = PlayOnceVideo(
    sources=(("img/scene-black-hole.webm", "video/webm"), ("img/scene-black-hole.mp4", "video/mp4")),
    poster="img/scene-black-hole-poster.webp",
    width=1280,
    height=800,
    phone_aspect="900/760",
    phone_position="100% 0",
)

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
            "acceptedAnswer": {"@type": "Answer", "text": "Yes. Multiple studies show polarized training (75-90% below LT1, 15-20% above LT2) consistently outperforms threshold-heavy training. Neal et al. (2013) showed 8% peak power gains vs 3% for threshold. Stöggl and Sperlich (2014) found polarized improved VO2peak by 11.7%. The 2025 network meta-analysis by Rosenblat and Seiler found no significant overall difference between intensity distributions, but favored polarized training for competitive athletes."},
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
    og_image=OgImage(url=f"{URL}img/og-tombstone.jpg", width=1200, height=630),
    headline="Sweet Spot Isn’t That Sweet",
    kicker="Training · Science · Opinion",
    dek="It’s made up, it makes you slower, science hates it, the name is weird, and its marketing makes us all dumber",
    date_published=date(2026, 3, 26),
    hero=HeroImage.from_picture(SCENE_TOMBSTONE),
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
    Claim("Polarized beat threshold-heavy training in head-to-head trials. A 2025 meta-analysis found no overall winner, but favored polarized for competitive athletes.",
          "#fig-polarized", "See the studies · §07", 6),
)

# Chart internals for the three figures (drift, recovery, polarized).
CHART_CSS = """
.drift .col .act{--draw-at:150ms;--draw-dur:.75s}
.drift .col .over{--draw-at:800ms;--draw-dur:.5s}
.drift .col .v{--draw-at:1150ms;--draw-dur:.3s}
.drift .col .plan{--draw-i:0;--draw-dur:.35s}
.drift .tested{--draw-at:500ms}
.drift .cap>*{--draw-at:1250ms;--draw-dur:.4s}
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


# ── Coggan's diagram, redrawn (replaces the AI cartoon unitless-graph.png) ──
# Curves traced by eye from the diagram Hunter Allen credits to Coggan
# (hunterallenpowerblog.com, "Power Training Zones 101", 2015): x = % of FTP
# (40-150), y = arbitrary units (0-100).
COGGAN_EFFECT = ((41, 0), (55, 31), (70, 61), (80, 77), (90, 85.5), (95, 87.5), (100, 86), (110, 77),
                 (120, 61), (130, 41), (140, 19), (150, 0))
COGGAN_VOLUME = ((40, 97.5), (55, 96), (70, 92.5), (80, 88.5), (90, 84), (100, 77.5), (110, 66), (120, 50.5),
                 (130, 27), (138.5, 0))
COGGAN_STRAIN = ((40, 2.5), (55, 4.5), (70, 7.5), (80, 11), (90, 16), (100, 23), (110, 35), (120, 50), (130, 73),
                 (136, 90), (138.8, 100))
COGGAN_BANDS = (("L1", 40, 55, "#7d7aa8"), ("L2", 55, 75, "#4a78b0"), ("L3", 75, 90, "#3f9a5a"),
                ("L4", 90, 105, "#d8b62c"), ("L5", 105, 120, "#d58a3a"), ("L6", 120, 150, "#c62828"))
_INK, _INK2 = "#2a211b", "#59473c"


def _catmull(pts) -> str:
    """Catmull-Rom through the points, as cubic Béziers."""
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d


def coggan_svg() -> str:
    """The detailed diagram (720px wide on phones, panned sideways)."""
    L, T, PW, PH = 62, 34, 600, 330

    def X(v):
        return L + (v - 40) / 110 * PW

    def Y(v):
        return T + PH * (1 - v / 100)

    def P(pts):
        return _catmull([(X(a), Y(b)) for a, b in pts])

    g = [f'<svg viewBox="0 0 {L + PW + 18} {T + PH + 62}" role="img" aria-labelledby="cg-t cg-d" xmlns="http://www.w3.org/2000/svg">',
         "<title id=\"cg-t\">Reconstruction of Coggan's original diagram</title>",
         '<desc id="cg-d">Arbitrary units (0 to 100) against exercise intensity, 40 to 150 percent of functional threshold power, '
         "over training levels L1 to L6. Training effect (increase in threshold power) is an inverted U peaking near 95 percent. "
         "Maximum duration (volume) falls from about 97 at 40 percent to zero near 138 percent. Physiological strain rises slowly, "
         "then steeply, crossing maximum duration at 120 percent and 50 units. A dashed ellipse around roughly 76 to 94 percent, "
         'high on the training-effect curve, is labelled "Sweet Spot Training".</desc>',
         f'<defs><clipPath id="cg-clip"><rect x="{L}" y="{T}" width="{PW}" height="{PH}"/></clipPath>'
         '<marker id="cg-ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
         f'<path d="M0,0L10,5L0,10z" fill="{_INK}"/></marker></defs>']
    for lab, a, b, c in COGGAN_BANDS:
        g.append(f'<rect x="{X(a):.1f}" y="{T}" width="{X(b) - X(a):.1f}" height="{PH}" fill="{c}" fill-opacity=".22"/>')
        g.append(f'<text x="{(X(a) + X(b)) / 2:.1f}" y="{T + 20}" text-anchor="middle" font-size="15" font-weight="700" fill="{_INK}">{lab}</text>')
    for v in range(0, 101, 10):
        g.append(f'<line x1="{L - 5}" x2="{L}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{_INK}" stroke-width="1.5"/>'
                 f'<text x="{L - 9}" y="{Y(v) + 4.5:.1f}" text-anchor="end" font-size="13" fill="{_INK2}">{v}</text>')
    for v in range(40, 151, 10):
        g.append(f'<line x1="{X(v):.1f}" x2="{X(v):.1f}" y1="{T + PH}" y2="{T + PH + 5}" stroke="{_INK}" stroke-width="1.5"/>'
                 f'<text x="{X(v):.1f}" y="{T + PH + 21}" text-anchor="middle" font-size="13" fill="{_INK2}">{v}</text>')
    g.append(f'<path d="M{L},{T}V{T + PH}H{L + PW}" fill="none" stroke="{_INK}" stroke-width="2"/>')
    g.append(f'<text x="{L + PW / 2}" y="{T + PH + 48}" text-anchor="middle" font-size="14" font-weight="700" fill="{_INK}">'
             "Exercise intensity (% of functional threshold power)</text>")
    g.append(f'<text transform="translate(16 {T + PH / 2}) rotate(-90)" text-anchor="middle" font-size="14" font-weight="700" fill="{_INK}">Arbitrary units</text>')
    g.append('<g clip-path="url(#cg-clip)" fill="none" stroke-linecap="round">'
             f'<path d="{P(COGGAN_VOLUME)}" stroke="{_INK}" stroke-width="2"/>'
             f'<path d="{P(COGGAN_STRAIN)}" stroke="{_INK}" stroke-width="2"/>'
             f'<path d="{P(COGGAN_EFFECT)}" stroke="#1a1410" stroke-width="4"/></g>')
    g.append(f'<ellipse cx="{X(85.2):.1f}" cy="{Y(78.9):.1f}" rx="{X(99.8) - X(85.2):.1f}" ry="{Y(64.9) - Y(78.9):.1f}" '
             f'fill="none" stroke="{_INK}" stroke-width="2" stroke-dasharray="7 5"/>')
    g.append(f'<text x="{X(86):.1f}" y="{Y(59.5):.1f}" text-anchor="middle" font-size="12" font-weight="700" fill="{_INK}">"Sweet Spot Training"</text>')

    def note(lines, at, frm, to):
        out = "".join(f'<text x="{X(at[0]):.1f}" y="{Y(at[1]) + 17 * k:.1f}" text-anchor="middle" font-size="12.5" '
                      f'font-weight="700" fill="{_INK}">{t}</text>' for k, t in enumerate(lines))
        return out + (f'<line x1="{X(frm[0]):.1f}" y1="{Y(frm[1]):.1f}" x2="{X(to[0]):.1f}" y2="{Y(to[1]):.1f}" '
                      f'stroke="{_INK}" stroke-width="1.6" marker-end="url(#cg-ar)"/>')

    g.append(note(["Training effect", "(increase in threshold power)"], (60.5, 84), (62.3, 64), (66.7, 57.5)))
    g.append(note(["Physiological strain"], (95.4, 49.5), (98.6, 44), (104, 30.5)))
    g.append(note(["Maximum duration (volume)"], (114.9, 12.5), (117.8, 15.5), (128.2, 27.4)))
    g.append("</svg>")
    return "".join(g)


def coggan_phone_svg() -> str:
    """Phone overview: the whole diagram in 330 user units, labels 12.5."""
    W, L, T, PW, PH = 330, 36, 24, 284, 206
    fs = 12.5
    halo = 'paint-order="stroke" stroke="#faf6ef" stroke-width="4" stroke-linejoin="round"'

    def X(v):
        return L + (v - 40) / 110 * PW

    def Y(v):
        return T + PH * (1 - v / 100)

    def P(pts):
        return _catmull([(X(a), Y(b)) for a, b in pts])

    m = [f'<svg viewBox="0 0 {W} {T + PH + 46}" role="img" aria-labelledby="cgm-t cgm-d" xmlns="http://www.w3.org/2000/svg">',
         "<title id=\"cgm-t\">Reconstruction of Coggan's original diagram, overview</title>",
         '<desc id="cgm-d">Same diagram as the detailed version: training effect is an inverted U peaking near 95 percent of FTP; '
         "maximum duration falls from about 97 to zero near 138 percent; physiological strain rises slowly then steeply; "
         "a dashed ellipse around roughly 76 to 94 percent is labelled Sweet Spot Training.</desc>",
         f'<defs><clipPath id="cgm-clip"><rect x="{L}" y="{T}" width="{PW}" height="{PH}"/></clipPath>'
         '<marker id="cgm-ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
         f'<path d="M0,0L10,5L0,10z" fill="{_INK}"/></marker></defs>']
    for lab, a, b, c in COGGAN_BANDS:
        m.append(f'<rect x="{X(a):.1f}" y="{T}" width="{X(b) - X(a):.1f}" height="{PH}" fill="{c}" fill-opacity=".22"/>')
        m.append(f'<text x="{(X(a) + X(b)) / 2:.1f}" y="{T + 16}" text-anchor="middle" font-size="{fs}" font-weight="700" fill="{_INK}">{lab}</text>')
    for v in range(0, 101, 25):
        m.append(f'<line x1="{L - 4}" x2="{L}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{_INK}" stroke-width="1.5"/>'
                 f'<text x="{L - 6}" y="{Y(v) + 4.3:.1f}" text-anchor="end" font-size="{fs}" fill="{_INK2}">{v}</text>')
    for v in range(40, 141, 20):
        m.append(f'<line x1="{X(v):.1f}" x2="{X(v):.1f}" y1="{T + PH}" y2="{T + PH + 4}" stroke="{_INK}" stroke-width="1.5"/>'
                 f'<text x="{X(v):.1f}" y="{T + PH + 18}" text-anchor="middle" font-size="{fs}" fill="{_INK2}">{v}</text>')
    m.append(f'<path d="M{L},{T}V{T + PH}H{L + PW}" fill="none" stroke="{_INK}" stroke-width="2"/>')
    m.append(f'<text x="{L + PW / 2}" y="{T + PH + 40}" text-anchor="middle" font-size="{fs}" font-weight="700" fill="{_INK}">Intensity (% of FTP)</text>')
    m.append(f'<text transform="translate(11 {T + PH / 2}) rotate(-90)" text-anchor="middle" font-size="{fs}" font-weight="700" fill="{_INK}">Arbitrary units</text>')
    m.append(f'<g clip-path="url(#cgm-clip)" fill="none" stroke-linecap="round"><path d="{P(COGGAN_VOLUME)}" stroke="{_INK}" stroke-width="1.6"/>'
             f'<path d="{P(COGGAN_STRAIN)}" stroke="{_INK}" stroke-width="1.6"/><path d="{P(COGGAN_EFFECT)}" stroke="#1a1410" stroke-width="3.2"/></g>')
    m.append(f'<ellipse cx="{X(85.2):.1f}" cy="{Y(78.9):.1f}" rx="{X(99.8) - X(85.2):.1f}" ry="{Y(64.9) - Y(78.9):.1f}" '
             f'fill="none" stroke="{_INK}" stroke-width="1.6" stroke-dasharray="5 4"/>')

    def lab(t, at, dy=0):
        return (f'<text x="{X(at[0]):.1f}" y="{Y(at[1]) + dy:.1f}" text-anchor="middle" font-size="{fs}" '
                f'font-weight="700" fill="{_INK}" {halo}>{t}</text>')

    def arrow(frm, to):
        return (f'<line x1="{X(frm[0]):.1f}" y1="{Y(frm[1]):.1f}" x2="{X(to[0]):.1f}" y2="{Y(to[1]):.1f}" '
                f'stroke="{_INK}" stroke-width="1.4" marker-end="url(#cgm-ar)"/>')

    m.append(lab("Sweet Spot", (85.5, 57)) + lab("Training", (85.5, 57), 15))
    m.append(lab("Training", (53, 76)) + lab("effect", (53, 76), 15) + arrow((55.5, 63), (61.5, 54.5)))
    m.append(lab("Strain", (109, 47)) + arrow((109.5, 40.5), (114, 33)))
    m.append(lab("Volume", (113, 14)) + arrow((118, 17.5), (128.3, 27)))
    m.append("</svg>")
    return "".join(m)


COGGAN_FIGURE = SvgFigure(
    id="fig-graph",
    kicker="Evidence · reconstruction",
    title="Reconstruction of Coggan’s original diagram",
    svg=coggan_svg(),
    phone_svg=coggan_phone_svg(),
    phone_note_html=("Training effect = increase in threshold power &middot; Strain = physiological strain &middot; "
                     "Volume = maximum duration. Labels shortened from the original."),
    caption_html=(
        "Redrawn from the diagram Hunter Allen credits to Andy Coggan "
        '(<a href="https://www.hunterallenpowerblog.com/2015/05/power-training-zones-101.html" target="_blank" '
        'rel="noopener">Power Training Zones 101, 2015</a>). Curves traced by eye; the y-axis really is '
        "&ldquo;arbitrary units&rdquo;. "
        '<a href="img/unitless-graph.png" target="_blank" rel="noopener">The illustration this replaces</a>.'
    ),
    marker="coggan",
)

# ── The studies, side by side ──
# Numbers only from the essay or each cited abstract (verified 2026-10-09 in
# the prototype); an empty cell renders "—" = the abstract doesn't state it.
PUBMED = "https://pubmed.ncbi.nlm.nih.gov/"
STUDY_COLUMNS = (
    TableColumn("Study", width="17%", card="title"),
    TableColumn("Year", kind="num", width="8%", card="aside"),
    TableColumn("Athletes (n)", kind="num", width="15%", card="fact"),
    TableColumn("Weeks", kind="num", width="10%", card="fact"),
    TableColumn("Comparison", width="20%"),
    TableColumn("Headline result", width="30%"),
)


def _study(name, ref, year, n, n_note, weeks, weeks_html, weeks_note, comparison, result, pmid) -> TableRow:
    return TableRow(
        cells=(
            TableCell(f'{name} <sup><a href="#ref-{ref}">{ref}</a></sup>'),
            TableCell(str(year), sort=year),
            TableCell(str(n) if n != "" else "", sort=n, note_html=n_note),
            TableCell(weeks_html, sort=weeks, note_html=weeks_note),
            TableCell(comparison),
            TableCell(result),
        ),
        links=(TableLink(f"{PUBMED}{pmid}/", "abstract", f"Abstract on PubMed (ref {ref})"),),
    )


STUDIES = DataTable(
    id="fig-studies",
    kicker="The studies, side by side",
    title="What the cited papers actually tested",
    intro_html="Numbers come from each paper&rsquo;s abstract; &ldquo;&mdash;&rdquo; means the abstract doesn&rsquo;t state it.",
    footnote_html=("Zone splits are % of training time below LT1 / between / above LT2. "
                   "Meta-analyses list pooled athletes."),
    columns=STUDY_COLUMNS,
    rows=(
        _study("Neal et al.", 9, 2013, 12, "male cyclists, crossover", 6, "6", "per arm",
               "Polarized (80/0/20) vs threshold (57/43/0)",
               "Peak power +8% vs +3%; lactate threshold +9% vs +2%", "23264537"),
        _study("St&ouml;ggl &amp; Sperlich", 10, 2014, 48, "runners, cyclists, triathletes, XC skiers", 9, "9", "",
               "Polarized vs threshold vs HIIT vs high volume",
               "Polarized: VO2peak +11.7%, time to exhaustion +17.4%; threshold: slight work-economy gain only", "24550842"),
        _study("Esteve-Lanao et al.", 11, 2007, 12, "subelite runners", "", "5 mo", "weeks not stated",
               "More zone 1 (80.5/11.8/8.3) vs more zone 2 (66.8/24.7/8.5)",
               "10.4 km race: &minus;157 s vs &minus;121.5 s (p = 0.03)", "17685689"),
        _study("Rosenblat et al.", 12, 2019, "", "4 studies reviewed, 3 pooled", "", "", "",
               "Polarized vs threshold (meta-analysis)",
               "Time trial: moderate effect favouring polarized (ES &minus;0.66, 95% CI &minus;1.17 to &minus;0.15)", "29863593"),
        _study("Rosenblat, Seiler et al.", 13, 2025, 348, "13 studies; 198 competitive, 150 recreational", "", "", "",
               "Polarized vs pyramidal and other distributions (network meta-analysis)",
               "No significant difference between polarized and any other distribution; competitive athletes may "
               "benefit more from polarized, recreational from pyramidal", "39888556"),
    ),
    sort_by=1,
    marker="studies",
)

# Every shell figure on the page. Add a meme or another scene with one line.
FIGURES = (
    COGGAN_FIGURE,
    EssayFigure(SCENE_BLACK_HOLE, video=BLACK_HOLE_CLIP, marker="black-hole"),
    STUDIES,
    EssayFigure(SCENE_TABLET, marker="tablet"),
)


def render() -> str:
    return render_editorial_page(
        META,
        BODY_PATH.read_text(encoding="utf-8"),
        in_short=IN_SHORT,
        in_short_on_phone="after_intro",
        ladder=True,
        figures=FIGURES,
        extra_css=CHART_CSS,
        extra_body_end=CHART_JS,
    )


def main() -> None:
    OUTPUT_PATH.write_text(render(), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH.relative_to(WORDPRESS.parent)}")


if __name__ == "__main__":
    main()
