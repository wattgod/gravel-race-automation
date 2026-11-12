// v7: engine6 unchanged (frozen v2 sim + v8 B1g plan bisection + v6 flat-bin drag factor) plus
//  (1) heat: per-bin power multiplier h(T) from Peiffer & Abbiss 2011 (17/22/27/32 C: 329/324/322/309 W), 1 at or below 17 C,
//      linear between points, held at 309/329 above 32 C (no extrapolation). Applied to the cool-day plan, then simulated without re-bisection.
//      keep = share of the loss kept (1 unacclimated; 11/48 after two weeks, Racinais et al. 2015).
//  (2) stats(): the plan's time-weighted average and NP (fourth-power mean over 25 m bins).
const EFF=0.978,G=9.80665,EDGES=[-0.08,-0.06,-0.04,-0.02,-0.01,0,0.01,0.02,0.04,0.06,0.08];
function band(g){let b=0;for(const e of EDGES)if(g>e)b++;return b}
function prep(d,o){const C=d.cols,n=C.g.length,sh=o.share||0,dc=o.dcut||0,tO=o.tempOff||0,wm=o.windMul==null?1:o.windMul,wr=o.windRot||0,B=new Array(n);
 for(let i=0;i<n;i++){const g=C.g[i],T=C.T[i]+tO,alt=C.alt[i];const pr=101325*Math.pow(1-2.25577e-5*alt,5.25588);const c=1/Math.sqrt(1+g*g);
  B[i]={g,kap:C.kap[i],ok:!!C.ok[i],rho:pr/(287.05*(T+273.15)),c,s:g*c,hw:wm*C.ws[i]*Math.cos((C.wd[i]+wr-C.h[i])*Math.PI/180),bd:band(g),df:Math.abs(g)<0.02?1-sh*dc:1,P:0,T}}return B}
function vss(o,m,cda,crr,wf){const Pe=o.P*EFF,hw=wf*o.hw,k=0.5*o.rho*cda*o.df,R=m*G*(crr*o.c+o.s);const f=v=>Pe/v-k*(v+hw)*Math.abs(v+hw)-R;
 let lo=1,hi=30;if(f(lo)<=0)return 1;if(f(hi)>=0)return 30;for(let it=0;it<50;it++){const mid=(lo+hi)/2;if(f(mid)>0)lo=mid;else hi=mid}return (lo+hi)/2}
function vlim(o,c){if(o.g>-0.02)return Infinity;return c>0?Math.sqrt(1/(c*o.kap)):Infinity}
function step(o,v,m,cda,crr,wf,L){if(v>L)v=L;let rem=25,T=0;const Pe=o.P*EFF,hw=wf*o.hw,k=0.5*o.rho*cda*o.df,R=m*G*(crr*o.c+o.s);
 while(rem>1e-6){const dt=Math.min(1,rem/v),ar=v+hw;const a=(Pe/v-k*ar*Math.abs(ar)-R)/m;v=Math.max(1,v+a*dt);if(v>L)v=L;const adv=Math.min(rem,v*dt);rem-=adv;T+=dt}return [T,v]}
function sim(B,m,cda,crr,wf,cap){const n=B.length,T=new Float64Array(n),V=new Float64Array(n);let v=1,started=false,prevOk=false;
 for(let i=0;i<n;i++){const o=B[i];if(!o.ok){prevOk=false;continue}if(!started){v=1;started=true}else if(!prevOk)v=vss(o,m,cda,crr,wf);
  const r=step(o,v,m,cda,crr,wf,cap?vlim(o,cap):Infinity);T[i]=r[0];v=r[1];V[i]=v;prevOk=true}return {T,V}}
function total(B,T){let s=0;for(let i=0;i<B.length;i++)if(B[i].ok)s+=T[i];return s}
// same bisection as v6 planW: P_i = AP*s*w[i], s bisected so the time-weighted average over ok bins equals AP
function planW(B,w,AP,m,cda,crr,wf,cap){if(!(AP>0))return {ok:false,why:"target"};const run=s=>{for(let i=0;i<B.length;i++)B[i].P=AP*s*w[i];const r=sim(B,m,cda,crr,wf,cap);let a=0,t=0;for(let i=0;i<B.length;i++)if(B[i].ok){a+=B[i].P*r.T[i];t+=r.T[i]}r.avg=t>0?a/t:NaN;r.Pw=Float64Array.from(B,o=>o.P);return r};
 return bis(run,"avg",AP,0.25,4)}
// v11 (Astra review #3): bisection that says when it fails: target outside the bracket, a non-finite statistic, or residual over 1e-3 after 60 rounds.
// Success: the run with ok:true. Failure: {ok:false, why}; callers must not show a time.
function bis(run,key,X,lo,hi){const rl=run(lo);if(!(rl[key]<=X*(1+1e-5)))return {ok:false,why:Number.isFinite(rl[key])?"bracket-low":"nan"};const rh=run(hi);if(!(rh[key]>=X*(1-1e-5)))return {ok:false,why:Number.isFinite(rh[key])?"bracket-high":"nan"};
 for(let it=0;it<60;it++){const mid=(lo+hi)/2,r=run(mid);if(!Number.isFinite(r[key]))return {ok:false,why:"nan"};if(Math.abs(r[key]-X)/X<1e-5){r.ok=true;return r}if(r[key]<X)lo=mid;else hi=mid}
 const r=run((lo+hi)/2);if(Math.abs(r[key]-X)/X<1e-3){r.ok=true;return r}return {ok:false,why:"residual"}}
const PEIFFER=[[17,1],[22,324/329],[27,322/329],[32,309/329]];
function heatMul(T){if(T<=PEIFFER[0][0])return 1;for(let i=1;i<PEIFFER.length;i++)if(T<=PEIFFER[i][0]){const a=PEIFFER[i-1],b=PEIFFER[i];return a[1]+(b[1]-a[1])*(T-a[0])/(b[0]-a[0])}return PEIFFER[PEIFFER.length-1][1]}
const ACCL_KEEP=11/48;
// heat on a finished cool-day plan r: returns a new result (r untouched); B[i].P is overwritten
function heat(B,r,keep,m,cda,crr,wf,cap){for(let i=0;i<B.length;i++)B[i].P=r.Pw[i]*(1-keep*(1-heatMul(B[i].T)));const h=sim(B,m,cda,crr,wf,cap);h.Pw=Float64Array.from(B,o=>o.P);return h}
// v11 (Astra review #1): NP is the standard one: 1 s power (each second the time-weighted mix of the bins it spans), 30 s rolling mean,
//  fourth-power mean from the first full window, fourth root. Ok bins only, joined end to end. Under 30 s of riding: np NaN (no NP exists).
function np30(B,r){const S=[];let p=0,f=0;for(let i=0;i<B.length;i++){if(!B[i].ok)continue;let rem=r.T[i];const w=r.Pw[i];
  while(rem>1e-12){const k=Math.min(rem,1-f);p+=w*k;f+=k;rem-=k;if(f>=1-1e-12){S.push(p);p=0;f=0}}}
 if(f>0.5)S.push(p/f);if(S.length<30)return NaN;let s=0,a4=0,n=0;for(let i=0;i<S.length;i++){s+=S[i];if(i>=30)s-=S[i-30];if(i>=29){a4+=Math.pow(s/30,4);n++}}return Math.pow(a4/n,0.25)}
function stats(B,r){let t=0,a=0;for(let i=0;i<B.length;i++)if(B[i].ok){t+=r.T[i];a+=r.Pw[i]*r.T[i]}return {t,ap:t>0?a/t:NaN,np:np30(B,r)}}
// v10 (planner effort = target IF): planNP bisects the same plan scale as planW, but on the plan's NP (stats(): 30 s rolling NP since v11) instead of its average.
function planNP(B,w,NP,m,cda,crr,wf,cap){if(!(NP>0))return {ok:false,why:"target"};const run=s=>{for(let i=0;i<B.length;i++)B[i].P=NP*s*w[i];const r=sim(B,m,cda,crr,wf,cap);r.Pw=Float64Array.from(B,o=>o.P);const q=stats(B,r);r.avg=q.ap;r.np=q.np;return r};
 return bis(run,"np",NP,0.1,4)}
// Default IF (IF_DEFAULTS.md §5/§6, locked by Matt 2026-11-11): IF = a - b ln(hours) per level; Beginner piecewise. h = predicted riding hours.
const IF_CURVE={elite:[0.95,0.091],advanced:[0.92,0.109],intermediate:[0.90,0.124]};
function ifDefault(level,h){if(level==="beginner"){if(h<=1)return 0.85;if(h<=2)return 0.85-(0.18/Math.LN2)*Math.log(h);return 0.67-(0.16/Math.log(8))*Math.log(h/2)}
 const c=IF_CURVE[level];if(!c)return null;return c[0]-c[1]*Math.log(h)}
// Fixed point: start at 1 h (the short end), IF from the curve, riding time from the model (secsAt(IF)), repeat until hours move < tol. Capped; ok:false if it does not settle.
function defaultIF(level,secsAt,o){o=o||{};const tol=o.tol||1/360,cap=o.cap||30;let h=1;
 for(let it=1;it<=cap;it++){const IF=ifDefault(level,h);if(IF==null||!(IF>0))return {ok:false,why:"level",it};const h2=secsAt(IF)/3600;if(!(h2>0))return {ok:false,why:"time",it};
  if(Math.abs(h2-h)<tol)return {ok:true,IF,h:h2,it};h=h2}
 return {ok:false,why:"cap",it:cap,h}}
if(typeof module!=="undefined")module.exports={np30,bis,prep,sim,planW,total,band,EDGES,heat,heatMul,ACCL_KEEP,stats,planNP,ifDefault,defaultIF,IF_CURVE};
