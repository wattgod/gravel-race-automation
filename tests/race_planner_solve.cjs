// Runs the public planner core + engine on every shipped course for one sample
// rider, and on one rider whose effort cannot be reached. Prints JSON.
// Called by tests/test_race_planner.py.
'use strict';
const fs = require('fs'), path = require('path');
const ROOT = path.resolve(__dirname, '..');
const E = require(ROOT + '/wordpress/planner/engine7.js');
const core = require(ROOT + '/wordpress/planner/gg-planner-core.js');
const status = JSON.parse(fs.readFileSync(ROOT + '/data/planner/status.json', 'utf8'));
const BRACKETS = JSON.parse(process.argv[2]);
const SAMPLE = { ftp: 250, band: null, kg: 75, gearKg: 9.6, hours: '7-10', levelPick: null,
  group: 'some', IF: null, stops: 30, carbs: 50, heatTrained: false };
const out = {};
for (const [slug, s] of Object.entries(status.races)) {
  if (s.status !== 'eligible' && s.status !== 'flagged') continue;
  const course = JSON.parse(fs.readFileSync(ROOT + '/data/planner/courses/' + slug + '.json', 'utf8'));
  const flags = (s.flags || []).map(f => f.kind);
  const opts = { visitorSetsEffort: flags.includes('visitor_sets_effort') };
  const t = Date.now();
  const r = core.estimate(E, course, SAMPLE, opts);
  const res = { ok: r.ok, ms: Date.now() - t };
  if (r.ok) {
    Object.assign(res, { IF: r.IF, level: r.level, mid_s: r.mid.total, fast_s: r.fast.total, slow_s: r.slow.total, span: r.span });
    res.rows = core.improvements(E, r, SAMPLE, { fit: 1.05, pos: 0.2, stopsCut: 10 }, BRACKETS);
    // No size picked yet: those rows carry no number.
    res.rows_unpicked = core.improvements(E, r, SAMPLE, { fit: null, pos: null, stopsCut: null }, BRACKETS);
  } else Object.assign(res, { why: r.why, miss: r.miss });
  // A course with a gap in its data: no time, a reason (never read as zero).
  const broken = JSON.parse(JSON.stringify(course));
  broken.bins.cols.g[10] = null;
  const bad = core.estimate(E, broken, SAMPLE, opts);
  res.broken = { ok: bad.ok, why: bad.why || null, has_time: !!(bad.mid && bad.mid.total) };
  // The engine's own solver failing (target power outside its bracket): no time, a reason.
  const D = { cols: Object.assign({}, course.bins.cols, { T: course.bins.cols.g.map(() => 15), ws: course.bins.cols.g.map(() => 0), wd: course.bins.cols.g.map(() => 0) }),
    crr: course.engine.crr, wf: course.engine.wf, cap: course.engine.cap, phi: course.engine.phi };
  const fail = core.runOnce(E, D, { np: -5, m: 85, cda: 0.332, cap: course.engine.cap, share: 0, heatKeep: 0 });
  res.solver_fail = { ok: fail.ok, why: fail.why || null, has_time: fail.total != null };
  const noTime = (c) => { const x = core.estimate(E, c, SAMPLE, opts); return { ok: x.ok, why: x.why || null, has_time: !!(x.mid && x.mid.total) }; };
  // Weather that stops two hours after the start: the ride is not covered.
  const short = JSON.parse(JSON.stringify(course));
  for (const w of short.weather.editions[0].openmeteo) {
    const h = w.hourly, i = h.time.findIndex(t => Date.parse(t + 'Z') / 1000 - w.utc_offset_seconds >= Date.parse(short.weather.editions[0].start_iso) / 1000);
    for (const k of Object.keys(h)) h[k] = h[k].slice(0, i + 2);
  }
  res.uncovered = noTime(short);
  // Weather with no hours at all.
  const empty = JSON.parse(JSON.stringify(course));
  for (const w of empty.weather.editions[0].openmeteo) for (const k of Object.keys(w.hourly)) w.hourly[k] = [];
  res.empty_weather = noTime(empty);
  // A missing model setting is never read as zero.
  const nocrr = JSON.parse(JSON.stringify(course));
  nocrr.engine.crr = null;
  res.no_crr = noTime(nocrr);
  out[slug] = res;
}
process.stdout.write(JSON.stringify(out));
