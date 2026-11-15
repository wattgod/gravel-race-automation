/* Gravel God finish-time planner: Web Worker.
 * Loads the frozen engine and the planner core in their own scope (the
 * engine's top-level names never meet the page's scripts), fetches the
 * race's course once, and answers estimate requests with plain data.
 * Script and course URLs come from the page in the "init" message.
 */
"use strict";
var course = null, core = null, E = null, initError = null;

function geometry(c) {
  var cols = c.bins.cols, n = cols.g.length, step = c.bins.step_m;
  var k = Math.max(1, Math.floor(n / 500)), la = [], lo = [], alt = [], km = [];
  for (var i = 0; i < n; i += k) { la.push(cols.la[i]); lo.push(cols.lo[i]); alt.push(cols.alt[i]); km.push(i * step / 1000); }
  la.push(cols.la[n - 1]); lo.push(cols.lo[n - 1]); alt.push(cols.alt[n - 1]); km.push((n - 1) * step / 1000);
  return { la: la, lo: lo, alt: alt, km: km, total_km: n * step / 1000 };
}

function hoursOf(est) {
  var out = [], total = est.mid.total, step = course.bins.step_m, n = Math.ceil(total / 3600);
  for (var h = 1; h <= n; h++) {
    var t = Math.min(h * 3600, total), i = core.binAt(est.cum, total, t);
    out.push({ h: h, t: t, km: (i + 1) * step / 1000, temp: est.temps[i], la: course.bins.cols.la[i], lo: course.bins.cols.lo[i] });
  }
  return out;
}

self.onmessage = function (ev) {
  var m = ev.data || {};
  if (m.type === "init") {
    try {
      importScripts(m.engine, m.core);
      core = self.GGPlannerCore;
      E = { prep: self.prep, planNP: self.planNP, stats: self.stats, heat: self.heat, total: self.total,
        ifDefault: self.ifDefault, defaultIF: self.defaultIF };
      for (var key in E) if (typeof E[key] !== "function") throw new Error("engine function missing: " + key);
    } catch (err) {
      initError = "the planner could not load (" + err.message + ")";
      self.postMessage({ type: "init", ok: false, why: initError });
      return;
    }
    fetch(m.course, { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) throw new Error("course file HTTP " + r.status);
      return r.json();
    }).then(function (c) {
      var bad = core.checkCourse(c);
      if (bad) throw new Error(bad);
      course = c;
      self.postMessage({ type: "init", ok: true, geo: geometry(c) });
    }).catch(function (err) {
      initError = "the course could not load (" + err.message + ")";
      self.postMessage({ type: "init", ok: false, why: initError });
    });
    return;
  }
  if (m.type === "run") {
    if (!course) { self.postMessage({ type: "run", id: m.id, ok: false, why: initError || "the course is still loading" }); return; }
    var est;
    try { est = core.estimate(E, course, m.rider, m.opts); }
    catch (err) { est = { ok: false, why: "the model stopped with an error (" + err.message + ")" }; }
    if (!est.ok) { self.postMessage({ type: "run", id: m.id, ok: false, why: est.why, miss: est.miss || null }); return; }
    var rows;
    try { rows = core.improvements(E, est, m.rider, m.picks, m.brackets); }
    catch (err) { rows = null; }
    self.postMessage({
      type: "run", id: m.id, ok: true,
      level: est.level, IF: est.IF, IFsource: est.IFsource, defaultIF: est.defaultIF,
      ftp: { mid: est.ftp.mid, lo: est.ftp.lo, hi: est.ftp.hi },
      span: est.span, mid: est.mid.total, fast: est.fast.total, slow: est.slow.total,
      np: est.IF * est.ftp.mid, ap: est.mid.ap,
      edition: { date: est.edition.date, start_local: est.edition.start_local },
      hours: hoursOf(est), rows: rows
    });
  }
};
