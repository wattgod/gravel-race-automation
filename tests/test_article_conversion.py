"""Behavior contracts for restrained article conversion surfaces."""
import json
import subprocess
import sys
from pathlib import Path

from bs4 import BeautifulSoup
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'wordpress'))
import editorial_shell as shell


@pytest.mark.parametrize('depths', [[74,75,100,0,100], [100], [25,50,75,100,100]])
def test_deep_read_once_per_page_load(depths):
    source=shell.render_article_events_js('example').removeprefix('<script>').removesuffix('</script>')
    program='''
const vm=require('node:vm');
let callbacks={},events=[];
const html={scrollTop:0,scrollHeight:2000,clientHeight:1000};
const window={pageYOffset:0,addEventListener:(name,fn)=>callbacks[name]=fn};
const document={documentElement:html,body:{scrollTop:0,scrollHeight:2000,clientHeight:1000},querySelectorAll:()=>[]};
const gtag=(kind,name,data)=>events.push({name,...data});
vm.runInNewContext(SOURCE,{window,document,gtag});
for(const depth of DEPTHS){window.pageYOffset=depth*10;callbacks.scroll();}
console.log(JSON.stringify(events));
'''.replace('SOURCE',json.dumps(source)).replace('DEPTHS',json.dumps(depths))
    result=subprocess.run(['node','-e',program],capture_output=True,text=True,check=True)
    events=json.loads(result.stdout)
    assert sum(e['name']=='article_deep_read' for e in events)==1
    assert [e['depth_threshold'] for e in events if e['name']=='article_scroll_depth']==[25,50,75,100]


def test_footer_has_one_native_newsletter_form_and_no_claimed_signup_event():
    soup=BeautifulSoup(shell.render_footer(),'html.parser')
    frames=soup.select('iframe')
    assert len(frames)==1
    assert frames[0]['src'].startswith('https://gravelgodcycling.substack.com/embed')
    assert frames[0]['title']=='Subscribe to Slow, Mid, 38s'
    assert frames[0]['loading']=='lazy'
    assert soup.select_one('a[data-label="substack_bottom"]')
    assert 'sign_up' not in shell.render_footer()


def test_relevant_offer_routes_and_personal_default():
    from article_offers import offer_for_slug,render_offer
    training=render_offer(offer_for_slug('sweet-spot-training-cycling'))
    race=render_offer(offer_for_slug('i-screwed-up-unbound-2024-so-you-dont-have-to'))
    personal=render_offer(offer_for_slug('nobody-asked-you-to-retire'))
    assert training.count('data-cta=')==1 and '/products/training-plans/' in training
    assert race.count('data-cta=')==1 and '/race/unbound-200/' in race
    assert personal==''
    assert render_offer(offer_for_slug('unknown-future-essay'))==''


def test_every_archive_page_has_one_signup_and_only_its_reviewed_offer():
    from generate_articles_index import load_essays, ARTICLES_DIR, POSTS_DIR, OUTPUT_PATH
    from article_offers import offer_for_slug,PLAN_ARTICLES,COACHING_ARTICLES,RACE_ARTICLES,GUIDE_ARTICLES
    essays=load_essays()
    known={e.slug for e in essays}
    assert set(PLAN_ARTICLES)|set(COACHING_ARTICLES)|set(RACE_ARTICLES)|set(GUIDE_ARTICLES) <= known
    for essay in essays:
        parent=ARTICLES_DIR if essay.url.startswith('/articles/') else POSTS_DIR
        page=(parent/essay.slug/'index.html').read_text()
        soup=BeautifulSoup(page,'html.parser')
        assert len(soup.select('iframe[title="Subscribe to Slow, Mid, 38s"]'))==1,essay.slug
        expected=offer_for_slug(essay.slug)
        offers=soup.select('aside.article-offer')
        assert len(offers)==(1 if expected else 0),essay.slug
        assert not soup.select('.slot-ladder'),essay.slug
        if expected:
            assert offers[0].select_one('a')['href']==expected['href']
            assert page.count("source: 'editorial'")==1
    assert OUTPUT_PATH.read_text().count('title="Subscribe to Slow, Mid, 38s"')==1


def test_commercial_click_emits_one_canonical_event_and_one_article_event():
    from blog_tracking import get_plan_intent_tracking_script
    script=shell.render_article_events_js('training')+get_plan_intent_tracking_script()
    script=script.replace('<script>','').replace('</script>','')
    program='''
const vm=require('node:vm');
let listeners=[],events=[];
const link={getAttribute:k=>({'data-cta':'custom_plan',href:'/products/training-plans/','data-label':'custom_plan'}[k]),addEventListener:(name,fn)=>listeners.push(fn)};
const window={addEventListener:()=>{},location:{pathname:'/articles/training/'}};
const document={querySelectorAll:()=>[link]};
vm.runInNewContext(SOURCE,{window,document,gtag:(kind,name,data)=>events.push({name,...data})});
for(const fn of listeners)fn();
console.log(JSON.stringify(events));
'''.replace('SOURCE',json.dumps(script))
    result=subprocess.run(['node','-e',program],capture_output=True,text=True,check=True)
    events=json.loads(result.stdout)
    assert [e['name'] for e in events].count('cta_click')==1
    assert [e['name'] for e in events].count('article_cta_click')==1
    assert not any(e['name'] in {'sign_up','generate_lead','purchase'} for e in events)
