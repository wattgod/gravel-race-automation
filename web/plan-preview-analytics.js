/* Shared custom-plan funnel. Never send search text, HR/FTP, email, or notes. */
(function(){
'use strict';
function consented(){return /(^|; )(?:gg|rl|xl|gl)_consent=accepted(?:;|$)/.test(document.cookie);}
function role(root,name){return root.querySelector('[data-role="'+name+'"]');}
function config(root){try{return JSON.parse(document.getElementById(root.dataset.configId).textContent);}catch(e){return {};}}
var allowed=['source','brand','race_slug','hours_per_week','preferred_days_count','experience_level','goal_type','control_method','preset_id','week_number','workout_kind','plan_weeks','samples_count','error_kind','search_results','has_query','second_race_enabled','grit_enabled','destination'];
window.planPreviewAnalytics=function(root,name,extra){
 if(!consented()||typeof window.gtag!=='function')return false;
 try{var cfg=config(root),race=role(root,'race'),data={source:'training_plan_simulator',brand:cfg.brand||'unknown',race_slug:race?race.value:cfg.race&&cfg.race.slug||'',plan_weeks:Number(role(root,'plan-weeks')&&role(root,'plan-weeks').value)||0,second_race_enabled:!!(role(root,'second-enable')&&role(root,'second-enable').checked)};
  if(!/^[a-z0-9-]{1,80}$/.test(data.race_slug))delete data.race_slug;
  Object.keys(extra||{}).forEach(function(key){if(key==='session_kind')data.workout_kind=extra[key];else if(allowed.indexOf(key)!==-1)data[key]=extra[key];});
  window.gtag('event',name,data);return true;
 }catch(e){return false;}
};
document.querySelectorAll('[data-training-preview]').forEach(function(root){
 if(root.dataset.analyticsReady)return;root.dataset.analyticsReady='true';var seen=false,timer=null,heading=root.querySelector('h2')||root;
 function track(name,data){return window.planPreviewAnalytics(root,name,data);}
 function view(){if(seen)return;var r=heading.getBoundingClientRect();if(r.top<innerHeight&&r.bottom>0)seen=track('plan_preview_view');}
 if(typeof IntersectionObserver==='function'){var observer=new IntersectionObserver(function(entries){if(entries.some(function(e){return e.isIntersecting;})){view();if(seen)observer.disconnect();}},{threshold:.5});observer.observe(heading);}else view();
 // Acceptance can happen after the calculator becomes visible.
 document.addEventListener('click',function(){if(!seen)setTimeout(view,0);});
 ['race-search','second-search'].forEach(function(name){var field=role(root,name);if(!field)return;field.addEventListener('input',function(){clearTimeout(timer);timer=setTimeout(function(){var select=role(root,name==='race-search'?'race':'second-race');var count=select?Array.from(select.options).filter(function(o){return o.value&&!o.hidden;}).length:0;track('plan_preview_race_search',{has_query:!!field.value.trim(),search_results:count});},350);});});
 var controls=role(root,'controls');if(controls)controls.addEventListener('change',function(event){var name=event.target.dataset.role;if(name==='race'||name==='second-race')track('plan_preview_race_select');if(name==='second-enable')track('plan_preview_second_race_toggle',{second_race_enabled:event.target.checked});if(name==='grit')track('plan_preview_grit_toggle',{grit_enabled:event.target.checked});});
 var cta=role(root,'cta');if(cta)cta.addEventListener('click',function(){var path=new URL(cta.href,location.origin).pathname;track('plan_preview_cta_click',{destination:path.indexOf('/season-plan/')!==-1?'season_plan':config(root).brand==='xc_ski_labs'?'intake':'race_plan'});});
 root.addEventListener('planpreview:ready',function(event){track('plan_preview_ready',{samples_count:event.detail.samples_count,plan_weeks:event.detail.plan_weeks});});
 root.addEventListener('planpreview:unavailable',function(event){track('plan_preview_error',{error_kind:event.detail.error_kind});});
});
})();
