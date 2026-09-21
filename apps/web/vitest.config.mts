import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL(".", import.meta.url)),
    },
  },
  test: {
    // Component tests (.test.tsx) opt into a DOM via a
    // `// @vitest-environment jsdom` comment at the top of the file;
    // plain .test.ts files (e.g. lib/api.test.ts) stay on this lighter
    // default.
    environment: "node",
    include: ["**/*.test.ts", "**/*.test.tsx"],
  },
});
