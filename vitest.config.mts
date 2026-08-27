import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: [
      "lectures/**/typescript/**/*.test.ts",
      "projects/**/typescript/**/*.test.ts",
      "tools/**/typescript/**/*.test.ts",
    ],
    exclude: ["**/node_modules/**", "_reference/**"],
    // Fail-on-empty: zero discovered tests is an error, never a green run.
    passWithNoTests: false,
  },
});
