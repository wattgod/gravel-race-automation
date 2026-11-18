"""GG×Glyph action chamfer for race-page buttons (action = chamfer, real
buttons only). Each button keeps its own border and hover colours: the clip
cuts two corners and a stroke in the border's colour (--gg-chb wide, --gg-chc)
redraws each cut edge. Focus drops the clip and strokes so the cobalt ring is
whole, as the Course Dossier does."""

CHAMFER = 'polygon(0 0,calc(100% - 10px) 0,100% 10px,100% 100%,10px 100%,0 calc(100% - 10px))'


def chamfer_css(selectors, width='var(--gg-border-width-standard)',
                colour='var(--gg-border-color-default)') -> str:
    every = ','.join(selectors)
    focus = ','.join(f'{sel}:focus-visible' for sel in selectors)
    return (f'{every}{{--gg-chb:{width};--gg-chc:{colour};border-radius:0!important;clip-path:{CHAMFER};'
            'background-image:linear-gradient(to top right,transparent calc(50% - var(--gg-chb)),var(--gg-chc) calc(50% - var(--gg-chb)),var(--gg-chc) 50%,transparent 50%),'
            'linear-gradient(to top right,transparent 50%,var(--gg-chc) 50%,var(--gg-chc) calc(50% + var(--gg-chb)),transparent calc(50% + var(--gg-chb)))!important;'
            'background-size:10px 10px!important;background-position:top right,bottom left!important;'
            'background-repeat:no-repeat!important;background-origin:border-box!important}'
            f'{focus}{{clip-path:none;background-image:none!important;outline:3px solid var(--gg-color-cobalt);outline-offset:2px}}')
