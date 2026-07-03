import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@specula/shared-types"],
  // Turbopack's on-disk persistent dev cache (default-on since Next 16.1) can
  // corrupt and panic on restore ("Every task must have a task type"). Disable it
  // — Turbopack still runs in-memory. Revert once the upstream bug is fixed.
  experimental: { turbopackFileSystemCacheForDev: false },
  // Our E2E harness runs two `next dev` instances from this same apps/web dir
  // (:3000 public + :3001 DEV_AUTH_BYPASS for authed specs). `next dev` writes
  // build state to a per-directory `<distDir>/dev` (locked by default in Next
  // 16.2) — two instances sharing it corrupt each other's route manifests
  // (intermittent 404s). Give the bypass instance its own dist dir so both can
  // run concurrently and safely.
  ...(process.env.NEXT_DIST_DIR ? { distDir: process.env.NEXT_DIST_DIR } : {}),
};

export default nextConfig;
