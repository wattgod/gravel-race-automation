// Parity: the Surge Check port must give Endure's answer on Endure's own fixture.
import { readFileSync } from "node:fs";
import { readRide, band } from "../wordpress/surge_check/surge-core.js";
const fx = JSON.parse(readFileSync(new URL("./fixtures/surge-index-parity.json", import.meta.url), "utf8"));
const r = readRide(fx.power.map((v, t) => ({ t, v })), fx.ftpW);
const e = fx.expected;
const ok = r.kind === "read" && r.index === e.index && r.timePct === e.timePct && r.harderPct === e.harder
  && JSON.stringify(r.surges.map((s) => [s.t0, s.t1])) === JSON.stringify(e.surges);
// Smart recording is refused, not misread.
const sparse = [];
for (let t = 0; t < 4 * 2800; t += 4) sparse.push({ t, v: 150 });
const sparseOk = readRide(sparse, 250).reason === "sparse";
const bandsOk = [0, 9, 10, 19, 20, 29, 30, 80].map((i) => band(i).key).join() === "smooth,smooth,normal,normal,surgy,surgy,very_surgy,very_surgy";
console.log(JSON.stringify({ ok, sparseOk, bandsOk, got: [r.index, r.timePct, r.harderPct] }));
process.exit(ok && sparseOk && bandsOk ? 0 : 1);
