import { mkdir } from "node:fs/promises";
import { dirname } from "node:path";
import { chromium } from "@playwright/test";
import { encode } from "next-auth/jwt";
import {
  E2E_AUTH_SECRET,
  E2E_USER,
  SESSION_COOKIE,
  STORAGE_STATE,
  VISUAL_PORT,
} from "./auth";

// Mint a genuine Auth.js JWT session cookie and persist it as Playwright storage
// state, so every visual test starts authenticated against the production-build
// server (which has the dev bypass disabled). The cookie is signed with the same
// secret + salt the server decodes with, so `auth()` accepts it exactly like a
// real Google sign-in.
export default async function globalSetup(): Promise<void> {
  const value = await encode({
    token: {
      name: E2E_USER.name,
      email: E2E_USER.email,
      sub: "e2e-visual-user",
    },
    secret: E2E_AUTH_SECRET,
    salt: SESSION_COOKIE,
    maxAge: 60 * 60 * 24 * 30,
  });

  await mkdir(dirname(STORAGE_STATE), { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext();
  await context.addCookies([
    {
      name: SESSION_COOKIE,
      value,
      domain: "localhost",
      path: "/",
      httpOnly: true,
      sameSite: "Lax",
      expires: Math.floor(Date.now() / 1000) + 60 * 60 * 24 * 30,
    },
  ]);
  // Prove the session is accepted before the suite runs: a bad cookie name/secret
  // would silently redirect every view to /signin and quietly pass a wrong-looking
  // baseline. Fail loudly here instead.
  const page = await context.newPage();
  const res = await page.goto(`http://localhost:${VISUAL_PORT}/jobs`, {
    waitUntil: "domcontentloaded",
  });
  if (res && new URL(res.url()).pathname.startsWith("/signin")) {
    await browser.close();
    throw new Error(
      "Visual harness auth failed: /jobs redirected to /signin — the minted " +
        "session cookie was not accepted (check SESSION_COOKIE name / AUTH_SECRET).",
    );
  }

  await context.storageState({ path: STORAGE_STATE });
  await browser.close();
}
