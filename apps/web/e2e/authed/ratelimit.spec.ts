import { test, expect } from "@playwright/test";
import { SignJWT } from "jose";
import {
  E2E_API_URL,
  E2E_SERVICE_JWT_SECRET,
  E2E_USER_SUB,
} from "../visual/auth";

// Runs under the `authed` project (baseURL :3001, DEV_AUTH_BYPASS=1). The API webServer
// runs with PIPELINE_MODE=recorded (playwright.config.ts) so a triggered run completes
// without live OpenAI/network calls.
//
// Targets the NET lane's on-demand trigger rate-limit: past run_cooldown_s (60s) /
// run_rate_limit_per_hour (10), POST /runs returns 429 with the frozen RateLimitError
// shape ({error: "rate_limited", retryAfterS}) — enforced by rate_limit_guard in
// routers/run.py and rendered by RateLimitedRoute in ratelimit.py.
//
// UI surfacing is deferred to M6 (decided) — the "Refresh now" flow doesn't show a
// rate-limit message today. It's also not currently *possible* to assert that shape
// through the Next BFF route: src/app/api/runs/route.ts calls bffFetch (lib/api/bff.ts),
// which on any non-ok upstream response discards the status and body and throws a bare
// `Error` — an uncaught throw in a Route Handler renders as a 500 with no body. Verified
// locally: triggering twice through /api/runs yields 201 then a bodyless 500, never the
// 429/RateLimitError shape. Fixing that pass-through is app code, out of scope for this
// spec-only change.
//
// So this spec asserts the real contract at the layer that actually carries it: FastAPI
// itself, over the network, via the harness's own uvicorn instance (the same one the BFF
// proxies to) — not a mock. It mints a service JWT the same way bffFetch does (same
// secret/issuer/audience/subject) and calls POST /api/v1/runs directly through
// page.request.
async function serviceToken(): Promise<string> {
  return new SignJWT({ email: "demo@specula.app", name: "Demo User" })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(E2E_USER_SUB)
    .setIssuer("specula-web")
    .setAudience("specula-api")
    .setIssuedAt()
    .setExpirationTime("60s")
    .sign(new TextEncoder().encode(E2E_SERVICE_JWT_SECRET));
}

test.describe("Run-trigger rate limit", () => {
  test("a trigger inside the cooldown returns 429 with the RateLimitError shape", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      try {
        sessionStorage.setItem("specula_intro", "1");
      } catch {}
    });

    // Confirm the real trigger affordance is on the page before going around it.
    await page.goto("/jobs");
    await expect(
      page.getByRole("heading", { name: "Jobs", level: 1 }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /refresh now/i }),
    ).toBeVisible();

    const headers = { Authorization: `Bearer ${await serviceToken()}` };
    const runsUrl = `${E2E_API_URL}/api/v1/runs`;

    // First trigger: 201 if the seeded demo user is outside its cooldown, or already
    // 429 if another spec triggered a run for the same shared demo tenant within the
    // last run_cooldown_s (all authed specs share one demo user + one in-process
    // limiter). Either is fine — not asserted on.
    await page.request.post(runsUrl, { headers });

    // Second trigger, immediately after: whatever the first result was, this one is
    // always inside an active cooldown window (either just started by our own first
    // call above, or already under way from another spec's trigger) — so it
    // deterministically rate-limits regardless of test execution order.
    const res = await page.request.post(runsUrl, { headers });
    expect(res.status()).toBe(429);
    const body = (await res.json()) as { error: string; retryAfterS: number };
    expect(body.error).toBe("rate_limited");
    expect(typeof body.retryAfterS).toBe("number");
    expect(body.retryAfterS).toBeGreaterThan(0);
  });
});
