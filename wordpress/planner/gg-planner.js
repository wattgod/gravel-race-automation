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
  /* Sizes for the Fitness, Position and Quicker-stops rows. The rider picks
     each one; until then the row shows no number. */
  var picks = { fit: null, pos: null, stopsCut: null };
  var worker = null, geo = null, ready = false, pending = null, runId = 0, shownOnce = false, opened = false, scrollNext = false;

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
    stopAnim(); dropMap(); runId++; pending = null; lastResult = null; scrollNext = false;
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
  function send(msg) { msg.id = ++runId; worker.postMessage(msg); }

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
    stopAnim(); dropMap(); lastResult = null; out.hidden = false; out.removeAttribute("aria-busy"); clear(out);
    out.appendChild(el("div", { cls: "gg-planner-card gg-planner-fail" }, [
      el("p", { cls: "gg-planner-eyebrow", text: "No estimate" }),
      el("p", { text: "No time is shown because " + (WHY[why] || why) + "." })
    ]));
  }

  /* ---------- analytics (manual interaction only; consent mode applies) ----------
     planner_result_shown fires once per page view, on the first result. Later
     recalculations (any input change, a size chip) do not fire it again, so
     plan_cta_click / planner_result_shown reads as clicks per visitor who saw a time. */
  function announce(m) {
    if (shownOnce || typeof gtag !== "function") return;
    shownOnce = true;
    gtag("event", cfg.events.result, {
      race_slug: cfg.slug, level: m.level, effort_source: m.IFsource,
      power_input: form.elements.noftp.checked ? "band" : "ftp", planner_status: cfg.status
    });
  }

  /* ---------- result ---------- */
  function render(m) {
    stopAnim(); dropMap();
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
    var span = m.span, ifTxt = function (x) { return x.toFixed(2); };
    var bandTxt = m.ftp.lo !== m.ftp.hi ? ", across your band's FTP (" + Math.round(m.ftp.lo) + "–" + Math.round(m.ftp.hi) + " W)" : "";
    head.appendChild(el("p", { cls: "gg-planner-sum", text: "Effort IF " + ifTxt(m.IF) + ", " +
      (m.IFsource === "set" ? "the effort you typed" : "the default for " + LEVEL_NAME[m.level] + " riders") +
      ". Range: a level easier or harder, IF " + ifTxt(span.slow) + " to " + ifTxt(span.fast) + bandTxt + "." }));
    cfg.notes.forEach(function (n) { head.appendChild(el("p", { cls: "gg-planner-flag", text: n.charAt(0).toUpperCase() + n.slice(1) + "." })); });
    var edit = el("button", { type: "button", cls: "gg-planner-edit", text: "Change effort" });
    edit.addEventListener("click", function () { form.elements["if"].value = m.IF.toFixed(2); form.elements["if"].focus(); });
    head.appendChild(edit);
    head.appendChild(howItWorks(m, span, ifTxt));
    out.appendChild(head);

    if (geo) out.appendChild(mapCard(m));
    out.appendChild(fuelCard(m, stops));
    out.appendChild(rowsCard(m));
    if (cfg.offer) out.appendChild(offerCard(m));
    out.appendChild(finePrint(m));
    // After a click on the button, bring the time into view below the sticky
    // site header (the cards carry scroll-margin-top for the header's height).
    if (scrollNext) {
      scrollNext = false;
      var top = head.getBoundingClientRect().top, hh = parseInt(getComputedStyle(document.documentElement).getPropertyValue("--gg-header-height"), 10) || 0;
      if (top < hh || top > window.innerHeight * 0.6) head.scrollIntoView({ block: "start", behavior: reducedMotion() ? "auto" : "smooth" });
    }
  }

  /* Everything that explains the numbers, closed by default. */
  function howItWorks(m, span, ifTxt) {
    var edYear = String(m.edition.date).slice(0, 4);
    var det = el("details", { cls: "gg-planner-info gg-planner-how" }, [el("summary", { text: "How this works" })]);
    var effort = "Effort: IF " + m.IF.toFixed(2) + ", normalized power " + Math.round(m.np) + " W on an FTP of " + Math.round(m.ftp.mid) + " W" +
      (m.ftp.lo !== m.ftp.hi ? " (the middle of your band)" : "") + ". ";
    effort += m.IFsource === "set" ? "The effort you typed." :
      "The default for " + LEVEL_NAME[m.level] + " riders on a ride of " + hm(m.mid) + ", set from published race power and coaching judgement. Type your own in Effort (IF) to change it.";
    [
      "Middle of the range: " + hm(m.mid) + " of riding at your effort. " + cfg.weather_line,
      "Range: if you ride a level easier or harder than " + (m.IFsource === "set" ? "the effort you typed" : "your level's default effort") +
        " (IF " + ifTxt(span.slow) + " to " + ifTxt(span.fast) + ", same effort curves)" +
        (m.ftp.lo !== m.ftp.hi ? ", across your band's FTP (" + Math.round(m.ftp.lo) + "–" + Math.round(m.ftp.hi) + " W)" : "") +
        ". It is not an accuracy figure.",
      effort,
      "Map and profile: dots mark the middle of your range at the end of each riding hour. The filled pin is the fast end of your range and the open pin the slow end, at the same moment. Profile colour is planned power against your day's average, from easy (light teal) to hardest (dark brown); grey where the course has no riding data. Click the map or drag along the profile to move through the ride.",
      "Wind and temperature in the line under the profile are the " + edYear + " race day's at that time, not a forecast. Route and elevation come from the race's public Ride with GPS route.",
      "Base map: " + cfg.map.credit + ". The map library and map tiles load from other sites; nothing you type here is sent anywhere."
    ].forEach(function (t) { det.appendChild(el("p", { cls: "gg-planner-fine", text: t })); });
    return det;
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

  /* ---------- base map ----------
     Leaflet and OpenStreetMap tiles, as on the race search page. Only the
     library (pinned, with SRI) and the tiles load from other sites; nothing the
     rider typed goes with them. If either fails, no map is drawn and the card
     says so: there is no stand-in outline. */
  var leafState = null, leafWait = [], leaf = null;
  function loadLeaflet(cb) {
    if (leafState === "ok" || leafState === "fail") { cb(leafState === "ok"); return; }
    leafWait.push(cb);
    if (leafState === "loading") return;
    leafState = "loading";
    var M = cfg.map;
    var done = function (ok) { leafState = ok ? "ok" : "fail"; var w = leafWait; leafWait = []; w.forEach(function (f) { f(ok); }); };
    // Draw only once both the script and its stylesheet are in: a map laid
    // out before Leaflet's CSS arrives places its panes and tiles wrongly.
    var left = 2, ok = true;
    var one = function (good) { ok = ok && good; if (--left === 0) done(ok && !!(window.L && window.L.map)); };
    var css = el("link", { rel: "stylesheet", href: M.css, integrity: M.css_sri, crossorigin: "anonymous" });
    css.addEventListener("load", function () { one(true); }); css.addEventListener("error", function () { one(false); });
    var js = el("script", { src: M.js, integrity: M.js_sri, crossorigin: "anonymous" });
    js.addEventListener("load", function () { one(true); }); js.addEventListener("error", function () { one(false); });
    document.head.appendChild(css); document.head.appendChild(js);
  }
  var leafRO = null;
  function dropMap() {
    if (leafRO) { leafRO.disconnect(); leafRO = null; }
    if (leaf) { try { leaf.remove(); } catch (e) {} leaf = null; }
  }

  function mapCard(m) {
    var R = m.ride;
    var card = el("div", { cls: "gg-planner-card gg-planner-ride" });
    var headRow = el("div", { cls: "gg-planner-ridehead" }, [el("h3", { text: "Your " + cfg.race })]);
    var play = null;
    if (R) { play = el("button", { type: "button", cls: "gg-planner-edit", "aria-pressed": "false", text: "Replay" }); headRow.appendChild(play); }
    card.appendChild(headRow);

    var box = el("div", { cls: "gg-planner-basemap", role: "region", "aria-label": "Course map with your position at each riding hour" });
    var mapNote = el("p", { cls: "gg-planner-fine gg-planner-mapnote" });
    mapNote.hidden = true;
    card.appendChild(box); card.appendChild(mapNote);
    var pins = null, pinAt = null;
    function placePins() {
      if (!pins || !pinAt) return;
      pins.fast.setLatLng([R.la[pinAt[0]], R.lo[pinAt[0]]]); pins.slow.setLatLng([R.la[pinAt[1]], R.lo[pinAt[1]]]);
    }
    function noMap(why) {
      if (!box.isConnected) return;
      dropMap(); pins = null; box.hidden = true; mapNote.hidden = false;
      mapNote.textContent = "The map is not shown: " + why + "." + (R ? " The profile below still works." : "");
    }
    // After the card is on the page: Leaflet needs a sized container.
    setTimeout(function () {
      if (!box.isConnected) return;
      loadLeaflet(function (ok) {
        if (!box.isConnected) return;  // a newer result replaced this card
        if (!ok) { noMap("the map library did not load"); return; }
        var L = window.L, M = cfg.map;
        dropMap();
        // Fractional zoom so the route fills the map (whole levels can halve it).
        // On touch screens one finger scrolls the page, not the map; the zoom
        // buttons still work.
        // With reduced motion: no zoom, fade, marker or pan animation, no inertia.
        var still = reducedMotion();
        var map = L.map(box, { scrollWheelZoom: false, dragging: !L.Browser.mobile, tap: false, zoomSnap: 0, zoomDelta: 1,
          zoomAnimation: !still, fadeAnimation: !still, markerZoomAnimation: !still, inertia: !still });
        if (still) {
          // Keyboard panning goes through panBy; make every pan immediate.
          var panBy = map.panBy;
          map.panBy = function (offset, opt) { return panBy.call(map, offset, L.extend({}, opt, { animate: false })); };
        }
        map.attributionControl.setPrefix(M.prefix);
        leaf = map;
        // The first fitted view must load whole: if any of its tiles fails, no
        // map is shown (never the route over holes). Once that view is in,
        // tiles that fail while the visitor pans or zooms are left as Leaflet
        // shows them.
        var tiles = L.tileLayer(M.tiles, { attribution: M.attribution, maxZoom: M.max_zoom }), firstView = true;
        tiles.on("tileerror", function () { if (firstView) { firstView = false; noMap("some of the map tiles did not load"); } });
        tiles.on("load", function () { firstView = false; });
        tiles.addTo(map);
        var line = geo.la.map(function (la, i) { return [la, geo.lo[i]]; });
        var route = L.polyline(line, { className: "gg-planner-route", weight: 4, opacity: 1, interactive: false }).addTo(map);
        // Fit the route with a margin of 5% of the map's shorter side, now and
        // whenever the map changes size (resize, orientation), until the
        // visitor zooms or pans; after that their view is kept. Replay and
        // scrubbing only move the pins.
        var fitting = false, userView = false, bounds = route.getBounds();
        function fit() {
          var sz = map.getSize(); if (!sz.x || !sz.y) return;
          var pad = Math.round(0.05 * Math.min(sz.x, sz.y));
          fitting = true; map.fitBounds(bounds, { padding: [pad, pad], animate: false }); fitting = false;
        }
        map.on("zoomstart movestart", function () { if (!fitting) userView = true; });
        fit();
        if (window.ResizeObserver) {
          leafRO = new ResizeObserver(function () {
            if (!leaf) return;
            fitting = true; map.invalidateSize({ animate: false }); fitting = false;
            if (!userView) fit();
          });
          leafRO.observe(box);
        }
        m.hours.forEach(function (p) { L.circleMarker([p.la, p.lo], { radius: 5, className: "gg-planner-dot", fillOpacity: 1, opacity: 1, interactive: false }).addTo(map); });
        if (!R) return;
        pins = {
          slow: L.circleMarker(line[0], { radius: 8, className: "gg-planner-pin gg-planner-pin-slow", fillOpacity: 1, opacity: 1, interactive: false }).addTo(map),
          fast: L.circleMarker(line[0], { radius: 8, className: "gg-planner-pin gg-planner-pin-fast", fillOpacity: 1, opacity: 1, interactive: false }).addTo(map)
        };
        placePins();
        // A click on or near the route moves the replay there.
        map.on("click", function (ev) {
          var c = map.latLngToContainerPoint(ev.latlng), best = -1, bd = 40 * 40;
          for (var j = 0; j < R.km.length; j++) {
            var q = map.latLngToContainerPoint([R.la[j], R.lo[j]]), dx = q.x - c.x, dy = q.y - c.y, dd = dx * dx + dy * dy;
            if (dd < bd) { bd = dd; best = j; }
          }
          if (best >= 0) scrubKm(R.km[best]);
        });
      });
    }, 0);

    // The profile is drawn at its on-screen width, full width under the map.
    var PW = Math.round(Math.max(320, Math.min(1400, (section.clientWidth || 640) - 48))), PH = PW < 560 ? 170 : 150, T = geo.total_km;
    var a0 = Math.min.apply(null, geo.alt), a1 = Math.max.apply(null, geo.alt);
    var px = function (km) { return 54 + km / T * (PW - 64); }, py = function (a) { return PH - 22 - (a - a0) / ((a1 - a0) || 1) * (PH - 44); };
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
    card.appendChild(prof);

    if (!R) {
      card.appendChild(el("p", { cls: "gg-planner-fine", text: "Dots: where the middle of your range is at the end of each riding hour. The replay is not shown: the model could not lay out your ride point by point." }));
      return card;
    }
    // Not a live region: it changes every frame during Replay. Keyboard and
    // screen-reader users get the same text through the slider's valuetext.
    var readout = el("p", { cls: "gg-planner-readout", "aria-live": "off" });
    card.appendChild(readout);

    var edYear = String(m.edition.date).slice(0, 4), endT = R.slow.t[R.slow.t.length - 1];
    function setMoment(sec, kmCursor) {
      var kc = kmCursor != null ? kmCursor : kmAt(R, R.mid, sec);
      var kf = kmAt(R, R.fast, sec), ks = kmAt(R, R.slow, sec);
      pinAt = [idxAt(R.km, kf), idxAt(R.km, ks)];
      placePins();
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
    function profKm(ev) { var r = prof.getBoundingClientRect(); var xv = (ev.clientX - r.left) / r.width * PW; return (xv - 54) / (PW - 64) * T; }
    prof.addEventListener("pointerdown", function (ev) { try { prof.setPointerCapture(ev.pointerId); } catch (e) {} scrubKm(profKm(ev)); });
    prof.addEventListener("pointermove", function (ev) { if (ev.buttons) scrubKm(profKm(ev)); });
    prof.addEventListener("keydown", function (ev) {
      var unit = units === "imp" ? MI : 1, cur = parseFloat(prof.getAttribute("aria-valuenow")) || 0, step = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1, PageUp: 10, PageDown: -10 }[ev.key];
      if (step) { ev.preventDefault(); scrubKm(cur + step * unit); }
      else if (ev.key === "Home") { ev.preventDefault(); scrubKm(0); }
      else if (ev.key === "End") { ev.preventDefault(); scrubKm(T); }
    });

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
    card.appendChild(el("p", { cls: "gg-planner-fine", text: F.label + ": the fuelling range our race guides use for a day this long. General guidance, not medical advice: test it in training." }));
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
      else line.appendChild(document.createTextNode("(the 25 g unit our race guides count in)."));
    }
    sel.addEventListener("change", function () { gelPick = sel.value; show(); });
    box.appendChild(el("label", null, ["Count it in gels: ", sel]));
    box.appendChild(line);
    show();
    return box;
  }

  /* Notes are lists of text and {cite: key}; each cite becomes an [n] link to
     the page's numbered source list (cfg.cite holds the numbers). */
  var ROWS = {
    fit: { name: "Fitness", note: ["A size you choose: the same effort on a higher FTP. What riders gain on our plans is not published yet."] },
    gut: { name: "Gut training", stretch: "a 3-hour study applied after hour two", note: ["More carbs an hour made a 20 km time trial after two hours of riding faster ", { cite: "gut" }, ". This row applies that to your riding after hour two and counts nothing past 78 g an hour."] },
    heat: { name: "Heat training", stretch: "one-hour studies stretched to a full day", note: ["Two weeks of heat training won back most of the power lost in a hot time trial ", { cite: "heat_gain" }, ". The loss by temperature ", { cite: "heat_loss" }, " is applied to the past race day's temperatures."] },
    group: { name: "Group riding", note: ["Holding a group for more of the flat road: about a third less drag while you are in it ", { cite: "group" }, ". A group also sets your pace; that is not modelled."] },
    pos: { name: "Position", note: ["More of the day in the drops: 10% less drag than upright in a wind tunnel ", { cite: "position" }, ". A size you choose."] },
    corner: { name: "Cornering", note: ["Carrying more speed through descending corners, at the model's quicker cornering setting. A rough size."] },
    stops: { name: "Quicker stops", note: ["Race-day logistics, not fitness: minute for minute off your finish, not your riding time."] }
  };
  function cite(key) {
    var n = cfg.cite && cfg.cite[key];
    if (typeof n !== "number") return null;
    return el("a", { cls: "gg-planner-cite", href: "#gg-citation-" + n, text: "[" + n + "]" });
  }
  function noteNodes(parts) {
    return parts.map(function (p) { return typeof p === "string" ? p : cite(p.cite); });
  }

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
      if (r.key === "fit") { label += r.pick ? " · choose a size" : " · FTP +" + Math.round((picks.fit - 1) * 100) + "%"; extra = chips("fit", "fit", [[1.03, "+3%"], [1.05, "+5%"], [1.10, "+10%"]]); }
      if (r.key === "pos") { label += r.pick ? " · choose a size" : " · " + Math.round(picks.pos * 100) + "% more of the day in the drops"; extra = chips("pos", "pos", [[0.10, "10%"], [0.20, "20%"], [0.30, "30%"]]); }
      if (r.key === "stops") { label += r.pick ? " · choose a size" : " · " + Math.min(picks.stopsCut, rider().stops || 0) + " fewer minutes stopped"; extra = chips("stops", "stopsCut", [[5, "5 min"], [10, "10 min"], [15, "15 min"]]); }
      if (r.key === "group") label += " · more of the flat road sheltered";
      if (r.key === "heat") label += r.already ? " · already in your time" : " · two weeks in the heat";
      if (r.key === "gut") label += r.ask ? " · type your carbs an hour above to size this" : r.already ? " · you already eat " + r.from + " g an hour" : " · " + r.from + " → " + r.to + " g an hour";
      if (r.why) val = "not shown";
      else if (r.ask || r.already || r.pick) val = "–";
      else val = r.saved_s < 30 ? "under 1 min" : mins(r.saved_s) + " min faster";
      var name = el("span", null, [label]);
      if (def.stretch && !r.ask && !r.already) name.appendChild(el("span", { cls: "gg-planner-tag", text: "stretched" }));
      var row = el("div", { cls: "gg-planner-imp" }, [name, el("b", { text: val })]);
      var note = noteNodes(def.note);
      if (def.stretch && !r.ask && !r.already) note.push(" Stretched: " + def.stretch + ".");
      if (r.why) note.push(" Not shown: the model could not solve this change.");
      row.appendChild(el("small", null, note));
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
      ul, a,
      el("p", { cls: "gg-planner-fine", text: o.price_note })
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
  /* An [n] marker jumps to the page's source list. On phones that section
     starts collapsed (the page's deep-dive disclosure), so open it first by
     its own header control; the hash jump then lands on a visible item. */
  section.addEventListener("click", function (e) {
    var link = e.target && e.target.closest ? e.target.closest(".gg-planner-cite") : null;
    if (!link) return;
    var target = document.getElementById((link.getAttribute("href") || "").replace(/^#/, ""));
    var owner = target ? target.closest(".gg-section") : null;
    if (owner && owner.classList.contains("gg-section-collapsed")) {
      var header = owner.querySelector(".gg-section-header");
      if (header) header.click();
    }
  });
  form.addEventListener("submit", function (e) { e.preventDefault(); scrollNext = true; run(); });
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
