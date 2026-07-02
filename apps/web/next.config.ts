import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@specula/shared-types"],
  // Turbopack's on-disk persistent dev cache (default-on since Next 16.1) can
  // corrupt and panic on restore ("Every task must have a task type"). Disable it
  // — Turbopack still runs in-memory. Revert once the upstream bug is fixed.
  experimental: { turbopackFileSystemCacheForDev: false },
};

export default nextConfig;
