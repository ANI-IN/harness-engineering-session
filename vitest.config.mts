import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: [
      "lectures/**/typescript/**/*.test.ts",
      "projects/**/typescript/**/*.test.ts",
    ],
    exclude: ["**/node_modules/**", "_reference/**"],
    passWithNoTests: true,
  },
});
