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
  const opts = { spanSteps: flags.includes('climbing') ? 2 : 1, visitorSetsEffort: flags.includes('visitor_sets_effort') };
  const t = Date.now();
  const r = core.estimate(E, course, SAMPLE, opts);
  const res = { ok: r.ok, ms: Date.now() - t };
  if (r.ok) {
    Object.assign(res, { IF: r.IF, level: r.level, mid_s: r.mid.total, fast_s: r.fast.total, slow_s: r.slow.total, span: r.span });
    res.rows = core.improvements(E, r, SAMPLE, { fit: 1.05, pos: 0.2, stopsCut: 10 }, BRACKETS);
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
  // A rider so slow that the past race-day weather does not cover the ride: no time, a reason.
  const slow = core.estimate(E, course, Object.assign({}, SAMPLE, { ftp: 80, kg: 160, gearKg: 45, IF: 0.40 }), opts);
  res.uncovered = { ok: slow.ok, why: slow.why || null };
  out[slug] = res;
}
process.stdout.write(JSON.stringify(out));
