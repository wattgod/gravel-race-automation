/* Gravel God: finish-time outlook.
 * Runs the live planner's own Web Worker (same engine, same course file,
 * same-origin) twice: the rider as typed, then the same rider with more
 * watts at the same effort (IF). Nothing leaves the page: no tracking, no
 * map tiles, no outside requests. A failed run shows no time and says why.
 */
(function () {
  "use strict";
  var root = document.getElementById("gg-sim");
  if (!root) return;
  var cfg;
  try { cfg = JSON.parse(root.querySelector(".gg-sim-config").textContent); } catch (e) { return; }

  if (document.body.classList.contains("gg-sim-embed") && window.parent !== window) {
    new ResizeObserver(function () {
      window.parent.postMessage({ type: "gg-finish-outlook:size", height: Math.ceil(root.getBoundingClientRect().height) }, "*");
    }).observe(root);
  }

  var LB = 0.45359237, MI = 1.609344;
  function q(s) { return root.querySelector(s); }
  var form = q(".gg-sim-form"), msgEl = q(".gg-sim-msg"), noteEl = q(".gg-sim-note"), sayEl = q(".gg-sim-say");
  var gainN = q(".gg-sim-gain-n"), gainU = q(".gg-sim-gain-u");
  var tBase = q(".gg-sim-t-base"), tPlus = q(".gg-sim-t-plus"), lBase = q(".gg-sim-l-base"), lPlus = q(".gg-sim-l-plus");
  var hx = q(".gg-sim-hx"), ifEl = q(".gg-sim-if"), unitBtn = q(".gg-sim-unit");
  var svg = q(".gg-sim-svg"), routeEl = q(".gg-sim-route"), trailBase = q(".gg-sim-trail--base"), trailPlus = q(".gg-sim-trail--plus");
  var mkBase = q(".gg-sim-mk--base"), mkPlus = q(".gg-sim-mk--plus"), mkPlusT = q(".gg-sim-mk-plus-t"), startEl = q(".gg-sim-start");
  var clockT = q(".gg-sim-clock-t"), playBtn = q(".gg-sim-play"), replayBtn = q(".gg-sim-replay"), scrub = q(".gg-sim-scrub");

  var GEAR_KG = cfg.bike_kg + cfg.bottles * cfg.bottle_kg;  // all-round carbon + 2 x 750 ml, no pack (the live form's defaults)
  var WHY = {
    "solve:target": "there is no effort to solve for",
    "solve:bracket-low": "the model could not find a pacing plan that low",
    "solve:bracket-high": "the model could not find a pacing plan that reaches this effort",
    "solve:nan": "the model returned no number for this course",
    "solve:residual": "the model's pacing plan did not settle on this effort",
    "solve:time": "the model returned no riding time",
    "effort:cap": "the default effort did not settle on a riding time",
    "effort:time": "the model could not find a pacing plan at the default effort",
    "effort:level": "there is no default effort for this level",
    "effort:span": "the effort range could not be worked out"
  };
  var LEVEL_NAME = { beginner: "Beginner", intermediate: "Intermediate", advanced: "Advanced", elite: "Elite" };

  /* Units: read the live planner's saved choice; never write it. */
  var units = (function () {
    try { var s = localStorage.getItem("gg_planner_units"); if (s === "imp" || s === "met") return s; } catch (e) {}
    return (navigator.language || "").toLowerCase() === "en-us" ? "imp" : "met";
  })();
  function setUnitLabel() {
    unitBtn.textContent = units === "imp" ? "lb" : "kg";
    unitBtn.setAttribute("aria-label", units === "imp" ? "Weight in pounds. Switch to kilograms" : "Weight in kilograms. Switch to pounds");
  }
  if (units === "met") form.elements.wt.value = String(+(165 * LB).toFixed(1));
  setUnitLabel();
  unitBtn.addEventListener("click", function () {
    var v = num(form.elements.wt.value), kg = v == null || isNaN(v) ? null : (units === "imp" ? v * LB : v);
    units = units === "imp" ? "met" : "imp";
    if (kg != null) form.elements.wt.value = String(+(units === "imp" ? kg / LB : kg).toFixed(1));
    setUnitLabel();
    if (last) showNote(); // distances follow the units
    request(true);
  });

  /* ---------- small helpers ---------- */
  function pad(x) { return String(x).padStart(2, "0"); }
  function hm(s) { var m = Math.round(s / 60); return Math.floor(m / 60) + ":" + pad(m % 60); }
  function dist(km) { return units === "imp" ? Math.round(km / MI) + " mi" : Math.round(km) + " km"; }
  /* null = blank; NaN = typed but not a plain number */
  function num(raw) {
    raw = String(raw == null ? "" : raw).trim();
    if (!raw) return null;
    return /^\d+([.,]\d+)?$/.test(raw) ? parseFloat(raw.replace(",", ".")) : NaN;
  }
  function setState(s) { root.setAttribute("data-state", s); }
  function markBad(name, bad) { var f = form.elements[name].closest(".gg-sim-field"); if (f) f.classList.toggle("is-bad", bad); }

  /* ---------- inputs ---------- */
  function readInputs() {
    var ftp = num(form.elements.ftp.value), w = num(form.elements.wt.value), plus = num(String(form.elements.plus.value).trim().replace(/^\+/, ""));
    var kg = w == null || isNaN(w) ? w : (units === "imp" ? w * LB : w);
    var bad = [];
    var ftpBad = !(ftp >= 80 && ftp <= 500), kgBad = !(kg >= 35 && kg <= 160);
    var plusBad = !(plus >= 1 && plus <= 100 && Math.round(plus) === plus);
    if (ftpBad) bad.push("FTP (80–500 W)");
    if (kgBad) bad.push(units === "imp" ? "weight (77–353 lb)" : "weight (35–160 kg)");
    if (plusBad) bad.push("more watts (a whole number, 1–100)");
    else if (!ftpBad && ftp + plus > 500) { plusBad = true; bad.push("more watts (FTP plus extra can't pass 500 W)"); }
    markBad("ftp", ftpBad); markBad("wt", kgBad); markBad("plus", plusBad);
    hx.textContent = plusBad ? "X" : String(plus);
    return bad.length ? { bad: bad } : { ftp: ftp, kg: kg, plus: plus };
  }
  function rider(ftp, kg, IF) {
    return { ftp: ftp, band: null, kg: kg, gearKg: GEAR_KG, hours: cfg.hours, levelPick: null,
      group: cfg.group, IF: IF == null ? null : IF, stops: null, carbs: null, heatTrained: false };
  }

  /* ---------- worker (the live planner's own) ---------- */
  var worker = null, ready = false, initFail = null, runId = 0, job = null, queued = null, geo = null, last = null;
  function boot() {
    try { worker = new Worker(cfg.worker_url); }
    catch (e) { fail("the simulator could not start in this browser"); return; }
    worker.onmessage = onMsg;
    worker.onerror = function () {
      worker.terminate();
      worker = null;
      ready = false;
      fail("the planner stopped with an error");
    };
    worker.postMessage({ type: "init", engine: cfg.engine_url, core: cfg.core_url, course: cfg.course_url });
  }
  function post(id, r, fit) {
    worker.postMessage({ type: "run", id: id, rider: r, opts: { visitorSetsEffort: !!cfg.visitor_sets_effort, edition: 0 },
      picks: { fit: fit, pos: null, stopsCut: null }, brackets: cfg.brackets });
  }
  function go(inp) {
    job = { inp: inp, stage: "base", id: ++runId };
    // fit = the planner's own "Fitness" row at the same ratio: a cross-check only
    post(job.id, rider(inp.ftp, inp.kg, null), (inp.ftp + inp.plus) / inp.ftp);
  }
  function onMsg(ev) {
    var m = ev.data || {};
    if (m.type === "init") {
      if (!m.ok) { ready = false; initFail = m.why; fail(m.why); return; }
      geo = m.geo; ready = true; fitMap();
      if (queued) { var p = queued; queued = null; go(p); }
      return;
    }
    if (m.type !== "run" || !job || m.id !== job.id) return;  // a newer request replaced this one
    if (!m.ok) { job = null; fail(m.miss ? "still needed: " + m.miss.join(", ") : (WHY[m.why] || m.why)); return; }
    if (job.stage === "base") {
      job.base = m;
      var fit = (m.rows || []).filter(function (r) { return r.key === "fit"; })[0];
      job.fitS = fit && typeof fit.saved_s === "number" ? fit.saved_s : null;
      job.stage = "plus"; job.id = ++runId;
      post(job.id, rider(job.inp.ftp + job.inp.plus, job.inp.kg, m.IF), null);  // same effort, more watts
      return;
    }
    var j = job; job = null;
    show(j.inp, j.base, m, j.fitS);
  }

  var timer = null;
  function request(now) {
    clearTimeout(timer);
    if (now) { run(); return; }
    blank();
    setState("loading");
    msgEl.textContent = "Updating the estimate…";
    timer = setTimeout(run, 450);
  }
  function run() {
    var inp = readInputs();
    if (inp.bad) { withdraw("Check " + inp.bad.join(", ") + "."); return; }
    lBase.textContent = "You · " + inp.ftp + " W";
    lPlus.textContent = "+" + inp.plus + " W · " + (inp.ftp + inp.plus) + " W";
    mkPlusT.textContent = "+" + inp.plus + " W";
    setState(last ? "busy" : "loading");
    msgEl.textContent = "Running the course…";
    if (!worker) boot();
    if (!ready) { if (initFail) { fail(initFail); return; } queued = inp; return; }
    go(inp);
  }

  /* An input problem or a failed run withdraws every number on screen. */
  function blank() {
    stop(); last = null; runId++; job = null; queued = null;
    gainN.textContent = "–"; tBase.textContent = "–:––"; tPlus.textContent = "–:––"; ifEl.textContent = "";
    gainU.textContent = "minutes saved"; noteEl.textContent = ""; sayEl.textContent = ""; clockT.textContent = "0:00"; A = B = null;
    trailBase.setAttribute("points", ""); trailPlus.setAttribute("points", "");
    controls(false);
  }
  function withdraw(text) { blank(); setState("error"); msgEl.textContent = text; }
  function fail(why) { blank(); setState("error"); msgEl.textContent = "No estimate: " + why + "."; }

  function show(inp, base, plus, fitS) {
    var gain = base.mid - plus.mid, mins = Math.round(base.mid / 60) - Math.round(plus.mid / 60);
    tBase.textContent = hm(base.mid); tPlus.textContent = hm(plus.mid);
    if (mins >= 1) { gainN.textContent = String(mins); gainU.textContent = "minutes saved"; }
    else { gainN.textContent = "0"; gainU.textContent = "min: under a minute on this course"; }
    ifEl.textContent = " (IF " + base.IF.toFixed(2) + ", the default for " + (LEVEL_NAME[base.level] || base.level) + " riders)";
    msgEl.textContent = "";
    // QA hooks for the reviewer: the planner's own Fitness row at the same ratio
    root.setAttribute("data-gain-s", String(Math.round(gain)));
    root.setAttribute("data-fit-check-s", fitS == null ? "" : String(Math.round(fitS)));
    setState("ready");
    last = { inp: inp, base: base, plus: plus };
    buildRide();
  }

  /* Fit the map to the same coordinates that drive both rides. */
  var proj = null;
  function fitMap() {
    var loMin = Math.min.apply(null, geo.lo), loMax = Math.max.apply(null, geo.lo);
    var laMin = Math.min.apply(null, geo.la), laMax = Math.max.apply(null, geo.la);
    var horizontalScale = Math.cos((laMin + laMax) / 2 * Math.PI / 180);
    var width = (loMax - loMin) * horizontalScale, height = laMax - laMin;
    var scale = Math.min(720 / (width || 1), 920 / (height || 1));
    var ox = (800 - width * scale) / 2, oy = (1000 - height * scale) / 2;
    proj = function (la, lo) { return [ox + (lo - loMin) * horizontalScale * scale, oy + (laMax - la) * scale]; };
    var d = "";
    for (var k = 0; k < geo.la.length; k++) {
      var point = proj(geo.la[k], geo.lo[k]);
      d += (k ? "L" : "M") + point[0].toFixed(1) + " " + point[1].toFixed(1);
    }
    routeEl.setAttribute("d", d);
    var start = proj(geo.la[0], geo.lo[0]);
    place(startEl, start); place(mkBase, start); place(mkPlus, start);
  }
  function place(g, xy) { g.setAttribute("transform", "translate(" + xy[0].toFixed(1) + " " + xy[1].toFixed(1) + ")"); }

  /* One rider's replay: cumulative riding seconds and position per point, from the worker's series. */
  function track(m) {
    var r = m.ride;
    if (!r || !r.mid || !r.mid.t || !r.mid.t.length) return null;
    // Scale the series so each marker reaches the line at the engine's own
    // total (the time printed in the table), not a raw sum of point times.
    var raw = r.mid.t, k = raw[raw.length - 1] > 0 ? m.mid / raw[raw.length - 1] : 1;
    var st = proj(geo.la[0], geo.lo[0]), xy = [], t = [];
    for (var i = 0; i < raw.length; i++) { t.push(raw[i] * k); xy.push(proj(r.la[i], r.lo[i])); }
    return { t: t, xy: xy, km: r.km, start: st, end: m.mid };
  }
  function at(S, t) {
    var n = S.t.length;
    if (t >= S.end) return { xy: S.xy[n - 1], i: n - 1, km: S.km[n - 1], done: true };
    var lo = 0, hi = n - 1;
    while (lo < hi) { var mid = (lo + hi) >> 1; if (S.t[mid] >= t) hi = mid; else lo = mid + 1; }
    var t0 = lo ? S.t[lo - 1] : 0, p0 = lo ? S.xy[lo - 1] : S.start, k0 = lo ? S.km[lo - 1] : 0;
    var f = S.t[lo] > t0 ? (t - t0) / (S.t[lo] - t0) : 1;
    return { xy: [p0[0] + (S.xy[lo][0] - p0[0]) * f, p0[1] + (S.xy[lo][1] - p0[1]) * f], i: lo, km: k0 + (S.km[lo] - k0) * f, done: false };
  }
  function trail(S, pos) {
    var s = S.start[0].toFixed(1) + "," + S.start[1].toFixed(1);
    for (var i = 0; i < pos.i; i++) s += " " + S.xy[i][0].toFixed(1) + "," + S.xy[i][1].toFixed(1);
    return s + " " + pos.xy[0].toFixed(1) + "," + pos.xy[1].toFixed(1);
  }

  /* ---------- replay ---------- */
  var A = null, B = null, tEnd = 0, simT = 0, playing = false, raf = 0, lastTs = 0, DUR = 12000;
  var mq = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : { matches: false };
  var visible = true, waiting = false;
  function reduced() { return !!mq.matches; }
  function controls(on) { playBtn.disabled = !on; replayBtn.disabled = !on; scrub.disabled = !on; }
  function buildRide() {
    stop();
    A = proj ? track(last.base) : null; B = proj ? track(last.plus) : null;
    if (!A || !B) { controls(false); noteEl.textContent = "The replay could not be drawn for this run; the times above still stand."; return; }
    tEnd = Math.max(A.end, B.end);
    controls(true);
    if (reduced()) { simT = Math.min(A.end, B.end); frame(); return; }
    simT = 0; frame();
    if (visible) play(); else waiting = true;
  }
  function frame() {
    var a = at(A, simT), b = at(B, simT);
    place(mkBase, a.xy); place(mkPlus, b.xy);
    trailBase.setAttribute("points", trail(A, a)); trailPlus.setAttribute("points", trail(B, b));
    clockT.textContent = hm(simT);
    scrub.value = String(Math.round(simT / tEnd * 1000));
    scrub.setAttribute("aria-valuetext", "Riding time " + hm(simT));
    showNote();
  }
  function showNote() {
    if (!A || !B || !last) return;
    var first = B.end <= A.end ? B : A, other = first === B ? A : B, plusFirst = first === B;
    var total = A.km[A.km.length - 1], tag = "+" + last.inp.plus + " W";
    var apart = Math.round(Math.abs(last.base.mid - last.plus.mid) / 60), text, say = "";
    if (simT < first.end) text = "You " + dist(at(A, simT).km) + " · " + tag + " " + dist(at(B, simT).km);
    else if (simT < other.end) {
      var back = dist(total - at(other, first.end).km);
      text = plusFirst ? tag + " finishes in " + hm(first.end) + ". You're " + back + " from the line."
        : "You finish in " + hm(first.end) + ". " + tag + " is " + back + " from the line.";
      say = text;
    } else { text = "Both home. " + apart + " min apart after " + dist(total) + "."; say = text; }
    if (noteEl.textContent !== text) noteEl.textContent = text;
    if (sayEl.textContent !== say) sayEl.textContent = say;
  }
  function loop(ts) {
    if (!playing) return;
    var dt = lastTs ? Math.min(100, ts - lastTs) : 0; lastTs = ts;
    simT = Math.min(tEnd, simT + dt / DUR * tEnd);
    frame();
    if (simT >= tEnd) { stop(); return; }
    raf = requestAnimationFrame(loop);
  }
  function play() {
    if (!A) return;
    if (simT >= tEnd) simT = 0;
    playing = true; lastTs = 0; waiting = false;
    playBtn.textContent = "Pause"; playBtn.setAttribute("aria-pressed", "true");
    cancelAnimationFrame(raf); raf = requestAnimationFrame(loop);
  }
  function stop() {
    playing = false; cancelAnimationFrame(raf);
    playBtn.textContent = "Play"; playBtn.setAttribute("aria-pressed", "false");
  }
  playBtn.addEventListener("click", function () { if (playing) stop(); else play(); });
  replayBtn.addEventListener("click", function () { simT = 0; frame(); play(); });
  scrub.addEventListener("input", function () { if (!A) return; stop(); simT = (+scrub.value / 1000) * tEnd; frame(); });
  function onMotion() { if (reduced() && playing && A && B) { stop(); simT = Math.min(A.end, B.end); frame(); } }
  if (mq.addEventListener) mq.addEventListener("change", onMotion); else if (mq.addListener) mq.addListener(onMotion);
  document.addEventListener("visibilitychange", function () { if (document.hidden && playing) stop(); });
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (es) {
      visible = es[0].isIntersecting;
      if (!visible && playing) { stop(); waiting = true; }
      else if (visible && waiting && A && !reduced()) play();
    }, { threshold: 0.25 }).observe(svg);
  }

  /* ---------- wire up ---------- */
  form.addEventListener("submit", function (e) { e.preventDefault(); request(true); });
  form.addEventListener("input", function () { request(false); });
  form.addEventListener("keydown", function (e) { if (e.key === "Enter" && e.target.tagName === "INPUT") { e.preventDefault(); request(true); } });
  // The embedded form can accept values the rider explicitly chooses to copy.
  if (document.body.classList.contains("gg-sim-embed") && window.parent !== window) {
    window.addEventListener("message", function (event) {
      var data = event.data;
      if (event.source !== window.parent || !data || data.type !== "gg-finish-outlook:baseline") return;
      var haveFtp = Number.isFinite(data.ftp) && data.ftp >= 80 && data.ftp <= 500;
      var haveWeight = Number.isFinite(data.weightKg) && data.weightKg >= 35 && data.weightKg <= 160;
      if (haveFtp) form.elements.ftp.value = String(data.ftp);
      if (haveWeight) form.elements.wt.value = String(Math.round((units === "imp" ? data.weightKg / LB : data.weightKg) * 10) / 10);
      if (haveFtp || haveWeight) {
        q(".gg-sim-eg").textContent = haveFtp && haveWeight ? "Saved FTP and weight" : haveFtp ? "Saved FTP · example weight" : "Example FTP · saved weight";
        request(false);
      }
    });
  }
  request(true);
})();
