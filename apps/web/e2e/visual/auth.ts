// Constants for the production-build visual harness.
//
// The visual suite screenshots a real `next build && next start` server (no dev
// overlay, no on-demand compilation — deterministic by construction). Production
// disables the dev auth bypass, so instead of the bypass we authenticate the way
// the real app does: a genuine, signed Auth.js JWT session cookie, minted in
// global-setup and injected via storageState.
//
// This never touches production. It is a throwaway secret used only to sign a
// local cookie for a local server; the deployed app has its own AUTH_SECRET and no
// bypass. `src/app/(app)/layout.tsx` is unchanged — the bypass stays gated on
// `NODE_ENV !== "production"`, which is impossible on Vercel.
export const E2E_AUTH_SECRET =
  "specula-visual-e2e-secret-not-for-production-do-not-reuse";

// Auth.js names the JWT session cookie `authjs.session-token` over http (the
// `__Secure-` prefix is added only for https). The visual server runs on
// http://localhost, so this is both the cookie name and the encode `salt`.
export const SESSION_COOKIE = "authjs.session-token";

// The user encoded into the session — chosen so the rendered sidebar reads exactly
// like the local `DEV_AUTH_BYPASS` user, keeping the views visually identical.
export const E2E_USER = { name: "Dev (bypass)", email: "dev@local" } as const;

// Where global-setup writes the authenticated storage state the tests load.
export const STORAGE_STATE = "e2e/visual/.auth/state.json";

// The port the production-build visual server listens on.
export const VISUAL_PORT = 3002;
