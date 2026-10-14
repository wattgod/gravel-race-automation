"""Semantic field-reference visuals shared by the three public guide generators."""
from __future__ import annotations
import html

def esc(value):
    return html.escape(str(value if value is not None else ''), quote=True)

def table(block, inline=None):
    inline = inline or esc
    headers = block.get('headers', [])
    caption = block.get('caption') or block.get('title') or 'Reference table'
    head = ''.join(f'<th scope="col">{esc(label)}</th>' for label in headers)
    rows = []
    for row in block.get('rows', []):
        cells = []
        for index, value in enumerate(row):
            label = headers[index] if index < len(headers) else ''
            tag = 'th' if index == 0 else 'td'
            scope = ' scope="row"' if index == 0 else ''
            cells.append(f'<{tag}{scope} data-label="{esc(label)}">{inline(value)}</{tag}>')
        rows.append('<tr>'+''.join(cells)+'</tr>')
    return f'<div class="guide-table-scroll" tabindex="0" role="region" aria-label="{esc(caption)}"><table class="guide-table"><caption>{inline(caption)}</caption><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'

def figure(title, body, caption='', alt='', example=False, asset_id=''):
    kind = 'Worked example' if example else 'Field reference'
    caption_html = f'<figcaption>{esc(caption)}</figcaption>' if caption else ''
    return f'<figure class="guide-reference" role="figure" data-asset-id="{esc(asset_id)}" aria-label="{esc(alt or title)}"><header><span class="guide-reference-kind">{kind}</span><h3>{esc(title)}</h3></header><div class="guide-reference-body">{body}</div>{caption_html}</figure>'

def sequence(items, inline=None):
    inline=inline or esc
    return '<ol class="guide-sequence">'+''.join(f'<li><span class="guide-sequence-number">{i:02}</span><div><h4>{esc(title)}</h4><div>{inline(copy)}</div></div></li>' for i,(title,copy) in enumerate(items,1))+'</ol>'

def bars(items, maximum, unit=''):
    rows=[]
    for label,value in items:
        if value is None:
            display='Not recorded'; width=0
        else:
            display=f'{value:g}{unit}' if isinstance(value,(int,float)) else str(value)
            width=max(0,min(100,float(value)/maximum*100))
        rows.append(f'<li><span>{esc(label)}</span><div class="guide-bar-track" aria-hidden="true"><i style="width:{width:g}%"></i></div><strong>{esc(display)}</strong></li>')
    return '<ul class="guide-bars">'+''.join(rows)+'</ul>'

def line_chart(series, labels, y_label='', x_label='Week'):
    """A common numeric axis, direct series keys, and an accessible value table."""
    width,height=880,340; left,right,top,bottom=66,30,22,62
    values=[float(v) for _,data in series for v in data]
    lo=min(0,min(values)); hi=max(values); span=hi-lo or 1
    chart_w=width-left-right; chart_h=height-top-bottom
    svg=[f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(y_label)} by {esc(x_label)}" class="guide-line-chart">']
    for tick in range(5):
        value=lo+span*tick/4; y=height-bottom-(value-lo)/span*chart_h
        svg.append(f'<line x1="{left}" y1="{y:g}" x2="{width-right}" y2="{y:g}" class="guide-chart-grid"/><text x="{left-10}" y="{y+5:g}" text-anchor="end">{value:g}</text>')
    for index,label in enumerate(labels):
        x=left+index/max(1,len(labels)-1)*chart_w
        svg.append(f'<text x="{x:g}" y="{height-bottom+25}" text-anchor="middle">{esc(label)}</text>')
    for index,(name,data) in enumerate(series):
        points=' '.join(f'{left+i/max(1,len(data)-1)*chart_w:g},{height-bottom-(float(value)-lo)/span*chart_h:g}' for i,value in enumerate(data))
        dash=['','8 5','2 4'][index%3]
        svg.append(f'<polyline points="{points}" class="guide-chart-line guide-chart-line-{index%3}" stroke-dasharray="{dash}" fill="none"/>')
    svg.append(f'<text x="{left}" y="{height-10}">{esc(x_label)} · {esc(y_label)}</text></svg>')
    keys='<div class="guide-chart-key">'+''.join(f'<span class="guide-chart-key-{i%3}">{esc(name)}</span>' for i,(name,_) in enumerate(series))+'</div>'
    data_table=table({'title':'Chart values','headers':[x_label]+[name for name,_ in series], 'rows':[[label]+[data[i] for _,data in series] for i,label in enumerate(labels)]})
    return keys+'<div class="guide-chart-scroll" tabindex="0" role="region" aria-label="Chart; scroll horizontally on a small screen">'+''.join(svg)+'</div><details class="guide-chart-data"><summary>View chart values</summary>'+data_table+'</details>'

def css(ink, paper, panel, line, accent, data_font, body_font):
    return f'''
.guide-reference,.guide-table-scroll,.guide-visual-surface {{--ref-ink:{ink};--ref-paper:{paper};--ref-panel:{panel};--ref-line:{line};--ref-accent:{accent};--ref-data:{data_font};--ref-body:{body_font}; color:var(--ref-ink);}}
.guide-reference {{ margin:36px 0; background:var(--ref-paper); border-block:2px solid var(--ref-ink); padding:24px 0; max-width:100%; }}
.guide-reference>header {{ display:block; margin-bottom:20px; }}
.guide-reference-kind {{ font:700 11px/1.4 var(--ref-data); letter-spacing:.12em; text-transform:uppercase; }}
.guide-reference h3 {{ margin:6px 0 0; font:700 clamp(22px,3vw,30px)/1.15 var(--ref-body); letter-spacing:0; text-transform:none; }}
.guide-reference figcaption {{ display:block; padding:16px 0 0; margin:18px 0 0; border-top:1px solid var(--ref-line); font:400 15px/1.5 var(--ref-body); color:var(--ref-ink); background:transparent; }}
.guide-reference-body {{ min-width:0; }}
.guide-table-scroll {{ max-width:100%; overflow:auto; margin:28px 0; }}
.guide-table {{ width:100%; border-collapse:collapse; background:var(--ref-paper); font:400 16px/1.5 var(--ref-body); color:var(--ref-ink); }}
.guide-table caption {{ text-align:left; font:700 22px/1.3 var(--ref-body); padding:0 0 14px; caption-side:top; }}
.guide-table th,.guide-table td {{ padding:16px 14px; border-bottom:1px solid var(--ref-line); vertical-align:top; text-align:left; }}
.guide-table thead th {{ border-block:2px solid var(--ref-ink); font:700 12px/1.4 var(--ref-data); letter-spacing:.04em; text-transform:uppercase; }}
.guide-table tbody th {{ font:700 16px/1.5 var(--ref-body); min-width:120px; }}
.guide-table td::before {{ display:none; }}
.guide-sequence {{ list-style:none; padding:0; margin:0; counter-reset:none; }}
.guide-sequence li {{ display:grid; grid-template-columns:48px 1fr; gap:18px; padding:20px 0; border-bottom:1px solid var(--ref-line); }}
.guide-sequence-number {{ font:700 22px/1.3 var(--ref-data); }}
.guide-sequence h4 {{ margin:0 0 6px; font:700 19px/1.3 var(--ref-body); }}
.guide-sequence li div {{ font:400 16px/1.6 var(--ref-body); }}
.guide-bars {{ list-style:none; padding:0; margin:0; }}
.guide-bars li {{ display:grid; grid-template-columns:minmax(130px,1fr) 2fr 74px; gap:16px; align-items:center; padding:12px 0; border-bottom:1px solid var(--ref-line); font:400 15px/1.5 var(--ref-data); }}
.guide-bars strong {{ text-align:right; }}
.guide-bar-track {{ height:16px; background:var(--ref-panel); border:1px solid var(--ref-line); }}
.guide-bar-track i {{ display:block; height:100%; background:var(--ref-accent); }}
.guide-chart-scroll {{ overflow:auto; max-width:100%; }}
.guide-line-chart {{ display:block; width:100%; min-width:620px; height:auto; }}
.guide-line-chart text {{ font:400 14px var(--ref-data); fill:var(--ref-ink); }}
.guide-chart-grid {{ stroke:var(--ref-line); stroke-width:1; }}
.guide-chart-line {{ stroke:var(--ref-ink); stroke-width:3; vector-effect:non-scaling-stroke; }}
.guide-chart-line-1 {{ stroke:var(--ref-accent); }}
.guide-chart-key {{ display:flex; gap:24px; flex-wrap:wrap; font:700 13px/1.5 var(--ref-data); margin:0 0 14px; }}
.guide-chart-key span::before {{ content:''; display:inline-block; width:24px; border-top:3px solid var(--ref-ink); margin-right:8px; vertical-align:middle; }}
.guide-chart-key-1::before {{ border-color:var(--ref-accent)!important; border-top-style:dashed!important; }}
.guide-chart-key-2::before {{ border-top-style:dotted!important; }}
.guide-chart-data summary {{ cursor:pointer; min-height:44px; display:flex; align-items:center; font:700 13px var(--ref-data); }}
.guide-reference a:focus-visible,.guide-chart-scroll:focus-visible,.guide-table-scroll:focus-visible,.guide-chart-data summary:focus-visible {{ outline:3px solid var(--ref-accent); outline-offset:3px; }}
@media(max-width:600px) {{
.guide-reference {{ padding:20px 0; margin:28px 0; }}
.guide-table thead {{ position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }}
.guide-table,.guide-table tbody,.guide-table tr,.guide-table td,.guide-table tbody th {{ display:block; width:100%; }}
.guide-table tr {{ border-bottom:2px solid var(--ref-ink); padding:14px 0; }}
.guide-table tbody th {{ padding:10px 0; border:0; font-size:19px; }}
.guide-table td {{ display:grid; grid-template-columns:minmax(90px,34%) 1fr; gap:14px; padding:10px 0; border-bottom:1px solid var(--ref-line); }}
.guide-table td::before {{ display:block; content:attr(data-label); font:700 11px/1.5 var(--ref-data); text-transform:uppercase; }}
.guide-bars li {{ grid-template-columns:1fr 70px; gap:8px; }}
.guide-bars li>span {{ grid-column:1/-1; }}
.guide-sequence li {{ grid-template-columns:36px 1fr; gap:12px; }}
}}
'''
