import { SignJWT } from "jose";
import { getSession } from "@/auth";

type Identity = { sub: string; email: string; name: string };

// Resolve the caller's identity for the service JWT. Normally from the Auth.js session.
// Under the local dev auth bypass (double-gated so it can NEVER run in production, exactly
// like the (app)/layout.tsx gate) there is no real session, so mint for the seeded demo
// user — otherwise every API-backed page would 500 with "no authenticated session" when
// running with DEV_AUTH_BYPASS=1 (local UI work + the E2E harness).
async function resolveIdentity(): Promise<Identity | null> {
  const bypass =
    process.env.NODE_ENV !== "production" &&
    process.env.DEV_AUTH_BYPASS === "1";
  if (bypass) {
    return { sub: "demo-user", email: "demo@specula.app", name: "Demo User" };
  }
  const session = await getSession();
  if (!session?.user?.id) return null;
  return {
    sub: session.user.id,
    email: session.user.email ?? "",
    name: session.user.name ?? "",
  };
}

// Server-side only. Mints a short-lived (60s) HS256 service JWT from the caller's identity
// and calls FastAPI with it. The browser never calls FastAPI directly — only the Next
// server (route handlers / server components) does. The claim contract (alg / secret /
// iss / aud / sub=google_sub) must match FastAPI's `auth.py`.
async function bffRequest(path: string, init?: RequestInit): Promise<Response> {
  const identity = await resolveIdentity();
  if (!identity) throw new Error("bffFetch: no authenticated session");

  const secretValue = process.env.SERVICE_JWT_SECRET;
  if (!secretValue) throw new Error("bffFetch: SERVICE_JWT_SECRET is not set");
  const secret = new TextEncoder().encode(secretValue);

  const token = await new SignJWT({
    email: identity.email,
    name: identity.name,
  })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(identity.sub)
    .setIssuer("specula-web")
    .setAudience("specula-api")
    .setIssuedAt()
    .setExpirationTime("60s")
    .sign(secret);

  const base = process.env.API_URL ?? "http://localhost:8000";
  return fetch(`${base}/api/v1${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...init?.headers,
    },
    cache: "no-store",
  });
}

// Throws on a non-2xx response — the right default for most routes.
export async function bffFetch<T = unknown>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await bffRequest(path, init);
  if (!res.ok) {
    throw new Error(
      `bffFetch ${init?.method ?? "GET"} ${path} → ${res.status}`,
    );
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

// Like bffFetch but returns the raw Response without throwing on non-2xx, so a route can
// forward FastAPI's real status + body to the client (e.g. a 429 rate-limit the user should
// see) instead of collapsing every failure into an opaque 500.
export async function bffFetchRaw(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  return bffRequest(path, init);
}
