import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    // `next-auth` (pulled in transitively by lib/api/bff.ts -> @/auth) ships
    // extensionless internal imports like `next/server` that Node's strict ESM
    // resolution can't resolve when the package is externalized. Force it (and
    // `next`) through Vite's own resolver, which tolerates that, instead.
    server: {
      deps: {
        inline: [/next-auth/, /^next$/],
      },
    },
  },
});
