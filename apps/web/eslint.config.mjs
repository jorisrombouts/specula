import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import eslintConfigPrettier from "eslint-config-prettier";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // All Next dist-dir variants — the E2E authed server uses `.next-authed`, and
    // ad-hoc runs use their own `NEXT_DIST_DIR` (`.next-fw`, `.next-probe`, …). Ignore
    // every `.next*` so a stray build dir can't fail lint.
    ".next*/**",
    // Playwright HTML report + results are generated build artifacts, not source.
    "playwright-report/**",
    "test-results/**",
  ]),
  {
    // Playwright E2E specs/fixtures aren't React — the fixture `use` callback
    // (`await use(page)`) trips react-hooks/rules-of-hooks as if it were React's
    // `use()` hook. Scope that rule off for the e2e dir.
    files: ["e2e/**/*.ts"],
    rules: { "react-hooks/rules-of-hooks": "off" },
  },
  eslintConfigPrettier,
]);

export default eslintConfig;
