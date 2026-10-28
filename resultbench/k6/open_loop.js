// k6 cross-check of the ResultBench load generator (plan section 7.2).
//
// The thesis uses its own Go generator because it must model refresh
// behaviour and check every response against ground truth. This script
// applies the same open-loop arrival pattern with a standard tool, without
// refreshes, so the two can be compared on latency and success rate for the
// same design and load. Agreement within run-to-run noise supports the
// validity of the Go generator's measurements.
//
//   docker run --rm --network rb-net -v "$PWD/k6:/scripts" grafana/k6:0.57.0 run \
//     -e TARGET=http://portal:8080 -e MODE=constant -e RATE=200 -e DURATION=60s /scripts/open_loop.js
//
// MODE=constant: RATE requests/s for DURATION (compare with `rb calibrate` steps).
// MODE=surge:    PEAK requests/s at release, then a piecewise approximation of
//                the exponential decay in bench/scenarios/core.yaml.
import http from "k6/http";
import { check } from "k6";
import { Counter } from "k6/metrics";

const TARGET = __ENV.TARGET || "http://portal:8080";
const MODE = __ENV.MODE || "constant";
const N = Number(__ENV.N || 1000000);
const BASE = Number(__ENV.ROLL_BASE || 2710000000);
const TIMEOUT = __ENV.TIMEOUT || "10s";
const MAX_VUS = Number(__ENV.MAX_VUS || 5000);

function scenario() {
  if (MODE === "surge") {
    const peak = Number(__ENV.PEAK || 200);
    const tau = Number(__ENV.TAU || 90);
    const stages = [{ target: peak, duration: "5s" }];
    // Linear segments at 0.5 tau steps approximate peak * exp(-t / tau).
    for (let k = 1; k <= 6; k++) {
      stages.push({ target: Math.max(1, Math.round(peak * Math.exp(-(k * 0.5)))), duration: `${Math.round(tau / 2)}s` });
    }
    return { executor: "ramping-arrival-rate", startRate: Math.round(peak * 0.2), timeUnit: "1s",
             preAllocatedVUs: Math.min(MAX_VUS, peak * 2), maxVUs: MAX_VUS, stages };
  }
  return { executor: "constant-arrival-rate", rate: Number(__ENV.RATE || 100), timeUnit: "1s",
           duration: __ENV.DURATION || "60s", preAllocatedVUs: 200, maxVUs: MAX_VUS };
}

export const options = {
  scenarios: { load: scenario() },
  summaryTrendStats: ["med", "p(95)", "p(99)", "max"],
};

const wrong = new Counter("wrong_student");

export default function () {
  const roll = BASE + Math.floor(Math.random() * N);
  const res = http.get(`${TARGET}/result?roll=${roll}`, { timeout: TIMEOUT });
  const ok = check(res, {
    "status 200": (r) => r.status === 200,
    "within 2s": (r) => r.timings.duration <= 2000,
  });
  if (res.status === 200) {
    let body = null;
    try { body = res.json(); } catch (e) { /* not JSON: counted by the status check */ }
    if (!body || body.roll !== roll) wrong.add(1);
  }
  return ok;
}
