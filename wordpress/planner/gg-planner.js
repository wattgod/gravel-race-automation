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
  function setUnits(u) {
    var kg = readKg();
    units = u;
    try { localStorage.setItem("gg_planner_units", u); } catch (e) {}
    section.querySelectorAll("[data-units]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-units") === u)); });
    section.querySelectorAll('[data-unit="weight"]').forEach(function (n) { n.textContent = u === "imp" ? "lb" : "kg"; });
    if (kg != null && !isNaN(kg)) form.elements.kg.value = String(+(u === "imp" ? kg / LB : kg).toFixed(1));
    if (lastResult) render(lastResult);
  }
  function readKg() { var v = num("kg"); if (v == null || isNaN(v)) return v; return units === "imp" ? v * LB : v; }

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
    var bikeId = radio("bike"), bike = cfg.bikes.filter(function (b) { return b.id === bikeId; })[0];
    var bottles = num("bottles");
    var gearKg = bike && bottles != null && bottles >= 0 && bottles <= 4 && Math.round(bottles) === bottles ? bike.kg + bottles * cfg.bottle.kg : null;
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
    var bottles = num("bottles");
    if (bottles != null && !(bottles >= 0 && bottles <= 4 && Math.round(bottles) === bottles)) bad.push("bottles (0–4)");
    return bad;
  }

  function localMiss(r) {
    var m = [];
    if (r.ftp == null && !r.band) m.push(form.elements.noftp.checked ? "a power band" : "your FTP");
    if (r.kg == null) m.push("your weight");
    if (!r.hours) m.push("hours a week you can train");
    if (!r.group) m.push("who you'll ride with");
    if (!radio("bike")) m.push("your bike");
    else if (num("bottles") == null) m.push("bottles (0–4)");
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
    runId++; pending = null; lastResult = null;
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
    lastResult = null; out.hidden = false; out.removeAttribute("aria-busy"); clear(out);
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
    out.appendChild(finePrint());
  }

  function mapCard(m) {
    var card = el("div", { cls: "gg-planner-card" }, [el("h3", { text: "Where you are each hour" })]);
    var wrap = el("div", { cls: "gg-planner-map" });
    // route, equirectangular with latitude scaling
    var la0 = Math.min.apply(null, geo.la), la1 = Math.max.apply(null, geo.la), lo0 = Math.min.apply(null, geo.lo), lo1 = Math.max.apply(null, geo.lo);
    var kx = Math.cos((la0 + la1) / 2 * Math.PI / 180), w = (lo1 - lo0) * kx || 1e-6, h = (la1 - la0) || 1e-6, S = 280 / Math.max(w, h);
    var W = Math.max(40, w * S) + 20, H = Math.max(40, h * S) + 20;
    var X = function (lo) { return 10 + (lo - lo0) * kx * S; }, Y = function (la) { return 10 + (la1 - la) * S; };
    var map = sv("svg", { viewBox: "0 0 " + W.toFixed(0) + " " + H.toFixed(0), role: "img", "aria-label": "Course map with your position at each riding hour" });
    var d = geo.la.map(function (la, i) { return (i ? "L" : "M") + X(geo.lo[i]).toFixed(1) + " " + Y(la).toFixed(1); }).join("");
    map.appendChild(sv("path", { d: d, "class": "gg-planner-route" }));
    m.hours.forEach(function (p) { map.appendChild(sv("circle", { cx: X(p.lo).toFixed(1), cy: Y(p.la).toFixed(1), r: 5, "class": "gg-planner-dot" })); });
    wrap.appendChild(map);
    // elevation profile with hour ticks
    var PW = 600, PH = 160, a0 = Math.min.apply(null, geo.alt), a1 = Math.max.apply(null, geo.alt), T = geo.total_km;
    var px = function (km) { return 30 + km / T * (PW - 40); }, py = function (a) { return PH - 20 - (a - a0) / ((a1 - a0) || 1) * (PH - 40); };
    var prof = sv("svg", { viewBox: "0 0 " + PW + " " + PH, role: "img", "aria-label": "Elevation profile with riding hours marked" });
    var pd = "M" + px(0) + " " + (PH - 20) + geo.km.map(function (k, i) { return "L" + px(k).toFixed(1) + " " + py(geo.alt[i]).toFixed(1); }).join("") + "L" + px(T) + " " + (PH - 20) + "Z";
    prof.appendChild(sv("path", { d: pd, "class": "gg-planner-prof" }));
    var every = m.hours.length > 10 ? 2 : 1;
    m.hours.forEach(function (p) {
      if (p.h % every && p.h !== m.hours.length) return;
      var x = px(Math.min(p.km, T)).toFixed(1);
      prof.appendChild(sv("line", { x1: x, x2: x, y1: 14, y2: PH - 20, "class": "gg-planner-tick" }));
      var t = sv("text", { x: x, y: 11, "text-anchor": "middle", "class": "gg-planner-tlabel" }); t.textContent = "h" + p.h; prof.appendChild(t);
    });
    var lbl = function (x, y, s, anchor) { var t = sv("text", { x: x, y: y, "class": "gg-planner-tlabel", "text-anchor": anchor || "start" }); t.textContent = s; prof.appendChild(t); };
    lbl(2, py(a1) + 4, units === "imp" ? Math.round(a1 * 3.28084) + " ft" : Math.round(a1) + " m");
    lbl(2, PH - 22, units === "imp" ? Math.round(a0 * 3.28084) + " ft" : Math.round(a0) + " m");
    lbl(PW - 4, PH - 4, dist(T), "end");
    wrap.appendChild(prof);
    card.appendChild(wrap);
    card.appendChild(el("p", { cls: "gg-planner-fine", text: "Dots: where the middle of your range is at the end of each riding hour. Route and elevation from the race's public Ride with GPS route." }));
    return card;
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

  function finePrint() {
    var det = el("details", { cls: "gg-planner-info" }, [el("summary", { text: "What this estimate assumes" })]);
    var ul = el("ul", { cls: "gg-planner-fine" });
    ["This is an estimate of riding time, not a prediction of your race. Real days vary with weather, stops, mechanicals and how you feel.",
     "Course: " + cfg.edition_line + ". " + (cfg.target_line ? cfg.target_line + " " : "") + "The race's route may change.",
     cfg.weather_line + " Race day will bring its own weather.",
     "Your FTP is used as entered. There is no altitude adjustment: if you race higher than you train, your power on the day may be lower.",
     "Surface is one rolling-resistance value for the whole course; tyres, mud and sand are not modelled.",
     "Riding position, cornering and how effort spreads over climbs come from the model's fixed settings, not from you.",
     "Your weight, bike and full bottles are carried all day; you drink them down, so this errs slow.",
     "Stops, walking, neutral starts and flats are not in the riding time."]
      .forEach(function (s) { ul.appendChild(el("li", { text: s })); });
    det.appendChild(ul);
    return det;
  }

  /* ---------- wiring ---------- */
  form.addEventListener("submit", function (e) { e.preventDefault(); run(); });
  form.addEventListener("focusin", start, { once: true });
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
