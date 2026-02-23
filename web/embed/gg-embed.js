(function(){
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
