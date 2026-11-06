"""Completeness, text preservation, offline regeneration and local image checks."""
import json
import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import import_substack_posts as imp

SOURCES = sorted(imp.SOURCES.glob('*.json'))


def test_archive_has_all_full_reprints():
    entries=json.loads((ROOT/'web/substack-index.json').read_text())
    expected={e['slug'] for e in entries if not e.get('local_url')}
    assert {s.stem for s in SOURCES} == expected
    assert len(expected)==43


@pytest.mark.parametrize('path', SOURCES, ids=lambda p:p.stem)
def test_reprint_preserves_full_source_and_regenerates_offline(path):
    meta=json.loads(path.read_text())
    body=path.with_suffix('.body.html').read_text()
    page=(imp.PAGES/meta['slug']/'index.html').read_text()
    assert page==imp.render(meta,body)
    src=BeautifulSoup(body,'html.parser')
    actual=BeautifulSoup(page,'html.parser')
    # The shell may add ids; it must preserve every paragraph, list item,
    # heading, quote, caption and table cell word for word, in reading order.
    tags=['p','li','h2','h3','h4','figcaption','td','th']
    expected=[n.get_text(' ',strip=True) for n in src.find_all(tags)]
    sections=actual.select('section.gg-blog-section')
    rendered=[n.get_text(' ',strip=True) for sec in sections for n in sec.find_all(tags)]
    assert rendered==expected
    assert len(src.get_text(' ',strip=True).split())>=int(meta['source_wordcount']*.6)
    assert not src.select('form,script,iframe,button,svg')
    assert 'substack.com/redirect/' not in body
    assert 'substack.com/action/' not in body
    for image in src.find_all('img'):
        assert image['src'].startswith('img/')
        assert (imp.PAGES/meta['slug']/image['src']).is_file()
    assert f'<link rel="canonical" href="{imp.SITE}/articles/{meta["slug"]}/">' in page
    assert 'Matti Rowe' in page and 'article_deep_read' in page


def test_partial_substack_teaser_is_rejected():
    with pytest.raises(ValueError,match='refusing teaser'):
        imp.import_post({'slug':'teaser','is_published':True,'free_unlock_required':True})
