import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const eslintConfig = [
  // Build output and dependencies were never excluded here — `npm run
  // lint` (bare `eslint`, no path argument) was therefore linting
  // compiled/minified files under .next/ as if they were source,
  // producing thousands of false-positive errors (single-letter
  // variables in a minified bundle trip no-unused-vars/no-explicit-any
  // constantly). This was masked during development because every prior
  // verification pass explicitly scoped the command to `eslint src`
  // instead of running the actual npm script. Fixed by ignoring build
  // output and other non-source directories globally, matching
  // Next.js's own documented flat-config recommendation.
  {
    ignores: ["node_modules/**", ".next/**", "out/**", "build/**", "coverage/**", "next-env.d.ts"],
  },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
];

export default eslintConfig;
