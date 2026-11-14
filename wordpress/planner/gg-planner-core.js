/* Gravel God finish-time planner: core (no DOM).
 *
 * Runs the frozen planner engine (wordpress/planner/engine7.js, copied
 * byte-identical; its physics is never changed here) on one race's course
 * bundle (data/planner/courses/<slug>.json) for one visitor.
 *
 * Every function either returns a result or {ok:false, why}. A failed solve
 * never produces a time: callers must show no number and say why. No
 * fallback values anywhere.
 *
 * Works in the browser (window.GGPlannerCore) and in node (module.exports),
 * so tests run the same code the page runs.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.GGPlannerCore = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var LEVELS = ["beginner", "intermediate", "advanced", "elite"];
  /* Training hours a week -> level (IF_DEFAULTS cut points: under 6 Beginner,
     6-9 Intermediate, 9-14 Advanced, 14+ Elite), by each chip's midpoint. */
  var HOURS = [
    { id: "3-5", label: "3–5", level: "beginner" },
    { id: "5-7", label: "5–7", level: "intermediate" },
    { id: "7-10", label: "7–10", level: "intermediate" },
    { id: "10-12", label: "10–12", level: "advanced" },
    { id: "12-15", label: "12–15", level: "advanced" },
    { id: "15+", label: "15+", level: "elite" }
  ];
  /* Share of flat road spent sheltered, and the drag cut inside a group
     (about a third less drag: Broker, Kyle and Burke 1999). */
  var GROUPS = [
    { id: "solo", share: 0, label: "On my own" },
    { id: "some", share: 0.33, label: "In a group some of the day" },
    { id: "most", share: 0.54, label: "In a group most of the day" }
  ];
  var DRAG_CUT = 0.36;
  /* Allen and Coggan FTP ratings (W/kg) as printed in Garmin's Edge 530 manual. */
  var BANDS = {
    m: [["Fair", 2.23, 2.78], ["Good", 2.79, 3.92], ["Excellent", 3.93, 5.04]],
    f: [["Fair", 1.90, 2.35], ["Good", 2.36, 3.32], ["Excellent", 3.33, 4.29]]
  };
  var IF_MIN = 0.40, IF_MAX = 1.05;
  var CORNER_CAP = 0.64;
  var HEAT_TRAINED_KEEP = 11 / 48;
  /* Smith et al. 2013: % less time-trial time than placebo, by g/h. */
  var SMITH = [[0, 0], [9, 1.0], [19, 2.0], [31, 3.0], [48, 4.0], [78, 4.7]];

  function levelIndex(level) { return LEVELS.indexOf(level); }

  /* ---------- weather placement (nearest location, nearest hour) ---------- */
  function hav(la1, lo1, la2, lo2) {
    var R = 6371000, r = Math.PI / 180;
    var dl = (la2 - la1) * r, dn = (lo2 - lo1) * r;
    var a = Math.sin(dl / 2) * Math.sin(dl / 2) +
      Math.cos(la1 * r) * Math.cos(la2 * r) * Math.sin(dn / 2) * Math.sin(dn / 2);
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
  }

  function hourly(edition) {
    var src = edition && edition.openmeteo;
    if (!Array.isArray(src) || !src.length) return { ok: false, why: "no weather for this edition" };
    var out = [];
    for (var s = 0; s < src.length; s++) {
      var w = src[s], h = w.hourly || {}, off = w.utc_offset_seconds;
      if (!isNum(off) || !isNum(w.latitude) || !isNum(w.longitude))
        return { ok: false, why: "weather station details are incomplete" };
      var cols = [h.time, h.temperature_2m, h.wind_speed_10m, h.wind_direction_10m];
      if (!cols.every(Array.isArray)) return { ok: false, why: "weather file is missing a column" };
      var nh = h.time.length;
      if (!nh || !cols.every(function (a) { return a.length === nh; }))
        return { ok: false, why: "weather file has no hours or uneven columns" };
      if (![h.temperature_2m, h.wind_speed_10m, h.wind_direction_10m].every(function (a) { return a.every(isNum); }))
        return { ok: false, why: "weather file has a gap" };
      var t = h.time.map(function (x) { return typeof x === "string" ? Date.parse(x + "Z") / 1000 - off : NaN; });
      if (!t.every(isFinite)) return { ok: false, why: "weather time labels are unreadable" };
      out.push({ la: w.latitude, lo: w.longitude, t: t, ws: h.wind_speed_10m, wd: h.wind_direction_10m, T: h.temperature_2m });
    }
    return { ok: true, H: out };
  }

  /* Fills cols.T/ws/wd for each bin from the station nearest the bin and the
     hour nearest the rider's predicted clock time there. */
  function placeWeather(cols, H, t0, cum) {
    var n = cols.g.length, near = new Array(n);
    for (var i = 0; i < n; i++) {
      var best = 0, bd = Infinity;
      for (var s = 0; s < H.length; s++) {
        var d = hav(cols.la[i], cols.lo[i], H[s].la, H[s].lo);
        if (d < bd) { bd = d; best = s; }
      }
      near[i] = best;
    }
    var T = new Array(n), ws = new Array(n), wd = new Array(n);
    for (var j = 0; j < n; j++) {
      var st = H[near[j]], t = t0 + (cum ? cum[j] : 0), k = 0;
      for (var q = 0; q < st.t.length; q++) if (Math.abs(st.t[q] - t) < Math.abs(st.t[k] - t)) k = q;
      if (Math.abs(st.t[k] - t) > 5400) return { ok: false, why: "the past race-day weather does not cover your predicted time on course" };
      if (st.ws[k] == null || st.wd[k] == null || st.T[k] == null) return { ok: false, why: "the past race-day weather has a gap" };
      T[j] = st.T[k]; ws[j] = st.ws[k]; wd[j] = st.wd[k];
    }
    return { ok: true, T: T, ws: ws, wd: wd };
  }

  /* ---------- one model run ---------- */
  /* P: {np, m, cda, cap, share, heatKeep}. Returns {ok:true,total,T,Pw,np,ap}
     or {ok:false, why}. */
  function runOnce(E, D, P) {
    var B = E.prep(D, { share: P.share, dcut: DRAG_CUT });
    var w = new Float64Array(B.length);
    for (var i = 0; i < B.length; i++) w[i] = D.phi[B[i].bd];
    var r = E.planNP(B, w, P.np, P.m, P.cda, D.crr, D.wf, P.cap);
    if (!r.ok) return { ok: false, why: "solve:" + (r.why || "unknown") };
    var cool = E.stats(B, r);
    if (P.heatKeep > 0) r = E.heat(B, r, P.heatKeep, P.m, P.cda, D.crr, D.wf, P.cap);
    var total = E.total(B, r.T);
    if (!(total > 0) || !isFinite(total)) return { ok: false, why: "solve:time" };
    return { ok: true, total: total, T: r.T, Pw: r.Pw, np: cool.np, ap: cool.ap };
  }

  function engineData(course, wx) {
    var c = course.bins.cols;
    return {
      cols: { g: c.g, kap: c.kap, alt: c.alt, h: c.h, ok: c.ok, la: c.la, lo: c.lo, T: wx.T, ws: wx.ws, wd: wx.wd },
      crr: course.engine.crr, wf: course.engine.wf, cap: course.engine.cap, phi: course.engine.phi
    };
  }

  function cumOf(T) {
    var c = new Float64Array(T.length), s = 0;
    for (var i = 0; i < T.length; i++) { c[i] = s; s += T[i]; }
    return c;
  }

  /* ---------- inputs ---------- */
  /* rider: {ftp|null, band:{sex,name}|null, kg, gearKg, hours, levelPick|null,
     group, IF|null, stops|null, carbs|null, heatTrained:bool} */
  function checkRider(rider, flags) {
    var miss = [];
    if (!(rider.kg >= 35 && rider.kg <= 160)) miss.push("your weight (35–160 kg)");
    if (rider.ftp == null && !rider.band) miss.push("your FTP or a power band");
    if (rider.ftp != null && !(rider.ftp >= 80 && rider.ftp <= 500)) miss.push("an FTP between 80 and 500 W");
    if (!(rider.gearKg >= 5 && rider.gearKg <= 45)) miss.push("your bike and water");
    if (!HOURS.some(function (h) { return h.id === rider.hours; })) miss.push("hours a week you can train");
    if (!GROUPS.some(function (g) { return g.id === rider.group; })) miss.push("who you ride with");
    if (rider.IF != null && !(rider.IF >= IF_MIN && rider.IF <= IF_MAX)) miss.push("an effort (IF) between 0.40 and 1.05");
    if (flags && flags.visitorSetsEffort && rider.IF == null) miss.push("your effort (IF): this course has no default");
    return miss;
  }

  function levelOf(rider) {
    if (rider.levelPick && levelIndex(rider.levelPick) >= 0) return rider.levelPick;
    var h = HOURS.filter(function (x) { return x.id === rider.hours; })[0];
    return h ? h.level : null;
  }

  function ftpOf(rider) {
    if (rider.ftp != null) return { mid: rider.ftp, lo: rider.ftp, hi: rider.ftp, band: null };
    var b = BANDS[rider.band.sex].filter(function (x) { return x[0] === rider.band.name; })[0];
    if (!b) return null;
    return { mid: (b[1] + b[2]) / 2 * rider.kg, lo: b[1] * rider.kg, hi: b[2] * rider.kg, band: b };
  }

  /* ---------- effort span (the range) ----------
     The range is the same ride one level easier and one level harder, on
     the same locked curves at the rider's riding hours. The top and bottom
     levels have one neighbour, so that one gap is used on both sides. A
     typed effort gets the same gaps, centred on the typed value. It is an
     effort span, not an accuracy or uncertainty figure. */
  function effortSpan(E, level, IF, hours) {
    var i = levelIndex(level), here = E.ifDefault(level, hours);
    var up = i < LEVELS.length - 1 ? E.ifDefault(LEVELS[i + 1], hours) - here : null;
    var dn = i > 0 ? here - E.ifDefault(LEVELS[i - 1], hours) : null;
    if (up == null) up = dn;
    if (dn == null) dn = up;
    if (!(up > 0) || !(dn > 0)) return null;
    return { fast: Math.min(IF_MAX, IF + up), slow: Math.max(IF_MIN, IF - dn), up: up, dn: dn };
  }

  /* A real number: null, "", strings and NaN are never read as values. */
  function isNum(x) { return typeof x === "number" && isFinite(x); }

  /* Every bin value must be a finite number; a gap is never read as zero. */
  function checkCourse(course) {
    var c = course && course.bins && course.bins.cols;
    if (!c) return "the course has no route data";
    var n = c.g && c.g.length;
    if (!n) return "the course has no route data";
    var keys = ["g", "kap", "alt", "la", "lo", "h", "ok"];
    for (var k = 0; k < keys.length; k++) {
      var a = c[keys[k]];
      if (!a || a.length !== n) return "the course data is incomplete";
      for (var i = 0; i < n; i++) if (typeof a[i] !== "number" || !isFinite(a[i])) return "the course data has a gap";
    }
    var e = course.engine;
    if (!e || !(isNum(e.crr) && e.crr > 0 && e.crr < 0.1) || !(isNum(e.wf) && e.wf >= 0 && e.wf <= 1) ||
        !(isNum(e.cap) && e.cap > 0) || !(isNum(e.solo_cda_default) && e.solo_cda_default > 0 && e.solo_cda_default < 1) ||
        !Array.isArray(e.phi) || e.phi.length !== 12 || !e.phi.every(function (x) { return isNum(x) && x > 0; }))
      return "the model settings for this course are incomplete";
    return null;
  }

  /* ---------- the whole estimate ---------- */
  /* opts: {edition (index into course.weather.editions),
     visitorSetsEffort} */
  function estimate(E, course, rider, opts) {
    opts = opts || {};
    var miss = checkRider(rider, opts);
    if (miss.length) return { ok: false, why: "missing", miss: miss };
    var bad = checkCourse(course);
    if (bad) return { ok: false, why: bad };
    var ed = course.weather && course.weather.editions && course.weather.editions[opts.edition || 0];
    if (!ed || !ed.start_iso) return { ok: false, why: "no past race-day weather with a start time" };
    var hw = hourly(ed);
    if (!hw.ok) return { ok: false, why: hw.why };
    var t0 = Date.parse(ed.start_iso) / 1000;
    if (!isFinite(t0)) return { ok: false, why: "the start time is unreadable" };
    var level = levelOf(rider), F = ftpOf(rider);
    if (!level || !F) return { ok: false, why: "missing", miss: ["your level"] };
    var grp = GROUPS.filter(function (g) { return g.id === rider.group; })[0];
    var base = {
      m: rider.kg + rider.gearKg, cda: course.engine.solo_cda_default, cap: course.engine.cap,
      share: grp.share, heatKeep: rider.heatTrained ? HEAT_TRAINED_KEEP : 1
    };
    function withNP(np, extra) { var o = {}, k; for (k in base) o[k] = base[k]; o.np = np; if (extra) for (k in extra) o[k] = extra[k]; return o; }

    /* Weather by predicted clock time: three passes, each settling the effort. */
    var cum = null, D = null, IFused = null, def = null, mid = null;
    for (var pass = 0; pass < 3; pass++) {
      var wx = placeWeather(course.bins.cols, hw.H, t0, cum);
      if (!wx.ok) return { ok: false, why: wx.why };
      D = engineData(course, wx);
      if (rider.IF != null) {
        IFused = rider.IF;
      } else {
        def = E.defaultIF(level, function (IF) { var r = runOnce(E, D, withNP(IF * F.mid)); return r.ok ? r.total : NaN; });
        if (!def.ok) return { ok: false, why: "effort:" + def.why };
        IFused = def.IF;
      }
      mid = runOnce(E, D, withNP(IFused * F.mid));
      if (!mid.ok) return { ok: false, why: mid.why };
      cum = cumOf(mid.T);
    }
    var hours = mid.total / 3600;
    var span = effortSpan(E, level, IFused, hours);
    if (!span) return { ok: false, why: "effort:span" };
    var fast = runOnce(E, D, withNP(span.fast * F.hi));
    if (!fast.ok) return { ok: false, why: fast.why };
    var slow = runOnce(E, D, withNP(span.slow * F.lo));
    if (!slow.ok) return { ok: false, why: slow.why };

    return {
      ok: true, level: level, IF: IFused, IFsource: rider.IF != null ? "set" : "default",
      defaultIF: def && def.ok ? def.IF : null, ftp: F, span: span,
      mid: mid, fast: fast, slow: slow, D: D, base: base, edition: ed,
      cum: cum, temps: D.cols.T, withNP: withNP
    };
  }

  /* ---------- improvement rows: each on its own, never summed ---------- */
  function smithAt(gh) {
    if (gh <= 0) return 0;
    for (var i = 1; i < SMITH.length; i++) if (gh <= SMITH[i][0]) {
      var a = SMITH[i - 1], b = SMITH[i];
      return a[1] + (b[1] - a[1]) * (gh - a[0]) / (b[0] - a[0]);
    }
    return SMITH[SMITH.length - 1][1];
  }

  function fuelBracket(brackets, hours) {
    for (var i = 0; i < brackets.length; i++) if (hours <= brackets[i][0]) return brackets[i];
    return brackets[brackets.length - 1];
  }

  /* picks: {fit, pos, stopsCut}, each a size the rider chose or null.
     A row whose size has not been chosen gets {key, pick:true} and no
     number: the page never picks a size for the rider. Returns rows with
     {key, saved_s} or {key, why}; a row that fails says so. */
  function picked(x) { return isNum(x); }
  function improvements(E, est, rider, picks, brackets) {
    var rows = [], base = est.mid.total, np = est.IF * est.ftp.mid;
    picks = picks || {};
    function rerun(key, extra) {
      var r = runOnce(E, est.D, est.withNP(np, extra));
      rows.push(r.ok ? { key: key, saved_s: base - r.total } : { key: key, why: r.why });
    }
    if (picked(picks.fit)) rerun("fit", { np: np * picks.fit });
    else rows.push({ key: "fit", pick: true });
    if (typeof rider.carbs === "number") {
      var b = fuelBracket(brackets, (base + 60 * (rider.stops || 0)) / 3600);
      var target = Math.min(b[2], 78);
      if (rider.carbs < target) {
        var r0 = smithAt(rider.carbs) / 100, r1 = smithAt(target) / 100, d = (r1 - r0) / (1 - r0);
        rows.push({ key: "gut", saved_s: d * Math.max(0, base - 7200), from: rider.carbs, to: target });
      } else rows.push({ key: "gut", already: true, from: rider.carbs, to: target });
    } else rows.push({ key: "gut", ask: true });
    if (rider.heatTrained) rows.push({ key: "heat", already: true });
    else rerun("heat", { heatKeep: HEAT_TRAINED_KEEP });
    if (est.base.share < 0.54) rerun("group", { share: 0.54 });
    if (picked(picks.pos)) rerun("pos", { cda: est.base.cda * (1 - 0.10 * picks.pos) });
    else rows.push({ key: "pos", pick: true });
    if (est.D.cap > CORNER_CAP + 1e-6) rerun("corner", { cap: CORNER_CAP });
    if (typeof rider.stops === "number" && rider.stops > 0) {
      if (picked(picks.stopsCut)) rows.push({ key: "stops", saved_s: 60 * Math.min(rider.stops, picks.stopsCut) });
      else rows.push({ key: "stops", pick: true });
    }
    return rows;
  }

  /* ---------- fuel ---------- */
  function fuel(brackets, seconds) {
    var h = seconds / 3600, b = fuelBracket(brackets, h);
    return { hours: h, lo: b[1], hi: b[2], label: b[3], totalLo: Math.round(h * b[1]), totalHi: Math.round(h * b[2]) };
  }

  /* where the rider is (bin index) at riding time t */
  function binAt(cum, total, t) {
    if (t >= total) return cum.length - 1;
    var lo = 0, hi = cum.length - 1;
    while (hi - lo > 1) { var m = (lo + hi) >> 1; if (cum[m] <= t) lo = m; else hi = m; }
    return lo;
  }

  return {
    LEVELS: LEVELS, HOURS: HOURS, GROUPS: GROUPS, BANDS: BANDS, IF_MIN: IF_MIN, IF_MAX: IF_MAX,
    hourly: hourly, placeWeather: placeWeather, runOnce: runOnce, estimate: estimate,
    improvements: improvements, fuel: fuel, binAt: binAt, checkRider: checkRider,
    levelOf: levelOf, checkCourse: checkCourse, effortSpan: effortSpan, smithAt: smithAt
  };
});
