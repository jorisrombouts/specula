import { SignJWT } from "jose";
import { auth } from "@/auth";

// Server-side only. Mints a short-lived (60s) HS256 service JWT from the signed-in
// Auth.js session and calls FastAPI with it. The browser never calls FastAPI directly
// — only the Next server (route handlers / server components) does. The claim contract
// (alg / secret / iss / aud / sub=google_sub) must match FastAPI's `auth.py`.
export async function bffFetch<T = unknown>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const session = await auth();
  const sub = session?.user?.id;
  if (!sub) throw new Error("bffFetch: no authenticated session");

  const secretValue = process.env.SERVICE_JWT_SECRET;
  if (!secretValue) throw new Error("bffFetch: SERVICE_JWT_SECRET is not set");
  const secret = new TextEncoder().encode(secretValue);

  const token = await new SignJWT({
    email: session.user?.email ?? "",
    name: session.user?.name ?? "",
  })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(sub)
    .setIssuer("specula-web")
    .setAudience("specula-api")
    .setIssuedAt()
    .setExpirationTime("60s")
    .sign(secret);

  const base = process.env.API_URL ?? "http://localhost:8000";
  const res = await fetch(`${base}/api/v1${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(
      `bffFetch ${init?.method ?? "GET"} ${path} → ${res.status}`,
    );
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}
