// Surge Check page script (gravelgodcycling.com/surge-check/).
// Reads .fit files in the browser (nothing is uploaded), scores each easy ride
// with the Surge Index (surge-core.js, Endure's own maths), and shows the
// chosen ride in Endure's Analyze view (an iframe of endurelabs.app/embed/surge)
// with every surge shaded. The ride reaches that frame only by postMessage,
// inside this browser. If the frame never answers, a plain chart stands in.
// DOM is built with createElement/textContent only, never from HTML strings.

import FitParser from "./vendor/fit-file-parser-2.1.0.js";
import { readRide, BANDS, band, centredMean } from "./surge-core.js";

const root = document.getElementById("gg-sc");
const $ = (id) => document.getElementById(id);
const out = $("gg-sc-out");
const ftpInput = $("gg-sc-ftp");
const drop = $("gg-sc-drop");
const fileInput = $("gg-sc-file");
const status = $("gg-sc-status");

const MAX_FILES = 30;
const MAX_BYTES = 40 * 1024 * 1024;
/** Endure's embed takes FTPs in this range (surge-embed-bridge.ts); the page holds the same line so the two always agree. */
const FTP_MIN = 50, FTP_MAX = 1000;
const CYCLING = new Set(["cycling", "e_biking"]);
const EMBED_TIMEOUT_MS = 8000;
const HOST_SOURCE = "gravel-god-surge-check";
const PAGE_SOURCE = "endure-surge-embed";
const ENDURE_HOME = "https://endurelabs.app/?utm_source=gravelgod&utm_medium=surge-check&utm_campaign=surge-index";

/** Endure's origin; a local Endure only when this page itself is local (?endure=http://localhost:3100). */
const ENDURE = (() => {
  const fallback = root.dataset.endure || "https://endurelabs.app";
  const local = /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
  const asked = new URLSearchParams(location.search).get("endure");
  if (local && asked) {
    try { return new URL(asked).origin; } catch { return fallback; }
  }
  return fallback;
})();

let rides = [];        // { name, start, fileFtp, samples, records } | { name, start?, error } | { name, start, notRide }
let selected = null;   // index into rides
let ftpTyped = false;  // until the rider types one, FTP comes from the newest bike ride's file
let filesTaken = 0;
let queue = Promise.resolve();
let embed = null;      // { frame, ready, failed, timer }

const MISS = {
  not_easy: (r) => `Not an easy ride (IF ${r.intensity.toFixed(2)})`,
  too_short: () => "Under 45 minutes",
  no_power: () => "No power data",
  no_ftp: () => "Enter your FTP",
  sparse: () => "Records every few seconds. Set 1-second recording",
  not_a_ride: () => "Not a bike ride",
};

// ── DOM helpers ──
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children.flat()) if (child != null) node.append(child);
  return node;
}

function track(name, params) {
  if (typeof window.gtag === "function") window.gtag("event", name, params);
}

// ── Reading files ──
function parseFit(buffer) {
  return new Promise((resolve, reject) => {
    const parser = new FitParser({ force: true, speedUnit: "m/s", lengthUnit: "m", temperatureUnit: "celsius", mode: "list" });
    parser.parse(buffer, (error, data) => (error ? reject(error) : resolve(data)));
  });
}

const fileFtpOf = (data) => {
  const zones = Array.isArray(data.zones_target) ? data.zones_target[0] : data.zones_target;
  const ftp = zones?.functional_threshold_power ?? data.user_profile?.functional_threshold_power;
  return Number.isFinite(ftp) && ftp > 0 ? ftp : null;
};

/** One entry per session: a multisport or merged file is several rides, and only bike sessions are read. */
async function parse(name, buffer) {
  let data;
  try { data = await parseFit(buffer); } catch { return [{ name, error: "Couldn't read this file" }]; }
  const records = (data.records || []).filter((r) => r.timestamp instanceof Date);
  if (!records.length) return [{ name, error: "No ride data" }];
  const fileFtp = fileFtpOf(data);
  const sessions = (data.sessions || []).filter((s) => s.start_time instanceof Date).sort((a, b) => a.start_time - b.start_time);
  // Half-open windows to the session end (+1 ms keeps its last record), never past the next session's start.
  const spans = sessions.length
    ? sessions.map((s, i) => {
        const next = sessions[i + 1] ? +sessions[i + 1].start_time : Infinity;
        const own = Number.isFinite(s.total_elapsed_time) ? +s.start_time + 1000 * s.total_elapsed_time + 1 : next;
        return { start: +s.start_time, end: Math.min(own, next), sport: s.sport };
      })
    : [{ start: +records[0].timestamp, end: Infinity, sport: undefined }];
  return spans.map((span) => {
    const base = { name, start: new Date(span.start), fileFtp };
    if (span.sport && !CYCLING.has(span.sport)) return { ...base, notRide: true };
    const own = records.filter((r) => +r.timestamp >= span.start && +r.timestamp < span.end);
    if (!own.length) return { ...base, error: "No ride data" };
    const t = (r) => (+r.timestamp - span.start) / 1000;
    return { ...base, records: own, samples: own.filter((r) => r.power != null).map((r) => ({ t: t(r), v: r.power })) };
  });
}

function addFiles(files) {
  const list = [...files];
  queue = queue.then(() => ingest(list));
}

async function ingest(files) {
  const take = files.slice(0, Math.max(0, MAX_FILES - filesTaken));
  if (!take.length) return;
  track("surge_check_files", { files: take.length });
  const parsed = [];
  for (const [k, f] of take.entries()) {
    status.hidden = false;
    status.textContent = `Reading ${k + 1} of ${take.length}…`;
    if (f.size > MAX_BYTES) { parsed.push({ name: f.name, error: "File too large" }); continue; }
    let sessions;
    try { sessions = await parse(f.name, await f.arrayBuffer()); }
    catch { sessions = [{ name: f.name, error: "Couldn't read this file" }]; }
    // Only a file that read counts toward the cap: a bad one costs the rider nothing.
    if (sessions.some((r) => !r.error)) filesTaken += 1;
    parsed.push(...sessions);
  }
  status.hidden = true;
  rides = rides.concat(parsed).sort((a, b) => (b.start ?? 0) - (a.start ?? 0));
  if (!ftpTyped) {
    const withFtp = rides.find((r) => r.fileFtp && r.samples);
    if (withFtp) ftpInput.value = withFtp.fileFtp;
  }
  selected = null;
  render(true);
}

// ── Reading rides ──
const median = (xs) => { const s = [...xs].sort((a, b) => a - b), m = Math.floor(s.length / 2); return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const fmtDate = (d) => (d ? d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "");
const fmtDur = (s) => `${Math.floor(s / 3600)}:${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}`;
const timeWords = (t) => (t < 1 ? "under 1" : String(t));

function render(fromUser = false) {
  out.replaceChildren();
  if (!rides.length) return;
  const ftp = Number(ftpInput.value);
  if (!(ftp >= FTP_MIN && ftp <= FTP_MAX)) {
    out.append(el("p", { class: "gg-sc-err", text: `Enter your FTP in watts (${FTP_MIN}–${FTP_MAX}).` }));
    analyze.hidden = true;
    return;
  }
  const reads = rides.map((r) => (r.error ? { kind: "error" } : r.notRide ? { kind: "unavailable", reason: "not_a_ride" } : readRide(r.samples, ftp)));
  const easy = reads.map((r, i) => [r, i]).filter(([r]) => r.kind === "read");
  if (selected == null || reads[selected]?.kind !== "read") selected = easy[0]?.[1] ?? null;

  if (easy.length) {
    const many = easy.length > 1;
    const index = many ? Math.round(median(easy.map(([r]) => r.index))) : easy[0][0].index;
    const harder = easy.map(([r]) => r.harderPct).filter((h) => h != null);
    const harderMid = harder.length ? Math.round(median(harder)) : null;
    const timeMid = Math.round(median(easy.map(([r]) => r.timePct)));
    const b = band(index);
    if (fromUser) track("surge_check_result", { band: b.key, rides: easy.length });
    const pin = el("span", { class: "gg-sc-pin" });
    pin.style.left = `${(Math.min(index, 42) / 42) * 100}%`;
    out.append(
      el("div", { class: "gg-sc-head" },
        el("div", { class: "gg-sc-big", text: String(index) }),
        el("div", { class: "gg-sc-band", text: b.label })),
      el("p", { class: "gg-sc-verdict", "data-band": b.key, text: b.line(many) }),
      el("p", { class: "gg-sc-sub", text:
        `${many ? `Median of ${easy.length} easy rides · ` : ""}${index}% of the load in ${timeWords(timeMid)}% of the time` +
        (harderMid != null ? ` · ${harderMid}% more load than the same work ridden smooth` : "") }),
      el("div", { class: "gg-sc-scale", role: "img", "aria-label": `Surge Index ${index}, band ${b.label}` },
        BANDS.map((x) => el("div", { class: x === b ? "on" : null })), pin),
      el("div", { class: "gg-sc-ticks" }, BANDS.map((x) => el("span", { text: x.label }))),
    );
  }

  const tbody = el("tbody");
  reads.forEach((r, i) => {
    const ride = rides[i];
    if (r.kind === "read") {
      const row = el("tr", { class: `gg-sc-pick${i === selected ? " gg-sc-sel" : ""}` },
        el("td", {}, el("button", { type: "button", class: "gg-sc-rowbtn", "aria-pressed": i === selected ? "true" : "false", text: fmtDate(ride.start) || ride.name })),
        el("td", { class: "gg-sc-num", text: fmtDur(r.readS) }),
        el("td", { class: "gg-sc-num", text: String(r.index) }),
        el("td", { class: "gg-sc-num", text: r.harderPct == null ? "–" : `${r.harderPct}%` }),
        el("td", { class: "gg-sc-bandcol", text: r.band.label }));
      row.addEventListener("click", () => { selected = i; render(); });
      tbody.append(row);
    } else {
      const why = r.kind === "error" ? ride.error : MISS[r.reason](r);
      tbody.append(el("tr", { class: "gg-sc-skip" }, el("td", { text: fmtDate(ride.start) || ride.name }), el("td", { colspan: 4, text: why })));
    }
  });
  out.append(el("div", { class: "gg-sc-rides" },
    el("h2", { class: "gg-sc-label", text: "Rides" }),
    el("table", {},
      el("thead", {}, el("tr", {},
        el("th", { text: "Date" }), el("th", { class: "gg-sc-num", text: "Time" }), el("th", { class: "gg-sc-num", text: "Surge Index" }),
        el("th", { class: "gg-sc-num", text: "Extra load" }), el("th", { class: "gg-sc-bandcol", text: "Band" }))),
      tbody)));
  if (easy.length === 1) out.append(el("p", { class: "gg-sc-note", text: "One ride says little. Drop five or more." }));
  if (selected != null) showRide(rides[selected], reads[selected], ftp);
}

// ── Endure's Analyze view ──
const analyze = $("gg-sc-analyze");
const frameWrap = $("gg-sc-frame");
const fallback = $("gg-sc-fallback");

function perSecond(records, start, pick) {
  const last = Math.round((+records[records.length - 1].timestamp - start) / 1000);
  const arr = new Array(Math.min(last + 1, 48 * 3600 + 1)).fill(null);
  for (const r of records) {
    const t = Math.round((+r.timestamp - start) / 1000);
    const v = pick(r);
    if (t >= 0 && t < arr.length && Number.isFinite(v)) arr[t] = v;
  }
  return arr;
}

function rideMessage(ride, ftp) {
  const start = +ride.start, rec = ride.records;
  return {
    source: HOST_SOURCE, v: 1, type: "ride",
    ftpW: ftp,
    units: /^en-US\b/.test(navigator.language || "") ? "imperial" : "metric",
    theme: "light",
    power: perSecond(rec, start, (r) => r.power),
    hr: perSecond(rec, start, (r) => r.heart_rate),
    cadence: perSecond(rec, start, (r) => r.cadence),
    speed: perSecond(rec, start, (r) => r.enhanced_speed ?? r.speed),
    altitude: perSecond(rec, start, (r) => r.enhanced_altitude ?? r.altitude),
    lat: perSecond(rec, start, (r) => r.position_lat),
    lng: perSecond(rec, start, (r) => r.position_long),
  };
}

let current = null; // { ride, read, ftp }

function showRide(ride, read, ftp) {
  current = { ride, read, ftp };
  analyze.hidden = false;
  if (!embed) startEmbed();
  if (embed.ready) sendRide();
  else drawFallback(); // stands in until Endure's view answers, and for good if it never does
}

function startEmbed() {
  const frame = el("iframe", {
    src: `${ENDURE}/embed/surge`,
    title: "Endure Analyze view",
    loading: "eager",
    referrerpolicy: "strict-origin",
    class: "gg-sc-iframe",
  });
  embed = { frame, ready: false, failed: false, timer: null };
  frameWrap.hidden = true;
  embed.timer = setTimeout(() => { if (!embed.ready) failEmbed(); }, EMBED_TIMEOUT_MS);
  frameWrap.append(frame);
}

function failEmbed() {
  embed.ready = false;
  embed.failed = true;
  frameWrap.hidden = true;
  drawFallback();
}

function sendRide() {
  if (!current || !embed?.frame.contentWindow) return;
  embed.frame.contentWindow.postMessage(rideMessage(current.ride, current.ftp), ENDURE);
}

window.addEventListener("message", (event) => {
  if (!embed || event.origin !== ENDURE || event.source !== embed.frame.contentWindow) return;
  const data = event.data;
  if (!data || data.source !== PAGE_SOURCE || data.v !== 1) return;
  if (data.type === "ready" && !embed.failed) {
    embed.ready = true;
    clearTimeout(embed.timer);
    frameWrap.hidden = false;
    fallback.hidden = true;
    sendRide();
  } else if (data.type === "error") {
    failEmbed();
  } else if (data.type === "height" && Number.isFinite(data.px)) {
    embed.frame.style.height = `${Math.min(Math.max(data.px, 200), 2000)}px`;
  }
});

// ── Stand-in chart when Endure can't be shown ──
function drawFallback() {
  if (!current) return;
  const { ride, read, ftp } = current;
  fallback.hidden = false;
  fallback.replaceChildren();
  const cv = el("canvas", { class: "gg-sc-canvas", role: "img", "aria-label": `Power with ${read.surges.length} surges marked` });
  const tip = el("div", { class: "gg-sc-tip" });
  fallback.append(
    el("h2", { class: "gg-sc-label", text: `${fmtDate(ride.start)} · Surge Index ${read.index} · ${read.surges.length} surges` }),
    el("div", { class: "gg-sc-chart" }, cv, tip),
    el("p", { class: "gg-sc-built" }, "Built on ", el("a", { href: ENDURE_HOME, target: "_blank", rel: "noopener", text: "Endure Labs" })),
  );
  const css = getComputedStyle(document.documentElement);
  const col = (n) => css.getPropertyValue(n).trim();
  const dpr = window.devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight;
  cv.width = W * dpr; cv.height = H * dpr;
  const g = cv.getContext("2d"); g.scale(dpr, dpr);
  const n = read.power.length, top = 2.0, padB = 18, rug = 14;
  const smooth = centredMean(Array.from(read.power, (w) => (Number.isNaN(w) ? 0 : w)), 30);
  const x = (t) => (t / n) * W, y = (pct) => (H - padB - rug - 4) * (1 - Math.min(pct, top) / top);
  g.fillStyle = col("--gg-color-light-gold");
  for (const s of read.surges) g.fillRect(x(s.t0), H - padB - rug, Math.max(1, x(s.t1) - x(s.t0)), rug);
  g.strokeStyle = col("--gg-color-secondary-brown"); g.setLineDash([3, 3]); g.lineWidth = 1;
  g.beginPath(); g.moveTo(0, y(0.9)); g.lineTo(W, y(0.9)); g.stroke(); g.setLineDash([]);
  g.strokeStyle = col("--gg-color-primary-brown"); g.lineWidth = 1.25; g.beginPath();
  for (let px = 0; px < W; px += 1) {
    const a = Math.floor((px / W) * n), b = Math.max(a + 1, Math.floor(((px + 1) / W) * n));
    let m = 0; for (let i = a; i < b; i += 1) if (read.read[i] && smooth[i] > m) m = smooth[i];
    const yy = y(m / ftp); px ? g.lineTo(px, yy) : g.moveTo(px, yy);
  }
  g.stroke();
  g.fillStyle = col("--gg-color-secondary-brown"); g.font = "11px 'Sometype Mono', monospace";
  g.fillText("90% FTP", W - 60, y(0.9) - 6);
  const hours = n / 3600, step = hours > 4 ? 2 : hours > 2 ? 1 : 0.5;
  for (let h = step; h < hours; h += step) g.fillText(`${h}h`, x(h * 3600) - 8, H - 4);
  cv.addEventListener("pointermove", (e) => {
    const rect = cv.getBoundingClientRect(), px = Math.max(0, Math.min(W, e.clientX - rect.left));
    const t = Math.floor((px / W) * n), slack = (n / W) * 4;
    const s = read.surges.find((q) => t >= q.t0 - slack && t < q.t1 + slack);
    const at = `${Math.floor(t / 3600)}h ${String(Math.floor((t % 3600) / 60)).padStart(2, "0")}m`;
    let txt = `${at} · ${Math.round(smooth[t])} W`;
    if (s) {
      let sum = 0; for (let i = s.t0; i < s.t1; i += 1) sum += read.power[i];
      txt = `${at} · surge ${s.t1 - s.t0} s at ${Math.round((100 * sum) / (s.t1 - s.t0) / ftp)}% FTP`;
    }
    tip.textContent = txt; tip.style.display = "block";
    tip.style.left = `${Math.min(px, W - tip.offsetWidth)}px`;
  });
  cv.addEventListener("pointerleave", () => { tip.style.display = "none"; });
}

// ── Inputs ──
fileInput.addEventListener("change", () => { if (fileInput.files.length) addFiles(fileInput.files); fileInput.value = ""; });
drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); } });
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("gg-sc-over"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("gg-sc-over"); }));
drop.addEventListener("drop", (e) => { if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files); });
ftpInput.addEventListener("input", () => { ftpTyped = true; render(); });
let resizeT;
window.addEventListener("resize", () => { clearTimeout(resizeT); resizeT = setTimeout(() => { if (!fallback.hidden) drawFallback(); }, 150); });
