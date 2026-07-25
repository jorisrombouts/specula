import { test, expect } from "@playwright/test";
import { SignJWT } from "jose";
import { E2E_API_URL, E2E_SERVICE_JWT_SECRET } from "../visual/auth";

// Runs under the `authed` project (baseURL :3001, DEV_AUTH_BYPASS=1). The API webServer
// runs with PIPELINE_MODE=recorded (playwright.config.ts) so a triggered run completes
// without live OpenAI/network calls.
//
// Targets the NET lane's on-demand trigger rate-limit: past run_cooldown_s (60s) /
// run_rate_limit_per_hour (10), POST /runs returns 429 with the frozen RateLimitError
// shape ({error: "rate_limited", retryAfterS}) — enforced by rate_limit_guard in
// routers/run.py and rendered by RateLimitedRoute in ratelimit.py.
//
// IMPORTANT — dedicated user, not the demo tenant: this spec triggers runs purely to
// exhaust a cooldown, which would otherwise leave the SHARED demo user rate-limited for
// the very next spec (refresh.spec.ts, alphabetically adjacent), making its "Refresh now"
// trigger 429 and its sidebar never reach "synced just now". The rate limit is per-user,
// so we mint for a throwaway sub instead — the API auto-provisions it (deps.py) — and the
// demo tenant stays clean. This isolation is the whole reason the spec passes a distinct
// subject below.
//
// Asserts the real contract at the layer that carries it: FastAPI over the network, via
// the harness's own uvicorn (the same one the BFF proxies to). Mints a service JWT the same
// way bffFetch does (secret/issuer/audience) and calls POST /api/v1/runs via page.request.
const RATELIMIT_SUB = "e2e-ratelimit-user";

async function serviceToken(): Promise<string> {
  return new SignJWT({
    email: "e2e-ratelimit@specula.app",
    name: "E2E Rate Limit",
  })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(RATELIMIT_SUB)
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

    // First trigger for the dedicated rate-limit user: 201 on a fresh limiter, or already
    // 429 if this same spec ran within the last run_cooldown_s against a reused server
    // (the in-process limiter is shared per API process). Either is fine — not asserted on.
    await page.request.post(runsUrl, { headers });

    // Second trigger, immediately after: whatever the first result was, this one is always
    // inside an active cooldown window (just started by our own first call above), so it
    // deterministically rate-limits.
    const res = await page.request.post(runsUrl, { headers });
    expect(res.status()).toBe(429);
    const body = (await res.json()) as { error: string; retryAfterS: number };
    expect(body.error).toBe("rate_limited");
    expect(typeof body.retryAfterS).toBe("number");
    expect(body.retryAfterS).toBeGreaterThan(0);
  });
});
