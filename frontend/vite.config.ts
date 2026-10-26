import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Library build of the <BrandList /> bundle (brandlist-mount contract): one ES module with React
// bundled in, so the Django page loads a single script and needs no import map.
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  // Library mode leaves process.env.NODE_ENV in place; the browser has no `process`.
  define: { "process.env.NODE_ENV": JSON.stringify(mode) },
  build: {
    lib: {
      entry: "src/main.tsx",
      formats: ["es"],
      fileName: () => "brand-list.js",
    },
    outDir: "dist",
  },
  test: {
    environment: "jsdom",
  },
}));
