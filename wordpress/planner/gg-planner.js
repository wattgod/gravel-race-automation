/* Gravel God finish-time planner: page UI.
 * Reads the section's JSON config, runs estimates in a Web Worker, and
 * builds every visible node with createElement/textContent, never from markup strings.
 * A failed estimate shows no time and says why. Improvement rows are shown
 * one at a time and never added together.
 */
(function () {
  "use strict";
  var section = document.querySelector(".gg-planner");
  if (!section) return;
  var cfgEl = section.querySelector(".gg-planner-config");
  var cfg;
  try { cfg = JSON.parse(cfgEl.textContent); } catch (e) { return; }
  var form = section.querySelector(".gg-planner-form");
  var out = section.querySelector(".gg-planner-out");
  var more = section.querySelector(".gg-planner-more");
  var need = section.querySelector(".gg-planner-need");
  var band = section.querySelector(".gg-planner-band");
  var ftpField = section.querySelector('[data-power="ftp"]');

  var LB = 0.45359237, MI = 1.609344;
  var LEVEL_NAME = { beginner: "Beginner", intermediate: "Intermediate", advanced: "Advanced", elite: "Elite" };
  var units = (function () {
    try { var s = localStorage.getItem("gg_planner_units"); if (s === "imp" || s === "met") return s; } catch (e) {}
    return (navigator.language || "").toLowerCase() === "en-us" ? "imp" : "met";
  })();
  var picks = { fit: 1.05, pos: 0.20, stopsCut: 10 };
  var worker = null, geo = null, ready = false, pending = null, runId = 0, lastSent = 0, shownOnce = false, opened = false;

  /* ---------- small DOM helpers ---------- */
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      if (k === "text") n.textContent = attrs[k];
      else if (k === "cls") n.className = attrs[k];
      else n.setAttribute(k, attrs[k]);
    }
    (kids || []).forEach(function (c) { if (c) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }
  var SVG = "http://www.w3.org/2000/svg";
  function sv(tag, attrs) { var n = document.createElementNS(SVG, tag); for (var k in attrs) n.setAttribute(k, attrs[k]); return n; }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function pad(x) { return String(x).padStart(2, "0"); }
  function hm(s) { var m = Math.round(s / 60); return Math.floor(m / 60) + ":" + pad(m % 60); }
  function mins(s) { return Math.round(s / 60); }
  function dist(km) { return units === "imp" ? Math.round(km / MI) + " mi" : Math.round(km) + " km"; }
  function temp(c) { return units === "imp" ? Math.round(c * 9 / 5 + 32) + "°F" : Math.round(c) + "°C"; }
  /* null = left blank; NaN = typed but not a plain number (never read as blank). */
  function num(name) {
    var f = form.elements[name]; if (!f) return null;
    var raw = String(f.value || "").trim();
    if (!raw) return null;
    return /^\d+([.,]\d+)?$/.test(raw) ? parseFloat(raw.replace(",", ".")) : NaN;
  }
  function radio(name) { var f = form.querySelector('input[name="' + name + '"]:checked'); return f ? f.value : null; }

  /* ---------- units ---------- */
  var MASS = ["kg", "bikekg", "geartot"];
  function setUnits(u) {
    var held = MASS.map(function (n) { return mass(n); });
    units = u;
    try { localStorage.setItem("gg_planner_units", u); } catch (e) {}
    section.querySelectorAll("[data-units]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-units") === u)); });
    section.querySelectorAll('[data-unit="weight"]').forEach(function (n) { n.textContent = u === "imp" ? "lb" : "kg"; });
    MASS.forEach(function (n, i) {
      var v = held[i];
      if (v != null && !isNaN(v) && form.elements[n]) form.elements[n].value = String(+(u === "imp" ? v / LB : v).toFixed(1));
    });
    if (lastResult) render(lastResult);
  }
  /* A weight field in kg: null when blank, NaN when not a number. */
  function mass(name) { var v = num(name); if (v == null || isNaN(v)) return v; return units === "imp" ? v * LB : v; }
  function readKg() { return mass("kg"); }

  /* ---------- worker ---------- */
  function start() {
    if (worker) return;
    try { worker = new Worker(cfg.worker_url); }
    catch (e) { fail("the planner could not start in this browser"); return; }
    worker.onmessage = function (ev) {
      var m = ev.data;
      if (m.type === "init") {
        if (!m.ok) { ready = false; failInit = m.why; if (pending) fail(m.why); return; }
        geo = m.geo; ready = true;
        if (pending) { var p = pending; pending = null; send(p); }
        return;
      }
      if (m.type === "run" && m.id === runId) {
        if (m.ok) { lastResult = m; render(m); announce(m); }
        else if (m.miss) { showNeed(m.miss); withdraw(); }
        else fail(m.why);
      }
    };
    worker.onerror = function () { fail("the planner stopped with an error"); };
    worker.postMessage({ type: "init", engine: cfg.engine_url, core: cfg.core_url, course: cfg.course_url });
  }
  var failInit = null, lastResult = null;

  function rider() {
    var noftp = form.elements.noftp.checked;
    var bikeId = radio("bike"), bikeKg = null;
    if (bikeId === "own") bikeKg = mass("bikekg");
    else { var bike = cfg.bikes.filter(function (b) { return b.id === bikeId; })[0]; bikeKg = bike ? bike.kg : null; }
    var bottles = num("bottles"), bt = cfg.bottles[+form.elements.bottle.value], pk = radio("pack");
    var packKg = pk && pk !== "none" && cfg.packs[+pk] ? cfg.packs[+pk].kg : 0;
    var tot = mass("geartot"), gearKg = null;
    if (tot != null) gearKg = tot;
    else if (bikeKg != null && !isNaN(bikeKg) && bt && bottles != null && bottles >= 0 && bottles <= 4 && Math.round(bottles) === bottles)
      gearKg = bikeKg + bottles * bt.kg + packKg;
    return {
      ftp: noftp ? null : num("ftp"),
      band: noftp && radio("band") ? { sex: radio("sex") || "m", name: radio("band") } : null,
      kg: readKg(), gearKg: gearKg, hours: radio("hours"), levelPick: radio("level") || null,
      group: radio("group"), IF: num("if"), stops: num("stops"), carbs: num("carbs"),
      heatTrained: form.elements.heat.checked
    };
  }

  /* Typed values that are not usable. Each is named; none is quietly dropped. */
  function invalid(r) {
    var bad = [], typed = function (v) { return v != null; };
    if (!form.elements.noftp.checked && typed(r.ftp) && !(r.ftp >= 80 && r.ftp <= 500)) bad.push("FTP (80–500 W)");
    if (typed(r.kg) && !(r.kg >= 35 && r.kg <= 160)) bad.push(units === "imp" ? "weight (77–353 lb)" : "weight (35–160 kg)");
    if (typed(r.IF) && !(r.IF >= 0.40 && r.IF <= 1.05)) bad.push("effort (IF 0.40–1.05)");
    if (typed(r.stops) && !(r.stops >= 0 && r.stops <= 600)) bad.push("time stopped (0–600 min)");
    if (typed(r.carbs) && !(r.carbs >= 0 && r.carbs <= 200)) bad.push("carbs an hour (0–200 g)");
    var bottles = num("bottles"), bk = mass("bikekg"), tot = mass("geartot");
    if (tot == null) {  // a typed total replaces the bike and water fields
      if (bottles != null && !(bottles >= 0 && bottles <= 4 && Math.round(bottles) === bottles)) bad.push("bottles (0–4)");
      if (radio("bike") === "own" && bk != null && !(bk >= 5 && bk <= 25)) bad.push(units === "imp" ? "bike weight (11–55 lb)" : "bike weight (5–25 kg)");
    }
    if (tot != null && !(tot >= 5 && tot <= 45)) bad.push(units === "imp" ? "total for bike, water and gear (11–99 lb)" : "total for bike, water and gear (5–45 kg)");
    return bad;
  }

  function localMiss(r) {
    var m = [];
    if (r.ftp == null && !r.band) m.push(form.elements.noftp.checked ? "a power band" : "your FTP");
    if (r.kg == null) m.push("your weight");
    if (!r.hours) m.push("hours a week you can train");
    if (!r.group) m.push("who you'll ride with");
    if (mass("geartot") == null) {
      if (!radio("bike")) m.push("your bike");
      else if (radio("bike") === "own" && mass("bikekg") == null) m.push("your bike's weight");
      if (num("bottles") == null) m.push("bottles (0–4)");
    }
    if (cfg.visitor_sets_effort && r.IF == null) m.push("your effort (IF)");
    return m;
  }

  function showNeed(list, bad) {
    var parts = [];
    if (bad && bad.length) parts.push("Check " + bad.join(", ") + ".");
    if (list && list.length) parts.push("Still needed: " + list.join(", ") + ".");
    need.textContent = parts.join(" ");
  }

  /* An input problem withdraws any time on screen: an old result never
     stands in for the inputs now in the form. */
  function withdraw() {
    stopAnim(); runId++; pending = null; lastResult = null;
    clear(out); out.hidden = true; out.removeAttribute("aria-busy");
  }

  function run() {
    if (!opened) { opened = true; more.hidden = false; }
    var r = rider(), bad = invalid(r), miss = localMiss(r);
    showNeed(miss, bad);
    if (miss.length || bad.length) { withdraw(); return; }
    start();
    var msg = { type: "run", rider: r, opts: { visitorSetsEffort: cfg.visitor_sets_effort, edition: 0 },
      picks: picks, brackets: cfg.brackets };
    working();
    if (!ready) { if (failInit) { fail(failInit); return; } pending = msg; return; }
    send(msg);
  }
  function send(msg) { msg.id = ++runId; lastSent = Date.now(); worker.postMessage(msg); }

  function working() {
    out.hidden = false;
    if (!lastResult) { clear(out); out.appendChild(el("div", { cls: "gg-planner-card" }, [el("p", { text: "Running the course…" })])); }
    else out.setAttribute("aria-busy", "true");
  }

  var WHY = {
    "solve:target": "there is no effort to solve for",
    "solve:bracket-low": "the model could not find a pacing plan that low",
    "solve:bracket-high": "the model could not find a pacing plan that reaches this effort",
    "solve:nan": "the model returned no number for this course",
    "solve:residual": "the model's pacing plan did not settle on your effort",
    "solve:time": "the model returned no riding time",
    "effort:cap": "your default effort did not settle on a riding time; type your own effort (IF) to see a time",
    "effort:time": "the model could not find a pacing plan at your default effort; type your own effort (IF)",
    "effort:level": "there is no default effort for this level",
    "effort:span": "the effort range could not be worked out"
  };
  function fail(why) {
    stopAnim(); lastResult = null; out.hidden = false; out.removeAttribute("aria-busy"); clear(out);
    out.appendChild(el("div", { cls: "gg-planner-card gg-planner-fail" }, [
      el("p", { cls: "gg-planner-eyebrow", text: "No estimate" }),
      el("p", { text: "No time is shown because " + (WHY[why] || why) + ". We show nothing rather than a guess." })
    ]));
  }

  /* ---------- analytics (manual interaction only; consent mode applies) ---------- */
  function announce(m) {
    if (typeof gtag !== "function") return;
    gtag("event", cfg.events.result, {
      race_slug: cfg.slug, level: m.level, effort_source: m.IFsource,
      power_input: form.elements.noftp.checked ? "band" : "ftp", planner_status: cfg.status
    });
  }

  /* ---------- result ---------- */
  function render(m) {
    stopAnim();
    out.hidden = false; out.removeAttribute("aria-busy"); clear(out);
    var stops = rider().stops;
    var lo = Math.min(m.fast, m.slow), hi = Math.max(m.fast, m.slow);
    var edYear = String(m.edition.date).slice(0, 4);

    var head = el("div", { cls: "gg-planner-card" });
    head.appendChild(el("p", { cls: "gg-planner-eyebrow", text: "Riding time · estimate · " + cfg.edition_short }));
    head.appendChild(el("div", { cls: "gg-planner-big", text: hm(lo) + "–" + hm(hi) }));
    head.appendChild(el("p", { text: stops != null
      ? "Riding time, plus your " + Math.round(stops) + " min stopped: finish " + hm(lo + stops * 60) + "–" + hm(hi + stops * 60) + "."
      : "Riding time only, plus your stops. Add your stopped minutes above to see a finish time." }));
    head.appendChild(el("p", { cls: "gg-planner-fine", text: "Middle of the range: " + hm(m.mid) + " of riding at your effort. " + cfg.weather_line }));
    var span = m.span, ifTxt = function (x) { return x.toFixed(2); };
    var spanTxt = "Range: if you ride a level easier or harder than " +
      (m.IFsource === "set" ? "the effort you typed" : "your level's default effort") +
      " (IF " + ifTxt(span.slow) + " to " + ifTxt(span.fast) + ", same effort curves)" +
      (m.ftp.lo !== m.ftp.hi ? ", across your band's FTP (" + Math.round(m.ftp.lo) + "–" + Math.round(m.ftp.hi) + " W)" : "") +
      ". It is not an accuracy figure.";
    head.appendChild(el("p", { cls: "gg-planner-fine", text: spanTxt }));
    cfg.notes.forEach(function (n) { head.appendChild(el("p", { cls: "gg-planner-flag", text: n.charAt(0).toUpperCase() + n.slice(1) + "." })); });
    var effort = "Effort: IF " + m.IF.toFixed(2) + ", normalized power " + Math.round(m.np) + " W on an FTP of " + Math.round(m.ftp.mid) + " W" +
      (m.ftp.lo !== m.ftp.hi ? " (the middle of your band)" : "") + ". ";
    effort += m.IFsource === "set" ? "The effort you typed." + (m.defaultIF ? "" : "") :
      "Gravel God's default for " + LEVEL_NAME[m.level] + " riders on a ride of " + hm(m.mid) + ", built from published race power and coaching judgement. Type your own in Effort (IF) to change it.";
    head.appendChild(el("p", { cls: "gg-planner-fine", text: effort }));
    var edit = el("button", { type: "button", cls: "gg-planner-edit", text: "Change effort" });
    edit.addEventListener("click", function () { form.elements["if"].value = m.IF.toFixed(2); form.elements["if"].focus(); });
    head.appendChild(edit);
    out.appendChild(head);

    if (geo) out.appendChild(mapCard(m));
    out.appendChild(fuelCard(m, stops));
    out.appendChild(rowsCard(m));
    if (cfg.offer) out.appendChild(offerCard(m));
    out.appendChild(finePrint(m));
  }

  /* ---------- your ride: map, profile, replay and scrub ----------
     Everything drawn here comes from the model runs for this rider. The two
     pins are the fast and slow ends of the range at the same moment. */
  var anim = null;
  function stopAnim() { if (anim) { cancelAnimationFrame(anim.raf); anim = null; } }
  function reducedMotion() { try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { return false; } }
  function idxAt(arr, v) { var lo = 0, hi = arr.length - 1; if (v <= arr[0]) return 0; while (lo < hi) { var md = (lo + hi) >> 1; if (arr[md] < v) lo = md + 1; else hi = md; } return lo; }
  /* Riding seconds at a distance, from cumulative end-of-point times. */
  function timeAt(R, run, km) {
    var j = idxAt(R.km, km), k0 = j ? R.km[j - 1] : 0, t0 = j ? run.t[j - 1] : 0;
    var f = R.km[j] > k0 ? Math.max(0, Math.min(1, (km - k0) / (R.km[j] - k0))) : 1;
    return t0 + f * (run.t[j] - t0);
  }
  /* Distance reached after a number of riding seconds. */
  function kmAt(R, run, sec) {
    if (sec >= run.t[run.t.length - 1]) return R.km[R.km.length - 1];
    var j = idxAt(run.t, sec), t0 = j ? run.t[j - 1] : 0, k0 = j ? R.km[j - 1] : 0;
    var f = run.t[j] > t0 ? (sec - t0) / (run.t[j] - t0) : 1;
    return k0 + f * (R.km[j] - k0);
  }
  function powerClass(w, ap) {
    if (w == null) return "gg-planner-p0";
    var r = w / ap;
    return r < 0.85 ? "gg-planner-p1" : r < 1.15 ? "gg-planner-p2" : r < 1.45 ? "gg-planner-p3" : "gg-planner-p4";
  }
  function dist1(km) { return units === "imp" ? (km / MI).toFixed(1) + " mi" : km.toFixed(1) + " km"; }
  function speedTxt(ms) { var kmh = Math.abs(ms) * 3.6; return units === "imp" ? Math.round(kmh / MI) + " mph" : Math.round(kmh) + " km/h"; }
  function rng(a, b, f) { var x = f(Math.min(a, b)), y = f(Math.max(a, b)); return x === y ? x : x + "–" + y; }

  function mapCard(m) {
    var R = m.ride, edYear = String(m.edition.date).slice(0, 4);
    var card = el("div", { cls: "gg-planner-card gg-planner-ride" });
    var headRow = el("div", { cls: "gg-planner-ridehead" }, [el("h3", { text: "Your " + cfg.race })]);
    var play = null;
    if (R) { play = el("button", { type: "button", cls: "gg-planner-edit", "aria-pressed": "false", text: "Replay" }); headRow.appendChild(play); }
    card.appendChild(headRow);
    var wrap = el("div", { cls: "gg-planner-map" });
    var la0 = Math.min.apply(null, geo.la), la1 = Math.max.apply(null, geo.la), lo0 = Math.min.apply(null, geo.lo), lo1 = Math.max.apply(null, geo.lo);
    var kx = Math.cos((la0 + la1) / 2 * Math.PI / 180), w = (lo1 - lo0) * kx || 1e-6, h = (la1 - la0) || 1e-6, S = 280 / Math.max(w, h);
    var W = Math.max(40, w * S) + 20, H = Math.max(40, h * S) + 20;
    var X = function (lo) { return 10 + (lo - lo0) * kx * S; }, Y = function (la) { return 10 + (la1 - la) * S; };
    var map = sv("svg", { viewBox: "0 0 " + W.toFixed(0) + " " + H.toFixed(0), role: "img", "aria-label": "Course map with your position at each riding hour" });
    var d = geo.la.map(function (la, i) { return (i ? "L" : "M") + X(geo.lo[i]).toFixed(1) + " " + Y(la).toFixed(1); }).join("");
    map.appendChild(sv("path", { d: d, "class": "gg-planner-route" }));
    m.hours.forEach(function (p) { map.appendChild(sv("circle", { cx: X(p.lo).toFixed(1), cy: Y(p.la).toFixed(1), r: 4, "class": "gg-planner-dot" })); });
    var pinSlow = sv("circle", { r: 7, "class": "gg-planner-pin gg-planner-pin-slow" });
    var pinFast = sv("circle", { r: 7, "class": "gg-planner-pin gg-planner-pin-fast" });
    if (R) { map.appendChild(pinSlow); map.appendChild(pinFast); }
    wrap.appendChild(map);

    // A narrower drawing on phones keeps labels readable and the slider tall enough to touch.
    var PW = section.clientWidth && section.clientWidth < 560 ? 360 : 600, PH = 170, T = geo.total_km;
    var a0 = Math.min.apply(null, geo.alt), a1 = Math.max.apply(null, geo.alt);
    var px = function (km) { return 30 + km / T * (PW - 40); }, py = function (a) { return PH - 22 - (a - a0) / ((a1 - a0) || 1) * (PH - 44); };
    var prof = sv("svg", { viewBox: "0 0 " + PW + " " + PH, "class": "gg-planner-profile" });
    var cursor = null, clipRect = null;
    if (R) {
      var clipId = "gg-planner-clip-" + cfg.slug;
      var defs = sv("defs", {}), clip = sv("clipPath", { id: clipId });
      clipRect = sv("rect", { x: 0, y: 0, width: px(0), height: PH }); clip.appendChild(clipRect); defs.appendChild(clip); prof.appendChild(defs);
      var ahead = sv("g", { "class": "gg-planner-ahead" }), done = sv("g", { "clip-path": "url(#" + clipId + ")" });
      for (var j = 0; j < R.km.length; j++) {
        var xa = px(j ? R.km[j - 1] : 0), xb = px(R.km[j]) + 0.6, y = py(R.alt[j]);
        var attrs = { x: xa.toFixed(1), y: y.toFixed(1), width: Math.max(0.6, xb - xa).toFixed(1), height: Math.max(0, PH - 22 - y).toFixed(1) };
        var cls = powerClass(R.mid.w[j], m.apRide);
        ahead.appendChild(sv("rect", Object.assign({ "class": cls }, attrs)));
        done.appendChild(sv("rect", Object.assign({ "class": cls }, attrs)));
      }
      prof.appendChild(ahead); prof.appendChild(done);
      prof.setAttribute("tabindex", "0"); prof.setAttribute("role", "slider");
      prof.setAttribute("aria-label", "Position on the course. Arrow keys move along it.");
      prof.setAttribute("aria-valuemin", "0"); prof.setAttribute("aria-valuemax", String(Math.round(T * 10) / 10));
    } else {
      var pd = "M" + px(0) + " " + (PH - 22) + geo.km.map(function (k, i) { return "L" + px(k).toFixed(1) + " " + py(geo.alt[i]).toFixed(1); }).join("") + "L" + px(T) + " " + (PH - 22) + "Z";
      prof.appendChild(sv("path", { d: pd, "class": "gg-planner-prof" }));
      prof.setAttribute("role", "img"); prof.setAttribute("aria-label", "Elevation profile with riding hours marked");
    }
    var every = m.hours.length > 10 ? 2 : 1, lastX = -1e9;
    m.hours.forEach(function (p) {
      if (p.h % every && p.h !== m.hours.length) return;
      var xn = px(Math.min(p.km, T));
      if (xn - lastX < 28) return;
      lastX = xn;
      var x = xn.toFixed(1);
      prof.appendChild(sv("line", { x1: x, x2: x, y1: 14, y2: PH - 22, "class": "gg-planner-tick" }));
      var t = sv("text", { x: x, y: 11, "text-anchor": "middle", "class": "gg-planner-tlabel" }); t.textContent = "h" + p.h; prof.appendChild(t);
    });
    var lbl = function (x, y, s, anchor) { var t = sv("text", { x: x, y: y, "class": "gg-planner-tlabel", "text-anchor": anchor || "start" }); t.textContent = s; prof.appendChild(t); };
    lbl(2, py(a1) + 4, units === "imp" ? Math.round(a1 * 3.28084) + " ft" : Math.round(a1) + " m");
    lbl(2, PH - 24, units === "imp" ? Math.round(a0 * 3.28084) + " ft" : Math.round(a0) + " m");
    lbl(PW - 4, PH - 6, dist(T), "end");
    if (R) { cursor = sv("line", { x1: px(0), x2: px(0), y1: 14, y2: PH - 22, "class": "gg-planner-cursor" }); prof.appendChild(cursor); }
    wrap.appendChild(prof);
    card.appendChild(wrap);

    if (!R) {
      card.appendChild(el("p", { cls: "gg-planner-fine", text: "Dots: where the middle of your range is at the end of each riding hour. The replay is not shown: the model could not lay out your ride point by point." }));
      return card;
    }
    // Not a live region: it changes every frame during Replay. Keyboard and
    // screen-reader users get the same text through the slider's valuetext.
    var readout = el("p", { cls: "gg-planner-readout", "aria-live": "off" });
    card.appendChild(readout);
    card.appendChild(el("p", { cls: "gg-planner-fine", text: "Dots: the middle of your range at the end of each riding hour. Filled pin: the fast end of your range; open pin: the slow end, at the same moment. Profile colour: planned power against your day's average, from easy (light teal) to hardest (dark brown); grey where the course has no riding data. Wind and temperature are the " + edYear + " race day's at that time, not a forecast. Route and elevation from the race's public Ride with GPS route." }));

    var endT = R.slow.t[R.slow.t.length - 1];
    function setMoment(sec, kmCursor) {
      var kc = kmCursor != null ? kmCursor : kmAt(R, R.mid, sec);
      var kf = kmAt(R, R.fast, sec), ks = kmAt(R, R.slow, sec);
      var jf = idxAt(R.km, kf), js = idxAt(R.km, ks);
      pinFast.setAttribute("cx", X(R.lo[jf]).toFixed(1)); pinFast.setAttribute("cy", Y(R.la[jf]).toFixed(1));
      pinSlow.setAttribute("cx", X(R.lo[js]).toFixed(1)); pinSlow.setAttribute("cy", Y(R.la[js]).toFixed(1));
      var x = px(kc).toFixed(1);
      cursor.setAttribute("x1", x); cursor.setAttribute("x2", x); clipRect.setAttribute("width", x);
      var j = idxAt(R.km, kc), tf = timeAt(R, R.fast, kc), ts = timeAt(R, R.slow, kc);
      var wf = R.fast.w[j], ws = R.slow.w[j], hw = R.hw[j];
      var parts = [dist1(kc), (units === "imp" ? Math.round(R.alt[j] * 3.28084) + " ft" : Math.round(R.alt[j]) + " m") + " · " + (R.grade[j] * 100).toFixed(1) + "%",
        "riding time " + rng(tf, ts, hm),
        wf == null || ws == null ? "no riding power here" : "about " + rng(wf, ws, Math.round) + " W",
        (Math.abs(hw) * 3.6 < 1 ? "calm" : speedTxt(hw) + " " + (hw > 0 ? "headwind" : "tailwind")) + ", " + temp(R.temp[j]) + " on the " + edYear + " race day"];
      readout.textContent = parts.join(" · ");
      prof.setAttribute("aria-valuenow", String(Math.round(kc * 10) / 10));
      prof.setAttribute("aria-valuetext", readout.textContent);
    }
    function scrubKm(km) { stopAnim(); play.setAttribute("aria-pressed", "false"); play.textContent = "Replay"; km = Math.max(0, Math.min(T, km)); setMoment(timeAt(R, R.mid, km), km); }
    function finish() { setMoment(endT, T); }
    finish();

    play.addEventListener("click", function () {
      if (anim) { stopAnim(); play.setAttribute("aria-pressed", "false"); play.textContent = "Replay"; return; }
      if (reducedMotion()) { finish(); return; }
      var t0 = null, DUR = 8000;
      play.setAttribute("aria-pressed", "true"); play.textContent = "Stop";
      anim = { raf: 0 };
      var tick = function (now) {
        if (!anim) return;
        if (t0 == null) t0 = now;
        var f = Math.min(1, (now - t0) / DUR), e = f < 0.5 ? 2 * f * f : 1 - Math.pow(-2 * f + 2, 2) / 2;
        setMoment(e * endT);
        if (f < 1) anim.raf = requestAnimationFrame(tick);
        else { anim = null; play.setAttribute("aria-pressed", "false"); play.textContent = "Replay"; finish(); }
      };
      anim.raf = requestAnimationFrame(tick);
    });
    function profKm(ev) { var r = prof.getBoundingClientRect(); var xv = (ev.clientX - r.left) / r.width * PW; return (xv - 30) / (PW - 40) * T; }
    prof.addEventListener("pointerdown", function (ev) { try { prof.setPointerCapture(ev.pointerId); } catch (e) {} scrubKm(profKm(ev)); });
    prof.addEventListener("pointermove", function (ev) { if (ev.buttons) scrubKm(profKm(ev)); });
    prof.addEventListener("keydown", function (ev) {
      var unit = units === "imp" ? MI : 1, cur = parseFloat(prof.getAttribute("aria-valuenow")) || 0, step = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1, PageUp: 10, PageDown: -10 }[ev.key];
      if (step) { ev.preventDefault(); scrubKm(cur + step * unit); }
      else if (ev.key === "Home") { ev.preventDefault(); scrubKm(0); }
      else if (ev.key === "End") { ev.preventDefault(); scrubKm(T); }
    });
    function mapKm(ev) {
      var r = map.getBoundingClientRect(), vb = map.viewBox.baseVal;
      var x = (ev.clientX - r.left) / r.width * vb.width, y = (ev.clientY - r.top) / r.height * vb.height, best = 0, bd = Infinity;
      for (var j = 0; j < R.km.length; j++) { var dx = X(R.lo[j]) - x, dy = Y(R.la[j]) - y, dd = dx * dx + dy * dy; if (dd < bd) { bd = dd; best = j; } }
      return R.km[best];
    }
    map.addEventListener("pointerdown", function (ev) { try { map.setPointerCapture(ev.pointerId); } catch (e) {} scrubKm(mapKm(ev)); });
    map.addEventListener("pointermove", function (ev) { if (ev.buttons) scrubKm(mapKm(ev)); });

    card.appendChild(paceNotes(m));
    return card;
  }

  function paceNotes(m) {
    var P = m.pace, ul = el("ul", { cls: "gg-planner-pace" });
    if (!P) { ul.appendChild(el("li", { text: "Pacing notes are not shown: the model could not work them out for this ride." })); return ul; }
    var why = P.why || {}, ftpTyped = rider().ftp != null, W = Math.round(P.ap) + " W";
    if (P.over && P.over.t >= 60) {
      var lg = Math.ceil(P.over.longest / 60);
      ul.appendChild(el("li", { text: "This plan has you above your FTP for about " + mins(P.over.t) + " minutes in total, in " + P.over.n + " short efforts on climbs, none longer than " + lg + " minute" + (lg > 1 ? "s" : "") + "." }));
    } else if (P.flat_s != null) {
      var lead = P.flat_s >= 30 ? "Pushing the climbs and easing the descents the way this plan does is worth about " + mins(P.flat_s) + " minutes over holding " + W + " (your ride's average) all day."
        : P.flat_s <= -30 ? "Holding " + W + " (your ride's average) all day would be about " + mins(-P.flat_s) + " minutes quicker than this plan's pacing on this course."
        : "Holding " + W + " (your ride's average) all day comes out within a minute of this plan's pacing on this course.";
      var ftpNote = "";
      if (ftpTyped && P.over) ftpNote = P.over.t === 0 ? " At this effort the plan never takes you above your FTP." : " At this effort the plan is above your FTP for under a minute in total.";
      ul.appendChild(el("li", { text: lead + ftpNote }));
    } else {
      ul.appendChild(el("li", { text: "The even-pacing comparison is not shown: " + (why.flat || "the model could not work it out") + "." }));
    }
    ul.appendChild(el("li", { text: P.r46 != null ? "On 4–6% grades this plan rides at about " + P.r46.toFixed(1) + "× your ride's average power."
      : "No 4–6% figure: " + (why.r46 || "the model could not work it out") + "." }));
    if (P.climb) {
      var c = P.climb, len = units === "imp" ? (c.len_m / 1609.344).toFixed(1) + " mi" : (c.len_m / 1000).toFixed(1) + " km";
      var tx = "Your longest climb starts at " + dist(c.start_km) + " (" + len + " at " + (c.grade * 100).toFixed(1) + "%): " + (c.t < 60 ? "under a minute" : "about " + mins(c.t) + " minutes");
      tx += P.climb_watts_shown ? " at about " + Math.round(c.w) + " W." : ". Climb watts aren't printed at this effort: it is outside the range of race efforts the climb pacing was built from.";
      ul.appendChild(el("li", { text: tx }));
    } else {
      ul.appendChild(el("li", { text: "No longest-climb note: " + (why.climb || "the model could not work it out") + "." }));
    }
    ul.appendChild(el("li", { cls: "gg-planner-fine", text: "All at the middle of your range, from the same model run as your time." }));
    return ul;
  }

  function fuelFor(seconds) {
    var h = seconds / 3600, b = cfg.brackets[cfg.brackets.length - 1];
    for (var i = 0; i < cfg.brackets.length; i++) if (h <= cfg.brackets[i][0]) { b = cfg.brackets[i]; break; }
    return { lo: b[1], hi: b[2], label: b[3], weeks: b[4], tlo: Math.round(h * b[1]), thi: Math.round(h * b[2]) };
  }

  function fuelCard(m, stops) {
    var day = m.mid + (stops || 0) * 60, F = fuelFor(day);
    var card = el("div", { cls: "gg-planner-card" }, [el("h3", { text: "Fuel for " + hm(day) + (stops != null ? " (riding plus stops)" : " of riding") })]);
    var kv = el("div", { cls: "gg-planner-kv" });
    [[F.lo + "–" + F.hi + " g", "carbs an hour"], [F.tlo + "–" + F.thi + " g", "carbs in total"],
     [units === "imp" ? "17–25 oz" : "500–750 ml", "fluid an hour, more in heat"], ["500–1,000 mg", "sodium an hour"]]
      .forEach(function (p) { kv.appendChild(el("div", null, [el("b", { text: p[0] }), p[1]])); });
    card.appendChild(kv);
    card.appendChild(el("p", { cls: "gg-planner-fine", text: F.label + ". Gravel God's race-guide fuelling rule for a day this long. General guidance, not medical advice: test it in training." }));
    if (cfg.gels.length) card.appendChild(gelPicker(F));
    var r = rider();
    if (typeof r.carbs === "number" && r.carbs < F.lo)
      card.appendChild(el("p", { cls: "gg-planner-fine", text: "You eat " + r.carbs + " g an hour now. Building to " + F.lo + "–" + F.hi + " g takes about " + F.weeks + " weeks of gut training." }));
    var det = el("details", { cls: "gg-planner-info" }, [el("summary", { text: "Hour by hour" })]);
    var tbl = el("table"), thead = el("tr");
    ["Riding hour", "Where", "Carbs so far", "Temperature on the " + String(m.edition.date).slice(0, 4) + " race day"].forEach(function (t) { thead.appendChild(el("th", { scope: "col", text: t })); });
    tbl.appendChild(el("thead", null, [thead]));
    var body = el("tbody");
    m.hours.forEach(function (p) {
      body.appendChild(el("tr", null, [el("td", { text: "h" + p.h }), el("td", { text: dist(p.km) }),
        el("td", { text: Math.round(F.lo * p.t / 3600) + "–" + Math.round(F.hi * p.t / 3600) + " g" }), el("td", { text: temp(p.temp) })]));
    });
    tbl.appendChild(body);
    det.appendChild(el("div", { cls: "gg-planner-table" }, [tbl]));
    det.appendChild(el("p", { cls: "gg-planner-fine", text: "Times are riding time from the start, without stops. Temperatures are that past race day's hourly weather where you would be, not a forecast." }));
    card.appendChild(det);
    return card;
  }

  var gelPick = "";
  function gelPicker(F) {
    var box = el("div", { cls: "gg-planner-gels" });
    var sel = el("select", { "aria-label": "Count it in gels" });
    sel.appendChild(el("option", { value: "", text: "Grams only" }));
    cfg.gels.forEach(function (g) { var o = el("option", { value: g.id, text: g.label + " · " + g.g + " g" }); if (g.id === gelPick) o.selected = true; sel.appendChild(o); });
    var line = el("p", { cls: "gg-planner-fine" });
    function show() {
      clear(line);
      var g = cfg.gels.filter(function (x) { return x.id === gelPick; })[0];
      if (!g) return;
      line.appendChild(document.createTextNode("About " + (F.lo / g.g).toFixed(1) + "–" + (F.hi / g.g).toFixed(1) + " an hour, " +
        Math.ceil(F.tlo / g.g) + "–" + Math.ceil(F.thi / g.g) + " in the day, at " + g.g + " g of carbs each "));
      if (g.url) { line.appendChild(document.createTextNode("(")); line.appendChild(el("a", { href: g.url, rel: "noopener", target: "_blank", text: "maker's page" })); line.appendChild(document.createTextNode(").")); }
      else line.appendChild(document.createTextNode("(the 25 g unit Gravel God's race guides count in)."));
    }
    sel.addEventListener("change", function () { gelPick = sel.value; show(); });
    box.appendChild(el("label", null, ["Count it in gels: ", sel]));
    box.appendChild(line);
    show();
    return box;
  }

  var ROWS = {
    fit: { name: "Fitness", note: "A size you choose: the same effort on a higher FTP. What riders gain on a Gravel God plan is not published yet." },
    gut: { name: "Gut training", stretch: "a 3-hour study applied after hour two", note: "More carbs an hour made a 20 km time trial after two hours of riding faster (Smith et al. 2013). We apply that to your riding after hour two and count nothing past 78 g an hour." },
    heat: { name: "Heat training", stretch: "one-hour studies stretched to a full day", note: "Two weeks of heat training won back most of the power lost in a hot time trial (Racinais et al. 2015). The loss by temperature is Peiffer and Abbiss 2011, on the past race day's temperatures." },
    group: { name: "Group riding", note: "Holding a group for more of the flat road: about a third less drag while you are in it. A group also sets your pace; that is not modelled." },
    pos: { name: "Position", note: "More of the day in the drops: 10% less drag than upright in a wind tunnel (Defraeye et al. 2010). A size you choose." },
    corner: { name: "Cornering", note: "Carrying more speed through descending corners, at the model's quicker cornering setting. A rough size." },
    stops: { name: "Quicker stops", note: "Race-day logistics, not fitness: minute for minute off your finish, not your riding time." }
  };

  function chips(row, key, options) {
    var box = el("div", { cls: "gg-planner-chips", role: "radiogroup", "aria-label": ROWS[row].name + " size" });
    options.forEach(function (o) {
      var inp = el("input", { type: "radio", name: "pick_" + key, value: String(o[0]) });
      if (picks[key] === o[0]) inp.checked = true;
      inp.addEventListener("change", function () { picks[key] = o[0]; run(); });
      box.appendChild(el("label", { cls: "gg-planner-chip" }, [inp, " " + o[1]]));
    });
    return box;
  }

  function rowsCard(m) {
    var card = el("div", { cls: "gg-planner-card" }, [
      el("h3", { text: "What training could change" }),
      el("p", { cls: "gg-planner-fine", text: "Each row is what one change would save on its own, at the middle of your range. The rows are not added together: changes overlap, and nobody can promise all of them." })
    ]);
    var list = el("div", { cls: "gg-planner-rows" });
    if (!m.rows) { list.appendChild(el("p", { text: "Not shown: the model could not work out these rows." })); card.appendChild(list); return card; }
    m.rows.forEach(function (r) {
      var def = ROWS[r.key], label = def.name, val = "", extra = null;
      if (r.key === "fit") { label += " · FTP +" + Math.round((picks.fit - 1) * 100) + "%"; extra = chips("fit", "fit", [[1.03, "+3%"], [1.05, "+5%"], [1.10, "+10%"]]); }
      if (r.key === "pos") { label += " · " + Math.round(picks.pos * 100) + "% more of the day in the drops"; extra = chips("pos", "pos", [[0.10, "10%"], [0.20, "20%"], [0.30, "30%"]]); }
      if (r.key === "stops") { label += " · " + Math.min(picks.stopsCut, rider().stops || 0) + " fewer minutes stopped"; extra = chips("stops", "stopsCut", [[5, "5 min"], [10, "10 min"], [15, "15 min"]]); }
      if (r.key === "group") label += " · more of the flat road sheltered";
      if (r.key === "heat") label += r.already ? " · already in your time" : " · two weeks in the heat";
      if (r.key === "gut") label += r.ask ? " · type your carbs an hour above to size this" : r.already ? " · you already eat " + r.from + " g an hour" : " · " + r.from + " → " + r.to + " g an hour";
      if (r.why) val = "not shown";
      else if (r.ask || r.already) val = "–";
      else val = r.saved_s < 30 ? "under 1 min" : mins(r.saved_s) + " min faster";
      var name = el("span", null, [label]);
      if (def.stretch && !r.ask && !r.already) name.appendChild(el("span", { cls: "gg-planner-tag", text: "stretched" }));
      var row = el("div", { cls: "gg-planner-imp" }, [name, el("b", { text: val })]);
      var note = def.note + (def.stretch && !r.ask && !r.already ? " Stretched: " + def.stretch + "." : "") +
        (r.why ? " Not shown: the model could not solve this change, so there is no number rather than a guess." : "");
      row.appendChild(el("small", { text: note }));
      if (extra) row.appendChild(extra);
      list.appendChild(row);
    });
    card.appendChild(list);
    return card;
  }

  function offerCard() {
    var o = cfg.offer;
    var a = el("a", { cls: "gg-planner-cta", href: o.href, "data-cta": "planner_custom_plan", text: "Build my plan · " + o.price });
    a.addEventListener("click", function () {
      if (typeof gtag === "function") gtag("event", cfg.events.cta, { race_slug: cfg.slug, source: "race_planner" });
    });
    var ul = el("ul");
    o.includes.forEach(function (s) { ul.appendChild(el("li", { text: s })); });
    return el("div", { cls: "gg-planner-card gg-planner-offer" }, [
      el("p", { cls: "gg-planner-eyebrow", text: "Custom training plan" }),
      el("h3", { text: "A plan for " + cfg.race + ", built around your hours" }),
      ul, a
    ]);
  }

  function kitNote(m) {
    var typedTotal = mass("geartot") != null;
    var base = typedTotal ? "Your typed total is used for bike, water and gear. " : "Clothes, shoes, helmet, tools and spares are not counted. ";
    var k = m && m.pace ? m.pace.kit3_s : null;
    if (k == null) return base + "What extra weight would cost is not shown: " + (m && m.pace && m.pace.why && m.pace.why.kit3 || "the model could not work it out") + ".";
    var amt = units === "imp" ? "An additional 6.6 lb" : "An additional 3 kg";
    if (Math.abs(k) < 30) return base + amt + " would change the middle of your range by under a minute.";
    return base + amt + " would " + (k > 0 ? "add" : "take off") + " about " + mins(Math.abs(k)) + " minutes " + (k > 0 ? "to" : "from") + " the middle of your range.";
  }

  function finePrint(m) {
    var det = el("details", { cls: "gg-planner-info" }, [el("summary", { text: "What this estimate assumes" })]);
    var ul = el("ul", { cls: "gg-planner-fine" });
    ["This is an estimate of riding time, not a prediction of your race. Real days vary with weather, stops, mechanicals and how you feel.",
     "Course: " + cfg.edition_line + ". " + (cfg.target_line ? cfg.target_line + " " : "") + "The race's route may change.",
     cfg.weather_line + " Race day will bring its own weather.",
     "Your FTP is used as entered. There is no altitude adjustment: if you race higher than you train, your power on the day may be lower.",
     "Surface is one rolling-resistance value for the whole course; tyres, mud and sand are not modelled.",
     "Riding position, cornering and how effort spreads over climbs come from the model's fixed settings, not from you.",
     "Your weight, bike and full bottles are carried all day; you drink them down, so this errs slow.",
     "Stops, walking, neutral starts and flats are not in the riding time.",
     kitNote(m)]
      .forEach(function (s) { ul.appendChild(el("li", { text: s })); });
    det.appendChild(ul);
    return det;
  }

  /* ---------- wiring ---------- */
  form.addEventListener("submit", function (e) { e.preventDefault(); run(); });
  form.addEventListener("focusin", start, { once: true });
  var ownBike = section.querySelector(".gg-planner-ownbike");
  form.querySelectorAll('input[name="bike"]').forEach(function (b) {
    b.addEventListener("change", function () { ownBike.hidden = radio("bike") !== "own"; });
  });
  form.elements.noftp.addEventListener("change", function () {
    var on = form.elements.noftp.checked; band.hidden = !on; ftpField.hidden = on;
  });
  var t = null;
  form.addEventListener("change", function (e) {
    if (!lastResult && !opened) return;
    if (e.target.name && e.target.name.indexOf("pick_") === 0) return;
    clearTimeout(t); t = setTimeout(run, 250);
  });
  section.querySelectorAll("[data-units]").forEach(function (b) {
    b.addEventListener("click", function () { setUnits(b.getAttribute("data-units")); });
  });
  setUnits(units);
})();
