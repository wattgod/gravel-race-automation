// Surge Index, ported line for line from Endure's src/lib/analysis/surge-index.ts
// (readSurgeIndex + surgeHarderPct, spec v3.1). Parity gate: tests/test_surge_check.py
// runs tests/surge_check_parity.mjs against the fixture Endure's own test uses.

export const GAP_FILL_S = 2;
export const MIN_READ_S = 2700;
export const SURGE_FTP_SHARE = 0.9;
export const SURGE_SMOOTH_S = 3;
export const SURGE_BRIDGE_S = 2;
export const SURGE_MIN_S = 5;
export const SURGE_MAX_S = 60;
export const MAX_ELAPSED_S = 48 * 3600;
export const EASY_MAX_IF = 0.75;
export const PEDAL_FTP_SHARE = 0.1;
export const MAX_SPACING_S = 1.5;

/**
 * Bands from 752 easy rides of 16 coached riders (Oct 2026): relative to that
 * group, not a harm threshold. One fixed line per band, the same every time.
 */
export const BANDS = [
  { max: 10, key: "smooth", label: "Smooth",
    line: (many) => `Easy, ridden easy. ${many ? "These rides were" : "This ride was"} what the workout asked for.` },
  { max: 20, key: "normal", label: "Normal",
    line: (many) => `A few kicks, but they didn't change ${many ? "the rides" : "the ride"}. On a typical ride, 7 of the 16 riders we studied sit here, more than in any other band.` },
  { max: 30, key: "surgy", label: "Surgy",
    line: (many) => `A fifth or more of the load came in short surges. The summary says easy; the surges quietly changed ${many ? "the workouts" : "the workout"}.` },
  { max: Infinity, key: "very_surgy", label: "Very surgy",
    line: (many) => `Close to a third of the load or more came in surges. That's a lot of hard riding for ${many ? "easy days" : "an easy day"}.` },
];
export const band = (index) => BANDS.find((b) => index < b.max);

export function grid(samples, length) {
  const out = new Float64Array(length).fill(Number.NaN);
  for (const { t, v } of samples) {
    const s = Math.round(t);
    if (s >= 0 && s < length && Number.isFinite(v)) out[s] = v;
  }
  return out;
}

export function fillShortGaps(values) {
  const out = Float64Array.from(values);
  let i = 0;
  while (i < out.length) {
    if (!Number.isNaN(out[i])) { i += 1; continue; }
    const start = i;
    while (i < out.length && Number.isNaN(out[i])) i += 1;
    if (start > 0 && i < out.length && i - start <= GAP_FILL_S) {
      const before = out[start - 1], after = out[i], span = i - start + 1;
      for (let k = start; k < i; k += 1) out[k] = before + ((after - before) * (k - start + 1)) / span;
    }
  }
  return out;
}

export function centredMean(values, window) {
  const n = values.length, before = Math.floor((window - 1) / 2), after = Math.floor(window / 2);
  const sums = new Float64Array(n + 1);
  for (let i = 0; i < n; i += 1) sums[i + 1] = sums[i] + values[i];
  const out = new Float64Array(n);
  for (let i = 0; i < n; i += 1) {
    const a = Math.max(0, i - before), b = Math.min(n, i + after + 1);
    out[i] = (sums[b] - sums[a]) / (b - a);
  }
  return out;
}

export function bridgedRuns(mask, bridge) {
  const out = [];
  let start = -1, last = -1;
  for (let i = 0; i < mask.length; i += 1) {
    if (mask[i]) { if (start < 0) start = i; last = i; }
    else if (start >= 0 && i - last > bridge) { out.push([start, last + 1]); start = -1; }
  }
  if (start >= 0) out.push([start, last + 1]);
  return out;
}

function median(values) {
  if (values.length === 0) return 0;
  const s = [...values].sort((a, b) => a - b), m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

/** Whole-ride NP on the elapsed clock, a missing second reading 0 W (as Endure's calculateNormalizedPower). */
export function normalizedPower(power) {
  let acc = 0, sum4 = 0, n = 0;
  for (let i = 0; i < power.length; i += 1) {
    acc += Number.isNaN(power[i]) ? 0 : power[i];
    if (i >= 30) acc -= Number.isNaN(power[i - 30]) ? 0 : power[i - 30];
    if (i >= 29) { sum4 += (acc / 30) ** 4; n += 1; }
  }
  return n ? (sum4 / n) ** 0.25 : 0;
}

/** Median spacing (s) between power samples: smart recording logs every few seconds, which the detector can't read. */
export function sampleSpacing(samples) {
  const ts = samples.map((s) => s.t).filter(Number.isFinite).sort((a, b) => a - b);
  const gaps = [];
  for (let i = 1; i < ts.length; i += 1) if (ts[i] > ts[i - 1]) gaps.push(ts[i] - ts[i - 1]);
  return gaps.length ? median(gaps) : 0;
}

export function surgeHarderPct(power, read, surges, ftpW) {
  if (surges.length === 0) return 0;
  const inSurge = new Uint8Array(power.length);
  for (const { t0, t1 } of surges) inSurge.fill(1, t0, t1);
  const share = [], surging = [];
  for (let i = 0; i < power.length; i += 1) {
    if (!read[i]) continue;
    share.push(power[i] / ftpW);
    surging.push(inSurge[i] === 1);
  }
  const outside = share.filter((x, i) => !surging[i] && x > PEDAL_FTP_SHARE);
  if (outside.length === 0) return null;
  const steady = median(outside);
  const calm = share.map((x, i) => (surging[i] ? steady : x));
  let excess = 0, pedalling = 0;
  for (let i = 0; i < share.length; i += 1) {
    excess += share[i] - calm[i];
    if (calm[i] > PEDAL_FTP_SHARE) pedalling += 1;
  }
  const add = pedalling > 0 ? excess / pedalling : 0;
  let load = 0, copy = 0;
  for (let i = 0; i < share.length; i += 1) {
    load += share[i] ** 2;
    copy += (calm[i] > PEDAL_FTP_SHARE ? calm[i] + add : calm[i]) ** 2;
  }
  return copy > 0 ? Math.max(0, Math.round(100 * (load / copy - 1))) : 0;
}

/**
 * Read one ride. samples: [{t: elapsed s, v: watts}]. Returns
 * {kind: "read", index, timePct, harderPct, surges, intensity, power, read, readS, band}
 * or {kind: "unavailable", reason, intensity?}.
 */
export function readRide(samples, ftpW) {
  const miss = (reason, extra = {}) => ({ kind: "unavailable", reason, ...extra });
  if (!(Number.isFinite(ftpW) && ftpW > 0)) return miss("no_ftp");
  if (!samples.some((s) => Number.isFinite(s.t) && Number.isFinite(s.v) && s.v > 0)) return miss("no_power");
  if (sampleSpacing(samples) > MAX_SPACING_S) return miss("sparse");
  let last = 0;
  for (const s of samples) if (Number.isFinite(s.t) && s.t > last && s.t <= MAX_ELAPSED_S) last = s.t;
  const raw = grid(samples, Math.round(last) + 1);
  const power = fillShortGaps(raw);
  const read = Array.from(power, (w) => !Number.isNaN(w));
  const readS = read.filter(Boolean).length;
  if (readS < MIN_READ_S) return miss("too_short");
  const intensity = Math.round(normalizedPower(raw)) / ftpW; // whole watts, as Endure stores NP
  if (!(intensity > 0 && intensity <= EASY_MAX_IF)) return miss("not_easy", { intensity });

  const floor = SURGE_FTP_SHARE * ftpW;
  const surges = [];
  let load = 0, surgeLoad = 0, surgeS = 0;
  for (const [a, b] of bridgedRuns(read, 0)) {
    const stretch = power.subarray(a, b);
    for (const w of stretch) load += (w / ftpW) ** 2;
    const power3 = centredMean(stretch, SURGE_SMOOTH_S);
    for (const [s, e] of bridgedRuns(Array.from(power3, (w) => w >= floor), SURGE_BRIDGE_S)) {
      if (e - s < SURGE_MIN_S || e - s > SURGE_MAX_S) continue;
      surges.push({ t0: a + s, t1: a + e });
      surgeS += e - s;
      for (let i = s; i < e; i += 1) surgeLoad += (stretch[i] / ftpW) ** 2;
    }
  }
  const index = load > 0 ? Math.round((100 * surgeLoad) / load) : 0;
  const timePct = Math.round((100 * surgeS) / readS);
  const harderPct = surgeHarderPct(power, read, surges, ftpW);
  return { kind: "read", index, timePct, harderPct, surges, intensity, power, read, readS, band: band(index) };
}
