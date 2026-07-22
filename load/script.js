// Specula API load harness (k6).
//
// Drives the authed FastAPI the way the Next BFF does: a short-lived HS256 service
// JWT (iss=specula-web, aud=specula-api, sub=<seeded user>) in an `Authorization:
// Bearer` header. See load/README.md for how to run and what the thresholds mean.
//
// Two scenarios:
//   browse  (default)  — ramping VUs hammering the read path: GET /jobs + GET /dashboard.
//   ingest  (INGEST=1) — a METERED trigger of POST /runs at a low arrival rate. Off by
//                        default because it mutates the tenant's latest-run and, once the
//                        NET rate-limit lands, is expected to 429 past the hourly cap
//                        (which this harness records as "rate limited", not an error).
import http from "k6/http";
import { check, sleep, fail } from "k6";
import crypto from "k6/crypto";
import encoding from "k6/encoding";
import { Trend, Rate, Counter } from "k6/metrics";

// --- config (all overridable via `k6 run -e KEY=value`) ---
const API_URL = __ENV.API_URL || "http://localhost:8000";
const SECRET = __ENV.SERVICE_JWT_SECRET || "";
const SUB = __ENV.USER_SUB || "demo-user";
const EMAIL = __ENV.USER_EMAIL || "demo@specula.app";
const ISSUER = __ENV.JWT_ISSUER || "specula-web";
const AUDIENCE = __ENV.JWT_AUDIENCE || "specula-api";
const VUS = Number(__ENV.VUS || 20);
const RAMP = __ENV.RAMP || "20s";
const HOLD = __ENV.HOLD || "40s";
const INGEST = (__ENV.INGEST || "0") === "1";

// --- custom metrics (per-endpoint p95 + a controlled error rate) ---
const jobsLatency = new Trend("jobs_latency", true);
const dashLatency = new Trend("dashboard_latency", true);
const ingestLatency = new Trend("ingest_latency", true);
// endpoint_errors is OUR definition of "wrong": a read that isn't 200, or an ingest
// that is neither 201 (accepted) nor 429 (metered/rate-limited). The built-in
// http_req_failed would wrongly count expected 429s as failures.
const endpointErrors = new Rate("endpoint_errors");
const rateLimited = new Counter("rate_limited_429");

// Mint an HS256 service JWT entirely in-VM (k6 has no jose). base64url-no-pad segments,
// signed with HMAC-SHA256 — the exact shape apps/api/specula_api/auth.py validates.
function mintJwt(ttlSeconds) {
  const now = Math.floor(Date.now() / 1000);
  const seg = (obj) => encoding.b64encode(JSON.stringify(obj), "rawurl");
  const header = seg({ alg: "HS256", typ: "JWT" });
  const payload = seg({
    sub: SUB,
    email: EMAIL,
    name: "Load Test",
    iss: ISSUER,
    aud: AUDIENCE,
    iat: now,
    exp: now + ttlSeconds,
  });
  const signingInput = `${header}.${payload}`;
  const sig = crypto.hmac("sha256", SECRET, signingInput, "base64rawurl");
  return `${signingInput}.${sig}`;
}

export const options = {
  scenarios: {
    browse: {
      executor: "ramping-vus",
      exec: "browse",
      startVUs: 0,
      stages: [
        { duration: RAMP, target: VUS },
        { duration: HOLD, target: VUS },
        { duration: "10s", target: 0 },
      ],
      gracefulRampDown: "5s",
    },
    ...(INGEST
      ? {
          ingest: {
            executor: "constant-arrival-rate",
            exec: "ingest",
            rate: 1,
            timeUnit: "10s", // ~1 trigger / 10s = deliberately metered
            duration: HOLD,
            preAllocatedVUs: 2,
            maxVUs: 4,
          },
        }
      : {}),
  },
  thresholds: {
    // Pass/fail gates. Cross either → investigate before trusting the run.
    endpoint_errors: ["rate<0.01"], // < 1% unexpected responses
    jobs_latency: ["p(95)<500"], // GET /jobs p95 under 500ms
    dashboard_latency: ["p(95)<500"], // GET /dashboard p95 under 500ms
  },
};

// Mint one token up front and validate auth/reachability before the ramp, so a bad
// secret or a down API fails loudly here instead of as 100% errors mid-run. TTL covers
// the whole run (default ~70s) with generous headroom.
export function setup() {
  if (!SECRET) {
    fail("SERVICE_JWT_SECRET is required (e.g. -e SERVICE_JWT_SECRET=dev-fanout-secret).");
  }
  const token = mintJwt(3600);
  const res = http.get(`${API_URL}/api/v1/jobs`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status !== 200) {
    fail(
      `warm-up GET /api/v1/jobs → ${res.status} (expected 200). ` +
        `Check API_URL, SERVICE_JWT_SECRET, and that the API + its DB are up.`,
    );
  }
  return { token };
}

export function browse(data) {
  const headers = { Authorization: `Bearer ${data.token}` };
  // 3:1 jobs:dashboard — the Jobs view is the app's primary read.
  if (Math.random() < 0.75) {
    const res = http.get(`${API_URL}/api/v1/jobs`, {
      headers,
      tags: { endpoint: "jobs" },
    });
    jobsLatency.add(res.timings.duration);
    endpointErrors.add(res.status !== 200);
    check(res, { "GET /jobs is 200": (r) => r.status === 200 });
  } else {
    const res = http.get(`${API_URL}/api/v1/dashboard`, {
      headers,
      tags: { endpoint: "dashboard" },
    });
    dashLatency.add(res.timings.duration);
    // 200 whether it's the DASH summary or the pre-merge stub — both are valid.
    endpointErrors.add(res.status !== 200);
    check(res, { "GET /dashboard is 200": (r) => r.status === 200 });
  }
  sleep(Math.random() * 0.5 + 0.1); // 100-600ms think time
}

export function ingest(data) {
  const headers = { Authorization: `Bearer ${data.token}` };
  const res = http.post(`${API_URL}/api/v1/runs`, null, {
    headers,
    tags: { endpoint: "runs" },
  });
  ingestLatency.add(res.timings.duration);
  if (res.status === 429) {
    rateLimited.add(1); // expected once past the NET hourly cap — metered, not an error
  }
  endpointErrors.add(res.status !== 201 && res.status !== 429);
  check(res, { "POST /runs is 201 or 429": (r) => r.status === 201 || r.status === 429 });
}
